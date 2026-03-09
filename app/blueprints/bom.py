import csv
import io
import re
import difflib
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Component, ComponentHistory, Order, Product, BomItem, Group, Housing, ComponentLibrary
from app.forms import ProductForm, BomImportForm, ProduceForm

bom_bp = Blueprint('bom', __name__, url_prefix='/products')


# ── CSV parser ────────────────────────────────────────────────────────────────

def _parse_bom_csv(file_bytes: bytes) -> list:
    """Parse JLCPCB/EasyEDA BOM CSV. Handles UTF-16 LE, UTF-8 BOM, plain UTF-8."""
    if file_bytes[:2] == b'\xff\xfe':
        text = file_bytes[2:].decode('utf-16-le')
    elif file_bytes[:3] == b'\xef\xbb\xbf':
        text = file_bytes[3:].decode('utf-8')
    else:
        try:
            text = file_bytes.decode('utf-8')
        except UnicodeDecodeError:
            text = file_bytes.decode('utf-16')

    # Remove null bytes from UTF-16 that may remain
    text = text.replace('\x00', '')

    reader = csv.DictReader(io.StringIO(text), delimiter='\t')
    rows = []
    for row in reader:
        cleaned = {(k or '').strip(): (v or '').strip().strip('"') for k, v in row.items() if k}
        if any(cleaned.values()):
            rows.append(cleaned)
    return rows


# ── Duplicate analysis ────────────────────────────────────────────────────────

# Known SMD package sizes (longest first so 01005 matches before 1005)
_SMD_PACKAGES = ['01005', '2512', '2010', '1812', '1210', '1206', '0805', '0603', '0402', '0201']
# Aliases: non-standard → canonical
_FP_ALIASES = {'06003': '0603', '08005': '0805', '12006': '1206'}


def _norm_fp(fp: str) -> str:
    """Normalize footprint string to canonical SMD package code."""
    if not fp:
        return ''
    s = re.sub(r'[^A-Za-z0-9]', '', fp).upper()
    # Strip leading component-type letter(s): R0603 → 0603, C0402 → 0402
    stripped = re.sub(r'^[RCLDUQFBT]+', '', s)
    for candidate in (stripped, s):
        if candidate in _FP_ALIASES:
            return _FP_ALIASES[candidate]
        for pkg in _SMD_PACKAGES:
            if candidate == pkg or candidate.startswith(pkg):
                return pkg
    return stripped or s


_SI_MULT = {
    'p': 1e-12, 'P': 1e-12,
    'n': 1e-9,  'N': 1e-9,
    'u': 1e-6,  'U': 1e-6,  'µ': 1e-6,  'μ': 1e-6,
    'm': 1e-3,
    'k': 1e3,   'K': 1e3,
    'M': 1e6,
    'G': 1e9,
    'R': 1.0,   'r': 1.0,   'Ω': 1.0,
    '':  1.0,
}

# Maps unit strings (Russian + SI, lowercase) → multiplier to base unit
_UNIT_MULT = {
    # Capacitance → Farads
    'пф': 1e-12, 'пф.': 1e-12,
    'нф': 1e-9,  'нф.': 1e-9,
    'мкф': 1e-6, 'мкф.': 1e-6,
    'мф': 1e-3,
    'ф': 1.0,
    'pf': 1e-12, 'nf': 1e-9, 'uf': 1e-6, 'µf': 1e-6, 'μf': 1e-6, 'f': 1.0,
    # Resistance → Ohms
    'ом': 1.0, 'ω': 1.0, 'ohm': 1.0,
    'ком': 1e3, 'кω': 1e3, 'kohm': 1e3,
    'мом': 1e6, 'мω': 1e6, 'mohm': 1e6,
    'r': 1.0, 'k': 1e3, 'kΩ': 1e3, 'mΩ': 1e6,
    # Inductance → Henries
    'нгн': 1e-9,  'nh': 1e-9,
    'мкгн': 1e-6, 'µh': 1e-6, 'μh': 1e-6, 'uh': 1e-6,
    'мгн': 1e-3,  'mh': 1e-3,
    'гн': 1.0,    'h': 1.0,
    # Voltage → Volts
    'мв': 1e-3, 'mv': 1e-3,
    'в': 1.0,   'v': 1.0,
    'кв': 1e3,  'kv': 1e3,
    # Current → Amperes
    'мка': 1e-6, 'µa': 1e-6, 'ua': 1e-6,
    'ма': 1e-3,  'ma': 1e-3,
    'а': 1.0,    'a': 1.0,
    # Frequency → Hz
    'гц': 1.0,   'hz': 1.0,
    'кгц': 1e3,  'khz': 1e3,
    'мгц': 1e6,  'mhz': 1e6,
    'ггц': 1e9,  'ghz': 1e9,
    # Dimensionless / count
    'шт': None, '': None,
}


def _comp_base_value(comp) -> float | None:
    """Return component's nominal value in base SI units.

    Tries (in order):
      1. Parse comp.name as a value string (e.g. '100n', '4.7k')
      2. Combine comp.nominal_value + comp.unit using _UNIT_MULT table
    """
    v = _parse_value(comp.name)
    if v is not None:
        return v
    if comp.nominal_value is not None:
        unit_key = (comp.unit or '').strip().lower()
        mult = _UNIT_MULT.get(unit_key)
        if mult is not None:
            return comp.nominal_value * mult
    return None


def _parse_value(val: str):
    """
    Parse component value to a float in base units.
    Handles: 1k, 1K, 100R, 4.7k, 0.1u, 100n, 100nF, 4.7uF, 10pF,
             4k7, 4R7, 1n0, 2M2 (EIA letter-as-decimal notation) …
    Returns float or None.
    """
    if not val:
        return None
    v = re.sub(r'\s+', '', val)

    # EIA notation: 4k7 → 4.7k, 4R7 → 4.7Ω, 1n0 → 1.0nF
    m = re.match(r'^(\d+)([pPnNuUµμmMkKGRrΩ])(\d+)([FfHh]?)$', v)
    if m:
        try:
            int_part = int(m.group(1))
            dec_str  = m.group(3)
            num = int_part + int(dec_str) / (10 ** len(dec_str))
            mult = _SI_MULT.get(m.group(2), None)
            if mult is not None:
                return num * mult
        except (ValueError, ZeroDivisionError):
            pass

    # Standard notation: 4.7k, 100n, 0.1u, 100R, 10pF …
    m = re.match(r'^(\d+(?:[.,]\d+)?)([pPnNuUµμmMkKGRrΩ]?)([FfHhΩohm]*)?$', v)
    if not m:
        return None
    try:
        num = float(m.group(1).replace(',', '.'))
    except ValueError:
        return None
    mult = _SI_MULT.get(m.group(2) or '', None)
    if mult is None:
        return None
    return num * mult


def _find_bom_duplicates(items):
    """
    Find groups of BOM items that look like duplicates or near-duplicates.
    Returns list of {'items': [...], 'reason': str, 'type': str}
    """
    groups = []
    seen = set()

    def add(group_items, reason, kind):
        key = frozenset(i.id for i in group_items)
        if key not in seen and len(group_items) >= 2:
            seen.add(key)
            groups.append({'entries': list(group_items), 'reason': reason, 'type': kind})

    # 1. Same parsed numeric value
    by_val = defaultdict(list)
    for item in items:
        v = _parse_value(item.name)
        if v is not None:
            by_val[f'{v:.8e}'].append(item)

    for key, grp in by_val.items():
        if len(grp) < 2:
            continue
        fps = [_norm_fp(i.footprint or '') for i in grp]
        unique_fps = set(fps)
        if len(unique_fps) == 1:
            add(grp, 'Одинаковый номинал и одинаковый корпус', 'exact')
        else:
            fps_str = ', '.join(sorted(unique_fps))
            add(grp, f'Одинаковый номинал, разные корпуса ({fps_str})', 'diff_fp')

    # 2. Same name (case-insensitive), different footprints
    by_name = defaultdict(list)
    for item in items:
        by_name[item.name.strip().upper()].append(item)
    for key, grp in by_name.items():
        if len(grp) < 2:
            continue
        fps = set(_norm_fp(i.footprint or '') for i in grp)
        if len(fps) > 1:
            add(grp, f'Одинаковое название «{grp[0].name}», разные корпуса ({", ".join(sorted(fps))})', 'diff_fp')

    # 3. Same Manufacturer Part (non-empty)
    by_mfr = defaultdict(list)
    for item in items:
        mp = (item.manufacturer_part or '').strip()
        if mp:
            by_mfr[mp.upper()].append(item)
    for key, grp in by_mfr.items():
        if len(grp) >= 2:
            add(grp, f'Одинаковый Manufacturer Part: {grp[0].manufacturer_part}', 'same_mfr')

    return groups


# ── Auto-match ────────────────────────────────────────────────────────────────

def _val_key(v: float) -> str:
    """Canonical string key for a parsed float value (8 significant digits)."""
    return f'{v:.8e}'


def _auto_match(item: BomItem):
    """
    Match a BOM item to a warehouse component.

    Priority:
      1. Exact Manufacturer Part → confidence 1.0
      2. Exact Name match        → confidence 0.95
      3. Normalized value + same footprint/housing  → confidence 0.90
      4. Normalized value, unique match (no housing) → confidence 0.75
      5. Normalized value, multiple matches, pick by stock → confidence 0.70
      6. Fuzzy name match (len > 4, ratio ≥ 0.60)   → confidence = ratio
    """
    active = Component.query.filter_by(is_archived=False)

    # ── 1. Exact Manufacturer Part ──────────────────────────────────────────
    mfr = (item.manufacturer_part or '').strip()
    if mfr and mfr not in ('?', '-', ''):
        c = active.filter(Component.name.ilike(mfr)).first()
        if not c:
            c = active.filter(Component.name.ilike(f'%{mfr}%')).first()
        if c:
            return c, 1.0

    # ── 2. Exact Name match ─────────────────────────────────────────────────
    c = active.filter(Component.name.ilike(item.name)).first()
    if c:
        return c, 0.95

    # ── 3–5. Normalized value matching ─────────────────────────────────────
    parsed = _parse_value(item.name)
    fp_canon = _norm_fp(item.footprint or '')

    all_comps = active.all()  # loaded once, reused by fuzzy step too

    if parsed is not None:
        target_key = _val_key(parsed)

        # Buckets: value+footprint match / value-only match
        fp_matches = []
        val_matches = []

        for comp in all_comps:
            comp_val = _comp_base_value(comp)
            if comp_val is None:
                continue
            if _val_key(comp_val) != target_key:
                continue

            # Value matches — now check footprint/housing
            val_matches.append(comp)
            if fp_canon:
                housing_name = comp.housing.housing_name if comp.housing else ''
                if _norm_fp(housing_name) == fp_canon:
                    fp_matches.append(comp)

        # 3. Value + footprint match — prefer most stock
        if fp_matches:
            best = max(fp_matches, key=lambda c: c.quantity)
            return best, 0.90

        # 4. Unique value match (no ambiguity)
        if len(val_matches) == 1:
            return val_matches[0], 0.75

        # 5. Multiple value matches — pick by highest stock
        if val_matches:
            best = max(val_matches, key=lambda c: c.quantity)
            return best, 0.70

    # ── 6. Fuzzy name match ─────────────────────────────────────────────────
    if len(item.name) > 4:
        best_ratio, best_comp = 0.0, None
        name_lower = item.name.lower()
        for comp in all_comps:
            ratio = difflib.SequenceMatcher(None, name_lower, comp.name.lower()).ratio()
            if ratio > best_ratio:
                best_ratio, best_comp = ratio, comp
        if best_ratio >= 0.60:
            return best_comp, best_ratio

    return None, 0.0


# ── Routes ────────────────────────────────────────────────────────────────────

@bom_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('main.index'))

    form = ProductForm()
    if form.validate_on_submit():
        if not (current_user.role == 'super_admin' or current_user.can_create_components):
            flash('Нет прав для создания изделий', 'error')
        else:
            product = Product(
                name=form.name.data.strip(),
                description=form.description.data,
                created_by_id=current_user.id,
            )
            db.session.add(product)
            try:
                db.session.commit()
                flash(f'Изделие «{product.name}» создано', 'success')
                return redirect(url_for('bom.view', id=product.id))
            except Exception:
                db.session.rollback()
                flash('Изделие с таким названием уже существует', 'error')

    products = Product.query.order_by(Product.created_at.desc()).all()
    return render_template('products.html', products=products, form=form)


@bom_bp.route('/<int:id>')
@login_required
def view(id):
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('main.index'))

    product = Product.query.get_or_404(id)
    item_status = []
    for item in product.bom_items:
        available = item.component.quantity if item.component else 0
        item_status.append({
            'item': item,
            'available': available,
            'sufficient': available >= item.quantity,
        })
    duplicate_groups = _find_bom_duplicates(product.bom_items)
    produce_form = ProduceForm()
    all_groups = Group.query.order_by(Group.name).all()
    all_housings = Housing.query.order_by(Housing.housing_name).all()
    return render_template('product_view.html', product=product,
                           item_status=item_status, produce_form=produce_form,
                           duplicate_groups=duplicate_groups,
                           all_groups=all_groups, all_housings=all_housings)


@bom_bp.route('/import', methods=['GET', 'POST'])
@login_required
def import_bom():
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для импорта BOM', 'error')
        return redirect(url_for('bom.index'))

    form = BomImportForm()
    if form.validate_on_submit():
        file = form.bom_file.data
        file_bytes = file.read()

        try:
            rows = _parse_bom_csv(file_bytes)
        except Exception as e:
            flash(f'Ошибка разбора CSV: {e}', 'error')
            return render_template('bom_import.html', form=form)

        if not rows:
            flash('CSV-файл пуст или не содержит данных', 'error')
            return render_template('bom_import.html', form=form)

        # Determine product name
        product_name = (form.product_name.data or '').strip()
        if not product_name:
            stem = (file.filename or 'BOM').rsplit('.', 1)[0]
            parts = stem.split('_')
            if len(parts) >= 3 and parts[0].upper() == 'BOM':
                product_name = '_'.join(parts[1:-1])
            elif len(parts) >= 2 and parts[0].upper() == 'BOM':
                product_name = '_'.join(parts[1:])
            else:
                product_name = stem

        # Create or replace
        product = Product.query.filter_by(name=product_name).first()
        if product:
            BomItem.query.filter_by(product_id=product.id).delete()
        else:
            product = Product(name=product_name, created_by_id=current_user.id)
            db.session.add(product)
            db.session.flush()

        # Column name map (EasyEDA export uses these exact names)
        COL = {
            'id':        'ID',
            'name':      'Name',
            'des':       'Designator',
            'fp':        'Footprint',
            'qty':       'Quantity',
            'mfr_part':  'Manufacturer Part',
            'mfr':       'Manufacturer',
            'supplier':  'Supplier',
            'sup_part':  'Supplier Part',
            'price':     'Price',
        }

        count = 0
        for row in rows:
            try:
                qty = int(row.get(COL['qty'], '1') or 1)
            except ValueError:
                qty = 1
            try:
                price = float(row.get(COL['price'], '') or '')
            except ValueError:
                price = None

            db.session.add(BomItem(
                product_id=product.id,
                bom_id=row.get(COL['id'], ''),
                name=row.get(COL['name'], '') or 'Без названия',
                designator=row.get(COL['des'], '') or None,
                footprint=row.get(COL['fp'], '') or None,
                quantity=qty,
                manufacturer_part=row.get(COL['mfr_part'], '') or None,
                manufacturer=row.get(COL['mfr'], '') or None,
                supplier=row.get(COL['supplier'], '') or None,
                supplier_part=row.get(COL['sup_part'], '') or None,
                price=price,
            ))
            count += 1

        db.session.commit()
        flash(f'Импортировано {count} позиций для «{product_name}»', 'success')
        return redirect(url_for('bom.match', id=product.id))

    return render_template('bom_import.html', form=form)


@bom_bp.route('/<int:id>/match', methods=['GET', 'POST'])
@login_required
def match(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('Нет прав для сопоставления', 'error')
        return redirect(url_for('bom.index'))

    product = Product.query.get_or_404(id)

    if request.method == 'POST':
        for item in product.bom_items:
            raw = request.form.get(f'component_{item.id}', '0')
            try:
                comp_id = int(raw)
            except ValueError:
                comp_id = 0
            if comp_id:
                item.component_id = comp_id
                item.match_confidence = 1.0
            else:
                item.component_id = None
                item.match_confidence = None
        db.session.commit()
        flash('Сопоставление сохранено', 'success')
        return redirect(url_for('bom.view', id=product.id))

    # GET: auto-match unmatched (or all if ?rematch=1)
    rematch = request.args.get('rematch') == '1'
    for item in product.bom_items:
        if item.component_id is None or rematch:
            comp, conf = _auto_match(item)
            item.component_id = comp.id if comp else None
            item.match_confidence = conf if comp else None
    db.session.commit()

    all_components = (Component.query
                      .filter_by(is_archived=False)
                      .order_by(Component.name).all())
    all_groups = Group.query.order_by(Group.name).all()
    all_housings = Housing.query.order_by(Housing.housing_name).all()
    from app.forms import ProduceForm
    csrf_form = ProduceForm()
    return render_template('bom_match.html', product=product, all_components=all_components,
                           csrf_form=csrf_form, all_groups=all_groups, all_housings=all_housings)


@bom_bp.route('/<int:id>/produce', methods=['POST'])
@login_required
def produce(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('Нет прав для списания', 'error')
        return redirect(url_for('bom.view', id=id))

    product = Product.query.get_or_404(id)
    try:
        n = max(1, int(request.form.get('quantity', 1)))
    except ValueError:
        flash('Некорректное количество', 'error')
        return redirect(url_for('bom.view', id=id))

    results = []
    for item in product.bom_items:
        required = item.quantity * n
        comp = item.component
        if comp is None:
            results.append({'item': item, 'required': required,
                            'deducted': 0, 'shortage': required, 'status': 'unmatched'})
            continue

        to_deduct = min(comp.quantity, required)
        shortage = required - to_deduct
        if to_deduct > 0:
            old_qty = comp.quantity
            comp.quantity -= to_deduct
            db.session.add(ComponentHistory(
                unique_id=comp.unique_id,
                user_id=current_user.id,
                action='bom_writeoff',
                field_changed='quantity',
                old_value=str(old_qty),
                new_value=str(comp.quantity),
                timestamp=datetime.utcnow(),
            ))
        status = 'ok' if shortage == 0 else ('partial' if to_deduct > 0 else 'missing')
        results.append({'item': item, 'required': required,
                        'deducted': to_deduct, 'shortage': shortage, 'status': status})

    db.session.commit()
    total_short = sum(r['shortage'] for r in results)
    if total_short == 0:
        flash(f'Компоненты для {n} изделий успешно списаны', 'success')
    else:
        flash(f'Списание выполнено, нехватка: {total_short} позиций', 'error')

    produce_form = ProduceForm()
    return render_template('produce_result.html', product=product, results=results, n=n, produce_form=produce_form)


@bom_bp.route('/<int:id>/order', methods=['POST'])
@login_required
def order_missing(id):
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для создания заказов', 'error')
        return redirect(url_for('bom.view', id=id))

    product = Product.query.get_or_404(id)
    try:
        n = max(1, int(request.form.get('quantity', 1)))
    except ValueError:
        n = 1

    created, unmatched = 0, 0
    for item in product.bom_items:
        required = item.quantity * n
        if item.component is None:
            unmatched += 1
            continue
        shortage = required - item.component.quantity
        if shortage > 0:
            db.session.add(Order(
                component_id=item.component_id,
                quantity=shortage,
                date=datetime.utcnow(),
                user_id=current_user.id,
            ))
            created += 1

    db.session.commit()
    if created:
        flash(f'Создано {created} заказов на пополнение склада', 'success')
    else:
        flash('Нет недостающих компонентов для заказа', 'success')
    if unmatched:
        flash(f'{unmatched} позиций BOM не сопоставлены со складом', 'error')

    return redirect(url_for('orders.index'))


@bom_bp.route('/<int:id>/bom/<int:item_id>/edit', methods=['POST'])
@login_required
def edit_bom_item(id, item_id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('Нет прав для редактирования', 'error')
        return redirect(url_for('bom.match', id=id))

    item = BomItem.query.get_or_404(item_id)
    if item.product_id != id:
        flash('Позиция не принадлежит этому изделию', 'error')
        return redirect(url_for('bom.match', id=id))

    item.name = request.form.get('name', '').strip() or item.name
    try:
        item.quantity = max(1, int(request.form.get('quantity', item.quantity)))
    except ValueError:
        pass
    item.designator = request.form.get('designator', '').strip() or None
    item.footprint = request.form.get('footprint', '').strip() or None
    item.manufacturer_part = request.form.get('manufacturer_part', '').strip() or None
    db.session.commit()
    flash('Позиция BOM обновлена', 'success')
    back = request.args.get('back')
    if back == 'view':
        return redirect(url_for('bom.view', id=id))
    return redirect(url_for('bom.match', id=id))


@bom_bp.route('/<int:id>/merge', methods=['POST'])
@login_required
def merge_items(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('Нет прав для объединения', 'error')
        return redirect(url_for('bom.match', id=id))

    raw_ids = request.form.getlist('item_ids')
    item_ids = []
    for v in raw_ids:
        for part in v.split(','):
            try:
                item_ids.append(int(part.strip()))
            except ValueError:
                pass
    item_ids = list(dict.fromkeys(item_ids))  # deduplicate, preserve order

    if len(item_ids) < 2:
        flash('Выберите минимум 2 позиции для объединения', 'error')
        return redirect(url_for('bom.match', id=id))

    items = BomItem.query.filter(
        BomItem.id.in_(item_ids), BomItem.product_id == id
    ).all()
    if len(items) < 2:
        flash('Позиции не найдены', 'error')
        return redirect(url_for('bom.match', id=id))

    primary = items[0]
    primary.quantity = sum(i.quantity for i in items)
    designators = [i.designator for i in items if i.designator]
    primary.designator = ', '.join(designators) or None
    for item in items[1:]:
        db.session.delete(item)
    db.session.commit()
    flash(f'Объединено {len(items)} позиций в одну', 'success')
    back = request.args.get('back')
    if back == 'view':
        return redirect(url_for('bom.view', id=id))
    return redirect(url_for('bom.match', id=id))


@bom_bp.route('/<int:id>/bom/<int:item_id>/create_component', methods=['POST'])
@login_required
def create_component_from_bom(id, item_id):
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для создания компонентов', 'error')
        return redirect(url_for('bom.match', id=id))

    item = BomItem.query.get_or_404(item_id)
    if item.product_id != id:
        flash('Позиция не принадлежит этому изделию', 'error')
        return redirect(url_for('bom.match', id=id))

    name = request.form.get('name', '').strip() or item.manufacturer_part or item.name
    try:
        type_id = int(request.form.get('type_id', 0))
    except ValueError:
        type_id = 0
    if not type_id:
        flash('Укажите тип компонента', 'error')
        return redirect(url_for('bom.match', id=id))

    housing_id = request.form.get('housing_id', type=int) or None
    manufacturer = request.form.get('manufacturer', '').strip() or item.manufacturer or None

    existing = Component.query.filter_by(name=name, type_id=type_id, housing_id=housing_id).first()
    if existing:
        item.component_id = existing.id
        item.match_confidence = 1.0
        db.session.commit()
        flash(f'Связано с существующим компонентом «{existing.name}»', 'success')
        return redirect(url_for('bom.match', id=id))

    comp = Component(
        name=name,
        type_id=type_id,
        housing_id=housing_id,
        manufacturer=manufacturer,
        quantity=0,
        created_by_id=current_user.id,
        is_archived=False,
    )
    db.session.add(comp)
    db.session.flush()
    db.session.add(ComponentHistory(
        unique_id=comp.unique_id,
        user_id=current_user.id,
        action='create',
        timestamp=datetime.utcnow(),
    ))
    item.component_id = comp.id
    item.match_confidence = 1.0
    db.session.commit()
    flash(f'Компонент «{comp.name}» создан и связан с позицией BOM', 'success')
    return redirect(url_for('bom.match', id=id))


@bom_bp.route('/<int:id>/bom/<int:item_id>/add_to_library', methods=['POST'])
@login_required
def add_to_library(id, item_id):
    back = request.args.get('back', '')

    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для добавления в библиотеку', 'error')
        return redirect(url_for('bom.view' if back == 'view' else 'bom.match', id=id))

    item = BomItem.query.get_or_404(item_id)
    if item.product_id != id:
        flash('Позиция не принадлежит этому изделию', 'error')
        return redirect(url_for('bom.view' if back == 'view' else 'bom.match', id=id))

    name = request.form.get('name', '').strip() or item.manufacturer_part or item.name
    try:
        type_id = int(request.form.get('type_id', 0))
    except ValueError:
        type_id = 0
    if not type_id:
        flash('Укажите тип компонента', 'error')
        return redirect(url_for('bom.match', id=id))

    housing_id = request.form.get('housing_id', type=int) or None
    manufacturer = request.form.get('manufacturer', '').strip() or item.manufacturer or None
    description = request.form.get('description', '').strip() or None

    existing = ComponentLibrary.query.filter_by(name=name, type_id=type_id, housing_id=housing_id).first()
    if existing:
        flash(f'«{name}» уже есть в библиотеке', 'info')
        return redirect(url_for('bom.view' if back == 'view' else 'bom.match', id=id))

    from sqlalchemy.exc import IntegrityError
    lib = ComponentLibrary(
        name=name,
        type_id=type_id,
        housing_id=housing_id,
        manufacturer=manufacturer,
        description=description,
    )
    db.session.add(lib)
    try:
        db.session.commit()
        flash(f'«{lib.name}» добавлен в библиотеку', 'success')
    except IntegrityError:
        db.session.rollback()
        flash('Компонент с таким именем/типом/корпусом уже существует в библиотеке', 'error')
    return redirect(url_for('bom.view' if back == 'view' else 'bom.match', id=id))


@bom_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_components):
        flash('Нет прав для удаления изделий', 'error')
        return redirect(url_for('bom.index'))

    product = Product.query.get_or_404(id)
    db.session.delete(product)
    db.session.commit()
    flash(f'Изделие «{product.name}» удалено', 'success')
    return redirect(url_for('bom.index'))

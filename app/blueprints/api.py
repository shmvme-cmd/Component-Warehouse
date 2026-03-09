import json
import os
import urllib.request
import urllib.error
import re

from flask import Blueprint, jsonify, request
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from sqlalchemy import or_

from app.extensions import db
from app.models import Group, Subgroup, ComponentType, Housing, ComponentLibrary, Component

api_bp = Blueprint('api', __name__)


@api_bp.route('/api/library/search')
@login_required
def library_search():
    q = request.args.get('q', '').strip()
    if not q or len(q) < 1:
        return jsonify([])
    items = (ComponentLibrary.query
             .outerjoin(ComponentType, ComponentLibrary.type_id == ComponentType.id)
             .outerjoin(Housing, ComponentLibrary.housing_id == Housing.id)
             .filter(or_(
                 ComponentLibrary.name.ilike(f'%{q}%'),
                 ComponentLibrary.manufacturer.ilike(f'%{q}%'),
                 ComponentLibrary.description.ilike(f'%{q}%'),
                 ComponentType.name.ilike(f'%{q}%'),
                 Housing.housing_name.ilike(f'%{q}%'),
             ))
             .order_by(ComponentLibrary.name)
             .limit(30).all())
    results = []
    for it in items:
        results.append({
            'id': it.id,
            'name': it.name,
            'group': it.comp_type.subgroup.group.name if it.comp_type else '—',
            'subgroup': it.comp_type.subgroup.name if it.comp_type else '—',
            'type': it.comp_type.name if it.comp_type else '—',
            'housing': it.housing.housing_name if it.housing else '',
            'nominal': f"{it.nominal_value} {it.unit or ''}".strip() if it.nominal_value else '',
            'manufacturer': it.manufacturer or '',
        })
    return jsonify(results)


@api_bp.route('/api/components/search')
@login_required
def components_search():
    q = request.args.get('q', '').strip()
    if not q:
        return jsonify([])
    query = (Component.query
             .filter_by(is_archived=False)
             .outerjoin(ComponentType, Component.type_id == ComponentType.id)
             .outerjoin(Housing,       Component.housing_id == Housing.id)
             .filter(or_(
                 Component.name.ilike(f'%{q}%'),
                 Component.manufacturer.ilike(f'%{q}%'),
                 ComponentType.name.ilike(f'%{q}%'),
                 Housing.housing_name.ilike(f'%{q}%'),
             )))
    if current_user.role == 'admin':
        query = query.filter(Component.created_by_id == current_user.id)
    items = query.order_by(Component.name).limit(100).all()
    results = []
    for it in items:
        results.append({
            'id': it.id,
            'name': it.name,
            'group':    it.comp_type.subgroup.group.name if it.comp_type else '—',
            'subgroup': it.comp_type.subgroup.name       if it.comp_type else '—',
            'type':     it.comp_type.name                if it.comp_type else '—',
            'housing':  it.housing.housing_name          if it.housing   else '',
            'nominal':  f"{it.nominal_value} {it.unit or ''}".strip() if it.nominal_value else '',
            'manufacturer': it.manufacturer or '',
            'quantity': it.quantity,
        })
    return jsonify(results)


@api_bp.route('/get_subgroups/<int:group_id>')
def get_subgroups(group_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_subgroups)):
        return jsonify([])
    subgroups = Subgroup.query.filter_by(group_id=group_id).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subgroups])


@api_bp.route('/get_types/<int:subgroup_id>')
def get_types(subgroup_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_types)):
        return jsonify([])
    types = ComponentType.query.filter_by(subgroup_id=subgroup_id).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in types])


@api_bp.route('/get_units/<int:subgroup_id>')
def get_units(subgroup_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_subgroups)):
        return jsonify([])
    subgroup = Subgroup.query.get(subgroup_id)
    if subgroup:
        units = json.loads(subgroup.units_schema)
        return jsonify([{'unit': u} for u in units])
    return jsonify([])


@api_bp.route('/api/create_group', methods=['POST'])
@login_required
def create_group():
    if not (current_user.role == 'super_admin' or current_user.can_create_groups):
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Название обязательно'}), 400
    try:
        g = Group(name=name)
        db.session.add(g)
        db.session.commit()
        return jsonify({'id': g.id, 'name': g.name})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Группа с таким названием уже существует'}), 409


@api_bp.route('/api/create_subgroup', methods=['POST'])
@login_required
def create_subgroup():
    if not (current_user.role == 'super_admin' or current_user.can_create_subgroups):
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json()
    name = (data.get('name') or '').strip()
    group_id = data.get('group_id')
    units_raw = (data.get('units') or '').strip()
    if not name or not group_id:
        return jsonify({'error': 'Название и группа обязательны'}), 400
    if not Group.query.get(group_id):
        return jsonify({'error': 'Группа не найдена'}), 404
    units = [u.strip() for u in units_raw.split(',') if u.strip()] or ['шт']
    try:
        s = Subgroup(name=name, group_id=group_id, units_schema=json.dumps(units, ensure_ascii=False))
        db.session.add(s)
        db.session.commit()
        return jsonify({'id': s.id, 'name': s.name})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Подгруппа с таким названием уже существует в этой группе'}), 409


@api_bp.route('/api/create_type', methods=['POST'])
@login_required
def create_type():
    if not (current_user.role == 'super_admin' or current_user.can_create_types):
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json()
    name = (data.get('name') or '').strip()
    subgroup_id = data.get('subgroup_id')
    if not name or not subgroup_id:
        return jsonify({'error': 'Название и подгруппа обязательны'}), 400
    if not Subgroup.query.get(subgroup_id):
        return jsonify({'error': 'Подгруппа не найдена'}), 404
    try:
        t = ComponentType(name=name, subgroup_id=subgroup_id)
        db.session.add(t)
        db.session.commit()
        return jsonify({'id': t.id, 'name': t.name})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Тип с таким названием уже существует в этой подгруппе'}), 409


@api_bp.route('/api/create_housing', methods=['POST'])
@login_required
def create_housing():
    if not (current_user.role == 'super_admin' or current_user.can_create_housings):
        return jsonify({'error': 'Доступ запрещён'}), 403
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Название обязательно'}), 400
    try:
        h = Housing(housing_name=name)
        db.session.add(h)
        db.session.commit()
        return jsonify({'id': h.id, 'name': h.housing_name})
    except IntegrityError:
        db.session.rollback()
        return jsonify({'error': 'Корпус с таким названием уже существует'}), 409


_FP_PATTERNS_PY = [
    # Numeric SMD packages: use digit-boundary ((?<!\d)/(?!\d)) so that
    # C0603, R0603, _0603_ all match, but 12603 or 06030 do not.
    (re.compile(r'(?<!\d)01005(?!\d)', re.I), '01005'),
    (re.compile(r'(?<!\d)0201(?!\d)',  re.I), '0201'),
    (re.compile(r'(?<!\d)0402(?!\d)',  re.I), '0402'),
    (re.compile(r'(?<!\d)0603(?!\d)',  re.I), '0603'),
    (re.compile(r'(?<!\d)0805(?!\d)',  re.I), '0805'),
    (re.compile(r'(?<!\d)1206(?!\d)',  re.I), '1206'),
    (re.compile(r'(?<!\d)1210(?!\d)',  re.I), '1210'),
    (re.compile(r'(?<!\d)2010(?!\d)',  re.I), '2010'),
    (re.compile(r'(?<!\d)2512(?!\d)',  re.I), '2512'),
    # Named packages: word-boundary is fine (letters adjacent to digits → clear boundary)
    (re.compile(r'SOT-?223',       re.I), 'SOT-223'),
    (re.compile(r'SOT-?23[^0-9]|SOT-?23$', re.I), 'SOT-23'),
    (re.compile(r'SOT-?89',        re.I), 'SOT-89'),
    (re.compile(r'SOT-?323',       re.I), 'SOT-323'),
    (re.compile(r'SOD-?123',       re.I), 'SOD-123'),
    (re.compile(r'SOD-?323',       re.I), 'SOD-323'),
    (re.compile(r'DO-?214',        re.I), 'DO-214'),
    (re.compile(r'SOIC-?8[^0-9]|SOIC-?8$|SOP-?8[^0-9]|SOP-?8$', re.I), 'SOIC-8'),
    (re.compile(r'SOIC-?16|SOP-?16',  re.I), 'SOIC-16'),
    (re.compile(r'TSSOP-?8[^0-9]|TSSOP-?8$', re.I), 'TSSOP-8'),
    (re.compile(r'TSSOP-?16',      re.I), 'TSSOP-16'),
    (re.compile(r'DIP-?8[^0-9]|DIP-?8$', re.I), 'DIP-8'),
    (re.compile(r'DIP-?14',        re.I), 'DIP-14'),
    (re.compile(r'DIP-?16',        re.I), 'DIP-16'),
    (re.compile(r'TO-?92',         re.I), 'TO-92'),
    (re.compile(r'TO-?220',        re.I), 'TO-220'),
    (re.compile(r'TO-?263',        re.I), 'TO-263'),
]


def _match_housing_from_footprint(footprint: str):
    """Find Housing.id by matching footprint string → canonical package → DB lookup."""
    if not footprint:
        return None
    canonical = None
    for pat, pkg in _FP_PATTERNS_PY:
        if pat.search(footprint):
            canonical = pkg
            break
    if not canonical:
        return None
    cl = canonical.lower().replace('-', '').replace('_', '').replace(' ', '')
    for h in Housing.query.order_by(Housing.housing_name).all():
        hl = h.housing_name.lower().replace('-', '').replace('_', '').replace(' ', '')
        if hl == cl or cl in hl or hl.startswith(cl):
            return h.id
    return None


def _detect_component_category(value: str):
    """Detect component category from a value string (100n, 10k, 4.7uH, etc.)."""
    if not value:
        return None
    v = re.sub(r'\s+', '', value)

    # Capacitor: digit + p/n/u/µ (NOT followed by H) + optional F
    if re.search(r'\d[pPnNuUµμ](?![Hh])[Ff]?$', v):
        return 'capacitor'
    # Explicit farads without prefix
    if re.search(r'\d[Ff]$', v) and not re.search(r'[Hh][Ff]$', v):
        return 'capacitor'

    # Inductor: digit + optional SI prefix + H (not Hz)
    if re.search(r'\d[pPnNuUmMµμ]?[Hh]$', v) and not v.upper().endswith('HZ'):
        return 'inductor'

    # Resistor: k/K/M/G/R/r/Ω suffix, or "ohm", or bare number
    if re.search(r'\d[kKMGRrΩ]$', v):
        return 'resistor'
    if re.search(r'ohm$', v, re.I):
        return 'resistor'
    if re.match(r'^\d+([.,]\d+)?$', v):
        return 'resistor'

    # LED by name pattern
    if re.search(r'\bLED\b', v, re.I):
        return 'led'

    return None


@api_bp.route('/api/detect_type')
@login_required
def detect_type():
    """Rule-based component type detection. Returns {category, group_id, subgroup_id, type_id, housing_id}."""
    name = request.args.get('name', '').strip()
    footprint = request.args.get('footprint', '').strip()
    if not name and not footprint:
        return jsonify({})

    category = _detect_component_category(name) if name else None

    result = {}
    if not category and not footprint:
        return jsonify(result)

    keywords_map = {
        'capacitor':  ['конден', 'capacit'],
        'resistor':   ['резист', 'resist'],
        'inductor':   ['катуш', 'индукт', 'inductor'],
        'diode':      ['диод', 'diode'],
        'transistor': ['транзист', 'transistor'],
        'led':        ['светодиод', 'светоизл', 'led'],
        'crystal':    ['кварц', 'crystal'],
        'fuse':       ['предохран', 'fuse'],
    }
    if category:
        result['category'] = category

    # Housing from footprint
    if footprint:
        hid = _match_housing_from_footprint(footprint)
        if hid:
            result['housing_id'] = hid

    keywords = keywords_map.get(category, []) if category else []

    if keywords:
        # 1. Search Subgroup names
        sub_conds = [Subgroup.name.ilike(f'%{kw}%') for kw in keywords]
        subgroup = Subgroup.query.filter(or_(*sub_conds)).first()

        if subgroup:
            result['group_id'] = subgroup.group_id
            result['subgroup_id'] = subgroup.id
            ctype = ComponentType.query.filter_by(subgroup_id=subgroup.id).first()
            if ctype:
                result['type_id'] = ctype.id
        else:
            # 2. Search ComponentType names
            type_conds = [ComponentType.name.ilike(f'%{kw}%') for kw in keywords]
            ctype = ComponentType.query.filter(or_(*type_conds)).first()
            if ctype:
                result['group_id'] = ctype.subgroup.group_id
                result['subgroup_id'] = ctype.subgroup_id
                result['type_id'] = ctype.id
            else:
                # 3. Search Group names (e.g. group="Резисторы" with subgroups "SMD 0402" etc.)
                grp_conds = [Group.name.ilike(f'%{kw}%') for kw in keywords]
                group = Group.query.filter(or_(*grp_conds)).first()
                if group:
                    result['group_id'] = group.id
                    sub = Subgroup.query.filter_by(group_id=group.id).first()
                    if sub:
                        result['subgroup_id'] = sub.id
                        ctype = ComponentType.query.filter_by(subgroup_id=sub.id).first()
                        if ctype:
                            result['type_id'] = ctype.id

    return jsonify(result)


@api_bp.route('/api/mouser_lookup', methods=['POST'])
@login_required
def mouser_lookup():
    """Lookup component info from Mouser Electronics API."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Название обязательно'}), 400

    api_key = os.environ.get('MOUSER_API_KEY', '')
    if not api_key:
        return jsonify({'error': 'MOUSER_API_KEY не настроен в .env'}), 503

    payload = json.dumps({
        'SearchByKeywordRequest': {
            'keyword': name,
            'records': 5,
            'startingRecord': 0,
            'searchOptions': '',
            'searchWithYourSignUpLanguage': '',
        }
    }).encode()
    req = urllib.request.Request(
        f'https://api.mouser.com/api/v1/search/keyword?apiKey={api_key}',
        data=payload,
        headers={'Content-Type': 'application/json', 'Accept': 'application/json'},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())

        errors = body.get('Errors') or []
        if errors:
            return jsonify({'error': errors[0].get('Message', 'Mouser API error')}), 502

        parts = (body.get('SearchResults') or {}).get('Parts') or []
        if not parts:
            return jsonify({'error': 'Компонент не найден в базе Mouser'}), 404

        part = parts[0]
        result = {
            'source':           'mouser',
            'manufacturer':     part.get('Manufacturer', ''),
            'manufacturer_part': part.get('ManufacturerPartNumber', ''),
            'description':      part.get('Description', ''),
            'mouser_url':       part.get('ProductDetailUrl', ''),
        }

        # Extract package from ProductAttributes (try multiple attribute names)
        package = None
        for attr in (part.get('ProductAttributes') or []):
            aname = (attr.get('AttributeName') or '').lower()
            if any(kw in aname for kw in ('package', 'case', 'mounting', 'footprint')):
                package = attr.get('AttributeValue', '')
                break
        if not package:
            package = part.get('PackageType') or ''
        # Last resort: try to extract package from description
        if not package:
            package = result.get('description', '')

        if package:
            hid = _match_housing_from_footprint(package)
            if hid:
                result['housing_id'] = hid
                result['package'] = package

        # Try to map Mouser category → group/subgroup/type
        mouser_cat = (part.get('Category') or '').lower()
        _mouser_cat_map = {
            'capacitor': 'capacitor', 'capacitors': 'capacitor',
            'resistor': 'resistor',   'resistors': 'resistor',
            'inductor': 'inductor',   'inductors': 'inductor',
            'diode': 'diode',         'diodes': 'diode',
            'transistor': 'transistor', 'transistors': 'transistor',
            'led': 'led',
            'crystal': 'crystal',     'crystals': 'crystal', 'oscillator': 'crystal',
        }
        category = None
        for key, cat in _mouser_cat_map.items():
            if key in mouser_cat:
                category = cat
                break

        if category:
            result['category'] = category
            keywords_map = {
                'capacitor':  ['конден', 'capacit'],
                'resistor':   ['резист', 'resist'],
                'inductor':   ['катуш', 'индукт', 'inductor'],
                'diode':      ['диод', 'diode'],
                'transistor': ['транзист', 'transistor'],
                'led':        ['светодиод', 'led'],
                'crystal':    ['кварц', 'crystal'],
            }
            keywords = keywords_map.get(category, [])
            if keywords:
                sub_conds = [Subgroup.name.ilike(f'%{kw}%') for kw in keywords]
                subgroup = Subgroup.query.filter(or_(*sub_conds)).first()
                if subgroup:
                    result['group_id'] = subgroup.group_id
                    result['subgroup_id'] = subgroup.id
                    ctype = ComponentType.query.filter_by(subgroup_id=subgroup.id).first()
                    if ctype:
                        result['type_id'] = ctype.id
                else:
                    type_conds = [ComponentType.name.ilike(f'%{kw}%') for kw in keywords]
                    ctype = ComponentType.query.filter(or_(*type_conds)).first()
                    if ctype:
                        result['group_id'] = ctype.subgroup.group_id
                        result['subgroup_id'] = ctype.subgroup_id
                        result['type_id'] = ctype.id
                    else:
                        grp_conds = [Group.name.ilike(f'%{kw}%') for kw in keywords]
                        group = Group.query.filter(or_(*grp_conds)).first()
                        if group:
                            result['group_id'] = group.id
                            sub = Subgroup.query.filter_by(group_id=group.id).first()
                            if sub:
                                result['subgroup_id'] = sub.id
                                ctype = ComponentType.query.filter_by(subgroup_id=sub.id).first()
                                if ctype:
                                    result['type_id'] = ctype.id

        return jsonify(result)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return jsonify({'error': f'Mouser API {e.code}: {body[:300]}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@api_bp.route('/api/lcsc_lookup', methods=['POST'])
@login_required
def lcsc_lookup():
    """Lookup component info from LCSC (wmsc.lcsc.com public search)."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Название обязательно'}), 400

    _LCSC_UA = (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    )
    _LCSC_HEADERS = {
        'User-Agent': _LCSC_UA,
        'Accept': 'application/json, text/plain, */*',
        'Accept-Language': 'en-US,en;q=0.9',
        'Referer': 'https://www.lcsc.com/',
        'Origin': 'https://www.lcsc.com',
    }

    # Try two known endpoints (wmsc is used by KiCad, global_search is newer)
    _LCSC_URLS = [
        f'https://wmsc.lcsc.com/wmsc/search/global?q={urllib.request.quote(name)}&currentPage=1&pageSize=5',
        f'https://lcsc.com/api/global_search/v2?q={urllib.request.quote(name)}&currentPage=1&pageSize=5',
    ]

    body = None
    last_err = 'нет ответа'
    for _url in _LCSC_URLS:
        try:
            req = urllib.request.Request(_url, headers=_LCSC_HEADERS)
            with urllib.request.urlopen(req, timeout=12) as resp:
                body = json.loads(resp.read())
            if body.get('code') == 200:
                break
            last_err = body.get('msg') or str(body.get('code', 'err'))
            body = None
        except Exception as ex:
            last_err = str(ex)
            body = None

    try:
        if not body:
            return jsonify({'error': f'LCSC недоступен: {last_err}'}), 502

        result_data = body.get('result') or {}
        # Try tipProductDetails first (exact match by part number), then productList
        tip = result_data.get('tipProductDetails') or []
        product_list = (result_data.get('productSearchResultVO') or {}).get('productList') or []
        parts = tip + product_list
        if not parts:
            return jsonify({'error': 'Компонент не найден в базе LCSC'}), 404

        part = parts[0]
        description = (part.get('productIntroEn') or part.get('productDescEn') or
                       part.get('productIntro') or '')
        result = {
            'source':            'lcsc',
            'manufacturer':      part.get('brandNameEn') or part.get('brandName', ''),
            'manufacturer_part': part.get('productModel', ''),
            'description':       description,
            'lcsc_code':         part.get('productCode', ''),
        }

        # encapStandard is usually clean: "0603", "SOT-23", etc.
        package = (part.get('encapStandard') or part.get('packageStandard') or
                   part.get('encap') or '')
        if not package and description:
            package = description  # fall back to parsing from description

        if package:
            hid = _match_housing_from_footprint(package)
            if hid:
                result['housing_id'] = hid
                result['package'] = package

        # Category mapping
        cat_str = (part.get('catalogName') or part.get('catalogNodePathEn') or '').lower()
        _lcsc_cat_map = {
            'capacitor': 'capacitor', 'multilayer ceramic': 'capacitor',
            'resistor': 'resistor',
            'inductor': 'inductor',   'ferrite': 'inductor',
            'diode': 'diode',
            'transistor': 'transistor', 'mosfet': 'transistor',
            'led': 'led',             'light emitting': 'led',
            'crystal': 'crystal',     'oscillator': 'crystal',
        }
        category = None
        for key, cat in _lcsc_cat_map.items():
            if key in cat_str:
                category = cat
                break

        if category:
            result['category'] = category
            _keywords_map = {
                'capacitor':  ['конден', 'capacit'],
                'resistor':   ['резист', 'resist'],
                'inductor':   ['катуш', 'индукт', 'inductor'],
                'diode':      ['диод', 'diode'],
                'transistor': ['транзист', 'transistor'],
                'led':        ['светодиод', 'led'],
                'crystal':    ['кварц', 'crystal'],
            }
            keywords = _keywords_map.get(category, [])
            if keywords:
                sub_conds = [Subgroup.name.ilike(f'%{kw}%') for kw in keywords]
                subgroup = Subgroup.query.filter(or_(*sub_conds)).first()
                if subgroup:
                    result['group_id'] = subgroup.group_id
                    result['subgroup_id'] = subgroup.id
                    ctype = ComponentType.query.filter_by(subgroup_id=subgroup.id).first()
                    if ctype:
                        result['type_id'] = ctype.id
                else:
                    type_conds = [ComponentType.name.ilike(f'%{kw}%') for kw in keywords]
                    ctype = ComponentType.query.filter(or_(*type_conds)).first()
                    if ctype:
                        result['group_id'] = ctype.subgroup.group_id
                        result['subgroup_id'] = ctype.subgroup_id
                        result['type_id'] = ctype.id
                    else:
                        grp_conds = [Group.name.ilike(f'%{kw}%') for kw in keywords]
                        group = Group.query.filter(or_(*grp_conds)).first()
                        if group:
                            result['group_id'] = group.id
                            sub = Subgroup.query.filter_by(group_id=group.id).first()
                            if sub:
                                result['subgroup_id'] = sub.id
                                ctype = ComponentType.query.filter_by(subgroup_id=sub.id).first()
                                if ctype:
                                    result['type_id'] = ctype.id

        return jsonify(result)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return jsonify({'error': f'LCSC API {e.code}: {body[:200]}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def _call_openai_compat(api_key, base_url, model, prompt):
    """Вызов OpenAI-совместимого API (Groq, OpenAI и др.)."""
    payload = json.dumps({
        "model": model,
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/chat/completions",
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (compatible; ComponentWarehouse/1.0)",
        }
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())
        return body['choices'][0]['message']['content'].strip()


def _call_anthropic(api_key, prompt):
    """Вызов Anthropic API."""
    payload = json.dumps({
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 256,
        "messages": [{"role": "user", "content": prompt}]
    }).encode()
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        body = json.loads(resp.read())
        return body['content'][0]['text'].strip()


@api_bp.route('/api/lookup_component', methods=['POST'])
@login_required
def lookup_component():
    """Запрос характеристик компонента через ИИ (Groq/Anthropic)."""
    data = request.get_json() or {}
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify({'error': 'Название обязательно'}), 400

    groq_key = os.environ.get('GROQ_API_KEY', '')
    anthropic_key = os.environ.get('ANTHROPIC_API_KEY', '')

    if not groq_key and not anthropic_key:
        return jsonify({'error': 'Нет API-ключа. Добавьте GROQ_API_KEY (бесплатно: console.groq.com) или ANTHROPIC_API_KEY в .env'}), 503

    # Build available types list for AI to pick from (max 60 entries)
    db_types = (ComponentType.query
                .join(Subgroup, ComponentType.subgroup_id == Subgroup.id)
                .join(Group, Subgroup.group_id == Group.id)
                .all())
    cats_text = '; '.join(
        f"id={t.id}:{t.subgroup.group.name}/{t.subgroup.name}/{t.name}"
        for t in db_types[:60]
    )

    prompt = (
        f"Electronic component: '{name}'. "
        "Return ONLY a valid JSON object, no markdown, no extra text. Keys: "
        "nominal_value (number or null), "
        "unit (string like 'Ω','F','H','V','A','Hz','nF','uF','pF','kΩ','MHz' or null), "
        "housing (SMD package like '0402','0603','0805','SOT-23','SOP-8','DIP-8' or null), "
        "description (string in Russian, max 80 chars, or null), "
        f"type_id (integer ID from this list or null — {cats_text}). "
        'Example: {"nominal_value":100,"unit":"nF","housing":"0402","description":"Конденсатор керамический","type_id":3}'
    )

    try:
        if groq_key:
            text = _call_openai_compat(groq_key, "https://api.groq.com/openai/v1",
                                       "llama-3.1-8b-instant", prompt)
        else:
            text = _call_anthropic(anthropic_key, prompt)

        m = re.search(r'\{.*\}', text, re.DOTALL)
        if not m:
            return jsonify({'error': 'Не удалось распарсить ответ ИИ'}), 502

        result = json.loads(m.group())

        # Resolve type_id → subgroup_id, group_id
        tid = result.get('type_id')
        if tid:
            t = ComponentType.query.get(int(tid))
            if t:
                result['type_id'] = t.id
                result['subgroup_id'] = t.subgroup_id
                result['group_id'] = t.subgroup.group_id
            else:
                result.pop('type_id', None)

        # Match housing name → housing_id
        housing_name = result.get('housing')
        if housing_name:
            h = (Housing.query
                 .filter(Housing.housing_name.ilike(housing_name)).first()
                 or Housing.query
                 .filter(Housing.housing_name.ilike(f'%{housing_name}%')).first())
            if h:
                result['housing_id'] = h.id

        return jsonify(result)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8', errors='replace')
        return jsonify({'error': f'API {e.code}: {body[:300]}'}), 502
    except Exception as e:
        return jsonify({'error': str(e)}), 500

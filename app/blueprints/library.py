from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import ComponentLibrary, ComponentType, Group, Subgroup, Housing, Component
from app.forms import LibraryItemForm, ProduceForm

library_bp = Blueprint('library', __name__, url_prefix='/library')


def _build_form_choices(form, group_id=0, subgroup_id=0):
    groups = Group.query.order_by(Group.name).all()
    form.group_id.choices = [(0, 'Выберите группу')] + [(g.id, g.name) for g in groups]

    if group_id:
        subgroups = Subgroup.query.filter_by(group_id=group_id).order_by(Subgroup.name).all()
    else:
        subgroups = Subgroup.query.order_by(Subgroup.name).all()
    form.subgroup_id.choices = [(0, 'Выберите подгруппу')] + [(s.id, s.name) for s in subgroups]

    if subgroup_id:
        types = ComponentType.query.filter_by(subgroup_id=subgroup_id).order_by(ComponentType.name).all()
    else:
        types = ComponentType.query.order_by(ComponentType.name).all()
    form.type_id.choices = [(0, 'Выберите тип')] + [(t.id, t.name) for t in types]

    housings = Housing.query.order_by(Housing.housing_name).all()
    form.housing_id.choices = [(0, '— нет —')] + [(h.id, h.housing_name) for h in housings]


@library_bp.route('/', methods=['GET'])
@login_required
def index():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('main.index'))

    q          = request.args.get('q', '').strip()
    group_id   = request.args.get('group_id',   type=int, default=0)
    subgroup_id= request.args.get('subgroup_id',type=int, default=0)
    type_id    = request.args.get('type_id',    type=int, default=0)

    query = (ComponentLibrary.query
             .outerjoin(ComponentType, ComponentLibrary.type_id == ComponentType.id)
             .outerjoin(Housing, ComponentLibrary.housing_id == Housing.id)
             .outerjoin(Subgroup, ComponentType.subgroup_id == Subgroup.id))
    if q:
        query = query.filter(or_(
            ComponentLibrary.name.ilike(f'%{q}%'),
            ComponentLibrary.manufacturer.ilike(f'%{q}%'),
            ComponentLibrary.description.ilike(f'%{q}%'),
            ComponentType.name.ilike(f'%{q}%'),
            Housing.housing_name.ilike(f'%{q}%'),
        ))
    if type_id:
        query = query.filter(ComponentLibrary.type_id == type_id)
    elif subgroup_id:
        query = query.filter(ComponentType.subgroup_id == subgroup_id)
    elif group_id:
        query = query.filter(Subgroup.group_id == group_id)

    items = query.order_by(ComponentLibrary.name).all()

    # Build tree: group -> subgroup -> type -> [items]
    from collections import defaultdict
    tree = {}  # {group: {subgroup: {type: [item, ...]}}}
    for item in items:
        if not item.comp_type:
            continue
        g = item.comp_type.subgroup.group
        s = item.comp_type.subgroup
        t = item.comp_type
        tree.setdefault(g, {}).setdefault(s, {}).setdefault(t, []).append(item)

    # Sidebar counts per group/subgroup/type (all items, ignoring current filter)
    all_items = ComponentLibrary.query.all()
    group_counts    = defaultdict(int)
    subgroup_counts = defaultdict(int)
    type_counts     = defaultdict(int)
    for it in all_items:
        if it.comp_type:
            type_counts[it.comp_type.id] += 1
            subgroup_counts[it.comp_type.subgroup_id] += 1
            group_counts[it.comp_type.subgroup.group_id] += 1

    groups    = Group.query.order_by(Group.name).all()
    subgroups = Subgroup.query.order_by(Subgroup.name).all()
    types     = ComponentType.query.order_by(ComponentType.name).all()

    csrf_form = ProduceForm()
    return render_template('library.html',
        items=items, tree=tree, q=q,
        group_id=group_id, subgroup_id=subgroup_id, type_id=type_id,
        groups=groups, subgroups=subgroups, types=types,
        group_counts=group_counts, subgroup_counts=subgroup_counts, type_counts=type_counts,
        csrf_form=csrf_form)


@library_bp.route('/new', methods=['GET', 'POST'])
@login_required
def create():
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для создания', 'error')
        return redirect(url_for('library.index'))

    next_action = request.args.get('next') or request.form.get('next_action', '')

    form = LibraryItemForm()
    group_id = request.form.get('group_id', type=int) or 0
    subgroup_id = request.form.get('subgroup_id', type=int) or 0
    _build_form_choices(form, group_id, subgroup_id)

    if form.validate_on_submit():
        if not form.type_id.data:
            flash('Укажите тип компонента', 'error')
        else:
            try:
                item = ComponentLibrary(
                    name=form.name.data.strip(),
                    type_id=form.type_id.data,
                    housing_id=form.housing_id.data or None,
                    manufacturer=form.manufacturer.data or None,
                    nominal_value=form.nominal_value.data,
                    unit=form.unit.data or None,
                    description=form.description.data or None,
                )
                db.session.add(item)
                db.session.commit()
                flash(f'«{item.name}» добавлен в библиотеку', 'success')
                if next_action == 'stock':
                    return redirect(url_for('library.add_to_stock', id=item.id))
                return redirect(url_for('library.index'))
            except IntegrityError:
                db.session.rollback()
                flash('Компонент с таким именем/типом/корпусом уже существует в библиотеке', 'error')

    return render_template('library_form.html', form=form, title='Добавить в библиотеку',
                           next_action=next_action)


@library_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('Нет прав для редактирования', 'error')
        return redirect(url_for('library.index'))

    item = ComponentLibrary.query.get_or_404(id)
    form = LibraryItemForm(obj=item)

    if request.method == 'POST':
        group_id = request.form.get('group_id', type=int) or 0
        subgroup_id = request.form.get('subgroup_id', type=int) or 0
    else:
        subgroup = item.comp_type.subgroup if item.comp_type else None
        subgroup_id = subgroup.id if subgroup else 0
        group_id = subgroup.group_id if subgroup else 0
        form.group_id.data = group_id
        form.subgroup_id.data = subgroup_id
        form.type_id.data = item.type_id
        form.housing_id.data = item.housing_id or 0

    _build_form_choices(form, group_id, subgroup_id)

    if form.validate_on_submit():
        if not form.type_id.data:
            flash('Укажите тип компонента', 'error')
        else:
            try:
                item.name = form.name.data.strip()
                item.type_id = form.type_id.data
                item.housing_id = form.housing_id.data or None
                item.manufacturer = form.manufacturer.data or None
                item.nominal_value = form.nominal_value.data
                item.unit = form.unit.data or None
                item.description = form.description.data or None
                db.session.commit()
                flash('Запись библиотеки обновлена', 'success')
                return redirect(url_for('library.index'))
            except IntegrityError:
                db.session.rollback()
                flash('Компонент с таким именем/типом/корпусом уже существует', 'error')

    return render_template('library_form.html', form=form, title='Редактировать запись библиотеки', item=item)


@library_bp.route('/<int:id>/add_to_stock', methods=['POST'])
@login_required
def add_to_stock(id):
    """Создать складскую запись на основе библиотечной."""
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('Нет прав для создания компонентов', 'error')
        return redirect(url_for('library.index'))

    lib = ComponentLibrary.query.get_or_404(id)
    existing = Component.query.filter_by(
        name=lib.name, type_id=lib.type_id, housing_id=lib.housing_id
    ).first()
    if existing:
        flash(f'Компонент «{lib.name}» уже есть на складе', 'success')
        return redirect(url_for('components.view', id=existing.id))

    from app.models import ComponentHistory
    from datetime import datetime
    comp = Component(
        name=lib.name,
        type_id=lib.type_id,
        housing_id=lib.housing_id,
        manufacturer=lib.manufacturer,
        nominal_value=lib.nominal_value,
        unit=lib.unit,
        parameters=lib.parameters,
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
    db.session.commit()
    flash(f'Компонент «{comp.name}» добавлен на склад (кол-во: 0). Не забудьте обновить количество.', 'success')
    return redirect(url_for('components.edit', id=comp.id))


@library_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_components):
        flash('Нет прав для удаления', 'error')
        return redirect(url_for('library.index'))

    item = ComponentLibrary.query.get_or_404(id)
    name = item.name
    db.session.delete(item)
    db.session.commit()
    flash(f'«{name}» удалён из библиотеки', 'success')
    return redirect(url_for('library.index'))

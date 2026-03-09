import json
from collections import defaultdict
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Group, Subgroup, ComponentType, Housing, Component, ComponentHistory
from app.forms import ComponentForm, SearchForm

components_bp = Blueprint('components', __name__)


@components_bp.route('/components', methods=['GET'])
@login_required
def index():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра компонентов', 'error')
        return redirect(url_for('main.index'))

    q           = request.args.get('q', '').strip()
    group_id    = request.args.get('group_id',    type=int, default=0)
    subgroup_id = request.args.get('subgroup_id', type=int, default=0)
    type_id     = request.args.get('type_id',     type=int, default=0)

    query = (Component.query
             .filter_by(is_archived=False)
             .outerjoin(ComponentType, Component.type_id == ComponentType.id)
             .outerjoin(Housing,       Component.housing_id == Housing.id)
             .outerjoin(Subgroup,      ComponentType.subgroup_id == Subgroup.id))

    if current_user.role == 'admin':
        query = query.filter(Component.created_by_id == current_user.id)

    if q:
        query = query.filter(or_(
            Component.name.ilike(f'%{q}%'),
            Component.manufacturer.ilike(f'%{q}%'),
            ComponentType.name.ilike(f'%{q}%'),
            Housing.housing_name.ilike(f'%{q}%'),
        ))
    if type_id:
        query = query.filter(Component.type_id == type_id)
    elif subgroup_id:
        query = query.filter(ComponentType.subgroup_id == subgroup_id)
    elif group_id:
        query = query.filter(Subgroup.group_id == group_id)

    items = query.order_by(Component.name).all()

    # Build display tree: group → subgroup → type → [items]
    tree = {}
    for item in items:
        if not item.comp_type:
            continue
        g = item.comp_type.subgroup.group
        s = item.comp_type.subgroup
        t = item.comp_type
        tree.setdefault(g, {}).setdefault(s, {}).setdefault(t, []).append(item)

    # Sidebar counts (all non-archived visible to user)
    all_q = Component.query.filter_by(is_archived=False)
    if current_user.role == 'admin':
        all_q = all_q.filter_by(created_by_id=current_user.id)
    group_counts    = defaultdict(int)
    subgroup_counts = defaultdict(int)
    type_counts     = defaultdict(int)
    for it in all_q.all():
        if it.comp_type:
            type_counts[it.comp_type.id] += 1
            subgroup_counts[it.comp_type.subgroup_id] += 1
            group_counts[it.comp_type.subgroup.group_id] += 1

    groups    = Group.query.order_by(Group.name).all()
    subgroups = Subgroup.query.order_by(Subgroup.name).all()
    types     = ComponentType.query.order_by(ComponentType.name).all()

    # SearchForm kept only for CSRF token (used in add-modal)
    form = SearchForm()
    form.group_id.choices    = [(0, 'Все группы')]    + [(g.id, g.name) for g in groups]
    form.subgroup_id.choices = [(0, 'Все подгруппы')] + [(s.id, s.name) for s in subgroups]
    form.type_id.choices     = [(0, 'Все типы')]      + [(t.id, t.name) for t in types]

    return render_template(
        'components.html',
        items=items, tree=tree, q=q,
        group_id=group_id, subgroup_id=subgroup_id, type_id=type_id,
        groups=groups, subgroups=subgroups, types=types,
        group_counts=group_counts, subgroup_counts=subgroup_counts, type_counts=type_counts,
        form=form,
    )


@components_bp.route('/components/view/<int:id>')
@login_required
def view(id):
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра компонентов', 'error')
        return redirect(url_for('components.index'))
    component = Component.query.get_or_404(id)
    recent_history = (ComponentHistory.query
                      .filter_by(unique_id=component.unique_id)
                      .order_by(ComponentHistory.timestamp.desc())
                      .limit(5).all())
    return render_template('component_view.html', component=component, recent_history=recent_history)


@components_bp.route('/components/add', methods=['GET', 'POST'])
@login_required
def add():
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('У вас нет прав для создания компонентов', 'error')
        return redirect(url_for('components.index'))

    form = ComponentForm()
    group_id = request.form.get('group_id', type=int) or 0
    subgroup_id = request.form.get('subgroup_id', type=int) or 0

    all_groups = Group.query.all()
    all_subgroups = Subgroup.query.filter_by(group_id=group_id).all() if group_id else Subgroup.query.all()
    all_types = ComponentType.query.filter_by(subgroup_id=subgroup_id).all() if subgroup_id else ComponentType.query.all()
    subgroup = Subgroup.query.get(subgroup_id) if subgroup_id else None

    form.group_id.choices = [(0, 'Выберите группу')] + [(g.id, g.name) for g in all_groups]
    form.subgroup_id.choices = [(0, 'Выберите подгруппу')] + [(s.id, s.name) for s in all_subgroups]
    form.type_id.choices = [(0, 'Выберите тип')] + [(t.id, t.name) for t in all_types]
    form.housing_id.choices = [(h.id, h.housing_name) for h in Housing.query.all()]
    unit_choices = [(u, u) for u in json.loads(subgroup.units_schema)] if subgroup else []
    submitted_unit = request.form.get('unit', '')
    if submitted_unit and (submitted_unit,) not in [(u[0],) for u in unit_choices]:
        unit_choices.append((submitted_unit, submitted_unit))
    form.unit.choices = unit_choices + [('', 'Выберите единицу')]

    if form.validate_on_submit():
        if form.group_id.data == 0 or form.subgroup_id.data == 0 or form.type_id.data == 0 or not form.unit.data:
            flash('Выберите группу, подгруппу, тип и единицу измерения', 'error')
            return render_template('component_form.html', form=form, action='add')

        component = Component(
            name=form.name.data,
            type_id=form.type_id.data,
            housing_id=form.housing_id.data,
            manufacturer=form.manufacturer.data,
            quantity=form.quantity.data,
            price=form.price.data,
            arrival_date=form.arrival_date.data,
            location=form.location.data,
            nominal_value=form.nominal_value.data,
            unit=form.unit.data,
            parameters=json.dumps(form.additional_parameters.data),
            created_by_id=current_user.id,
            is_archived=False,
        )
        try:
            db.session.add(component)
            db.session.flush()
            db.session.add(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='create',
                timestamp=datetime.utcnow(),
            ))
            db.session.commit()
            flash('Компонент добавлен!', 'success')
            return redirect(url_for('components.index'))
        except IntegrityError:
            db.session.rollback()
            flash('Компонент с таким названием уже существует', 'error')
            return render_template('component_form.html', form=form, action='add')

    return render_template('component_form.html', form=form, action='add')


@components_bp.route('/components/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('У вас нет прав для редактирования компонентов', 'error')
        return redirect(url_for('components.index'))

    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете редактировать только свои записи', 'error')
        return redirect(url_for('components.index'))

    form = ComponentForm()
    group_id = request.form.get('group_id', type=int) or component.comp_type.subgroup.group_id
    subgroup_id = request.form.get('subgroup_id', type=int) or component.comp_type.subgroup_id

    all_groups = Group.query.all()
    all_subgroups = Subgroup.query.filter_by(group_id=group_id).all() if group_id else Subgroup.query.all()
    all_types = ComponentType.query.filter_by(subgroup_id=subgroup_id).all() if subgroup_id else ComponentType.query.all()
    subgroup = Subgroup.query.get(subgroup_id) if subgroup_id else None

    form.group_id.choices = [(0, 'Выберите группу')] + [(g.id, g.name) for g in all_groups]
    form.subgroup_id.choices = [(0, 'Выберите подгруппу')] + [(s.id, s.name) for s in all_subgroups]
    form.type_id.choices = [(0, 'Выберите тип')] + [(t.id, t.name) for t in all_types]
    form.housing_id.choices = [(h.id, h.housing_name) for h in Housing.query.all()]
    unit_choices = [(u, u) for u in json.loads(subgroup.units_schema)] if subgroup else []
    submitted_unit = request.form.get('unit', '') or component.unit
    if submitted_unit and (submitted_unit,) not in [(u[0],) for u in unit_choices]:
        unit_choices.append((submitted_unit, submitted_unit))
    form.unit.choices = unit_choices + [('', 'Выберите единицу')]

    if form.validate_on_submit():
        if form.group_id.data == 0 or form.subgroup_id.data == 0 or form.type_id.data == 0 or not form.unit.data:
            flash('Выберите группу, подгруппу, тип и единицу измерения', 'error')
            return render_template('component_form.html', form=form, action='edit', component=component)

        fields = [
            ('name', component.name, form.name.data),
            ('type_id', component.type_id, form.type_id.data),
            ('housing_id', component.housing_id, form.housing_id.data),
            ('manufacturer', component.manufacturer, form.manufacturer.data),
            ('quantity', component.quantity, form.quantity.data),
            ('price', component.price, form.price.data),
            ('arrival_date', component.arrival_date, form.arrival_date.data),
            ('location', component.location, form.location.data),
            ('nominal_value', component.nominal_value, form.nominal_value.data),
            ('unit', component.unit, form.unit.data),
            ('parameters', component.parameters, json.dumps(form.additional_parameters.data)),
        ]
        changes = [
            ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed=field,
                old_value=str(old),
                new_value=str(new),
                timestamp=datetime.utcnow(),
            )
            for field, old, new in fields if old != new
        ]

        component.name = form.name.data
        component.type_id = form.type_id.data
        component.housing_id = form.housing_id.data
        component.manufacturer = form.manufacturer.data
        component.quantity = form.quantity.data
        component.price = form.price.data
        component.arrival_date = form.arrival_date.data
        component.location = form.location.data
        component.nominal_value = form.nominal_value.data
        component.unit = form.unit.data
        component.parameters = json.dumps(form.additional_parameters.data)

        try:
            for change in changes:
                db.session.add(change)
            db.session.commit()
            flash('Компонент обновлён!', 'success')
            return redirect(url_for('components.index'))
        except IntegrityError:
            db.session.rollback()
            flash('Компонент с таким названием уже существует', 'error')
            return render_template('component_form.html', form=form, action='edit', component=component)

    if not request.form:
        form.name.data = component.name
        form.group_id.data = component.comp_type.subgroup.group_id
        form.subgroup_id.data = component.comp_type.subgroup_id
        form.type_id.data = component.type_id
        form.housing_id.data = component.housing_id
        form.manufacturer.data = component.manufacturer
        form.quantity.data = component.quantity
        form.price.data = component.price
        form.arrival_date.data = component.arrival_date
        form.location.data = component.location
        form.nominal_value.data = component.nominal_value
        form.unit.data = component.unit
        form.additional_parameters.data = json.loads(component.parameters) if component.parameters else {}

    return render_template('component_form.html', form=form, action='edit', component=component)


@components_bp.route('/components/delete/<int:id>')
@login_required
def delete(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_components):
        flash('У вас нет прав для удаления компонентов', 'error')
        return redirect(url_for('components.index'))

    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете удалять только свои записи', 'error')
        return redirect(url_for('components.index'))

    from app.models import Order
    if Order.query.filter_by(component_id=id).first():
        flash('Нельзя удалить компонент, связанный с заказами', 'error')
        return redirect(url_for('components.index'))

    try:
        component.is_archived = True
        db.session.add(ComponentHistory(
            unique_id=component.unique_id,
            user_id=current_user.id,
            action='archive',
            timestamp=datetime.utcnow(),
        ))
        db.session.commit()
        flash('Компонент перемещён в архив!', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash(f'Ошибка при архивировании компонента: {str(e)}', 'error')
        current_app.logger.error(f'Ошибка при архивировании компонента {id}: {str(e)}')

    return redirect(url_for('components.index'))


@components_bp.route('/components/history/<int:id>')
@login_required
def history(id):
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра истории компонентов', 'error')
        return redirect(url_for('components.index'))

    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете просматривать только свои записи', 'error')
        return redirect(url_for('components.index'))

    history = ComponentHistory.query.filter_by(unique_id=component.unique_id).order_by(
        ComponentHistory.timestamp.desc()
    ).all()
    if not history:
        flash('История для этого компонента не найдена', 'error')
        return redirect(url_for('components.index'))

    return render_template('component_history.html', component=component, history=history)


@components_bp.route('/archive')
@login_required
def archive():
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    archived_components = Component.query.filter_by(is_archived=True).all()
    return render_template('archive.html', archived_components=archived_components)


@components_bp.route('/archive/restore/<int:id>')
@login_required
def restore(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.archive'))

    component = Component.query.get_or_404(id)
    if not component.is_archived:
        flash('Компонент не находится в архиве', 'error')
        return redirect(url_for('components.archive'))

    try:
        component.is_archived = False
        db.session.add(ComponentHistory(
            unique_id=component.unique_id,
            user_id=current_user.id,
            action='restore',
            timestamp=datetime.utcnow(),
        ))
        db.session.commit()
        flash('Компонент успешно восстановлен!', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash(f'Ошибка при восстановлении компонента: {str(e)}', 'error')
        current_app.logger.error(f'Ошибка при восстановлении компонента {id}: {str(e)}')

    return redirect(url_for('components.index'))


@components_bp.route('/archive/delete/<int:id>')
@login_required
def delete_archived(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.archive'))

    component = Component.query.get_or_404(id)
    if not component.is_archived:
        flash('Компонент не находится в архиве', 'error')
        return redirect(url_for('components.archive'))

    try:
        ComponentHistory.query.filter_by(unique_id=component.unique_id).delete()
        db.session.delete(component)
        db.session.commit()
        flash('Компонент окончательно удалён из архива!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении компонента из архива: {str(e)}', 'error')
        current_app.logger.error(f'Ошибка при удалении компонента {id}: {str(e)}')

    return redirect(url_for('components.archive'))

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Subgroup, ComponentType, Housing, Component
from app.forms import ComponentTypeForm, HousingForm

catalog_bp = Blueprint('catalog', __name__)


@catalog_bp.route('/types', methods=['GET', 'POST'])
@login_required
def types():
    if not (current_user.role == 'super_admin' or current_user.can_view_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    form = ComponentTypeForm()
    form.subgroup_id.choices = [(s.id, f"{s.group.name} - {s.name}") for s in Subgroup.query.all()]
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_types):
        try:
            db.session.add(ComponentType(name=form.name.data, subgroup_id=form.subgroup_id.data))
            db.session.commit()
            flash('Тип добавлен!', 'success')
            return redirect(url_for('catalog.types'))
        except IntegrityError:
            db.session.rollback()
            flash('Тип с таким названием уже существует в этой подгруппе', 'error')
    types = ComponentType.query.all()
    return render_template(
        'types.html', form=form, types=types,
        can_edit=(current_user.role == 'super_admin' or current_user.can_edit_types),
        can_delete=(current_user.role == 'super_admin' or current_user.can_delete_types),
    )


@catalog_bp.route('/types/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_type(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('catalog.types'))
    component_type = ComponentType.query.get_or_404(id)
    form = ComponentTypeForm(obj=component_type)
    form.subgroup_id.choices = [(s.id, f"{s.group.name} - {s.name}") for s in Subgroup.query.all()]
    if form.validate_on_submit():
        try:
            component_type.name = form.name.data
            component_type.subgroup_id = form.subgroup_id.data
            db.session.commit()
            flash('Тип обновлён!', 'success')
            return redirect(url_for('catalog.types'))
        except IntegrityError:
            db.session.rollback()
            flash('Тип с таким названием уже существует в этой подгруппе', 'error')
    return render_template('type_form.html', form=form, component_type=component_type)


@catalog_bp.route('/types/delete/<int:id>')
@login_required
def delete_type(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('catalog.types'))
    component_type = ComponentType.query.get_or_404(id)
    if Component.query.filter_by(type_id=id).first():
        flash('Нельзя удалить тип, используемый в компонентах', 'error')
    else:
        db.session.delete(component_type)
        db.session.commit()
        flash('Тип удалён!', 'success')
    return redirect(url_for('catalog.types'))


@catalog_bp.route('/housings', methods=['GET', 'POST'])
@login_required
def housings():
    if not (current_user.role == 'super_admin' or current_user.can_view_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    form = HousingForm()
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_housings):
        try:
            db.session.add(Housing(housing_name=form.housing_name.data))
            db.session.commit()
            flash('Корпус добавлен!', 'success')
            return redirect(url_for('catalog.housings'))
        except IntegrityError:
            db.session.rollback()
            flash('Корпус с таким названием уже существует', 'error')
    housings = Housing.query.all()
    return render_template(
        'housings.html', form=form, housings=housings,
        can_edit=(current_user.role == 'super_admin' or current_user.can_edit_housings),
        can_delete=(current_user.role == 'super_admin' or current_user.can_delete_housings),
    )


@catalog_bp.route('/housings/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_housing(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('catalog.housings'))
    housing = Housing.query.get_or_404(id)
    form = HousingForm(obj=housing)
    if form.validate_on_submit():
        try:
            housing.housing_name = form.housing_name.data
            db.session.commit()
            flash('Корпус обновлён!', 'success')
            return redirect(url_for('catalog.housings'))
        except IntegrityError:
            db.session.rollback()
            flash('Корпус с таким названием уже существует', 'error')
    return render_template('housing_form.html', form=form, housing=housing)


@catalog_bp.route('/housings/delete/<int:id>')
@login_required
def delete_housing(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('catalog.housings'))
    housing = Housing.query.get_or_404(id)
    if Component.query.filter_by(housing_id=id).first():
        flash('Нельзя удалить корпус, используемый в компонентах', 'error')
    else:
        db.session.delete(housing)
        db.session.commit()
        flash('Корпус удалён!', 'success')
    return redirect(url_for('catalog.housings'))

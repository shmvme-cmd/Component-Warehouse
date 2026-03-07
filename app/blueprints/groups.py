import json

from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Group, Subgroup, ComponentType
from app.forms import GroupForm, SubgroupForm

groups_bp = Blueprint('groups', __name__)


@groups_bp.route('/groups', methods=['GET', 'POST'])
@login_required
def index():
    if not (current_user.role == 'super_admin' or current_user.can_view_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    form = GroupForm()
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_groups):
        try:
            db.session.add(Group(name=form.name.data))
            db.session.commit()
            flash('Группа добавлена!', 'success')
            return redirect(url_for('groups.index'))
        except IntegrityError:
            db.session.rollback()
            flash('Группа с таким названием уже существует', 'error')
    groups = Group.query.all()
    return render_template(
        'groups.html', form=form, groups=groups,
        can_edit=(current_user.role == 'super_admin' or current_user.can_edit_groups),
        can_delete=(current_user.role == 'super_admin' or current_user.can_delete_groups),
    )


@groups_bp.route('/groups/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups.index'))
    group = Group.query.get_or_404(id)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        try:
            group.name = form.name.data
            db.session.commit()
            flash('Группа обновлена!', 'success')
            return redirect(url_for('groups.index'))
        except IntegrityError:
            db.session.rollback()
            flash('Группа с таким названием уже существует', 'error')
    return render_template('group_form.html', form=form, group=group)


@groups_bp.route('/groups/delete/<int:id>')
@login_required
def delete_group(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups.index'))
    group = Group.query.get_or_404(id)
    if Subgroup.query.filter_by(group_id=id).first():
        flash('Нельзя удалить группу, связанную с подгруппами', 'error')
    else:
        db.session.delete(group)
        db.session.commit()
        flash('Группа удалена!', 'success')
    return redirect(url_for('groups.index'))


@groups_bp.route('/subgroups', methods=['GET', 'POST'])
@login_required
def subgroups():
    if not (current_user.role == 'super_admin' or current_user.can_view_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    form = SubgroupForm()
    form.group_id.choices = [(g.id, g.name) for g in Group.query.all()]
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_subgroups):
        try:
            units = form.units.data.split(',')
            db.session.add(Subgroup(
                name=form.name.data,
                group_id=form.group_id.data,
                units_schema=json.dumps(units, ensure_ascii=False),
            ))
            db.session.commit()
            flash('Подгруппа добавлена!', 'success')
            return redirect(url_for('groups.subgroups'))
        except IntegrityError:
            db.session.rollback()
            flash('Подгруппа с таким названием уже существует в этой группе', 'error')
    subgroups = Subgroup.query.all()
    return render_template(
        'subgroups.html', form=form, subgroups=subgroups,
        can_edit=(current_user.role == 'super_admin' or current_user.can_edit_subgroups),
        can_delete=(current_user.role == 'super_admin' or current_user.can_delete_subgroups),
    )


@groups_bp.route('/subgroups/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subgroup(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups.subgroups'))
    subgroup = Subgroup.query.get_or_404(id)
    form = SubgroupForm(obj=subgroup)
    form.group_id.choices = [(g.id, g.name) for g in Group.query.all()]
    if form.validate_on_submit():
        try:
            units = form.units.data.split(',')
            subgroup.name = form.name.data
            subgroup.group_id = form.group_id.data
            subgroup.units_schema = json.dumps(units, ensure_ascii=False)
            db.session.commit()
            flash('Подгруппа обновлена!', 'success')
            return redirect(url_for('groups.subgroups'))
        except IntegrityError:
            db.session.rollback()
            flash('Подгруппа с таким названием уже существует в этой группе', 'error')
    form.units.data = ','.join(json.loads(subgroup.units_schema))
    return render_template('subgroup_form.html', form=form, subgroup=subgroup)


@groups_bp.route('/subgroups/delete/<int:id>')
@login_required
def delete_subgroup(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups.subgroups'))
    subgroup = Subgroup.query.get_or_404(id)
    if ComponentType.query.filter_by(subgroup_id=id).first():
        flash('Нельзя удалить подгруппу, связанную с типами', 'error')
    else:
        db.session.delete(subgroup)
        db.session.commit()
        flash('Подгруппа удалена!', 'success')
    return redirect(url_for('groups.subgroups'))

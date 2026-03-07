from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_required, current_user
from passlib.hash import pbkdf2_sha256

from app.extensions import db
from app.models import User, Component, Order, ComponentHistory
from app.forms import UserForm

users_bp = Blueprint('users', __name__, url_prefix='/users')


@users_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    form = UserForm()
    if form.validate_on_submit():
        hashed_password = pbkdf2_sha256.hash(form.password.data) if form.password.data else None
        if User.query.filter_by(username=form.username.data).first():
            flash('Пользователь с таким именем уже существует', 'error')
        else:
            user = User(
                username=form.username.data,
                password=hashed_password if hashed_password else pbkdf2_sha256.hash('default123'),
                role=form.role.data,
                can_create_groups=form.can_create_groups.data,
                can_edit_groups=form.can_edit_groups.data,
                can_delete_groups=form.can_delete_groups.data,
                can_view_groups=form.can_view_groups.data,
                can_create_subgroups=form.can_create_subgroups.data,
                can_edit_subgroups=form.can_edit_subgroups.data,
                can_delete_subgroups=form.can_delete_subgroups.data,
                can_view_subgroups=form.can_view_subgroups.data,
                can_create_types=form.can_create_types.data,
                can_edit_types=form.can_edit_types.data,
                can_delete_types=form.can_delete_types.data,
                can_view_types=form.can_view_types.data,
                can_create_housings=form.can_create_housings.data,
                can_edit_housings=form.can_edit_housings.data,
                can_delete_housings=form.can_delete_housings.data,
                can_view_housings=form.can_view_housings.data,
                can_create_components=form.can_create_components.data,
                can_edit_components=form.can_edit_components.data,
                can_delete_components=form.can_delete_components.data,
                can_view_components=form.can_view_components.data,
            )
            db.session.add(user)
            db.session.commit()
            flash('Пользователь успешно добавлен!', 'success')
            return redirect(url_for('users.index'))
    users = User.query.all()
    return render_template('users.html', form=form, users=users)


@users_bp.route('/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        existing = User.query.filter_by(username=form.username.data).first()
        if existing and existing.id != user.id:
            flash('Пользователь с таким именем уже существует', 'error')
        else:
            user.username = form.username.data
            if form.password.data:
                user.password = pbkdf2_sha256.hash(form.password.data)
            user.role = form.role.data
            user.can_create_groups = form.can_create_groups.data
            user.can_edit_groups = form.can_edit_groups.data
            user.can_delete_groups = form.can_delete_groups.data
            user.can_view_groups = form.can_view_groups.data
            user.can_create_subgroups = form.can_create_subgroups.data
            user.can_edit_subgroups = form.can_edit_subgroups.data
            user.can_delete_subgroups = form.can_delete_subgroups.data
            user.can_view_subgroups = form.can_view_subgroups.data
            user.can_create_types = form.can_create_types.data
            user.can_edit_types = form.can_edit_types.data
            user.can_delete_types = form.can_delete_types.data
            user.can_view_types = form.can_view_types.data
            user.can_create_housings = form.can_create_housings.data
            user.can_edit_housings = form.can_edit_housings.data
            user.can_delete_housings = form.can_delete_housings.data
            user.can_view_housings = form.can_view_housings.data
            user.can_create_components = form.can_create_components.data
            user.can_edit_components = form.can_edit_components.data
            user.can_delete_components = form.can_delete_components.data
            user.can_view_components = form.can_view_components.data
            db.session.commit()
            flash('Пользователь успешно обновлён!', 'success')
            return redirect(url_for('users.index'))
    return render_template('user_edit.html', form=form, user=user)


@users_bp.route('/delete/<int:id>')
@login_required
def delete(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components.index'))
    user = User.query.get_or_404(id)
    if user.role == 'super_admin':
        flash('Нельзя удалить супер админа', 'error')
    elif (Component.query.filter_by(created_by_id=user.id).first()
          or Order.query.filter_by(user_id=user.id).first()
          or ComponentHistory.query.filter_by(user_id=user.id).first()):
        flash('Нельзя удалить пользователя, связанного с компонентами, заказами или историей изменений', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Пользователь удалён!', 'success')
    return redirect(url_for('users.index'))

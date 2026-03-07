from flask import Blueprint, render_template, redirect, url_for, flash
from flask_login import login_user, logout_user, login_required, current_user
from passlib.hash import pbkdf2_sha256

from app.extensions import db
from app.models import User
from app.forms import LoginForm, RegisterForm

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('components.index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and pbkdf2_sha256.verify(form.password.data, user.password):
            login_user(user)
            return redirect(url_for('components.index'))
        flash('Неверное имя пользователя или пароль', 'error')
    return render_template('login.html', form=form)


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('components.index'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Пользователь уже существует', 'error')
        else:
            new_user = User(
                username=form.username.data,
                password=pbkdf2_sha256.hash(form.password.data),
                role='user',
                can_create_groups=False, can_edit_groups=False, can_delete_groups=False, can_view_groups=True,
                can_create_subgroups=False, can_edit_subgroups=False, can_delete_subgroups=False, can_view_subgroups=True,
                can_create_types=False, can_edit_types=False, can_delete_types=False, can_view_types=True,
                can_create_housings=False, can_edit_housings=False, can_delete_housings=False, can_view_housings=True,
                can_create_components=False, can_edit_components=False, can_delete_components=False, can_view_components=True,
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Пользователь успешно зарегистрирован!', 'success')
            return redirect(url_for('auth.login'))
    return render_template('register.html', form=form)


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

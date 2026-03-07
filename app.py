from flask import Flask, render_template, redirect, url_for, flash, request, send_file, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SelectField, IntegerField, FloatField, DateTimeField, TextAreaField, BooleanField, SelectMultipleField
from wtforms.validators import DataRequired, NumberRange, Optional
from passlib.hash import pbkdf2_sha256
import json
from datetime import datetime
import io
import csv
from sqlalchemy.exc import IntegrityError
from models import db, User, Group, Subgroup, ComponentType, Housing, Component, Order, ComponentHistory
from forms import LoginForm, RegisterForm, UserForm, ComponentForm, GroupForm, SubgroupForm, ComponentTypeForm, HousingForm, OrderForm, SearchForm
from component_structure import structure, housing_list

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///inventory.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

@app.route('/')
def index():
    return redirect(url_for('components'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('components'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if user and pbkdf2_sha256.verify(form.password.data, user.password):
            login_user(user)
            return redirect(url_for('components'))
        flash('Неверное имя пользователя или пароль', 'error')
    return render_template('login.html', form=form)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('components'))
    form = RegisterForm()
    if form.validate_on_submit():
        if User.query.filter_by(username=form.username.data).first():
            flash('Пользователь уже существует', 'error')
        else:
            hashed_password = pbkdf2_sha256.hash(form.password.data)
            new_user = User(
                username=form.username.data,
                password=hashed_password,
                role='user',
                can_create_groups=False,
                can_edit_groups=False,
                can_delete_groups=False,
                can_view_groups=True,
                can_create_subgroups=False,
                can_edit_subgroups=False,
                can_delete_subgroups=False,
                can_view_subgroups=True,
                can_create_types=False,
                can_edit_types=False,
                can_delete_types=False,
                can_view_types=True,
                can_create_housings=False,
                can_edit_housings=False,
                can_delete_housings=False,
                can_view_housings=True,
                can_create_components=False,
                can_edit_components=False,
                can_delete_components=False,
                can_view_components=True
            )
            db.session.add(new_user)
            db.session.commit()
            flash('Пользователь успешно зарегистрирован!', 'success')
            return redirect(url_for('login'))
    return render_template('register.html', form=form)

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

@app.route('/users', methods=['GET', 'POST'])
@login_required
def users():
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    form = UserForm()
    if form.validate_on_submit():
        hashed_password = pbkdf2_sha256.hash(form.password.data) if form.password.data else None
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user:
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
                can_view_components=form.can_view_components.data
            )
            db.session.add(user)
            db.session.commit()
            flash('Пользователь успешно добавлен!', 'success')
            return redirect(url_for('users'))
    users = User.query.all()
    return render_template('users.html', form=form, users=users)

@app.route('/users/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_user(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    user = User.query.get_or_404(id)
    form = UserForm(obj=user)
    if form.validate_on_submit():
        existing_user = User.query.filter_by(username=form.username.data).first()
        if existing_user and existing_user.id != user.id:
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
            return redirect(url_for('users'))
    return render_template('user_edit.html', form=form, user=user)

@app.route('/users/delete/<int:id>')
@login_required
def delete_user(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    user = User.query.get_or_404(id)
    if user.role == 'super_admin':
        flash('Нельзя удалить супер админа', 'error')
    elif Component.query.filter_by(created_by_id=user.id).first() or Order.query.filter_by(user_id=user.id).first() or ComponentHistory.query.filter_by(user_id=user.id).first():
        flash('Нельзя удалить пользователя, связанного с компонентами, заказами или историей изменений', 'error')
    else:
        db.session.delete(user)
        db.session.commit()
        flash('Пользователь удалён!', 'success')
    return redirect(url_for('users'))

@app.route('/groups', methods=['GET', 'POST'])
@login_required
def groups():
    if not (current_user.role == 'super_admin' or current_user.can_view_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    form = GroupForm()
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_groups):
        try:
            group = Group(name=form.name.data)
            db.session.add(group)
            db.session.commit()
            flash('Группа добавлена!', 'success')
            return redirect(url_for('groups'))
        except IntegrityError:
            db.session.rollback()
            flash('Группа с таким названием уже существует', 'error')
    groups = Group.query.all()
    return render_template('groups.html', form=form, groups=groups, can_edit=(current_user.role == 'super_admin' or current_user.can_edit_groups), can_delete=(current_user.role == 'super_admin' or current_user.can_delete_groups))

@app.route('/groups/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_group(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups'))
    group = Group.query.get_or_404(id)
    form = GroupForm(obj=group)
    if form.validate_on_submit():
        try:
            group.name = form.name.data
            db.session.commit()
            flash('Группа обновлена!', 'success')
            return redirect(url_for('groups'))
        except IntegrityError:
            db.session.rollback()
            flash('Группа с таким названием уже существует', 'error')
    return render_template('group_form.html', form=form, group=group)

@app.route('/groups/delete/<int:id>')
@login_required
def delete_group(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_groups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('groups'))
    group = Group.query.get_or_404(id)
    if Subgroup.query.filter_by(group_id=id).first():
        flash('Нельзя удалить группу, связанную с подгруппами', 'error')
    else:
        db.session.delete(group)
        db.session.commit()
        flash('Группа удалена!', 'success')
    return redirect(url_for('groups'))

@app.route('/subgroups', methods=['GET', 'POST'])
@login_required
def subgroups():
    if not (current_user.role == 'super_admin' or current_user.can_view_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    form = SubgroupForm()
    form.group_id.choices = [(g.id, g.name) for g in Group.query.all()]
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_subgroups):
        try:
            units = form.units.data.split(',')
            subgroup = Subgroup(name=form.name.data, group_id=form.group_id.data, units_schema=json.dumps(units, ensure_ascii=False))
            db.session.add(subgroup)
            db.session.commit()
            flash('Подгруппа добавлена!', 'success')
            return redirect(url_for('subgroups'))
        except IntegrityError:
            db.session.rollback()
            flash('Подгруппа с таким названием уже существует в этой группе', 'error')
    subgroups = Subgroup.query.all()
    return render_template('subgroups.html', form=form, subgroups=subgroups, can_edit=(current_user.role == 'super_admin' or current_user.can_edit_subgroups), can_delete=(current_user.role == 'super_admin' or current_user.can_delete_subgroups))

@app.route('/subgroups/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_subgroup(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('subgroups'))
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
            return redirect(url_for('subgroups'))
        except IntegrityError:
            db.session.rollback()
            flash('Подгруппа с таким названием уже существует в этой группе', 'error')
    form.units.data = ','.join(json.loads(subgroup.units_schema))
    return render_template('subgroup_form.html', form=form, subgroup=subgroup)

@app.route('/subgroups/delete/<int:id>')
@login_required
def delete_subgroup(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_subgroups):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('subgroups'))
    subgroup = Subgroup.query.get_or_404(id)
    if ComponentType.query.filter_by(subgroup_id=id).first():
        flash('Нельзя удалить подгруппу, связанную с типами', 'error')
    else:
        db.session.delete(subgroup)
        db.session.commit()
        flash('Подгруппа удалена!', 'success')
    return redirect(url_for('subgroups'))

@app.route('/types', methods=['GET', 'POST'])
@login_required
def types():
    if not (current_user.role == 'super_admin' or current_user.can_view_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    form = ComponentTypeForm()
    form.subgroup_id.choices = [(s.id, f"{s.group.name} - {s.name}") for s in Subgroup.query.all()]
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_types):
        try:
            component_type = ComponentType(name=form.name.data, subgroup_id=form.subgroup_id.data)
            db.session.add(component_type)
            db.session.commit()
            flash('Тип добавлен!', 'success')
            return redirect(url_for('types'))
        except IntegrityError:
            db.session.rollback()
            flash('Тип с таким названием уже существует в этой подгруппе', 'error')
    types = ComponentType.query.all()
    return render_template('types.html', form=form, types=types, can_edit=(current_user.role == 'super_admin' or current_user.can_edit_types), can_delete=(current_user.role == 'super_admin' or current_user.can_delete_types))

@app.route('/types/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_type(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('types'))
    component_type = ComponentType.query.get_or_404(id)
    form = ComponentTypeForm(obj=component_type)
    form.subgroup_id.choices = [(s.id, f"{s.group.name} - {s.name}") for s in Subgroup.query.all()]
    if form.validate_on_submit():
        try:
            component_type.name = form.name.data
            component_type.subgroup_id = form.subgroup_id.data
            db.session.commit()
            flash('Тип обновлён!', 'success')
            return redirect(url_for('types'))
        except IntegrityError:
            db.session.rollback()
            flash('Тип с таким названием уже существует в этой подгруппе', 'error')
    return render_template('type_form.html', form=form, component_type=component_type)

@app.route('/types/delete/<int:id>')
@login_required
def delete_type(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_types):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('types'))
    component_type = ComponentType.query.get_or_404(id)
    if Component.query.filter_by(type_id=id).first():
        flash('Нельзя удалить тип, используемый в компонентах', 'error')
    else:
        db.session.delete(component_type)
        db.session.commit()
        flash('Тип удалён!', 'success')
    return redirect(url_for('types'))

@app.route('/housings', methods=['GET', 'POST'])
@login_required
def housings():
    if not (current_user.role == 'super_admin' or current_user.can_view_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    form = HousingForm()
    if form.validate_on_submit() and (current_user.role == 'super_admin' or current_user.can_create_housings):
        try:
            housing = Housing(housing_name=form.housing_name.data)
            db.session.add(housing)
            db.session.commit()
            flash('Корпус добавлен!', 'success')
            return redirect(url_for('housings'))
        except IntegrityError:
            db.session.rollback()
            flash('Корпус с таким названием уже существует', 'error')
    housings = Housing.query.all()
    return render_template('housings.html', form=form, housings=housings, can_edit=(current_user.role == 'super_admin' or current_user.can_edit_housings), can_delete=(current_user.role == 'super_admin' or current_user.can_delete_housings))

@app.route('/housings/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_housing(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('housings'))
    housing = Housing.query.get_or_404(id)
    form = HousingForm(obj=housing)
    if form.validate_on_submit():
        try:
            housing.housing_name = form.housing_name.data
            db.session.commit()
            flash('Корпус обновлён!', 'success')
            return redirect(url_for('housings'))
        except IntegrityError:
            db.session.rollback()
            flash('Корпус с таким названием уже существует', 'error')
    return render_template('housing_form.html', form=form, housing=housing)

@app.route('/housings/delete/<int:id>')
@login_required
def delete_housing(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_housings):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('housings'))
    housing = Housing.query.get_or_404(id)
    if Component.query.filter_by(housing_id=id).first():
        flash('Нельзя удалить корпус, используемый в компонентах', 'error')
    else:
        db.session.delete(housing)
        db.session.commit()
        flash('Корпус удалён!', 'success')
    return redirect(url_for('housings'))

@app.route('/components', methods=['GET', 'POST'])
@login_required
def components():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра компонентов', 'error')
        return redirect(url_for('index'))
    
    form = SearchForm()
    form.group_id.choices = [(0, 'Все группы')] + [(g.id, g.name) for g in Group.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_groups) else [(0, 'Все группы')]
    form.subgroup_id.choices = [(0, 'Все подгруппы')] + [(s.id, s.name) for s in Subgroup.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_subgroups) else [(0, 'Все подгруппы')]
    form.type_id.choices = [(0, 'Все типы')] + [(t.id, t.name) for t in ComponentType.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_types) else [(0, 'Все типы')]
    
    search = form.search.data if form.validate_on_submit() else request.args.get('search', '')
    group_id = form.group_id.data if form.validate_on_submit() else request.args.get('group_id', type=int, default=0)
    subgroup_id = form.subgroup_id.data if form.validate_on_submit() else request.args.get('subgroup_id', type=int, default=0)
    type_id = form.type_id.data if form.validate_on_submit() else request.args.get('type_id', type=int, default=0)
    page = request.args.get('page', 1, type=int)
    
    query = Component.query.filter_by(is_archived=False)
    if current_user.role == 'admin':
        query = query.filter_by(created_by_id=current_user.id)
    if search:
        query = query.filter(Component.name.ilike(f'%{search}%') | Component.manufacturer.ilike(f'%{search}%'))
    if type_id:
        query = query.filter_by(type_id=type_id)
    elif subgroup_id:
        query = query.join(ComponentType).filter(ComponentType.subgroup_id==subgroup_id)
    elif group_id:
        query = query.join(ComponentType).join(Subgroup).filter(Subgroup.group_id==group_id)
    
    components = query.paginate(page=page, per_page=10)
    return render_template('components.html', components=components, form=form, search=search, group_id=group_id, subgroup_id=subgroup_id, type_id=type_id)

@app.route('/components/add', methods=['GET', 'POST'])
@login_required
def add_component():
    if not (current_user.role == 'super_admin' or current_user.can_create_components):
        flash('У вас нет прав для создания компонентов', 'error')
        return redirect(url_for('components'))
    
    form = ComponentForm()
    group_id = request.form.get('group_id', type=int, default=0) or form.group_id.data
    subgroup_id = request.form.get('subgroup_id', type=int, default=0) or form.subgroup_id.data
    
    form.group_id.choices = [(0, 'Выберите группу')] + [(g.id, g.name) for g in Group.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_groups) else [(0, 'Выберите группу')]
    form.subgroup_id.choices = [(0, 'Выберите подгруппу')] + [(s.id, s.name) for s in Subgroup.query.filter_by(group_id=group_id).all()] if group_id and (current_user.role == 'super_admin' or current_user.can_view_subgroups) else [(0, 'Выберите подгруппу')]
    form.type_id.choices = [(0, 'Выберите тип')] + [(t.id, t.name) for t in ComponentType.query.filter_by(subgroup_id=subgroup_id).all()] if subgroup_id and (current_user.role == 'super_admin' or current_user.can_view_types) else [(0, 'Выберите тип')]
    form.housing_id.choices = [(h.id, h.housing_name) for h in Housing.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_housings) else []
    form.unit.choices = [(u, u) for u in json.loads(Subgroup.query.get(subgroup_id).units_schema)] + [('', 'Выберите единицу')] if subgroup_id else [('', 'Выберите единицу')]
    
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
            is_archived=False
        )
        try:
            db.session.add(component)
            db.session.flush()  # Получаем ID компонента
            history = ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='create',
                timestamp=datetime.utcnow()
            )
            db.session.add(history)
            db.session.commit()
            flash('Компонент добавлен!', 'success')
            return redirect(url_for('components'))
        except IntegrityError:
            db.session.rollback()
            flash('Компонент с таким названием уже существует', 'error')
            return render_template('component_form.html', form=form, action='add')
    
    return render_template('component_form.html', form=form, action='add')

@app.route('/components/edit/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_component(id):
    if not (current_user.role == 'super_admin' or current_user.can_edit_components):
        flash('У вас нет прав для редактирования компонентов', 'error')
        return redirect(url_for('components'))
    
    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете редактировать только свои записи', 'error')
        return redirect(url_for('components'))
    
    form = ComponentForm()
    group_id = request.form.get('group_id', type=int, default=0) or (component.comp_type.subgroup.group_id if component else 0)
    subgroup_id = request.form.get('subgroup_id', type=int, default=0) or (component.comp_type.subgroup_id if component else 0)
    
    form.group_id.choices = [(0, 'Выберите группу')] + [(g.id, g.name) for g in Group.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_groups) else [(0, 'Выберите группу')]
    form.subgroup_id.choices = [(0, 'Выберите подгруппу')] + [(s.id, s.name) for s in Subgroup.query.filter_by(group_id=group_id).all()] if group_id and (current_user.role == 'super_admin' or current_user.can_view_subgroups) else [(0, 'Выберите подгруппу')]
    form.type_id.choices = [(0, 'Выберите тип')] + [(t.id, t.name) for t in ComponentType.query.filter_by(subgroup_id=subgroup_id).all()] if subgroup_id and (current_user.role == 'super_admin' or current_user.can_view_types) else [(0, 'Выберите тип')]
    form.housing_id.choices = [(h.id, h.housing_name) for h in Housing.query.all()] if (current_user.role == 'super_admin' or current_user.can_view_housings) else []
    form.unit.choices = [(u, u) for u in json.loads(Subgroup.query.get(subgroup_id).units_schema)] + [('', 'Выберите единицу')] if subgroup_id else [('', 'Выберите единицу')]
    
    if form.validate_on_submit():
        if form.group_id.data == 0 or form.subgroup_id.data == 0 or form.type_id.data == 0 or not form.unit.data:
            flash('Выберите группу, подгруппу, тип и единицу измерения', 'error')
            return render_template('component_form.html', form=form, action='edit', component=component)
        
        # Записываем изменения в историю
        changes = []
        if component.name != form.name.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='name',
                old_value=str(component.name),
                new_value=str(form.name.data),
                timestamp=datetime.utcnow()
            ))
        if component.type_id != form.type_id.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='type_id',
                old_value=str(component.type_id),
                new_value=str(form.type_id.data),
                timestamp=datetime.utcnow()
            ))
        if component.housing_id != form.housing_id.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='housing_id',
                old_value=str(component.housing_id),
                new_value=str(form.housing_id.data),
                timestamp=datetime.utcnow()
            ))
        if component.manufacturer != form.manufacturer.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='manufacturer',
                old_value=str(component.manufacturer),
                new_value=str(form.manufacturer.data),
                timestamp=datetime.utcnow()
            ))
        if component.quantity != form.quantity.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='quantity',
                old_value=str(component.quantity),
                new_value=str(form.quantity.data),
                timestamp=datetime.utcnow()
            ))
        if component.price != form.price.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='price',
                old_value=str(component.price),
                new_value=str(form.price.data),
                timestamp=datetime.utcnow()
            ))
        if component.arrival_date != form.arrival_date.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='arrival_date',
                old_value=str(component.arrival_date),
                new_value=str(form.arrival_date.data),
                timestamp=datetime.utcnow()
            ))
        if component.location != form.location.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='location',
                old_value=str(component.location),
                new_value=str(form.location.data),
                timestamp=datetime.utcnow()
            ))
        if component.nominal_value != form.nominal_value.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='nominal_value',
                old_value=str(component.nominal_value),
                new_value=str(form.nominal_value.data),
                timestamp=datetime.utcnow()
            ))
        if component.unit != form.unit.data:
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='unit',
                old_value=str(component.unit),
                new_value=str(form.unit.data),
                timestamp=datetime.utcnow()
            ))
        if component.parameters != json.dumps(form.additional_parameters.data):
            changes.append(ComponentHistory(
                unique_id=component.unique_id,
                user_id=current_user.id,
                action='update',
                field_changed='parameters',
                old_value=str(component.parameters),
                new_value=json.dumps(form.additional_parameters.data),
                timestamp=datetime.utcnow()
            ))

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
            return redirect(url_for('components'))
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

@app.route('/components/delete/<int:id>')
@login_required
def delete_component(id):
    if not (current_user.role == 'super_admin' or current_user.can_delete_components):
        flash('У вас нет прав для удаления компонентов', 'error')
        return redirect(url_for('components'))
    
    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете удалять только свои записи', 'error')
        return redirect(url_for('components'))
    
    if Order.query.filter_by(component_id=id).first():
        flash('Нельзя удалить компонент, связанный с заказами', 'error')
        return redirect(url_for('components'))
    
    try:
        component.is_archived = True
        history = ComponentHistory(
            unique_id=component.unique_id,
            user_id=current_user.id,
            action='archive',
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        db.session.commit()
        flash('Компонент перемещён в архив!', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash(f'Ошибка при архивировании компонента: {str(e)}', 'error')
        app.logger.error(f'Ошибка при архивировании компонента {id}: {str(e)}')
    
    return redirect(url_for('components'))

@app.route('/components/history/<int:id>')
@login_required
def component_history(id):
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра истории компонентов', 'error')
        return redirect(url_for('components'))
    
    component = Component.query.get_or_404(id)
    if current_user.role == 'admin' and component.created_by_id != current_user.id:
        flash('Вы можете просматривать только свои записи', 'error')
        return redirect(url_for('components'))
    
    history = ComponentHistory.query.filter_by(unique_id=component.unique_id).order_by(ComponentHistory.timestamp.desc()).all()
    if not history:
        flash('История для этого компонента не найдена', 'error')
        return redirect(url_for('components'))
    
    return render_template('component_history.html', component=component, history=history)

@app.route('/archive')
@login_required
def archive():
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('components'))
    archived_components = Component.query.filter_by(is_archived=True).all()
    return render_template('archive.html', archived_components=archived_components)

@app.route('/archive/restore/<int:id>')
@login_required
def restore_archive_component(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('archive'))
    component = Component.query.get_or_404(id)
    
    if not component.is_archived:
        flash('Компонент не находится в архиве', 'error')
        return redirect(url_for('archive'))
    
    try:
        component.is_archived = False
        history = ComponentHistory(
            unique_id=component.unique_id,
            user_id=current_user.id,
            action='restore',
            timestamp=datetime.utcnow()
        )
        db.session.add(history)
        db.session.commit()
        flash('Компонент успешно восстановлен!', 'success')
    except IntegrityError as e:
        db.session.rollback()
        flash(f'Ошибка при восстановлении компонента: {str(e)}', 'error')
        app.logger.error(f'Ошибка при восстановлении компонента {id}: {str(e)}')
    
    return redirect(url_for('components'))

@app.route('/archive/delete/<int:id>')
@login_required
def delete_archive_component(id):
    if current_user.role != 'super_admin':
        flash('Доступ запрещён', 'error')
        return redirect(url_for('archive'))
    component = Component.query.get_or_404(id)
    
    if not component.is_archived:
        flash('Компонент не находится в архиве', 'error')
        return redirect(url_for('archive'))
    
    try:
        ComponentHistory.query.filter_by(unique_id=component.unique_id).delete()
        db.session.delete(component)
        db.session.commit()
        flash('Компонент окончательно удалён из архива!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении компонента из архива: {str(e)}', 'error')
        app.logger.error(f'Ошибка при удалении компонента {id}: {str(e)}')
    
    return redirect(url_for('archive'))

@app.route('/orders', methods=['GET', 'POST'])
@login_required
def orders():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('index'))
    form = OrderForm()
    form.component_id.choices = [(c.id, c.name) for c in Component.query.filter_by(is_archived=False).all()]
    if form.validate_on_submit():
        component = Component.query.get_or_404(form.component_id.data)
        if component.quantity < form.quantity.data:
            flash('Недостаточно компонентов на складе!', 'error')
        else:
            component.quantity -= form.quantity.data
            order = Order(
                component_id=form.component_id.data,
                quantity=form.quantity.data,
                date=datetime.utcnow(),
                user_id=current_user.id
            )
            db.session.add(order)
            db.session.commit()
            flash('Заказ создан!', 'success')
        return redirect(url_for('orders'))
    orders = Order.query.paginate(per_page=10)
    return render_template('orders.html', form=form, orders=orders)

@app.route('/report')
@login_required
def report():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра отчёта', 'error')
        return redirect(url_for('index'))
    
    components = Component.query.filter(Component.quantity < 10, Component.is_archived == False).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Название', 'Группа', 'Подгруппа', 'Тип', 'Корпус', 'Производитель', 'Количество', 'Цена', 'Номинал', 'Единица'])
    for c in components:
        writer.writerow([
            c.id, c.name, c.comp_type.subgroup.group.name, c.comp_type.subgroup.name, c.comp_type.name,
            c.housing.housing_name if c.housing else '', c.manufacturer, c.quantity, c.price, c.nominal_value, c.unit
        ])
    
    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='low_stock_report.csv'
    )

@app.route('/get_subgroups/<int:group_id>')
def get_subgroups(group_id):
    if not (current_user.role == 'super_admin' or current_user.can_view_subgroups):
        return jsonify([])
    subgroups = Subgroup.query.filter_by(group_id=group_id).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subgroups])

@app.route('/get_types/<int:subgroup_id>')
def get_types(subgroup_id):
    if not (current_user.role == 'super_admin' or current_user.can_view_types):
        return jsonify([])
    types = ComponentType.query.filter_by(subgroup_id=subgroup_id).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in types])

@app.route('/get_units/<int:subgroup_id>')
def get_units(subgroup_id):
    if not (current_user.role == 'super_admin' or current_user.can_view_subgroups):
        return jsonify([])
    subgroup = Subgroup.query.get(subgroup_id)
    if subgroup:
        units = json.loads(subgroup.units_schema)
        return jsonify([{'unit': u} for u in units])
    return jsonify([])

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        print(f"Созданные таблицы после db.create_all(): {db.Model.metadata.tables.keys()}")

        # Создание начальных данных
        if not User.query.filter_by(username='super_admin').first():
            hashed_password = pbkdf2_sha256.hash('super123')
            super_admin = User(
                username='super_admin',
                password=hashed_password,
                role='super_admin',
                can_create_groups=True,
                can_edit_groups=True,
                can_delete_groups=True,
                can_view_groups=True,
                can_create_subgroups=True,
                can_edit_subgroups=True,
                can_delete_subgroups=True,
                can_view_subgroups=True,
                can_create_types=True,
                can_edit_types=True,
                can_delete_types=True,
                can_view_types=True,
                can_create_housings=True,
                can_edit_housings=True,
                can_delete_housings=True,
                can_view_housings=True,
                can_create_components=True,
                can_edit_components=True,
                can_delete_components=True,
                can_view_components=True
            )
            db.session.add(super_admin)
            db.session.commit()

        # Добавление групп, подгрупп, типов и корпусов
        for group_name, subgroups in structure.items():
            group = Group.query.filter_by(name=group_name).first()
            if not group:
                group = Group(name=group_name)
                db.session.add(group)
                db.session.commit()
            for subgroup_name, data in subgroups.items():
                subgroup = Subgroup.query.filter_by(name=subgroup_name, group_id=group.id).first()
                if not subgroup:
                    subgroup = Subgroup(
                        name=subgroup_name,
                        group_id=group.id,
                        units_schema=json.dumps(data['units'], ensure_ascii=False)
                    )
                    db.session.add(subgroup)
                    db.session.commit()
                for type_name in data['types']:
                    component_type = ComponentType.query.filter_by(name=type_name, subgroup_id=subgroup.id).first()
                    if not component_type:
                        component_type = ComponentType(name=type_name, subgroup_id=subgroup.id)
                        db.session.add(component_type)
                        db.session.commit()

        for housing_name in housing_list:
            housing = Housing.query.filter_by(housing_name=housing_name).first()
            if not housing:
                housing = Housing(housing_name=housing_name)
                db.session.add(housing)
                db.session.commit()

        # Добавление тестового компонента
        if not Component.query.first():
            component_type = ComponentType.query.first()
            housing = Housing.query.first()
            super_admin = User.query.filter_by(username='super_admin').first()
            component = Component(
                name='Тестовый резистор',
                type_id=component_type.id,
                housing_id=housing.id,
                manufacturer='Test Manufacturer',
                quantity=100,
                price=0.1,
                arrival_date=datetime.utcnow(),
                location='Склад 1',
                nominal_value=1000,
                unit='Ohm',
                parameters=json.dumps({'description': 'Тестовый компонент'}),
                created_by_id=super_admin.id,
                is_archived=False
            )
            db.session.add(component)
            db.session.flush()  # Получаем ID компонента
            history = ComponentHistory(
                unique_id=component.unique_id,
                user_id=super_admin.id,
                action='create',
                timestamp=datetime.utcnow()
            )
            db.session.add(history)
            db.session.commit()

    app.run(debug=True, host='0.0.0.0', port=5500)
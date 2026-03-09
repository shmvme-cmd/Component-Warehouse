from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import StringField, PasswordField, SelectField, IntegerField, FloatField, DateTimeField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Optional, NumberRange
from datetime import datetime


class LoginForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Войти')


class RegisterForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


class UserForm(FlaskForm):
    username = StringField('Имя пользователя', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[Optional()])
    role = SelectField('Роль', choices=[('user', 'Пользователь'), ('admin', 'Администратор'), ('super_admin', 'Супер администратор')], validators=[DataRequired()])
    can_create_groups = BooleanField('Создание групп')
    can_edit_groups = BooleanField('Редактирование групп')
    can_delete_groups = BooleanField('Удаление групп')
    can_view_groups = BooleanField('Просмотр групп')
    can_create_subgroups = BooleanField('Создание подгрупп')
    can_edit_subgroups = BooleanField('Редактирование подгрупп')
    can_delete_subgroups = BooleanField('Удаление подгрупп')
    can_view_subgroups = BooleanField('Просмотр подгрупп')
    can_create_types = BooleanField('Создание типов')
    can_edit_types = BooleanField('Редактирование типов')
    can_delete_types = BooleanField('Удаление типов')
    can_view_types = BooleanField('Просмотр типов')
    can_create_housings = BooleanField('Создание корпусов')
    can_edit_housings = BooleanField('Редактирование корпусов')
    can_delete_housings = BooleanField('Удаление корпусов')
    can_view_housings = BooleanField('Просмотр корпусов')
    can_create_components = BooleanField('Создание компонентов')
    can_edit_components = BooleanField('Редактирование компонентов')
    can_delete_components = BooleanField('Удаление компонентов')
    can_view_components = BooleanField('Просмотр компонентов')
    submit = SubmitField('Сохранить')


class ComponentForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    group_id = SelectField('Группа', choices=[(0, 'Выберите группу')], coerce=int)
    subgroup_id = SelectField('Подгруппа', choices=[(0, 'Выберите подгруппу')], coerce=int)
    type_id = SelectField('Тип', choices=[(0, 'Выберите тип')], coerce=int, validators=[Optional()])
    housing_id = SelectField('Корпус', coerce=int, validators=[Optional()])
    manufacturer = StringField('Производитель', validators=[Optional()])
    quantity = IntegerField('Количество', validators=[DataRequired(), NumberRange(min=0)])
    price = FloatField('Цена', validators=[Optional()])
    arrival_date = DateTimeField('Дата поступления', format='%Y-%m-%d', default=datetime.now, validators=[Optional()])
    location = StringField('Местоположение', validators=[Optional()])
    nominal_value = FloatField('Номинал', validators=[Optional()])
    unit = SelectField('Единица измерения', choices=[('', 'Выберите единицу')], validators=[Optional()])
    additional_parameters = StringField('Дополнительные параметры', validators=[Optional()])
    submit = SubmitField('Сохранить')


class GroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class SubgroupForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    group_id = SelectField('Группа', coerce=int, validators=[DataRequired()])
    units = StringField('Единицы измерения (через запятую)', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class ComponentTypeForm(FlaskForm):
    name = StringField('Название', validators=[DataRequired()])
    subgroup_id = SelectField('Подгруппа', coerce=int, validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class HousingForm(FlaskForm):
    housing_name = StringField('Название корпуса', validators=[DataRequired()])
    submit = SubmitField('Сохранить')


class OrderForm(FlaskForm):
    component_id = SelectField('Компонент', coerce=int, validators=[DataRequired()])
    quantity = IntegerField('Количество', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Создать заказ')


class ProductForm(FlaskForm):
    name = StringField('Название изделия', validators=[DataRequired()])
    description = StringField('Описание', validators=[Optional()])
    submit = SubmitField('Создать')


class BomImportForm(FlaskForm):
    bom_file = FileField('BOM-файл (CSV)', validators=[
        FileRequired(),
        FileAllowed(['csv'], 'Только CSV-файлы'),
    ])
    product_name = StringField('Название изделия (пусто = из имени файла)', validators=[Optional()])
    submit = SubmitField('Импортировать')


class ProduceForm(FlaskForm):
    quantity = IntegerField('Количество изделий', validators=[DataRequired(), NumberRange(min=1)])
    submit = SubmitField('Списать компоненты')


class LibraryItemForm(FlaskForm):
    name = StringField('Название / артикул', validators=[DataRequired()])
    group_id = SelectField('Группа', choices=[(0, 'Выберите группу')], coerce=int)
    subgroup_id = SelectField('Подгруппа', choices=[(0, 'Выберите подгруппу')], coerce=int)
    type_id = SelectField('Тип', choices=[(0, 'Выберите тип')], coerce=int, validators=[Optional()])
    housing_id = SelectField('Корпус', coerce=int, validators=[Optional()])
    manufacturer = StringField('Производитель', validators=[Optional()])
    nominal_value = FloatField('Номинал', validators=[Optional()])
    unit = StringField('Единица', validators=[Optional()])
    description = StringField('Описание', validators=[Optional()])
    submit = SubmitField('Сохранить')


class SearchForm(FlaskForm):
    search = StringField('Поиск', validators=[Optional()])
    group_id = SelectField('Группа', choices=[(0, 'Все группы')], coerce=int, validators=[Optional()])
    subgroup_id = SelectField('Подгруппа', choices=[(0, 'Все подгруппы')], coerce=int, validators=[Optional()])
    type_id = SelectField('Тип', choices=[(0, 'Все типы')], coerce=int, validators=[Optional()])
    submit = SubmitField('Фильтровать')

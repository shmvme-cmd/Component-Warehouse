from flask_login import UserMixin
from datetime import datetime
import uuid

from app.extensions import db


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='user')
    can_create_groups = db.Column(db.Boolean, default=False)
    can_edit_groups = db.Column(db.Boolean, default=False)
    can_delete_groups = db.Column(db.Boolean, default=False)
    can_view_groups = db.Column(db.Boolean, default=True)
    can_create_subgroups = db.Column(db.Boolean, default=False)
    can_edit_subgroups = db.Column(db.Boolean, default=False)
    can_delete_subgroups = db.Column(db.Boolean, default=False)
    can_view_subgroups = db.Column(db.Boolean, default=True)
    can_create_types = db.Column(db.Boolean, default=False)
    can_edit_types = db.Column(db.Boolean, default=False)
    can_delete_types = db.Column(db.Boolean, default=False)
    can_view_types = db.Column(db.Boolean, default=True)
    can_create_housings = db.Column(db.Boolean, default=False)
    can_edit_housings = db.Column(db.Boolean, default=False)
    can_delete_housings = db.Column(db.Boolean, default=False)
    can_view_housings = db.Column(db.Boolean, default=True)
    can_create_components = db.Column(db.Boolean, default=False)
    can_edit_components = db.Column(db.Boolean, default=False)
    can_delete_components = db.Column(db.Boolean, default=False)
    can_view_components = db.Column(db.Boolean, default=True)


class Group(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    subgroups = db.relationship('Subgroup', backref='group', lazy=True, cascade="all, delete-orphan")


class Subgroup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    group_id = db.Column(db.Integer, db.ForeignKey('group.id'), nullable=False)
    units_schema = db.Column(db.Text, nullable=False)
    __table_args__ = (db.UniqueConstraint('name', 'group_id', name='unique_subgroup_name_group'),)


class ComponentType(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    subgroup_id = db.Column(db.Integer, db.ForeignKey('subgroup.id'), nullable=False)
    subgroup = db.relationship('Subgroup', backref=db.backref('types', lazy=True))
    __table_args__ = (db.UniqueConstraint('name', 'subgroup_id', name='unique_type_name_subgroup'),)


class Housing(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    housing_name = db.Column(db.String(50), unique=True, nullable=False)


class Component(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(36), unique=True, nullable=False, default=lambda: str(uuid.uuid4()))
    name = db.Column(db.String(100), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('component_type.id'), nullable=False)
    housing_id = db.Column(db.Integer, db.ForeignKey('housing.id'), nullable=True)
    manufacturer = db.Column(db.String(100))
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=True)
    arrival_date = db.Column(db.DateTime, nullable=True)
    location = db.Column(db.String(100), nullable=True)
    nominal_value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    parameters = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    is_archived = db.Column(db.Boolean, default=False, nullable=False)
    comp_type = db.relationship('ComponentType', backref=db.backref('components', lazy=True))
    housing = db.relationship('Housing', backref=db.backref('components', lazy=True))
    created_by = db.relationship('User', backref=db.backref('components', lazy=True))
    history = db.relationship('ComponentHistory', backref='component', lazy=True, cascade='all, delete-orphan')
    __table_args__ = (db.UniqueConstraint('name', 'type_id', 'housing_id', name='unique_component_name_type_housing'),)


class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    component_id = db.Column(db.Integer, db.ForeignKey('component.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    component = db.relationship('Component', backref=db.backref('orders', lazy=True))
    user = db.relationship('User', backref=db.backref('orders', lazy=True))


class ComponentHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    unique_id = db.Column(db.String(36), db.ForeignKey('component.unique_id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    action = db.Column(db.String(50), nullable=False)
    field_changed = db.Column(db.String(50), nullable=True)
    old_value = db.Column(db.Text, nullable=True)
    new_value = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    user = db.relationship('User', backref=db.backref('history', lazy=True))


class ComponentLibrary(db.Model):
    """Библиотека компонентов — спецификации без складских остатков."""
    __tablename__ = 'component_library'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False)
    type_id = db.Column(db.Integer, db.ForeignKey('component_type.id'), nullable=False)
    housing_id = db.Column(db.Integer, db.ForeignKey('housing.id'), nullable=True)
    manufacturer = db.Column(db.String(100), nullable=True)
    nominal_value = db.Column(db.Float, nullable=True)
    unit = db.Column(db.String(20), nullable=True)
    parameters = db.Column(db.Text, nullable=True)
    description = db.Column(db.Text, nullable=True)
    comp_type = db.relationship('ComponentType', backref=db.backref('library_items', lazy=True))
    housing = db.relationship('Housing', backref=db.backref('library_items', lazy=True))
    __table_args__ = (db.UniqueConstraint('name', 'type_id', 'housing_id', name='unique_lib_name_type_housing'),)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_by_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    bom_items = db.relationship('BomItem', backref='product', lazy=True,
                                cascade='all, delete-orphan')
    created_by = db.relationship('User', backref=db.backref('products', lazy=True))


class BomItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    bom_id = db.Column(db.String(20), nullable=True)
    name = db.Column(db.String(200), nullable=False)
    designator = db.Column(db.String(500), nullable=True)
    footprint = db.Column(db.String(200), nullable=True)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    manufacturer_part = db.Column(db.String(200), nullable=True)
    manufacturer = db.Column(db.String(200), nullable=True)
    supplier = db.Column(db.String(100), nullable=True)
    supplier_part = db.Column(db.String(200), nullable=True)
    price = db.Column(db.Float, nullable=True)
    component_id = db.Column(db.Integer, db.ForeignKey('component.id'), nullable=True)
    match_confidence = db.Column(db.Float, nullable=True)
    component = db.relationship('Component', backref=db.backref('bom_items', lazy=True))

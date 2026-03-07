import click
import json
from datetime import datetime
from flask.cli import with_appcontext
from passlib.hash import pbkdf2_sha256


@click.command('init-db')
@with_appcontext
def init_db_command():
    """Создать таблицы и заполнить начальными данными."""
    from app.extensions import db
    from app.models import User, Group, Subgroup, ComponentType, Housing, Component, ComponentHistory
    from app.component_structure import structure, housing_list

    db.create_all()
    click.echo('Таблицы созданы.')

    if not User.query.filter_by(username='super_admin').first():
        super_admin = User(
            username='super_admin',
            password=pbkdf2_sha256.hash('super123'),
            role='super_admin',
            can_create_groups=True, can_edit_groups=True, can_delete_groups=True, can_view_groups=True,
            can_create_subgroups=True, can_edit_subgroups=True, can_delete_subgroups=True, can_view_subgroups=True,
            can_create_types=True, can_edit_types=True, can_delete_types=True, can_view_types=True,
            can_create_housings=True, can_edit_housings=True, can_delete_housings=True, can_view_housings=True,
            can_create_components=True, can_edit_components=True, can_delete_components=True, can_view_components=True,
        )
        db.session.add(super_admin)
        db.session.commit()
        click.echo('Суперадмин создан (логин: super_admin, пароль: super123).')

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
                    units_schema=json.dumps(data['units'], ensure_ascii=False),
                )
                db.session.add(subgroup)
                db.session.commit()
            for type_name in data['types']:
                if not ComponentType.query.filter_by(name=type_name, subgroup_id=subgroup.id).first():
                    db.session.add(ComponentType(name=type_name, subgroup_id=subgroup.id))
            db.session.commit()

    for housing_name in housing_list:
        if not Housing.query.filter_by(housing_name=housing_name).first():
            db.session.add(Housing(housing_name=housing_name))
    db.session.commit()
    click.echo('Структура компонентов и корпуса загружены.')

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
            is_archived=False,
        )
        db.session.add(component)
        db.session.flush()
        db.session.add(ComponentHistory(
            unique_id=component.unique_id,
            user_id=super_admin.id,
            action='create',
            timestamp=datetime.utcnow(),
        ))
        db.session.commit()
        click.echo('Тестовый компонент добавлен.')

    click.echo('База данных инициализирована.')

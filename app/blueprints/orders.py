import csv
import io
from datetime import datetime

from flask import Blueprint, render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Component, Order
from app.forms import OrderForm

orders_bp = Blueprint('orders', __name__)


@orders_bp.route('/orders', methods=['GET', 'POST'])
@login_required
def index():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('Доступ запрещён', 'error')
        return redirect(url_for('main.index'))
    form = OrderForm()
    form.component_id.choices = [(c.id, c.name) for c in Component.query.filter_by(is_archived=False).all()]
    if form.validate_on_submit():
        component = Component.query.get_or_404(form.component_id.data)
        if component.quantity < form.quantity.data:
            flash('Недостаточно компонентов на складе!', 'error')
        else:
            component.quantity -= form.quantity.data
            db.session.add(Order(
                component_id=form.component_id.data,
                quantity=form.quantity.data,
                date=datetime.utcnow(),
                user_id=current_user.id,
            ))
            db.session.commit()
            flash('Заказ создан!', 'success')
        return redirect(url_for('orders.index'))
    orders = Order.query.paginate(per_page=10)
    return render_template('orders.html', form=form, orders=orders)


@orders_bp.route('/report')
@login_required
def report():
    if not (current_user.role == 'super_admin' or current_user.can_view_components):
        flash('У вас нет прав для просмотра отчёта', 'error')
        return redirect(url_for('main.index'))

    components = Component.query.filter(
        Component.quantity < 10, Component.is_archived == False
    ).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['ID', 'Название', 'Группа', 'Подгруппа', 'Тип', 'Корпус', 'Производитель', 'Количество', 'Цена', 'Номинал', 'Единица'])
    for c in components:
        writer.writerow([
            c.id, c.name,
            c.comp_type.subgroup.group.name,
            c.comp_type.subgroup.name,
            c.comp_type.name,
            c.housing.housing_name if c.housing else '',
            c.manufacturer, c.quantity, c.price, c.nominal_value, c.unit,
        ])

    output.seek(0)
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv',
        as_attachment=True,
        download_name='low_stock_report.csv',
    )

import json

from flask import Blueprint, jsonify
from flask_login import current_user

from app.models import Subgroup, ComponentType

api_bp = Blueprint('api', __name__)


@api_bp.route('/get_subgroups/<int:group_id>')
def get_subgroups(group_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_subgroups)):
        return jsonify([])
    subgroups = Subgroup.query.filter_by(group_id=group_id).all()
    return jsonify([{'id': s.id, 'name': s.name} for s in subgroups])


@api_bp.route('/get_types/<int:subgroup_id>')
def get_types(subgroup_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_types)):
        return jsonify([])
    types = ComponentType.query.filter_by(subgroup_id=subgroup_id).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in types])


@api_bp.route('/get_units/<int:subgroup_id>')
def get_units(subgroup_id):
    if not (current_user.is_authenticated and (current_user.role == 'super_admin' or current_user.can_view_subgroups)):
        return jsonify([])
    subgroup = Subgroup.query.get(subgroup_id)
    if subgroup:
        units = json.loads(subgroup.units_schema)
        return jsonify([{'unit': u} for u in units])
    return jsonify([])

from flask import Flask
from config import Config
from app.extensions import db, login_manager
from app.cli import init_db_command


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.blueprints.auth import auth_bp
    from app.blueprints.users import users_bp
    from app.blueprints.groups import groups_bp
    from app.blueprints.catalog import catalog_bp
    from app.blueprints.components import components_bp
    from app.blueprints.orders import orders_bp
    from app.blueprints.api import api_bp
    from app.blueprints.main import main_bp
    from app.blueprints.tools import tools_bp
    from app.blueprints.bom import bom_bp
    from app.blueprints.library import library_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(users_bp)
    app.register_blueprint(groups_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(components_bp)
    app.register_blueprint(orders_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(tools_bp)
    app.register_blueprint(bom_bp)
    app.register_blueprint(library_bp)

    app.cli.add_command(init_db_command)

    @app.template_filter('fnum')
    def format_num(value):
        """Format float without scientific notation, stripping trailing zeros."""
        if value is None:
            return ''
        try:
            v = float(value)
        except (TypeError, ValueError):
            return str(value)
        if v == int(v) and abs(v) < 1e15:
            return str(int(v))
        return f'{v:.10f}'.rstrip('0').rstrip('.')

    return app

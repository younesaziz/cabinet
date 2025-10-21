from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
import os

# Extensions
 db = SQLAlchemy()
 migrate = Migrate()
 login_manager = LoginManager()


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=True)

    # Config
    env = os.environ.get("FLASK_ENV", "development")
    app.config.from_object("config.DevConfig" if env != "production" else "config.ProdConfig")

    # Ensure instance folder
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"

    # Import models for migrations
    from cabinet.models import User, Cabinet, Societe, DocTemplate, Cession  # noqa: F401

    # Register blueprints
    from cabinet.auth.routes import auth_bp
    from cabinet.dashboard.routes import dashboard_bp
    from cabinet.cabinets.routes import cabinets_bp
    from cabinet.societes.routes import societes_bp
    from cabinet.doc_templates.routes import templates_bp
    from cabinet.cessions.routes import cessions_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(cabinets_bp, url_prefix="/cabinets")
    app.register_blueprint(societes_bp, url_prefix="/societes")
    app.register_blueprint(templates_bp, url_prefix="/templates")
    app.register_blueprint(cessions_bp, url_prefix="/cessions")

    @app.route("/healthz")
    def healthz():
        return {"status": "ok"}

    return app

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
import os

from config import Config

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_class: type = Config) -> Flask:
    app = Flask(__name__, static_folder="static", template_folder="templates")
    app.config.from_object(config_class)

    # Ensure required directories exist
    os.makedirs(app.config["EXPORT_DIR"], exist_ok=True)
    os.makedirs(app.config["DATA_DIR"], exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    from . import models  # noqa: F401
    from .routes import bp as accounting_bp
    app.register_blueprint(accounting_bp)

    @app.cli.command("init-defaults")
    def init_defaults() -> None:
        """Initialize default journals and VAT rates if missing."""
        from .models import Journal, VatRate
        with app.app_context():
            created = 0
            defaults = [
                {"code": "ACH", "name": "Journal des achats", "type": "purchases", "prefix": "ACH-"},
                {"code": "VTE", "name": "Journal des ventes", "type": "sales", "prefix": "VTE-"},
                {"code": "TRS", "name": "Journal de trésorerie", "type": "cash", "prefix": "TRS-"},
                {"code": "OD",  "name": "Journal des opérations diverses", "type": "general", "prefix": "OD-"},
            ]
            for j in defaults:
                if not Journal.query.filter_by(code=j["code"]).first():
                    journal = Journal(**j)
                    db.session.add(journal)
                    created += 1
            # VAT rates
            if not VatRate.query.filter_by(code="TVA20").first():
                db.session.add(VatRate(code="TVA20", label="TVA 20%", rate=0.20))
                created += 1
            if not VatRate.query.filter_by(code="EXO").first():
                db.session.add(VatRate(code="EXO", label="Exonéré", rate=0.0))
                created += 1
            db.session.commit()
            print(f"Initialized {created} defaults.")

    return app

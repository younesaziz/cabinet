import os
from datetime import timedelta

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-change-me")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        f"sqlite:///{os.path.join(BASE_DIR, 'data', 'app.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    EXPORT_DIR = os.path.join(BASE_DIR, 'exports')
    DATA_DIR = os.path.join(BASE_DIR, 'data')

    # PDF/Excel defaults
    COMPANY_NAME = os.environ.get("COMPANY_NAME", "Cabinet Comptable")
    COMPANY_LOGO_PATH = os.environ.get("COMPANY_LOGO_PATH", os.path.join(BASE_DIR, 'app', 'static', 'logo.png'))

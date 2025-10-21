from app import db
from cabinet.models import User


def ensure_database_seeded() -> None:
    db.create_all()
    if not User.query.first():
        admin = User(email="admin@example.com", role="admin")
        admin.set_password("admin123")
        db.session.add(admin)
        db.session.commit()

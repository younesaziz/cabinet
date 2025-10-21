from datetime import datetime, date
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from sqlalchemy import func

from app import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="admin", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def set_password(self, password: str) -> None:
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        return check_password_hash(self.password_hash, password)


class Cabinet(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, unique=True)

    societes = relationship("Societe", back_populates="cabinet", cascade="all, delete-orphan")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Cabinet {self.id} {self.name}>"


class Societe(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False, index=True)
    type_juridique = db.Column(db.String(50), nullable=True)
    capital = db.Column(db.Float, nullable=True)
    gerant = db.Column(db.String(255), nullable=True)
    rc = db.Column(db.String(255), nullable=True)

    cabinet_id = db.Column(db.Integer, db.ForeignKey("cabinet.id"), nullable=True)
    cabinet = relationship("Cabinet", back_populates="societes")

    associates = relationship("Associate", back_populates="societe", cascade="all, delete-orphan")
    cessions = relationship("Cession", back_populates="societe", cascade="all, delete-orphan")

    def total_parts(self) -> int:
        return sum(a.parts_count for a in self.associates)

    def distribution(self):
        total = self.total_parts() or 1
        return [
            {
                "name": a.name,
                "address": a.address,
                "parts_count": a.parts_count,
                "percent": (a.parts_count / total) * 100.0,
            }
            for a in self.associates
        ]


class Associate(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    societe_id = db.Column(db.Integer, db.ForeignKey("societe.id"), nullable=False)
    name = db.Column(db.String(255), nullable=False)
    address = db.Column(db.String(255), nullable=True)
    parts_count = db.Column(db.Integer, nullable=False, default=0)

    societe = relationship("Societe", back_populates="associates")


class DocTemplate(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(50), nullable=False)  # statuts / pv
    content = db.Column(db.Text, nullable=False)


class Cession(db.Model, TimestampMixin):
    id = db.Column(db.Integer, primary_key=True)
    societe_id = db.Column(db.Integer, db.ForeignKey("societe.id"), nullable=False)
    date = db.Column(db.Date, default=date.today, nullable=False)
    cedant = db.Column(db.String(255), nullable=False)
    cedant_address = db.Column(db.String(255), nullable=True)
    cessionnaire = db.Column(db.String(255), nullable=False)
    cessionnaire_address = db.Column(db.String(255), nullable=True)
    parts_count = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=True)
    payment_mode = db.Column(db.String(100), nullable=True)
    conditions = db.Column(db.Text, nullable=True)

    societe = relationship("Societe", back_populates="cessions")

    @staticmethod
    def apply_to_distribution(societe: "Societe", cedant: str, cessionnaire: str, parts: int) -> None:
        """Apply a cession to a societe's associates distribution in-memory.
        Creates associates if needed, ensures no negative parts.
        """
        if parts <= 0:
            return
        cedant_assoc = next((a for a in societe.associates if a.name == cedant), None)
        if cedant_assoc is None:
            cedant_assoc = Associate(name=cedant, parts_count=0)
            societe.associates.append(cedant_assoc)
        cessionnaire_assoc = next((a for a in societe.associates if a.name == cessionnaire), None)
        if cessionnaire_assoc is None:
            cessionnaire_assoc = Associate(name=cessionnaire, parts_count=0)
            societe.associates.append(cessionnaire_assoc)
        cedant_assoc.parts_count = max(0, (cedant_assoc.parts_count or 0) - parts)
        cessionnaire_assoc.parts_count = (cessionnaire_assoc.parts_count or 0) + parts

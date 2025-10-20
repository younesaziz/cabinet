from __future__ import annotations
from datetime import date, datetime
from typing import Optional

from . import db


class TimestampMixin:
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class Account(db.Model, TimestampMixin):
    __tablename__ = "accounts"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    name = db.Column(db.String(255), nullable=False)
    class_code = db.Column(db.String(1), nullable=False)  # '1'..'8'
    type = db.Column(db.String(20), nullable=False)  # asset, liability, equity, income, expense

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Account {self.code} - {self.name}>"


class Journal(db.Model, TimestampMixin):
    __tablename__ = "journals"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(10), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    type = db.Column(db.String(20), nullable=False)  # purchases, sales, cash, general

    prefix = db.Column(db.String(20), nullable=False, default="J-")
    next_number = db.Column(db.Integer, nullable=False, default=1)

    def next_sequence(self, when: Optional[date] = None) -> str:
        when = when or date.today()
        seq = f"{self.prefix}{when.year}-{self.next_number:04d}"
        self.next_number += 1
        return seq


class Entry(db.Model, TimestampMixin):
    __tablename__ = "entries"

    id = db.Column(db.Integer, primary_key=True)
    journal_id = db.Column(db.Integer, db.ForeignKey("journals.id"), nullable=False, index=True)
    journal = db.relationship(Journal, backref=db.backref("entries", lazy=True))

    entry_date = db.Column(db.Date, nullable=False, index=True)
    reference = db.Column(db.String(50), nullable=False, index=True)  # auto-numbered
    description = db.Column(db.String(255), nullable=True)
    document_ref = db.Column(db.String(100), nullable=True)  # Référence pièce justificative

    validated = db.Column(db.Boolean, default=False, index=True)

    def total_debit(self) -> float:
        return float(sum(line.debit or 0 for line in self.lines))

    def total_credit(self) -> float:
        return float(sum(line.credit or 0 for line in self.lines))

    def is_balanced(self) -> bool:
        return round(self.total_debit() - self.total_credit(), 2) == 0.0


class EntryLine(db.Model, TimestampMixin):
    __tablename__ = "entry_lines"

    id = db.Column(db.Integer, primary_key=True)
    entry_id = db.Column(db.Integer, db.ForeignKey("entries.id"), nullable=False, index=True)
    entry = db.relationship(Entry, backref=db.backref("lines", lazy=True, cascade="all, delete-orphan"))

    account_id = db.Column(db.Integer, db.ForeignKey("accounts.id"), nullable=False, index=True)
    account = db.relationship(Account)

    label = db.Column(db.String(255), nullable=True)
    debit = db.Column(db.Numeric(14, 2), nullable=True, default=0)
    credit = db.Column(db.Numeric(14, 2), nullable=True, default=0)


class VatRate(db.Model, TimestampMixin):
    __tablename__ = "vat_rates"

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False)
    label = db.Column(db.String(100), nullable=False)
    rate = db.Column(db.Numeric(5, 4), nullable=False)  # e.g., 0.2000


class Customer(db.Model, TimestampMixin):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    vat_id = db.Column(db.String(50), nullable=True)  # ICE/IF
    address = db.Column(db.String(255), nullable=True)


class Invoice(db.Model, TimestampMixin):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    number = db.Column(db.String(50), unique=True, nullable=False)
    invoice_date = db.Column(db.Date, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)
    customer = db.relationship(Customer)

    is_quote = db.Column(db.Boolean, default=False)
    prefix = db.Column(db.String(10), nullable=False, default="INV-")

    @property
    def total_ht(self) -> float:
        return float(sum(item.total_ht for item in self.items))

    @property
    def total_tva(self) -> float:
        return float(sum(item.tva_amount for item in self.items))

    @property
    def total_ttc(self) -> float:
        return self.total_ht + self.total_tva


class InvoiceItem(db.Model, TimestampMixin):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False, index=True)
    invoice = db.relationship(Invoice, backref=db.backref("items", lazy=True, cascade="all, delete-orphan"))

    description = db.Column(db.String(255), nullable=False)
    quantity = db.Column(db.Numeric(12, 3), nullable=False, default=1)
    unit_price = db.Column(db.Numeric(14, 2), nullable=False, default=0)

    vat_rate_id = db.Column(db.Integer, db.ForeignKey("vat_rates.id"), nullable=True)
    vat_rate = db.relationship(VatRate)

    @property
    def total_ht(self) -> float:
        return float((self.quantity or 0) * (self.unit_price or 0))

    @property
    def tva_amount(self) -> float:
        rate = float(self.vat_rate.rate) if self.vat_rate else 0.0
        return round(self.total_ht * rate, 2)


class Numbering(db.Model, TimestampMixin):
    __tablename__ = "numbering"

    id = db.Column(db.Integer, primary_key=True)
    scope = db.Column(db.String(20), unique=True, nullable=False)  # e.g., 'invoice'
    prefix = db.Column(db.String(20), nullable=False)
    next_number = db.Column(db.Integer, nullable=False, default=1)

    def next_sequence(self, when: Optional[date] = None) -> str:
        when = when or date.today()
        seq = f"{self.prefix}{when.year}-{self.next_number:04d}"
        self.next_number += 1
        return seq

from __future__ import annotations

import io
import json
from datetime import date, datetime
from decimal import Decimal
from typing import Dict, List, Optional, Tuple

import pandas as pd
from flask import (
    Blueprint,
    Response,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from xhtml2pdf import pisa

from . import db
from .models import (
    Account,
    Entry,
    EntryLine,
    Invoice,
    InvoiceItem,
    Journal,
    Numbering,
    VatRate,
)


bp = Blueprint("accounting", __name__)


# ---------- Helpers ----------

def _parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def _render_pdf_from_template(template: str, context: dict, filename: str) -> Response:
    html = render_template(template, **context)
    pdf_stream = io.BytesIO()
    pisa.CreatePDF(io.StringIO(html), dest=pdf_stream)  # type: ignore[arg-type]
    pdf_stream.seek(0)
    return send_file(
        pdf_stream,
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )


def _df_to_excel_download(df: pd.DataFrame, filename: str) -> Response:
    out = io.BytesIO()
    with pd.ExcelWriter(out, engine="xlsxwriter") as writer:
        df.to_excel(writer, index=False)
    out.seek(0)
    return send_file(
        out,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )


# ---------- Home ----------


@bp.route("/")
def home() -> Response | str:
    return redirect(url_for("accounting.journals"))


# ---------- Accounts (PCM) ----------


@bp.route("/accounts")
def accounts() -> str:
    q = Account.query.order_by(Account.code).all()
    return render_template("accounts/list.html", accounts=q)


@bp.route("/accounts/seed-pcm")
def seed_pcm() -> Response:
    """Seed Moroccan PCM from bundled JSON if accounts table is empty."""
    if Account.query.count() > 0:
        flash("Des comptes existent déjà.", "info")
        return redirect(url_for("accounting.accounts"))

    data_path = current_app.root_path + "/data/pcm_ma.json"
    try:
        with open(data_path, "r", encoding="utf-8") as f:
            items = json.load(f)
    except FileNotFoundError:
        flash("Fichier PCM introuvable.", "danger")
        return redirect(url_for("accounting.accounts"))

    created = 0
    for row in items:
        acc = Account(
            code=row["code"],
            name=row["name"],
            class_code=row["class"],
            type=row["type"],
        )
        db.session.add(acc)
        created += 1
    db.session.commit()
    flash(f"{created} comptes PCM importés.", "success")
    return redirect(url_for("accounting.accounts"))


@bp.route("/accounts/import", methods=["POST"])
def import_accounts() -> Response:
    file = request.files.get("file")
    if not file:
        flash("Aucun fichier fourni.", "warning")
        return redirect(url_for("accounting.accounts"))
    df = pd.read_csv(file)
    required = {"code", "name", "class", "type"}
    if not required.issubset(df.columns):
        flash("Colonnes requises: code,name,class,type", "danger")
        return redirect(url_for("accounting.accounts"))
    created = 0
    for _, r in df.iterrows():
        if not Account.query.filter_by(code=str(r["code"]).strip()).first():
            acc = Account(
                code=str(r["code"]).strip(),
                name=str(r["name"]).strip(),
                class_code=str(r["class"]).strip(),
                type=str(r["type"]).strip(),
            )
            db.session.add(acc)
            created += 1
    db.session.commit()
    flash(f"{created} comptes importés.", "success")
    return redirect(url_for("accounting.accounts"))


# ---------- Journals and Entries ----------


@bp.route("/journals")
def journals() -> str:
    j = Journal.query.order_by(Journal.code).all()
    return render_template("journals/list.html", journals=j)


@bp.route("/journals/<int:journal_id>/entries/new")
def entry_new(journal_id: int) -> str:
    journal = Journal.query.get_or_404(journal_id)
    accounts = Account.query.order_by(Account.code).all()
    today = date.today().strftime("%Y-%m-%d")
    return render_template(
        "entries/new.html",
        journal=journal,
        accounts=accounts,
        today=today,
    )


@bp.route("/journals/<int:journal_id>/entries", methods=["POST"])
def entry_create(journal_id: int) -> Response:
    journal = Journal.query.get_or_404(journal_id)
    entry_date = _parse_date(request.form.get("entry_date", date.today().isoformat()))
    description = request.form.get("description") or None
    document_ref = request.form.get("document_ref") or None

    reference = journal.next_sequence(entry_date)
    entry = Entry(
        journal=journal,
        entry_date=entry_date,
        reference=reference,
        description=description,
        document_ref=document_ref,
        validated=False,
    )
    db.session.add(entry)

    # Lines
    line_count = int(request.form.get("line_count", 5))
    for i in range(line_count):
        acc_id = request.form.get(f"account_{i}")
        label = request.form.get(f"label_{i}") or None
        debit_str = request.form.get(f"debit_{i}") or ""
        credit_str = request.form.get(f"credit_{i}") or ""
        if not acc_id:
            continue
        debit = Decimal(debit_str.replace(",", ".")) if debit_str else Decimal("0")
        credit = Decimal(credit_str.replace(",", ".")) if credit_str else Decimal("0")
        if debit == 0 and credit == 0:
            continue
        line = EntryLine(entry=entry, account_id=int(acc_id), label=label, debit=debit, credit=credit)
        db.session.add(line)

    # Persist
    if not entry.is_balanced():
        db.session.rollback()
        flash("Écriture non équilibrée (Débit ≠ Crédit).", "danger")
        return redirect(url_for("accounting.entry_new", journal_id=journal.id))

    db.session.commit()
    flash(f"Écriture {entry.reference} créée.", "success")
    return redirect(url_for("accounting.entry_view", entry_id=entry.id))


@bp.route("/entries/<int:entry_id>")
def entry_view(entry_id: int) -> str:
    entry = Entry.query.get_or_404(entry_id)
    return render_template("entries/view.html", entry=entry)


@bp.route("/entries/<int:entry_id>/validate", methods=["POST"])
def entry_validate(entry_id: int) -> Response:
    entry = Entry.query.get_or_404(entry_id)
    entry.validated = True
    db.session.commit()
    flash("Écriture validée.", "success")
    return redirect(url_for("accounting.entry_view", entry_id=entry.id))


@bp.route("/journals/<int:journal_id>/export.xlsx")
def journal_export_xlsx(journal_id: int) -> Response:
    journal = Journal.query.get_or_404(journal_id)
    rows = []
    for e in journal.entries:
        for l in e.lines:
            rows.append(
                {
                    "Référence": e.reference,
                    "Date": e.entry_date.isoformat(),
                    "Compte": l.account.code,
                    "Intitulé": l.account.name,
                    "Libellé": l.label or "",
                    "Débit": float(l.debit or 0),
                    "Crédit": float(l.credit or 0),
                }
            )
    df = pd.DataFrame(rows)
    filename = f"journal_{journal.code}_{date.today().isoformat()}.xlsx"
    return _df_to_excel_download(df, filename)


@bp.route("/journals/<int:journal_id>/export.pdf")
def journal_export_pdf(journal_id: int) -> Response:
    journal = Journal.query.get_or_404(journal_id)
    lines: List[Dict] = []
    for e in journal.entries:
        for l in e.lines:
            lines.append(
                {
                    "reference": e.reference,
                    "date": e.entry_date,
                    "account_code": l.account.code,
                    "account_name": l.account.name,
                    "label": l.label or "",
                    "debit": float(l.debit or 0),
                    "credit": float(l.credit or 0),
                }
            )
    return _render_pdf_from_template(
        "journals/export_pdf.html",
        {
            "company": current_app.config.get("COMPANY_NAME"),
            "journal": journal,
            "lines": lines,
            "today": date.today(),
        },
        filename=f"journal_{journal.code}.pdf",
    )


# ---------- Reports ----------


def _date_range_from_request() -> Tuple[Optional[date], Optional[date]]:
    start = request.args.get("start")
    end = request.args.get("end")
    start_d = _parse_date(start) if start else None
    end_d = _parse_date(end) if end else None
    return start_d, end_d


@bp.route("/reports/trial-balance")
def report_trial_balance() -> str:
    start_d, end_d = _date_range_from_request()
    q = (
        db.session.query(
            Account.code,
            Account.name,
            db.func.coalesce(db.func.sum(EntryLine.debit), 0).label("debit"),
            db.func.coalesce(db.func.sum(EntryLine.credit), 0).label("credit"),
        )
        .join(EntryLine.account)
        .join(EntryLine.entry)
        .filter(Entry.validated.is_(True))
    )
    if start_d:
        q = q.filter(Entry.entry_date >= start_d)
    if end_d:
        q = q.filter(Entry.entry_date <= end_d)
    q = q.group_by(Account.code, Account.name).order_by(Account.code)
    rows = [
        {
            "code": code,
            "name": name,
            "debit": float(debit),
            "credit": float(credit),
            "balance": round(float(debit) - float(credit), 2),
        }
        for code, name, debit, credit in q.all()
    ]
    totals = {
        "debit": round(sum(r["debit"] for r in rows), 2),
        "credit": round(sum(r["credit"] for r in rows), 2),
    }
    return render_template("reports/trial_balance.html", rows=rows, totals=totals, start=start_d, end=end_d)


@bp.route("/reports/trial-balance.xlsx")
def report_trial_balance_xlsx() -> Response:
    with current_app.test_request_context():
        # reuse logic by calling function directly would require refactor; rebuild quickly
        start_d, end_d = _date_range_from_request()
    q = (
        db.session.query(
            Account.code,
            Account.name,
            db.func.coalesce(db.func.sum(EntryLine.debit), 0).label("debit"),
            db.func.coalesce(db.func.sum(EntryLine.credit), 0).label("credit"),
        )
        .join(EntryLine.account)
        .join(EntryLine.entry)
        .filter(Entry.validated.is_(True))
    )
    if start_d:
        q = q.filter(Entry.entry_date >= start_d)
    if end_d:
        q = q.filter(Entry.entry_date <= end_d)
    q = q.group_by(Account.code, Account.name).order_by(Account.code)
    df = pd.DataFrame(
        [
            {
                "Compte": code,
                "Intitulé": name,
                "Débit": float(debit),
                "Crédit": float(credit),
                "Solde": round(float(debit) - float(credit), 2),
            }
            for code, name, debit, credit in q.all()
        ]
    )
    return _df_to_excel_download(df, "balance_generale.xlsx")


@bp.route("/reports/ledger")
def report_ledger() -> str:
    start_d, end_d = _date_range_from_request()
    accounts = Account.query.order_by(Account.code).all()
    ledger: Dict[str, List[dict]] = {}
    for acc in accounts:
        q = (
            EntryLine.query.join(EntryLine.entry)
            .filter(Entry.validated.is_(True), EntryLine.account_id == acc.id)
        )
        if start_d:
            q = q.filter(Entry.entry_date >= start_d)
        if end_d:
            q = q.filter(Entry.entry_date <= end_d)
        q = q.order_by(Entry.entry_date, Entry.reference)
        ledger[acc.code] = [
            {
                "date": l.entry.entry_date,
                "reference": l.entry.reference,
                "label": l.label or "",
                "debit": float(l.debit or 0),
                "credit": float(l.credit or 0),
            }
            for l in q.all()
        ]
    return render_template("reports/ledger.html", ledger=ledger, accounts=accounts, start=start_d, end=end_d)


@bp.route("/reports/balance-sheet")
def report_balance_sheet() -> str:
    # Simple mapping by class code
    start_d, end_d = _date_range_from_request()
    def sum_for_classes(classes: List[str]) -> float:
        q = (
            db.session.query(
                db.func.coalesce(db.func.sum(EntryLine.debit), 0).label("debit"),
                db.func.coalesce(db.func.sum(EntryLine.credit), 0).label("credit"),
            )
            .join(EntryLine.account)
            .join(EntryLine.entry)
            .filter(Entry.validated.is_(True), Account.class_code.in_(classes))
        )
        if start_d:
            q = q.filter(Entry.entry_date >= start_d)
        if end_d:
            q = q.filter(Entry.entry_date <= end_d)
        debit, credit = q.first() or (0, 0)
        return round(float(debit) - float(credit), 2)

    assets = sum_for_classes(["1", "2", "3", "5"])  # fixed assets, inventory, accounts receivable, cash
    liabilities_equity = -sum_for_classes(["4"])  # suppliers, equity debts (credit balances)

    return render_template(
        "reports/balance_sheet.html",
        assets=assets,
        liabilities_equity=liabilities_equity,
        start=start_d,
        end=end_d,
    )


@bp.route("/reports/income-statement")
def report_income_statement() -> str:
    start_d, end_d = _date_range_from_request()
    def sum_for_classes(classes: List[str]) -> float:
        q = (
            db.session.query(
                db.func.coalesce(db.func.sum(EntryLine.debit), 0).label("debit"),
                db.func.coalesce(db.func.sum(EntryLine.credit), 0).label("credit"),
            )
            .join(EntryLine.account)
            .join(EntryLine.entry)
            .filter(Entry.validated.is_(True), Account.class_code.in_(classes))
        )
        if start_d:
            q = q.filter(Entry.entry_date >= start_d)
        if end_d:
            q = q.filter(Entry.entry_date <= end_d)
        debit, credit = q.first() or (0, 0)
        return round(float(credit) - float(debit), 2)  # income positive

    revenue = sum_for_classes(["7"])  # sales
    expenses = sum_for_classes(["6"])  # expenses
    result = revenue - expenses

    return render_template(
        "reports/income_statement.html",
        revenue=revenue,
        expenses=expenses,
        result=result,
        start=start_d,
        end=end_d,
    )


# ---------- VAT ----------


def _period_bounds(period: str, frequency: str) -> Tuple[date, date]:
    # period: 'YYYY-MM', frequency: 'monthly' or 'quarterly'
    year, month = [int(x) for x in period.split("-")]
    start = date(year, month, 1)
    if frequency == "quarterly":
        q_month = ((month - 1) // 3) * 3 + 1
        start = date(year, q_month, 1)
        end_month = q_month + 2
    else:
        end_month = month
    # naive end of month
    if end_month in (1, 3, 5, 7, 8, 10, 12):
        end_day = 31
    elif end_month == 2:
        end_day = 29 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 28
    else:
        end_day = 30
    end = date(year, end_month, end_day)
    return start, end


@bp.route("/vat/declaration")
def vat_declaration() -> str:
    period = request.args.get("period", date.today().strftime("%Y-%m"))
    frequency = request.args.get("frequency", "monthly")
    start, end = _period_bounds(period, frequency)

    # Compute from invoices (as a baseline). In a full system we would also reconcile with entries
    items = (
        InvoiceItem.query.join(InvoiceItem.invoice)
        .filter(Invoice.invoice_date >= start, Invoice.invoice_date <= end)
        .all()
    )
    total_ht = sum(i.total_ht for i in items)
    total_tva = sum(i.tva_amount for i in items)

    return render_template(
        "vat/declaration.html",
        period=period,
        frequency=frequency,
        start=start,
        end=end,
        total_ht=round(float(total_ht), 2),
        total_tva=round(float(total_tva), 2),
    )


@bp.route("/vat/declaration.xlsx")
def vat_declaration_xlsx() -> Response:
    period = request.args.get("period", date.today().strftime("%Y-%m"))
    frequency = request.args.get("frequency", "monthly")
    start, end = _period_bounds(period, frequency)

    items = (
        InvoiceItem.query.join(InvoiceItem.invoice)
        .filter(Invoice.invoice_date >= start, Invoice.invoice_date <= end)
        .all()
    )
    df = pd.DataFrame(
        [
            {
                "Date": i.invoice.invoice_date.isoformat(),
                "Facture": i.invoice.number,
                "Description": i.description,
                "Qté": float(i.quantity or 0),
                "PU": float(i.unit_price or 0),
                "HT": i.total_ht,
                "TVA": i.tva_amount,
            }
            for i in items
        ]
    )
    return _df_to_excel_download(df, f"declaration_tva_{period}.xlsx")


@bp.route("/vat/declaration.pdf")
def vat_declaration_pdf() -> Response:
    period = request.args.get("period", date.today().strftime("%Y-%m"))
    frequency = request.args.get("frequency", "monthly")
    start, end = _period_bounds(period, frequency)

    items = (
        InvoiceItem.query.join(InvoiceItem.invoice)
        .filter(Invoice.invoice_date >= start, Invoice.invoice_date <= end)
        .all()
    )
    return _render_pdf_from_template(
        "vat/declaration_pdf.html",
        {"period": period, "frequency": frequency, "items": items, "start": start, "end": end},
        filename=f"declaration_tva_{period}.pdf",
    )


# ---------- Invoicing ----------


@bp.route("/invoices")
def invoices() -> str:
    inv = Invoice.query.order_by(Invoice.invoice_date.desc(), Invoice.number.desc()).all()
    return render_template("invoices/list.html", invoices=inv)


@bp.route("/invoices/new")
def invoice_new() -> str:
    customers = [(c.id, c.name) for c in db.session.query(db.text("1 as id, 'Client Divers' as name")).all()]  # placeholder
    vat_rates = VatRate.query.order_by(VatRate.rate.desc()).all()
    today = date.today().strftime("%Y-%m-%d")
    return render_template("invoices/new.html", customers=customers, vat_rates=vat_rates, today=today)


def _next_number(scope: str, prefix: str) -> str:
    cfg = Numbering.query.filter_by(scope=scope).first()
    if not cfg:
        cfg = Numbering(scope=scope, prefix=prefix, next_number=1)
        db.session.add(cfg)
        db.session.commit()
    number = cfg.next_sequence(date.today())
    db.session.commit()
    return number


@bp.route("/invoices", methods=["POST"])
def invoice_create() -> Response:
    is_quote = request.form.get("is_quote") == "1"
    invoice_date = _parse_date(request.form.get("invoice_date", date.today().isoformat()))
    prefix = "DEV-" if is_quote else "INV-"
    number = _next_number("quote" if is_quote else "invoice", prefix)

    inv = Invoice(number=number, invoice_date=invoice_date, customer_id=1, is_quote=is_quote, prefix=prefix)
    db.session.add(inv)

    item_count = int(request.form.get("item_count", 3))
    for i in range(item_count):
        desc = request.form.get(f"desc_{i}") or None
        qty = request.form.get(f"qty_{i}") or "0"
        price = request.form.get(f"price_{i}") or "0"
        vat_rate_id = request.form.get(f"vat_{i}") or None
        if not desc:
            continue
        item = InvoiceItem(
            invoice=inv,
            description=desc,
            quantity=Decimal(qty.replace(",", ".")),
            unit_price=Decimal(price.replace(",", ".")),
            vat_rate_id=int(vat_rate_id) if vat_rate_id else None,
        )
        db.session.add(item)

    db.session.commit()
    flash(f"Document créé: {inv.number}", "success")
    return redirect(url_for("accounting.invoices"))


@bp.route("/invoices/<int:invoice_id>/pdf")
def invoice_pdf(invoice_id: int) -> Response:
    inv = Invoice.query.get_or_404(invoice_id)
    return _render_pdf_from_template(
        "invoices/pdf.html",
        {"invoice": inv, "company": current_app.config.get("COMPANY_NAME")},
        filename=f"{inv.number}.pdf",
    )

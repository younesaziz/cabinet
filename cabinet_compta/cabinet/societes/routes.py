from io import BytesIO

from flask import render_template, request, redirect, url_for, send_file
from flask_login import login_required
import pandas as pd

from . import societes_bp
from app import db
from cabinet.models import Societe, Cabinet


@societes_bp.route("/")
@login_required
def index():
    items = Societe.query.order_by(Societe.created_at.desc()).all()
    cabinets = Cabinet.query.order_by(Cabinet.name.asc()).all()
    return render_template("societes/index.html", societes=items, cabinets=cabinets)


@societes_bp.route("/create", methods=["POST"]) 
@login_required
def create():
    name = request.form.get("name")
    type_juridique = request.form.get("type_juridique")
    capital = request.form.get("capital")
    gerant = request.form.get("gerant")
    rc = request.form.get("rc")
    cabinet_id = request.form.get("cabinet_id")
    if name:
        item = Societe(
            name=name,
            type_juridique=type_juridique or None,
            capital=float(capital) if capital else None,
            gerant=gerant or None,
            rc=rc or None,
            cabinet_id=int(cabinet_id) if cabinet_id else None,
        )
        db.session.add(item)
        db.session.commit()
    return redirect(url_for("societes.index"))


@societes_bp.route("/export/xlsx")
@login_required
def export_xlsx():
    rows = [
        {
            "ID": s.id,
            "Nom": s.name,
            "Type": s.type_juridique,
            "Capital": s.capital,
            "Gérant": s.gerant,
            "RC": s.rc,
            "Cabinet": s.cabinet.name if s.cabinet else None,
        }
        for s in Societe.query.order_by(Societe.name.asc()).all()
    ]
    df = pd.DataFrame(rows)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Sociétés")
    output.seek(0)
    return send_file(
        output,
        as_attachment=True,
        download_name="societes.xlsx",
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

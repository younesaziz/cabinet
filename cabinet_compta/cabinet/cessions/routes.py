from flask import render_template, request, redirect, url_for
from flask_login import login_required

from app import db
from cabinet.models import Cession, Societe

from . import cessions_bp


@cessions_bp.route("/")
@login_required
def index():
    items = Cession.query.order_by(Cession.created_at.desc()).all()
    societes = Societe.query.order_by(Societe.name.asc()).all()
    return render_template("cessions/index.html", cessions=items, societes=societes)


@cessions_bp.route("/create", methods=["POST"]) 
@login_required
def create():
    societe_id = request.form.get("societe_id", type=int)
    cedant = request.form.get("cedant")
    cedant_address = request.form.get("cedant_address")
    cessionnaire = request.form.get("cessionnaire")
    cessionnaire_address = request.form.get("cessionnaire_address")
    parts_count = request.form.get("parts_count", type=int)
    price = request.form.get("price", type=float)
    payment_mode = request.form.get("payment_mode")
    conditions = request.form.get("conditions")

    if not societe_id or not cedant or not cessionnaire or not parts_count:
        return redirect(url_for("cessions.index"))

    societe = Societe.query.get_or_404(societe_id)
    cession = Cession(
        societe_id=societe_id,
        cedant=cedant,
        cedant_address=cedant_address,
        cessionnaire=cessionnaire,
        cessionnaire_address=cessionnaire_address,
        parts_count=parts_count,
        price=price,
        payment_mode=payment_mode,
        conditions=conditions,
    )
    db.session.add(cession)

    # Update associates distribution
    Cession.apply_to_distribution(societe, cedant, cessionnaire, parts_count)

    db.session.commit()
    return redirect(url_for("cessions.index"))

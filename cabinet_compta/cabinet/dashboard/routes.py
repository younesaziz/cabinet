from flask import render_template, jsonify
from flask_login import login_required
from sqlalchemy import func

from . import dashboard_bp
from cabinet.models import Societe, Cession


@dashboard_bp.route("/")
@login_required
def index():
    societes_count = Societe.query.count()
    last_cessions = Cession.query.order_by(Cession.created_at.desc()).limit(10).all()
    return render_template(
        "dashboard/index.html",
        societes_count=societes_count,
        last_cessions=last_cessions,
    )


@dashboard_bp.route("/dashboard/data/companies-by-type.json")
@login_required
def companies_by_type_json():
    rows = (
        Societe.query.with_entities(Societe.type_juridique, func.count(Societe.id))
        .group_by(Societe.type_juridique)
        .all()
    )
    labels = [r[0] or "N/A" for r in rows]
    values = [r[1] for r in rows]
    return jsonify({"labels": labels, "values": values})

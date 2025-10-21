from flask import render_template, request, redirect, url_for
from flask_login import login_required

from . import cabinets_bp
from app import db
from cabinet.models import Cabinet


@cabinets_bp.route("/")
@login_required
def index():
    items = Cabinet.query.order_by(Cabinet.created_at.desc()).all()
    return render_template("cabinets/index.html", cabinets=items)


@cabinets_bp.route("/create", methods=["POST"]) 
@login_required
def create():
    name = request.form.get("name")
    if name:
        db.session.add(Cabinet(name=name))
        db.session.commit()
    return redirect(url_for("cabinets.index"))


@cabinets_bp.route("/<int:cabinet_id>/delete", methods=["POST"]) 
@login_required
def delete(cabinet_id: int):
    item = Cabinet.query.get_or_404(cabinet_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("cabinets.index"))

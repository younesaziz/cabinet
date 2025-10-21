from flask import render_template, request, redirect, url_for
from flask_login import login_required

from io import BytesIO
from app import db
from cabinet.models import DocTemplate, Societe
from cabinet.utils.pdf import render_pdf

from . import templates_bp


@templates_bp.route("/")
@login_required
def index():
    items = DocTemplate.query.order_by(DocTemplate.created_at.desc()).all()
    return render_template("doc_templates/index.html", templates_list=items)


@templates_bp.route("/create", methods=["POST"]) 
@login_required
def create():
    title = request.form.get("title")
    type_ = request.form.get("type")
    content = request.form.get("content")
    if title and type_ and content:
        db.session.add(DocTemplate(title=title, type=type_, content=content))
        db.session.commit()
    return redirect(url_for("templates.index"))


@templates_bp.route("/<int:template_id>")
@login_required
def edit(template_id: int):
    item = DocTemplate.query.get_or_404(template_id)
    return render_template("doc_templates/edit.html", item=item)


@templates_bp.route("/<int:template_id>/save", methods=["POST"]) 
@login_required
def save(template_id: int):
    item = DocTemplate.query.get_or_404(template_id)
    item.title = request.form.get("title") or item.title
    item.type = request.form.get("type") or item.type
    item.content = request.form.get("content") or item.content
    db.session.commit()
    return redirect(url_for("templates.index"))


@templates_bp.route("/<int:template_id>/delete", methods=["POST"]) 
@login_required
def delete(template_id: int):
    item = DocTemplate.query.get_or_404(template_id)
    db.session.delete(item)
    db.session.commit()
    return redirect(url_for("templates.index"))


@templates_bp.route("/<int:template_id>/pdf")
@login_required
def export_pdf(template_id: int):
    item = DocTemplate.query.get_or_404(template_id)
    company_id = request.args.get("company_id", type=int)
    societe = Societe.query.get(company_id) if company_id else None

    # Build context for placeholders
    context = {
        "NOM": societe.name if societe else "",
        "GERANT": societe.gerant if societe else "",
        "DATE": request.args.get("date") or "",
        "TYPE_JURIDIQUE": societe.type_juridique if societe else "",
        "RC": societe.rc if societe else "",
    }

    html = render_template(
        "doc_templates/pdf/base.html",
        raw_content=item.content,
        context=context,
        title=item.title,
    )
    pdf_bytes = render_pdf(html)
    return (
        pdf_bytes,
        200,
        {
            "Content-Type": "application/pdf",
            "Content-Disposition": f"attachment; filename={item.type}-{item.id}.pdf",
        },
    )

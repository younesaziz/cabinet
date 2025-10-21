from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required

from . import auth_bp
from .forms import LoginForm
from app import db, login_manager
from cabinet.models import User


@login_manager.user_loader
def load_user(user_id: str):
    try:
        return User.query.get(int(user_id))
    except Exception:
        return None


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower()).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            next_url = request.args.get("next") or url_for("dashboard.index")
            return redirect(next_url)
        flash("Identifiants invalides", "danger")
    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))

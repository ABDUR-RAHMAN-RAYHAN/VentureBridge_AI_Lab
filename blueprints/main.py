from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import User
from forms import ProfileForm, ContactForm
from utils import save_upload

bp = Blueprint("main", __name__)

_ROLE_COLORS = {
    "founder": "#1f8fe0",
    "investor": "#1eb872",
    "jobseeker": "#c9a227",
    "admin": "#7a8b99",
}
_ROLE_LABELS = {
    "founder": "Founders",
    "investor": "Investors",
    "jobseeker": "Job Seekers",
    "admin": "Admins",
}


@bp.route("/")
def index():
    stats = {"members": User.query.filter_by(is_active_account=True).count()}
    return render_template("public/index.html", stats=stats)


@bp.route("/about")
def about():
    return render_template("public/about.html")


@bp.route("/privacy")
def privacy():
    return render_template("public/privacy.html")


@bp.route("/terms")
def terms():
    return render_template("public/terms.html")


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    form = ContactForm()
    if form.validate_on_submit():
        flash("Thanks for reaching out — we'll get back to you shortly.", "success")
        return redirect(url_for("main.contact"))
    return render_template("public/contact.html", form=form)


@bp.route("/dashboard")
@login_required
def dashboard():
    ctx = {}
    if current_user.role == "admin":
        ctx["total_users"] = User.query.count()
        rows = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
        counts = dict(rows)
        ctx["role_breakdown"] = [
            {"label": _ROLE_LABELS[role], "count": counts.get(role, 0), "color": _ROLE_COLORS[role]}
            for role in ("founder", "investor", "jobseeker", "admin") if counts.get(role, 0) > 0
        ]
    return render_template("dashboard/dashboard.html", **ctx)


@bp.route("/profile")
@login_required
def profile():
    return render_template("profile/view.html", profile=current_user.profile)


@bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    profile = current_user.profile
    form = ProfileForm(obj=profile)
    if form.validate_on_submit():
        if form.photo.data:
            try:
                filename = save_upload(form.photo.data, "logos", {"png", "jpg", "jpeg"})
                profile.photo = filename
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("profile/form.html", form=form, profile=profile)
        profile.phone = form.phone.data
        profile.bio = form.bio.data
        profile.location = form.location.data
        profile.education = form.education.data
        profile.experience = form.experience.data
        profile.industry = form.industry.data
        profile.skills = form.skills.data
        profile.interests = form.interests.data
        db.session.commit()
        flash("Profile updated successfully.", "success")
        return redirect(url_for("main.profile"))
    elif request.method == "POST":
        for field_name, errors in form.errors.items():
            field_label = getattr(form, field_name).label.text
            for err in errors:
                flash(f"{field_label}: {err}", "danger")
    return render_template("profile/form.html", form=form, profile=profile)

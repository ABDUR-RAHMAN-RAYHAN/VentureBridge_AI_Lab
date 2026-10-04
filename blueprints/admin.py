from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import (User, Startup, Job, StartupDocument, IdentityVerification, AuditLog)
from decorators import roles_required
from utils import log_action

bp = Blueprint("admin", __name__, url_prefix="/admin")


@bp.before_request
@login_required
@roles_required("admin")
def _guard():
    pass


@bp.route("/users")
def users():
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    query = User.query
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(User.full_name.ilike(like), User.email.ilike(like)))
    if role:
        query = query.filter_by(role=role)
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template("admin/users.html", users=all_users, q=q, role=role)


@bp.route("/users/<int:user_id>/toggle", methods=["POST"])
def toggle_user(user_id):
    user = User.query.get_or_404(user_id)
    if user.role == "admin" and user.is_active_account:
        other_admins = User.query.filter_by(role="admin", is_active_account=True).filter(User.id != user.id).count()
        if other_admins == 0:
            flash("Cannot deactivate the only remaining admin account.", "danger")
            return redirect(url_for("admin.users"))
    user.is_active_account = not user.is_active_account
    db.session.commit()
    log_action("user_status_toggled", f"user_id={user.id} active={user.is_active_account}")
    flash(f"{user.full_name} is now {'active' if user.is_active_account else 'deactivated'}.", "success")
    return redirect(url_for("admin.users"))


@bp.route("/startups")
def startups():
    q = request.args.get("q", "").strip()
    query = Startup.query
    if q:
        query = query.filter(Startup.name.ilike(f"%{q}%"))
    all_startups = query.order_by(Startup.created_at.desc()).all()
    return render_template("admin/startups.html", startups=all_startups, q=q)


@bp.route("/startups/<int:startup_id>/toggle", methods=["POST"])
def toggle_startup(startup_id):
    startup = Startup.query.get_or_404(startup_id)
    startup.is_active = not startup.is_active
    db.session.commit()
    log_action("startup_status_toggled", f"startup_id={startup.id} active={startup.is_active}")
    flash(f"Startup '{startup.name}' is now {'active' if startup.is_active else 'deactivated'}.", "success")
    return redirect(url_for("admin.startups"))


@bp.route("/jobs")
def jobs():
    all_jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template("admin/jobs.html", jobs=all_jobs)


@bp.route("/jobs/<int:job_id>/toggle", methods=["POST"])
def toggle_job(job_id):
    job = Job.query.get_or_404(job_id)
    job.status = "closed" if job.status == "open" else "open"
    db.session.commit()
    log_action("job_status_toggled_by_admin", f"job_id={job.id} status={job.status}")
    flash(f"Job '{job.title}' is now {job.status}.", "success")
    return redirect(url_for("admin.jobs"))


@bp.route("/verification-queue")
def verification_queue():
    pending = IdentityVerification.query.filter_by(status="pending").order_by(
        IdentityVerification.submitted_at.asc()).all()
    return render_template("admin/verification_queue.html", pending=pending)


@bp.route("/verification/<int:v_id>/decide", methods=["POST"])
def decide_verification(v_id):
    v = IdentityVerification.query.get_or_404(v_id)
    decision = request.form.get("decision")
    reason = request.form.get("reason", "").strip()
    if decision not in ("approved", "rejected"):
        abort(400)
    if decision == "rejected" and not reason:
        flash("A reason is required when rejecting.", "danger")
        return redirect(url_for("admin.verification_queue"))
    v.status = decision
    v.reason = reason if decision == "rejected" else None
    v.reviewed_at = datetime.utcnow()
    v.reviewed_by = current_user.id
    db.session.commit()
    log_action("identity_verification_reviewed", f"verification_id={v.id} decision={decision}")
    flash(f"Verification {decision}.", "success")
    return redirect(url_for("admin.verification_queue"))


@bp.route("/document-queue")
def document_queue():
    pending = StartupDocument.query.filter_by(status="pending").order_by(
        StartupDocument.uploaded_at.asc()).all()
    return render_template("admin/document_queue.html", pending=pending)


@bp.route("/document/<int:doc_id>/decide", methods=["POST"])
def decide_document(doc_id):
    doc = StartupDocument.query.get_or_404(doc_id)
    decision = request.form.get("decision")
    reason = request.form.get("reason", "").strip()
    if decision not in ("approved", "rejected"):
        abort(400)
    if decision == "rejected" and not reason:
        flash("A reason is required when rejecting.", "danger")
        return redirect(url_for("admin.document_queue"))
    doc.status = decision
    doc.review_reason = reason if decision == "rejected" else None
    doc.reviewed_at = datetime.utcnow()
    doc.reviewed_by = current_user.id
    db.session.commit()
    doc.startup.refresh_document_status()
    log_action("startup_document_reviewed", f"document_id={doc.id} decision={decision} startup_id={doc.startup_id}")
    flash(f"Document {decision}.", "success")
    return redirect(url_for("admin.document_queue"))


@bp.route("/audit-log")
def audit_log():
    page = request.args.get("page", 1, type=int)
    pagination = AuditLog.query.order_by(AuditLog.created_at.desc()).paginate(page=page, per_page=40, error_out=False)
    return render_template("admin/audit_log.html", pagination=pagination, logs=pagination.items)

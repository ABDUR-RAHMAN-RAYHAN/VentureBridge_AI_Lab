from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Job, Startup, JobApplication
from forms import JobForm, JobApplicationForm
from decorators import roles_required
from utils import save_upload, log_action, is_upload

bp = Blueprint("jobs", __name__, url_prefix="/jobs")

PER_PAGE = 9


@bp.route("/")
def list_jobs():
    q = request.args.get("q", "").strip()
    location = request.args.get("location", "").strip()
    job_type = request.args.get("job_type", "").strip()
    skill = request.args.get("skill", "").strip()
    page = request.args.get("page", 1, type=int)
    # ?mine=1 — a founder's own postings (any status), linked from the dashboard.
    mine = (request.args.get("mine", "") == "1" and current_user.is_authenticated
            and current_user.role == "founder")

    if mine:
        startup_ids = [s.id for s in current_user.startups]
        query = Job.query.filter(Job.startup_id.in_(startup_ids)) if startup_ids \
            else Job.query.filter(Job.id < 0)
    else:
        query = Job.query.join(Startup).filter(Job.status == "open", Startup.is_active.is_(True),
                                                Startup.document_status == "approved")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Job.title.ilike(like), Job.description.ilike(like)))
    if location:
        query = query.filter(Job.location.ilike(f"%{location}%"))
    if job_type:
        query = query.filter(Job.job_type == job_type)
    if skill:
        query = query.filter(Job.required_skills.ilike(f"%{skill}%"))

    pagination = query.order_by(Job.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    return render_template("jobs/list.html", pagination=pagination, jobs=pagination.items,
                            q=q, location=location, job_type=job_type, skill=skill, mine=mine)


@bp.route("/<int:job_id>")
def detail(job_id):
    job = Job.query.get_or_404(job_id)
    is_owner_or_admin = current_user.is_authenticated and (
        current_user.id == job.startup.founder_id or current_user.role == "admin")
    if not is_owner_or_admin and not job.startup.is_publicly_visible():
        abort(404)
    already_applied = False
    if current_user.is_authenticated and current_user.role == "jobseeker":
        already_applied = JobApplication.query.filter_by(job_id=job.id, applicant_id=current_user.id).first() is not None
    app_form = JobApplicationForm()
    return render_template("jobs/detail.html", job=job, already_applied=already_applied, app_form=app_form)


@bp.route("/startup/<int:startup_id>/create", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def create(startup_id):
    startup = Startup.query.get_or_404(startup_id)
    if startup.founder_id != current_user.id:
        abort(403)
    if not current_user.is_verified():
        flash("You need an approved identity verification before you can post a job. "
              "Submit your live-photo verification first.", "warning")
        return redirect(url_for("main.profile_edit"))
    form = JobForm()
    if form.validate_on_submit():
        job = Job(
            startup_id=startup.id, title=form.title.data.strip(), description=form.description.data,
            required_skills=form.required_skills.data, experience_level=form.experience_level.data,
            job_type=form.job_type.data, location=form.location.data,
            salary_min=form.salary_min.data, salary_max=form.salary_max.data, deadline=form.deadline.data,
        )
        db.session.add(job)
        db.session.commit()
        log_action("job_created", f"job_id={job.id} startup_id={startup.id}")
        flash("Job posted!", "success")
        return redirect(url_for("jobs.detail", job_id=job.id))
    return render_template("jobs/form.html", form=form, startup=startup)


@bp.route("/<int:job_id>/toggle", methods=["POST"])
@login_required
@roles_required("founder")
def toggle_status(job_id):
    job = Job.query.get_or_404(job_id)
    if job.startup.founder_id != current_user.id:
        abort(403)
    job.status = "closed" if job.status == "open" else "open"
    db.session.commit()
    log_action("job_status_toggled", f"job_id={job.id} status={job.status}")
    flash(f"Job marked as {job.status}.", "success")
    return redirect(request.referrer or url_for("main.dashboard"))


@bp.route("/<int:job_id>/apply", methods=["POST"])
@login_required
@roles_required("jobseeker")
def apply(job_id):
    job = Job.query.get_or_404(job_id)
    if job.status != "open":
        flash("This job is no longer accepting applications.", "warning")
        return redirect(url_for("jobs.detail", job_id=job.id))
    if JobApplication.query.filter_by(job_id=job.id, applicant_id=current_user.id).first():
        flash("You have already applied to this job.", "warning")
        return redirect(url_for("jobs.detail", job_id=job.id))

    form = JobApplicationForm()
    if form.validate_on_submit():
        try:
            fname = save_upload(form.cv.data, "cv", {"pdf", "doc", "docx"})
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("jobs.detail", job_id=job.id))
        application = JobApplication(job_id=job.id, applicant_id=current_user.id,
                                      cv_filename=fname, cover_message=form.cover_message.data)
        db.session.add(application)
        db.session.commit()
        log_action("job_application_submitted", f"job_id={job.id}")
        flash("Application submitted!", "success")
    else:
        flash("Please attach a CV/resume and a cover message.", "danger")
    return redirect(url_for("jobs.detail", job_id=job.id))


@bp.route("/<int:job_id>/applications")
@login_required
@roles_required("founder")
def applications(job_id):
    job = Job.query.get_or_404(job_id)
    if job.startup.founder_id != current_user.id:
        abort(403)
    apps = job.applications.order_by(JobApplication.applied_at.desc()).all()
    return render_template("jobs/applications_founder.html", job=job, apps=apps)


@bp.route("/applications/<int:app_id>/status", methods=["POST"])
@login_required
@roles_required("founder")
def update_application_status(app_id):
    application = JobApplication.query.get_or_404(app_id)
    if application.job.startup.founder_id != current_user.id:
        abort(403)
    new_status = request.form.get("status")
    if new_status not in ("submitted", "reviewing", "shortlisted", "rejected", "accepted"):
        abort(400)
    application.status = new_status
    db.session.commit()
    log_action("application_status_changed", f"app_id={application.id} status={new_status}")
    flash("Application status updated.", "success")
    return redirect(url_for("jobs.applications", job_id=application.job_id))


@bp.route("/applications")
@login_required
@roles_required("founder")
def received_applications():
    """Every application across all of this founder's jobs (dashboard card target)."""
    status = request.args.get("status", "").strip()
    startup_ids = [s.id for s in current_user.startups]
    if startup_ids:
        query = JobApplication.query.join(Job).filter(Job.startup_id.in_(startup_ids))
        if status:
            query = query.filter(JobApplication.status == status)
        apps = query.order_by(JobApplication.applied_at.desc()).all()
    else:
        apps = []
    return render_template("jobs/applications_received.html", apps=apps, status=status)


@bp.route("/my-applications")
@login_required
@roles_required("jobseeker")
def my_applications():
    status = request.args.get("status", "").strip()
    query = JobApplication.query.filter_by(applicant_id=current_user.id)
    if status:
        query = query.filter_by(status=status)
    apps = query.order_by(JobApplication.applied_at.desc()).all()
    return render_template("jobs/applications_seeker.html", apps=apps, status=status)

from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from sqlalchemy import func
from extensions import db
from models import (User, Startup, Job, JobApplication, InvestmentRequest, Agreement,
                     IdentityVerification, VerificationPhoto, StartupDocument, AuditLog, Connection)
from forms import ProfileForm, ContactForm, VerificationForm
from utils import save_upload, save_base64_image, log_action, is_upload

bp = Blueprint("main", __name__)


@bp.route("/")
def index():
    stats = {
        "members": User.query.filter_by(is_active_account=True).count(),
        "startups": Startup.query.filter_by(is_active=True).count(),
        "jobs": Job.query.filter_by(status="open").count(),
        "verified_startups": Startup.query.filter_by(document_status="approved").count(),
    }
    featured = Startup.query.filter_by(is_active=True, document_status="approved").order_by(Startup.created_at.desc()).limit(3).all()
    return render_template("public/index.html", stats=stats, featured=featured)


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
        log_action("contact_form_submitted", f"from={form.email.data}")
        flash("Thanks for reaching out — we'll get back to you shortly.", "success")
        return redirect(url_for("main.contact"))
    return render_template("public/contact.html", form=form)


# Colors used by the dashboard breakdown bars
_C_BLUE = "#1f8fe0"
_C_GREEN = "#1eb872"
_C_GOLD = "#c9a227"
_C_RED = "#e0575b"
_C_SLATE = "#7a8b99"
_C_DEEP = "#0f5c99"

_APP_STATUS_STYLE = [
    ("submitted", "Submitted", _C_BLUE),
    ("reviewing", "Reviewing", _C_GOLD),
    ("shortlisted", "Shortlisted", _C_GREEN),
    ("accepted", "Accepted", _C_DEEP),
    ("rejected", "Rejected", _C_RED),
]

_REQ_STATUS_STYLE = [
    ("pending", "Awaiting founder", _C_SLATE),
    ("awaiting_investor_review", "Proposal to review", _C_GOLD),
    ("awaiting_founder_review", "Changes sent back", _C_GOLD),
    ("milestones_setup", "Setting milestones", _C_BLUE),
    ("awaiting_signatures", "Awaiting signatures", _C_BLUE),
    ("active", "Active", _C_GREEN),
    ("rejected", "Rejected", _C_RED),
]

_ROLE_STYLE = [
    ("founder", "Founders", _C_BLUE),
    ("investor", "Investors", _C_GREEN),
    ("jobseeker", "Job Seekers", _C_GOLD),
    ("admin", "Admins", _C_SLATE),
]


def _to_breakdown(counts, style):
    """Turn {key: count} into the ordered list the breakdown macro expects."""
    return [{"label": label, "count": counts.get(key, 0), "color": color}
            for key, label, color in style if counts.get(key, 0) > 0]


@bp.route("/dashboard")
@login_required
def dashboard():
    ctx = {}

    if current_user.role == "founder":
        startup_ids = [s.id for s in current_user.startups]
        ctx["startup_count"] = len(startup_ids)
        ctx["active_jobs"] = Job.query.filter(Job.startup_id.in_(startup_ids), Job.status == "open").count() if startup_ids else 0
        ctx["applications_received"] = JobApplication.query.join(Job).filter(Job.startup_id.in_(startup_ids)).count() if startup_ids else 0
        ctx["pending_requests"] = InvestmentRequest.query.filter(
            InvestmentRequest.startup_id.in_(startup_ids), InvestmentRequest.status == "pending").count() if startup_ids else 0
        ctx["startups"] = current_user.startups.all()

        rows = db.session.query(JobApplication.status, func.count(JobApplication.id)).join(Job).filter(
            Job.startup_id.in_(startup_ids)).group_by(JobApplication.status).all() if startup_ids else []
        ctx["app_breakdown"] = _to_breakdown(dict(rows), _APP_STATUS_STYLE)

        agreements = [r.agreement for r in InvestmentRequest.query.filter(
            InvestmentRequest.startup_id.in_(startup_ids)).all() if r.agreement] if startup_ids else []
        active = [a for a in agreements if a.status == "active"]
        ctx["total_expected"] = sum(float(a.funding_amount) for a in active)
        ctx["total_received"] = sum(a.total_received_by_founder() for a in agreements)
        ctx["pending_release"] = sum(a.total_still_held() for a in agreements)
        ctx["awaiting_investor_payment"] = sum(
            float(a.funding_amount) for a in active if not a.admin_confirmed_deposit_at)

    elif current_user.role == "investor":
        reqs = InvestmentRequest.query.filter_by(investor_id=current_user.id)
        ctx["sent"] = reqs.count()
        ctx["accepted"] = reqs.filter_by(status="active").count()
        ctx["connections"] = Connection.query.filter(
            (Connection.user_a_id == current_user.id) | (Connection.user_b_id == current_user.id)).count()

        rows = db.session.query(InvestmentRequest.status, func.count(InvestmentRequest.id)).filter_by(
            investor_id=current_user.id).group_by(InvestmentRequest.status).all()
        ctx["req_breakdown"] = _to_breakdown(dict(rows), _REQ_STATUS_STYLE)

        agreements = [r.agreement for r in reqs.all() if r.agreement]
        active = [a for a in agreements if a.status == "active"]
        ctx["total_committed"] = sum(float(a.funding_amount) for a in active)
        ctx["total_sent"] = sum(float(a.funding_amount) for a in agreements if a.admin_confirmed_deposit_at)
        ctx["total_owed"] = sum(float(a.funding_amount) for a in active if not a.admin_confirmed_deposit_at)

    elif current_user.role == "jobseeker":
        apps = JobApplication.query.filter_by(applicant_id=current_user.id)
        ctx["applications_sent"] = apps.count()
        ctx["shortlisted"] = apps.filter_by(status="shortlisted").count()
        rows = db.session.query(JobApplication.status, func.count(JobApplication.id)).filter_by(
            applicant_id=current_user.id).group_by(JobApplication.status).all()
        ctx["app_breakdown"] = _to_breakdown(dict(rows), _APP_STATUS_STYLE)

    elif current_user.role == "admin":
        ctx["total_users"] = User.query.count()
        ctx["total_startups"] = Startup.query.count()
        ctx["pending_docs"] = StartupDocument.query.filter_by(status="pending").count()
        ctx["pending_verifications"] = IdentityVerification.query.filter_by(status="pending").count()

        rows = db.session.query(User.role, func.count(User.id)).group_by(User.role).all()
        ctx["role_breakdown"] = _to_breakdown(dict(rows), _ROLE_STYLE)

        all_agreements = Agreement.query.all()
        ctx["admin_held"] = sum(a.total_still_held() for a in all_agreements)
        ctx["admin_released"] = sum(a.total_received_by_founder() for a in all_agreements)
        ctx["admin_fees"] = sum(a.total_fee_charged() for a in all_agreements)
        # Deposits awaiting confirmation + milestones ready to release
        deposits_to_confirm = sum(1 for a in all_agreements
                                   if a.investor_deposited_at and not a.admin_confirmed_deposit_at)
        milestones_ready = sum(1 for a in all_agreements if a.admin_confirmed_deposit_at
                                for m in a.milestones if m.status == "pending" and m.is_next_in_sequence())
        ctx["admin_actions_pending"] = deposits_to_confirm + milestones_ready

    return render_template("dashboard/dashboard.html", **ctx)


@bp.route("/profile")
@login_required
def profile():
    verification_history = []
    if current_user.requires_identity_verification():
        verification_history = IdentityVerification.query.filter_by(
            user_id=current_user.id).order_by(IdentityVerification.submitted_at.desc()).all()
    return render_template("profile/view.html", profile=current_user.profile,
                            verification_history=verification_history)


@bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def profile_edit():
    """
    A single form, a single "Save Profile" button. Saving profile fields and
    submitting identity verification are two independent concerns handled in
    ONE request, so there is no way to fill in both sections but only submit
    one of them by mistake (the previous two-form design allowed exactly
    that, silently losing whichever section wasn't submitted).
    """
    profile = current_user.profile
    form = ProfileForm(obj=profile)
    verification_form = VerificationForm()

    if request.method == "POST":
        profile_ok = True
        if form.validate_on_submit():
            if is_upload(form.photo.data):
                try:
                    filename = save_upload(form.photo.data, "logos", {"png", "jpg", "jpeg"})
                    profile.photo = filename
                except ValueError as e:
                    flash(f"Profile photo: {e}", "danger")
                    profile_ok = False
            if profile_ok:
                profile.phone = form.phone.data
                profile.bio = form.bio.data
                profile.location = form.location.data
                profile.education = form.education.data
                profile.experience = form.experience.data
                profile.industry = form.industry.data
                profile.skills = form.skills.data
                profile.interests = form.interests.data
        else:
            profile_ok = False
            for field_name, errors in form.errors.items():
                field_label = getattr(form, field_name).label.text
                for err in errors:
                    flash(f"{field_label}: {err}", "danger")

        # Identity verification is optional on this submission: only attempt
        # it if the person actually provided verification data. Admins don't
        # go through identity verification at all — they're staff accounts,
        # not marketplace participants — so the whole flow is skipped for them.
        verification_attempted = False
        verification_ok = True
        if current_user.requires_identity_verification():
            photos_given = [verification_form.photo_1.data, verification_form.photo_2.data,
                             verification_form.photo_3.data]
            photos_count = sum(1 for p in photos_given if p)
            id_doc_given = is_upload(verification_form.id_document.data)
            verification_attempted = photos_count > 0 or id_doc_given

            if verification_attempted:
                missing = []
                if not id_doc_given:
                    missing.append("NID/ID card upload")
                if photos_count < 3:
                    missing.append(f"all 3 live photos (you provided {photos_count})")
                if missing:
                    flash("Identity verification was not submitted — missing: " + " and ".join(missing) +
                          ". Your profile information above was still saved.", "warning")
                    verification_ok = False
                else:
                    try:
                        id_doc_filename = save_upload(verification_form.id_document.data, "verification",
                                                       {"pdf", "png", "jpg", "jpeg"})
                        verification = IdentityVerification(user_id=current_user.id, doc_type=verification_form.doc_type.data,
                                                             id_document_filename=id_doc_filename)
                        db.session.add(verification)
                        db.session.flush()
                        for slot, field in enumerate([verification_form.photo_1, verification_form.photo_2,
                                                       verification_form.photo_3], start=1):
                            fname = save_base64_image(field.data, "verification")
                            db.session.add(VerificationPhoto(verification_id=verification.id, filename=fname,
                                                              slot=slot, captured_live=True))
                        log_action("identity_verification_submitted", f"doc_type={verification_form.doc_type.data}")
                    except ValueError as e:
                        db.session.rollback()
                        flash(f"Identity verification failed: {e}. Your profile information above was still saved.", "danger")
                        verification_ok = False

        if profile_ok:
            db.session.commit()
            log_action("profile_updated")
            if verification_attempted and verification_ok:
                flash("Profile updated and identity verification submitted for admin review.", "success")
            else:
                flash("Profile updated successfully.", "success")
            return redirect(url_for("main.profile"))
        else:
            db.session.rollback()

    return render_template("profile/form.html", form=form, verification_form=verification_form, profile=profile)

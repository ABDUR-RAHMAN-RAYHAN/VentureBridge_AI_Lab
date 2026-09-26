from flask import Blueprint, render_template, redirect, url_for, flash, request, abort
from flask_login import login_required, current_user
from extensions import db
from models import Startup, StartupDocument, InvestmentRequest, Connection
from forms import StartupForm, StartupDocumentForm, InvestmentRequestForm
from decorators import roles_required
from utils import save_upload, log_action, is_upload
from algorithms.knn_recommender import find_similar_startups

bp = Blueprint("startups", __name__, url_prefix="/startups")

PER_PAGE = 9


@bp.route("/")
def list_startups():
    q = request.args.get("q", "").strip()
    industry = request.args.get("industry", "").strip()
    location = request.args.get("location", "").strip()
    stage = request.args.get("stage", "").strip()
    page = request.args.get("page", 1, type=int)
    # ?mine=1 — the founder's own listings, including ones still pending review.
    # This is what the "Startups" card on the dashboard links to.
    mine = request.args.get("mine", "") == "1" and current_user.is_authenticated

    if mine:
        query = Startup.query.filter_by(founder_id=current_user.id)
    else:
        query = Startup.query.filter_by(is_active=True, document_status="approved")
    if q:
        like = f"%{q}%"
        query = query.filter(db.or_(Startup.name.ilike(like), Startup.description.ilike(like)))
    if industry:
        query = query.filter(Startup.industry.ilike(f"%{industry}%"))
    if location:
        query = query.filter(Startup.location.ilike(f"%{location}%"))
    if stage:
        query = query.filter_by(stage=stage)

    pagination = query.order_by(Startup.created_at.desc()).paginate(page=page, per_page=PER_PAGE, error_out=False)
    industries = [r[0] for r in db.session.query(Startup.industry).distinct() if r[0]]
    return render_template("startups/list.html", pagination=pagination, startups=pagination.items,
                            industries=industries, q=q, industry=industry, location=location,
                            stage=stage, mine=mine)


@bp.route("/<int:startup_id>")
def detail(startup_id):
    startup = Startup.query.get_or_404(startup_id)
    is_owner_or_admin = current_user.is_authenticated and (
        current_user.id == startup.founder_id or current_user.role == "admin")
    if not is_owner_or_admin and not startup.is_publicly_visible():
        # Don't reveal that an unverified/deactivated startup exists to the public
        abort(404)
    already_requested = False
    is_connected = False
    if current_user.is_authenticated and current_user.role == "investor":
        already_requested = InvestmentRequest.query.filter_by(
            investor_id=current_user.id, startup_id=startup.id).first() is not None
    if current_user.is_authenticated:
        is_connected = Connection.query.filter(
            ((Connection.user_a_id == current_user.id) & (Connection.user_b_id == startup.founder_id)) |
            ((Connection.user_b_id == current_user.id) & (Connection.user_a_id == startup.founder_id))
        ).first() is not None
    req_form = InvestmentRequestForm()

    candidate_pool = Startup.query.filter(
        Startup.is_active.is_(True), Startup.document_status == "approved", Startup.id != startup.id
    ).all()
    similar = find_similar_startups(startup, candidate_pool, k=3)

    return render_template("startups/detail.html", startup=startup, already_requested=already_requested,
                            is_connected=is_connected, req_form=req_form, similar=similar)


@bp.route("/create", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def create():
    if not current_user.is_verified():
        flash("You need an approved identity verification before you can list a startup. "
              "Submit your live-photo verification first.", "warning")
        return redirect(url_for("main.profile_edit"))
    form = StartupForm()
    if form.validate_on_submit():
        if not is_upload(form.trade_license.data):
            flash("A Trade License document is required to publish a startup.", "danger")
            return render_template("startups/form.html", form=form, mode="create")
        startup = Startup(
            founder_id=current_user.id, name=form.name.data.strip(), description=form.description.data,
            industry=form.industry.data, stage=form.stage.data, location=form.location.data,
            website=form.website.data, founded_year=form.founded_year.data,
            business_model=form.business_model.data, team_size=form.team_size.data,
        )
        if is_upload(form.logo.data):
            try:
                startup.logo = save_upload(form.logo.data, "logos", {"png", "jpg", "jpeg"})
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("startups/form.html", form=form, mode="create")
        db.session.add(startup)
        db.session.flush()
        try:
            fname = save_upload(form.trade_license.data, "documents", {"pdf", "png", "jpg", "jpeg"})
        except ValueError as e:
            db.session.rollback()
            flash(str(e), "danger")
            return render_template("startups/form.html", form=form, mode="create")
        db.session.add(StartupDocument(startup_id=startup.id, doc_type="Trade License", filename=fname))
        db.session.commit()
        log_action("startup_created", f"startup_id={startup.id} name={startup.name}")
        flash("Startup created! It is now public but flagged 'Pending Document Review' "
              "until an admin approves your Trade License.", "success")
        return redirect(url_for("startups.detail", startup_id=startup.id))
    return render_template("startups/form.html", form=form, mode="create")


@bp.route("/<int:startup_id>/edit", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def edit(startup_id):
    startup = Startup.query.get_or_404(startup_id)
    if startup.founder_id != current_user.id:
        abort(403)
    form = StartupForm(obj=startup)
    if form.validate_on_submit():
        startup.name = form.name.data.strip()
        startup.description = form.description.data
        startup.industry = form.industry.data
        startup.stage = form.stage.data
        startup.location = form.location.data
        startup.website = form.website.data
        startup.founded_year = form.founded_year.data
        startup.business_model = form.business_model.data
        startup.team_size = form.team_size.data
        if is_upload(form.logo.data):
            try:
                startup.logo = save_upload(form.logo.data, "logos", {"png", "jpg", "jpeg"})
            except ValueError as e:
                flash(str(e), "danger")
                return render_template("startups/form.html", form=form, mode="edit", startup=startup)
        db.session.commit()
        log_action("startup_updated", f"startup_id={startup.id}")
        flash("Startup updated.", "success")
        return redirect(url_for("startups.detail", startup_id=startup.id))
    return render_template("startups/form.html", form=form, mode="edit", startup=startup)


@bp.route("/<int:startup_id>/documents", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def documents(startup_id):
    startup = Startup.query.get_or_404(startup_id)
    if startup.founder_id != current_user.id:
        abort(403)
    form = StartupDocumentForm()
    if form.validate_on_submit():
        try:
            fname = save_upload(form.document.data, "documents", {"pdf", "png", "jpg", "jpeg"})
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("startups.documents", startup_id=startup.id))
        db.session.add(StartupDocument(startup_id=startup.id, doc_type=form.doc_type.data, filename=fname))
        startup.document_status = "pending"
        db.session.commit()
        log_action("startup_document_uploaded", f"startup_id={startup.id} type={form.doc_type.data}")
        flash("Document submitted for admin review.", "success")
        return redirect(url_for("startups.documents", startup_id=startup.id))
    docs = startup.documents.order_by(StartupDocument.uploaded_at.desc()).all()
    return render_template("startups/documents.html", startup=startup, form=form, docs=docs)

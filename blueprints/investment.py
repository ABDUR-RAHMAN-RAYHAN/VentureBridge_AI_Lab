import json
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, abort, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import (InvestmentRequest, Startup, Connection, Agreement, FundingMilestone,
                     FundingProposal, FundingProposalItem, User)
from forms import (InvestmentRequestForm, InvestorApproachForm, AgreementForm,
                    FinancialProposalForm, SignatureForm, MilestoneProofForm)
from decorators import roles_required
from utils import log_action, make_reference_no, save_upload, notify
from config import Config
from algorithms.csp_scheduler import solve_milestone_schedule

bp = Blueprint("investment", __name__, url_prefix="/investment")


def _parse_items(raw_json):
    try:
        items = json.loads(raw_json or "[]")
    except (ValueError, TypeError):
        items = []
    return [it for it in items if it.get("reason") and it.get("amount")]


def _parse_items_ms(raw_json):
    try:
        items = json.loads(raw_json or "[]")
    except (ValueError, TypeError):
        items = []
    return [m for m in items if m.get("title") and m.get("amount")]


def _guard_party(req):
    """Only the investor, the founder who owns the startup, or an admin may act on a request."""
    allowed = current_user.role == "admin" or current_user.id in (req.investor_id, req.startup.founder_id)
    if not allowed:
        abort(404)  # don't reveal the request exists to unrelated users


# =========================================================
# Founder browses verified investors and approaches one directly.
# This only adds a new *entry point* — the request this creates is the
# same InvestmentRequest, in the same "pending" state, that the existing
# founder_requests / submit_proposal / reject flow below already handles.
# Nothing past this point changes.
# =========================================================
@bp.route("/investors")
@login_required
@roles_required("founder")
def browse_investors():
    q = request.args.get("q", "").strip()
    query = User.query.filter_by(role="investor", is_active_account=True)
    if q:
        query = query.filter(User.full_name.ilike(f"%{q}%"))
    investors = [u for u in query.order_by(User.full_name).all() if u.is_verified()]

    startup_ids = [s.id for s in current_user.startups]
    already_contacted = {r.investor_id for r in InvestmentRequest.query.filter(
        InvestmentRequest.startup_id.in_(startup_ids)).all()} if startup_ids else set()

    return render_template("investment/investors.html", investors=investors, q=q,
                            already_contacted=already_contacted)


@bp.route("/investors/<int:investor_id>/approach", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def approach_investor(investor_id):
    investor = User.query.filter_by(id=investor_id, role="investor", is_active_account=True).first_or_404()
    if not investor.is_verified():
        abort(404)  # only verified investors are approachable
    if not current_user.is_verified():
        flash("You need an approved identity verification before you can contact an investor. "
              "Submit your NID and live photo verification first.", "warning")
        return redirect(url_for("main.profile_edit"))

    my_startups = current_user.startups.all()
    if not my_startups:
        flash("List a startup before reaching out to an investor.", "warning")
        return redirect(url_for("startups.create"))

    form = InvestorApproachForm()
    form.startup_id.choices = [(s.id, s.name) for s in my_startups]

    if form.validate_on_submit():
        startup = next((s for s in my_startups if s.id == form.startup_id.data), None)
        if not startup:
            abort(400)
        if InvestmentRequest.query.filter_by(investor_id=investor.id, startup_id=startup.id).first():
            flash("You have already reached out to this investor for this startup.", "warning")
            return redirect(url_for("investment.browse_investors"))

        req = InvestmentRequest(investor_id=investor.id, startup_id=startup.id, message=form.message.data)
        db.session.add(req)
        db.session.commit()
        log_action("investment_outreach_sent", f"startup_id={startup.id} investor_id={investor.id}")
        notify(investor.id, "New investment request",
               f"{current_user.full_name} would like you to consider investing in {startup.name}.",
               url_for("investment.investor_requests"))
        flash(f"Your investment request has been sent to {investor.full_name}.", "success")
        return redirect(url_for("investment.founder_requests"))

    return render_template("investment/approach_investor.html", form=form, investor=investor)


# =========================================================
# STEP 1 — Investor sends interest
# =========================================================
@bp.route("/startup/<int:startup_id>/request", methods=["POST"])
@login_required
@roles_required("investor")
def send_request(startup_id):
    if not current_user.is_verified():
        flash("You need an approved identity verification before you can send investment interest. "
              "Submit your NID and live photo verification first.", "warning")
        return redirect(url_for("main.profile_edit"))
    startup = Startup.query.get_or_404(startup_id)
    if not startup.is_publicly_visible():
        abort(404)
    if InvestmentRequest.query.filter_by(investor_id=current_user.id, startup_id=startup.id).first():
        flash("You have already sent an interest request to this startup.", "warning")
        return redirect(url_for("startups.detail", startup_id=startup.id))

    form = InvestmentRequestForm()
    if form.validate_on_submit():
        req = InvestmentRequest(investor_id=current_user.id, startup_id=startup.id, message=form.message.data)
        db.session.add(req)
        db.session.commit()
        log_action("investment_interest_sent", f"startup_id={startup.id}")
        flash("Your investment interest has been sent to the founder.", "success")
        notify(startup.founder_id, "New investment interest",
               f"{current_user.full_name} is interested in investing in {startup.name}.",
               url_for("investment.founder_requests"))
    else:
        flash("A message is required to express interest.", "danger")
    return redirect(url_for("startups.detail", startup_id=startup.id))


@bp.route("/founder")
@login_required
@roles_required("founder")
def founder_requests():
    startup_ids = [s.id for s in current_user.startups]
    reqs = InvestmentRequest.query.filter(InvestmentRequest.startup_id.in_(startup_ids)).order_by(
        InvestmentRequest.created_at.desc()).all() if startup_ids else []
    return render_template("investment/founder_requests.html", reqs=reqs)


@bp.route("/investor")
@login_required
@roles_required("investor")
def investor_requests():
    reqs = InvestmentRequest.query.filter_by(investor_id=current_user.id).order_by(
        InvestmentRequest.created_at.desc()).all()
    return render_template("investment/investor_requests.html", reqs=reqs)


@bp.route("/<int:req_id>/reject", methods=["POST"])
@login_required
@roles_required("founder")
def reject(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.startup.founder_id != current_user.id:
        abort(403)
    if req.status != "pending":
        flash("This request is already in negotiation and can no longer be flatly rejected here.", "warning")
        return redirect(url_for("investment.founder_requests"))
    req.status = "rejected"
    req.decided_at = datetime.utcnow()
    db.session.commit()
    log_action("investment_request_rejected", f"request_id={req.id}")
    flash("Investment interest rejected.", "info")
    notify(req.investor_id, "Investment interest declined",
           f"{req.startup.name} declined your investment interest.", url_for("investment.investor_requests"))
    return redirect(url_for("investment.founder_requests"))


# =========================================================
# STEP 2 — Founder accepts interest -> submits financial distribution proposal
# =========================================================
@bp.route("/<int:req_id>/propose", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def submit_proposal(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.startup.founder_id != current_user.id:
        abort(403)
    if req.status not in ("pending", "awaiting_founder_review"):
        flash("This request isn't awaiting a proposal from you right now.", "warning")
        return redirect(url_for("investment.founder_requests"))

    form = FinancialProposalForm()
    if form.validate_on_submit():
        items = _parse_items(form.items_json.data)
        if not items:
            flash("Add at least one line item explaining what the money is for.", "danger")
            return render_template("investment/submit_proposal.html", req=req, form=form)
        item_total = sum(float(i["amount"]) for i in items)
        if round(item_total, 2) != round(float(form.total_amount.data), 2):
            flash(f"Line items must add up exactly to the total requested (${form.total_amount.data:,.2f}). "
                  f"They currently total ${item_total:,.2f}.", "danger")
            return render_template("investment/submit_proposal.html", req=req, form=form)

        latest = req.latest_proposal()
        next_version = (latest.version + 1) if latest else 1
        if latest and latest.status == "pending":
            latest.status = "superseded"
        proposal = FundingProposal(request_id=req.id, version=next_version, proposed_by_id=current_user.id,
                                    total_amount=form.total_amount.data, notes=form.notes.data)
        db.session.add(proposal)
        db.session.flush()
        for it in items:
            db.session.add(FundingProposalItem(proposal_id=proposal.id, reason=it["reason"][:255], amount=float(it["amount"])))
        req.status = "awaiting_investor_review"
        db.session.commit()
        log_action("funding_proposal_submitted", f"request_id={req.id} version={next_version} by=founder")
        flash("Your financial distribution proposal has been sent to the investor for review.", "success")
        notify(req.investor_id, "New funding proposal",
               f"{req.startup.name} sent you a funding distribution proposal to review.",
               url_for("investment.view_proposal", req_id=req.id))
        return redirect(url_for("investment.view_proposal", req_id=req.id))

    return render_template("investment/submit_proposal.html", req=req, form=form)


# =========================================================
# STEP 3 — View the current proposal (both parties) + history
# =========================================================
@bp.route("/<int:req_id>/proposal")
@login_required
def view_proposal(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    _guard_party(req)
    history = req.proposals.order_by(FundingProposal.version.desc()).all()
    latest = history[0] if history else None
    return render_template("investment/proposal.html", req=req, history=history, latest=latest)


@bp.route("/<int:req_id>/proposal/accept", methods=["POST"])
@login_required
def accept_proposal(req_id):
    """Either party accepts the CURRENT proposal, moving the request into milestone setup."""
    req = InvestmentRequest.query.get_or_404(req_id)
    _guard_party(req)
    latest = req.latest_proposal()
    if not latest:
        abort(400)
    if current_user.id == latest.proposed_by_id:
        flash("You proposed these terms — waiting on the other party to respond.", "warning")
        return redirect(url_for("investment.view_proposal", req_id=req.id))
    if req.status not in ("awaiting_investor_review", "awaiting_founder_review"):
        flash("This proposal is no longer awaiting a decision.", "warning")
        return redirect(url_for("investment.view_proposal", req_id=req.id))

    latest.status = "accepted"
    req.status = "milestones_setup"
    db.session.commit()
    log_action("funding_proposal_accepted", f"request_id={req.id} proposal_id={latest.id} by_user={current_user.id}")
    flash("Terms accepted. The founder can now set up the milestone schedule and generate the agreement.", "success")
    other_id = req.investor_id if current_user.id == req.startup.founder_id else req.startup.founder_id
    notify(other_id, "Funding terms accepted",
           f"The other party accepted the funding terms for {req.startup.name}. Milestones are being set up.",
           url_for("investment.view_proposal", req_id=req.id))
    if current_user.role == "founder":
        return redirect(url_for("investment.build_milestones", req_id=req.id))
    return redirect(url_for("investment.view_proposal", req_id=req.id))


@bp.route("/<int:req_id>/proposal/revise", methods=["GET", "POST"])
@login_required
@roles_required("investor")
def revise_proposal(req_id):
    """Investor reviews the founder's proposal and sends back changes instead of accepting."""
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.investor_id != current_user.id:
        abort(403)
    if req.status != "awaiting_investor_review":
        flash("There's no founder proposal currently awaiting your review.", "warning")
        return redirect(url_for("investment.view_proposal", req_id=req.id))

    latest = req.latest_proposal()
    form = FinancialProposalForm()
    if request.method == "GET" and latest:
        form.total_amount.data = float(latest.total_amount)
        form.notes.data = latest.notes

    if form.validate_on_submit():
        items = _parse_items(form.items_json.data)
        if not items:
            flash("Add at least one line item.", "danger")
            return render_template("investment/revise_proposal.html", req=req, form=form, latest=latest)
        item_total = sum(float(i["amount"]) for i in items)
        if round(item_total, 2) != round(float(form.total_amount.data), 2):
            flash(f"Line items must add up exactly to the total (${form.total_amount.data:,.2f}).", "danger")
            return render_template("investment/revise_proposal.html", req=req, form=form, latest=latest)

        if latest:
            latest.status = "superseded"
        next_version = (latest.version + 1) if latest else 1
        proposal = FundingProposal(request_id=req.id, version=next_version, proposed_by_id=current_user.id,
                                    total_amount=form.total_amount.data, notes=form.notes.data)
        db.session.add(proposal)
        db.session.flush()
        for it in items:
            db.session.add(FundingProposalItem(proposal_id=proposal.id, reason=it["reason"][:255], amount=float(it["amount"])))
        req.status = "awaiting_founder_review"
        db.session.commit()
        log_action("funding_proposal_revised", f"request_id={req.id} version={next_version} by=investor")
        flash("Your proposed changes have been sent back to the founder.", "success")
        notify(req.startup.founder_id, "Proposal revised by investor",
               f"The investor proposed changes to the funding terms for {req.startup.name}.",
               url_for("investment.view_proposal", req_id=req.id))
        return redirect(url_for("investment.view_proposal", req_id=req.id))

    return render_template("investment/revise_proposal.html", req=req, form=form, latest=latest)


# =========================================================
# STEP 4 — Founder builds the milestone schedule + generates the agreement
# =========================================================
@bp.route("/<int:req_id>/milestones", methods=["GET", "POST"])
@login_required
@roles_required("founder")
def build_milestones(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.startup.founder_id != current_user.id:
        abort(403)
    if req.status != "milestones_setup":
        flash("Milestones can only be set once both sides have agreed on the funding terms.", "warning")
        return redirect(url_for("investment.founder_requests"))

    final_proposal = req.latest_proposal()
    form = AgreementForm()
    if form.validate_on_submit():
        milestones_raw = _parse_items_ms(form.milestone_titles.data)
        if not milestones_raw:
            flash("Add at least one funding milestone.", "danger")
            return render_template("investment/build_milestones.html", req=req, form=form, proposal=final_proposal)
        total_ms = sum(float(m["amount"]) for m in milestones_raw)
        if round(total_ms, 2) != round(float(final_proposal.total_amount), 2):
            flash(f"Milestone amounts must add up exactly to the agreed total (${float(final_proposal.total_amount):,.2f}). "
                  f"They currently total ${total_ms:,.2f}.", "danger")
            return render_template("investment/build_milestones.html", req=req, form=form, proposal=final_proposal)

        agreement = Agreement(
            request_id=req.id, reference_no=make_reference_no(req.id),
            funding_amount=final_proposal.total_amount, platform_fee_percent=Config.PLATFORM_FEE_PERCENT,
            benefit_terms=form.benefit_terms.data, status="awaiting_signatures",
        )
        db.session.add(agreement)
        db.session.flush()
        for idx, m in enumerate(milestones_raw):
            db.session.add(FundingMilestone(agreement_id=agreement.id, title=m["title"][:150],
                                             description=m.get("description", "")[:1000],
                                             amount=float(m["amount"]), order_index=idx))
        req.status = "awaiting_signatures"
        db.session.commit()
        log_action("agreement_generated", f"request_id={req.id} agreement_id={agreement.id}")
        flash("Agreement generated. Both parties must now sign it before your journey together begins.", "success")
        notify(req.investor_id, "Agreement ready to sign",
               f"An agreement for {req.startup.name} has been generated — your signature is needed.",
               url_for("investment.sign_agreement", req_id=req.id))
        return redirect(url_for("investment.sign_agreement", req_id=req.id))

    return render_template("investment/build_milestones.html", req=req, form=form, proposal=final_proposal)


@bp.route("/<int:req_id>/milestones/csp-generate")
@login_required
@roles_required("founder")
def csp_generate_milestones(req_id):
    """
    Generates a valid milestone split using a CSP backtracking solver (see
    algorithms/csp_scheduler.py) rather than requiring the founder to do the
    arithmetic by hand. Returns JSON for the milestone-builder page to fill
    in client-side; the founder can still rename/edit before submitting.
    """
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.startup.founder_id != current_user.id:
        abort(403)
    final_proposal = req.latest_proposal()
    if not final_proposal:
        abort(400)

    count = request.args.get("count", 4, type=int)
    count = max(2, min(count, 8))

    amounts = solve_milestone_schedule(float(final_proposal.total_amount), count)
    if amounts is None:
        return jsonify({"ok": False, "error": "No valid schedule exists for that many milestones "
                                                "within the 10%-50% per-milestone bounds. Try a different count."})
    return jsonify({"ok": True, "amounts": amounts})


# =========================================================
# STEP 5 — Both parties sign the agreement
# =========================================================
@bp.route("/<int:req_id>/sign", methods=["GET", "POST"])
@login_required
def sign_agreement(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    _guard_party(req)
    agreement = req.agreement
    if not agreement:
        abort(404)

    is_founder = current_user.id == req.startup.founder_id
    is_investor = current_user.id == req.investor_id
    already_signed = (is_founder and agreement.founder_signed_at) or (is_investor and agreement.investor_signed_at)

    form = SignatureForm()
    if form.validate_on_submit() and not already_signed and agreement.status == "awaiting_signatures":
        try:
            sig_filename = save_upload(form.signature_document.data, "signatures", {"pdf", "png", "jpg", "jpeg"})
        except ValueError as e:
            flash(str(e), "danger")
            return render_template("investment/sign.html", req=req, agreement=agreement, form=form,
                                    is_founder=is_founder, is_investor=is_investor, already_signed=already_signed)

        now = datetime.utcnow()
        other_party_id = None
        if is_founder:
            agreement.founder_signature_filename = sig_filename
            agreement.founder_signed_at = now
            other_party_id = req.investor_id
        elif is_investor:
            agreement.investor_signature_filename = sig_filename
            agreement.investor_signed_at = now
            other_party_id = req.startup.founder_id

        if agreement.is_fully_signed():
            agreement.status = "active"
            req.status = "active"
            req.decided_at = now
            a, b = sorted([req.investor_id, req.startup.founder_id])
            if not Connection.query.filter_by(user_a_id=a, user_b_id=b).first():
                db.session.add(Connection(user_a_id=a, user_b_id=b, source="investment"))
            log_action("agreement_fully_signed", f"request_id={req.id} agreement_id={agreement.id}")
            flash("Both signatures are in. The agreement is now downloadable, and messaging is "
                  "unlocked — your journey together starts now!", "success")
            db.session.commit()
            notify(req.investor_id, "Agreement fully signed",
                   f"Your agreement for {req.startup.name} is now active and downloadable.",
                   url_for("investment.agreement", req_id=req.id))
            notify(req.startup.founder_id, "Agreement fully signed",
                   f"Your agreement with {req.investor.full_name} is now active and downloadable.",
                   url_for("investment.agreement", req_id=req.id))
        else:
            log_action("agreement_signed_by_party", f"request_id={req.id} agreement_id={agreement.id} by_user={current_user.id}")
            flash("Your signature has been recorded. Waiting on the other party to sign before "
                  "the agreement can be downloaded.", "success")
            db.session.commit()
            notify(other_party_id, "Your signature is needed",
                   f"The other party has signed the agreement for {req.startup.name} — your signature is next.",
                   url_for("investment.sign_agreement", req_id=req.id))
        return redirect(url_for("investment.agreement", req_id=req.id))

    return render_template("investment/sign.html", req=req, agreement=agreement, form=form,
                            is_founder=is_founder, is_investor=is_investor, already_signed=already_signed)


# =========================================================
# Agreement document (view + admin milestone release)
# =========================================================
@bp.route("/<int:req_id>/agreement")
@login_required
def agreement(req_id):
    req = InvestmentRequest.query.get_or_404(req_id)
    if not req.agreement:
        abort(404)
    _guard_party(req)
    milestones = req.agreement.milestones.order_by(FundingMilestone.order_index).all()
    final_proposal = req.proposals.filter_by(status="accepted").order_by(FundingProposal.version.desc()).first()
    return render_template("investment/agreement.html", req=req, agreement=req.agreement,
                            milestones=milestones, final_proposal=final_proposal)


# =========================================================
# FUND FLOW
# The investor deposits the FULL amount once; VentureBridge holds it and
# releases it to the founder milestone by milestone, in order, net of fee.
# =========================================================

@bp.route("/<int:req_id>/deposit", methods=["POST"])
@login_required
@roles_required("investor")
def deposit_funds(req_id):
    """STEP 1: investor sends the full funding amount to VentureBridge, once."""
    req = InvestmentRequest.query.get_or_404(req_id)
    if req.investor_id != current_user.id:
        abort(403)
    agreement = req.agreement
    if not agreement or agreement.status != "active":
        flash("The agreement must be fully signed by both parties before funds can be sent.", "danger")
        return redirect(url_for("investment.agreement", req_id=req.id))
    if agreement.investor_deposited_at:
        flash("You have already marked the funds as sent for this agreement.", "warning")
        return redirect(url_for("investment.agreement", req_id=req.id))

    note = request.form.get("note", "").strip()
    if not note:
        flash("Please include a reference or note describing how you sent the funds (e.g. transaction ID).", "danger")
        return redirect(url_for("investment.agreement", req_id=req.id))

    agreement.investor_deposited_at = datetime.utcnow()
    agreement.investor_deposit_note = note[:500]
    db.session.commit()
    log_action("agreement_funds_deposited",
               f"agreement_id={agreement.id} amount={agreement.funding_amount} note={note[:100]}")
    flash(f"Marked the full amount of ${float(agreement.funding_amount):,.2f} as sent. "
          "An admin will confirm receipt, then release it to the founder milestone by milestone.", "success")
    for admin in User.query.filter_by(role="admin", is_active_account=True).all():
        notify(admin.id, "Investor deposit awaiting confirmation",
               f"{current_user.full_name} marked ${float(agreement.funding_amount):,.2f} as sent for "
               f"{req.startup.name}. Please confirm receipt.",
               url_for("investment.agreement", req_id=req.id))
    return redirect(url_for("investment.agreement", req_id=req.id))


@bp.route("/<int:req_id>/confirm-deposit", methods=["POST"])
@login_required
@roles_required("admin")
def confirm_deposit(req_id):
    """STEP 2: admin confirms the full deposit arrived and is now held by VentureBridge."""
    req = InvestmentRequest.query.get_or_404(req_id)
    agreement = req.agreement
    if not agreement:
        abort(404)
    if not agreement.investor_deposited_at:
        flash("The investor hasn't marked the funds as sent yet.", "warning")
        return redirect(url_for("investment.agreement", req_id=req.id))
    if agreement.admin_confirmed_deposit_at:
        flash("This deposit has already been confirmed.", "warning")
        return redirect(url_for("investment.agreement", req_id=req.id))

    agreement.admin_confirmed_deposit_at = datetime.utcnow()
    agreement.admin_confirmed_deposit_by = current_user.id
    db.session.commit()
    log_action("agreement_deposit_confirmed",
               f"agreement_id={agreement.id} amount={agreement.funding_amount}")
    flash(f"Confirmed receipt of ${float(agreement.funding_amount):,.2f}. "
          "You can now release milestones to the founder one by one.", "success")
    notify(req.investor_id, "Deposit confirmed",
           f"VentureBridge confirmed receipt of your ${float(agreement.funding_amount):,.2f} deposit for "
           f"{req.startup.name}.", url_for("investment.agreement", req_id=req.id))
    notify(req.startup.founder_id, "Funds received by VentureBridge",
           f"The investor's deposit for {req.startup.name} has been confirmed and will be released to you "
           "milestone by milestone.", url_for("investment.agreement", req_id=req.id))
    return redirect(url_for("investment.agreement", req_id=req.id))


@bp.route("/milestone/<int:milestone_id>/release", methods=["POST"])
@login_required
@roles_required("admin")
def release_milestone(milestone_id):
    """
    STEP 3: admin releases one milestone to the founder, net of the platform
    fee. Milestones must be released in order, and only after the investor's
    full deposit has been confirmed.
    """
    milestone = FundingMilestone.query.get_or_404(milestone_id)
    agreement = milestone.agreement
    if agreement.status != "active":
        flash("Funds can only be released once the agreement is fully signed by both parties.", "danger")
        return redirect(url_for("investment.agreement", req_id=agreement.request_id))
    if not agreement.admin_confirmed_deposit_at:
        flash("The investor's full deposit must be received and confirmed before releasing any milestone.", "danger")
        return redirect(url_for("investment.agreement", req_id=agreement.request_id))
    if milestone.status == "released":
        flash("This milestone has already been released.", "warning")
        return redirect(url_for("investment.agreement", req_id=agreement.request_id))
    if not milestone.is_next_in_sequence():
        flash("Milestones must be released in order — complete the earlier milestone first.", "danger")
        return redirect(url_for("investment.agreement", req_id=agreement.request_id))

    milestone.status = "released"
    milestone.released_at = datetime.utcnow()
    milestone.released_by = current_user.id
    db.session.commit()
    log_action("milestone_released",
               f"milestone_id={milestone.id} gross={milestone.amount} "
               f"fee={milestone.platform_fee_amount():.2f} net_to_founder={milestone.net_to_founder():.2f}")
    flash(f"Released '{milestone.title}': ${milestone.net_to_founder():,.2f} to the founder "
          f"(${milestone.platform_fee_amount():,.2f} platform fee retained).", "success")
    req = agreement.request
    notify(req.startup.founder_id, "Milestone funds released",
           f"${milestone.net_to_founder():,.2f} for '{milestone.title}' has been released to you.",
           url_for("investment.agreement", req_id=req.id))
    notify(req.investor_id, "Milestone released",
           f"'{milestone.title}' (${float(milestone.amount):,.2f}) has been released to the founder for "
           f"{req.startup.name}.", url_for("investment.agreement", req_id=req.id))
    return redirect(url_for("investment.agreement", req_id=agreement.request_id))


@bp.route("/milestone/<int:milestone_id>/upload-proof", methods=["POST"])
@login_required
@roles_required("founder")
def upload_milestone_proof(milestone_id):
    """STEP 4: founder uploads proof of how the released funds were used."""
    milestone = FundingMilestone.query.get_or_404(milestone_id)
    req = milestone.agreement.request
    if req.startup.founder_id != current_user.id:
        abort(403)
    if milestone.status != "released":
        flash("Proof can only be uploaded after this milestone's funds have been released to you.", "danger")
        return redirect(url_for("investment.agreement", req_id=req.id))

    form = MilestoneProofForm()
    if form.validate_on_submit():
        try:
            fname = save_upload(form.proof_document.data, "proof", {"pdf", "png", "jpg", "jpeg"})
        except ValueError as e:
            flash(str(e), "danger")
            return redirect(url_for("investment.agreement", req_id=req.id))
        milestone.proof_document_filename = fname
        milestone.proof_description = form.description.data[:500]
        milestone.proof_uploaded_at = datetime.utcnow()
        db.session.commit()
        log_action("milestone_proof_uploaded", f"milestone_id={milestone.id}")
        flash(f"Proof of use uploaded for '{milestone.title}' — visible to the investor and admin.", "success")
    else:
        flash("Please attach a document and describe what it proves.", "danger")
    return redirect(url_for("investment.agreement", req_id=req.id))


@bp.route("/transactions")
@login_required
@roles_required("founder", "investor", "admin")
def transaction_history():
    """
    A ledger of every milestone this user is party to, with its current stage,
    the platform fee, and the net amount the founder receives. Admins see
    every milestone platform-wide as an oversight ledger.
    """
    if current_user.role == "admin":
        reqs = InvestmentRequest.query.all()
    elif current_user.role == "investor":
        reqs = InvestmentRequest.query.filter_by(investor_id=current_user.id).all()
    else:
        startup_ids = [s.id for s in current_user.startups]
        reqs = InvestmentRequest.query.filter(InvestmentRequest.startup_id.in_(startup_ids)).all() if startup_ids else []

    rows = []
    for r in reqs:
        if not r.agreement:
            continue
        for m in r.agreement.milestones.order_by(FundingMilestone.order_index).all():
            rows.append({"milestone": m, "agreement": r.agreement, "request": r})
    rows.sort(key=lambda x: x["milestone"].released_at or datetime.min, reverse=True)
    return render_template("investment/transaction_history.html", rows=rows)

import secrets
from datetime import datetime, timedelta
from flask_login import UserMixin
from extensions import db, bcrypt

# ---------- Enums (plain string constants; enforced in app logic) ----------
ROLES = ("founder", "investor", "jobseeker", "admin")
DOC_STATUS = ("pending", "approved", "rejected")
APP_STATUS = ("submitted", "reviewing", "shortlisted", "rejected", "accepted")
REQUEST_STATUS = ("pending", "awaiting_investor_review", "awaiting_founder_review",
                   "milestones_setup", "awaiting_signatures", "active", "rejected")
MILESTONE_STATUS = ("pending", "released")
JOB_STATUS = ("open", "closed")
STAGES = ("Idea", "MVP", "Early Stage", "Growth", "Scaling")
JOB_TYPES = ("Full-time", "Part-time", "Internship", "Remote", "Contract")
DOC_TYPES = ("Trade License", "Certificate of Incorporation", "Tax Registration", "Other")
ID_DOC_TYPES = ("National ID", "Passport", "Driving License")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all,delete")
    startups = db.relationship("Startup", backref="founder", lazy="dynamic", foreign_keys="Startup.founder_id")

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    # Flask-Login expects is_active property
    @property
    def is_active(self):
        return self.is_active_account

    def is_verified(self):
        return any(v.status == "approved" for v in self.verifications)

    def requires_identity_verification(self):
        """Admins operate under staff trust, not the marketplace's NID/live-photo
        flow — they never need to submit or hold identity verification."""
        return self.role != "admin"


class Profile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), unique=True, nullable=False)
    photo = db.Column(db.String(255))
    phone = db.Column(db.String(30))
    bio = db.Column(db.Text)
    location = db.Column(db.String(120))
    education = db.Column(db.String(255))
    experience = db.Column(db.String(255))
    industry = db.Column(db.String(120))
    skills = db.Column(db.String(500))       # comma-separated
    interests = db.Column(db.String(500))    # comma-separated

    # Weights reflect how much each field matters to a usable profile, and
    # sum to 100. Identity verification (worth 20) only applies to roles
    # that go through that flow; for those that don't (admins), its weight
    # is folded back proportionally into the other fields so 100% is still
    # reachable from the fields alone.
    FIELD_WEIGHTS = {
        "bio": 12, "experience": 12, "skills": 12,
        "photo": 8, "location": 8, "education": 8, "industry": 8, "interests": 8,
        "phone": 4,
    }
    VERIFICATION_WEIGHT = 20

    def completion_percent(self):
        weights = self.FIELD_WEIGHTS
        needs_verification = self.user and self.user.requires_identity_verification()
        if not needs_verification:
            scale = 100 / (100 - self.VERIFICATION_WEIGHT)
            weights = {field: w * scale for field, w in weights.items()}

        earned = sum(w for field, w in weights.items() if getattr(self, field))
        if needs_verification and self.user.is_verified():
            earned += self.VERIFICATION_WEIGHT
        return int(round(earned))


class Startup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    founder_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    name = db.Column(db.String(150), nullable=False, index=True)
    logo = db.Column(db.String(255))
    description = db.Column(db.Text)
    industry = db.Column(db.String(120), index=True)
    stage = db.Column(db.String(30))
    location = db.Column(db.String(120), index=True)
    website = db.Column(db.String(255))
    founded_year = db.Column(db.Integer)
    business_model = db.Column(db.String(255))
    team_size = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, default=True)
    document_status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    documents = db.relationship("StartupDocument", backref="startup", cascade="all,delete", lazy="dynamic")
    jobs = db.relationship("Job", backref="startup", cascade="all,delete", lazy="dynamic")
    investment_requests = db.relationship("InvestmentRequest", backref="startup", cascade="all,delete", lazy="dynamic")

    def refresh_document_status(self):
        docs = self.documents.all()
        if not docs:
            self.document_status = "pending"
        elif any(d.status == "rejected" for d in docs):
            self.document_status = "rejected"
        elif all(d.status == "approved" for d in docs):
            self.document_status = "approved"
        else:
            self.document_status = "pending"
        db.session.commit()

    def has_trade_license(self):
        return self.documents.filter_by(doc_type="Trade License").count() > 0

    def is_publicly_visible(self):
        return self.is_active and self.document_status == "approved"


class StartupDocument(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    startup_id = db.Column(db.Integer, db.ForeignKey("startup.id"), nullable=False)
    doc_type = db.Column(db.String(50), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), default="pending")
    review_reason = db.Column(db.Text)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))
    reviewed_at = db.Column(db.DateTime)
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)


class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    startup_id = db.Column(db.Integer, db.ForeignKey("startup.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False, index=True)
    description = db.Column(db.Text)
    required_skills = db.Column(db.String(500))
    experience_level = db.Column(db.String(50))
    job_type = db.Column(db.String(30))
    location = db.Column(db.String(120), index=True)
    salary_min = db.Column(db.Integer)
    salary_max = db.Column(db.Integer)
    deadline = db.Column(db.Date)
    status = db.Column(db.String(10), default="open")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    applications = db.relationship("JobApplication", backref="job", cascade="all,delete", lazy="dynamic")


class JobApplication(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey("job.id"), nullable=False)
    applicant_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    cv_filename = db.Column(db.String(255), nullable=False)
    cover_message = db.Column(db.Text)
    status = db.Column(db.String(20), default="submitted")
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)

    applicant = db.relationship("User", foreign_keys=[applicant_id])

    __table_args__ = (db.UniqueConstraint("job_id", "applicant_id", name="uq_job_applicant"),)


class InvestmentRequest(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    investor_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    startup_id = db.Column(db.Integer, db.ForeignKey("startup.id"), nullable=False)
    message = db.Column(db.Text, nullable=False)
    # Who started this request: "investor" (classic — expresses interest with just a
    # message; the founder proposes a funding breakdown afterwards) or "founder"
    # (a direct funding ask that already states an amount and equity/share offer).
    initiated_by = db.Column(db.String(10), nullable=False, default="investor")
    # pending -> rejected
    #         -> awaiting_investor_review (founder submitted a funding proposal)
    #         -> awaiting_founder_review (investor countered with changes)
    #         -> (loops between the two review states any number of times)
    #         -> milestones_setup (final amount/terms agreed; founder builds milestones)
    #         -> awaiting_signatures (agreement generated, needs both signatures)
    #         -> active (both signed; connection + messaging unlocked)
    status = db.Column(db.String(30), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    decided_at = db.Column(db.DateTime)

    investor = db.relationship("User", foreign_keys=[investor_id])
    agreement = db.relationship("Agreement", backref="request", uselist=False, cascade="all,delete")
    proposals = db.relationship("FundingProposal", backref="request", cascade="all,delete", lazy="dynamic")

    def latest_proposal(self):
        return self.proposals.order_by(FundingProposal.version.desc()).first()

    def is_equity_ask(self):
        """True for a founder-initiated request: amount + equity%, no itemized breakdown."""
        return self.initiated_by == "founder"


class FundingProposal(db.Model):
    """
    A financial-distribution proposal in the negotiation between founder and
    investor: how much money is needed, and a line-item breakdown of why.
    Each round (founder's initial draft, investor's counter, etc.) is a new
    version so the full negotiation history is preserved.
    """
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("investment_request.id"), nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    proposed_by_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    total_amount = db.Column(db.Numeric(14, 2), nullable=False)
    # Equity/share percentage offered in exchange for total_amount. Only set on
    # founder-initiated ("equity ask") requests — null for the classic,
    # item-breakdown flow.
    equity_percent = db.Column(db.Float)
    notes = db.Column(db.Text)
    # pending = awaiting the other party's decision; superseded = a later version replaced it; accepted = final
    status = db.Column(db.String(20), default="pending")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    proposed_by = db.relationship("User", foreign_keys=[proposed_by_id])
    items = db.relationship("FundingProposalItem", backref="proposal", cascade="all,delete", lazy="dynamic")


class FundingProposalItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    proposal_id = db.Column(db.Integer, db.ForeignKey("funding_proposal.id"), nullable=False)
    reason = db.Column(db.String(255), nullable=False)
    amount = db.Column(db.Numeric(14, 2), nullable=False)


class Agreement(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    request_id = db.Column(db.Integer, db.ForeignKey("investment_request.id"), unique=True, nullable=False)
    reference_no = db.Column(db.String(50), unique=True, nullable=False)
    funding_amount = db.Column(db.Numeric(14, 2), nullable=False)
    platform_fee_percent = db.Column(db.Float, default=2.5)
    benefit_terms = db.Column(db.Text)  # equity %, revenue share, etc., free text
    status = db.Column(db.String(20), default="awaiting_signatures")  # awaiting_signatures -> active
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    founder_signed_name = db.Column(db.String(150))
    founder_signed_at = db.Column(db.DateTime)
    investor_signed_name = db.Column(db.String(150))
    investor_signed_at = db.Column(db.DateTime)

    # The investor deposits the FULL funding amount once, up front. VentureBridge
    # then holds it and releases it to the founder milestone by milestone.
    investor_deposited_at = db.Column(db.DateTime)
    investor_deposit_note = db.Column(db.String(500))
    admin_confirmed_deposit_at = db.Column(db.DateTime)
    admin_confirmed_deposit_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    milestones = db.relationship("FundingMilestone", backref="agreement", cascade="all,delete", lazy="dynamic")

    def total_released(self):
        """Gross amount released (before platform fee deduction)."""
        return sum(float(m.amount) for m in self.milestones if m.status == "released")

    def total_fee_charged(self):
        return sum(float(m.platform_fee_amount() or 0) for m in self.milestones if m.status == "released")

    def total_received_by_founder(self):
        """Net amount the founder has actually received, after platform fees."""
        return sum(float(m.net_to_founder()) for m in self.milestones if m.status == "released")

    def total_still_held(self):
        """Funds deposited and confirmed but not yet released to the founder."""
        if not self.admin_confirmed_deposit_at:
            return 0.0
        return float(self.funding_amount) - self.total_released()

    def deposit_stage(self):
        """not_deposited -> awaiting_confirmation -> held"""
        if self.admin_confirmed_deposit_at:
            return "held"
        if self.investor_deposited_at:
            return "awaiting_confirmation"
        return "not_deposited"

    def is_fully_signed(self):
        return bool(self.founder_signed_at and self.investor_signed_at)


class FundingMilestone(db.Model):
    """
    The investor deposits the full amount up front (tracked on Agreement).
    Each milestone is then released by an admin, in order, once the previous
    one is complete. The founder receives the milestone amount MINUS the
    platform fee; the fee is VentureBridge's charge for facilitating.

    Status: pending -> released
    """
    id = db.Column(db.Integer, primary_key=True)
    agreement_id = db.Column(db.Integer, db.ForeignKey("agreement.id"), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(14, 2), nullable=False)
    status = db.Column(db.String(20), default="pending")
    order_index = db.Column(db.Integer, default=0)

    released_at = db.Column(db.DateTime)
    released_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    # Founder uploads proof of how the released funds were used.
    # Visible to the investor and admin.
    proof_document_filename = db.Column(db.String(255))
    proof_description = db.Column(db.String(500))
    proof_uploaded_at = db.Column(db.DateTime)

    def platform_fee_amount(self):
        return round(float(self.amount) * (self.agreement.platform_fee_percent / 100), 2)

    def net_to_founder(self):
        """What the founder actually receives after VentureBridge's fee."""
        return round(float(self.amount) - self.platform_fee_amount(), 2)

    def is_next_in_sequence(self):
        """
        True if this is the earliest still-pending milestone — enforcing that
        milestones are released one by one, in order.
        """
        pending = self.agreement.milestones.filter_by(status="pending").order_by(
            FundingMilestone.order_index).first()
        return pending is not None and pending.id == self.id


class Connection(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_a_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    user_b_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    source = db.Column(db.String(30), default="investment")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint("user_a_id", "user_b_id", name="uq_connection_pair"),)

    def other(self, user_id):
        return self.user_b_id if self.user_a_id == user_id else self.user_a_id


class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    connection_id = db.Column(db.Integer, db.ForeignKey("connection.id"), nullable=False)
    sender_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime)


class IdentityVerification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    doc_type = db.Column(db.String(30), nullable=False)
    id_document_filename = db.Column(db.String(255))  # uploaded NID/passport/license photo or scan
    status = db.Column(db.String(20), default="pending")
    reason = db.Column(db.Text)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at = db.Column(db.DateTime)
    reviewed_by = db.Column(db.Integer, db.ForeignKey("user.id"))

    user = db.relationship("User", foreign_keys=[user_id], backref="verifications")
    photos = db.relationship("VerificationPhoto", backref="verification", cascade="all,delete")


class VerificationPhoto(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    verification_id = db.Column(db.Integer, db.ForeignKey("identity_verification.id"), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    slot = db.Column(db.Integer, nullable=False)  # 1, 2, 3
    captured_live = db.Column(db.Boolean, default=True)


class LoginAttempt(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), index=True)
    ip_address = db.Column(db.String(64))
    success = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AuditLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(64))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    actor = db.relationship("User", foreign_keys=[user_id])


class PasswordReset(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token = db.Column(db.String(100), unique=True, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)
    used = db.Column(db.Boolean, default=False)

    @staticmethod
    def create_for(user_id):
        token = secrets.token_urlsafe(32)
        pr = PasswordReset(user_id=user_id, token=token,
                            expires_at=datetime.utcnow() + timedelta(hours=1))
        db.session.add(pr)
        return pr

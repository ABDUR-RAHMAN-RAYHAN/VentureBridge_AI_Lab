from flask import current_app
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed, FileRequired
from wtforms import (StringField, PasswordField, SelectField, TextAreaField,
                      IntegerField, FloatField, DateField, HiddenField)
from wtforms.validators import (DataRequired, Email, Length, EqualTo, Optional,
                                 NumberRange, ValidationError)
from models import User

DEFAULT_ALLOWED_EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "hotmail.com", "outlook.com"]


def allowed_email_domains():
    """The providers an account may be registered with (config-driven)."""
    try:
        return current_app.config.get("ALLOWED_EMAIL_DOMAINS", DEFAULT_ALLOWED_EMAIL_DOMAINS)
    except RuntimeError:          # outside an app context
        return DEFAULT_ALLOWED_EMAIL_DOMAINS


def validate_email_domain(email):
    """Raises ValidationError when the address is not on an allowed provider."""
    domains = allowed_email_domains()
    if not domains or "*" in domains:
        return
    domain = email.rsplit("@", 1)[-1].lower().strip() if "@" in email else ""
    if domain not in domains:
        pretty = ", ".join(domains[:-1]) + " or " + domains[-1] if len(domains) > 1 else domains[0]
        raise ValidationError(f"Please use a {pretty} address.")


DOC_EXT = ["pdf", "png", "jpg", "jpeg"]
IMG_EXT = ["png", "jpg", "jpeg"]


class RegisterForm(FlaskForm):
    full_name = StringField("Full Name", validators=[DataRequired(), Length(2, 120)])
    email = StringField("Email", validators=[DataRequired(), Email(), Length(max=150)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password",
                                      validators=[DataRequired(), EqualTo("password", message="Passwords must match.")])
    role = SelectField("I am a...", choices=[("founder", "Founder"), ("investor", "Investor"),
                                              ("jobseeker", "Job Seeker")], validators=[DataRequired()])

    def validate_email(self, field):
        email = (field.data or "").lower().strip()
        validate_email_domain(email)
        if User.query.filter_by(email=email).first():
            raise ValidationError("An account with this email already exists.")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])


class ForgotPasswordForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])


class ResetPasswordForm(FlaskForm):
    password = PasswordField("New Password", validators=[DataRequired(), Length(min=8)])
    confirm_password = PasswordField("Confirm Password", validators=[DataRequired(), EqualTo("password")])


class ProfileForm(FlaskForm):
    photo = FileField("Profile Photo", validators=[Optional(), FileAllowed(IMG_EXT, "Images only.")])
    phone = StringField("Phone", validators=[Optional(), Length(max=30)])
    bio = TextAreaField("Bio", validators=[Optional(), Length(max=2000)])
    location = StringField("Location", validators=[Optional(), Length(max=120)])
    education = StringField("Education", validators=[Optional(), Length(max=255)])
    experience = StringField("Experience", validators=[Optional(), Length(max=255)])
    industry = StringField("Industry", validators=[Optional(), Length(max=120)])
    skills = StringField("Skills (comma-separated)", validators=[Optional(), Length(max=500)])
    interests = StringField("Interests (comma-separated)", validators=[Optional(), Length(max=500)])


class StartupForm(FlaskForm):
    name = StringField("Startup Name", validators=[DataRequired(), Length(2, 150)])
    logo = FileField("Logo", validators=[Optional(), FileAllowed(IMG_EXT, "Images only.")])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=4000)])
    industry = StringField("Industry", validators=[DataRequired(), Length(max=120)])
    stage = SelectField("Business Stage", choices=[(s, s) for s in
                         ("Idea", "MVP", "Early Stage", "Growth", "Scaling")], validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired(), Length(max=120)])
    website = StringField("Website", validators=[Optional(), Length(max=255)])
    founded_year = IntegerField("Founded Year", validators=[Optional(), NumberRange(min=1900, max=2100)])
    business_model = StringField("Business Model", validators=[Optional(), Length(max=255)])
    team_size = IntegerField("Team Size", validators=[Optional(), NumberRange(min=1)])
    trade_license = FileField("Trade License (required)", validators=[Optional(), FileAllowed(DOC_EXT)])


class StartupDocumentForm(FlaskForm):
    doc_type = SelectField("Document Type", choices=[(d, d) for d in
                            ("Trade License", "Certificate of Incorporation", "Tax Registration", "Other")],
                            validators=[DataRequired()])
    document = FileField("File", validators=[FileRequired(), FileAllowed(DOC_EXT)])


class JobForm(FlaskForm):
    title = StringField("Job Title", validators=[DataRequired(), Length(2, 150)])
    description = TextAreaField("Description", validators=[DataRequired()])
    required_skills = StringField("Required Skills (comma-separated)", validators=[Optional(), Length(max=500)])
    experience_level = StringField("Experience Level", validators=[Optional(), Length(max=50)])
    job_type = SelectField("Job Type", choices=[(j, j) for j in
                            ("Full-time", "Part-time", "Internship", "Remote", "Contract")], validators=[DataRequired()])
    location = StringField("Location", validators=[DataRequired(), Length(max=120)])
    salary_min = IntegerField("Salary Min", validators=[Optional(), NumberRange(min=0)])
    salary_max = IntegerField("Salary Max", validators=[Optional(), NumberRange(min=0)])
    deadline = DateField("Application Deadline", validators=[Optional()])


class JobApplicationForm(FlaskForm):
    cv = FileField("CV / Resume (required)", validators=[FileRequired(), FileAllowed(["pdf", "doc", "docx"], "PDF/DOC only.")])
    cover_message = TextAreaField("Cover Message", validators=[DataRequired(), Length(max=3000)])


class InvestmentRequestForm(FlaskForm):
    message = TextAreaField("Message to founder", validators=[DataRequired(), Length(max=2000)])


class FounderFundingRequestForm(FlaskForm):
    """A founder's direct funding ask sent to a specific investor: how much
    the startup needs and what equity/share it's offered in exchange."""
    startup_id = SelectField("Which of your startups is this for?", coerce=int, validators=[DataRequired()])
    total_amount = FloatField("Investment Needed (USD)", validators=[DataRequired(), NumberRange(min=1)])
    equity_percent = FloatField("Equity / Share Offered (%)", validators=[DataRequired(), NumberRange(min=0.01, max=100)])
    message = TextAreaField("Message to investor", validators=[DataRequired(), Length(max=2000)])


class FinancialProposalForm(FlaskForm):
    total_amount = FloatField("Total Funding Requested (USD)", validators=[DataRequired(), NumberRange(min=1)])
    # Only used for a founder-initiated equity ask; left blank on the classic,
    # itemized-breakdown flow.
    equity_percent = FloatField("Equity / Share Offered (%)", validators=[Optional(), NumberRange(min=0.01, max=100)])
    notes = TextAreaField("Overall Justification", validators=[DataRequired(), Length(max=3000)],
                           description="Explain the general context for this funding ask.")
    items_json = HiddenField()  # JSON-encoded list of {reason, amount} built client-side


class ProposalDecisionForm(FlaskForm):
    decision = HiddenField(validators=[DataRequired()])  # "accept" or "revise"


class AgreementForm(FlaskForm):
    benefit_terms = TextAreaField("Agreed Benefit / Equity / Terms", validators=[DataRequired(), Length(max=3000)])
    milestone_titles = HiddenField()   # JSON-encoded list built client-side


class SignatureForm(FlaskForm):
    signed_name = StringField("Type your full legal name to sign", validators=[DataRequired(), Length(2, 150)])
    confirm = HiddenField(validators=[DataRequired(message="You must confirm you agree to the terms.")])


class MilestoneProofForm(FlaskForm):
    proof_document = FileField("Proof Document (receipt, invoice, photo, etc.)",
                                validators=[FileRequired(), FileAllowed(DOC_EXT, "PDF/Image only.")])
    description = StringField("What does this prove?", validators=[DataRequired(), Length(max=500)])


class VerificationForm(FlaskForm):
    doc_type = SelectField("ID Document Type", choices=[(d, d) for d in
                            ("National ID", "Passport", "Driving License")], validators=[Optional()])
    id_document = FileField("Upload NID / ID Card Photo", validators=[Optional(), FileAllowed(DOC_EXT, "PDF/Image only.")])
    photo_1 = HiddenField(validators=[Optional()])
    photo_2 = HiddenField(validators=[Optional()])
    photo_3 = HiddenField(validators=[Optional()])


class ReviewForm(FlaskForm):
    decision = HiddenField(validators=[DataRequired()])
    reason = TextAreaField("Reason (required if rejecting)", validators=[Optional(), Length(max=1000)])


class MessageForm(FlaskForm):
    body = TextAreaField("Message", validators=[DataRequired(), Length(max=3000)])


class ContactForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=120)])
    email = StringField("Email", validators=[DataRequired(), Email()])
    message = TextAreaField("Message", validators=[DataRequired(), Length(max=3000)])

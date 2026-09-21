import secrets
from datetime import datetime, timedelta
from flask_login import UserMixin
from extensions import db, bcrypt

# There are exactly four roles in VentureBridge. Week 1 only needs to
# authenticate and route people to the right dashboard by role — the
# role-specific features (startups, jobs, investment, verification) are
# built in Week 2 and Week 3.
ROLES = ("founder", "investor", "jobseeker", "admin")


class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, index=True)
    is_active_account = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    profile = db.relationship("Profile", backref="user", uselist=False, cascade="all,delete")

    def set_password(self, raw):
        self.password_hash = bcrypt.generate_password_hash(raw).decode("utf-8")

    def check_password(self, raw):
        return bcrypt.check_password_hash(self.password_hash, raw)

    # Flask-Login expects an is_active property
    @property
    def is_active(self):
        return self.is_active_account


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

    def completion_percent(self):
        fields = [self.photo, self.phone, self.bio, self.location,
                  self.education, self.experience, self.industry, self.skills, self.interests]
        filled = sum(1 for f in fields if f)
        return int((filled / len(fields)) * 100)


class LoginAttempt(db.Model):
    """Backs the sliding-window rate limiter on the login form."""
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), index=True)
    ip_address = db.Column(db.String(64))
    success = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


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

from datetime import datetime, timedelta
from flask import Blueprint, render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from extensions import db
from models import User, Profile, LoginAttempt, PasswordReset
from forms import (RegisterForm, LoginForm, ForgotPasswordForm, ResetPasswordForm,
                    allowed_email_domains)
from utils import log_action
from config import Config

bp = Blueprint("auth", __name__)


def _dashboard_for(user):
    return url_for("main.dashboard")


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(_dashboard_for(current_user))
    form = RegisterForm()
    if form.validate_on_submit():
        user = User(
            full_name=form.full_name.data.strip(),
            email=form.email.data.lower().strip(),
            role=form.role.data,
        )
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.flush()
        db.session.add(Profile(user_id=user.id))
        db.session.commit()

        # Regenerate session on registration to prevent fixation
        session.clear()
        login_user(user)
        session["_fresh_id"] = user.id
        log_action("register", f"New {user.role} account created", user_id=user.id)
        flash("Welcome to VentureBridge! Your account has been created.", "success")
        return redirect(_dashboard_for(user))
    return render_template("auth/register.html", form=form,
                            allowed_domains=allowed_email_domains())


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(_dashboard_for(current_user))
    form = LoginForm()
    if form.validate_on_submit():
        email = form.email.data.lower().strip()
        ip = request.remote_addr or "unknown"
        window_start = datetime.utcnow() - timedelta(minutes=Config.LOGIN_WINDOW_MINUTES)

        recent_failures = LoginAttempt.query.filter(
            LoginAttempt.email == email,
            LoginAttempt.ip_address == ip,
            LoginAttempt.success.is_(False),
            LoginAttempt.created_at >= window_start,
        ).count()

        if recent_failures >= Config.LOGIN_MAX_ATTEMPTS:
            flash(f"Too many failed login attempts. Please try again after "
                  f"{Config.LOGIN_WINDOW_MINUTES} minutes.", "danger")
            return render_template("auth/login.html", form=form)

        user = User.query.filter_by(email=email).first()
        success = bool(user and user.check_password(form.password.data))

        db.session.add(LoginAttempt(email=email, ip_address=ip, success=success))
        db.session.commit()

        if not success:
            flash("Invalid email or password.", "danger")
            log_action("login_failed", f"email={email}")
            return render_template("auth/login.html", form=form)

        if not user.is_active_account:
            flash("This account has been deactivated. Contact support.", "danger")
            return render_template("auth/login.html", form=form)

        # Regenerate session on login to prevent session fixation
        session.clear()
        login_user(user)
        session["_fresh_id"] = user.id
        log_action("login_success", user_id=user.id)
        flash(f"Welcome back, {user.full_name}!", "success")
        next_page = request.args.get("next")
        return redirect(next_page or _dashboard_for(user))
    return render_template("auth/login.html", form=form)


@bp.route("/logout")
@login_required
def logout():
    log_action("logout")
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("main.index"))


@bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    reset_link = None
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()
        if user:
            pr = PasswordReset.create_for(user.id)
            db.session.commit()
            reset_link = url_for("auth.reset_password", token=pr.token, _external=True)
            log_action("password_reset_requested", user_id=user.id)
        flash("If that email exists, a reset link has been generated below "
              "(shown directly since no email server is configured in this demo).", "info")
    return render_template("auth/forgot_password.html", form=form, reset_link=reset_link)


@bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token):
    pr = PasswordReset.query.filter_by(token=token).first()
    if not pr or pr.used or pr.expires_at < datetime.utcnow():
        flash("This reset link is invalid or has expired.", "danger")
        return redirect(url_for("auth.forgot_password"))

    form = ResetPasswordForm()
    if form.validate_on_submit():
        user = User.query.get(pr.user_id)
        user.set_password(form.password.data)
        pr.used = True
        db.session.commit()
        log_action("password_reset_completed", user_id=user.id)
        flash("Your password has been reset. Please log in.", "success")
        return redirect(url_for("auth.login"))
    return render_template("auth/reset_password.html", form=form)

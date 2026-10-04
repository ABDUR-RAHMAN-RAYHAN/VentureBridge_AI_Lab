import os
from flask import Flask, request, render_template, url_for
from config import Config
from extensions import db, login_manager, csrf, bcrypt
from models import User


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    bcrypt.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # ---- Blueprints ----
    from blueprints.auth import bp as auth_bp
    from blueprints.main import bp as main_bp
    from blueprints.startups import bp as startups_bp
    from blueprints.jobs import bp as jobs_bp
    from blueprints.investment import bp as investment_bp
    from blueprints.messaging import bp as messaging_bp
    from blueprints.admin import bp as admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(startups_bp)
    app.register_blueprint(jobs_bp)
    app.register_blueprint(investment_bp)
    app.register_blueprint(messaging_bp)
    app.register_blueprint(admin_bp)

    # ---- Security headers on every response ----
    @app.after_request
    def set_security_headers(response):
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(self), microphone=()"
        if request.is_secure:
            app.config["SESSION_COOKIE_SECURE"] = True
        return response

    # ---- Graceful error pages (no stack traces leaked) ----
    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors.html", code=403,
                                message="You don't have permission to view this page."), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors.html", code=404, message="Page not found."), 404

    @app.errorhandler(413)
    def too_large(e):
        return render_template("errors.html", code=413, message="Uploaded file is too large."), 413

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        return render_template("errors.html", code=500,
                                message="Something went wrong on our end. Please try again."), 500

    # ---- Template globals ----
    @app.context_processor
    def inject_globals():
        from datetime import datetime as dt
        from flask_login import current_user
        unread = 0
        if current_user.is_authenticated:
            from models import Notification
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return {"current_year": dt.utcnow().year, "unread_notif_count": unread}

    # ---- Cache-busting for static files (css/js) ----
    # Browsers aggressively cache static assets by URL. Without this, a
    # person who already has the site open (or visited it before) can keep
    # running an old cached style.css/main.js after we ship a fix, and the
    # page *looks* up to date (server-rendered HTML is always fresh) while
    # the actual interactive behavior silently stays on the old JS. Appending
    # each file's own last-modified time as a query string gives every
    # updated file a new URL automatically, so the browser is forced to
    # re-fetch it the moment it changes -- no manual "hard refresh" needed
    # going forward.
    @app.template_global()
    def asset_url(filename):
        path = os.path.join(app.static_folder, filename)
        try:
            v = int(os.path.getmtime(path))
        except OSError:
            v = 0
        return f"{url_for('static', filename=filename)}?v={v}"

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

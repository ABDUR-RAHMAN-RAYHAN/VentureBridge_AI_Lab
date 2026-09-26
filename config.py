import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

    # Default: SQLite (zero setup). To use MySQL instead, set DATABASE_URL, e.g.:
    # mysql+pymysql://user:password@localhost/venturebridge
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'venturebridge.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB max upload

    ALLOWED_DOC_EXTENSIONS = {"pdf", "png", "jpg", "jpeg"}
    ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg"}
    ALLOWED_MIME_TYPES = {
        "application/pdf", "image/png", "image/jpeg",
    }

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure flag is applied dynamically in app.py based on request scheme

    # Only these email providers may be used to create an account. Override
    # with e.g. ALLOWED_EMAIL_DOMAINS="gmail.com,yahoo.com,mycompany.com"
    # Set it to "*" to disable the restriction entirely.
    ALLOWED_EMAIL_DOMAINS = [
        d.strip().lower()
        for d in os.environ.get(
            "ALLOWED_EMAIL_DOMAINS",
            "gmail.com,yahoo.com,hotmail.com,outlook.com",
        ).split(",")
        if d.strip()
    ]

    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_WINDOW_MINUTES = 15

    PLATFORM_FEE_PERCENT = 2.5  # fee charged on each milestone release

    WTF_CSRF_TIME_LIMIT = None

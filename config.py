import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me-in-production")

    # Default: SQLite (zero setup). To use MySQL instead, set DATABASE_URL, e.g.:
    # mysql+pymysql://user:password@localhost/venturebridge
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL", f"sqlite:///{os.path.join(BASE_DIR, 'venturebridge_week1.db')}"
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.path.join(BASE_DIR, "static", "uploads")
    MAX_CONTENT_LENGTH = 8 * 1024 * 1024  # 8MB max upload

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    # Secure flag is applied dynamically in app.py based on request scheme

    LOGIN_MAX_ATTEMPTS = 5
    LOGIN_WINDOW_MINUTES = 15

    WTF_CSRF_TIME_LIMIT = None

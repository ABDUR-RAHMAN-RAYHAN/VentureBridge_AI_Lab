from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf import CSRFProtect
from flask_bcrypt import Bcrypt

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()
bcrypt = Bcrypt()

login_manager.login_view = "auth.login"
login_manager.login_message = "Please log in to access this page."
login_manager.login_message_category = "warning"

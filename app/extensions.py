from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from app.database import db

csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Por favor, faça login para acessar o sistema."
login_manager.login_message_category = "warning"


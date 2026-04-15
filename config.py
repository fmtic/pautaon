from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"
DEFAULT_DB_PATH = INSTANCE_DIR / "database.db"


def get_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


class Config:
    """Configuração central do sistema."""

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-key-substituir-em-producao")

    REMEMBER_COOKIE_DURATION = timedelta(hours=8)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE", get_bool("FLASK_DEBUG", False) is False and os.getenv("FLASK_ENV") == "production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
    DEBUG = get_bool("FLASK_DEBUG", APP_ENV == "development")

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD")
    ADMIN_FORCE_PASSWORD_CHANGE = get_bool("ADMIN_FORCE_PASSWORD_CHANGE", True)

    LDAP_SERVER_URI = os.getenv("LDAP_SERVER_URI")
    LDAP_USE_SSL = get_bool("LDAP_USE_SSL", True)
    LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "10"))

    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    GOOGLE_CALENDAR_DELEGATED_USER = os.getenv("GOOGLE_CALENDAR_DELEGATED_USER")
    GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


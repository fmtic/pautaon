from __future__ import annotations

import os
from datetime import timedelta
from pathlib import Path
from urllib.parse import urlparse, urlunparse

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


def normalize_database_url(database_url: str) -> str:
    parsed = urlparse(database_url)
    scheme = parsed.scheme
    username = parsed.username or ""

    if scheme == "postgresql":
        parsed = parsed._replace(scheme="postgresql+psycopg")
    elif scheme == "postgresql+psycopg2":
        parsed = parsed._replace(scheme="postgresql+psycopg")

    if username.endswith("+psycopg"):
        parsed = parsed._replace(netloc=parsed.netloc.replace(username, username.replace("+psycopg", ""), 1))

    return urlunparse(parsed)


class Config:
    """Configuração central do sistema.

    Os valores padrão abaixo são apenas para desenvolvimento local. Em produção,
    a chave secreta deve ser definida explicitamente no ambiente para evitar
    sessões e cookies inseguros.
    """

    APP_ENV = os.getenv("APP_ENV", os.getenv("FLASK_ENV", "development"))
    DEBUG = get_bool("FLASK_DEBUG", APP_ENV == "development")

    SECRET_KEY = os.getenv("SECRET_KEY")
    if not SECRET_KEY:
        if APP_ENV == "production":
            raise RuntimeError("SECRET_KEY deve ser definido no ambiente para produção.")
        SECRET_KEY = "dev-key-substituir-em-producao"

    REMEMBER_COOKIE_DURATION = timedelta(hours=8)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_COOKIE_SECURE = get_bool("SESSION_COOKIE_SECURE", get_bool("FLASK_DEBUG", False) is False and os.getenv("FLASK_ENV") == "production")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    SQLALCHEMY_DATABASE_URI = normalize_database_url(
        os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_DB_PATH}")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD")
    ADMIN_FORCE_PASSWORD_CHANGE = get_bool("ADMIN_FORCE_PASSWORD_CHANGE", True)

    LDAP_SERVER_URI = os.getenv("LDAP_SERVER_URI")
    LDAP_USE_SSL = get_bool("LDAP_USE_SSL", True)
    LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "10"))
    LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")
    LDAP_VALIDATE_CERT = get_bool("LDAP_VALIDATE_CERT", True)
    LDAP_CA_CERT_FILE = os.getenv("LDAP_CA_CERT_FILE")

    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    GOOGLE_CALENDAR_DELEGATED_USER = os.getenv("GOOGLE_CALENDAR_DELEGATED_USER")
    GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]


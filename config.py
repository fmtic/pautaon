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


def get_int(name: str, default: int) -> int:
    """Lê um inteiro do ambiente sem derrubar a aplicação por valor inválido."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    try:
        return int(value.strip())
    except ValueError:
        return default


#: Tamanho mínimo exigido para ``SECRET_KEY`` (S1-01).
SECRET_KEY_MINIMO = 32

#: Valor padrão antigo — público e, portanto, proibido.
SECRET_KEY_PROIBIDA = "dev-key-substituir-em-producao"

_COMANDO_CHAVE = 'python -c "import secrets; print(secrets.token_urlsafe(48))"'


def _resolver_app_env() -> str:
    """Ambiente da aplicação.

    ``APP_ENV`` é a chave oficial; ``FLASK_ENV`` continua aceito apenas como
    alias legado (o padrão do Flask migrou para ``FLASK_ENV`` → ``APP_ENV``).
    """
    valor = os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or "development"
    return valor.strip().lower()


def _app_env_explicito() -> str | None:
    """Valor de ``APP_ENV`` quando o operador o declarou (ou ``None``).

    Serve para separar "desenvolvimento pedido" de "desenvolvimento por
    omissão": as decisões de segurança usam o padrão seguro quando ninguém
    declarou nada. ``FLASK_ENV`` não participa (S1-09).
    """
    valor = os.getenv("APP_ENV")
    if valor is None or not valor.strip():
        return None
    return valor.strip().lower()


def _resolver_session_cookie_secure() -> bool:
    """``SESSION_COOKIE_SECURE`` seguro por padrão (S1-09).

    O padrão é ``True`` em qualquer cenário — inclusive quando ``APP_ENV`` não
    existe no ambiente. Só desliga com ``APP_ENV=development`` declarado e
    explícito, porque o servidor embarcado roda em HTTP e o navegador
    descartaria o cookie. ``SESSION_COOKIE_SECURE`` pode sobrepor nos dois
    sentidos.
    """
    padrao = _app_env_explicito() != "development"
    return get_bool("SESSION_COOKIE_SECURE", padrao)


def _resolver_debug(app_env: str) -> bool:
    """``DEBUG`` só liga com ``FLASK_DEBUG=true`` explícito **e** development.

    O padrão passa a ser ``False`` em qualquer ambiente: depurar exige ação
    deliberada do operador (S1-02).
    """
    return get_bool("FLASK_DEBUG", False) and app_env == "development"


def validar_secret_key(valor: str | None) -> str:
    """Valida a ``SECRET_KEY`` e devolve o valor aceito (S1-01).

    A aplicação não inicia sem chave, com a chave padrão histórica ou com
    menos de :data:`SECRET_KEY_MINIMO` caracteres — em qualquer ``APP_ENV``.
    """
    if not valor or not str(valor).strip():
        raise RuntimeError(
            "SECRET_KEY ausente: defina a variável de ambiente SECRET_KEY com "
            f"pelo menos {SECRET_KEY_MINIMO} caracteres. "
            f"Gere uma chave com: {_COMANDO_CHAVE}"
        )
    valor = str(valor).strip()
    if valor == SECRET_KEY_PROIBIDA or valor.startswith("dev-key"):
        raise RuntimeError(
            "SECRET_KEY inválida: o valor padrão de desenvolvimento é público e "
            "não pode ser usado (sessões e cookies poderiam ser forjados). "
            f"Gere uma chave com: {_COMANDO_CHAVE}"
        )
    if len(valor) < SECRET_KEY_MINIMO:
        raise RuntimeError(
            f"SECRET_KEY inválida: use pelo menos {SECRET_KEY_MINIMO} caracteres "
            f"(atual: {len(valor)}). Gere uma chave com: {_COMANDO_CHAVE}"
        )
    return valor


def validar_configuracao(config) -> None:
    """Recusa configurações inseguras na inicialização (S1-01 e S1-02)."""
    app_env = str(config.get("APP_ENV") or "development").strip().lower()
    validar_secret_key(config.get("SECRET_KEY"))
    if config.get("DEBUG") and app_env == "production":
        raise RuntimeError(
            "DEBUG não pode estar ligado com APP_ENV=production: o depurador do "
            "Werkzeug permite execução de código no servidor. Defina "
            "FLASK_DEBUG=false (ou remova a variável) e reinicie."
        )


def _get_database_uri() -> str:
    raw_uri = os.getenv("DATABASE_URL")
    if not raw_uri:
        return f"sqlite:///{DEFAULT_DB_PATH.as_posix()}"
    if raw_uri.startswith("sqlite:///instance/"):
        rel_file = raw_uri[len("sqlite:///instance/"):]
        return f"sqlite:///{(INSTANCE_DIR / rel_file).as_posix()}"
    if raw_uri.startswith("sqlite:///") and not raw_uri.startswith("sqlite:////") and ":" not in raw_uri[10:]:
        # Caminho relativo no Windows (ex: sqlite:///database.db)
        rel_file = raw_uri[len("sqlite:///"):]
        return f"sqlite:///{(BASE_DIR / rel_file).as_posix()}"
    return raw_uri


class Config:
    """Configuração central do sistema.

    Os valores padrão abaixo são apenas para desenvolvimento local. Em produção,
    a chave secreta deve ser definida explicitamente no ambiente para evitar
    sessões e cookies inseguros.
    """

    APP_ENV = _resolver_app_env()
    DEBUG = _resolver_debug(APP_ENV)
    TEMPLATES_AUTO_RELOAD = True

    # Sem fallback: a validação acontece em `create_app` (ver
    # `validar_configuracao`) para que configurações de teste possam definir a
    # própria chave explicitamente, sem afrouxar a regra da aplicação.
    SECRET_KEY = os.getenv("SECRET_KEY")

    REMEMBER_COOKIE_DURATION = timedelta(hours=8)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    # O deslizante do Flask renova o prazo a cada requisição; explícito para que
    # o limite absoluto (abaixo) seja o único que não pode ser prorrogado.
    SESSION_REFRESH_EACH_REQUEST = True

    # S1-06: tempo máximo de vida de uma sessão, desde o login, independente de
    # atividade. ``SESSION_ABSOLUTE_HOURS`` (horas) permite ajustar sem deploy.
    SESSION_ABSOLUTE_LIFETIME = timedelta(hours=get_int("SESSION_ABSOLUTE_HOURS", 8))

    SESSION_COOKIE_SECURE = _resolver_session_cookie_secure()
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv("SESSION_COOKIE_SAMESITE", "Lax")

    # S1-09: ``max-age`` do HSTS em segundos (padrão 180 dias). Só é enviado
    # em respostas HTTPS; ``0`` desliga o cabeçalho.
    HSTS_MAX_AGE = get_int("HSTS_MAX_AGE", 15552000)

    # S1-15: liga o ProxyFix. Só deve ser ``true`` quando existe proxy reverso
    # confiável (IIS/Apache) reescrevendo os cabeçalhos X-Forwarded-*.
    TRUSTED_PROXY = get_bool("TRUSTED_PROXY", False)

    # S1-14: CSP em Report-Only, montada a partir do inventário de hosts
    # externos (E0). Só ``cdn.jsdelivr.net`` (Chart.js e bootstrap-icons) e
    # ``calendar.google.com`` (iframe do Serviço Social) são carregados; os
    # links para sos.grael.org.br e developers.google.com são navegação e não
    # entram em nenhuma diretiva. ``unsafe-inline`` é obrigatório hoje: há
    # ``onclick``/``style`` inline em 172 pontos dos templates.
    CSP_REPORT_ONLY = get_bool("CSP_REPORT_ONLY", True)
    CSP_REPORT_ONLY_POLICY = os.getenv("CSP_REPORT_ONLY_POLICY") or (
        "default-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'; "
        "frame-src 'self' https://calendar.google.com; "
        "img-src 'self' data:; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
        "font-src 'self' data: https://cdn.jsdelivr.net"
    )

    SQLALCHEMY_DATABASE_URI = _get_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", str(INSTANCE_DIR / "uploads"))

    # AJ5-B: teto global do corpo da requisição. O pior caso legítimo é o form
    # de aluno: 7 documentos PDF (2 MB cada, validados por arquivo em
    # `registros.shared.validar_pdf`) + foto (2 MB, S1-08) + campos ≈ 16 MB,
    # com folga até 20 MB. As demais rotas de upload (modelo de certificado
    # 5 MB, anexo de atendimento 2 MB, logos 3 MB) cabem nesse valor, então o
    # limite é global — não há rota legítima que exija mais. Acima disso o
    # Werkzeug corta o stream antes do parsing (413), sem esgotar a memória.
    MAX_CONTENT_LENGTH = 20 * 1024 * 1024

    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "admin@example.com")
    ADMIN_NAME = os.getenv("ADMIN_NAME", "Administrador")
    ADMIN_DEFAULT_PASSWORD = os.getenv("ADMIN_DEFAULT_PASSWORD")
    ADMIN_FORCE_PASSWORD_CHANGE = get_bool("ADMIN_FORCE_PASSWORD_CHANGE", True)

    LDAP_ENABLED = get_bool("LDAP_ENABLED", False)
    LDAP_SERVER_URI = os.getenv("LDAP_SERVER_URI", os.getenv("LDAP_SERVER"))
    LDAP_PORT = int(os.getenv("LDAP_PORT", "636"))
    LDAP_DOMAIN = os.getenv("LDAP_DOMAIN")
    LDAP_CA_CERT_FILE = os.getenv("LDAP_CA_CERT_FILE")
    LDAP_VALIDATE_CERT = get_bool("LDAP_VALIDATE_CERT", True)
    LDAP_USE_SSL = get_bool("LDAP_USE_SSL", True)
    LDAP_CONNECT_TIMEOUT = int(os.getenv("LDAP_CONNECT_TIMEOUT", "10"))

    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID")
    GOOGLE_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    GOOGLE_CALENDAR_DELEGATED_USER = os.getenv("GOOGLE_CALENDAR_DELEGATED_USER")
    GOOGLE_CALENDAR_SCOPES = ["https://www.googleapis.com/auth/calendar"]
    # Google Chat — Notificador de pauta
    GOOGLE_CHAT_SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CHAT_SERVICE_ACCOUNT_FILE") or os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    GOOGLE_CHAT_SCOPES = [
        scope.strip()
        for scope in os.getenv("GOOGLE_CHAT_SCOPES", "https://www.googleapis.com/auth/chat.bot").split(",")
        if scope.strip()
    ]
    NOTIFICADOR_DIAS_ATRASO = get_int("NOTIFICADOR_DIAS_ATRASO", 7)
    NOTIFICADOR_DRY_RUN = get_bool("NOTIFICADOR_DRY_RUN", True)
    NOTIFICADOR_LOG_LEVEL = os.getenv("NOTIFICADOR_LOG_LEVEL", "INFO")

    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    GOOGLE_OAUTH_REDIRECT_URI = os.getenv("GOOGLE_OAUTH_REDIRECT_URI")
    GOOGLE_OAUTH_ALLOWED_DOMAINS = [
        item.strip().lower()
        for item in os.getenv("GOOGLE_OAUTH_ALLOWED_DOMAINS", "").split(",")
        if item.strip()
    ]
    GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED = get_bool("GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED", True)

    # Envio de e-mail
    # Configurações do Flask-Mail / SMTP Google Workspace
    MAIL_SERVER = os.getenv("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT = int(os.getenv("MAIL_PORT", "587"))
    MAIL_USE_TLS = get_bool("MAIL_USE_TLS", True)
    MAIL_USE_SSL = get_bool("MAIL_USE_SSL", False)
    MAIL_USERNAME = os.getenv("MAIL_USERNAME")
    MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER = os.getenv("MAIL_DEFAULT_SENDER", os.getenv("MAIL_USERNAME"))


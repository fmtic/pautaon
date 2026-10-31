from __future__ import annotations

import re
import secrets
import ssl
import string

from flask import current_app, request
from flask_login import current_user
from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError

from app.database import db
from app.models import LogAcao


def _build_ldap_bind_user(identity: str, domain: str | None = None) -> str:
    """Normaliza a identidade usada para o bind no AD.

    Aceita tanto o UPN completo (`usuario@pgrael.local`) quanto o nome simples
    (`usuario`). Quando o domínio estiver configurado, o nome simples é convertido
    automaticamente para o formato de login do AD.
    """
    identity = identity.strip()
    if not identity:
        return identity
    if "@" in identity:
        return identity
    if domain:
        return f"{identity}@{domain}"
    return identity


def _build_ldap_tls(validate: bool = True, ca_certs_file: str | None = None) -> Tls:
    """Constrói a configuração TLS para um servidor AD/LDAP seguro."""
    tls_kwargs: dict[str, object] = {
        "validate": ssl.CERT_REQUIRED if validate else ssl.CERT_NONE,
        "version": ssl.PROTOCOL_TLSv1_2,
    }
    if ca_certs_file:
        tls_kwargs["ca_certs_file"] = ca_certs_file
    return Tls(**tls_kwargs)


def authenticate_against_ldap(email: str, password: str) -> bool:
    """Autentica no LDAP apenas quando a integração estiver configurada."""
    server_uri = current_app.config.get("LDAP_SERVER_URI")
    if not server_uri:
        return False

    tls = _build_ldap_tls(
        validate=current_app.config.get("LDAP_VALIDATE_CERT", True),
        ca_certs_file=current_app.config.get("LDAP_CA_CERT_FILE"),
    )
    server = Server(
        server_uri,
        use_ssl=current_app.config.get("LDAP_USE_SSL", True),
        tls=tls,
        get_info=ALL,
        connect_timeout=current_app.config.get("LDAP_CONNECT_TIMEOUT", 10),
    )
    bind_user = _build_ldap_bind_user(
        email,
        current_app.config.get("LDAP_DOMAIN"),
    )

    try:
        connection = Connection(server, user=bind_user, password=password, auto_bind=True)
        is_bound = connection.bound
        connection.unbind()
        return is_bound
    except LDAPBindError:
        return False
    except Exception:
        current_app.logger.exception("Falha ao autenticar no LDAP.")
        return False


def register_security_log(action: str, details: str = "") -> None:
    """Persiste logs de auditoria sem interromper o fluxo da requisição."""
    try:
        log_entry = LogAcao(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            usuario_nome=(
                current_user.name if current_user.is_authenticated else "Anônimo/Sistema"
            ),
            acao=action,
            detalhes=details[:500],
            ip=request.remote_addr,
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao registrar log de segurança.")


def validate_password_strength(password: str) -> list[str]:
    """Retorna os problemas encontrados na senha informada."""
    errors: list[str] = []
    if len(password) < 8:
        errors.append("A senha deve ter no mínimo 8 caracteres.")
    if not re.search(r"[A-Z]", password):
        errors.append("A senha deve conter ao menos uma letra maiúscula.")
    if not re.search(r"[a-z]", password):
        errors.append("A senha deve conter ao menos uma letra minúscula.")
    if not re.search(r"\d", password):
        errors.append("A senha deve conter ao menos um número.")
    if not re.search(r"""[!@#$%^&*()\-_=+\[\]{};:'",.<>?/\\|`~]""", password):
        errors.append("A senha deve conter ao menos um caractere especial (!@#$%...).")
    return errors


_SAFE_SPECIAL_CHARS = "!@#$%*-_=+"


def generate_secure_random_password(length: int = 12) -> str:
    """Gera uma senha aleatória segura que atende aos requisitos de complexidade.

    Garante:
      - Ao menos 1 letra maiúscula [A-Z]
      - Ao menos 1 letra minúscula [a-z]
      - Ao menos 1 número [0-9]
      - Ao menos 1 caractere especial permitido (!@#$%*-_=+)
      - Comprimento mínimo de 8 caracteres (padrão: 12)
      - Aleatoriedade criptográfica via ``secrets``
    """
    if length < 8:
        length = 8

    # Garante os 4 requisitos obrigatórios
    chars = [
        secrets.choice(string.ascii_uppercase),
        secrets.choice(string.ascii_lowercase),
        secrets.choice(string.digits),
        secrets.choice(_SAFE_SPECIAL_CHARS),
    ]

    # Preenche os caracteres restantes com a união dos conjuntos permitidos
    todos_caracteres = string.ascii_letters + string.digits + _SAFE_SPECIAL_CHARS
    chars.extend(secrets.choice(todos_caracteres) for _ in range(length - 4))

    # Embaralha de forma criptograficamente segura
    rng = secrets.SystemRandom()
    rng.shuffle(chars)
    password = "".join(chars)

    # Asserção de integridade contra os critérios de complexidade
    assert not validate_password_strength(password), "Senha gerada não atendeu aos critérios de complexidade"
    return password

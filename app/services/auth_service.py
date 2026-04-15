from __future__ import annotations

import re
import ssl

from flask import current_app, request
from flask_login import current_user
from ldap3 import ALL, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError

from app.database import db
from app.models import LogAcao


def authenticate_against_ldap(email: str, password: str) -> bool:
    """Autentica no LDAP apenas quando a integração estiver configurada."""
    server_uri = current_app.config.get("LDAP_SERVER_URI")
    if not server_uri:
        return False

    tls = Tls(validate=ssl.CERT_NONE, version=ssl.PROTOCOL_TLSv1_2)
    server = Server(
        server_uri,
        use_ssl=current_app.config.get("LDAP_USE_SSL", True),
        tls=tls,
        get_info=ALL,
        connect_timeout=current_app.config.get("LDAP_CONNECT_TIMEOUT", 10),
    )

    try:
        connection = Connection(server, user=email, password=password, auto_bind=True)
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

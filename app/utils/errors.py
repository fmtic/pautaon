from __future__ import annotations

import logging
import traceback
from datetime import datetime
from uuid import uuid4
from typing import Optional

from flask import current_app, flash

from sqlalchemy.exc import SQLAlchemyError
from ldap3.core.exceptions import LDAPException
from werkzeug.routing import BuildError
import requests


# Category codes (two-digit) — map high-level source to short code
ERROR_CATEGORY_MAP = {
    'db': '01',        # Banco de dados / SQLAlchemy
    'api': '02',       # Chamadas externas / HTTP APIs
    'ldap': '03',      # LDAP / Active Directory
    'template': '04',  # Template / Routing / URL building
    'auth': '05',      # Autenticação e autorização
    'validation': '06',# Validações de entrada
    'unknown': '99',
}


def _categorize_exception(exc: Exception) -> str:
    """Infer the broad category code for an exception instance."""
    if isinstance(exc, SQLAlchemyError):
        return ERROR_CATEGORY_MAP['db']
    if isinstance(exc, LDAPException):
        return ERROR_CATEGORY_MAP['ldap']
    if isinstance(exc, BuildError):
        return ERROR_CATEGORY_MAP['template']
    if isinstance(exc, requests.exceptions.RequestException):
        return ERROR_CATEGORY_MAP['api']
    # Fallback to unknown
    return ERROR_CATEGORY_MAP['unknown']


def _make_error_code(category_code: str) -> str:
    """Generate a compact error code including a timestamp and short uuid.

    Example: 01-20260909T111523-3f4a1b
    """
    ts = datetime.utcnow().strftime('%Y%m%dT%H%M%S')
    suffix = uuid4().hex[:6]
    return f"{category_code}-{ts}-{suffix}"


def flash_and_log(exc: Exception, location: Optional[str] = None, hint: Optional[str] = None) -> str:
    """Log full exception and flash a sanitized message with a short error code.

    Returns the generated error code for reference.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)

    category = None
    if hint and hint.lower() in ERROR_CATEGORY_MAP:
        category = ERROR_CATEGORY_MAP[hint.lower()]
    else:
        try:
            category = _categorize_exception(exc)
        except Exception:
            category = ERROR_CATEGORY_MAP['unknown']

    code = _make_error_code(category)

    location_info = f" at {location}" if location else ""
    # Log full traceback with code for support/debugging
    logger.exception(f"[{code}]{location_info} Unhandled exception: %s", exc)

    # Flash sanitized message to user
    flash(f"Um erro foi encontrado (código {code}), contate o suporte.", "danger")

    return code


def log_error_code(exc: Exception, location: Optional[str] = None, hint: Optional[str] = None) -> str:
    """Log full exception and return the generated error code without flashing.

    Use this for API endpoints or background jobs where flashing a message
    to the user is not appropriate.
    """
    logger = current_app.logger if current_app else logging.getLogger(__name__)

    category = None
    if hint and hint.lower() in ERROR_CATEGORY_MAP:
        category = ERROR_CATEGORY_MAP[hint.lower()]
    else:
        try:
            category = _categorize_exception(exc)
        except Exception:
            category = ERROR_CATEGORY_MAP['unknown']

    code = _make_error_code(category)
    location_info = f" at {location}" if location else ""
    logger.exception(f"[{code}]{location_info} Unhandled exception: %s", exc)
    return code

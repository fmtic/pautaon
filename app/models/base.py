"""
================================================================================
BASE.PY - Imports comuns e convenções do pacote de modelos
================================================================================

Este arquivo NÃO define modelos. Ele existe para:

    1. Centralizar os imports que todos os submódulos do pacote usam
       (`db`, `get_local_now`, `datetime`, `date`, etc.).
    2. Documentar as convenções do pacote.
    3. Ser o ponto único de extensão para futuros mixins (TimestampMixin,
       SoftDeleteMixin, TenantMixin) sem quebrar os módulos existentes.

TIPOS PERSONALIZADOS
--------------------
- JSONType: JSONB em PostgreSQL (binário, indexável via GIN), JSON em SQLite.
  Use SEMPRE este tipo (não `db.JSON` puro) para colunas JSON do projeto.
================================================================================
"""

# --- Imports de biblioteca padrão -------------------------------------------------
import json
from datetime import datetime, date, timezone
from typing import List, Optional

# --- Imports de terceiros ---------------------------------------------------------
from flask_login import UserMixin
from sqlalchemy import JSON as _JSON
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import JSONB as _JSONB
from sqlalchemy.ext.hybrid import hybrid_property
from werkzeug.security import generate_password_hash, check_password_hash

# --- Imports internos da aplicação ------------------------------------------------
from app.database import db
from app.utils.timezone import get_local_now


# --- Tipos personalizados ---------------------------------------------------------
# JSONB no PostgreSQL (indexável, binário, eficiente), JSON nos demais dialetos.
# Use este tipo em QUALQUER coluna JSON do projeto.
JSONType = _JSON().with_variant(_JSONB(), 'postgresql')


__all__ = [
    # Biblioteca padrão
    'json', 'datetime', 'date', 'timezone', 'List', 'Optional',
    # Terceiros
    'UserMixin', 'select', 'hybrid_property',
    'generate_password_hash', 'check_password_hash',
    # Aplicação
    'db', 'get_local_now',
    # Tipos personalizados
    'JSONType',
]
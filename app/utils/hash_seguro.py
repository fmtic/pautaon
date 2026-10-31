"""Helper único de hashing seguro para identificadores (e-mail/IP).

Usa HMAC-SHA256 com chave derivada da SECRET_KEY via HKDF (RFC 5869) e um
rótulo de contexto fixo. Nunca armazena o identificador em claro.
"""
from __future__ import annotations

import hashlib
import hmac

from flask import current_app


# Rótulo de contexto fixo para a derivação da chave.
_CONTEXTO = b"pautaon:identificador:v1"


def _chave_derivada() -> bytes:
    """Deriva uma chave estável a partir de SECRET_KEY via HKDF (HMAC-SHA256)."""
    secret = current_app.config.get("SECRET_KEY")
    if not secret:
        raise RuntimeError("SECRET_KEY ausente para derivação de chave.")
    ikm = secret.encode("utf-8") if isinstance(secret, str) else bytes(secret)
    # HKDF-Extract
    salt = b"pautaon-hkdf-salt"
    prk = hmac.new(salt, ikm, hashlib.sha256).digest()
    # HKDF-Expand
    info = _CONTEXTO
    t = b""
    okm = b""
    for i in range(1, 2):  # 32 bytes bastam
        t = hmac.new(prk, t + info + bytes([i]), hashlib.sha256).digest()
        okm += t
    return okm[:32]


def hmac_identificador(valor: str) -> str:
    """Retorna HMAC-SHA256 hex (64 chars) do valor normalizado.

    O valor é normalizado (strip + lower) antes do hashing. A chave é derivada
    da SECRET_KEY via HKDF; mudar a SECRET_KEY muda todos os hashes.
    """
    if valor is None:
        valor = ""
    normalizado = str(valor).strip().lower()
    chave = _chave_derivada()
    return hmac.new(chave, normalizado.encode("utf-8"), hashlib.sha256).hexdigest()

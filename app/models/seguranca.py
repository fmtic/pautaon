"""SEGURANCA.PY - Controle de tentativas de login (rate limit por conta/IP)."""
from __future__ import annotations

from datetime import datetime

from app.models.base import db, get_local_now


class LoginControle(db.Model):
    __tablename__ = "login_controle"

    id = db.Column(db.Integer, primary_key=True)
    escopo = db.Column(db.String(10), nullable=False)  # 'conta' ou 'ip'
    chave_hash = db.Column(db.String(64), nullable=False)
    falhas = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    janela_inicio = db.Column(db.DateTime, nullable=True)
    bloqueado_ate = db.Column(db.DateTime, nullable=True)
    nivel = db.Column(db.Integer, nullable=False, default=0, server_default="0")
    atualizado_em = db.Column(db.DateTime, nullable=True, default=get_local_now)

    __table_args__ = (
        db.UniqueConstraint("escopo", "chave_hash", name="uq_login_controle_escopo_chave"),
    )

"""Sessão autenticada: carimbo de versão, expiração absoluta e revogação (S1-06).

O cookie do Flask assinado com a `SECRET_KEY` não pode ser invalidado por si
só: quem copia o cookie continua autenticado até ele expirar. Este módulo
resolve isso com um contador por usuário:

  * ``user.session_version`` (coluna, migration ``b5c6d7e8f9a0``) é o número
    da geração de sessões válida;
  * o login grava ``session["sv"]`` (a geração) e ``session["iat"]`` (epoch do
    início) depois de limpar a sessão anterior — sem fixação de sessão;
  * o ``user_loader`` compara ``sv`` com a coluna na linha que ele **já
    carregou** (nenhum SELECT extra) e recusa a sessão quando diverge, quando
    falta ou quando passou de ``SESSION_ABSOLUTE_LIFETIME`` desde ``iat``;
  * revogar = ``UPDATE "user" SET session_version = session_version + 1`` via
    Core (atômico, sem passar pelo ORM e sem disparar o listener de auditoria).

O limite por inatividade continua sendo o do Flask
(``PERMANENT_SESSION_LIFETIME`` + ``SESSION_REFRESH_EACH_REQUEST``); o limite
absoluto é independente dele e nunca é prorrogado por atividade.
"""

from __future__ import annotations

import time
from datetime import timedelta

from flask import current_app, g, has_request_context, session
from flask_login import login_user
from sqlalchemy import text

from app.database import db

#: Chaves da sessão (``sv`` = session version, ``iat`` = issued at).
SV = "sv"
IAT = "iat"

#: Marca em ``g`` que o ``user_loader`` recusou a sessão (e por quê).
RECUSA = "sessao_recusada"

MENSAGENS = {
    "versao": (
        "Sua sessão foi encerrada por segurança (novo acesso ou alteração no "
        "cadastro). Entre novamente."
    ),
    "expirada": (
        "Sua sessão expirou após o limite máximo de uso. Entre novamente."
    ),
}


def _agora() -> int:
    """Epoch atual — isolado para os testes congelarem o relógio."""
    return int(time.time())


def iniciar_sessao(usuario) -> None:
    """Abre a sessão autenticada descartando qualquer estado anterior.

    A limpeza antes do ``login_user`` impede fixação de sessão: o identificador
    que o visitante anônimo trazia não sobrevive ao login.
    """
    session.clear()
    login_user(usuario)
    session.permanent = True
    session[SV] = int(usuario.session_version or 0)
    session[IAT] = _agora()


def motivo_recusa(usuario) -> str | None:
    """``None`` quando a sessão vale; ``'versao'`` ou ``'expirada'`` quando não."""
    sv = session.get(SV)
    if sv is None or int(sv) != int(usuario.session_version or 0):
        return "versao"

    iat = session.get(IAT)
    if not isinstance(iat, int):
        return "versao"

    limite = current_app.config.get(
        "SESSION_ABSOLUTE_LIFETIME", timedelta(hours=8)
    )
    if _agora() - iat > limite.total_seconds():
        return "expirada"
    return None


def recusar_sessao(motivo: str) -> None:
    """Marca em ``g`` que a sessão foi recusada (lido no ``before_request``)."""
    g.setdefault(RECUSA, motivo)


def motivo_pendente() -> str | None:
    return g.pop(RECUSA, None)


def revogar_sem_commit(user_id: int) -> None:
    """Marca o incremento na transação corrente (uso em exclusão de usuário)."""
    db.session.execute(
        text(
            'UPDATE "user" SET session_version = session_version + 1 '
            "WHERE id = :id"
        ),
        {"id": int(user_id)},
    )


def revogar_sessoes(user_id: int, motivo: str, *, registrar_log: bool = True) -> int:
    """Incrementa a versão do usuário e devolve o novo valor.

    ``UPDATE`` direto: atômico (o banco resolve o ``+ 1``) e invisível ao
    ORM, então nem ``updated_by`` nem ``LogAcao`` de alteração aparecem por
    ruído. O log de segurança é um único evento "Sessões revogadas".
    """
    chave = {"id": int(user_id)}
    revogar_sem_commit(user_id)
    db.session.commit()

    nova = db.session.execute(
        text('SELECT session_version FROM "user" WHERE id = :id'), chave
    ).scalar()

    if registrar_log and has_request_context():
        from app.services.auth_service import register_security_log

        register_security_log(
            "Sessões revogadas", f"motivo={motivo} usuario_id={int(user_id)}"
        )
    return int(nova or 0)

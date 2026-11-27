"""AJ17-C — desvínculo administrativo da conta Google de um usuário.

A operação é estritamente local: limpa **somente** ``google_id`` e
``google_email`` do alvo. Não apaga usuário, não muda senha/perfil/unidade,
não toca em alunos/turmas e não revoga a sessão ativa — a pessoa continua
logada depois do desvínculo. Não há migration: as colunas já existem
(migration ``6a8df39d``).

Regra de bloqueio: sem Google, a conta precisa ter outro meio de entrada —
hash de senha local persistido ou autenticação corporativa (``is_ad_user``).
Vale também para o próprio administrador: ele não pode retirar o próprio
acesso se não sobrar senha nem domínio.

A auditoria é gravada na mesma transação (sem ``register_security_log``,
que engole exceções e faria ``rollback`` da alteração). O rótulo é novo;
os rótulos antigos de ``log_acao`` permanecem intactos (AJ4).
"""

from __future__ import annotations

from typing import NamedTuple

from flask import has_request_context, request

from app.database import db
from app.models import LogAcao, User

#: Rótulo novo e explícito da ação de desvínculo (AJ17-C).
ACAO_DESVINCULAR_GOOGLE = "Desvincular conta Google"


class DesvinculoGoogleAdminError(ValueError):
    """Recusa esperada — a mensagem é segura para aparecer no flash."""


class ResultadoDesvinculoGoogle(NamedTuple):
    usuario_id: int
    usuario_email: str
    google_email: str | None
    alterado: bool


def conta_tem_outro_acesso(usuario: User) -> bool:
    """Indica se sobra senha local utilizável ou acesso corporativo (AD).

    O login local só tenta o hash quando ``user.password`` é truthy
    (`app/auth.py`, tentativa 1); contas AD autenticam no domínio mesmo sem
    hash persistido. ``first_login`` não entra aqui: ele apenas obriga a
    trocar uma senha que já existe.
    """
    return bool(usuario.is_ad_user or usuario.password)


def desvincular_conta_google(
    usuario_id: int, *, admin_id: int
) -> ResultadoDesvinculoGoogle:
    """Limpa o vínculo Google do alvo e registra a auditoria na mesma transação.

    Idempotente: conta sem ``google_id`` e sem ``google_email`` devolve
    ``alterado=False`` sem gravação e sem log. Recusas esperadas levantam
    ``DesvinculoGoogleAdminError``; qualquer outra exceção faz ``rollback`` e
    é propagada para a rota decidir a mensagem genérica.
    """
    usuario = db.session.get(User, int(usuario_id))
    if usuario is None:
        raise DesvinculoGoogleAdminError(
            "Não foi possível localizar a conta. Atualize a página e tente novamente."
        )

    uid = int(usuario.id)
    email = usuario.email
    google_email = usuario.google_email

    if not usuario.google_id and not usuario.google_email:
        return ResultadoDesvinculoGoogle(
            usuario_id=uid,
            usuario_email=email,
            google_email=google_email,
            alterado=False,
        )

    if not conta_tem_outro_acesso(usuario):
        raise DesvinculoGoogleAdminError(
            "Não foi possível desvincular. Sem o Google, esta conta precisa "
            "de senha ou acesso corporativo. Defina uma senha antes de tentar novamente."
        )

    admin = db.session.get(User, int(admin_id))
    try:
        # Únicas colunas tocadas — nenhuma revogação de sessão.
        usuario.google_id = None
        usuario.google_email = None
        db.session.add(
            LogAcao(
                usuario_id=int(admin_id),
                usuario_nome=admin.name if admin else "Administrador",
                acao=ACAO_DESVINCULAR_GOOGLE,
                detalhes=(
                    f"admin_id={int(admin_id)} usuario_id={uid} usuario_email={email} "
                    f"google_email={google_email or ''}"
                )[:500],
                ip=request.remote_addr if has_request_context() else None,
                unidade_id=admin.unidade_id if admin else None,
            )
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return ResultadoDesvinculoGoogle(
        usuario_id=uid,
        usuario_email=email,
        google_email=google_email,
        alterado=True,
    )

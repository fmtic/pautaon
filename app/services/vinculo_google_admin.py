"""AJ24 — unificação de conta Google pendente com usuário existente (admin).

Regra de negócio: a identidade Google (``google_id``/``google_email``, colunas
já existentes em ``user`` — ver migration ``6a8df39d``) é transferida para a
conta alvo; a conta pendente é removida. **Nenhum registro é realocado**: tudo
o que pertence ao alvo continua no ``id`` dele. A pendente nunca teve acesso.

Por isso, antes de qualquer escrita, varremos via ``db.metadata`` todas as
colunas com FK para ``user.id`` e recusamos a operação se houver alguma linha
apontando para a origem. A varredura é derivada do metadata do SQLAlchemy —
não é uma lista manual de tabelas —, então novos modelos passam a ser
cobertos automaticamente.

A ordem da transação é importante: ``DELETE`` da origem + ``flush()`` antes de
gravar o ``google_id`` no alvo, porque ``user.google_id`` é UNIQUE.
"""

from __future__ import annotations

from typing import NamedTuple

from flask import has_request_context, request
from sqlalchemy import func, select

from app.database import db
from app.models import LogAcao, User
from app.models.enums import UserRole

TIPO_FK_USER_ID = ("user", "id")


class VinculoGoogleAdminError(ValueError):
    """Recusa de validação da unificação — mensagem segura para o flash."""


class ResultadoVinculoGoogle(NamedTuple):
    origem_id: int
    alvo_id: int
    google_email: str
    origem_email: str
    alvo_email: str


def _colunas_com_fk_para_user():
    """Itera (tabela, coluna) para toda FK declarada para ``user.id``."""
    for nome_tabela, tabela in db.metadata.tables.items():
        for coluna in tabela.columns:
            if any(
                (fk.column.table.name, fk.column.name) == TIPO_FK_USER_ID
                for fk in coluna.foreign_keys
            ):
                yield nome_tabela, tabela, coluna


def referencias_a_usuario(user_id: int) -> dict[str, int]:
    """``{'tabela.coluna': quantidade}`` para linhas que apontam ao usuário.

    Usada tanto na recusa da origem quanto nos testes de "sem perda de dados":
    as contagens do alvo devem ser idênticas antes e depois da unificação.
    """
    encontradas: dict[str, int] = {}
    alvo_id = int(user_id)
    for nome_tabela, tabela, coluna in _colunas_com_fk_para_user():
        total = db.session.execute(
            select(func.count()).select_from(tabela).where(coluna == alvo_id)
        ).scalar()
        if total:
            encontradas[f"{nome_tabela}.{coluna.name}"] = int(total)
    return encontradas


def _validar_origem(origem: User | None) -> None:
    if origem is None or origem.role != UserRole.PENDENTE.value:
        raise VinculoGoogleAdminError(
            "A conta de origem precisa ser um cadastro pendente."
        )
    if not origem.google_id:
        raise VinculoGoogleAdminError(
            "A conta pendente selecionada não possui identidade Google para vincular."
        )


def _validar_alvo(origem: User, alvo: User | None) -> None:
    if alvo is None:
        raise VinculoGoogleAdminError("Selecione um usuário existente válido.")
    if alvo.id == origem.id:
        raise VinculoGoogleAdminError(
            "A conta alvo não pode ser a própria conta pendente."
        )
    if not alvo.is_active or alvo.role == UserRole.PENDENTE.value:
        raise VinculoGoogleAdminError(
            "A conta alvo precisa estar ativa e não pode ser pendente."
        )
    if alvo.google_id:
        raise VinculoGoogleAdminError(
            "A conta alvo já possui vínculo com uma conta Google."
        )
    outro = db.session.execute(
        select(User).where(User.google_id == origem.google_id)
    ).scalars().first()
    if outro is not None and outro.id != origem.id:
        raise VinculoGoogleAdminError(
            "Esta identidade Google já está vinculada a outro usuário."
        )


def _registrar_log(
    admin_id: int,
    *,
    origem_id: int,
    alvo_id: int,
    origem_email: str,
    alvo_email: str,
    google_email: str,
) -> None:
    """Grava a auditoria na MESMA transação (sem commit próprio).

    Não usamos ``register_security_log`` aqui: aquele helper engole exceções e
    faz ``rollback``, o que descartaria a unificação se o INSERT do log falhasse.
    """
    admin = db.session.get(User, admin_id)
    db.session.add(
        LogAcao(
            usuario_id=admin_id,
            usuario_nome=admin.name if admin else "Administrador",
            # Rótulo já congelado pelo AJ4 (categoria "edição"): evita drift
            # na varredura AST de rótulos de log_acao.
            acao="Alteração de Cadastros",
            detalhes=(
                f"admin_id={admin_id} origem_id={origem_id} origem_email={origem_email} "
                f"alvo_id={alvo_id} alvo_email={alvo_email} google_email={google_email}"
            )[:500],
            ip=request.remote_addr if has_request_context() else None,
            unidade_id=admin.unidade_id if admin else None,
        )
    )


def vincular_conta_google_pendente(
    origem_id: int, alvo_id: int, *, admin_id: int
) -> ResultadoVinculoGoogle:
    """Vincula a identidade Google da pendente ao alvo e remove a pendente.

    Levanta ``VinculoGoogleAdminError`` para recusas esperadas e replica
    qualquer outra exceção após ``rollback`` — nenhuma escrita parcial sobrevive.
    """
    origem = db.session.get(User, int(origem_id))
    _validar_origem(origem)
    alvo = db.session.get(User, int(alvo_id))
    _validar_alvo(origem, alvo)  # type: ignore[arg-type]

    referencias = referencias_a_usuario(origem.id)  # type: ignore[union-attr]
    if referencias:
        detalhes = ", ".join(
            f"{chave}={total}" for chave, total in sorted(referencias.items())
        )
        raise VinculoGoogleAdminError(
            "A conta pendente possui registros vinculados ("
            + detalhes
            + "). A unificação foi cancelada para não perder dados; resolva essas "
            "referências antes de vincular."
        )

    # Snapshot antes do DELETE: o objeto de origem deixa de ser utilizável no
    # flush e os e-mails precisam entrar no log e no resultado.
    google_id = origem.google_id  # type: ignore[union-attr]
    google_email = origem.google_email or ""
    origem_email = origem.email  # type: ignore[union-attr]
    alvo_email = alvo.email  # type: ignore[union-attr]
    ids = (int(origem.id), int(alvo.id))  # type: ignore[union-attr]

    try:
        # UNIQUE(user.google_id): a origem precisa sair antes de gravar no alvo.
        db.session.delete(origem)
        db.session.flush()
        alvo.google_id = google_id  # type: ignore[union-attr]
        alvo.google_email = google_email
        _registrar_log(
            int(admin_id),
            origem_id=ids[0],
            alvo_id=ids[1],
            origem_email=origem_email,
            alvo_email=alvo_email,
            google_email=google_email,
        )
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise

    return ResultadoVinculoGoogle(
        origem_id=ids[0],
        alvo_id=ids[1],
        google_email=google_email,
        origem_email=origem_email,
        alvo_email=alvo_email,
    )

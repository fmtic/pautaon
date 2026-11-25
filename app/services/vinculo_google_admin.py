"""AJ24 — unificação de conta Google pendente com usuário existente (admin).

Regra de negócio: a identidade Google (``google_id``/``google_email``, colunas
já existentes em ``user`` — ver migration ``6a8df39d``) é transferida para a
conta alvo; a conta pendente é removida. Com uma única exceção (AJ24-B),
**nenhum registro é realocado**: tudo o que pertence ao alvo continua no ``id``
dele. A pendente nunca teve acesso local.

AJ24-B: ``log_acao.usuario_id`` é a única FK eximida da recusa. Toda conta
pendente nasce de um acesso Google que grava um log de acesso nessa tabela;
recusar por causa dele tornaria a unificação sempre impossível. Na mesma
transação, essas linhas são reaponteadas para o alvo (``UPDATE log_acao SET
usuario_id = alvo WHERE usuario_id = origem``) **antes** do ``DELETE``, e a
quantidade movida é registrada no ``detalhes`` do log da unificação como
``logs_reapontados=N``. Nenhuma outra FK é eximida: a varredura continua
estrita e recusa com ``tabela.coluna=contagem``.

Por isso, antes de qualquer escrita, varremos via ``db.metadata`` todas as
colunas com FK para ``user.id`` e recusamos a operação se houver alguma linha
apontando para a origem (exceto a FK de ``log_acao``, tratada acima). A
varredura é derivada do metadata do SQLAlchemy — não é uma lista manual de
tabelas —, então novos modelos passam a ser cobertos automaticamente.

A ordem da transação é importante: os logs são movidos e a origem é removida
(com ``flush()``) antes de gravar o ``google_id`` no alvo, porque
``user.google_id`` é UNIQUE.
"""

from __future__ import annotations

from typing import NamedTuple

from flask import has_request_context, request
from sqlalchemy import func, select, update

from app.database import db
from app.models import LogAcao, User
from app.models.enums import UserRole

TIPO_FK_USER_ID = ("user", "id")
#: Única FK que pode ser transferida em vez de recusar a unificação (AJ24-B).
FK_LOG_ACAO_USUARIO = "log_acao.usuario_id"


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


def _contar_fk(tabela, coluna, user_id: int) -> int:
    total = db.session.execute(
        select(func.count()).select_from(tabela).where(coluna == user_id)
    ).scalar()
    return int(total)


def referencias_a_usuario(user_id: int) -> dict[str, int]:
    """``{'tabela.coluna': quantidade}`` para linhas que apontam ao usuário.

    Usada tanto na recusa da origem quanto nos testes de "sem perda de dados":
    as contagens do alvo devem ser idênticas antes e depois da unificação.

    AJ24-B: ``log_acao.usuario_id`` não entra nesse dict — ele é reaponteado na
    unificação, não é referência impeditiva. Toda outra FK continua estrita.
    """
    encontradas: dict[str, int] = {}
    alvo_id = int(user_id)
    for nome_tabela, tabela, coluna in _colunas_com_fk_para_user():
        chave = f"{nome_tabela}.{coluna.name}"
        if chave == FK_LOG_ACAO_USUARIO:
            continue
        total = _contar_fk(tabela, coluna, alvo_id)
        if total:
            encontradas[chave] = total
    return encontradas


def logs_a_reapontar(user_id: int) -> int:
    """Quantidade de linhas de ``log_acao`` da conta a ser unificada (AJ24-B)."""
    for nome_tabela, tabela, coluna in _colunas_com_fk_para_user():
        if f"{nome_tabela}.{coluna.name}" == FK_LOG_ACAO_USUARIO:
            return _contar_fk(tabela, coluna, int(user_id))
    return 0


def _reapontar_logs(origem_id: int, alvo_id: int) -> int:
    """Move os logs da origem para o alvo na mesma transação (AJ24-B).

    ``UPDATE`` roda antes do ``DELETE`` da origem para não perder as linhas
    nem violar a FK. ``expire_all()`` evita que uma relação ``User.logs``
    carregada antes do UPDATE faça o delete anular o ``usuario_id`` recém-movido.
    """
    resultado = db.session.execute(
        update(LogAcao)
        .where(LogAcao.usuario_id == origem_id)
        .values(usuario_id=alvo_id)
        .execution_options(synchronize_session=False)
    )
    movidas = int(resultado.rowcount or 0)
    db.session.expire_all()
    return movidas


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
    logs_reapontados: int,
) -> None:
    """Grava a auditoria na MESMA transação (sem commit próprio).

    Não usamos ``register_security_log`` aqui: aquele helper engole exceções e
    faz ``rollback``, o que descartaria a unificação se o INSERT do log falhasse.

    AJ24-B: ``logs_reapontados`` preserva a rastreabilidade das linhas movidas
    da origem para o alvo. ``LogAcao`` não tem colunas específicas para esses
    dados, então seguem no ``detalhes`` no formato ``chave=valor`` do AJ24.
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
                f"alvo_id={alvo_id} alvo_email={alvo_email} google_email={google_email} "
                f"logs_reapontados={logs_reapontados}"
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
        # AJ24-B: mover os logs ANTES do DELETE, contando as linhas movidas.
        # Qualquer erro a partir daqui desfaz o UPDATE junto com o resto.
        logs_reapontados = _reapontar_logs(ids[0], ids[1])
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
            logs_reapontados=logs_reapontados,
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

"""I1 — informações do aluno visíveis ao professor da oferta.

**Uma** regra de acesso, usada pelo endpoint (`/aluno/<id>/info-professor`),
pela pauta de frequência (ícone) e pela pauta impressa: o professor vê os dados
do aluno quando existe **inscrição qualificada** — inscrição ativa, aluno ativo,
oferta ativa, turma ativa, professor efetivo da oferta igual ao usuário, turma
na unidade do usuário e período letivo **não encerrado** (`data_fim` nula ou
`>= hoje` local; período que ainda vai começar entra). Basta **uma** inscrição
qualificada.

**Professor da oferta (PARTE B, 28/10/2026):** a condição é SOMENTE
``turma_curso.professor_id == usuário`` — **sem herança** de
``turma.professor_id`` (a turma é um agregador de ofertas). Oferta sem professor
cadastrado não libera nada para perfil professor. A mesma expressão é usada pela
pauta impressa (``imprimir_pauta``) e por aqui: ``condicao_professor_da_oferta``
(SQL) e ``professor_da_oferta`` (objeto já carregado). A herança continua nos
demais leitores (listagem de turmas, painel do conselho, dashboard) — pendência
registrada no backlog.

Blocos exibidos — cada um **somente quando preenchido**:

    - ``acompanhante``: ``Aluno.acompanhante_aulas`` **com** a flag
      ``Aluno.vai_acompanhado_aulas`` — exatamente a regra da pauta impressa
      (`dados_alunos_impressao` em `registros/turmas.py`), inclusive a flag;
    - ``instrucoes``: ``PerfilDiversidade.informacoes_para_professor`` (strip),
      também igual à impressão.

Medicação e idade **não** entram aqui: medicação fica fora por decisão (ver
pendência aberta no backlog/MER) e a idade já aparece no cartão da pauta.
"""

from __future__ import annotations

from datetime import date
from typing import Iterable, Optional

from sqlalchemy import or_, select

from app.database import db
from app.models import (
    Aluno,
    Inscricao,
    PeriodoLetivo,
    PerfilDiversidade,
    Turma,
    TurmaCurso,
)
from app.utils.timezone import get_local_now

#: Chaves dos blocos devolvidos para a tela/endpoint.
BLOCO_ACOMPANHANTE = "acompanhante"
BLOCO_INSTRUCOES = "instrucoes"


def hoje_local() -> date:
    """Data de hoje no fuso do sistema (America/Sao_Paulo)."""
    return get_local_now().date()


def condicao_professor_da_oferta(user_id) -> object:
    """A ÚNICA expressão de "professor da oferta" (PARTE B): sem herança.

    Usada pela regra do I1 (endpoint + pauta) e pela guarda da pauta impressa;
    qualquer alteração de semântica deve passar por aqui.
    """
    return TurmaCurso.professor_id == user_id


def professor_da_oferta(oferta, usuario) -> bool:
    """Mesma regra de `condicao_professor_da_oferta`, para oferta já carregada.

    Existe para quem já tem a lista de ofertas em memória (a impressão resolve a
    oferta antes da guarda e não faz consulta extra). `None` nunca é
    "professor da oferta" — oferta sem professor não libera nada.
    """
    if oferta is None or usuario is None:
        return False
    usuario_id = getattr(usuario, "id", usuario)
    return oferta.professor_id is not None and oferta.professor_id == usuario_id


def _condicoes_acesso(user) -> list:
    """Condições da inscrição qualificada (item 3 das decisões do I1)."""
    return [
        Inscricao.ativo.is_(True),
        Aluno.ativo.is_(True),
        TurmaCurso.ativo.is_(True),
        Turma.ativo.is_(True),
        # Professor da oferta (PARTE B): turma_curso.professor_id == usuário,
        # SEM fallback para a turma. A unidade da turma continua obrigatória.
        condicao_professor_da_oferta(user.id),
        Turma.unidade_id == user.unidade_id,
        # Período não encerrado: sem período na turma conta como "sem data de
        # fim"; período futuro entra.
        or_(
            PeriodoLetivo.id.is_(None),
            PeriodoLetivo.data_fim.is_(None),
            PeriodoLetivo.data_fim >= hoje_local(),
        ),
    ]


def _stmt_inscricoes_qualificadas(aluno_ids: Iterable[int], user):
    """UMA consulta: inscrições qualificadas + os dois campos de conteúdo."""
    return (
        select(
            Inscricao.aluno_id,
            Aluno.vai_acompanhado_aulas,
            Aluno.acompanhante_aulas,
            PerfilDiversidade.informacoes_para_professor,
        )
        .join(Aluno, Aluno.id == Inscricao.aluno_id)
        .join(TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .outerjoin(PeriodoLetivo, PeriodoLetivo.id == Turma.periodo_letivo_id)
        .outerjoin(
            PerfilDiversidade, PerfilDiversidade.aluno_id == Aluno.id,
        )
        .where(
            Inscricao.aluno_id.in_(list(aluno_ids)),
            *_condicoes_acesso(user),
        )
    )


def blocos_preenchidos(
    acompanhante_aulas: Optional[str],
    vai_acompanhado: bool,
    informacoes_professor: Optional[str],
) -> dict:
    """Só os blocos que têm conteúdo (mesma regra de "preenchido" da impressão)."""
    blocos = {}

    acompanhante = (acompanhante_aulas or "").strip()
    if vai_acompanhado and acompanhante:
        blocos[BLOCO_ACOMPANHANTE] = acompanhante

    instrucoes = (informacoes_professor or "").strip()
    if instrucoes:
        blocos[BLOCO_INSTRUCOES] = instrucoes

    return blocos


def consultar_aluno_para_professor(aluno_id: int, user) -> tuple[bool, dict]:
    """`(tem_acesso, blocos)` do aluno para aquele professor — UMA consulta.

    Separa "sem permissão" (tem_acesso=False) de "acesso, mas nada
    preenchido" (tem_acesso=True, blocos vazio): o endpoint devolve 403 no
    primeiro e 404 no segundo.
    """
    if user is None or not getattr(user, "is_authenticated", False):
        return False, {}

    linha = db.session.execute(
        _stmt_inscricoes_qualificadas([aluno_id], user)
    ).first()
    if linha is None:
        return False, {}

    return True, blocos_preenchidos(
        linha.acompanhante_aulas,
        linha.vai_acompanhado_aulas,
        linha.informacoes_para_professor,
    )


def info_aluno_para_professor(aluno_id: int, user) -> Optional[dict]:
    """Blocos do aluno para aquele professor; `None` se sem acesso ou vazio."""
    tem_acesso, blocos = consultar_aluno_para_professor(aluno_id, user)
    if not tem_acesso or not blocos:
        return None
    return blocos


def alunos_com_info_professor(aluno_ids: Iterable[int], user) -> set[int]:
    """Ids com acesso **e** ao menos um bloco preenchido — uma única consulta.

    É o que a pauta de frequência (ícone) e a pauta impressa (linhas de
    acompanhante/instruções) precisam: nada de N+1 por aluno.
    """
    ids = [int(aluno_id) for aluno_id in aluno_ids]
    if not ids or user is None or not getattr(user, "is_authenticated", False):
        return set()

    com_info: set[int] = set()
    for aluno_id, vai_acompanhado, acompanhante, instrucoes in db.session.execute(
        _stmt_inscricoes_qualificadas(ids, user)
    ):
        if aluno_id in com_info:
            continue
        if blocos_preenchidos(acompanhante, vai_acompanhado, instrucoes):
            com_info.add(aluno_id)
    return com_info

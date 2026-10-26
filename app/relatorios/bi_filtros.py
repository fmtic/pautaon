"""Filtros compartilhados da Central de BI.

Os filtros que dependem de contexto acadêmico utilizam o vínculo:

    Aluno -> Inscricao -> TurmaCurso (oferta) / Turma

Isso preserva o histórico das inscrições e evita depender de uma coluna
unidade_id inexistente em Aluno.

ETAPA D3b.4a (decisão 1): `curso_id` e `professor_id` passam a ser resolvidos
pela OFERTA (`TurmaCurso.curso_id` / `TurmaCurso.professor_id`), sem fallback
para a turma. Consultas de inscrição juntam `TurmaCurso` por
`Inscricao.turma_curso_id` (NOT NULL desde c3d4e5f6a7b8); consultas de
linhas com oferta nullable (`Frequencia`, `RegistroAula`) usam
`cond_linha_por_oferta`, que aplica a regra (3) do responsável: a linha própria
casa pela sua oferta; linhas legadas (`turma_curso_id IS NULL`) só contam
quando a turma tem exatamente UMA oferta ativa e ela casa com o filtro.
`programa` e `turno` continuam como estão (D3b.7).
"""

from sqlalchemy import and_, case, func, or_, select

from app.models import Aluno, Inscricao, Turma, TurmaCurso
from app.services.enturmado import (  # noqa: F401 — reexporta os nomes originais
    cond_inscricao_enturmada,
    cond_oferta_efetiva,
)

# ETAPA D3b.3: `cond_oferta_efetiva` e `cond_inscricao_enturmada` foram movidos
# para o módulo neutro `app.services.enturmado` (fonte única de "enturmado").
# Este módulo os reexporta para que NENHUM chamador do BI precise mudar.


def cond_linha_por_oferta(col_turma_curso_id, col_turma_id, curso_id=None,
                          professor_id=None):
    """Condição SQL para LINHAS com `turma_curso_id` nullable (Frequencia,
    RegistroAula) que casa curso/professor pela OFERTA, com a regra do legado
    (decisão 3 da ETAPA D3b.4a):

        - linha com oferta própria → vale se a OFERTA da linha casa o filtro
          (sem exigir `TurmaCurso.ativo`: curso/professor são atributos da
          oferta, inclusive de oferta inativa em período encerrado);
        - linha legada (`turma_curso_id IS NULL`) → só vale quando a turma da
          linha tem exatamente UMA oferta ATIVA e essa oferta casa o filtro
          (regra D2, espelhando `frequencia_oferta.ofertas_unicas_ativas`);
          em turma com 2+ ofertas ativas o legado fica apenas nos totais de
          unidade/turma.
    """
    casam = []
    if curso_id is not None:
        casam.append(TurmaCurso.curso_id == curso_id)
    if professor_id is not None:
        casam.append(TurmaCurso.professor_id == professor_id)
    if not casam:
        return None

    oferta_da_linha = col_turma_curso_id.in_(
        select(TurmaCurso.id).where(*casam)
    )

    # Turmas com exatamente UMA oferta ativa, e essa oferta casando o filtro.
    # O HAVING conta só ofertas ativas (não o filtro): 2+ ofertas ativas
    # desqualifica a turma mesmo que uma delas case.
    turmas_unica_match = (
        select(TurmaCurso.turma_id)
        .where(TurmaCurso.ativo.is_(True))
        .group_by(TurmaCurso.turma_id)
        .having(
            func.count(TurmaCurso.id) == 1,
            func.max(case((and_(*casam), 1), else_=0)) == 1,
        )
    )
    legado_unico = (
        col_turma_curso_id.is_(None)
        & col_turma_id.in_(turmas_unica_match)
    )

    return or_(oferta_da_linha, legado_unico)


def aplicar_filtros_aluno(query, filtros):
    """Aplica filtros globais a uma query baseada em Aluno.

    A unidade pertence diretamente ao Aluno.
    Filtros acadêmicos são resolvidos pelo vínculo:
        Aluno -> Inscricao -> Turma (período/turma) -> TurmaCurso (curso/prof)
    """
    precisa_inscricao = any(
        filtros.get(campo)
        for campo in (
            "periodo_letivo_id",
            "curso_id",
            "turma_id",
            "professor_id",
        )
    )

    if filtros.get("unidade_id"):
        query = query.filter(Aluno.unidade_id == filtros["unidade_id"])

    if precisa_inscricao:
        query = query.join(
            Inscricao,
            Inscricao.aluno_id == Aluno.id,
        ).join(
            Turma,
            Turma.id == Inscricao.turma_id,
        ).filter(
            # Turma desativada (excluída) não entra em contagens agregadas.
            Turma.ativo.is_(True),
        )

        if filtros.get("periodo_letivo_id"):
            query = query.filter(
                Turma.periodo_letivo_id == filtros["periodo_letivo_id"]
            )

        if filtros.get("turma_id"):
            query = query.filter(Turma.id == filtros["turma_id"])

        # D3b.4a (decisão 1): curso/professor pela OFERTA da inscrição
        # (Inscricao.turma_curso_id é NOT NULL — não há fallback para a turma).
        if filtros.get("curso_id") or filtros.get("professor_id"):
            query = query.join(
                TurmaCurso,
                TurmaCurso.id == Inscricao.turma_curso_id,
            )
            if filtros.get("curso_id"):
                query = query.filter(
                    TurmaCurso.curso_id == filtros["curso_id"]
                )
            if filtros.get("professor_id"):
                query = query.filter(
                    TurmaCurso.professor_id == filtros["professor_id"]
                )

        query = query.distinct()

    if filtros.get("data_inicio"):
        query = query.filter(Aluno.created_at >= filtros["data_inicio"])

    if filtros.get("data_fim"):
        query = query.filter(Aluno.created_at <= filtros["data_fim"])

    return query


def aplicar_filtros_inscricao(query, filtros):
    """Aplica filtros globais a uma query baseada em Inscricao.

    A query deve ter Inscricao como entidade principal.
    """
    query = query.join(
        Turma,
        Turma.id == Inscricao.turma_id,
    ).filter(
        # Turma desativada (excluída) não entra em contagens agregadas.
        Turma.ativo.is_(True),
    )

    if filtros.get("unidade_id"):
        query = query.filter(Turma.unidade_id == filtros["unidade_id"])

    if filtros.get("periodo_letivo_id"):
        query = query.filter(Turma.periodo_letivo_id == filtros["periodo_letivo_id"])

    if filtros.get("turma_id"):
        query = query.filter(Turma.id == filtros["turma_id"])

    # D3b.4a (decisão 1): curso/professor pela OFERTA da inscrição.
    if filtros.get("curso_id") or filtros.get("professor_id"):
        query = query.join(
            TurmaCurso,
            TurmaCurso.id == Inscricao.turma_curso_id,
        )
        if filtros.get("curso_id"):
            query = query.filter(TurmaCurso.curso_id == filtros["curso_id"])
        if filtros.get("professor_id"):
            query = query.filter(TurmaCurso.professor_id == filtros["professor_id"])

    if filtros.get("data_inicio"):
        query = query.filter(Inscricao.data_inicio >= filtros["data_inicio"])

    if filtros.get("data_fim"):
        query = query.filter(Inscricao.data_inicio <= filtros["data_fim"])

    return query

"""Filtros compartilhados da Central de BI.

Os filtros que dependem de contexto acadêmico utilizam o vínculo:

    Aluno -> Inscricao -> Turma

Isso preserva o histórico das inscrições e evita depender de uma coluna
unidade_id inexistente em Aluno.
"""

from app.models import Aluno, Inscricao, Turma


def aplicar_filtros_aluno(query, filtros):
    """Aplica filtros globais a uma query baseada em Aluno.

    A unidade pertence diretamente ao Aluno.
    Filtros acadêmicos são resolvidos pelo vínculo:
        Aluno -> Inscricao -> Turma
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
        )

        if filtros.get("periodo_letivo_id"):
            query = query.filter(
                Turma.periodo_letivo_id == filtros["periodo_letivo_id"]
            )

        if filtros.get("curso_id"):
            query = query.filter(Turma.curso_id == filtros["curso_id"])

        if filtros.get("turma_id"):
            query = query.filter(Turma.id == filtros["turma_id"])

        if filtros.get("professor_id"):
            query = query.filter(Turma.professor_id == filtros["professor_id"])

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
    )

    if filtros.get("unidade_id"):
        query = query.filter(Turma.unidade_id == filtros["unidade_id"])

    if filtros.get("periodo_letivo_id"):
        query = query.filter(Turma.periodo_letivo_id == filtros["periodo_letivo_id"])

    if filtros.get("curso_id"):
        query = query.filter(Turma.curso_id == filtros["curso_id"])

    if filtros.get("turma_id"):
        query = query.filter(Turma.id == filtros["turma_id"])

    if filtros.get("professor_id"):
        query = query.filter(Turma.professor_id == filtros["professor_id"])

    if filtros.get("data_inicio"):
        query = query.filter(Inscricao.data_inicio >= filtros["data_inicio"])

    if filtros.get("data_fim"):
        query = query.filter(Inscricao.data_inicio <= filtros["data_fim"])

    return query

"""Filtros compartilhados da Central de BI.

Os filtros que dependem de contexto acadêmico utilizam o vínculo:

    Aluno -> Inscricao -> Turma

Isso preserva o histórico das inscrições e evita depender de uma coluna
unidade_id inexistente em Aluno.
"""

from sqlalchemy import and_, func, or_, select

from app.models import Aluno, Inscricao, Turma, TurmaCurso


def cond_inscricao_enturmada():
    """Condição SQL: a LINHA de Inscricao conta como enturmada em oferta ativa.

    Regras (decisão do responsável — Etapa J2):
        - Turma.ativo=False significa turma excluída/desativada: não entra
          em contagens agregadas.
        - Inscrição conta quando: Inscricao.ativo=True, a Turma da inscrição
          está ativa E a inscrição está ligada a uma oferta ativa — por
          `turma_curso_id` apontando para um TurmaCurso ativo da mesma turma,
          ou por `turma_curso_id` NULL numa turma com exatamente 1 oferta
          ativa (ambiguidade com 2+ ofertas ativas não conta).

    A condição referencia apenas `Inscricao`, portanto é reutilizável tanto
    em queries com JOIN em Turma quanto em queries baseadas só em Inscricao
    (EXISTS correlacionados). Chamada típica: `.filter(cond_inscricao_enturmada())`.
    """
    turma_ativa = (
        select(Turma.id)
        .where(
            Turma.id == Inscricao.turma_id,
            Turma.ativo.is_(True),
        )
        # Manter Turma no FROM do EXISTS mesmo quando a query externa já
        # junta Turma (evita auto-correlação que zeraria o FROM do subselect).
        .correlate_except(Turma)
        .exists()
    )
    oferta_apontada_ativa = (
        select(TurmaCurso.id)
        .where(
            TurmaCurso.id == Inscricao.turma_curso_id,
            TurmaCurso.ativo.is_(True),
            TurmaCurso.turma_id == Inscricao.turma_id,
        )
        .correlate_except(TurmaCurso)
        .exists()
    )
    oferta_unicica = (
        select(func.count(TurmaCurso.id))
        .where(
            TurmaCurso.turma_id == Inscricao.turma_id,
            TurmaCurso.ativo.is_(True),
        )
        .correlate_except(TurmaCurso)
        .scalar_subquery()
    )
    return and_(
        Inscricao.ativo.is_(True),
        turma_ativa,
        or_(
            oferta_apontada_ativa,
            and_(
                Inscricao.turma_curso_id.is_(None),
                oferta_unicica == 1,
            ),
        ),
    )


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
        ).filter(
            # Turma desativada (excluída) não entra em contagens agregadas.
            Turma.ativo.is_(True),
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
    ).filter(
        # Turma desativada (excluída) não entra em contagens agregadas.
        Turma.ativo.is_(True),
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

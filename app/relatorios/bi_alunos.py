"app/relatorios/bi_alunos.py"

"""Consultas dos indicadores de alunos do módulo de Relatórios e BI."""

from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
    User,
)
from app import db


def total_alunos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de alunos distintos conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_aluno

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = aplicar_filtros_aluno(Aluno.query, filtros)

    return query.count()


def alunos_ativos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de alunos ativos conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_aluno

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.filter(Aluno.ativo.is_(True))
    query = aplicar_filtros_aluno(query, filtros)

    return query.count()


def alunos_inativos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de alunos inativos conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_aluno

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.filter(Aluno.ativo.is_(False))
    query = aplicar_filtros_aluno(query, filtros)

    return query.count()


def novos_alunos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos cadastrados no período informado."""
    from .bi_filtros import aplicar_filtros_aluno

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = aplicar_filtros_aluno(Aluno.query, filtros)

    return query.count()


def alunos_pcd(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos PCD conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_aluno

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = aplicar_filtros_aluno(Aluno.query, filtros)
    alunos = query.all()

    total = 0

    for aluno in alunos:
        if aluno.perfil_diversidade is not None:
            possui_laudo = bool(aluno.perfil_diversidade.saude_laudo)
        else:
            possui_laudo = bool(
                (aluno.diversidade_json or {}).get("saude_laudo", False)
            )

        if possui_laudo:
            total += 1

    return total


def alunos_por_unidade(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos distintos agrupada por unidade."""
    from app.models import Inscricao, Unidade

    query = Aluno.query.join(Unidade, Unidade.id == Aluno.unidade_id)
    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    precisa_inscricao = any(
        valor
        for valor in (
            periodo_letivo_id,
            curso_id,
            turma_id,
            professor_id,
        )
    )

    if precisa_inscricao:
        query = query.join(Inscricao, Inscricao.aluno_id == Aluno.id).join(
            Turma, Turma.id == Inscricao.turma_id
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if turma_id:
            query = query.filter(Turma.id == turma_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Aluno.created_at >= data_inicio)

    if data_fim:
        query = query.filter(Aluno.created_at <= data_fim)

    resultados = (
        query.with_entities(
            Unidade.id,
            Unidade.nome,
            db.func.count(db.distinct(Aluno.id)),
        )
        .group_by(Unidade.id, Unidade.nome)
        .order_by(Unidade.nome)
        .all()
    )

    return [
        {
            "id": unidade_id,
            "nome": nome,
            "valor": total,
        }
        for unidade_id, nome, total in resultados
    ]


def alunos_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos distintos agrupada por curso."""
    from app.models import Inscricao

    query = (
        Aluno.query.join(Inscricao, Inscricao.aluno_id == Aluno.id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .join(Curso, Curso.id == Turma.curso_id)
    )

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Aluno.created_at >= data_inicio)

    if data_fim:
        query = query.filter(Aluno.created_at <= data_fim)

    resultados = (
        query.with_entities(
            Curso.id,
            Curso.nome,
            db.func.count(db.distinct(Aluno.id)),
        )
        .group_by(Curso.id, Curso.nome)
        .order_by(Curso.nome)
        .all()
    )

    return [
        {
            "id": curso_id,
            "nome": nome,
            "valor": total,
        }
        for curso_id, nome, total in resultados
    ]


def alunos_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos distintos agrupada por turma."""
    from app.models import Inscricao

    query = Aluno.query.join(Inscricao, Inscricao.aluno_id == Aluno.id).join(
        Turma, Turma.id == Inscricao.turma_id
    )

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Aluno.created_at >= data_inicio)

    if data_fim:
        query = query.filter(Aluno.created_at <= data_fim)

    resultados = (
        query.with_entities(
            Turma.id,
            Turma.nome,
            db.func.count(db.distinct(Aluno.id)),
        )
        .group_by(Turma.id, Turma.nome)
        .order_by(Turma.nome)
        .all()
    )

    return [
        {
            "id": turma_id,
            "nome": nome,
            "valor": total,
        }
        for turma_id, nome, total in resultados
    ]


"""
----------------------------------------
INS-001
----------------------------------------
"""


def total_inscricoes(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de inscrições conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_inscricao

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = aplicar_filtros_inscricao(Inscricao.query, filtros)

    return query.count()


"""
----------------------------------------
INS-002
----------------------------------------
"""


def inscricoes_ativas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de inscrições ativas conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_inscricao

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Inscricao.query.filter(Inscricao.ativo.is_(True))
    query = aplicar_filtros_inscricao(query, filtros)

    return query.count()


"""
----------------------------------------
INS-003
----------------------------------------
"""


def inscricoes_encerradas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de inscrições encerradas conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_inscricao

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Inscricao.query.filter(Inscricao.ativo.is_(False))
    query = aplicar_filtros_inscricao(query, filtros)

    return query.count()


"""
----------------------------------------
INS-004
----------------------------------------
"""


def novas_inscricoes(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de novas inscrições no período informado."""
    from .bi_filtros import aplicar_filtros_inscricao

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = aplicar_filtros_inscricao(Inscricao.query, filtros)

    return query.count()


"""
----------------------------------------
INS-004
----------------------------------------
"""


def inscricoes_desativadas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de inscrições desativadas conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_inscricao

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Inscricao.query.filter(Inscricao.ativo.is_(False))
    query = aplicar_filtros_inscricao(query, filtros)

    return query.count()


def inscricoes_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de inscrições agrupada por curso."""
    from app.models import Curso

    query = Inscricao.query.join(Turma, Turma.id == Inscricao.turma_id).join(
        Curso, Curso.id == Turma.curso_id
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Inscricao.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Inscricao.data_inicio <= data_fim)

    resultados = (
        query.with_entities(
            Curso.id,
            Curso.nome,
            db.func.count(Inscricao.id),
        )
        .group_by(Curso.id, Curso.nome)
        .order_by(Curso.nome)
        .all()
    )

    return [
        {
            "id": curso_id,
            "nome": nome,
            "valor": total,
        }
        for curso_id, nome, total in resultados
    ]


def total_lancamentos_frequencia(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de lançamentos de frequência conforme os filtros do BI."""
    query = Frequencia.query

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    return query.count()


def total_presencas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de presenças conforme os filtros do BI."""
    query = Frequencia.query.filter(Frequencia.conceito.in_(["A", "B", "C", "D"]))

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    return query.count()


def total_faltas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de faltas conforme os filtros do BI."""
    query = Frequencia.query.filter(Frequencia.conceito == "F")

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    return query.count()


def total_faltas_justificadas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de faltas justificadas conforme os filtros do BI."""
    query = Frequencia.query.filter(Frequencia.conceito == "J")

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    return query.count()


def frequencia_media(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média global, excluindo faltas justificadas."""
    query = Frequencia.query.filter(Frequencia.conceito.in_(["A", "B", "C", "D", "F"]))

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    total = query.count()

    if total == 0:
        return 0.0

    presentes = query.filter(Frequencia.conceito.in_(["A", "B", "C", "D"])).count()

    return round((presentes / total) * 100, 1)


"""Retorna alunos com frequência igual ou superior a 90%."""


def alunos_frequencia_90(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA

    query = Frequencia.query

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    registros = query.all()
    frequencias = {}

    for registro in registros:
        if registro.conceito not in CONCEITOS_CONTABEIS:
            continue

        frequencias.setdefault(registro.aluno_id, []).append(registro.conceito)

    total = 0

    for conceitos in frequencias.values():
        presentes = sum(1 for conceito in conceitos if conceito in CONCEITOS_PRESENCA)

        frequencia = (presentes / len(conceitos)) * 100

        if frequencia >= 90:
            total += 1

    return total


"""Retorna alunos com frequência entre 75% e 89%."""
from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA


def alunos_frequencia_75_89(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):

    query = Frequencia.query

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    registros = query.all()
    frequencias = {}

    for registro in registros:
        if registro.conceito not in CONCEITOS_CONTABEIS:
            continue

        frequencias.setdefault(
            registro.aluno_id,
            [],
        ).append(registro.conceito)

    total = 0

    for conceitos in frequencias.values():
        presentes = sum(conceito in CONCEITOS_PRESENCA for conceito in conceitos)

        frequencia = (presentes / len(conceitos)) * 100

        if 75 <= round(frequencia, 1) <= 89:
            total += 1

    return total


"""Retorna alunos com frequência inferior a 75%."""


def alunos_frequencia_inferior_75(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA

    query = Frequencia.query

    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(Frequencia.turma_id == turma_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == Frequencia.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    registros = query.all()
    frequencias = {}

    for registro in registros:
        if registro.conceito not in CONCEITOS_CONTABEIS:
            continue

        frequencias.setdefault(registro.aluno_id, []).append(registro.conceito)

    total = 0

    for conceitos in frequencias.values():
        presentes = sum(1 for conceito in conceitos if conceito in CONCEITOS_PRESENCA)

        frequencia = (presentes / len(conceitos)) * 100

        if frequencia < 75:
            total += 1

    return total


def frequencia_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média agrupada por turma."""

    query = Turma.query

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    turmas = query.order_by(Turma.nome).all()

    resultados = []

    for turma in turmas:
        frequencia = turma.freq_geral

        if data_inicio or data_fim:
            frequencia_query = Frequencia.query.filter(Frequencia.turma_id == turma.id)

            if data_inicio:
                frequencia_query = frequencia_query.filter(
                    Frequencia.data >= data_inicio
                )

            if data_fim:
                frequencia_query = frequencia_query.filter(Frequencia.data <= data_fim)

            registros = frequencia_query.all()

            contabilizaveis = [
                registro
                for registro in registros
                if registro.conceito in ["A", "B", "C", "D", "F"]
            ]

            if contabilizaveis:
                presentes = sum(
                    registro.conceito in ["A", "B", "C", "D"]
                    for registro in contabilizaveis
                )
                frequencia = round(
                    (presentes / len(contabilizaveis)) * 100,
                    1,
                )
            else:
                frequencia = 0.0

        resultados.append(
            {
                "id": turma.id,
                "nome": turma.nome,
                "valor": frequencia,
            }
        )

    return resultados


def frequencia_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média agrupada por curso."""

    query = Frequencia.query.join(Turma, Turma.id == Frequencia.turma_id).join(
        Curso, Curso.id == Turma.curso_id
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)

    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    registros = query.with_entities(
        Curso.id,
        Curso.nome,
        Frequencia.conceito,
    ).all()

    frequencias = {}

    for curso_id_resultado, nome, conceito in registros:
        if conceito not in ["A", "B", "C", "D", "F"]:
            continue

        frequencias.setdefault(
            (curso_id_resultado, nome),
            [],
        ).append(conceito)

    resultados = []

    for (curso_id_resultado, nome), conceitos in frequencias.items():
        presentes = sum(conceito in ["A", "B", "C", "D"] for conceito in conceitos)

        frequencia = round(
            (presentes / len(conceitos)) * 100,
            1,
        )

        resultados.append(
            {
                "id": curso_id_resultado,
                "nome": nome,
                "valor": frequencia,
            }
        )

    return sorted(
        resultados,
        key=lambda item: item["nome"],
    )


def total_turmas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de turmas conforme os filtros informados."""

    query = Turma.query

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    return query.count()


def turmas_ativas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de turmas ativas conforme os filtros informados."""

    query = Turma.query.filter(Turma.ativo.is_(True))

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    return query.count()


def media_alunos_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a média de alunos por turma conforme os filtros informados."""

    turmas_query = Turma.query

    if unidade_id:
        turmas_query = turmas_query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        turmas_query = turmas_query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        turmas_query = turmas_query.filter(Turma.curso_id == curso_id)

    if turma_id:
        turmas_query = turmas_query.filter(Turma.id == turma_id)

    if professor_id:
        turmas_query = turmas_query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        turmas_query = turmas_query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        turmas_query = turmas_query.filter(Turma.data_inicio <= data_fim)

    turmas = turmas_query.all()

    if not turmas:
        return 0.0

    total_alunos = 0

    for turma in turmas:
        total_alunos += Inscricao.query.filter(
            Inscricao.turma_id == turma.id,
            Inscricao.ativo.is_(True),
        ).count()

    return round(total_alunos / len(turmas), 1)


def turmas_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de turmas agrupada por curso."""

    query = Turma.query.join(
        Curso,
        Curso.id == Turma.curso_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    resultados = (
        query.with_entities(
            Curso.id,
            Curso.nome,
            db.func.count(Turma.id),
        )
        .group_by(Curso.id, Curso.nome)
        .order_by(Curso.nome)
        .all()
    )

    return [
        {
            "id": curso_id_resultado,
            "nome": nome,
            "valor": total,
        }
        for curso_id_resultado, nome, total in resultados
    ]


def turmas_por_periodo(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de turmas agrupada por período letivo."""

    query = Turma.query.join(
        PeriodoLetivo,
        PeriodoLetivo.id == Turma.periodo_letivo_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    resultados = (
        query.with_entities(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
            db.func.count(Turma.id),
        )
        .group_by(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
        )
        .order_by(PeriodoLetivo.nome)
        .all()
    )

    return [
        {
            "id": periodo_id,
            "nome": nome,
            "valor": total,
        }
        for periodo_id, nome, total in resultados
    ]


def turmas_por_unidade(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de turmas agrupada por unidade."""

    query = Turma.query.join(
        Unidade,
        Unidade.id == Turma.unidade_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    resultados = (
        query.with_entities(
            Unidade.id,
            Unidade.nome,
            db.func.count(Turma.id),
        )
        .group_by(
            Unidade.id,
            Unidade.nome,
        )
        .order_by(Unidade.nome)
        .all()
    )

    return [
        {
            "id": unidade_id_resultado,
            "nome": nome,
            "valor": total,
        }
        for unidade_id_resultado, nome, total in resultados
    ]


def turmas_por_professor(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de turmas agrupada por professor."""

    query = Turma.query.join(
        User,
        User.id == Turma.professor_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(Turma.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Turma.data_inicio <= data_fim)

    resultados = (
        query.with_entities(
            User.id,
            User.name,
            db.func.count(Turma.id),
        )
        .group_by(
            User.id,
            User.name,
        )
        .order_by(User.name)
        .all()
    )

    return [
        {
            "id": professor_id_resultado,
            "nome": nome,
            "valor": total,
        }
        for professor_id_resultado, nome, total in resultados
    ]


def total_aulas_registradas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de aulas registradas conforme os filtros informados."""

    query = RegistroAula.query

    if unidade_id:
        query = query.join(
            Turma,
            Turma.id == RegistroAula.turma_id,
        ).filter(Turma.unidade_id == unidade_id)

    if turma_id:
        query = query.filter(RegistroAula.turma_id == turma_id)

    if periodo_letivo_id or curso_id or professor_id:
        query = query.join(
            Turma,
            Turma.id == RegistroAula.turma_id,
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)

        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    return query.count()


def aulas_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por turma."""

    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    resultados = (
        query.with_entities(
            Turma.id,
            Turma.nome,
            db.func.count(RegistroAula.id),
        )
        .group_by(
            Turma.id,
            Turma.nome,
        )
        .order_by(Turma.nome)
        .all()
    )

    return [
        {
            "id": turma_id_resultado,
            "nome": nome,
            "valor": total,
        }
        for turma_id_resultado, nome, total in resultados
    ]


def aulas_por_periodo(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por período letivo."""

    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    ).join(
        PeriodoLetivo,
        PeriodoLetivo.id == Turma.periodo_letivo_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    resultados = (
        query.with_entities(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
            db.func.count(RegistroAula.id),
        )
        .group_by(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
        )
        .order_by(PeriodoLetivo.nome)
        .all()
    )

    return [
        {
            "id": periodo_id_resultado,
            "nome": nome,
            "valor": total,
        }
        for periodo_id_resultado, nome, total in resultados
    ]


def aulas_por_professor(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por professor."""

    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    ).join(
        User,
        User.id == Turma.professor_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    resultados = (
        query.with_entities(
            User.id,
            User.name,
            db.func.count(RegistroAula.id),
        )
        .group_by(User.id, User.name)
        .order_by(User.name)
        .all()
    )

    return [
        {"id": professor_id_resultado, "nome": nome, "valor": total}
        for professor_id_resultado, nome, total in resultados
    ]


def aulas_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por curso."""

    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    ).join(
        Curso,
        Curso.id == Turma.curso_id,
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    resultados = (
        query.with_entities(
            Curso.id,
            Curso.nome,
            db.func.count(RegistroAula.id),
        )
        .group_by(Curso.id, Curso.nome)
        .order_by(Curso.nome)
        .all()
    )

    return [
        {"id": curso_id_resultado, "nome": nome, "valor": total}
        for curso_id_resultado, nome, total in resultados
    ]

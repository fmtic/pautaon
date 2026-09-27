"app/relatorios/bi_alunos.py"

"""Consultas dos indicadores de alunos do módulo de Relatórios e BI."""

from app.models import Aluno, Curso, Turma, Unidade
from app import db


def total_alunos(unidade_id=None):
    """Retorna o total de alunos cadastrados."""

    query = Aluno.query

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    return query.count()


def alunos_ativos(unidade_id=None):
    """Retorna o total de alunos ativos."""

    query = Aluno.query.filter(Aluno.ativo.is_(True))

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    return query.count()


def alunos_inativos(unidade_id=None):
    """Retorna o total de alunos inativos."""

    query = Aluno.query.filter(Aluno.ativo.is_(False))

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    return query.count()


def novos_alunos(unidade_id=None, data_inicio=None, data_fim=None):
    """Retorna a quantidade de alunos cadastrados no período informado."""

    query = Aluno.query

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    if data_inicio:
        query = query.filter(Aluno.created_at >= data_inicio)

    if data_fim:
        query = query.filter(Aluno.created_at <= data_fim)

    return query.count()


def alunos_pcd(unidade_id=None):
    """Retorna a quantidade de alunos com indicação de PCD."""

    query = Aluno.query

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

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


def alunos_por_unidade():
    """Retorna a quantidade de alunos agrupada por unidade."""

    resultados = (
        Aluno.query.join(Unidade, Aluno.unidade_id == Unidade.id)
        .with_entities(
            Unidade.id,
            Unidade.nome,
            db.func.count(Aluno.id),
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


def alunos_por_curso(unidade_id=None):
    """Retorna a quantidade de alunos agrupada por curso."""

    query = Aluno.query.join(Aluno.turmas).join(Turma.curso)

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

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


def alunos_por_turma(unidade_id=None, curso_id=None):
    """Retorna a quantidade de alunos agrupada por turma."""

    query = Aluno.query.join(Aluno.turmas)

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

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


def total_inscricoes(unidade_id=None):
    """Retorna o total de inscrições cadastradas."""

    from app.models import Inscricao

    query = Inscricao.query

    if unidade_id:
        query = query.join(Inscricao.aluno).filter(Aluno.unidade_id == unidade_id)

    return query.count()


"""
----------------------------------------
INS-002
----------------------------------------
"""


def inscricoes_ativas(unidade_id=None):
    """Retorna o total de inscrições ativas."""

    from app.models import Inscricao

    query = Inscricao.query.filter(Inscricao.ativo.is_(True))

    if unidade_id:
        query = query.join(Inscricao.aluno).filter(Aluno.unidade_id == unidade_id)

    return query.count()


"""
----------------------------------------
INS-003
----------------------------------------
"""


def inscricoes_encerradas(unidade_id=None):
    """Retorna o total de inscrições encerradas."""

    from app.models import Inscricao

    query = Inscricao.query.filter(Inscricao.ativo.is_(False))

    if unidade_id:
        query = query.join(Inscricao.aluno).filter(Aluno.unidade_id == unidade_id)

    return query.count()


"""
----------------------------------------
INS-004
----------------------------------------
"""


def novas_inscricoes(unidade_id=None, data_inicio=None, data_fim=None):
    """Retorna a quantidade de inscrições iniciadas no período informado."""

    from app.models import Inscricao

    query = Inscricao.query

    if unidade_id:
        query = query.join(Inscricao.aluno).filter(Aluno.unidade_id == unidade_id)

    if data_inicio:
        query = query.filter(Inscricao.data_inicio >= data_inicio)

    if data_fim:
        query = query.filter(Inscricao.data_inicio <= data_fim)

    return query.count()


"""
----------------------------------------
INS-004
----------------------------------------
"""


def inscricoes_desativadas(unidade_id=None, data_inicio=None, data_fim=None):
    """Retorna a quantidade de inscrições desativadas no período informado."""

    from app.models import Inscricao

    query = Inscricao.query.filter(Inscricao.ativo.is_(False))

    if unidade_id:
        query = query.join(Inscricao.aluno).filter(Aluno.unidade_id == unidade_id)

    if data_inicio:
        query = query.filter(Inscricao.data_desativacao >= data_inicio)

    if data_fim:
        query = query.filter(Inscricao.data_desativacao <= data_fim)

    return query.count()

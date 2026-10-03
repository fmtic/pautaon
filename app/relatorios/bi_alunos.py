"app/relatorios/bi_alunos.py"

"""Consultas dos indicadores de alunos do módulo de Relatórios e BI."""

from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    PerfilDiversidade,
    RegistroAula,
    TemaAula,
    Turma,
    Unidade,
    User,
)
from app import db
from app.models.enums import StatusAluno
from app.services.aluno_status import (
    periodos_de_referencia_bi,
    status_alunos_para_bi,
)
from sqlalchemy import func, case, cast, Integer
from sqlalchemy.orm import selectinload
from datetime import date


def total_alunos(
    unidade_id=None,
    periodo_letivo_id=None,
    turno=None,
):
    """Conta cadastros ativos incluídos no escopo do período do BI."""
    return len(status_alunos_para_bi(
        unidade_id=unidade_id,
        periodo_letivo_id=periodo_letivo_id,
        turno=turno,
    ))


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


def alunos_sexo(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
    turno=None,
):
    """
    ALU-005: Distribuição de alunos enturmados no período por gênero/sexo.

    Prioriza o campo estruturado `PerfilDiversidade.genero` (Onda 3A).
    Para alunos sem perfil estruturado, faz fallback no JSON legado
    `Aluno.diversidade_json` via Python, garantindo cobertura total.
    A população é Novo + Renovado + Retornante no escopo filtrado.
    """
    from .bi_filtros import aplicar_filtros_aluno
    status_enturmados = {
        StatusAluno.NOVO,
        StatusAluno.RENOVADO,
        StatusAluno.RETORNANTE,
    }
    ids_enturmados = [
        aluno_id
        for aluno_id, status in status_alunos_para_bi(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
            turno=turno,
        ).items()
        if status in status_enturmados
    ]
    if not ids_enturmados:
        return []

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.filter(Aluno.id.in_(ids_enturmados)).options(
        selectinload(Aluno.perfil_diversidade)
    )
    query = aplicar_filtros_aluno(query, filtros)
    alunos = query.all()

    contagem: dict[str, int] = {}
    for aluno in alunos:
        # Fonte 1: campo estruturado PerfilDiversidade.genero (Onda 3A)
        if aluno.perfil_diversidade is not None and aluno.perfil_diversidade.genero:
            rotulo = aluno.perfil_diversidade.genero.strip() or "Não Informado"
        else:
            # Fonte 2: fallback no JSON legado diversidade_json
            genero_legado = (aluno.diversidade_json or {}).get("genero", "") or ""
            rotulo = genero_legado.strip() if genero_legado.strip() else "Não Informado"

        contagem[rotulo] = contagem.get(rotulo, 0) + 1

    dados = [
        {"id": rotulo, "nome": rotulo, "valor": total}
        for rotulo, total in contagem.items()
    ]
    dados.sort(key=lambda x: x["valor"], reverse=True)
    return dados


def alunos_por_faixa_etaria(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
    turno=None,
):
    """
    ALU-006: Distribuição de alunos enturmados no período por faixa etária.

    Calcula a idade a partir de `Aluno.data_nascimento` via Python para
    compatibilidade com SQLite (desenvolvimento) e PostgreSQL (produção).
    Alunos sem data_nascimento são agrupados em "Não Informado".
    A população é Novo + Renovado + Retornante no escopo filtrado.

    Faixas:
        - Menor de 12 anos
        - 12 a 17 anos
        - 18 a 24 anos
        - 25 a 39 anos
        - 40 a 59 anos
        - 60 anos ou mais
        - Não Informado
    """
    from .bi_filtros import aplicar_filtros_aluno

    # Ordem de exibição das faixas
    ORDEM_FAIXAS = [
        "Menor de 12 anos",
        "12 a 17 anos",
        "18 a 24 anos",
        "25 a 39 anos",
        "40 a 59 anos",
        "60 anos ou mais",
        "Não Informado",
    ]

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    status_enturmados = {
        StatusAluno.NOVO,
        StatusAluno.RENOVADO,
        StatusAluno.RETORNANTE,
    }
    ids_enturmados = [
        aluno_id
        for aluno_id, status in status_alunos_para_bi(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
            turno=turno,
        ).items()
        if status in status_enturmados
    ]
    if not ids_enturmados:
        return []

    query = Aluno.query.filter(Aluno.id.in_(ids_enturmados))
    query = aplicar_filtros_aluno(query, filtros)
    alunos = query.all()

    hoje = date.today()
    contagem: dict[str, int] = {faixa: 0 for faixa in ORDEM_FAIXAS}

    for aluno in alunos:
        if not aluno.data_nascimento:
            contagem["Não Informado"] += 1
            continue

        dn = aluno.data_nascimento
        idade = hoje.year - dn.year - (
            (hoje.month, hoje.day) < (dn.month, dn.day)
        )

        if idade < 12:
            contagem["Menor de 12 anos"] += 1
        elif idade <= 17:
            contagem["12 a 17 anos"] += 1
        elif idade <= 24:
            contagem["18 a 24 anos"] += 1
        elif idade <= 39:
            contagem["25 a 39 anos"] += 1
        elif idade <= 59:
            contagem["40 a 59 anos"] += 1
        else:
            contagem["60 anos ou mais"] += 1

    # Retorna na ordem definida, omitindo faixas com 0 alunos
    dados = [
        {"id": faixa, "nome": faixa, "valor": contagem[faixa]}
        for faixa in ORDEM_FAIXAS
        if contagem[faixa] > 0
    ]
    return dados


def novos_alunos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Conta cadastros criados no intervalo, sem exigir enturmação."""
    from app.services.aluno_status import periodos_de_referencia_bi

    if periodo_letivo_id is not None or (data_inicio is None and data_fim is None):
        periodos = periodos_de_referencia_bi(
            periodo_letivo_id=periodo_letivo_id,
            unidade_id=unidade_id,
            data_ref=date.today(),
        )
        intervalos = [
            (
                periodo.unidade_id,
                data_inicio or periodo.data_inicio,
                data_fim or periodo.data_fim,
            )
            for periodo in periodos
        ]
        if not intervalos:
            return 0

        condicoes = [
            db.and_(
                Aluno.unidade_id == unidade_id_intervalo,
                func.date(Aluno.created_at) >= inicio.isoformat(),
                func.date(Aluno.created_at) <= fim.isoformat(),
            )
            for unidade_id_intervalo, inicio, fim in intervalos
            if inicio <= fim
        ]
        return Aluno.query.filter(db.or_(*condicoes)).count() if condicoes else 0

    query = Aluno.query
    if unidade_id is not None:
        query = query.filter(Aluno.unidade_id == unidade_id)
    if data_inicio is not None:
        query = query.filter(func.date(Aluno.created_at) >= str(data_inicio))
    if data_fim is not None:
        query = query.filter(func.date(Aluno.created_at) <= str(data_fim))
    return query.count()


def alunos_pcd(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
    turno=None,
):
    """Conta alunos enturmados com PCD conforme os filtros do BI."""
    from .bi_filtros import aplicar_filtros_aluno

    status_enturmados = {
        StatusAluno.NOVO,
        StatusAluno.RENOVADO,
        StatusAluno.RETORNANTE,
    }
    ids_enturmados = [
        aluno_id
        for aluno_id, status in status_alunos_para_bi(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
            turno=turno,
        ).items()
        if status in status_enturmados
    ]
    if not ids_enturmados:
        return 0

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.filter(Aluno.id.in_(ids_enturmados)).options(
        selectinload(Aluno.perfil_diversidade)
    )
    query = aplicar_filtros_aluno(query, filtros)
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
    turno=None,
):
    """Conta alunos enturmados distintos por curso no escopo de P/D."""
    from app.models import Inscricao
    status_enturmados = {
        StatusAluno.NOVO,
        StatusAluno.RENOVADO,
        StatusAluno.RETORNANTE,
    }
    periodos = periodos_de_referencia_bi(
        periodo_letivo_id=periodo_letivo_id,
        unidade_id=unidade_id,
        data_ref=date.today(),
    )
    if not periodos:
        return []

    ids_enturmados = [
        aluno_id
        for aluno_id, status in status_alunos_para_bi(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
            turno=turno,
        ).items()
        if status in status_enturmados
    ]
    if not ids_enturmados:
        return []

    query = (
        Aluno.query.filter(Aluno.id.in_(ids_enturmados))
        .join(Inscricao, Inscricao.aluno_id == Aluno.id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .join(Curso, Curso.id == Turma.curso_id)
        .filter(
            Inscricao.ativo.is_(True),
            Turma.periodo_letivo_id.in_([periodo.id for periodo in periodos]),
        )
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
    turno=None,
):
    """Conta alunos enturmados distintos por turma no escopo de P/D."""
    from app.models import Inscricao
    status_enturmados = {
        StatusAluno.NOVO,
        StatusAluno.RENOVADO,
        StatusAluno.RETORNANTE,
    }
    periodos = periodos_de_referencia_bi(
        periodo_letivo_id=periodo_letivo_id,
        unidade_id=unidade_id,
        data_ref=date.today(),
    )
    if not periodos:
        return []

    ids_enturmados = [
        aluno_id
        for aluno_id, status in status_alunos_para_bi(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
            turno=turno,
        ).items()
        if status in status_enturmados
    ]
    if not ids_enturmados:
        return []

    query = (
        Aluno.query.filter(Aluno.id.in_(ids_enturmados))
        .join(Inscricao, Inscricao.aluno_id == Aluno.id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .filter(
            Inscricao.ativo.is_(True),
            Turma.periodo_letivo_id.in_([periodo.id for periodo in periodos]),
        )
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


def aulas_por_tema(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por tema."""

    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    ).join(
        TemaAula,
        TemaAula.id == RegistroAula.tema_id,
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
            TemaAula.id,
            TemaAula.titulo,
            func.count(RegistroAula.id),
        )
        .group_by(TemaAula.id, TemaAula.titulo)
        .order_by(TemaAula.titulo)
        .all()
    )

    return [
        {"id": tema_id, "nome": titulo, "valor": total}
        for tema_id, titulo, total in resultados
    ]


def aulas_por_unidade(
    unidade_id=None,
    periodo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    query = (
        db.session.query(
            Unidade.id,
            Unidade.nome,
            func.count(RegistroAula.id),
        )
        .join(Turma, Turma.unidade_id == Unidade.id)
        .join(RegistroAula, RegistroAula.turma_id == Turma.id)
    )

    if unidade_id:
        query = query.filter(Unidade.id == unidade_id)

    if periodo_id:
        query = query.filter(RegistroAula.periodo_id == periodo_id)

    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if professor_id:
        query = query.filter(RegistroAula.professor_id == professor_id)

    if data_inicio:
        query = query.filter(RegistroAula.data >= data_inicio)

    if data_fim:
        query = query.filter(RegistroAula.data <= data_fim)

    resultados = query.group_by(Unidade.id, Unidade.nome).order_by(Unidade.nome).all()

    return [
        {
            "id": unidade_id,
            "nome": nome,
            "valor": valor,
        }
        for unidade_id, nome, valor in resultados
    ]


def aulas_por_dia(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por data."""

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
            RegistroAula.data,
            func.count(RegistroAula.id),
        )
        .group_by(RegistroAula.data)
        .order_by(RegistroAula.data)
        .all()
    )

    return [
        {"id": data, "nome": str(data), "valor": total} for data, total in resultados
    ]


def alunos_por_faixa_renda(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos distintos agrupada por faixa de renda familiar."""
    from .bi_filtros import aplicar_filtros_aluno
    from app.models import PerfilSocioeconomico

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.outerjoin(PerfilSocioeconomico)
    query = aplicar_filtros_aluno(query, filtros)

    resultados = (
        query.with_entities(
            Aluno.id,
            PerfilSocioeconomico.renda_familiar,
        )
        .distinct()
        .all()
    )

    faixas = {
        "nao_informado": {"nome": "Não informado", "valor": 0},
        "ate_1500": {"nome": "Até R$ 1.500,00", "valor": 0},
        "1500_3000": {"nome": "De R$ 1.500,01 a R$ 3.000,00", "valor": 0},
        "3000_6000": {"nome": "De R$ 3.000,01 a R$ 6.000,00", "valor": 0},
        "acima_6000": {"nome": "Acima de R$ 6.000,00", "valor": 0},
    }

    for _, renda in resultados:
        if renda is None:
            faixas["nao_informado"]["valor"] += 1
        elif renda <= 1500:
            faixas["ate_1500"]["valor"] += 1
        elif renda <= 3000:
            faixas["1500_3000"]["valor"] += 1
        elif renda <= 6000:
            faixas["3000_6000"]["valor"] += 1
        else:
            faixas["acima_6000"]["valor"] += 1

    return [
        {"id": k, "nome": v["nome"], "valor": v["valor"]} for k, v in faixas.items()
    ]


def alunos_beneficiarios_programas_sociais(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos beneficiários de programas sociais."""
    from .bi_filtros import aplicar_filtros_aluno
    from app.models import PerfilSocioeconomico

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.outerjoin(PerfilSocioeconomico)
    query = aplicar_filtros_aluno(query, filtros)
    query = query.filter(PerfilSocioeconomico.beneficio_social_status == "Sim")

    return query.count()


def alunos_por_tipo_deficiencia(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos com laudo agrupada por tipo de deficiência."""
    from .bi_filtros import aplicar_filtros_aluno
    from app.models import PerfilDiversidade

    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    query = Aluno.query.outerjoin(PerfilDiversidade)
    query = aplicar_filtros_aluno(query, filtros)
    query = query.filter(PerfilDiversidade.saude_laudo.is_(True))

    resultados = (
        query.with_entities(
            PerfilDiversidade.tipo_deficiencia,
            db.func.count(db.distinct(Aluno.id)),
        )
        .group_by(PerfilDiversidade.tipo_deficiencia)
        .order_by(PerfilDiversidade.tipo_deficiencia)
        .all()
    )

    return [
        {
            "id": tipo or "nao_informado",
            "nome": tipo or "Não informado",
            "valor": total,
        }
        for tipo, total in resultados
    ]


def total_atendimentos(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de atendimentos conforme os filtros do BI."""
    from app.models import Atendimento, Aluno, Inscricao, Turma

    query = Atendimento.query

    if unidade_id:
        query = query.filter(Atendimento.unidade_id == unidade_id)

    if data_inicio:
        query = query.filter(Atendimento.data_atendimento >= data_inicio)

    if data_fim:
        query = query.filter(Atendimento.data_atendimento <= data_fim)

    if periodo_letivo_id or curso_id or turma_id or professor_id:
        query = (
            query.join(Aluno, Aluno.id == Atendimento.aluno_id)
            .join(Inscricao, Inscricao.aluno_id == Aluno.id)
            .join(Turma, Turma.id == Inscricao.turma_id)
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

        query = query.distinct()

    return query.count()


def frequencia_critica_por_vulnerabilidade(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de alunos com frequência < 75% agrupada por vulnerabilidade social."""
    from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA
    from app.models import PerfilSocioeconomico, Turma, Frequencia

    query = Frequencia.query
    if unidade_id:
        query = query.filter(Frequencia.unidade_id == unidade_id)
    if data_inicio:
        query = query.filter(Frequencia.data >= data_inicio)
    if data_fim:
        query = query.filter(Frequencia.data <= data_fim)

    if periodo_letivo_id or curso_id or turma_id or professor_id:
        query = query.join(Turma, Turma.id == Frequencia.turma_id)
        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    registros = query.all()
    frequencias = {}
    for reg in registros:
        if reg.conceito not in CONCEITOS_CONTABEIS:
            continue
        frequencias.setdefault(reg.aluno_id, []).append(reg.conceito)

    alunos_criticos_ids = []
    for aluno_id, conceitos in frequencias.items():
        presentes = sum(1 for c in conceitos if c in CONCEITOS_PRESENCA)
        freq = (presentes / len(conceitos)) * 100
        if freq < 75:
            alunos_criticos_ids.append(aluno_id)

    if not alunos_criticos_ids:
        return [
            {"id": "sim", "nome": "Vulnerável (Sim)", "valor": 0},
            {"id": "nao", "nome": "Não Vulnerável (Não)", "valor": 0},
        ]

    perfis = PerfilSocioeconomico.query.filter(
        PerfilSocioeconomico.aluno_id.in_(alunos_criticos_ids)
    ).all()
    mapa_vuln = {p.aluno_id: p.vulnerabilidade_social for p in perfis}

    vulneravel_count = sum(
        1 for aid in alunos_criticos_ids if mapa_vuln.get(aid, False)
    )
    nao_vulneravel_count = len(alunos_criticos_ids) - vulneravel_count

    return [
        {"id": "sim", "nome": "Vulnerável (Sim)", "valor": vulneravel_count},
        {"id": "nao", "nome": "Não Vulnerável (Não)", "valor": nao_vulneravel_count},
    ]


def alunos_raca_conselho(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a distribuição de alunos por raça/cor avaliados no Conselho de Classe."""
    from app.models import ConselhoClasse, PerfilDiversidade, Turma

    query = ConselhoClasse.query.join(
        PerfilDiversidade, PerfilDiversidade.aluno_id == ConselhoClasse.aluno_id
    )
    if unidade_id:
        query = query.filter(ConselhoClasse.unidade_id == unidade_id)

    if periodo_letivo_id or curso_id or turma_id or professor_id:
        query = query.join(Turma, Turma.id == ConselhoClasse.turma_id)
        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    resultados = (
        query.with_entities(
            PerfilDiversidade.raca_cor,
            db.func.count(db.distinct(ConselhoClasse.aluno_id)),
        )
        .group_by(PerfilDiversidade.raca_cor)
        .order_by(PerfilDiversidade.raca_cor)
        .all()
    )

    return [
        {
            "id": raca or "nao_informado",
            "nome": raca or "Não informado",
            "valor": total,
        }
        for raca, total in resultados
    ]


def sem_internet_por_bairro_zona(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna alunos sem acesso à internet agrupados por zona e bairro."""
    from .bi_filtros import aplicar_filtros_aluno
    from app.models import EnderecoAluno

    query = Aluno.query.join(EnderecoAluno, EnderecoAluno.aluno_id == Aluno.id)
    query = query.filter(EnderecoAluno.possui_acesso_internet.is_(False))
    query = aplicar_filtros_aluno(
        query,
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
    )

    resultados = (
        query.with_entities(
            EnderecoAluno.zona,
            EnderecoAluno.bairro,
            db.func.count(db.distinct(Aluno.id)),
        )
        .group_by(EnderecoAluno.zona, EnderecoAluno.bairro)
        .order_by(EnderecoAluno.zona, EnderecoAluno.bairro)
        .all()
    )

    return [
        {
            "id": f"{zona or 'Indefinida'}_{bairro or 'Indefinido'}",
            "nome": f"{zona or 'Zona N/I'} - {bairro or 'Bairro N/I'}",
            "valor": total,
        }
        for zona, bairro, total in resultados
    ]


def transferencias_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de transferências agrupada por curso de origem."""
    from app.models import Transferencia, Turma, Curso

    query = Transferencia.query.join(
        Turma, Turma.id == Transferencia.turma_origem_id
    ).join(Curso, Curso.id == Turma.curso_id)

    if unidade_id:
        query = query.filter(Transferencia.unidade_id == unidade_id)
    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
    if curso_id:
        query = query.filter(Turma.curso_id == curso_id)
    if turma_id:
        query = query.filter(Turma.id == turma_id)
    if professor_id:
        query = query.filter(Turma.professor_id == professor_id)
    if data_inicio:
        query = query.filter(Transferencia.data_transferencia >= data_inicio)
    if data_fim:
        query = query.filter(Transferencia.data_transferencia <= data_fim)

    resultados = (
        query.with_entities(
            Curso.id,
            Curso.nome,
            db.func.count(Transferencia.id),
        )
        .group_by(Curso.id, Curso.nome)
        .order_by(Curso.nome)
        .all()
    )

    return [
        {
            "id": cid,
            "nome": nome,
            "valor": total,
        }
        for cid, nome, total in resultados
    ]


def desempenho_conselho_por_renda(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o desempenho no Conselho de Classe agrupado por faixa de renda familiar."""
    from app.models import ConselhoClasse, PerfilSocioeconomico, Turma

    query = ConselhoClasse.query.join(
        PerfilSocioeconomico, PerfilSocioeconomico.aluno_id == ConselhoClasse.aluno_id
    )

    if unidade_id:
        query = query.filter(ConselhoClasse.unidade_id == unidade_id)

    if periodo_letivo_id or curso_id or turma_id or professor_id:
        query = query.join(Turma, Turma.id == ConselhoClasse.turma_id)
        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
        if curso_id:
            query = query.filter(Turma.curso_id == curso_id)
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        if professor_id:
            query = query.filter(Turma.professor_id == professor_id)

    resultados = query.with_entities(
        ConselhoClasse.situacao_final,
        PerfilSocioeconomico.renda_familiar,
    ).all()

    faixas = {
        "ate_1500": {"nome": "Até R$ 1.500,00", "aprovados": 0, "outros": 0},
        "1500_3000": {
            "nome": "De R$ 1.500,01 a R$ 3.000,00",
            "aprovados": 0,
            "outros": 0,
        },
        "acima_3000": {"nome": "Acima de R$ 3.000,00", "aprovados": 0, "outros": 0},
        "nao_informado": {"nome": "Não informado", "aprovados": 0, "outros": 0},
    }

    for sit, renda in resultados:
        if renda is None:
            chave_renda = "nao_informado"
        elif renda <= 1500:
            chave_renda = "ate_1500"
        elif renda <= 3000:
            chave_renda = "1500_3000"
        else:
            chave_renda = "acima_3000"

        if sit and "APROVADO" in str(sit).upper():
            faixas[chave_renda]["aprovados"] += 1
        else:
            faixas[chave_renda]["outros"] += 1

    return [
        {
            "id": k,
            "nome": f"{v['nome']} (Aprovados: {v['aprovados']}, Outros: {v['outros']})",
            "valor": v["aprovados"] + v["outros"],
        }
        for k, v in faixas.items()
    ]


def _contar_status_aluno(
    status_alvo,
    unidade_id=None,
    periodo_letivo_id=None,
    turno=None,
):
    status = status_alunos_para_bi(
        unidade_id=unidade_id,
        periodo_letivo_id=periodo_letivo_id,
        turno=turno,
    )
    return sum(valor in status_alvo for valor in status.values())


def alunos_enturmados(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.NOVO, StatusAluno.RENOVADO, StatusAluno.RETORNANTE},
        unidade_id,
        periodo_letivo_id,
        turno,
    )


def alunos_nao_enturmados(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {
            StatusAluno.EM_JANELA,
            StatusAluno.NAO_RENOVADO,
            StatusAluno.DESENTURMADO,
            StatusAluno.OUTROS,
        },
        unidade_id,
        periodo_letivo_id,
        turno,
    )


def alunos_novos_no_periodo(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.NOVO}, unidade_id, periodo_letivo_id, turno
    )


def alunos_renovados(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.RENOVADO}, unidade_id, periodo_letivo_id, turno
    )


def alunos_retornantes(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.RETORNANTE}, unidade_id, periodo_letivo_id, turno
    )


def alunos_nao_renovados(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.NAO_RENOVADO}, unidade_id, periodo_letivo_id, turno
    )


def alunos_em_janela(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.EM_JANELA}, unidade_id, periodo_letivo_id, turno
    )


def alunos_desenturmados(unidade_id=None, periodo_letivo_id=None, turno=None):
    return _contar_status_aluno(
        {StatusAluno.DESENTURMADO}, unidade_id, periodo_letivo_id, turno
    )

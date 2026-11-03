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
    TurmaCurso,
    Unidade,
    User,
)
from app import db
from app.models.enums import StatusAluno
from app.services.aluno_status import (
    periodos_de_referencia_bi,
    status_alunos_para_bi,
)
from app.services.enturmado import (
    cond_aluno_no_escopo_unidade,
    unidade_efetiva_aluno,
)
from app.relatorios.bi_filtros import (
    cond_inscricao_enturmada,
    cond_linha_por_oferta,
)
# ETAPA D3b.4a (decisão 4): percentual, faixa e agregação em lote vêm do
# serviço único `frequencia_oferta`; curso/professor de linhas com oferta
# nullable são resolvidos por `cond_linha_por_oferta` (decisões 1 e 3).
from app.services.frequencia_oferta import (
    agregar_por_oferta,
    agregar_por_turma,
    faixa as faixa_de,
    ofertas_unicas_ativas,
    percentual,
)
from sqlalchemy import func, and_, or_, select
from sqlalchemy.orm import selectinload
from datetime import date


# ---------------------------------------------------------------------------
# ETAPA D3b.4a — helpers de linha (Frequencia/RegistroAula) por OFERTA
# ---------------------------------------------------------------------------

# Listas literais preservam exatamente os conceitos usados pelo código anterior
# (presença A-D; contáveis A-D + F; J fora do percentual).
_CONCEITOS_PRESENCA = ["A", "B", "C", "D"]
_CONCEITOS_CONTABEIS = ["A", "B", "C", "D", "F"]


def _base_frequencia(filtros, conceitos=None):
    """Query base de linhas `Frequencia` com os filtros do BI por OFERTA.

    unidade/turma/datas são colunas diretas; período e o critério de turma
    ativa vêm do join ÚNICO em `Turma` (A1: turma excluída logicamente,
    `Turma.ativo = False`, não entra em nenhuma contagem — mesmo critério de
    Resumo, FRE-009/FRE-010 e painel pedagógico); curso/professor casam pela
    OFERTA da linha (`cond_linha_por_oferta`) — legado só entra em turma de
    oferta única ativa (regra D2 da decisão 3).
    """
    query = Frequencia.query.join(
        Turma,
        Turma.id == Frequencia.turma_id,
    ).filter(Turma.ativo.is_(True))

    if filtros.get("unidade_id"):
        query = query.filter(Turma.unidade_id == filtros["unidade_id"])

    if filtros.get("turma_id"):
        query = query.filter(Frequencia.turma_id == filtros["turma_id"])

    if filtros.get("data_inicio"):
        query = query.filter(Frequencia.data >= filtros["data_inicio"])

    if filtros.get("data_fim"):
        query = query.filter(Frequencia.data <= filtros["data_fim"])

    if filtros.get("periodo_letivo_id"):
        query = query.filter(Turma.periodo_letivo_id == filtros["periodo_letivo_id"])

    cond = cond_linha_por_oferta(
        Frequencia.turma_curso_id,
        Frequencia.turma_id,
        curso_id=filtros.get("curso_id"),
        professor_id=filtros.get("professor_id"),
    )
    if cond is not None:
        query = query.filter(cond)

    if conceitos is not None:
        query = query.filter(Frequencia.conceito.in_(conceitos))

    return query


def _base_registro_aula(filtros):
    """Query base de `RegistroAula` com join ÚNICO em Turma (corrige o join
    duplo caracterizado em D3b.4a: unidade + curso/prof/período geravam
    `ambiguous column name: turma.unidade_id` — 500 na rota), filtros de
    curso/professor pela OFERTA via `cond_linha_por_oferta` e o critério de
    turma ativa dos demais agregados (A1: `Turma.ativo = False` fora).
    """
    query = RegistroAula.query.join(
        Turma,
        Turma.id == RegistroAula.turma_id,
    ).filter(Turma.ativo.is_(True))

    if filtros.get("unidade_id"):
        query = query.filter(Turma.unidade_id == filtros["unidade_id"])

    if filtros.get("periodo_letivo_id"):
        query = query.filter(Turma.periodo_letivo_id == filtros["periodo_letivo_id"])

    if filtros.get("turma_id"):
        query = query.filter(Turma.id == filtros["turma_id"])

    cond = cond_linha_por_oferta(
        RegistroAula.turma_curso_id,
        RegistroAula.turma_id,
        curso_id=filtros.get("curso_id"),
        professor_id=filtros.get("professor_id"),
    )
    if cond is not None:
        query = query.filter(cond)

    if filtros.get("data_inicio"):
        query = query.filter(RegistroAula.data >= filtros["data_inicio"])

    if filtros.get("data_fim"):
        query = query.filter(RegistroAula.data <= filtros["data_fim"])

    return query


def _totais_por_aluno(filtros):
    """`aluno_id -> [presentes, faltas]` em UMA consulta agregada (D3b.4a).

    Só entram linhas contábeis (A-D, F); J fica fora, exatamente como a regra
    do serviço. Substitui o carregamento linha a linha das faixas antigas.
    """
    linhas = (
        _base_frequencia(filtros, conceitos=_CONCEITOS_CONTABEIS)
        .with_entities(
            Frequencia.aluno_id,
            Frequencia.conceito,
            func.count(Frequencia.id),
        )
        .group_by(Frequencia.aluno_id, Frequencia.conceito)
        .all()
    )

    totais = {}
    for aluno_id, conceito, n in linhas:
        atual = totais.setdefault(aluno_id, [0, 0])
        if conceito in _CONCEITOS_PRESENCA:
            atual[0] += n
        else:
            atual[1] += n
    return totais


def _contagem_por_faixa(alvo, filtros):
    """FRE-006/007/008 como UMA função auxiliar parametrizada (decisão 4).

    Percentual e faixa vêm do serviço `frequencia_oferta` (faixa sobre o valor
    arredondado: hi >= 90, mid >= 75, lo abaixo), de modo que hi + mid + lo
    somam exatamente o total de alunos com frequência contável no escopo.
    """
    return sum(
        1
        for presentes, faltas in _totais_por_aluno(filtros).values()
        if faixa_de(percentual(presentes, faltas)) == alvo
    )


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
                cond_aluno_no_escopo_unidade(unidade_id_intervalo),
                func.date(Aluno.created_at) >= inicio.isoformat(),
                func.date(Aluno.created_at) <= fim.isoformat(),
            )
            for unidade_id_intervalo, inicio, fim in intervalos
            if inicio <= fim
        ]
        return Aluno.query.filter(db.or_(*condicoes)).count() if condicoes else 0

    query = Aluno.query
    if unidade_id is not None:
        query = query.filter(cond_aluno_no_escopo_unidade(unidade_id))
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

    unidade_aluno = unidade_efetiva_aluno()
    query = Aluno.query.join(Unidade, Unidade.id == unidade_aluno)
    if unidade_id:
        query = query.filter(unidade_aluno == unidade_id)

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
        ).filter(
            # Só conta enturmado em oferta ativa (turma desativada fora).
            cond_inscricao_enturmada(),
        )

        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

        if turma_id:
            query = query.filter(Turma.id == turma_id)

        # D3b.4a (decisão 1): curso/professor pela OFERTA da inscrição
        # (Inscricao.turma_curso_id é NOT NULL — sem fallback para a turma).
        # Decisão 6: a base do indicador continua a cadastral do catálogo.
        if curso_id or professor_id:
            query = query.join(
                TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id
            )
            if curso_id:
                query = query.filter(TurmaCurso.curso_id == curso_id)
            if professor_id:
                query = query.filter(TurmaCurso.professor_id == professor_id)

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
        # D3b.4a (decisão 1): o curso vem da OFERTA da inscrição
        # (TurmaCurso.curso_id), sem fallback para Turma.curso_id.
        .join(TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id)
        .join(Curso, Curso.id == TurmaCurso.curso_id)
        .filter(
            # Etapa J3: só conta enturmado em oferta ativa (helper inclui
            # Inscricao.ativo e Turma.ativo; NULL ambíguo com 2+ ofertas fora).
            cond_inscricao_enturmada(),
            Turma.periodo_letivo_id.in_([periodo.id for periodo in periodos]),
        )
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    # D3b.4a (decisões 1 e 2): curso/professor pela OFERTA; o aluno é
    # distinto DENTRO de cada curso (a soma dos cursos pode exceder os
    # alunos distintos da unidade — documentado no catálogo).
    if curso_id:
        query = query.filter(TurmaCurso.curso_id == curso_id)

    if professor_id:
        query = query.filter(TurmaCurso.professor_id == professor_id)

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
            # Etapa J3: só conta enturmado em oferta ativa (ver alunos_por_curso).
            cond_inscricao_enturmada(),
            Turma.periodo_letivo_id.in_([periodo.id for periodo in periodos]),
        )
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    # D3b.4a (decisões 1 e 2): curso/professor pela OFERTA da inscrição;
    # o aluno conta uma vez por turma (distinct por Turma já no group_by).
    if curso_id or professor_id:
        query = query.join(
            TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id
        )
        if curso_id:
            query = query.filter(TurmaCurso.curso_id == curso_id)
        if professor_id:
            query = query.filter(TurmaCurso.professor_id == professor_id)

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
    """Retorna a quantidade de inscrições agrupada por curso.

    D3b.4a (decisão 1): o curso vem da OFERTA da inscrição
    (`Inscricao.turma_curso_id` -> `TurmaCurso.curso_id`), sem fallback.
    """
    from app.models import Curso

    query = Inscricao.query.join(Turma, Turma.id == Inscricao.turma_id).join(
        TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id
    ).join(
        Curso, Curso.id == TurmaCurso.curso_id
    ).filter(
        # Turma desativada (excluída) não entra em contagens agregadas.
        Turma.ativo.is_(True),
    )

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    if curso_id:
        query = query.filter(TurmaCurso.curso_id == curso_id)

    if professor_id:
        query = query.filter(TurmaCurso.professor_id == professor_id)

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
    """Retorna o total de lançamentos de frequência conforme os filtros do BI.

    D3b.4a (decisões 1 e 3): curso/professor casam pela OFERTA da linha.
    """
    return _base_frequencia(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    ).count()


def total_presencas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de presenças conforme os filtros do BI (D3b.4a: por OFERTA)."""
    return _base_frequencia(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
        conceitos=_CONCEITOS_PRESENCA,
    ).count()


def total_faltas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de faltas conforme os filtros do BI (D3b.4a: por OFERTA)."""
    return _base_frequencia(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
        conceitos=["F"],
    ).count()


def total_faltas_justificadas(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna o total de faltas justificadas conforme os filtros do BI (D3b.4a: por OFERTA)."""
    return _base_frequencia(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        },
        conceitos=["J"],
    ).count()


def frequencia_media(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média global, excluindo faltas justificadas.

    D3b.4a (decisão 4): o percentual vem da regra única do serviço
    `frequencia_oferta` — presentes/(presentes+faltas), J fora, 1 casa.
    """
    contagens = (
        _base_frequencia(
            {
                "unidade_id": unidade_id,
                "periodo_letivo_id": periodo_letivo_id,
                "curso_id": curso_id,
                "turma_id": turma_id,
                "professor_id": professor_id,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            },
            conceitos=_CONCEITOS_CONTABEIS,
        )
        .with_entities(Frequencia.conceito, func.count(Frequencia.id))
        .group_by(Frequencia.conceito)
        .all()
    )

    presentes = sum(
        n for conceito, n in contagens if conceito in _CONCEITOS_PRESENCA
    )
    faltas = sum(n for conceito, n in contagens if conceito == "F")

    return percentual(presentes, faltas)


"""FRE-006/007/008 (D3b.4a, decisão 4): as três faixas viram UMA função
auxiliar parametrizada (`_contagem_por_faixa`), sobre o percentual e a faixa
do serviço `frequencia_oferta` (faixa sobre o valor arredondado: hi >= 90,
mid >= 75, lo abaixo). Assim hi + mid + lo somam exatamente o total de alunos
com frequência contável no escopo (fecha a brecha do 89,96%)."""


def alunos_frequencia_90(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna alunos com frequência na faixa "hi" (>= 90% arredondado)."""
    return _contagem_por_faixa(
        "hi",
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


def alunos_frequencia_75_89(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna alunos com frequência na faixa "mid" (75% <= arredondado < 90%)."""
    return _contagem_por_faixa(
        "mid",
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


def alunos_frequencia_inferior_75(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna alunos com frequência na faixa "lo" (< 75% arredondado)."""
    return _contagem_por_faixa(
        "lo",
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


def frequencia_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média agrupada por turma.

    D3b.4a: o percentual exibido continua POR TURMA (todas as linhas da
    turma — decisão 3: o legado entra nos totais de unidade/turma), mas a
    agregação passa a ser em lote pelo serviço `frequencia_oferta`
    (`agregar_por_turma`), sem iterar turma a turma. Os filtros curso e
    professor passam a selecionar as TURMAS pela OFERTA (decisão 1): a
    turma aparece quando tem oferta ativa casando o filtro.
    """

    # Turma desativada (excluída) não entra em contagens agregadas.
    query = Turma.query.filter(Turma.ativo.is_(True))

    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if turma_id:
        query = query.filter(Turma.id == turma_id)

    # D3b.4a (decisão 1): curso/professor pela OFERTA — a turma entra quando
    # tem oferta ATIVA casando o filtro.
    casam = []
    if curso_id:
        casam.append(TurmaCurso.curso_id == curso_id)
    if professor_id:
        casam.append(TurmaCurso.professor_id == professor_id)
    if casam:
        query = query.filter(
            select(TurmaCurso.id)
            .where(
                TurmaCurso.turma_id == Turma.id,
                TurmaCurso.ativo.is_(True),
                *casam,
            )
            .exists()
        )

    turmas = query.order_by(Turma.nome).all()
    if not turmas:
        return []

    turmas_ids = [turma.id for turma in turmas]

    if data_inicio or data_fim:
        # Recálculo por intervalo de datas: UMA consulta agregada (sem N+1).
        fq = db.session.query(
            Frequencia.turma_id,
            Frequencia.conceito,
            func.count(Frequencia.id),
        ).filter(
            Frequencia.turma_id.in_(turmas_ids),
            Frequencia.conceito.in_(_CONCEITOS_CONTABEIS),
        )
        if unidade_id:
            fq = fq.filter(Turma.unidade_id == unidade_id)
        if data_inicio:
            fq = fq.filter(Frequencia.data >= data_inicio)
        if data_fim:
            fq = fq.filter(Frequencia.data <= data_fim)

        totais = {tid: [0, 0] for tid in turmas_ids}
        for tid, conceito, n in fq.group_by(
            Frequencia.turma_id, Frequencia.conceito
        ).all():
            if conceito == "F":
                totais[tid][1] += n
            else:
                totais[tid][0] += n
        percentuais = {tid: percentual(p, f) for tid, (p, f) in totais.items()}
    else:
        # Agregação em lote pelo serviço único (1 consulta para todas as
        # turmas; turmas sem frequência ficam ausentes do dict).
        agregado = agregar_por_turma(turmas_ids)
        percentuais = {tid: info.pct_turma for tid, info in agregado.items()}

    return [
        {
            "id": turma.id,
            "nome": turma.nome,
            # Turma sem frequência: 0.0 (mesmo comportamento do anterior).
            "valor": percentuais.get(turma.id, 0.0),
        }
        for turma in turmas
    ]


def frequencia_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a frequência média agrupada por curso.

    D3b.4a (decisão 3): frequência POR CURSO usa somente linhas de OFERTA
    (`TurmaCurso.curso_id`, sem fallback para a turma); as linhas legadas
    (`turma_curso_id IS NULL`) entram no curso da oferta quando ela é a
    única ativa da turma (regra D2, aplicada dentro do serviço
    `agregar_por_oferta`). Agregação em lote — sem carregar linha a linha
    nem iterar turma a turma.
    """
    ofertas = (
        db.session.query(TurmaCurso.id, TurmaCurso.curso_id, Curso.nome)
        .join(Turma, Turma.id == TurmaCurso.turma_id)
        .join(Curso, Curso.id == TurmaCurso.curso_id)
        .filter(
            # Turma desativada (excluída) não entra em contagens agregadas.
            Turma.ativo.is_(True),
        )
    )

    if unidade_id:
        ofertas = ofertas.filter(Turma.unidade_id == unidade_id)

    if periodo_letivo_id:
        ofertas = ofertas.filter(Turma.periodo_letivo_id == periodo_letivo_id)

    if turma_id:
        ofertas = ofertas.filter(Turma.id == turma_id)

    if curso_id:
        ofertas = ofertas.filter(TurmaCurso.curso_id == curso_id)

    if professor_id:
        ofertas = ofertas.filter(TurmaCurso.professor_id == professor_id)

    linhas_oferta = ofertas.all()
    if not linhas_oferta:
        return []

    curso_por_oferta = {
        oferta_id: (curso_rel, nome)
        for oferta_id, curso_rel, nome in linhas_oferta
    }
    contagem = {}

    def _acumula(oferta_id, presentes, faltas):
        chave = curso_por_oferta.get(oferta_id)
        if chave is None:
            return
        atual = contagem.setdefault(chave, [0, 0])
        atual[0] += presentes
        atual[1] += faltas

    if data_inicio or data_fim:
        # Recálculo por intervalo de datas: a mesma regra D2 do serviço, em
        # UMA consulta agregada (ofertas próprias + legadas das turmas em
        # que a oferta pedida é a única ativa).
        ids = list(curso_por_oferta)
        unicas = ofertas_unicas_ativas(ids)
        turmas_unicas = {
            oferta_id: turma_rel
            for oferta_id, turma_rel in db.session.query(
                TurmaCurso.id, TurmaCurso.turma_id
            )
            .filter(TurmaCurso.id.in_(sorted(unicas)))
            .all()
        } if unicas else {}

        alvos = [Frequencia.turma_curso_id.in_(ids)]
        if turmas_unicas:
            alvos.append(
                and_(
                    Frequencia.turma_curso_id.is_(None),
                    Frequencia.turma_id.in_(set(turmas_unicas.values())),
                )
            )

        fq = db.session.query(
            Frequencia.turma_curso_id,
            Frequencia.turma_id,
            Frequencia.conceito,
            func.count(Frequencia.id),
        ).filter(
            or_(*alvos),
            Frequencia.conceito.in_(_CONCEITOS_CONTABEIS),
        )
        if unidade_id:
            fq = fq.filter(Turma.unidade_id == unidade_id)
        if data_inicio:
            fq = fq.filter(Frequencia.data >= data_inicio)
        if data_fim:
            fq = fq.filter(Frequencia.data <= data_fim)

        for tcurso_id, turma_rel, conceito, n in fq.group_by(
            Frequencia.turma_curso_id,
            Frequencia.turma_id,
            Frequencia.conceito,
        ).all():
            if tcurso_id is None:
                # legado: atribuído à única oferta ativa daquela turma (D2)
                alvo = next(
                    (
                        oid
                        for oid, t in turmas_unicas.items()
                        if t == turma_rel
                    ),
                    None,
                )
            else:
                alvo = tcurso_id
            presente = conceito in _CONCEITOS_PRESENCA
            _acumula(alvo, n if presente else 0, 0 if presente else n)
    else:
        # Serviço único: 1 consulta de frequência para todas as ofertas, com
        # a regra D2 do legado embutida.
        agregado = agregar_por_oferta(list(curso_por_oferta))
        for oferta_id, info in agregado.items():
            _acumula(oferta_id, info.presentes, info.faltas)

    resultados = [
        {
            "id": curso_rel,
            "nome": nome,
            "valor": percentual(p, f),
        }
        for (curso_rel, nome), (p, f) in contagem.items()
        if p + f  # curso sem nenhuma linha contável fica fora (como antes)
    ]

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

    # Turma desativada (excluída) não entra em contagens agregadas.
    # Contadores de TURMAS mantêm só Turma.ativo (não exigem oferta ativa).
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

    # Turma desativada (excluída) não entra; numerador só conta enturmados
    # em oferta ativa (helper da Etapa J2).
    turmas_query = Turma.query.filter(Turma.ativo.is_(True))

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
            cond_inscricao_enturmada(),
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

    # Turma desativada (excluída) não entra em contagens agregadas.
    query = Turma.query.filter(Turma.ativo.is_(True)).join(
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

    # Turma desativada (excluída) não entra em contagens agregadas.
    query = Turma.query.filter(Turma.ativo.is_(True)).join(
        PeriodoLetivo,
        PeriodoLetivo.id == Turma.periodo_letivo_id,
    ).join(
        Unidade,
        Unidade.id == PeriodoLetivo.unidade_id,
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
            Unidade.nome,
            db.func.count(Turma.id),
        )
        .group_by(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
            Unidade.nome,
        )
        .order_by(PeriodoLetivo.nome)
        .all()
    )

    return [
        {
            "id": periodo_id,
            "nome": f"{unidade_nome} {nome}",
            "valor": total,
        }
        for periodo_id, nome, unidade_nome, total in resultados
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

    # Turma desativada (excluída) não entra em contagens agregadas.
    query = Turma.query.filter(Turma.ativo.is_(True)).join(
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

    # Turma desativada (excluída) não entra em contagens agregadas.
    query = Turma.query.filter(Turma.ativo.is_(True)).join(
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
    """Retorna o total de aulas registradas conforme os filtros informados.

    D3b.4a (decisões 1 e 3): curso/professor casam pela OFERTA do registro
    (`cond_linha_por_oferta`). Corrige o defect do join duplo em `Turma`
    caracterizado nos testes: unidade + curso/professor/período geravam
    `ambiguous column name: turma.unidade_id` (OperationalError -> 500 na
    rota do BI).
    """
    return _base_registro_aula(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    ).count()


def aulas_por_turma(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por turma.

    D3b.4a (decisão 1): curso/professor casam pela OFERTA do registro.
    """

    query = _base_registro_aula(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    )

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
    """Retorna a quantidade de aulas registradas agrupada por período letivo.

    D3b.4a (decisão 1): curso/professor casam pela OFERTA do registro.
    """

    query = _base_registro_aula(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    ).join(
        PeriodoLetivo,
        PeriodoLetivo.id == Turma.periodo_letivo_id,
    ).join(
        Unidade,
        Unidade.id == PeriodoLetivo.unidade_id,
    )

    resultados = (
        query.with_entities(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
            Unidade.nome,
            db.func.count(RegistroAula.id),
        )
        .group_by(
            PeriodoLetivo.id,
            PeriodoLetivo.nome,
            Unidade.nome,
        )
        .order_by(PeriodoLetivo.nome)
        .all()
    )

    return [
        {
            "id": periodo_id_resultado,
            "nome": f"{unidade_nome} {nome}",
            "valor": total,
        }
        for periodo_id_resultado, nome, unidade_nome, total in resultados
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
    """Retorna a quantidade de aulas registradas agrupada por professor.

    D3b.4a (decisão 1): o agrupamento passa a ser pelo PROFESSOR DA OFERTA
    (`TurmaCurso.professor_id`), não mais por `Turma.professor_id`. Linhas
    com oferta própria agrupam pela sua oferta; linhas legadas entram quando
    a turma tem exatamente uma oferta ATIVA (regra D2 da decisão 3), pelo
    professor dessa oferta. Duas consultas agregadas + merge em Python
    (sem N+1); oferta sem professor fica fora do agrupamento (como antes,
    pelo join interno em `User`).
    """
    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    def _escopo(query):
        if filtros["unidade_id"]:
            query = query.filter(Turma.unidade_id == filtros["unidade_id"])
        if filtros["periodo_letivo_id"]:
            query = query.filter(
                Turma.periodo_letivo_id == filtros["periodo_letivo_id"]
            )
        if filtros["turma_id"]:
            query = query.filter(Turma.id == filtros["turma_id"])
        if filtros["curso_id"]:
            query = query.filter(TurmaCurso.curso_id == filtros["curso_id"])
        if filtros["professor_id"]:
            query = query.filter(
                TurmaCurso.professor_id == filtros["professor_id"]
            )
        if filtros["data_inicio"]:
            query = query.filter(RegistroAula.data >= filtros["data_inicio"])
        if filtros["data_fim"]:
            query = query.filter(RegistroAula.data <= filtros["data_fim"])
        return query

    # 1) linhas com oferta própria: agrupam pelo professor da SUA oferta.
    proprias = (
        _escopo(
            db.session.query(TurmaCurso.professor_id, func.count(RegistroAula.id))
            .select_from(RegistroAula)
            .join(Turma, Turma.id == RegistroAula.turma_id)
            .join(TurmaCurso, TurmaCurso.id == RegistroAula.turma_curso_id)
        )
        .group_by(TurmaCurso.professor_id)
        .all()
    )

    # 2) linhas legadas: só entram em turma de oferta ÚNICA ativa (regra D2),
    #    agrupadas pelo professor dessa oferta única.
    turmas_unica = (
        select(TurmaCurso.turma_id)
        .where(TurmaCurso.ativo.is_(True))
        .group_by(TurmaCurso.turma_id)
        .having(func.count(TurmaCurso.id) == 1)
    )
    legadas = (
        _escopo(
            db.session.query(TurmaCurso.professor_id, func.count(RegistroAula.id))
            .select_from(RegistroAula)
            .join(Turma, Turma.id == RegistroAula.turma_id)
            .join(
                TurmaCurso,
                and_(
                    TurmaCurso.turma_id == RegistroAula.turma_id,
                    TurmaCurso.ativo.is_(True),
                ),
            )
            .filter(
                RegistroAula.turma_curso_id.is_(None),
                Turma.id.in_(turmas_unica),
            )
        )
        .group_by(TurmaCurso.professor_id)
        .all()
    )

    totais = {}
    for professor_rel, n in proprias + legadas:
        if professor_rel is None:
            continue
        totais[professor_rel] = totais.get(professor_rel, 0) + n

    if not totais:
        return []

    nomes = dict(
        db.session.query(User.id, User.name)
        .filter(User.id.in_(list(totais)))
        .all()
    )

    resultados = [
        {
            "id": professor_rel,
            "nome": nomes.get(professor_rel, f"Professor #{professor_rel}"),
            "valor": total,
        }
        for professor_rel, total in totais.items()
    ]
    return sorted(resultados, key=lambda item: item["nome"])


def aulas_por_curso(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por curso.

    D3b.4a (decisões 1 e 3): o curso passa a ser o da OFERTA
    (`TurmaCurso.curso_id`). Linhas com oferta própria agrupam pelo curso
    da sua oferta; linhas legadas entram quando a turma tem exatamente uma
    oferta ATIVA (regra D2), pelo curso dessa oferta. Duas consultas
    agregadas + merge em Python (sem N+1).
    """
    filtros = {
        "unidade_id": unidade_id,
        "periodo_letivo_id": periodo_letivo_id,
        "curso_id": curso_id,
        "turma_id": turma_id,
        "professor_id": professor_id,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
    }

    def _escopo(query):
        if filtros["unidade_id"]:
            query = query.filter(Turma.unidade_id == filtros["unidade_id"])
        if filtros["periodo_letivo_id"]:
            query = query.filter(
                Turma.periodo_letivo_id == filtros["periodo_letivo_id"]
            )
        if filtros["turma_id"]:
            query = query.filter(Turma.id == filtros["turma_id"])
        if filtros["curso_id"]:
            query = query.filter(TurmaCurso.curso_id == filtros["curso_id"])
        if filtros["professor_id"]:
            query = query.filter(
                TurmaCurso.professor_id == filtros["professor_id"]
            )
        if filtros["data_inicio"]:
            query = query.filter(RegistroAula.data >= filtros["data_inicio"])
        if filtros["data_fim"]:
            query = query.filter(RegistroAula.data <= filtros["data_fim"])
        return query

    proprias = (
        _escopo(
            db.session.query(TurmaCurso.curso_id, func.count(RegistroAula.id))
            .select_from(RegistroAula)
            .join(Turma, Turma.id == RegistroAula.turma_id)
            .join(TurmaCurso, TurmaCurso.id == RegistroAula.turma_curso_id)
        )
        .group_by(TurmaCurso.curso_id)
        .all()
    )

    turmas_unica = (
        select(TurmaCurso.turma_id)
        .where(TurmaCurso.ativo.is_(True))
        .group_by(TurmaCurso.turma_id)
        .having(func.count(TurmaCurso.id) == 1)
    )
    legadas = (
        _escopo(
            db.session.query(TurmaCurso.curso_id, func.count(RegistroAula.id))
            .select_from(RegistroAula)
            .join(Turma, Turma.id == RegistroAula.turma_id)
            .join(
                TurmaCurso,
                and_(
                    TurmaCurso.turma_id == RegistroAula.turma_id,
                    TurmaCurso.ativo.is_(True),
                ),
            )
            .filter(
                RegistroAula.turma_curso_id.is_(None),
                Turma.id.in_(turmas_unica),
            )
        )
        .group_by(TurmaCurso.curso_id)
        .all()
    )

    totais = {}
    for curso_rel, n in proprias + legadas:
        if curso_rel is None:
            continue
        totais[curso_rel] = totais.get(curso_rel, 0) + n

    if not totais:
        return []

    nomes = dict(
        db.session.query(Curso.id, Curso.nome)
        .filter(Curso.id.in_(list(totais)))
        .all()
    )

    resultados = [
        {
            "id": curso_rel,
            "nome": nomes.get(curso_rel, f"Curso #{curso_rel}"),
            "valor": total,
        }
        for curso_rel, total in totais.items()
    ]
    return sorted(resultados, key=lambda item: item["nome"])


def aulas_por_tema(
    unidade_id=None,
    periodo_letivo_id=None,
    curso_id=None,
    turma_id=None,
    professor_id=None,
    data_inicio=None,
    data_fim=None,
):
    """Retorna a quantidade de aulas registradas agrupada por tema.

    D3b.4a (decisão 1): curso/professor casam pela OFERTA do registro.
    """

    query = _base_registro_aula(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    ).join(RegistroAula.temas)

    resultados = (
        query.with_entities(
            TemaAula.id,
            TemaAula.titulo,
            func.count(func.distinct(RegistroAula.id)),
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
    """Retorna a quantidade de aulas registradas agrupada por unidade.

    D3b.4a (decisão 1): curso/professor pela OFERTA (via
    `cond_linha_por_oferta`, com a regra D2 do legado). Corrige defect
    caracterizado: o código antigo filtrava por `RegistroAula.periodo_id` e
    `RegistroAula.professor_id`, atributos INEXISTENTES no modelo — qualquer
    filtro de período/professor derrubava a consulta (500 na rota). O
    período passa a ser o da turma.
    """
    query = (
        _base_registro_aula(
            {
                "unidade_id": unidade_id,
                "periodo_letivo_id": periodo_id,
                "curso_id": curso_id,
                "turma_id": turma_id,
                "professor_id": professor_id,
                "data_inicio": data_inicio,
                "data_fim": data_fim,
            }
        )
        .join(Unidade, Unidade.id == Turma.unidade_id)
        .with_entities(
            Unidade.id,
            Unidade.nome,
            func.count(RegistroAula.id),
        )
        .group_by(Unidade.id, Unidade.nome)
        .order_by(Unidade.nome)
        .all()
    )

    return [
        {
            "id": unidade_rel,
            "nome": nome,
            "valor": valor,
        }
        for unidade_rel, nome, valor in query
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
    """Retorna a quantidade de aulas registradas agrupada por data.

    D3b.4a (decisão 1): curso/professor casam pela OFERTA do registro.
    """

    query = _base_registro_aula(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    )

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
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        # D3b.4a (decisão 1): curso/professor pela OFERTA da inscrição.
        if curso_id or professor_id:
            query = query.join(
                TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id
            )
            if curso_id:
                query = query.filter(TurmaCurso.curso_id == curso_id)
            if professor_id:
                query = query.filter(
                    TurmaCurso.professor_id == professor_id
                )

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
    """Retorna a quantidade de alunos com frequência < 75% agrupada por vulnerabilidade social.

    D3b.4a (decisões 1, 3 e 4): curso/professor casam pela OFERTA da linha
    e a faixa "lo" (percentual arredondado < 75) vem do serviço único
    `frequencia_oferta`, com agregação em lote (UMA consulta
    GROUP BY aluno/conceito, sem carregar linha a linha).
    """
    from app.models import PerfilSocioeconomico

    totais = _totais_por_aluno(
        {
            "unidade_id": unidade_id,
            "periodo_letivo_id": periodo_letivo_id,
            "curso_id": curso_id,
            "turma_id": turma_id,
            "professor_id": professor_id,
            "data_inicio": data_inicio,
            "data_fim": data_fim,
        }
    )

    alunos_criticos_ids = [
        aluno_id
        for aluno_id, (presentes, faltas) in totais.items()
        if faixa_de(percentual(presentes, faltas)) == "lo"
    ]

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
    from app.models import ConselhoClasse, Turma

    query = ConselhoClasse.query.join(
        PerfilDiversidade, PerfilDiversidade.aluno_id == ConselhoClasse.aluno_id
    )
    if unidade_id:
        query = query.filter(ConselhoClasse.unidade_id == unidade_id)

    if periodo_letivo_id or curso_id or turma_id or professor_id:
        query = query.join(Turma, Turma.id == ConselhoClasse.turma_id)
        if periodo_letivo_id:
            query = query.filter(Turma.periodo_letivo_id == periodo_letivo_id)
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        # D3b.4a (decisão 1): curso/professor pela OFERTA do conselho
        # (ConselhoClasse.turma_curso_id é NOT NULL — sem fallback).
        if curso_id or professor_id:
            query = query.join(
                TurmaCurso, TurmaCurso.id == ConselhoClasse.turma_curso_id
            )
            if curso_id:
                query = query.filter(TurmaCurso.curso_id == curso_id)
            if professor_id:
                query = query.filter(
                    TurmaCurso.professor_id == professor_id
                )

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
        if turma_id:
            query = query.filter(Turma.id == turma_id)
        # D3b.4a (decisão 1): curso/professor pela OFERTA do conselho.
        if curso_id or professor_id:
            query = query.join(
                TurmaCurso, TurmaCurso.id == ConselhoClasse.turma_curso_id
            )
            if curso_id:
                query = query.filter(TurmaCurso.curso_id == curso_id)
            if professor_id:
                query = query.filter(
                    TurmaCurso.professor_id == professor_id
                )

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

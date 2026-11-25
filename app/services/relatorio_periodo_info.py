"""Agregação das Informações Gerais do Período (AJ31/AJ31-B).

A base de inscritos é o conjunto de pares ``(aluno, oferta)`` enturmados.
Contagens e percentuais saem exclusivamente desse conjunto: um ConselhoClasse
FINAL só entra quando o mesmo par existe nele.
"""

from sqlalchemy import and_, func

from app import db
from app.models import Aluno, ConselhoClasse, Inscricao, Turma, TurmaCurso
from app.models.enums import (
    SITUACAO_FINAL_OPCOES,
    SITUACOES_FINAIS_FAVORAVEIS,
    EtapaConselho,
    SituacaoFinal,
)
from app.services.enturmado import cond_inscricao_enturmada
from app.services.frequencia_oferta import percentual

# Apresentação ONLY: os valores vêm de SituacaoFinal/SITUACAO_FINAL_OPCOES.
_CONFIG_SITUACOES: dict[SituacaoFinal, dict] = {
    SituacaoFinal.APROVADO: {
        "rotulo": "Aprovado",
        "descricao": "Concluiu o curso com aproveitamento",
        "legenda": "Concluiu o curso com aproveitamento.",
        "cor": "success",
        "exibir_se_zero": True,
    },
    SituacaoFinal.PARTICIPANTE: {
        "rotulo": "Participante",
        "descricao": "Participou do curso",
        "legenda": "Participou do curso.",
        "cor": "primary",
        "exibir_se_zero": True,
    },
    SituacaoFinal.REPROVADO_POR_FALTAS: {
        "rotulo": "Reprovado por faltas",
        "descricao": "Frequência abaixo do mínimo exigido",
        "legenda": "Frequência abaixo do mínimo exigido.",
        "cor": "warning",
        "exibir_se_zero": True,
    },
    SituacaoFinal.DESISTENTE: {
        "rotulo": "Desistente",
        "descricao": "Cancelou a matrícula",
        "legenda": "Cancelou a matrícula.",
        "cor": "danger",
        "exibir_se_zero": True,
    },
    SituacaoFinal.EVADIDO: {
        "rotulo": "Evadido",
        "descricao": "Deixou de frequentar sem formalizar a saída",
        "legenda": "Deixou de frequentar sem formalizar a saída.",
        "cor": "secondary",
        "exibir_se_zero": True,
    },
    SituacaoFinal.EMPREGADO: {
        "rotulo": "Empregado",
        "descricao": "Inserido no mercado de trabalho",
        "legenda": "Inserido no mercado de trabalho.",
        "cor": "info",
        "exibir_se_zero": True,
    },
}

_CONFIG_PADRAO = {
    "rotulo": None,
    "descricao": "Situação final registrada no conselho",
    "legenda": "Situação final registrada no conselho.",
    "cor": "secondary",
    "exibir_se_zero": True,
}

FORMULA_APROVEITAMENTO = (
    f"alunos {SituacaoFinal.APROVADO.value}s ou {SituacaoFinal.PARTICIPANTE.value}s"
    " ÷ alunos com situação final definida"
)


def _apresentacao(valor: str) -> dict:
    """Devolve apresentação para qualquer valor gravado, inclusive desconhecido."""
    try:
        chave = SituacaoFinal(valor)
    except ValueError:
        chave = None
    cfg = _CONFIG_SITUACOES.get(chave, _CONFIG_PADRAO)
    return {
        "rotulo": cfg.get("rotulo") or valor,
        "descricao": cfg.get("descricao") or valor,
        "legenda": cfg.get("legenda") or valor,
        "cor": cfg.get("cor") or "secondary",
        "exibir_se_zero": cfg.get("exibir_se_zero", True),
    }


def _base_inscritos(periodo_letivo_id: int, unidade_id: int | None):
    """Subquery com um registro por par `(aluno, oferta)` efetivamente inscrito."""
    consulta = (
        db.session.query(
            Inscricao.aluno_id.label("aluno_id"),
            Inscricao.turma_curso_id.label("turma_curso_id"),
        )
        .join(TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .join(Aluno, Aluno.id == Inscricao.aluno_id)
        .filter(
            Turma.periodo_letivo_id == periodo_letivo_id,
            Turma.ativo.is_(True),
            Aluno.ativo.is_(True),
            # Inclui Inscricao.ativo, Turma.ativo e cond_oferta_efetiva().
            cond_inscricao_enturmada(),
        )
        .distinct()
    )
    if unidade_id is not None:
        consulta = consulta.filter(Turma.unidade_id == unidade_id)
    return consulta.subquery("inscritos_base")


def _pares_avaliados():
    """Subquery com no máximo um registro por par `(aluno, oferta)` FINAL."""
    return (
        db.session.query(
            ConselhoClasse.aluno_id.label("aluno_id"),
            ConselhoClasse.turma_curso_id.label("turma_curso_id"),
            ConselhoClasse.situacao_final.label("situacao_final"),
        )
        .filter(
            ConselhoClasse.etapa == EtapaConselho.FINAL,
            ConselhoClasse.situacao_final.isnot(None),
        )
        .distinct()
        .subquery("pares_avaliados")
    )


def obter_informacoes_gerais_periodo(
    periodo_letivo_id: int, unidade_id: int | None = None
) -> dict:
    """Distribuição das situações finais das ofertas efetivas do período.

    ``total_inscritos``, as contagens por situação e ``pendentes_definicao``
    derivam da MESMA subquery de pares inscritos. O join por
    ``(aluno_id, turma_curso_id)`` garante que nenhum ConselhoClasse de um par
    fora do conjunto de inscritos seja contado como avaliado.
    """
    base = _base_inscritos(periodo_letivo_id, unidade_id)
    pares = _pares_avaliados()
    mesmo_par = and_(
        base.c.aluno_id == pares.c.aluno_id,
        base.c.turma_curso_id == pares.c.turma_curso_id,
    )

    total_inscritos = db.session.query(func.count()).select_from(base).scalar() or 0

    contagens = dict(
        db.session.query(
            pares.c.situacao_final,
            func.count(pares.c.aluno_id),
        )
        .join(base, mesmo_par)
        .group_by(pares.c.situacao_final)
        .all()
    )
    total_avaliados = sum(contagens.values())

    # Contagem direta dos pares inscritos sem situação final — sem max(0, ...).
    pendentes_definicao = (
        db.session.query(func.count())
        .select_from(base)
        .outerjoin(pares, mesmo_par)
        .filter(pares.c.aluno_id.is_(None))
        .scalar()
        or 0
    )

    # Enum é a fonte única; valores gravados fora dele também aparecem.
    valores = list(SITUACAO_FINAL_OPCOES)
    valores += sorted(v for v in contagens if v not in SITUACAO_FINAL_OPCOES)

    indicadores = []
    for valor in valores:
        quantidade = contagens.get(valor, 0)
        percentual_valor = (
            percentual(quantidade, total_avaliados - quantidade)
            if total_avaliados
            else 0.0
        )
        indicadores.append(
            {
                "situacao": valor,
                **_apresentacao(valor),
                "quantidade": quantidade,
                "percentual": percentual_valor,
            }
        )

    favoraveis = sum(
        contagens.get(valor, 0) for valor in SITUACOES_FINAIS_FAVORAVEIS
    )
    aproveitamento = {
        "quantidade": favoraveis,
        "percentual": (
            percentual(favoraveis, total_avaliados - favoraveis)
            if total_avaliados
            else None
        ),
        "formula": FORMULA_APROVEITAMENTO,
        "legenda": "Aproveitamento = alunos Aprovados ou Participantes ÷ alunos com situação final definida.",
    }

    return {
        "total_inscritos": total_inscritos,
        "total_avaliados": total_avaliados,
        "pendentes_definicao": pendentes_definicao,
        "indicadores": indicadores,
        "aproveitamento": aproveitamento,
    }

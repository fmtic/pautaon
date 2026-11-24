from sqlalchemy import func

from app.extensions import db
from app.models import Aluno, ConselhoClasse, Inscricao, Turma, TurmaCurso
from app.models.enums import EtapaConselho, SituacaoFinal


_CONFIG_SITUACOES = [
    {
        "enum": SituacaoFinal.APROVADO,
        "rotulo": "Aprovados",
        "descricao": "Concluíram com aproveitamento e frequência",
        "cor": "success",
        "exibir_se_zero": True,
    },
    {
        "enum": SituacaoFinal.PARTICIPANTE,
        "rotulo": "Participantes",
        "descricao": "Participação regular sem certificação integral",
        "cor": "primary",
        "exibir_se_zero": True,
    },
    {
        "enum": SituacaoFinal.REPROVADO_POR_FALTAS,
        "rotulo": "Reprovados por faltas",
        "descricao": "Frequência abaixo do mínimo exigido",
        "cor": "warning",
        "exibir_se_zero": True,
    },
    {
        "enum": SituacaoFinal.DESISTENTE,
        "rotulo": "Desistentes",
        "descricao": "Cancelamento formal de matrícula",
        "cor": "danger",
        "exibir_se_zero": True,
    },
    {
        "enum": SituacaoFinal.EVADIDO,
        "rotulo": "Evadidos",
        "descricao": "Abandono sem formalização",
        "cor": "secondary",
        "exibir_se_zero": False,
    },
    {
        "enum": SituacaoFinal.EMPREGADO,
        "rotulo": "Empregados",
        "descricao": "Inseridos no mercado de trabalho durante o curso",
        "cor": "info",
        "exibir_se_zero": False,
    },
]


def obter_informacoes_gerais_periodo(
    periodo_letivo_id: int, unidade_id: int | None = None
) -> dict:
    """
    Calcula a distribuição percentual de situações finais (Etapa FINAL)
    de todas as ofertas efetivas de um Período Letivo.
    """
    from app.relatorios.bi_filtros import cond_oferta_efetiva

    q_inscricoes = (
        db.session.query(func.count(Inscricao.id))
        .join(TurmaCurso, Inscricao.turma_curso_id == TurmaCurso.id)
        .join(Turma, TurmaCurso.turma_id == Turma.id)
        .join(Aluno, Inscricao.aluno_id == Aluno.id)
        .filter(
            Turma.periodo_letivo_id == periodo_letivo_id,
            Turma.ativo.is_(True),
            Aluno.ativo.is_(True),
            cond_oferta_efetiva(),
        )
    )
    if unidade_id is not None:
        q_inscricoes = q_inscricoes.filter(Turma.unidade_id == unidade_id)

    total_inscritos = q_inscricoes.scalar() or 0

    q_conselho = (
        db.session.query(
            ConselhoClasse.situacao_final,
            func.count(ConselhoClasse.id),
        )
        .join(TurmaCurso, ConselhoClasse.turma_curso_id == TurmaCurso.id)
        .join(Turma, TurmaCurso.turma_id == Turma.id)
        .join(Aluno, ConselhoClasse.aluno_id == Aluno.id)
        .filter(
            Turma.periodo_letivo_id == periodo_letivo_id,
            Turma.ativo.is_(True),
            Aluno.ativo.is_(True),
            ConselhoClasse.etapa == EtapaConselho.FINAL,
            ConselhoClasse.situacao_final.isnot(None),
            cond_oferta_efetiva(),
        )
        .group_by(ConselhoClasse.situacao_final)
    )
    if unidade_id is not None:
        q_conselho = q_conselho.filter(Turma.unidade_id == unidade_id)

    contagens = dict(q_conselho.all())
    total_avaliados = sum(contagens.values())

    indicadores = []
    for cfg in _CONFIG_SITUACOES:
        valor_enum = cfg["enum"].value
        qtd = contagens.get(valor_enum, 0)

        if qtd == 0 and not cfg["exibir_se_zero"]:
            continue

        percentual = (
            round((qtd / total_avaliados) * 100, 2)
            if total_avaliados > 0
            else 0.0
        )
        indicadores.append(
            {
                "situacao": valor_enum,
                "rotulo": cfg["rotulo"],
                "descricao": cfg["descricao"],
                "cor": cfg["cor"],
                "quantidade": qtd,
                "percentual": percentual,
            }
        )

    pendentes_definicao = max(0, total_inscritos - total_avaliados)

    return {
        "total_inscritos": total_inscritos,
        "total_avaliados": total_avaliados,
        "pendentes_definicao": pendentes_definicao,
        "indicadores": indicadores,
    }
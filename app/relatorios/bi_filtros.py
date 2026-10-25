"""Filtros compartilhados da Central de BI.

Os filtros que dependem de contexto acadêmico utilizam o vínculo:

    Aluno -> Inscricao -> Turma

Isso preserva o histórico das inscrições e evita depender de uma coluna
unidade_id inexistente em Aluno.
"""

from sqlalchemy import and_, or_, select

from app.models import Aluno, Inscricao, PeriodoLetivo, Turma, TurmaCurso
from app.models.base import get_local_now


def cond_oferta_efetiva():
    """Condição SQL (referencia `Inscricao`): a oferta apontada pela inscrição
    "conta" quando está ativa OU quando o período letivo da turma já encerrou.

    Regra do responsável (ETAPA M4): desativar uma oferta de período
    encerrado não pode alterar retroativamente BI e status. Casos:

        - oferta ativa                                    → conta;
        - oferta inativa, período da turma encerrado
          (`data_fim < hoje`)                             → conta (histórico);
        - oferta inativa, período em andamento ou futuro  → NÃO conta;
        - oferta inativa, turma sem `periodo_letivo_id`   → NÃO conta
          (sem período não há como atestar encerramento);
        - período com `data_fim` NULL                     → trata como em
          andamento (conservador, espelha a guarda de desativar_oferta).

    A oferta precisa pertencer à turma da inscrição (`turma_id` coerente) —
    mesmo aperto aplicado a `cond_inscricao_enturmada`.
    """
    hoje = get_local_now().date()
    return (
        select(TurmaCurso.id)
        .join(Turma, Turma.id == TurmaCurso.turma_id)
        .join(PeriodoLetivo, PeriodoLetivo.id == Turma.periodo_letivo_id)
        .where(
            TurmaCurso.id == Inscricao.turma_curso_id,
            TurmaCurso.turma_id == Inscricao.turma_id,
            or_(
                TurmaCurso.ativo.is_(True),
                and_(
                    PeriodoLetivo.data_fim.isnot(None),
                    PeriodoLetivo.data_fim < hoje,
                ),
            ),
        )
        # Manter TurmaCurso no FROM mesmo quando a query externa já o junta
        # (evita auto-correlação que zeraria o FROM do subselect).
        .correlate_except(TurmaCurso)
        .exists()
    )


def cond_inscricao_enturmada():
    """Condição SQL: a LINHA de Inscricao conta como enturmada em oferta efetiva.

    Regras (decisão do responsável — Etapa J2, endurecida na ETAPA B6,
    ajustada pela ETAPA M4 para o histórico de período encerrado):
        - Turma.ativo=False significa turma excluída/desativada: não entra
          em contagens agregadas.
        - Inscrição conta quando: Inscricao.ativo=True, a Turma da inscrição
          está ativa E a oferta apontada por `turma_curso_id` é efetiva
          (ativa, ou inativa em período da turma já encerrado — ver
          `cond_oferta_efetiva`), pertencendo à mesma turma.

    O antigo ramo de fallback (`turma_curso_id` NULL em turma com exatamente
    1 oferta ativa) tornou-se código morto: desde a migration da Onda 4
    (c3d4e5f6a7b8) Inscricao.turma_curso_id é NOT NULL, então nenhuma
    inscrição nova pode ficar sem oferta — o ramo foi removido.

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
    return and_(
        Inscricao.ativo.is_(True),
        turma_ativa,
        # ETAPA M4: oferta inativa em período encerrado conta (histórico);
        # em período em andamento/futuro ou sem período, exige-se oferta
        # ativa — comportamento J2/B6 preservado pelo `cond_oferta_efetiva`,
        # que também exige turma coerente com a oferta.
        cond_oferta_efetiva(),
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

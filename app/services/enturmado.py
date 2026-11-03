"""
ETAPA D3b.3 — definição única de "enturmado".

Módulo NEUTRO (não importa `app.relatorios` nem `app.registros`) que concentra
o predicado SQL canônico de enturmação, consumido pelo BI (`bi_filtros`
reexporta), pelo status canônico (`aluno_status`) e pelas telas de registro.

Definição DECIDIDA pelo responsável (docs/D3b_0_desenho.md, D3b.3):

    ENTURMADO = Aluno.ativo
                E Inscricao.ativo em Turma ativa
                E oferta EFETIVA (ativa, ou inativa em período já encerrado
                  — regra do M4).

Os predicados `cond_oferta_efetiva` e `cond_inscricao_enturmada` foram MOVIDOS
de `app/relatorios/bi_filtros.py` com comportamento idêntico (incluindo o
`correlate_except`, lição da anti-auto-correlação). O espelho
`aluno_status._cond_oferta_efetiva` (duplicado de propósito por causa do ciclo
de import — MER §12.13) passa a importar daqui, e o ciclo desaparece: este
módulo só depende de `app.models`.
"""
from __future__ import annotations

from sqlalchemy import and_, func, or_, select, true

from app import db
from app.models import Aluno, Inscricao, PeriodoLetivo, Turma, TurmaCurso
from app.models.base import get_local_now


# ---------------------------------------------------------------------------
# Predicados canônicos (movidos de bi_filtros — comportamento idêntico)
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Predicado de ALUNO (decisão D3b.3: cadastro ativo + vínculo enturmado)
# ---------------------------------------------------------------------------

def cond_aluno_enturmado(periodo_letivo_id: int | None = None):
    """Condição SQL (referencia `Aluno`): o aluno é ENTURMADO.

    Definição única (D3b.3): `Aluno.ativo` E existe inscrição enturmada
    (`cond_inscricao_enturmada`) — opcionalmente restrita a turmas de um
    período letivo. Implementado como EXISTS (não JOIN): não duplica linhas
    do aluno quando ele tem 2+ vínculos válidos.
    """
    insc = (
        select(Inscricao.id)
        .where(Inscricao.aluno_id == Aluno.id, cond_inscricao_enturmada())
    )
    if periodo_letivo_id is not None:
        insc = insc.join(Turma, Turma.id == Inscricao.turma_id).where(
            Turma.periodo_letivo_id == periodo_letivo_id
        )
    return and_(Aluno.ativo.is_(True), insc.exists())


# ---------------------------------------------------------------------------
# Consultas prontas (aluno distinto; sem N+1 — uma consulta por chamada)
# ---------------------------------------------------------------------------

def cond_aluno_no_escopo_unidade(unidade_id: int | None):
    """Escopo de aluno pela unidade própria ou por vínculo inequívoco com turma.

    Aluno sem unidade só pode ser atribuído à unidade quando todas as suas
    inscrições apontam para turmas de uma única unidade. Vínculos em mais de
    uma unidade permanecem fora do escopo para evitar exposição cruzada.
    """
    if unidade_id is None:
        return true()

    turma_da_unidade = (
        select(Inscricao.id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .where(
            Inscricao.aluno_id == Aluno.id,
            Turma.unidade_id == unidade_id,
        )
        .correlate(Aluno)
        .exists()
    )
    turma_de_outra_unidade = (
        select(Inscricao.id)
        .join(Turma, Turma.id == Inscricao.turma_id)
        .where(
            Inscricao.aluno_id == Aluno.id,
            Turma.unidade_id.is_not(None),
            Turma.unidade_id != unidade_id,
        )
        .correlate(Aluno)
        .exists()
    )
    return or_(
        Aluno.unidade_id == unidade_id,
        and_(
            Aluno.unidade_id.is_(None),
            turma_da_unidade,
            ~turma_de_outra_unidade,
        ),
    )


def unidade_efetiva_aluno():
    """Unidade própria ou unidade única derivável pelas turmas inscritas."""
    unidade_derivada = (
        select(func.min(Turma.unidade_id))
        .join(Inscricao, Inscricao.turma_id == Turma.id)
        .where(
            Inscricao.aluno_id == Aluno.id,
            Turma.unidade_id.is_not(None),
        )
        .group_by(Inscricao.aluno_id)
        .having(func.count(func.distinct(Turma.unidade_id)) == 1)
        .correlate(Aluno)
        .scalar_subquery()
    )
    return func.coalesce(Aluno.unidade_id, unidade_derivada)


def ids_alunos_enturmados(
    unidade_id: int | None = None,
    periodo_letivo_id: int | None = None,
) -> set[int]:
    """Conjunto distinto de alunos enturmados.

    `unidade_id`: escopo do chamador quando ele já filtra por unidade (as
    telas de registro filtram pela unidade da sessão); `None` cruza unidades
    (mesmo comportamento antigo de `PeriodoLetivo.alunos_enturmados`, que só
    restringe pelo período). `periodo_letivo_id`: restringe às turmas do
    período (como fazia o join por `Aluno.turmas` nos consumidores antigos).
    """
    q = db.session.query(Aluno.id).filter(
        cond_aluno_enturmado(periodo_letivo_id=periodo_letivo_id)
    )
    if unidade_id is not None:
        q = q.filter(cond_aluno_no_escopo_unidade(unidade_id))
    return {row[0] for row in q.distinct().all()}


def contar_alunos_enturmados(
    unidade_id: int | None = None,
    periodo_letivo_id: int | None = None,
) -> int:
    """Total de alunos ENTURMADOS (distintos) no escopo — mesma fonte dos
    cards, da property do período e das equivalências de teste."""
    return len(
        ids_alunos_enturmados(
            unidade_id=unidade_id,
            periodo_letivo_id=periodo_letivo_id,
        )
    )


__all__ = [
    "cond_oferta_efetiva",
    "cond_inscricao_enturmada",
    "cond_aluno_enturmado",
    "ids_alunos_enturmados",
    "contar_alunos_enturmados",
]

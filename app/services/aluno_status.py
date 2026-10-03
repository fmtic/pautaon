"""Classifica alunos por período a partir do histórico de inscrições."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import and_, case, func, or_

from app.database import db
from app.models import Aluno, Inscricao, PeriodoLetivo, Turma
from app.models.enums import JANELA_RENOVACAO_DIAS, StatusAluno
from app.utils.timezone import get_local_now

TURNOS_CONHECIDOS = ("Manhã", "Tarde", "Noite", "EAD")


def _normalizar_data_ref(data_ref: date | None) -> date:
    if data_ref is None:
        return get_local_now().date()
    if isinstance(data_ref, datetime):
        return data_ref.date()
    if not isinstance(data_ref, date):
        raise TypeError("data_ref deve ser uma data.")
    return data_ref


def _periodo_anterior(periodo: PeriodoLetivo) -> PeriodoLetivo | None:
    return (
        PeriodoLetivo.query
        .filter(
            PeriodoLetivo.unidade_id == periodo.unidade_id,
            PeriodoLetivo.data_inicio < periodo.data_inicio,
        )
        .order_by(PeriodoLetivo.data_inicio.desc(), PeriodoLetivo.id.desc())
        .first()
    )


def periodos_de_referencia_bi(
    periodo_letivo_id: int | None,
    unidade_id: int | None,
    data_ref: date,
) -> list[PeriodoLetivo]:
    if periodo_letivo_id is not None:
        periodo = db.session.get(PeriodoLetivo, periodo_letivo_id)
        if periodo is None:
            raise ValueError(f"Período letivo {periodo_letivo_id} não encontrado.")
        if unidade_id is not None and periodo.unidade_id != unidade_id:
            raise ValueError("O período letivo não pertence à unidade informada.")
        return [periodo]

    query = PeriodoLetivo.query.filter(
        PeriodoLetivo.ativo.is_(True),
        PeriodoLetivo.data_inicio <= data_ref,
        PeriodoLetivo.data_fim >= data_ref,
    )
    if unidade_id is not None:
        query = query.filter(PeriodoLetivo.unidade_id == unidade_id)

    vigentes_por_unidade = {}
    for periodo in query.order_by(
        PeriodoLetivo.unidade_id,
        PeriodoLetivo.data_inicio.desc(),
        PeriodoLetivo.id.desc(),
    ).all():
        vigentes_por_unidade.setdefault(periodo.unidade_id, periodo)
    return list(vigentes_por_unidade.values())


def _ids_coorte_turno(periodo: PeriodoLetivo, turno: str) -> set[int]:
    if turno == "Outros":
        filtro_turno = or_(
            Turma.turno.is_(None),
            Turma.turno == "",
            Turma.turno.notin_(TURNOS_CONHECIDOS),
        )
    else:
        filtro_turno = Turma.turno == turno

    ids = {
        row[0]
        for row in (
            db.session.query(Inscricao.aluno_id)
            .join(Turma, Inscricao.turma_id == Turma.id)
            .filter(Turma.periodo_letivo_id == periodo.id, filtro_turno)
            .distinct()
            .all()
        )
    }
    anterior = _periodo_anterior(periodo)
    if anterior is not None:
        ids.update(
            row[0]
            for row in db.session.query(Inscricao.aluno_id)
            .join(Turma, Inscricao.turma_id == Turma.id)
            .filter(Turma.periodo_letivo_id == anterior.id, filtro_turno)
            .distinct()
            .all()
        )
    return ids


def status_alunos_para_bi(
    periodo_letivo_id: int | None = None,
    unidade_id: int | None = None,
    turno: str | None = None,
    data_ref: date | None = None,
) -> dict[int, StatusAluno]:
    """Resolve o escopo global da Central e classifica alunos em lote.

    Sem período explícito, usa o período ativo vigente em D de cada unidade.
    Se houver períodos sobrepostos na unidade, escolhe o de início mais
    recente. Com filtro de turno, a coorte vem das inscrições em P ou P-1
    nesse turno; a classificação usa o histórico completo do aluno.
    """
    data_ref = _normalizar_data_ref(data_ref)
    periodos = periodos_de_referencia_bi(periodo_letivo_id, unidade_id, data_ref)
    resultado = {}

    for periodo in periodos:
        ids_coorte = (
            _ids_coorte_turno(periodo, turno)
            if turno
            else None
        )
        if ids_coorte is not None and not ids_coorte:
            continue
        resultado.update(
            status_alunos(
                periodo.id,
                data_ref=data_ref,
                aluno_ids=list(ids_coorte) if ids_coorte is not None else None,
            )
        )

    return resultado


def status_aluno(
    aluno_id: int,
    periodo_id: int,
    data_ref: date | None = None,
) -> StatusAluno | None:
    """Retorna o status do aluno no período, ou None se estiver inativo/fora da unidade."""
    return status_alunos(
        periodo_id=periodo_id,
        data_ref=data_ref,
        aluno_ids=[aluno_id],
    ).get(aluno_id)


def status_alunos(
    periodo_id: int,
    data_ref: date | None = None,
    aluno_ids: list[int] | None = None,
) -> dict[int, StatusAluno]:
    """Classifica em lote os alunos ativos da unidade do período.

    Para a data corrente (ou futura), considera `Inscricao.ativo`. Para datas
    passadas, reconstrói o vínculo pelo intervalo de início e desativação.
    Inscrições históricas são consideradas mesmo quando inativas.
    """
    periodo = db.session.get(PeriodoLetivo, periodo_id)
    if periodo is None:
        raise ValueError(f"Período letivo {periodo_id} não encontrado.")

    data_ref = _normalizar_data_ref(data_ref)

    requested_ids = set(aluno_ids) if aluno_ids is not None else None
    if requested_ids == set():
        return {}

    alunos_query = Aluno.query.filter(
        Aluno.unidade_id == periodo.unidade_id,
        Aluno.ativo.is_(True),
    )
    if requested_ids is not None:
        alunos_query = alunos_query.filter(Aluno.id.in_(requested_ids))
    ids_ativos = [row[0] for row in alunos_query.with_entities(Aluno.id).all()]
    if not ids_ativos:
        return {}

    periodo_anterior = _periodo_anterior(periodo)

    if data_ref < get_local_now().date():
        limite_desativacao = datetime.combine(data_ref, time.min)
        inscricao_ate_data = Inscricao.data_inicio <= data_ref
        vinculo_em_data = and_(
            inscricao_ate_data,
            or_(
                Inscricao.data_desativacao.is_(None),
                Inscricao.data_desativacao > limite_desativacao,
            ),
        )
    else:
        inscricao_ate_data = True
        vinculo_em_data = Inscricao.ativo.is_(True)

    inscricoes_periodo = (
        db.session.query(
            Inscricao.aluno_id,
            func.min(
                case(
                    (inscricao_ate_data, Inscricao.data_inicio),
                    else_=None,
                )
            ),
            func.max(case((vinculo_em_data, 1), else_=0)),
        )
        .join(Turma, Inscricao.turma_id == Turma.id)
        .filter(
            Turma.periodo_letivo_id == periodo.id,
            Inscricao.aluno_id.in_(ids_ativos),
        )
        .group_by(Inscricao.aluno_id)
        .all()
    )
    primeira_inscricao = {
        aluno_id: data
        for aluno_id, data, _ in inscricoes_periodo
        if data is not None
    }
    enturmados_em_data = {
        aluno_id
        for aluno_id, _, ativo_em_data in inscricoes_periodo
        if ativo_em_data
    }

    historico_anterior = {}
    if periodo_anterior is not None:
        historico_anterior = {
            aluno_id: (teve_anterior, teve_periodo_anterior)
            for aluno_id, teve_anterior, teve_periodo_anterior in (
                db.session.query(
                    Inscricao.aluno_id,
                    func.max(case((Turma.periodo_letivo_id == periodo_anterior.id, 1), else_=0)),
                    func.max(case((PeriodoLetivo.id.isnot(None), 1), else_=0)),
                )
                .join(Turma, Inscricao.turma_id == Turma.id)
                .join(PeriodoLetivo, Turma.periodo_letivo_id == PeriodoLetivo.id)
                .filter(
                    PeriodoLetivo.unidade_id == periodo.unidade_id,
                    PeriodoLetivo.data_inicio < periodo.data_inicio,
                    Inscricao.aluno_id.in_(ids_ativos),
                )
                .group_by(Inscricao.aluno_id)
                .all()
            )
        }

    fim_janela = periodo.data_inicio + timedelta(days=JANELA_RENOVACAO_DIAS)
    status: dict[int, StatusAluno] = {}
    ids_com_inscricao_periodo = set(primeira_inscricao)

    for aluno_id in ids_ativos:
        teve_periodo_anterior, teve_algum_anterior = historico_anterior.get(
            aluno_id, (0, 0)
        )

        if aluno_id in enturmados_em_data:
            if not teve_algum_anterior:
                status[aluno_id] = StatusAluno.NOVO
            elif (
                teve_periodo_anterior
                and primeira_inscricao[aluno_id] <= fim_janela
            ):
                status[aluno_id] = StatusAluno.RENOVADO
            else:
                status[aluno_id] = StatusAluno.RETORNANTE
        elif aluno_id in ids_com_inscricao_periodo:
            status[aluno_id] = StatusAluno.DESENTURMADO
        elif teve_periodo_anterior:
            status[aluno_id] = (
                StatusAluno.EM_JANELA
                if data_ref <= fim_janela
                else StatusAluno.NAO_RENOVADO
            )
        else:
            status[aluno_id] = StatusAluno.OUTROS

    return status


__all__ = [
    'periodos_de_referencia_bi',
    'status_aluno',
    'status_alunos',
    'status_alunos_para_bi',
]
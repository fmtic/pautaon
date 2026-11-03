"""Rota do painel pedagógico; só orquestra."""

from __future__ import annotations

from datetime import date

from flask import abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.models import Aluno, Inscricao, PeriodoLetivo, Turma
from app.services.enturmado import cond_aluno_no_escopo_unidade
from app.services.aluno_status import periodos_de_referencia_bi
from app.services.conselho_leitura import rotulo_oferta
from app.utils.logica import get_unidade_id

from .. import bp_relatorios
from ..shared import ROLES_RELATORIOS
from . import ficha_aluno as ficha_aluno_svc
from . import periodo as periodo_view
from . import turma as turma_view


def _escolher_periodo(
    periodos: list[PeriodoLetivo],
    periodo_id: int | None,
    unidade_id: int | None,
) -> PeriodoLetivo:
    if periodo_id:
        for p in periodos:
            if p.id == periodo_id:
                return p

    hoje = date.today()
    try:
        ativos = periodos_de_referencia_bi(
            periodo_letivo_id=None,
            unidade_id=unidade_id,
            data_ref=hoje,
        )
    except TypeError:
        ativos = []

    for p in ativos:
        if p.data_inicio and p.data_fim and p.data_inicio <= hoje <= p.data_fim:
            return p

    for p in periodos:
        if p.data_inicio and p.data_fim and p.data_inicio <= hoje <= p.data_fim:
            return p

    return periodos[0]


@bp_relatorios.route("/painel")
@login_required
def painel_pedagogico():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()
    turma_id = request.args.get("turma_id", type=int)
    periodo_id = request.args.get("periodo_letivo_id", type=int)

    periodos_q = PeriodoLetivo.query
    if unidade_id:
        periodos_q = periodos_q.filter_by(unidade_id=unidade_id)
    periodos = periodos_q.options(joinedload(PeriodoLetivo.unidade)).order_by(PeriodoLetivo.data_inicio.desc()).all()

    if not periodos:
        return render_template(
            "relatorios/painel_pedagogico.html",
            periodos=[],
            periodo=None,
            turma=None,
            visao_periodo=None,
            visao_turma=None,
            turmas_periodo=[],
        )

    periodo = _escolher_periodo(periodos, periodo_id, unidade_id)

    turmas_periodo = (
        Turma.query.filter_by(periodo_letivo_id=periodo.id, ativo=True)
        .order_by(Turma.nome)
        .all()
    )

    turma = None
    visao_turma = None
    visao_periodo = None

    if turma_id:
        turma = next((t for t in turmas_periodo if t.id == turma_id), None)
        if turma:
            visao_turma = turma_view.montar(turma, unidade_id)

    if visao_turma is None:
        visao_periodo = periodo_view.montar(periodo, unidade_id)

    return render_template(
        "relatorios/painel_pedagogico.html",
        periodos=periodos,
        periodo=periodo,
        turmas_periodo=turmas_periodo,
        turma=turma,
        visao_periodo=visao_periodo,
        visao_turma=visao_turma,
    )


# -----------------------------------------------------------------------------
# Busca de alunos (enturmados OU não no período) — alimenta a ficha 360°
# Endpoint: relatorios.busca_alunos
# -----------------------------------------------------------------------------
@bp_relatorios.route("/painel/busca")
@login_required
def busca_alunos():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()
    q = (request.args.get("q") or "").strip()
    periodo_id = request.args.get("periodo_letivo_id", type=int)

    if unidade_id is None:
        return render_template(
            "relatorios/busca_alunos.html",
            q=q,
            periodo=None,
            vinculos=[],
            erro="Unidade não identificada",
        )

    periodo = None
    if periodo_id:
        periodo = PeriodoLetivo.query.filter_by(
            id=periodo_id, unidade_id=unidade_id
        ).first()

    vinculos: list[dict] = []
    if q:
        like = f"%{q}%"
        alunos = (
            Aluno.query.filter(
                cond_aluno_no_escopo_unidade(unidade_id),
                (Aluno.nome.ilike(like)) | (Aluno.nome_social.ilike(like)),
            )
            .order_by(Aluno.nome)
            .limit(50)
            .all()
        )
        for a in alunos:
            insc = (
                Inscricao.query.join(Turma, Turma.id == Inscricao.turma_id)
                .filter(
                    Inscricao.aluno_id == a.id,
                    Inscricao.ativo.is_(True),
                    Turma.unidade_id == unidade_id,
                )
                .order_by(Inscricao.data_inicio.desc())
                .first()
            )
            t = insc.turma if insc else None
            vinculos.append(
                {
                    "aluno": a,
                    "turma": t,
                    "inscricao": insc,
                    "enturmado_no_periodo": (
                        t is not None
                        and periodo is not None
                        and t.periodo_letivo_id == periodo.id
                    ),
                }
            )

    return render_template(
        "relatorios/busca_alunos.html",
        q=q,
        periodo=periodo,
        vinculos=vinculos,
    )


# -----------------------------------------------------------------------------
# Ficha 360° do aluno
# Endpoint: relatorios.ficha_aluno_view
# -----------------------------------------------------------------------------
def _inscricoes_da_turma(aluno_id: int, turma_id: int) -> list[Inscricao]:
    """Inscrições ATIVAS do aluno na turma, em ordem estável (D5.5)."""
    return (
        Inscricao.query.options(joinedload(Inscricao.turma_curso))
        .filter_by(aluno_id=aluno_id, turma_id=turma_id, ativo=True)
        .order_by(Inscricao.id)
        .all()
    )


def _resolver_oferta(
    candidatas: list[Inscricao],
    atual: Inscricao | None,
    oferta_sel: int | None,
) -> Inscricao | None:
    """Escolhe a inscrição (aluno × oferta) que a ficha retrata (D5.5/M1).

    Com uma inscrição por turma o comportamento anterior não muda; com 2+
    ofertas, `?oferta_sel=` decide e só vale se casar com uma inscrição do
    aluno naquela turma. Sem escolha válida, mantém a inscrição entregue.
    """
    if len(candidatas) <= 1:
        return atual or (candidatas[0] if candidatas else None)
    if oferta_sel is not None:
        for candidata in candidatas:
            if candidata.turma_curso_id == oferta_sel:
                return candidata
    return atual or candidatas[0]


@bp_relatorios.route("/alunos/<int:aluno_id>/ficha")
@login_required
def ficha_aluno_view(aluno_id):
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()

    aluno = Aluno.query.filter_by(
        id=aluno_id,
        unidade_id=unidade_id,
    ).first_or_404()

    oferta_sel = request.args.get("oferta_sel", type=int)
    turma_id = request.args.get("turma_id", type=int)
    if turma_id:
        turma = Turma.query.filter_by(id=turma_id, unidade_id=unidade_id).first_or_404()
        candidatas = _inscricoes_da_turma(aluno.id, turma.id)
        if not candidatas:
            abort(404, "Aluno não inscrito nesta turma.")
        insc = _resolver_oferta(candidatas, None, oferta_sel)
    else:
        insc = (
            Inscricao.query.options(joinedload(Inscricao.turma_curso))
            .filter_by(aluno_id=aluno.id, ativo=True)
            .order_by(Inscricao.data_inicio.desc())
            .first()
        )
        if not insc:
            abort(
                404,
                "Aluno sem turma vigente. Use a busca para ver "
                "a ficha de uma turma anterior.",
            )
        turma = insc.turma
        candidatas = _inscricoes_da_turma(aluno.id, turma.id)
        insc = _resolver_oferta(candidatas, insc, oferta_sel)

    ctx = ficha_aluno_svc.montar(aluno, turma, insc)
    # D5.5: seletor de oferta — só aparece com 2+ inscrições na mesma turma.
    ctx["ofertas_disponiveis"] = [
        {
            "turma_curso_id": candidata.turma_curso_id,
            "rotulo": rotulo_oferta(candidata.turma_curso, turma),
        }
        for candidata in candidatas
    ]
    ctx["oferta_sel"] = insc.turma_curso_id if insc is not None else None

    ctx["contexto_restrito"]["permitido"] = current_user.role in {
        "admin",
        "pedagogico",
        "servico_social",
        "secretaria",
        "gerencia",
    }

    return render_template("relatorios/ficha_aluno.html", **ctx)

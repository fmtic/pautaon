"""Diário de Observações em modo global (a partir do Painel Pedagógico).

Lista os registros de `registro_aula` de todas as turmas do período, com
filtros por período letivo, turma, curso (oferta) e professor. É restrito aos
perfis que já acessam o Painel Pedagógico (`ROLES_RELATORIOS`); o fluxo por
turma (`registros.ver_observacoes`) continua com o seu próprio acesso.

Sem migration: a rota só lê `registro_aula`/`turma`/`turma_curso`.
"""

from __future__ import annotations

from flask import abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload

from app.models import PeriodoLetivo, RegistroAula, Turma, TurmaCurso, User
from app.utils.logica import get_unidade_id

from . import bp_relatorios
from .painel_pedagogico.rota import _escolher_periodo
from .shared import ROLES_RELATORIOS

# Teto de linhas por consulta: o diário pode ter milhares de registros e a
# tela é de leitura/inspeção. Acima disso o usuário refina os filtros.
LIMITE = 500


def _texto_preenchido(coluna):
    """Mesmo critério da listagem por turma: NULL e vazio não contam."""
    return and_(coluna.isnot(None), coluna != "")


def _turmas_do_periodo(periodo_id, unidade_id):
    query = Turma.query.filter_by(periodo_letivo_id=periodo_id, ativo=True)
    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)
    return query.order_by(Turma.nome).all()


def _ofertas_das_turmas(turmas):
    ids = [t.id for t in turmas]
    if not ids:
        return []
    return (
        TurmaCurso.query.filter(
            TurmaCurso.turma_id.in_(ids),
            TurmaCurso.ativo.is_(True),
        )
        .order_by(TurmaCurso.id)
        .all()
    )


def _professores_das_turmas(turmas, ofertas):
    """Professores que de fato atendem as turmas/ofertas filtradas."""
    ids = {t.professor_id for t in turmas if t.professor_id}
    ids |= {o.professor_id for o in ofertas if o.professor_id}
    if not ids:
        return []
    return User.query.filter(User.id.in_(ids)).order_by(User.name).all()


@bp_relatorios.route("/observacoes")
@login_required
def observacoes():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()

    periodos_q = PeriodoLetivo.query
    if unidade_id:
        periodos_q = periodos_q.filter_by(unidade_id=unidade_id)
    periodos = periodos_q.order_by(PeriodoLetivo.data_inicio.desc()).all()

    if not periodos:
        return render_template(
            "turmas/observacoes.html",
            modo_global=True,
            periodos=[], periodo=None, turma=None, turmas_periodo=[],
            ofertas=[], professores=[], historico=[], mostrar_curso=True,
            truncado=False, limite=LIMITE,
        )

    periodo = _escolher_periodo(
        periodos, request.args.get("periodo_letivo_id", type=int), unidade_id,
    )
    turmas_periodo = _turmas_do_periodo(periodo.id, unidade_id)

    # Turma fora do período/unidade é ignorada (volta para "todas").
    turma_id = request.args.get("turma_id", type=int)
    turma = next((t for t in turmas_periodo if t.id == turma_id), None)

    # Curso só faz sentido dentro da turma escolhida (filtro encadeado).
    ofertas = _ofertas_das_turmas([turma] if turma else turmas_periodo)
    oferta_id = request.args.get("turma_curso_id", type=int)
    oferta = next((o for o in ofertas if o.id == oferta_id), None)

    professores = _professores_das_turmas(turmas_periodo, ofertas)
    professor_id = request.args.get("professor_id", type=int)
    professor = next((p for p in professores if p.id == professor_id), None)

    query = (
        RegistroAula.query
        .join(Turma, Turma.id == RegistroAula.turma_id)
        .outerjoin(TurmaCurso, TurmaCurso.id == RegistroAula.turma_curso_id)
        .filter(
            Turma.periodo_letivo_id == periodo.id,
            Turma.ativo.is_(True),
            or_(
                _texto_preenchido(RegistroAula.observacoes),
                _texto_preenchido(RegistroAula.atividades),
            ),
        )
        .options(
            joinedload(RegistroAula.turma_rel).joinedload(Turma.professor),
            joinedload(RegistroAula.turma_curso).joinedload(TurmaCurso.curso),
            joinedload(RegistroAula.instrutor),
            joinedload(RegistroAula.temas),
        )
    )
    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)
    if turma:
        query = query.filter(RegistroAula.turma_id == turma.id)
    if oferta:
        query = query.filter(RegistroAula.turma_curso_id == oferta.id)
    if professor:
        # Professor da oferta quando houver; senão, o da turma (registro legado).
        query = query.filter(
            func.coalesce(TurmaCurso.professor_id, Turma.professor_id)
            == professor.id
        )

    registros = (
        query
        .order_by(RegistroAula.data.desc(), Turma.nome, RegistroAula.id)
        .limit(LIMITE + 1)
        .all()
    )
    truncado = len(registros) > LIMITE

    return render_template(
        "turmas/observacoes.html",
        modo_global=True,
        periodos=periodos, periodo=periodo,
        turma=turma, turmas_periodo=turmas_periodo,
        ofertas=ofertas, oferta=oferta,
        professores=professores, professor=professor,
        historico=registros[:LIMITE], obs=registros[:LIMITE],
        mostrar_curso=True, truncado=truncado, limite=LIMITE,
    )

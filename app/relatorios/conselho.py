"""Consolidação dos resultados do conselho de classe por período letivo."""

from flask import abort, render_template, request
from flask_login import current_user, login_required

from app.models import ConfiguracaoSistema, ConselhoClasse, Frequencia, Inscricao, PeriodoLetivo, Turma
from app.utils.logica import calcular_estatisticas_frequencia, get_unidade_id

from . import bp_relatorios
from .shared import ROLES_RELATORIOS


@bp_relatorios.route("/conselho")
@login_required
def resultado_conselho():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()
    periodo_id = request.args.get("periodo_letivo_id", type=int)
    turmas_all = request.args.get("turmas_all") == "1"
    turmas_ids = request.args.getlist("turmas", type=int)

    periodos_query = PeriodoLetivo.query
    if unidade_id:
        periodos_query = periodos_query.filter_by(unidade_id=unidade_id)
    periodos = periodos_query.order_by(PeriodoLetivo.nome).all()

    periodo_selecionado = None
    periodos_turmas = []
    selected_turma_ids = []
    registros = []
    turma_count = 0
    aluno_count = 0
    resumo_status = {}
    conselho_inicio = None
    conselho_fim = None

    if periodo_id:
        periodo_selecionado = PeriodoLetivo.query.get(periodo_id)
        if periodo_selecionado:
            turmas_query = Turma.query.filter_by(periodo_letivo_id=periodo_id, ativo=True)
            if unidade_id:
                turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
            periodos_turmas = turmas_query.order_by(Turma.nome).all()

            if turmas_all:
                selected_turma_ids = [t.id for t in periodos_turmas]
            else:
                selected_turma_ids = turmas_ids

            if selected_turma_ids:
                conselho_query = ConselhoClasse.query.filter(
                    ConselhoClasse.etapa == "FINAL",
                    ConselhoClasse.turma_id.in_(selected_turma_ids)
                )
                conselhos = conselho_query.all()

                for cons in conselhos:
                    aluno = cons.aluno
                    turma = cons.turma
                    if not aluno or not turma:
                        continue

                    inscricao = Inscricao.query.filter_by(
                        aluno_id=aluno.id, turma_id=turma.id
                    ).first()
                    nivel_aluno = inscricao.nivel if inscricao and inscricao.nivel else aluno.nivel or "-"

                    freq_conceitos = [
                        f.conceito for f in
                        Frequencia.query.filter_by(aluno_id=aluno.id, turma_id=turma.id).all()
                    ]
                    estatisticas = calcular_estatisticas_frequencia(freq_conceitos)
                    presenca_pct = estatisticas.get("presenca_percentual", 0)

                    proxima = cons.proxima_turma_obj.nome if cons.proxima_turma_obj else "-"

                    registros.append({
                        "turma": turma.nome,
                        "programa": turma.programa or "-",
                        "professor": turma.professor.name if turma.professor else "-",
                        "aluno": aluno.nome_social or aluno.nome,
                        "nivel": nivel_aluno,
                        "presenca": presenca_pct,
                        "situacao_final": cons.situacao_final or "Sem Registro",
                        "proxima_turma": proxima,
                    })
                turma_count = len(set(cons.turma_id for cons in conselhos))
                aluno_count = len(set(cons.aluno_id for cons in conselhos))

                situacoes = {}
                for cons in conselhos:
                    sit = cons.situacao_final or "Sem Registro"
                    situacoes[sit] = situacoes.get(sit, 0) + 1
                total = len(conselhos)
                for sit, cnt in situacoes.items():
                    resumo_status[sit] = {"count": cnt, "percent": round(cnt / total * 100, 1) if total else 0}
                resumo_status["total"] = total

        try:
            conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho').first()
            conf_fim = ConfiguracaoSistema.query.filter_by(chave='fim_conselho').first()
            if conf_inicio:
                conselho_inicio = conf_inicio.valor
            if conf_fim:
                conselho_fim = conf_fim.valor
        except Exception:
            pass

    return render_template(
        "relatorios/resultado_conselho.html",
        periodos=periodos,
        selected_periodo_id=periodo_id,
        periodo_selecionado=periodo_selecionado,
        periodos_turmas=periodos_turmas,
        selected_turma_ids=selected_turma_ids,
        selected_all_turmas=turmas_all,
        registros=registros,
        turma_count=turma_count,
        aluno_count=aluno_count,
        resumo_status=resumo_status,
        conselho_inicio=conselho_inicio,
        conselho_fim=conselho_fim,
    )

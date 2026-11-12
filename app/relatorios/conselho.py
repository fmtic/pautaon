"""Consolidação dos resultados do conselho de classe por período letivo.

D5.4: o resultado é POR OFERTA (etapa FINAL). Alunos vêm de
`Inscricao.turma_curso_id` e a frequência de `Frequencia.turma_curso_id`; o
seletor de oferta segue o padrão M1 — turma com 1 oferta ativa usa direto,
2+ exigem `?oferta_sel=` e turma sem oferta ativa recusa com aviso. O
isolamento por unidade vale para todos os perfis (filtro pela unidade da
sessão, como os demais leitores).
"""

from collections import defaultdict

from flask import abort, render_template, request
from flask_login import current_user, login_required
from sqlalchemy.orm import joinedload

from app.models import (
    Aluno,
    ConfiguracaoSistema,
    ConselhoClasse,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
)
from app.services.conselho_leitura import (
    cond_conselho_sem_conteudo,
    rotulo_oferta,
)
from app.services.turma_curso import ofertas_ativas
from app.utils.logica import calcular_estatisticas_frequencia, get_unidade_id

from . import bp_relatorios
from .shared import ROLES_RELATORIOS


def _resolver_ofertas(turmas, oferta_sel):
    """Resolve as ofertas do relatório (padrão M1).

    - Uma turma: 0 ativa → recusa com aviso; 1 → usa direto; 2+ → exige
      `oferta_sel` válido (senão devolve a lista para o seletor).
    - Várias turmas / "todas": considera todas as ofertas ativas.

    Devolve `(ofertas, exigir_escolha, mensagem)`.
    """
    if len(turmas) == 1:
        turma = turmas[0]
        ativas = ofertas_ativas(turma.id)
        if not ativas:
            return [], False, (
                f"A turma {turma.nome} não possui curso (oferta) ativa; "
                "não há resultado de conselho por oferta."
            )
        if len(ativas) == 1:
            if oferta_sel is not None and oferta_sel != ativas[0].id:
                return [], False, "A oferta escolhida não é uma oferta ativa desta turma."
            return ativas, False, None
        escolhida = next((o for o in ativas if o.id == oferta_sel), None)
        if escolhida is None:
            return ativas, True, (
                "Esta turma tem mais de um curso ativo. Selecione o curso "
                "(oferta) para ver o resultado do conselho."
            )
        return [escolhida], False, None

    ofertas = []
    for turma in turmas:
        ofertas.extend(ofertas_ativas(turma.id))
    if not ofertas:
        return [], False, (
            "Nenhuma das turmas selecionadas possui curso (oferta) ativa."
        )
    return ofertas, False, None


@bp_relatorios.route("/conselho")
@login_required
def resultado_conselho():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    unidade_id = get_unidade_id()
    periodo_id = request.args.get("periodo_letivo_id", type=int)
    turmas_all = request.args.get("turmas_all") == "1"
    turmas_ids = request.args.getlist("turmas", type=int)
    oferta_sel = request.args.get("oferta_sel", type=int)

    periodos_query = PeriodoLetivo.query
    if unidade_id:
        periodos_query = periodos_query.filter_by(unidade_id=unidade_id)
    periodos = periodos_query.order_by(PeriodoLetivo.nome).all()

    periodo_selecionado = None
    periodos_turmas = []
    selected_turma_ids = []
    ofertas_disponiveis = []
    exigir_escolha = False
    mensagem = None
    registros = []
    turma_count = 0
    aluno_count = 0
    resumo_status = {}
    conselho_inicio = None
    conselho_fim = None

    if periodo_id:
        periodo_query = PeriodoLetivo.query.filter_by(id=periodo_id)
        if unidade_id:
            periodo_query = periodo_query.filter_by(unidade_id=unidade_id)
        periodo_selecionado = periodo_query.first()
        if periodo_selecionado:
            turmas_query = Turma.query.filter_by(
                periodo_letivo_id=periodo_id, ativo=True
            )
            if unidade_id:
                turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
            periodos_turmas = turmas_query.order_by(Turma.nome).all()

            if turmas_all:
                selected_turma_ids = [t.id for t in periodos_turmas]
            else:
                selected_turma_ids = turmas_ids

            turmas_sel = [t for t in periodos_turmas if t.id in selected_turma_ids]
            if turmas_sel:
                ofertas, exigir_escolha, mensagem = _resolver_ofertas(
                    turmas_sel, oferta_sel
                )
                if exigir_escolha:
                    # 2+ ofertas sem escolha: mostra só o seletor, sem dados
                    # (não mistura cursos na mesma tabela).
                    ofertas_disponiveis = ofertas
                    ofertas = []

                oferta_ids = [o.id for o in ofertas]
                # AJ20: casca FINAL sem conteúdo equivale a linha ausente.
                conselhos = (
                    ConselhoClasse.query.filter(
                        ConselhoClasse.etapa == "FINAL",
                        ConselhoClasse.turma_curso_id.in_(oferta_ids),
                        ~cond_conselho_sem_conteudo(),
                    ).all()
                    if oferta_ids
                    else []
                )
                ofertas_map = (
                    {
                        o.id: o
                        for o in TurmaCurso.query.options(
                            joinedload(TurmaCurso.curso),
                            joinedload(TurmaCurso.turma),
                        )
                        .filter(TurmaCurso.id.in_(oferta_ids))
                        .all()
                    }
                    if oferta_ids
                    else {}
                )

                # Aluno, inscrição e frequência em LOTE (sem N+1 por linha).
                # `ConselhoClasse` não tem relationship `aluno` — só `turma`.
                aluno_ids = {cons.aluno_id for cons in conselhos}
                alunos_map = (
                    {
                        a.id: a
                        for a in Aluno.query.filter(Aluno.id.in_(aluno_ids)).all()
                    }
                    if aluno_ids
                    else {}
                )
                inscricoes_map = {}
                freq_map = defaultdict(list)
                if aluno_ids and oferta_ids:
                    for inscricao in (
                        Inscricao.query.filter(
                            Inscricao.aluno_id.in_(aluno_ids),
                            Inscricao.turma_curso_id.in_(oferta_ids),
                        )
                        .order_by(Inscricao.id)
                        .all()
                    ):
                        chave = (inscricao.aluno_id, inscricao.turma_curso_id)
                        atual = inscricoes_map.get(chave)
                        if atual is None or (inscricao.ativo and not atual.ativo):
                            inscricoes_map[chave] = inscricao
                    for freq in Frequencia.query.filter(
                        Frequencia.aluno_id.in_(aluno_ids),
                        Frequencia.turma_curso_id.in_(oferta_ids),
                    ).all():
                        freq_map[(freq.aluno_id, freq.turma_curso_id)].append(
                            freq.conceito
                        )

                for cons in conselhos:
                    aluno = alunos_map.get(cons.aluno_id)
                    oferta = ofertas_map.get(cons.turma_curso_id)
                    turma = oferta.turma if oferta is not None else cons.turma
                    if aluno is None or oferta is None or turma is None:
                        # Linha legada/sem oferta nunca é exibida (D5.4).
                        continue

                    # Alunos da OFERTA: inscrição na própria oferta.
                    inscricao = inscricoes_map.get((aluno.id, oferta.id))
                    if inscricao is None:
                        continue
                    nivel_aluno = inscricao.nivel or aluno.nivel or "-"

                    estatisticas = calcular_estatisticas_frequencia(
                        freq_map.get((aluno.id, oferta.id), [])
                    )
                    presenca_pct = estatisticas.get("presenca_percentual", 0)

                    proxima = (
                        cons.proxima_turma_obj.nome if cons.proxima_turma_obj else "-"
                    )

                    registros.append({
                        "turma": turma.nome,
                        "curso": oferta.curso.nome if oferta.curso else "-",
                        "oferta": rotulo_oferta(oferta),
                        "programa": oferta.programa or turma.programa or "-",
                        "professor": (
                            oferta.professor.name if oferta.professor
                            else (turma.professor.name if turma.professor else "-")
                        ),
                        "aluno": aluno.nome_social or aluno.nome,
                        "nivel": nivel_aluno,
                        "presenca": presenca_pct,
                        "situacao_final": cons.situacao_final or "Sem Registro",
                        "proxima_turma": proxima,
                    })
                turma_count = len({cons.turma_curso_id for cons in conselhos})
                aluno_count = len({cons.aluno_id for cons in conselhos})

                situacoes = {}
                for cons in conselhos:
                    sit = cons.situacao_final or "Sem Registro"
                    situacoes[sit] = situacoes.get(sit, 0) + 1
                total = len(conselhos)
                for sit, cnt in situacoes.items():
                    resumo_status[sit] = {
                        "count": cnt,
                        "percent": round(cnt / total * 100, 1) if total else 0,
                    }
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
        selected_oferta_id=oferta_sel,
        ofertas_disponiveis=ofertas_disponiveis,
        exigir_escolha=exigir_escolha,
        mensagem=mensagem,
        registros=registros,
        turma_count=turma_count,
        aluno_count=aluno_count,
        resumo_status=resumo_status,
        conselho_inicio=conselho_inicio,
        conselho_fim=conselho_fim,
    )

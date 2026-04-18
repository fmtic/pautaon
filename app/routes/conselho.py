from flask import Blueprint, render_template, request, redirect, flash, abort, url_for, jsonify
from flask_login import login_required, current_user
from app.models import (PerguntaConselho, Turma, Aluno, Frequencia,
                    OpcaoProximaTurma, ConselhoClasse, ConselhoResposta, Inscricao)
from app.database import db
from sqlalchemy import select, case
from datetime import datetime, date
from collections import OrderedDict
from app.utils.logica import get_unidade_id

bp = Blueprint('conselho', __name__)

# ---------------------------------------------------------------------------
# PAINEL GERAL
# ---------------------------------------------------------------------------

@bp.route('/conselho')
@login_required
def index_conselho():
    unidade_id = get_unidade_id()
    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)
        
    lista_programas = [p for p in db.session.execute(stmt_prog).scalars().all() if p]

    programa_ativo = request.args.get('programa', 'Todos')
    turno_ativo    = request.args.get('turno', 'Todos')

    stmt = select(Turma).where(Turma.ativo == True)
    if unidade_id:
        stmt = stmt.where(Turma.unidade_id == unidade_id)
        
    if programa_ativo != 'Todos':
        stmt = stmt.where(Turma.programa == programa_ativo)
    if turno_ativo != 'Todos':
        stmt = stmt.where(Turma.turno == turno_ativo)
    if current_user.role not in ['admin', 'pedagogico', 'gerencia']:
        stmt = stmt.where(Turma.professor_id == current_user.id)

    turmas = db.session.execute(stmt).scalars().all()

    return render_template('conselho/painel.html',
                           turmas=turmas,
                           lista_programas=lista_programas,
                           programa_ativo=programa_ativo,
                           turno_ativo=turno_ativo)


# ---------------------------------------------------------------------------
# GERENCIAMENTO DE PERGUNTAS
# ---------------------------------------------------------------------------

@bp.route('/conselho/perguntas')
@login_required
def gerenciar_perguntas():
    if current_user.role not in ['pedagogico', 'admin', 'gerencia']:
        abort(403)

    ordem_manual = ['INICIAL', 'PERCURSO', 'FINAL']

    ordem_etapas = case(
        {'INICIAL': 1, 'PERCURSO': 2, 'FINAL': 3},
        value=PerguntaConselho.etapa
    )
    
    unidade_id = get_unidade_id()
    query = PerguntaConselho.query.filter_by(ativo=True).order_by(ordem_etapas)
    # PerguntaConselho é global — perguntas são compartilhadas entre unidades
    perguntas_raw = query.all()

    # Agrupa preservando a ordem manual
    perguntas_agrupadas = OrderedDict()
    for etapa in ordem_manual:
        lista = [p for p in perguntas_raw if p.etapa == etapa]
        if lista:
            perguntas_agrupadas[etapa] = lista

    return render_template('conselho/perguntas.html', perguntas_agrupadas=perguntas_agrupadas)


@bp.route('/conselho/pergunta/salvar', methods=['POST'])
@login_required
def salvar_pergunta():
    if current_user.role not in ['pedagogico', 'admin', 'gerencia']:
        abort(403)

    pergunta_id = request.form.get('id')
    etapa  = request.form.get('etapa')
    tipo   = request.form.get('tipo')
    texto  = request.form.get('texto')
    opcoes = request.form.get('opcoes')

    if pergunta_id:
        pergunta        = db.get_or_404(PerguntaConselho, int(pergunta_id))
        pergunta.etapa  = etapa
        pergunta.tipo   = tipo
        pergunta.texto  = texto
        pergunta.opcoes = opcoes
    else:
        db.session.add(PerguntaConselho(
            etapa=etapa,
            tipo=tipo,
            texto=texto,
            opcoes=opcoes,
        ))

    db.session.commit()
    flash("Pergunta salva com sucesso!", "success")
    return redirect(url_for('conselho.gerenciar_perguntas'))


@bp.route('/conselho/pergunta/excluir/<int:id>')
@login_required
def excluir_pergunta(id):
    if current_user.role not in ['pedagogico', 'admin', 'gerencia']:
        abort(403)

    pergunta = db.get_or_404(PerguntaConselho, id)
    pergunta.ativo = False
    db.session.commit()
    flash("Pergunta removida com sucesso!", "info")
    return redirect(url_for('conselho.gerenciar_perguntas'))


# ---------------------------------------------------------------------------
# LANÇAMENTO DO CONSELHO
# ---------------------------------------------------------------------------

@bp.route('/conselho/lancamento')
@login_required
def lancamento_conselho():
    turma_id = request.args.get('turma')
    etapa    = request.args.get('etapa', 'INICIAL')
    programa_filtro = request.args.get('programa', 'Todos')
    turno_filtro    = request.args.get('turno', 'Todos')

    unidade_id = get_unidade_id()
    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)
    lista_programas = db.session.execute(stmt_prog).scalars().all()

    opcoes_proximas = OpcaoProximaTurma.query.filter_by(ativo=True).all()

    if current_user.role in ['admin', 'pedagogico', 'gerencia']:
        stmt = select(Turma).where(Turma.ativo == True)
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)
            
        if programa_filtro != 'Todos':
            stmt = stmt.where(Turma.programa == programa_filtro)
        if turno_filtro != 'Todos':
            stmt = stmt.where(Turma.turno == turno_filtro)
    else:
        stmt = select(Turma).where(
            Turma.professor_id == current_user.id, Turma.ativo == True
        )
    turmas_para_select = db.session.execute(stmt).scalars().all()

    # Sem turma selecionada: renderiza apenas os filtros
    if not turma_id:
        return render_template('conselho/lancamento.html',
                               turmas=turmas_para_select,
                               lista_programas=lista_programas,
                               programa_ativo=programa_filtro,
                               turno_ativo=turno_filtro, # Adicione este
                               etapa=etapa,
                               turma=None)

    turma_obj = db.get_or_404(Turma, turma_id)

    # --- Bloqueia lançamento se não tiver alunos ---
    alunos = Aluno.query.join(Inscricao).filter(
        Inscricao.turma_id == turma_id,
        Inscricao.ativo == True,
        Aluno.ativo == True
    ).order_by(Aluno.nome).all()
    if not alunos:
        flash(f'Não é possível abrir o conselho: A turma {turma_obj.nome} não possui alunos ativos.', 'warning')
        return redirect(url_for('conselho.lancamento_conselho', 
                            programa=programa_filtro, 
                            turno=turno_filtro,
                            etapa=etapa))

    # Busca ou cria registros de conselho por aluno para a etapa
    for aluno in alunos:
        existe = ConselhoClasse.query.filter_by(
            turma_id=turma_id,
            aluno_id=aluno.id,
            etapa=etapa
        ).first()
        if not existe:
            db.session.add(ConselhoClasse(
                turma_id=turma_id,
                aluno_id=aluno.id,
                etapa=etapa,
                unidade_id=get_unidade_id()
            ))
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Erro ao inicializar conselho: {e}', 'danger')
        return redirect(url_for('conselho.lancamento_conselho', etapa=etapa))

    # Usa o primeiro registro para referência de conselho_id nas respostas
    conselho = ConselhoClasse.query.filter_by(
        turma_id=turma_id, etapa=etapa
    ).first()

    turma = Turma.query.get_or_404(turma_id)
    alunos = Aluno.query.join(Inscricao).filter(
        Inscricao.turma_id == turma_id,
        Inscricao.ativo == True,
        Aluno.ativo == True
    ).order_by(Aluno.nome).all()
    perguntas = PerguntaConselho.query.filter_by(etapa=etapa, ativo=True).all()

    respostas_db = ConselhoResposta.query.join(ConselhoClasse).filter(
        ConselhoClasse.turma_id == turma_id,
        ConselhoClasse.etapa == etapa
    ).all()
    respostas_map = {f"{r.aluno_id}_{r.pergunta_id}": r.resposta for r in respostas_db}

    return render_template('conselho_lancamento.html',
                           turma=turma_obj,
                           alunos=alunos,
                           perguntas=perguntas,
                           etapa=etapa,
                           conselho=conselho,
                           respostas=respostas_map,
                           turmas=turmas_para_select,
                           lista_programas=lista_programas,
                           programa_ativo=programa_filtro,
                           turno_ativo=turno_filtro,
                           opcoes_proximas_turmas=opcoes_proximas)


@bp.route('/conselho/salvar', methods=['POST'])
@login_required
def salvar_conselho():
    turma_id = request.form.get('turma_id')
    etapa    = request.form.get('etapa')

    if not turma_id or not etapa:
        flash("Dados insuficientes para salvar.", "warning")
        return redirect(url_for('conselho.lancamento_conselho'))

    data_inicio = request.form.get('data_inicio')
    data_fim    = request.form.get('data_fim')

    conselhos_turma = ConselhoClasse.query.filter_by(
        turma_id=int(turma_id), etapa=etapa
    ).all()
    conselho_map = {c.aluno_id: c for c in conselhos_turma}

    for c in conselhos_turma:
        if data_inicio:
            c.data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
        if data_fim:
            c.data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()

    for key, value in request.form.items():
        aluno_id    = None
        pergunta_id = None

        if key.startswith('resp_turma_'):
            pergunta_id = int(key.replace('resp_turma_', ''))
        elif key.startswith('resp_'):
            parts = key.split('_')
            if len(parts) >= 3:
                aluno_id    = int(parts[1])
                pergunta_id = int(parts[2])

        if pergunta_id is None:
            continue

        conselho = conselho_map.get(aluno_id) or (conselhos_turma[0] if conselhos_turma else None)
        if not conselho:
            continue

        resposta = ConselhoResposta.query.filter_by(
            conselho_id=conselho.id,
            aluno_id=aluno_id,
            pergunta_id=pergunta_id
        ).first()

        if resposta:
            resposta.resposta = value
        else:
            db.session.add(ConselhoResposta(
                conselho_id=conselho.id,
                aluno_id=aluno_id,
                pergunta_id=pergunta_id,
                resposta=value
            ))

    db.session.commit()
    flash("Conselho atualizado com sucesso!", "success")
    return redirect(url_for('conselho.lancamento_conselho',
                            turma=turma_id, etapa=etapa))


# ---------------------------------------------------------------------------
# FECHAMENTO DE TURMA
# ---------------------------------------------------------------------------

@bp.route('/conselho/fechamento/<int:turma_id>')
@login_required
def fechamento_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    
    # CORREÇÃO DO ERRO: Filtramos a lista usando Python (List Comprehension)
    alunos = [aluno for aluno in turma.alunos if aluno.ativo]

    # BLOQUEIO: Se não houver alunos ativos, não prossegue para os cálculos
    if not alunos:
        flash(f'A turma "{turma.nome}" não possui alunos ativos para fechamento.', 'warning')
        return redirect(url_for('conselho.lancamento_conselho'))

    proximas_turmas = [
        "Vela-Básico", "Vela-Intermediário", "Vela-Avançado",
        "Profissionalizante", "Canoagem-Básica", "Canoagem-Intermediária",
        "Canoagem-Avançada", "Windsurf-Básico", "Windsurf-Intermediário",
        "Windsurf-Avançado", "Outro"
    ]

    dados_alunos = []
    for aluno in alunos:
        # Aqui o código segue seu fluxo normal de cálculo de frequência...
        registros = Frequencia.query.filter_by(aluno_id=aluno.id).all()
        total = len(registros)

        counts = {'A': 0, 'B': 0, 'C': 0, 'D': 0, 'F': 0, 'J': 0}
        for r in registros:
            if r.conceito in counts:
                counts[r.conceito] += 1

        def perc(qtd):
            return round((qtd / total * 100), 1) if total > 0 else 0

        dados_alunos.append({
            'obj':      aluno,
            'counts':   counts,
            'percs':    {k: perc(v) for k, v in counts.items()},
            'presenca': perc(counts['A'] + counts['B'] + counts['C'] + counts['D']),
            'falta':    perc(counts['F'])
        })

    return render_template('conselho/fechamento.html',
                           turma=turma,
                           dados=dados_alunos,
                           opcoes_turma=proximas_turmas)


@bp.route('/fechamento/<int:turma_id>/salvar', methods=['POST'])
@login_required
def salvar_fechamento_data(turma_id):
    """Salva situação final de cada aluno via JSON (chamada pelo JS)."""
    data     = request.get_json()
    registros = data.get('dados', [])

    try:
        for item in registros:
            p_turma_id = item.get('proxima_turma_id')
            if p_turma_id in ("", "None", None):
                p_turma_id = None

            conselho = ConselhoClasse.query.filter_by(
                turma_id=turma_id,
                aluno_id=item['aluno_id'],
                etapa='FINAL'
            ).first()

            if not conselho:
                conselho = ConselhoClasse(
                    turma_id=turma_id,
                    aluno_id=item['aluno_id'],
                    etapa='FINAL',
                    data_inicio=date.today(),
                    instrutor_id=current_user.id,
                    unidade_id=get_unidade_id()
                )
                db.session.add(conselho)

            conselho.situacao_final         = item['situacao']
            conselho.proxima_turma_id       = p_turma_id
            conselho.concluido              = True
            conselho.data_fim               = date.today()

        db.session.commit()
        return jsonify({"success": True})

    except Exception as e:
        db.session.rollback()
        print(f"Erro no salvamento: {str(e)}")
        return jsonify({"success": False, "message": str(e)})


# ---------------------------------------------------------------------------
# AVALIAÇÃO GERAL DA TURMA (feita pelo professor)
# ---------------------------------------------------------------------------

@bp.route('/turma/<int:turma_id>/avaliacao', methods=['GET', 'POST'])
@login_required
def avaliar_turma(turma_id):
    turma = db.get_or_404(Turma, turma_id)

    if current_user.role == 'professor' and turma.professor_id != current_user.id:
        abort(403)

    etapa_selecionada = request.args.get('etapa', 'INICIAL')
    perguntas = PerguntaConselho.query.filter_by(
        tipo='TURMA', etapa=etapa_selecionada, ativo=True
    ).all()
    respostas = {}

    if request.method == 'POST':
        # TODO: implementar salvamento das respostas de avaliação da turma
        flash(f"Avaliação da turma {turma.nome} salva!", "success")
        return redirect(url_for('registros.painel_professor'))

    return render_template('conselho/turma_aval.html',
                           turma=turma,
                           etapa_atual=etapa_selecionada,
                           perguntas=perguntas,
                           respostas=respostas)

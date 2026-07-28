import json
import logging

from flask import Blueprint, render_template, request, redirect, flash, abort, url_for, jsonify
from flask_login import login_required, current_user
from app.models import (PerguntaConselho, Turma, Aluno, Frequencia,
                    OpcaoProximaTurma, ConselhoClasse, ConselhoResposta, Inscricao)
from app.database import db
from sqlalchemy import select, case
from datetime import datetime, date
from collections import OrderedDict
from app.utils.logica import get_unidade_id

logger = logging.getLogger(__name__)
bp = Blueprint('conselho', __name__)


def _build_turma_avaliacao_payload(form_data, perguntas) -> str:
    """Serializa respostas de avaliação da turma em JSON, ignorando campos vazios.

    Este fluxo usa os campos de avaliação já previstos no modelo de Turma para
    preservar a estrutura atual do sistema acadêmico sem introduzir uma nova tabela.
    """
    respostas = {}
    for pergunta in perguntas:
        campo = f"resp_turma_{pergunta.id}"
        valor = form_data.get(campo, "")
        if valor is None:
            continue
        valor_limpo = str(valor).strip()
        if valor_limpo:
            respostas[str(pergunta.id)] = valor_limpo
    return json.dumps(respostas, ensure_ascii=False)


def _get_turma_avaliacao_respostas(turma: Turma, etapa: str) -> dict:
    """Recupera respostas previamente gravadas para a avaliação da turma de uma etapa."""
    campos = {
        "INICIAL": "avaliacao_inicial",
        "PERCURSO": "avaliacao_percurso",
        "FINAL": "avaliacao_final",
    }
    valor = getattr(turma, campos.get(etapa, "avaliacao_inicial"), "") or ""
    if not valor:
        return {}

    try:
        dados = json.loads(valor)
    except (TypeError, json.JSONDecodeError):
        return {}

    if not isinstance(dados, dict):
        return {}
    return {str(chave): str(valor_item) for chave, valor_item in dados.items() if valor_item}


def _normalize_conselho_request(form_data) -> dict:
    """Normaliza os campos do formulário de conselho para evitar valores inválidos.

    Esta função é usada para padronizar entradas vindas do formulário antes do
    processamento, preservando o fluxo atual do sistema acadêmico sem novos módulos.
    """
    normalized = {
        "turma_id": None,
        "etapa": form_data.get("etapa", "INICIAL"),
        "data_inicio": form_data.get("data_inicio", ""),
        "data_fim": form_data.get("data_fim", ""),
        "respostas": {},
    }

    turma_id = form_data.get("turma_id", "")
    if turma_id not in (None, ""):
        try:
            normalized["turma_id"] = int(str(turma_id).strip())
        except ValueError:
            normalized["turma_id"] = None

    for key, value in form_data.items():
        if key.startswith("resp_turma_"):
            pergunta_id = key.replace("resp_turma_", "")
            if pergunta_id:
                normalized["respostas"][f"turma_{pergunta_id}"] = str(value).strip()
        elif key.startswith("resp_"):
            parts = key.split("_")
            if len(parts) >= 3:
                aluno_id = parts[1]
                pergunta_id = parts[2]
                if aluno_id and pergunta_id:
                    normalized["respostas"][f"{aluno_id}_{pergunta_id}"] = str(value).strip()

    return normalized

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

    return render_template('conselho/lancamento.html',
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
    normalized = _normalize_conselho_request(request.form)
    turma_id = normalized["turma_id"]
    etapa = normalized["etapa"]

    if not turma_id or not etapa:
        flash("Dados insuficientes para salvar.", "warning")
        return redirect(url_for('conselho.lancamento_conselho'))

    data_inicio = normalized["data_inicio"]
    data_fim = normalized["data_fim"]

    conselhos_turma = ConselhoClasse.query.filter_by(
        turma_id=turma_id, etapa=etapa
    ).all()
    conselho_map = {c.aluno_id: c for c in conselhos_turma}

    for c in conselhos_turma:
        if data_inicio:
            try:
                c.data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data inicial inválido.", "warning")
                return redirect(url_for('conselho.lancamento_conselho', turma=turma_id, etapa=etapa))
        if data_fim:
            try:
                c.data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data final inválido.", "warning")
                return redirect(url_for('conselho.lancamento_conselho', turma=turma_id, etapa=etapa))

    for key, value in normalized["respostas"].items():
        aluno_id = None
        pergunta_id = None

        if key.startswith('turma_'):
            pergunta_id = int(key.replace('turma_', ''))
        else:
            parts = key.split('_')
            if len(parts) >= 2:
                aluno_id = int(parts[0])
                pergunta_id = int(parts[1])

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
        # Aqui o código segue seu fluxo normal de cálculo de frequência para esta turma
        registros = Frequencia.query.filter_by(aluno_id=aluno.id, turma_id=turma.id).all()
        if not registros:
            registros = Frequencia.query.filter_by(aluno_id=aluno.id, turma_id=None).all()
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
        logger.exception("Erro no salvamento do fechamento da turma %s", turma_id)
        return jsonify({"success": False, "message": "Falha ao salvar o fechamento da turma. Veja o log para detalhes."})


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
    respostas = _get_turma_avaliacao_respostas(turma, etapa_selecionada)

    if request.method == 'POST':
        # Nota técnica: a avaliação geral da turma é persistida no próprio registro da turma
        # para manter compatibilidade com o modelo acadêmico já existente e evitar uma nova tabela.
        try:
            payload = _build_turma_avaliacao_payload(request.form, perguntas)
            campos = {
                "INICIAL": "avaliacao_inicial",
                "PERCURSO": "avaliacao_percurso",
                "FINAL": "avaliacao_final",
            }
            setattr(turma, campos[etapa_selecionada], payload)
            db.session.add(turma)
            db.session.commit()
            flash(f"Avaliação da turma {turma.nome} salva!", "success")
            return redirect(url_for('registros.painel_professor'))
        except Exception:
            db.session.rollback()
            logger.exception("Falha ao salvar avaliação da turma %s", turma_id)
            flash("Não foi possível salvar a avaliação da turma. Tente novamente.", "danger")

    return render_template('conselho/turma_aval.html',
                           turma=turma,
                           etapa_atual=etapa_selecionada,
                           perguntas=perguntas,
                           respostas=respostas)

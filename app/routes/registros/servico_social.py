from datetime import datetime

from flask import current_app, flash, redirect, request, url_for, render_template, Blueprint
from flask_login import current_user, login_required

from app.database import db
from app.models import AgendaServicoSocial, RespostaFormulario, Aluno
from app.services.calendar_service import get_calendar_service

bp = Blueprint('servico_social', __name__, url_prefix='/servico-social')


@bp.route("/agendar-entrevista", methods=["POST"])
@login_required
def agendar_entrevista():
    if current_user.role not in ["admin", "secretaria", "servico_social"]:
        flash("Você não tem permissão para realizar agendamentos.", "danger")
        return redirect(url_for("main.dashboard"))

    titulo = request.form.get("titulo")
    data = request.form.get("data")
    hora = request.form.get("hora")
    categoria = request.form.get("categoria")
    local_encontro = request.form.get("localizacao")
    descricao_texto = request.form.get("descricao")
    participantes_input = request.form.get("participantes")

    if not all([titulo, data, hora, categoria]):
        flash("Por favor, preencha todos os campos obrigatórios.", "warning")
        return redirect(url_for("main.dashboard"))

    start_iso = f"{data}T{hora}:00-03:00"
    hora_fim_int = (int(hora[:2]) + 1) % 24
    end_iso = f"{data}T{hora_fim_int:02d}{hora[2:]}:00-03:00"

    event = {
        "summary": f"[{categoria}] {titulo}",
        "location": local_encontro or "Projeto Grael - Serviço Social",
        "description": f"{descricao_texto}\n\nRegistrado por: {current_user.name}",
        "start": {"dateTime": start_iso, "timeZone": "America/Sao_Paulo"},
        "end": {"dateTime": end_iso, "timeZone": "America/Sao_Paulo"},
        "reminders": {
            "useDefault": False,
            "overrides": [{"method": "popup", "minutes": 60}],
        },
    }

    if participantes_input:
        lista_emails = [email.strip() for email in participantes_input.split(",") if "@" in email]
        event["attendees"] = [{"email": email} for email in lista_emails]
    else:
        event["attendees"] = []

    try:
        service = get_calendar_service()
        calendar_id = current_app.config.get("GOOGLE_CALENDAR_ID")
        if not service or not calendar_id:
            flash("Integração com Google Calendar não configurada.", "danger")
            return redirect(url_for("main.dashboard"))

        created_event = service.events().insert(
            calendarId=calendar_id,
            body=event,
            sendUpdates="all",
        ).execute()

        db.session.add(
            AgendaServicoSocial(
                titulo=titulo,
                categoria=categoria,
                data=datetime.strptime(data, "%Y-%m-%d").date(),
                hora=hora,
                localizacao=local_encontro,
                descricao=descricao_texto,
                google_event_id=created_event.get("id"),
                participantes_emails=participantes_input,
                user_id=current_user.id,
            )
        )
        db.session.commit()
        flash("Agendamento sincronizado e salvo com sucesso!", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao sincronizar agendamento com Google Calendar.")
        flash("Erro na sincronização do agendamento.", "danger")

    return redirect(url_for("main.dashboard"))


@bp.route("/excluir-agendamento/<int:id>")
@login_required
def excluir_agendamento(id):
    agendamento = AgendaServicoSocial.query.get_or_404(id)

    try:
        service = get_calendar_service()
        calendar_id = current_app.config.get("GOOGLE_CALENDAR_ID")
        if service and calendar_id and agendamento.google_event_id:
            service.events().delete(
                calendarId=calendar_id,
                eventId=agendamento.google_event_id,
            ).execute()

        db.session.delete(agendamento)
        db.session.commit()
        flash("Agendamento removido do sistema e do Google Calendar.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao remover agendamento.")
        flash("Erro ao remover o agendamento.", "danger")

    return redirect(url_for("main.dashboard"))

# Dicionário com os tipos de formulário e seus respectivos templates
FORMULARIOS = {
    'notificacao': {
        'template': 'servico_social/forms/notificacao_violencia.html',
        'titulo': 'Ficha de Notificação de Maus Tratos/Violência'
    },
    'socioeconomica': {
        'template': 'servico_social/forms/socioeconomica.html',
        'titulo': 'Ficha de Análise Socioeconômica'
    },
    'atendimento_social': {
        'template': 'servico_social/forms/atendimento_social.html',
        'titulo': 'Ficha de Atendimento Social'
    },
    'profissionalizante_30': {
        'template': 'servico_social/forms/profissionalizante_30.html',
        'titulo': 'Entrevista Profissionalizante – 30+'
    },
    'profissionalizante_geral': {
        'template': 'servico_social/forms/profissionalizante_geral.html',
        'titulo': 'Entrevista para Curso Profissionalizante'
    },
    'plano_individual': {
        'template': 'servico_social/forms/plano_individual_trans.html',
        'titulo': 'Plano Individual / Atendimento para Crianças e Adolescentes Trans'
    }
}

@bp.route('/entrevistas')
@login_required
def listar_entrevistas():
    if current_user.role not in ['servico_social', 'admin']:
        abort(403)
    respostas = RespostaFormulario.query.filter_by(usuario_id=current_user.id)\
                .order_by(RespostaFormulario.created_at.desc()).all()
    # Se quiser mostrar todos os formulários (independente de quem preencheu), remova o filter_by.
    return render_template('servico_social/entrevistas.html', respostas=respostas)

@bp.route('/entrevistas/<tipo>', methods=['GET', 'POST'])
@login_required
def preencher_formulario(tipo):
    if current_user.role not in ['servico_social', 'admin']:
        abort(403)
    
    if tipo not in FORMULARIOS:
        flash('Formulário não encontrado.', 'warning')
        return redirect(url_for('servico_social.listar_entrevistas'))
    
    # Buscar lista de alunos ativos para um campo de seleção (opcional)
    alunos = Aluno.query.filter_by(ativo=True).order_by(Aluno.nome).all()
    
    if request.method == 'POST':
        dados = dict(request.form)
        dados.pop('csrf_token', None)   # remove o token do formulário
        
        aluno_id = dados.get('aluno_id')
        if aluno_id and aluno_id.isdigit():
            aluno_id = int(aluno_id)
        else:
            aluno_id = None
        
        resposta = RespostaFormulario(
            tipo_formulario=tipo,
            aluno_id=aluno_id,
            usuario_id=current_user.id,
            dados=dados
        )
        db.session.add(resposta)
        db.session.flush()          # para obter o id antes do commit
        numero_ocorrencia = f"{datetime.now().year}/{resposta.id:05d}"
        # Armazena no campo 'dados' ou em um campo específico
        dados['numero_ocorrencia'] = numero_ocorrencia
        resposta.dados = dados      # atualiza o JSON com o número gerado
        db.session.commit()
        flash('Formulário salvo com sucesso!', 'success')
        return redirect(url_for('servico_social.listar_entrevistas'))
    
    # GET: exibe o formulário vazio
    return render_template(
        FORMULARIOS[tipo]['template'],
        titulo=FORMULARIOS[tipo]['titulo'],
        alunos=alunos,
        tipo=tipo
    )

@bp.route('/aluno/<int:aluno_id>/dados')
@login_required
def dados_aluno(aluno_id):
    """Retorna os dados do aluno em JSON para preenchimento automático."""
    if current_user.role not in ['servico_social', 'admin']:
        abort(403)
    
    aluno = Aluno.query.get_or_404(aluno_id)
    
    # Extrai dados estruturados dos campos e JSONs
    dados = {
        'id': aluno.id,
        'nome': aluno.nome,
        'nome_social': aluno.nome_social or '',
        'data_nascimento': aluno.data_nascimento.strftime('%Y-%m-%d') if aluno.data_nascimento else '',
        'idade': aluno.idade,
        'sexo': aluno.diversidade_json.get('genero', ''),
        'raca_cor': aluno.diversidade_json.get('raca_cor', ''),
        'mae': aluno.identificacao_json.get('nome_mae', ''),
        'pai': aluno.identificacao_json.get('nome_pai', ''),
        'responsavel_nome': aluno.identificacao_json.get('responsavel_nome', ''),
        'parentesco_responsavel': aluno.identificacao_json.get('responsavel_parentesco', ''),
        'endereco': aluno.identificacao_json.get('endereco_completo', ''),
        'telefone': aluno.whatsapp or aluno.identificacao_json.get('telefone', ''),
        'turmas': [t.nome for t in aluno.turmas if t.ativo],
        'escola': aluno.escolaridade_json.get('escola_nome', ''),
        'serie': aluno.escolaridade_json.get('serie', ''),
        'turno': aluno.escolaridade_json.get('turno', ''),
        'deficiencia': aluno.diversidade_json.get('deficiencia_descricao', ''),
        'foto_url': url_for('static', filename=aluno.foto_path) if aluno.foto_path else url_for('static', filename='img/default.png')
    }
    
    return dados  # Flask retorna JSON automaticamente se for um dicionário

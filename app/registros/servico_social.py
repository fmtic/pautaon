"""
Serviço Social: agendamentos no Google Calendar + formulários dinâmicos
+ dossiê do aluno para preenchimento automático.

ONDA 3B
    `dados_aluno()` lê das tabelas novas via `get_perfil_completo`.
"""

from datetime import datetime

from flask import (
    current_app,
    flash,
    redirect,
    request,
    url_for,
    render_template,
    Blueprint,
    abort,
)
from flask_login import current_user, login_required

from app.database import db
from app.models import AgendaServicoSocial, RespostaFormulario, Aluno
from app.services.aluno_perfil import get_perfil_completo
from app.services.calendar_service import get_calendar_service
from app.utils.timezone import get_local_now

bp = Blueprint("servico_social", __name__, url_prefix="/servico-social")


# =============================================================================
# AGENDAMENTOS
# =============================================================================

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
        lista_emails = [
            email.strip() for email in participantes_input.split(",") if "@" in email
        ]
        event["attendees"] = [{"email": email} for email in lista_emails]
    else:
        event["attendees"] = []

    try:
        service = get_calendar_service()
        calendar_id = current_app.config.get("GOOGLE_CALENDAR_ID")
        if not service or not calendar_id:
            flash("Integração com Google Calendar não configurada.", "danger")
            return redirect(url_for("main.dashboard"))

        created_event = (
            service.events()
            .insert(calendarId=calendar_id, body=event, sendUpdates="all")
            .execute()
        )

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
        current_app.logger.exception(
            "Falha ao sincronizar agendamento com Google Calendar."
        )
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


# =============================================================================
# FORMULÁRIOS DINÂMICOS
# =============================================================================

FORMULARIOS = {
    "notificacao": {
        "template": "servico_social/forms/notificacao_violencia.html",
        "titulo": "Ficha de Notificação de Maus Tratos/Violência",
    },
    "socioeconomica": {
        "template": "servico_social/forms/socioeconomica.html",
        "titulo": "Ficha de Análise Socioeconômica",
    },
    "atendimento_social": {
        "template": "servico_social/forms/atendimento_social.html",
        "titulo": "Ficha de Atendimento Social",
    },
    "profissionalizante_30": {
        "template": "servico_social/forms/profissionalizante_30.html",
        "titulo": "Entrevista Profissionalizante – 30+",
    },
    "profissionalizante_geral": {
        "template": "servico_social/forms/profissionalizante_geral.html",
        "titulo": "Entrevista para Curso Profissionalizante",
    },
    "plano_individual": {
        "template": "servico_social/forms/plano_individual_trans.html",
        "titulo": "Plano Individual / Atendimento para Crianças e Adolescentes Trans",
    },
}


@bp.route("/entrevistas")
@login_required
def listar_entrevistas():
    if current_user.role not in ["servico_social", "admin"]:
        abort(403)
    respostas = (
        RespostaFormulario.query.filter_by(usuario_id=current_user.id)
        .order_by(RespostaFormulario.created_at.desc())
        .all()
    )
    return render_template("servico_social/entrevistas.html", respostas=respostas)


@bp.route("/entrevistas/<tipo>", methods=["GET", "POST"])
@login_required
def preencher_formulario(tipo):
    if current_user.role not in ["servico_social", "admin"]:
        abort(403)

    if tipo not in FORMULARIOS:
        flash("Formulário não encontrado.", "warning")
        return redirect(url_for("servico_social.listar_entrevistas"))

    alunos = Aluno.query.filter_by(ativo=True).order_by(Aluno.nome).all()

    if request.method == "POST":
        dados = dict(request.form)
        dados.pop("csrf_token", None)

        aluno_id = dados.get("aluno_id")
        if aluno_id and aluno_id.isdigit():
            aluno_id = int(aluno_id)
        else:
            aluno_id = None

        resposta = RespostaFormulario(
            tipo_formulario=tipo,
            aluno_id=aluno_id,
            usuario_id=current_user.id,
            dados=dados,
        )
        db.session.add(resposta)
        db.session.flush()
        numero_ocorrencia = f"{datetime.now().year}/{resposta.id:05d}"
        dados["numero_ocorrencia"] = numero_ocorrencia
        resposta.dados = dados
        db.session.commit()
        flash("Formulário salvo com sucesso!", "success")
        return redirect(url_for("servico_social.listar_entrevistas"))

    dados_vazio = {}
    return render_template(
        FORMULARIOS[tipo]["template"],
        titulo=FORMULARIOS[tipo]["titulo"],
        alunos=alunos,
        tipo=tipo,
        now=get_local_now(),
        dados_preenchidos=dados_vazio,
        modo_impressao=False,
    )


# =============================================================================
# DOSSIÊ DO ALUNO (preenchimento automático de formulários)
# =============================================================================

def _montar_endereco_completo(perfil_endereco: dict) -> str:
    """Junta rua, número, bairro, cidade, uf em uma única string legível."""
    partes = [
        perfil_endereco.get("rua"),
        perfil_endereco.get("numero"),
        perfil_endereco.get("bairro"),
        perfil_endereco.get("cidade"),
        perfil_endereco.get("uf"),
    ]
    partes = [p for p in partes if p]
    return ", ".join(partes)


@bp.route("/aluno/<int:aluno_id>/dados")
@login_required
def dados_aluno(aluno_id):
    """
    Retorna os dados do aluno em JSON para preenchimento automático.

    ONDA 3B: lê das tabelas estruturadas via `get_perfil_completo`.
    Campos sem correspondência na estrutura nova (ex.: `serie`,
    `deficiencia_descricao`) leem do JSON legado como fallback.
    """
    if current_user.role not in ["servico_social", "admin"]:
        abort(403)

    aluno = Aluno.query.get_or_404(aluno_id)
    perfil = get_perfil_completo(aluno)

    ident = perfil["identificacao"]
    div = perfil["diversidade"]
    socio = perfil["socioeconomico"]
    resp = perfil["responsavel"]
    end = perfil["endereco"]

    # SituacaoEscolar cobre escola/série/turno (a JSON `escolaridade_json`
    # só tem `doc_entregue` e nunca teve esses dados reais).
    situacao = aluno.situacao_escolar
    escola_nome = situacao.nome_instituicao if situacao else ""
    serie = situacao.escolaridade if situacao else ""
    turno_escolar = situacao.turno if situacao else ""

    # `deficiencia_descricao` não tem coluna nova — só existe no JSON antigo.
    # Mantido por compatibilidade enquanto houver dado.
    deficiencia = (aluno.diversidade_json or {}).get("deficiencia_descricao", "")

    dados = {
        "id": aluno.id,
        "nome": aluno.nome,
        "nome_social": aluno.nome_social or "",
        "data_nascimento": (
            aluno.data_nascimento.strftime("%Y-%m-%d")
            if aluno.data_nascimento else ""
        ),
        "idade": aluno.idade,
        "sexo": div.get("genero", ""),
        "raca_cor": div.get("raca_cor", ""),
        "mae": ident.get("nome_mae", ""),
        "pai": ident.get("nome_pai", ""),
        "responsavel_nome": resp.get("nome", ""),
        "parentesco_responsavel": resp.get("tipo", ""),
        "endereco": _montar_endereco_completo(end),
        "telefone": aluno.whatsapp or resp.get("telefone", ""),
        "turmas": [t.nome for t in aluno.turmas if t.ativo],
        "escola": escola_nome,
        "serie": serie,
        "turno": turno_escolar,
        "deficiencia": deficiencia,
        "foto_url": (
            url_for("static", filename=aluno.foto_path)
            if aluno.foto_path
            else url_for("static", filename="img/default.png")
        ),
    }

    return dados


# =============================================================================
# IMPRESSÃO
# =============================================================================

@bp.route("/impressao/<int:resposta_id>")
@login_required
def gerar_impressao(resposta_id):
    if current_user.role not in ["servico_social", "admin"]:
        abort(403)

    resposta = RespostaFormulario.query.get_or_404(resposta_id)

    tipo = resposta.tipo_formulario
    if tipo not in FORMULARIOS:
        flash("Tipo de formulário inválido para impressão.", "danger")
        return redirect(url_for("servico_social.listar_entrevistas"))

    return render_template(
        FORMULARIOS[tipo]["template"],
        titulo=FORMULARIOS[tipo]["titulo"],
        dados_preenchidos=resposta.dados,
        aluno=resposta.aluno,
        alunos=[],
        modo_impressao=True,
        tipo=tipo,
    )
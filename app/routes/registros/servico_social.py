from datetime import datetime

from flask import current_app, flash, redirect, request, url_for
from flask_login import current_user, login_required

from app.database import db
from app.models import AgendaServicoSocial
from app.services.calendar_service import get_calendar_service
from . import bp


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

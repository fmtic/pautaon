from threading import Thread
from flask import current_app, request
from flask_mail import Message
from flask_login import current_user
from app.extensions import db, mail
from app.models.auditoria import LogAcao

def _gravar_log_background(app, acao, detalhes, context_data):
    """Grava o log na tabela LogAcao rodando de forma segura dentro da thread."""
    with app.app_context():
        try:
            log = LogAcao(
                usuario_id=context_data.get("usuario_id"),
                usuario_nome=context_data.get("usuario_nome"),
                acao=acao,
                detalhes=detalhes,
                ip=context_data.get("ip"),
                unidade_id=context_data.get("unidade_id")
            )
            db.session.add(log)
            db.session.commit()
        except Exception as e:
            app.logger.error(f"Erro ao salvar log de auditoria no background: {e}")


def send_async_email(app, msg, acao_descricao, context_data, is_alert_email=False):
    with app.app_context():
        try:
            mail.send(msg)
            
            if not is_alert_email:
                _gravar_log_background(
                    app,
                    acao="Disparo de E-mail",
                    detalhes=f"Sucesso: {acao_descricao} -> {', '.join(msg.recipients)}",
                    context_data=context_data
                )
        except Exception as e:
            app.logger.error(f"Falha no disparo de e-mail para {msg.recipients}: {e}")

            if not is_alert_email:
                _gravar_log_background(
                    app,
                    acao="Erro E-mail",
                    detalhes=f"Falha: {acao_descricao} -> {', '.join(msg.recipients)} | Erro: {str(e)[:100]}",
                    context_data=context_data
                )

                admin_email = app.config.get("ADMIN_EMAIL")
                if admin_email and admin_email not in msg.recipients:
                    _notificar_admin_sobre_falha(app, msg, str(e), admin_email, context_data)


def _notificar_admin_sobre_falha(app, msg_original, erro_str, admin_email, context_data):
    """Envia um e-mail de alerta para o administrador detalhando a falha no disparo."""
    try:
        alerta_msg = Message(
            subject=f"[pautaON ALERT] Falha ao enviar e-mail para {', '.join(msg_original.recipients)}",
            recipients=[admin_email],
        )
        alerta_msg.html = f"""
        <div style="font-family: sans-serif; padding: 20px; color: #333;">
            <h3 style="color: #c53030;">Aviso de Falha no Disparo de E-mail</h3>
            <p>Ocorreu um erro ao tentar enviar uma notificação do sistema local.</p>
            <ul>
                <li><strong>Assunto original:</strong> {msg_original.subject}</li>
                <li><strong>Destinatário(s) pretendido(s):</strong> {', '.join(msg_original.recipients)}</li>
                <li><strong>Erro retornado:</strong> <code>{erro_str}</code></li>
            </ul>
        </div>
        """
        send_async_email(app, alerta_msg, "Alerta de Falha Técnica", context_data, is_alert_email=True)
    except Exception as ex:
        app.logger.critical(f"Falha crítica: não foi possível notificar o admin por e-mail: {ex}")


def send_email(subject: str, recipients: list[str], body_html: str, acao_descricao: str = "Notificação") -> None:
    app = current_app._get_current_object()

    # Captura os dados do usuário ATUAL (antes de entrar na Thread em background)
    try:
        context_data = {
            "usuario_id": getattr(current_user, "id", None),
            "usuario_nome": getattr(current_user, "name", "Sistema (Background)") if current_user.is_authenticated else "Sistema",
            "unidade_id": getattr(current_user, "unidade_id", None),
            "ip": request.remote_addr if request else "127.0.0.1"
        }
    except RuntimeError:
        # Fallback caso a função seja chamada de um script CLI ou contexto puramente sem request
        context_data = {
            "usuario_id": None, "usuario_nome": "Sistema CLI", "unidade_id": None, "ip": "127.0.0.1"
        }

    msg = Message(subject=subject, recipients=recipients)
    msg.html = body_html

    Thread(target=send_async_email, args=(app, msg, acao_descricao, context_data)).start()
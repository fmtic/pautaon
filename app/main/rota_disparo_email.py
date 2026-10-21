from flask import jsonify, request
from app.main import bp
from app.utils.disparo_email import send_email

@bp.route("/teste-email")
def teste_email():
    destinatario = request.args.get("para", "seu_email@dominio.com")

    html_corpo = """
    <div style="font-family: sans-serif; padding: 20px; color: #333;">
        <h2 style="color: #0056b3;">PautaON - Teste de E-mail</h2>
        <p>Este é um e-mail de teste para validar a integração SMTP via Google Workspace.</p>
        <p>Se você recebeu esta mensagem, o envio assíncrono em segundo plano está <strong>funcionando corretamente</strong>!</p>
    </div>
    """

    send_email(
        subject="[PautaON] Teste de Disparo Assíncrono",
        recipients=[destinatario],
        body_html=html_corpo
    )

    return jsonify({
        "status": "sucesso",
        "mensagem": f"Solicitação de e-mail enviada para a fila de execução para o endereço {destinatario}."
    }), 200
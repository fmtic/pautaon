import logging
from config import Config
from google.apps import chat_v1
from google.oauth2 import service_account

# Configuração de Logs baseada no .env / Config
logging.basicConfig(level=getattr(logging, Config.NOTIFICADOR_LOG_LEVEL, logging.INFO))
logger = logging.getLogger(__name__)

def enviar_notificacao(mensagem: str, space_id: str):
    """Envia uma notificação para um espaço do Google Chat."""
    
    if Config.NOTIFICADOR_DRY_RUN:
        logger.info("[DRY RUN] Notificação não enviada; modo de simulação ativo.")
        return

    if not Config.GOOGLE_CHAT_SERVICE_ACCOUNT_FILE:
        logger.error("Caminho do ficheiro da conta de serviço não configurado.")
        return

    try:
        # Autenticação
        credentials = service_account.Credentials.from_service_account_file(
            Config.GOOGLE_CHAT_SERVICE_ACCOUNT_FILE, 
            scopes=Config.GOOGLE_CHAT_SCOPES
        )
        client = chat_v1.ChatServiceClient(credentials=credentials)

        # Envio da mensagem
        request = chat_v1.CreateMessageRequest(
            parent=f"spaces/{space_id}",
            message={"text": mensagem},
        )
        response = client.create_message(request=request)
        logger.info(f"Mensagem enviada com sucesso: {response.name}")

    except Exception as e:
        logger.error(f"Erro ao enviar mensagem no Google Chat: {e}")
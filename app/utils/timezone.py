from datetime import datetime
from zoneinfo import ZoneInfo

def get_local_now() -> datetime:
    """Retorna o horário atual no fuso America/Sao_Paulo (Brasília)."""
    return datetime.now(ZoneInfo("America/Sao_Paulo"))

from datetime import datetime, timedelta, timezone

try:
    from zoneinfo import ZoneInfo

    _LOCAL_TZ = ZoneInfo("America/Sao_Paulo")
except Exception:
    # Windows sem base IANA de fusos: UTC-3 (Brasília, sem horário de verão).
    _LOCAL_TZ = timezone(timedelta(hours=-3))


def get_local_now() -> datetime:
    """Retorna o horário atual no fuso America/Sao_Paulo (Brasília)."""
    return datetime.now(_LOCAL_TZ)

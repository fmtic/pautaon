from __future__ import annotations

from pathlib import Path

from flask import current_app


def get_calendar_service():
    """Monta o client do Google Calendar a partir da configuração ativa."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
    except ModuleNotFoundError:
        current_app.logger.warning(
            "Dependências do Google Calendar não estão instaladas no ambiente atual."
        )
        return None

    key_path_value = current_app.config.get("GOOGLE_SERVICE_ACCOUNT_FILE")
    if not key_path_value:
        return None

    key_path = Path(key_path_value)
    if not key_path.exists():
        current_app.logger.warning("Arquivo de credenciais Google não encontrado: %s", key_path)
        return None

    creds = service_account.Credentials.from_service_account_file(
        key_path,
        scopes=current_app.config["GOOGLE_CALENDAR_SCOPES"],
    )

    delegated_user = current_app.config.get("GOOGLE_CALENDAR_DELEGATED_USER")
    if delegated_user:
        creds = creds.with_subject(delegated_user)

    return build("calendar", "v3", credentials=creds)

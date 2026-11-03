import logging

from config import Config
from scripts.notificador import enviar_notificacao


def test_dry_run_does_not_log_notification_contents(monkeypatch, caplog):
    monkeypatch.setattr(Config, "NOTIFICADOR_DRY_RUN", True)
    caplog.set_level(logging.INFO, logger="scripts.notificador")

    enviar_notificacao(
        mensagem="synthetic-sensitive-content",
        space_id="synthetic-space-id",
    )

    assert "Notificação não enviada" in caplog.text
    assert "synthetic-sensitive-content" not in caplog.text
    assert "synthetic-space-id" not in caplog.text

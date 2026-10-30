"""Escolha do endereço de escuta do servidor de desenvolvimento (S1-02).

O servidor embarcado do Flask só deve ser usado em desenvolvimento e, com o
depurador ligado, apenas em loopback: o console do Werkzeug permite execução de
código no servidor. Fora de ``development`` o app é publicado por waitress,
gunicorn ou IIS (wfastcgi) — ver ``docs/manual_deploy.md``.

O helper fica separado de ``run.py`` para poder ser testado sem criar a
aplicação no import.
"""

from __future__ import annotations

from collections.abc import Mapping

PORTA_PADRAO = 5000

MENSAGEM_PRODUCAO = (
    "O servidor de desenvolvimento do Flask não deve ser usado fora de "
    "development. Publique o app com waitress, gunicorn ou IIS (wfastcgi) — "
    "ver docs/manual_deploy.md."
)


def escolher_bind_dev(config: Mapping) -> tuple[str, int, bool]:
    """Devolve ``(host, porta, debug)`` para ``app.run``.

    - ``DEBUG`` ligado: somente ``127.0.0.1`` (nunca exposto na rede);
    - ``APP_ENV=development`` sem debug: ``0.0.0.0`` como antes;
    - qualquer outro ambiente: recusa, orientando o servidor WSGI de produção.
    """
    if config.get("DEBUG"):
        return "127.0.0.1", PORTA_PADRAO, True

    app_env = str(config.get("APP_ENV") or "").strip().lower()
    if app_env == "development":
        return "0.0.0.0", PORTA_PADRAO, False

    raise RuntimeError(MENSAGEM_PRODUCAO)

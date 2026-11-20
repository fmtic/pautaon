"""AJ23 — máscara de segredos para o log em arquivo.

O handler de arquivo do ``app.logger`` usa :func:`mascarar_para_log` em toda
linha formatada (mensagem **e** traceback). O registro do callback OAuth também
usa a função ao registrar a exceção: só o tipo e a mensagem sanitizada entram na
mensagem, e o ``logger.exception`` continua anexando o traceback.

Nada aqui muda o fluxo OAuth — é apenas defesa em profundidade para evitar que
``code``, tokens, ``client_secret``, senhas ou a URL completa do callback com
query cheguem ao ``logs/app.log``.
"""

from __future__ import annotations

import re
from typing import Any

from flask import current_app

#: Chaves cujo valor nunca deve aparecer no log.
_CHAVES_SENSIVEIS = (
    "access_token",
    "refresh_token",
    "id_token",
    "authorization_code",
    "client_secret",
    "token",
    "code",
    "password",
    "passwd",
    "senha",
)

#: URL com query: mantém o caminho, descarta tudo o que vem depois de ``?``.
_PADRAO_URL_QUERY = re.compile(
    r"(?P<base>https?://[^\s'\"<>]+)\?(?P<query>[^\s'\"<>]*)",
    re.IGNORECASE,
)

#: ``chave=valor`` / ``"chave": "valor"`` (JSON) — valor sempre mascarado.
_PADRAO_CHAVE_VALOR = re.compile(
    r"(?P<chave>\b[\"']?(?:"
    + "|".join(_CHAVES_SENSIVEIS)
    + r")[\"']?\s*[:=]\s*)(?P<aspas>[\"']?)(?P<valor>[^\s,;&\"')\]}]+)",
    re.IGNORECASE,
)


def _valores_sensiveis_config() -> tuple[str, ...]:
    """Valores exatos da configuração que também devem ser suprimidos."""
    try:
        config = current_app.config
    except RuntimeError:
        return ()
    candidatos = (
        config.get("GOOGLE_OAUTH_CLIENT_SECRET"),
        config.get("SECRET_KEY"),
    )
    # Valores curtos ("x", "1") apareceriam em texto legítimo; só mascarar
    # segredos com tamanho suficiente para serem identificáveis.
    return tuple(
        str(valor) for valor in candidatos if valor and len(str(valor)) >= 4
    )


def mascarar_para_log(mensagem: Any) -> str:
    """Devolve ``mensagem`` como texto sem segredos nem query de callback."""
    texto = str(mensagem)
    texto = _PADRAO_URL_QUERY.sub(
        lambda match: f"{match.group('base')}?<query omitida>", texto
    )
    texto = _PADRAO_CHAVE_VALOR.sub(
        lambda match: f"{match.group('chave')}{match.group('aspas')}<omitido>",
        texto,
    )
    for valor in _valores_sensiveis_config():
        texto = texto.replace(valor, "<omitido>")
    return texto

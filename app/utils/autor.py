"""Autor do lançamento (F1).

Caminho único para saber quem assinou a última gravação de `frequencia` e de
`conselho_resposta`. Repete o FORMATO de `AuditoriaMixin` (id + snapshot do
nome), sem herdar o mixin: nessas duas tabelas o autor é gravado
explicitamente pelos pontos de escrita, e não pelo listener de `before_flush`
(que criaria um `LogAcao` por linha de frequência a cada salvamento).

Contextos sem usuário (scripts e seeds) recebem `(None, None)` — o lançamento
fica com `autor_id`/`autor_nome` NULL, sem autor inventado.
"""

from __future__ import annotations

from typing import Optional, Tuple

from flask_login import current_user


def autor_do_lancamento() -> Tuple[Optional[int], Optional[str]]:
    """`(id, nome)` do usuário autenticado; `(None, None)` sem requisição.

    Fora de um request context o Flask-Login não tem usuário: scripts e seeds
    caem no ramo NULL (decisão da F1 — histórico sem usuário não ganha autor).
    """
    if not getattr(current_user, "is_authenticated", False):
        return None, None
    return getattr(current_user, "id", None), getattr(current_user, "name", None)

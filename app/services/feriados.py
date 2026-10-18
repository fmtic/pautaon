from __future__ import annotations

import json
from datetime import date, timedelta
from functools import lru_cache
from pathlib import Path

from flask import current_app


def _carregar_feriados_wwdates(ano_inicio: int, ano_fim: int) -> dict[str, str] | None:
    """Tenta obter feriados via wwdates. Retorna None se indisponível."""
    try:
        from wwdates.br.anbima import DatesBRAnbima
    except (ModuleNotFoundError, ImportError):
        current_app.logger.info(
            "wwdates não instalado; usando fallback JSON para feriados nacionais."
        )
        return None

    try:
        cal = DatesBRAnbima()
        feriados: dict[str, str] = {}
        cursor = date(ano_inicio, 1, 1)
        fim = date(ano_fim, 12, 31)
        while cursor <= fim:
            if cal.is_holiday(cursor):
                # wwdates não expõe o nome do feriado diretamente via is_holiday.
                # Preenchemos com um rótulo genérico; o JSON local pode ter nomes.
                feriados[cursor.isoformat()] = "Feriado nacional"
            cursor += timedelta(days=1)
        return feriados
    except Exception:
        current_app.logger.exception("Falha ao consultar wwdates; usando fallback JSON.")
        return None


def _carregar_feriados_json(ano_inicio: int, ano_fim: int) -> dict[str, str]:
    """Fallback: lê data/feriados_nacionais.json versionado no projeto."""
    caminho = Path(current_app.root_path) / "data" / "feriados_nacionais.json"
    if not caminho.exists():
        current_app.logger.warning("Arquivo de feriados não encontrado: %s", caminho)
        return {}

    with caminho.open(encoding="utf-8") as f:
        dados: dict[str, str] = json.load(f)

    return {
        ds: nome
        for ds, nome in dados.items()
        if ano_inicio <= int(ds[:4]) <= ano_fim
    }


@lru_cache(maxsize=8)
def obter_feriados_nacionais(ano_inicio: int, ano_fim: int) -> dict[str, str]:
    """Retorna { 'YYYY-MM-DD': 'Nome do Feriado' } para o intervalo.

    Estratégia:
    1. wwdates (offline, cache local) — feriados nacionais.
    2. Fallback para data/feriados_nacionais.json.
    3. Se ambos falharem, retorna dict vazio (calendário funciona normalmente).
    """
    feriados = _carregar_feriados_wwdates(ano_inicio, ano_fim)
    if feriados is not None:
        return feriados

    return _carregar_feriados_json(ano_inicio, ano_fim)
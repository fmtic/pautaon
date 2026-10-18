"""Formatação para template. Template não calcula nada — só usa estas saídas."""

from __future__ import annotations


_FAIXA_META = {
    "hi": {"label": "≥ 90%", "classe": "success"},
    "mid": {"label": "75–89%", "classe": "warning"},
    "lo": {"label": "< 75%", "classe": "danger"},
}


def faixa_meta(faixa: str) -> dict:
    return _FAIXA_META[faixa]


def fmt_pct(valor: float | None, casas: int = 1) -> str:
    if valor is None:
        return "—"
    return f"{valor:.{casas}f}%"


def fmt_diff(diff: float | None) -> str:
    if diff is None:
        return "—"
    sinal = "+" if diff >= 0 else ""
    return f"{sinal}{diff:.0f} pp"


def largura(parte: int, total: int) -> float:
    return round(parte / total * 100, 2) if total else 0.0


def larguras_faixas(faixas: dict) -> dict[str, float]:
    return {
        "hi": largura(faixas["hi"], faixas["total"]),
        "mid": largura(faixas["mid"], faixas["total"]),
        "lo": largura(faixas["lo"], faixas["total"]),
    }


def classe_tendencia(tend: float | None) -> str:
    if tend is None:
        return "secondary"
    return "success" if tend >= 0 else "danger"


def celulas_semanais(semanais: dict[int, float | None]) -> list[dict]:
    """Células prontas para a tabela semanal do template."""
    celulas = []
    for v in semanais.values():
        if v is None:
            celulas.append({"valor": None, "valor_str": "—",
                            "classe": None, "faixa": None})
        else:
            # importado aqui para evitar ciclo com helpers
            from .helpers import faixa
            f = faixa(v)
            celulas.append({
                "valor": v,
                "valor_str": f"{v:.0f}",
                "classe": _FAIXA_META[f]["classe"],
                "faixa": f,
            })
    return celulas
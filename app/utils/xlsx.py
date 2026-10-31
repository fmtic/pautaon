"""Sanitização de valores para exportação XLSX (S1-17).

Valores de texto que começam com ``=``, ``+``, ``-``, ``@`` ou tabulação/CR
podem ser interpretados como fórmula pelo Excel. Prefixamos com apóstrofo para
que sejam tratados como texto. Números e datas não são alterados.
"""

from __future__ import annotations

_PREFIXOS_PERIGOSOS = ("=", "+", "-", "@", "\t", "\r")


def sanitizar_valor_xlsx(valor):
    if isinstance(valor, str) and valor and valor[0] in _PREFIXOS_PERIGOSOS:
        return "'" + valor
    return valor


def sanitizar_dataframe(df):
    try:
        import pandas as pd
    except ImportError:
        return df
    for col in df.columns:
        df[col] = df[col].map(sanitizar_valor_xlsx)
    return df
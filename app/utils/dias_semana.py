"""Conversor único de dias da semana (H1-P1).

Fonte canônica de tradução entre tokens de texto ("Terça", "terca-feira",
"seg.") e o índice numérico ``date.weekday()`` (0 = segunda … 6 = domingo),
que é o domínio da nova tabela ``turma_curso_horario``.

Decisão H1-1: ``dia_semana`` = ``date.weekday()`` — segunda = 0. **Não**
confundir com ``Date.getDay()`` do JavaScript (domingo = 0): a conversão é
responsabilidade de quem fala com o frontend.

Nunca levanta exceção para token desconhecido: devolve ``None`` e deixa o
chamador decidir (a migration P3 acumula esses tokens como checagem de
bloqueio). Esta etapa apenas CRIA o módulo; a substituição dos parsers
antigos (``_parse_dias``, ``_data_bate_dias_semana``,
``calcular_dias_aula_turma`` e os ``split`` de listagem) é do H3.
"""
from __future__ import annotations

import unicodedata

# Forma canônica exibida nos formulários e gravada no CSV legado
# (ordem de ``date.weekday()``: 0 = segunda … 6 = domingo).
_CANONICOS: tuple[str, ...] = (
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
)

# Abreviações de três letras usadas para exibição (``registros/turmas.py``)
# — sem ponto, para que ``weekday_para_abrev`` sirva também a comparações.
_ABREVIACOES: tuple[str, ...] = (
    "Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom",
)


def _normalizar(token: str) -> str:
    """minúsculas, sem acentos, sem espaços nas bordas e sem ponto final."""
    texto = (token or "").strip().lower()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return texto.strip().rstrip(".").strip()


# Mapa token-normalizado → weekday. Montado a partir das formas canônicas,
# das formas "-feira" (aceitas por ``_data_bate_dias_semana``) e das
# abreviações de três letras.
_POR_TOKEN: dict[str, int] = {}
for _i, _nome in enumerate(_CANONICOS):
    _POR_TOKEN[_normalizar(_nome)] = _i
    _POR_TOKEN[f"{_normalizar(_nome)}-feira"] = _i
    _POR_TOKEN[_normalizar(_ABREVIACOES[_i])] = _i


def token_para_weekday(token: str | None) -> int | None:
    """Converte um token de dia em índice ``date.weekday()`` (0–6).

    Aceita nomes completos com e sem acento ("Terça"/"Terca"), formas
    "-feira" (inclusive o "Sábado-feira" tolerado pelo parser antigo),
    abreviações de três letras com ou sem ponto ("seg", "seg.", "Sab.").
    Token desconhecido ou vazio → ``None`` (nunca levanta, nunca adivinha).
    """
    if not token:
        return None
    texto = _normalizar(token)
    if not texto:
        return None
    if texto in _POR_TOKEN:
        return _POR_TOKEN[texto]
    # Sufixo "-feira" (ou "feira") genérico: "segunda feira", "tercafeira".
    base = texto.replace("-feira", "").replace("feira", "").strip()
    return _POR_TOKEN.get(base)


def csv_tokens_desconhecidos(csv: str | None) -> list[str]:
    """Tokens do CSV que não correspondem a nenhum dia (preserva original)."""
    desconhecidos: list[str] = []
    for bruto in (csv or "").split(","):
        if not bruto.strip():
            continue
        if token_para_weekday(bruto) is None:
            desconhecidos.append(bruto.strip())
    return desconhecidos


def csv_para_weekdays(csv: str | None) -> list[int]:
    """Converte CSV de dias em índices 0–6, preservando a ordem do texto.

    Duplicatas (inclusive entre formas diferentes: "Terça, terca") são
    removidas mantendo a primeira ocorrência. Tokens desconhecidos são
    ignorados — use ``csv_tokens_desconhecidos`` para detectá-los.
    """
    vistos: list[int] = []
    for bruto in (csv or "").split(","):
        dia = token_para_weekday(bruto)
        if dia is not None and dia not in vistos:
            vistos.append(dia)
    return vistos


def weekday_para_nome(dia: int) -> str:
    """Forma canônica com acento ("Terça", "Sábado"). Dia fora de 0–6 → ValueError."""
    if not isinstance(dia, int) or not 0 <= dia <= 6:
        raise ValueError(f"dia_semana fora do domínio 0–6: {dia!r}")
    return _CANONICOS[dia]


def weekday_para_abrev(dia: int) -> str:
    """Abreviação de três letras com acento ("Ter", "Sáb")."""
    if not isinstance(dia, int) or not 0 <= dia <= 6:
        raise ValueError(f"dia_semana fora do domínio 0–6: {dia!r}")
    return _ABREVIACOES[dia]


def weekdays_para_csv(dias: list[int] | tuple[int, ...] | None) -> str | None:
    """CSV canônico dos dias: nomes completos, ordenados 0→6, unidos por ", ".

    Exatamente o formato que os formulários de hoje gravam
    (``", ".join(form.getlist("dias_semana"))`` em ``_dados_oferta_form``).
    Lista vazia ou ``None`` → ``None``. Duplicatas são removidas.
    """
    if not dias:
        return None
    ordenados = sorted({int(d) for d in dias})
    if any(not 0 <= d <= 6 for d in ordenados):
        raise ValueError(f"dia_semana fora do domínio 0–6: {dias!r}")
    return ", ".join(weekday_para_nome(d) for d in ordenados)

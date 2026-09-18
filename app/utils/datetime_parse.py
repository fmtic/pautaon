"""
================================================================================
DATETIME_PARSE.PY - Helpers de parsing de datas e horas
================================================================================

Criado na Onda 2A. Centraliza a conversão de strings de formulário/querystring
para objetos `date` / `time` / `datetime`, tratando vazio e None de forma
consistente.

Uso:
    from app.utils.datetime_parse import parse_date, parse_time

    turma.data_inicio = parse_date(request.form.get('data_inicio'))
    turma.hora_inicio = parse_time(request.form.get('hora_inicio'))

    # Em filtros:
    de = parse_date(request.args.get('de'))
    if de:
        q = q.filter(Turma.data_inicio >= de)

REGRAS
------
- Entrada vazia ('', None, espaços) -> None. Nunca levanta exceção.
- Entrada já no tipo correto (`date`/`time`/`datetime`) -> devolvida como está.
- Entrada com formato inválido -> None (falha silenciosa é preferível em
  formulários; a validação de negócio deve ser feita na camada de serviço).
================================================================================
"""

from datetime import date, time, datetime
from typing import Optional, Union


DateLike = Union[str, date, datetime, None]
TimeLike = Union[str, time, None]
DateTimeLike = Union[str, datetime, None]


def parse_date(value: DateLike) -> Optional[date]:
    """
    Converte 'YYYY-MM-DD' em `date`.

    Aceita também:
        - `date` já pronto (devolvido como está)
        - `datetime` (devolve a parte `.date()`)

    Retorna None para vazio/None/inválido.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    s = str(value).strip()
    if not s:
        return None
    try:
        return datetime.strptime(s, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def parse_time(value: TimeLike) -> Optional[time]:
    """
    Converte 'HH:MM' ou 'HH:MM:SS' em `time`.

    Aceita também `time` já pronto. Retorna None para vazio/None/inválido.
    """
    if value is None:
        return None
    if isinstance(value, time):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in ('%H:%M', '%H:%M:%S'):
        try:
            return datetime.strptime(s, fmt).time()
        except (ValueError, TypeError):
            continue
    return None


def parse_datetime(value: DateTimeLike) -> Optional[datetime]:
    """
    Converte 'YYYY-MM-DDTHH:MM[:SS]' ou 'YYYY-MM-DD HH:MM[:SS]' em `datetime`.

    Aceita também `datetime` já pronto. Retorna None para vazio/None/inválido.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    s = str(value).strip()
    if not s:
        return None
    for fmt in (
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M',
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%d %H:%M',
    ):
        try:
            return datetime.strptime(s, fmt)
        except (ValueError, TypeError):
            continue
    return None


__all__ = ['parse_date', 'parse_time', 'parse_datetime']
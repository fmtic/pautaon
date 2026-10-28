"""H1-P1: conversor único de dias da semana (app/utils/dias_semana.py).

Testa apenas o módulo novo — os parsers antigos (``_parse_dias``,
``_data_bate_dias_semana``, ``calcular_dias_aula_turma``) continuam
intocados até o H3.
"""
from __future__ import annotations

import pytest

from app.utils.dias_semana import (
    csv_para_weekdays,
    csv_tokens_desconhecidos,
    token_para_weekday,
    weekday_para_abrev,
    weekday_para_nome,
    weekdays_para_csv,
)


# --- token_para_weekday: aliases, acento, -feira ----------------------------
def test_token_nomes_completos_com_e_sem_acento():
    assert token_para_weekday("Segunda") == 0
    assert token_para_weekday("Terça") == 1
    assert token_para_weekday("Terca") == 1          # sem acento
    assert token_para_weekday("Quarta") == 2
    assert token_para_weekday("Quinta") == 3
    assert token_para_weekday("Sexta") == 4
    assert token_para_weekday("Sábado") == 5
    assert token_para_weekday("Sabado") == 5         # sem acento
    assert token_para_weekday("Domingo") == 6


def test_token_varias_caixas_e_espacos():
    assert token_para_weekday("  SEGUNDA ") == 0
    assert token_para_weekday("terça") == 1
    assert token_para_weekday("QuArTa") == 2


def test_token_formas_feira():
    assert token_para_weekday("Segunda-feira") == 0
    assert token_para_weekday("terça-feira") == 1
    assert token_para_weekday("Quarta-feira") == 2
    assert token_para_weekday("QUINTA-FEIRA") == 3
    assert token_para_weekday("Sexta-feira") == 4
    assert token_para_weekday("Sábado-feira") == 5   # tolerado pelo parser antigo
    # sem hífen e sem acento
    assert token_para_weekday("terca feira") == 1
    assert token_para_weekday("segundafeira") == 0


def test_token_abreviacoes():
    for token, esperado in (
        ("seg", 0), ("seg.", 0), ("TER", 1), ("ter.", 1),
        ("qua", 2), ("Qui", 3), ("qui.", 3), ("sex", 4),
        ("sab", 5), ("Sáb.", 5), ("dom", 6),
    ):
        assert token_para_weekday(token) == esperado, token


def test_token_desconhecido_devolve_none_nunca_levanta():
    for lixo in ("Feriado", "seconda", "", "   ", "segxta", "Sexta-Feira2"):
        assert token_para_weekday(lixo) is None, lixo
    assert token_para_weekday(None) is None


# --- csv_para_weekdays / csv_tokens_desconhecidos ----------------------------
def test_csv_preserva_ordem_do_texto():
    # o CSV do formulário pode vir fora de ordem; a conversão preserva
    assert csv_para_weekdays("Sexta, Segunda, Quarta") == [4, 0, 2]


def test_csv_remove_duplicatas_inclusive_entre_formas():
    assert csv_para_weekdays("Terça, terca, Ter., terça-feira") == [1]
    assert csv_para_weekdays("Segunda, Segunda") == [0]


def test_csv_tolerante_a_espacos_e_vazios():
    assert csv_para_weekdays(" Segunda , ,Quarta,") == [0, 2]
    assert csv_para_weekdays(None) == []
    assert csv_para_weekdays("") == []


def test_csv_desconhecidos_listados_sem_levantar():
    assert csv_tokens_desconhecidos("Segunda, Feriado, X") == ["Feriado", "X"]
    assert csv_tokens_desconhecidos("Segunda, Terça") == []
    assert csv_tokens_desconhecidos(None) == []


# --- formas de saída ----------------------------------------------------------
def test_weekday_para_nome_canonico_com_acento():
    assert [weekday_para_nome(d) for d in range(7)] == [
        "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
    ]


def test_weekday_para_abrev():
    assert weekday_para_abrev(0) == "Seg"
    assert weekday_para_abrev(5) == "Sáb"
    assert weekday_para_abrev(6) == "Dom"


def test_weekday_fora_do_domainio_levanta():
    for invalido in (-1, 7, 99):
        with pytest.raises(ValueError):
            weekday_para_nome(invalido)
        with pytest.raises(ValueError):
            weekday_para_abrev(invalido)


def test_weekdays_para_csv_formato_dos_formularios():
    # nomes canônicos, ordenados 0→6, unidos por ", " (formato do form)
    assert weekdays_para_csv([4, 0, 2]) == "Segunda, Quarta, Sexta"
    assert weekdays_para_csv([5, 5, 1]) == "Terça, Sábado"  # sem duplicata
    assert weekdays_para_csv([]) is None
    assert weekdays_para_csv(None) is None
    with pytest.raises(ValueError):
        weekdays_para_csv([0, 8])


# --- round-trip ----------------------------------------------------------------
def test_round_trip_csv_canonicos():
    original = "Segunda, Terça, Quarta, Quinta, Sexta, Sábado, Domingo"
    dias = csv_para_weekdays(original)
    assert dias == [0, 1, 2, 3, 4, 5, 6]
    assert weekdays_para_csv(dias) == original


def test_round_trip_com_ruido():
    # entrada suja de formulário legado (ordem trocada, acento variando)
    entrada = "sábado, Sab., sexta-feira, Segunda, terca"
    dias = csv_para_weekdays(entrada)
    assert dias == [5, 4, 0, 1]
    assert weekdays_para_csv(dias) == "Segunda, Terça, Sexta, Sábado"

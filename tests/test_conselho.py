from types import SimpleNamespace

from app.routes.conselho import (
    _build_turma_avaliacao_payload,
    _normalize_conselho_request,
)


def test_build_turma_avaliacao_payload_ignores_empty_answers() -> None:
    form_data = {
        "resp_turma_10": "Boa turma",
        "resp_turma_11": "   ",
        "resp_turma_12": "Excelente",
    }
    perguntas = [
        SimpleNamespace(id=10),
        SimpleNamespace(id=11),
        SimpleNamespace(id=12),
    ]

    payload = _build_turma_avaliacao_payload(form_data, perguntas)

    assert payload == '{"10": "Boa turma", "12": "Excelente"}'


def test_normalize_conselho_request_parses_dates_and_values() -> None:
    payload = {
        "turma_id": "7",
        "etapa": "FINAL",
        "data_inicio": "2026-01-01",
        "data_fim": "2026-01-15",
        "resp_1_2": "Aprovado",
    }

    normalized = _normalize_conselho_request(payload)

    assert normalized["turma_id"] == 7
    assert normalized["etapa"] == "FINAL"
    assert normalized["data_inicio"] == "2026-01-01"
    assert normalized["data_fim"] == "2026-01-15"
    assert normalized["respostas"]["1_2"] == "Aprovado"

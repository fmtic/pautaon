"""Testes automatizados para os novos indicadores e indicadores cruzados do BI."""

import pytest
from app import create_app, db
from app.relatorios.bi import executar_indicador


@pytest.fixture
def app():
    app = create_app()
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:"
    })
    with app.app_context():
        db.create_all()
        yield app
        db.drop_all()


def test_indicadores_sociais_e_operacionais(app):
    """Valida a execução dos indicadores SOC-001, SOC-002, DIV-001 e ATD-001."""
    with app.app_context():
        # SOC-001: Alunos por faixa de renda familiar (retorna lista de faixas)
        res_soc1 = executar_indicador("SOC-001")
        assert isinstance(res_soc1, list)
        assert len(res_soc1) > 0

        # SOC-002: Alunos beneficiários de programas sociais (retorna inteiro)
        res_soc2 = executar_indicador("SOC-002")
        assert isinstance(res_soc2, int)

        # DIV-001: Alunos por tipo de deficiência (retorna lista)
        res_div1 = executar_indicador("DIV-001")
        assert isinstance(res_div1, list)

        # ATD-001: Total de atendimentos (retorna inteiro)
        res_atd1 = executar_indicador("ATD-001")
        assert isinstance(res_atd1, int)


def test_indicadores_cruzados(app):
    """Valida a execução dos indicadores cruzados CRU-001 a CRU-005."""
    codes = ["CRU-001", "CRU-002", "CRU-003", "CRU-004", "CRU-005"]
    
    with app.app_context():
        for code in codes:
            resultado = executar_indicador(code)
            assert isinstance(resultado, list), f"Indicador {code} deve retornar uma lista."
from decimal import Decimal

import pytest
from werkzeug.datastructures import MultiDict

from app.services.aluno_perfil import (
    _programas_sociais,
    money,
    renda_per_capita,
    tipo_deficiencia,
)


def test_money_accepts_brazilian_and_html_number_formats():
    assert money('1.234,56') == Decimal('1234.56')
    assert money('1234.56') == Decimal('1234.56')
    assert money('R$ 250,00') == Decimal('250.00')


def test_renda_per_capita_returns_rounded_value():
    assert renda_per_capita('1.000,00', 3) == Decimal('333.33')
    assert renda_per_capita(None, 3) is None


def test_renda_per_capita_rejects_zero_residents():
    with pytest.raises(ValueError, match='maior que zero'):
        renda_per_capita('100,00', 0)


def test_tipo_deficiencia_includes_tea_and_rejects_unknown_values():
    assert tipo_deficiencia('TEA') == 'TEA'
    with pytest.raises(ValueError, match='inválido'):
        tipo_deficiencia('Tipo não cadastrado')


def test_programas_sociais_combines_values_and_removes_duplicates():
    form = MultiDict([
        ('beneficio_social_nome', 'Bolsa Família'),
        ('beneficio_social_nome', 'Auxílio Gás'),
        ('beneficio_social_nome', 'bolsa família'),
    ])
    assert _programas_sociais(form) == 'Bolsa Família | Auxílio Gás'
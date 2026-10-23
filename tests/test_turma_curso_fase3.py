"""
Testes da Onda 4 — Fase 3: validação de concomitância de horários (§5).

Regra: cursos da mesma turma não podem ter aulas no mesmo dia e horário
dentro de vigências que se interceptam. Adjacência é permitida.

Cenários cobertos:
    - Sobreposição total (mesmos dias e mesmos horários).
    - Sobreposição parcial (mesmos dias, horários que se cruzam).
    - Adjacência exata (fimA == iniB) → permitido.
    - Dias diferentes → permitido.
    - Vigências que não se interceptam → permitido.
    - Vigência NULL (aberta) → sempre intercepta.
    - Edição que remove a sobreposição → permitido.
    - Edição que cria sobreposição → bloqueado.
    - Sem dados de horário → pula validação.
    - Rota POST nova com conflito → flash de erro.
"""

from datetime import date, time

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade, User
from app.services.turma_curso import (
    adicionar_oferta,
    editar_oferta,
    _parse_dias,
    _sobreposicao_horario,
    _sobreposicao_vigencia,
)
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    """Unidade com 3 cursos, 1 turma e admin."""
    unidade = Unidade(nome="Unidade Teste", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    admin = User(
        name="Admin F3", email="admin.f3@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(admin)

    c1 = Curso(nome="Carpintaria", unidade_id=unidade.id, ativo=True)
    c2 = Curso(nome="Mecânica", unidade_id=unidade.id, ativo=True)
    c3 = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
    db.session.add_all([c1, c2, c3])

    turma = Turma(
        nome="Turma Multi", unidade_id=unidade.id, ativo=True,
        curso_id=None,
    )
    db.session.add(turma)
    db.session.commit()

    return {
        "admin_id": admin.id,
        "turma_id": turma.id,
        "c1": c1.id,
        "c2": c2.id,
        "c3": c3.id,
        "unidade_id": unidade.id,
    }


def _turma(base):
    return db.session.get(Turma, base["turma_id"])


# ---------------------------------------------------------------------------
# Unitários: helpers de sobreposição
# ---------------------------------------------------------------------------

class TestParseDias:
    def test_csv_normal(self):
        assert _parse_dias("Segunda, Quarta, Sexta") == {"segunda", "quarta", "sexta"}

    def test_none(self):
        assert _parse_dias(None) == set()

    def test_vazio(self):
        assert _parse_dias("") == set()


class TestSobreposicaoHorario:
    def test_parcial(self):
        # [08:00, 12:00) ∩ [10:00, 14:00) → True
        assert _sobreposicao_horario(
            time(8), time(12), time(10), time(14)
        ) is True

    def test_adjacente(self):
        # [08:00, 12:00) e [12:00, 14:00) → False (adjacência permitida)
        assert _sobreposicao_horario(
            time(8), time(12), time(12), time(14)
        ) is False

    def test_disjunto(self):
        # [08:00, 10:00) e [14:00, 16:00) → False
        assert _sobreposicao_horario(
            time(8), time(10), time(14), time(16)
        ) is False

    def test_contido(self):
        # [08:00, 18:00) ∩ [10:00, 12:00) → True
        assert _sobreposicao_horario(
            time(8), time(18), time(10), time(12)
        ) is True


class TestSobreposicaoVigencia:
    def test_se_interceptam(self):
        assert _sobreposicao_vigencia(
            date(2026, 1, 1), date(2026, 6, 30),
            date(2026, 3, 1), date(2026, 12, 31),
        ) is True

    def test_nao_se_interceptam(self):
        # [jan–jun] e [jul–dez] → False (a_fim < b_ini)
        assert _sobreposicao_vigencia(
            date(2026, 1, 1), date(2026, 6, 30),
            date(2026, 7, 1), date(2026, 12, 31),
        ) is False

    def test_adjacencia_data(self):
        # [jan–jun30] e [jun30–dez] → True (a_fim == b_ini → intersecam)
        assert _sobreposicao_vigencia(
            date(2026, 1, 1), date(2026, 6, 30),
            date(2026, 6, 30), date(2026, 12, 31),
        ) is True

    def test_null_sempre_intercepta(self):
        assert _sobreposicao_vigencia(
            None, None, date(2026, 1, 1), date(2026, 12, 31),
        ) is True


# ---------------------------------------------------------------------------
# Serviço: adicionar_oferta com conflito
# ---------------------------------------------------------------------------

def test_adicionar_oferta_sobreposicao_total_bloqueada(base):
    turma = _turma(base)
    # Primeira: Segunda/Quarta 08:00–12:00
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda, Quarta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    # Segunda: mesmos dias/horário → conflito
    with pytest.raises(ValueError, match="concomitante"):
        adicionar_oferta(
            turma, curso_id=base["c2"],
            dias_semana="Segunda, Quarta",
            hora_inicio=time(8), hora_fim=time(12),
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
        )


def test_adicionar_oferta_sobreposicao_parcial_bloqueada(base):
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda, Quarta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    # 10:00–14:00 na Segunda → parcial sobreposição
    with pytest.raises(ValueError, match="concomitante"):
        adicionar_oferta(
            turma, curso_id=base["c2"],
            dias_semana="Segunda, Sexta",
            hora_inicio=time(10), hora_fim=time(14),
            data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
        )


def test_adicionar_oferta_adjacencia_permitida(base):
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda, Quarta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    # Adjacente: 12:00–14:00 → permitido
    oferta2 = adicionar_oferta(
        turma, curso_id=base["c2"],
        dias_semana="Segunda, Quarta",
        hora_inicio=time(12), hora_fim=time(14),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    assert oferta2.id is not None


def test_adicionar_oferta_dias_diferentes_permitida(base):
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda, Quarta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    # Terça/Sexta: sem dias em comum → permitido mesmo com horário sobreposto
    oferta2 = adicionar_oferta(
        turma, curso_id=base["c2"],
        dias_semana="Terça, Sexta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    assert oferta2.id is not None


def test_adicionar_oferta_vigencia_disjunta_permitida(base):
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    # Vigência [jul–dez]: não intercepta [jan–jun] → permitido
    oferta2 = adicionar_oferta(
        turma, curso_id=base["c2"],
        dias_semana="Segunda",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 7, 1), data_fim=date(2026, 12, 31),
    )
    assert oferta2.id is not None


def test_adicionar_oferta_sem_horario_pula_validacao(base):
    """Sem dias/horas a checagem de concomitância é pulada."""
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda",
        hora_inicio=time(8), hora_fim=time(12),
    )
    # c2 sem dias/horas → permitido
    oferta2 = adicionar_oferta(turma, curso_id=base["c2"])
    assert oferta2.id is not None


# ---------------------------------------------------------------------------
# Serviço: editar_oferta com/sem conflito
# ---------------------------------------------------------------------------

def test_editar_oferta_cria_conflito_bloqueado(base):
    turma = _turma(base)
    o1 = adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda",
        hora_inicio=time(8), hora_fim=time(12),
    )
    o2 = adicionar_oferta(
        turma, curso_id=base["c2"],
        dias_semana="Terça",
        hora_inicio=time(8), hora_fim=time(12),
    )
    # Editar o2 para "Segunda" → conflita com o1
    with pytest.raises(ValueError, match="concomitante"):
        editar_oferta(o2, dias_semana="Segunda")


def test_editar_oferta_remove_conflito_permite(base):
    turma = _turma(base)
    o1 = adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda",
        hora_inicio=time(8), hora_fim=time(12),
    )
    o2 = adicionar_oferta(
        turma, curso_id=base["c2"],
        dias_semana="Segunda",
        hora_inicio=time(12), hora_fim=time(14),
    )
    # Editar o2 para Terça → sem conflito
    editar_oferta(o2, dias_semana="Terça")
    assert o2.dias_semana == "Terça"


# ---------------------------------------------------------------------------
# Rota: POST com conflito → flash de erro
# ---------------------------------------------------------------------------

def test_rota_oferta_nova_conflito_rejeitada(base, app):
    turma = _turma(base)
    adicionar_oferta(
        turma, curso_id=base["c1"], principal=True,
        dias_semana="Segunda, Quarta",
        hora_inicio=time(8), hora_fim=time(12),
        data_inicio=date(2026, 1, 1), data_fim=date(2026, 6, 30),
    )
    client = app.test_client()
    with client.session_transaction() as s:
        s["_user_id"] = str(base["admin_id"])
        s["_fresh"] = True
        s["unidade_id"] = base["unidade_id"]
    resp = client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={
            "curso_id": base["c2"],
            "dias_semana": ["Segunda", "Quarta"],
            "hora_inicio": "08:00",
            "hora_fim": "12:00",
            "data_inicio": "2026-01-01",
            "data_fim": "2026-06-30",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    html = resp.get_data(as_text=True)
    assert "concomitante" in html.lower()
    # Não criou segunda oferta ativa
    ativas = TurmaCurso.query.filter_by(turma_id=base["turma_id"], ativo=True).count()
    assert ativas == 1

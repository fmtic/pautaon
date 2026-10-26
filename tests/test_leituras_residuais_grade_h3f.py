"""H3f — Leituras residuais de escalares em `turma_curso.py` passam a ler a grade.

PASSO 2 (caracterização ANTES da migração): fixa o comportamento ATUAL dos
leitores residuais listados no inventário (iii) do relatório H3e — mensagens de
conflito e de dia-fora-da-grade, defaults de `editar_oferta`, herança da 1ª
oferta e rótulo do seletor em `detalhe.html` — em **grade uniforme**. Estes
testes passam contra o código antigo e devem passar **idênticos** depois de os
escalares `dias_semana`/`hora_inicio`/`hora_fim` deixarem de ser lidos por
serviços (só projeção, `_sincronizar_legado` e fallback legado com warning).

PASSO 4 (depois): classes `TestMigration*` fixam o contrato novo — grade NÃO
uniforme preservada, defaults/conflito pela grade real, herança só para turma
sem grade, mensagens citando os dias da grade.
"""

from datetime import date, time
import re

import pytest

from app import create_app, db
from app.models import Curso, Turma, Unidade, User
from app.services.turma_curso import (
    adicionar_oferta,
    criar_oferta_inicial_da_turma,
    editar_oferta,
    resolver_oferta_lancamento,
)
from app.services.turma_curso_horario import definir_grade, grade_da_oferta
from config import Config

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _base(app, *, turma_legada=False):
    """Semente: unidade, admin, cursos A/B e 1 turma sem ofertas. A turma nasce
    com escalares Segunda 09:00–10:00; `turma_legada=True` vincula o curso A
    (caminho do seed `criar_oferta_inicial_da_turma`). Retorna ids."""
    unidade = Unidade(nome="U h3f", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    admin = User(
        name="Admin H3f", email="admin.h3f@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(admin)
    cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
    cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
    db.session.add_all([cA, cB])
    db.session.flush()
    turma = Turma(
        nome="T h3f", unidade_id=unidade.id, ativo=True,
        curso_id=(cA.id if turma_legada else None),
        turno="Manhã", dias_semana="Segunda",
        hora_inicio=time(9, 0), hora_fim=time(10, 0),
        data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
    )
    db.session.add(turma)
    db.session.commit()
    return {
        "unidade": unidade.id, "admin": admin.id,
        "cA": cA.id, "cB": cB.id, "turma": turma.id,
    }


def _turma_oferta(ids, *, curso="cA", dias="Segunda", ini=time(8), fim=time(12),
                  principal=True, data_ini=DATA_INI, data_fim=DATA_FIM, turno=None):
    """adicionar_oferta com defaults de conveniência (grade uniforme)."""
    turma = db.session.get(Turma, ids["turma"])
    return adicionar_oferta(
        turma, curso_id=ids[curso], principal=principal, programa="Teste",
        turno=turno, dias_semana=dias, hora_inicio=ini, hora_fim=fim,
        data_inicio=data_ini, data_fim=data_fim,
    )


def _loga(app, user_id, unidade_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
        sess["unidade_id"] = unidade_id
    return client


def _norm(html: str) -> str:
    """Colapsa whitespace do template para buscar trechos de texto."""
    return re.sub(r"\s+", " ", html)


def _grade(oferta):
    db.session.expire_all()
    return [
        (l.dia_semana, l.hora_inicio, l.hora_fim)
        for l in grade_da_oferta(db.session.get(type(oferta), oferta.id))
    ]


# ---------------------------------------------------------------------------
# PASSO 2 — Caracterização ANTES (grade uniforme): comportamento que NÃO pode
# mudar com a migração
# ---------------------------------------------------------------------------

class TestCaracterizacao:

    def test_aviso_conflito_uniforme_texto_exato(self, app):
        """Rótulo (iii) turma_curso.py:268 — uniforme cita o CSV da projeção no
        formato caracterizado pelo H3b (``<dias>, HH:MM–HH:MM``)."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda, Quarta")
        o2 = _turma_oferta(ids, curso="cB", dias="Segunda", ini=time(10),
                           fim=time(14), principal=False)
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda, Quarta, 08:00–12:00). A oferta foi salva."
        ]

    def test_mensagem_dia_fora_da_grade_cita_dias(self, app):
        """Rótulo (iii) turma_curso.py:894 — a mensagem cita os dias da oferta."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        terca = date(2026, 3, 3)
        with pytest.raises(ValueError) as exc:
            resolver_oferta_lancamento(ids["turma"], terca, turma_curso_id=oferta.id)
        msg = str(exc.value)
        assert "não cai em um dia de aula" in msg
        assert "(Segunda, Quarta)" in msg

    def test_editar_so_programa_preserva_grade(self, app):
        """Sem campos de agenda em `dados`: a grade não é tocada."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        antes = _grade(oferta)
        editar_oferta(oferta, programa="Programa Novo")
        db.session.commit()
        assert _grade(oferta) == antes
        recarregada = db.session.get(type(oferta), oferta.id)
        assert recarregada.dias_semana == "Segunda, Quarta"
        assert recarregada.hora_inicio == time(8) and recarregada.hora_fim == time(12)

    def test_editar_dias_preserva_horarios_por_default(self, app):
        """Default (iii) turma_curso.py:645-647 — só `dias_semana` no `dados`:
        o par vem do default efetivo (hoje o escalar; depois a grade uniforme,
        mesmo valor)."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        editar_oferta(oferta, dias_semana="Sexta")
        db.session.commit()
        assert _grade(oferta) == [(4, time(8, 0), time(12, 0))]
        recarregada = db.session.get(type(oferta), oferta.id)
        assert recarregada.dias_semana == "Sexta"

    def test_aviso_na_edicao_de_vigencia_com_dia_comum(self, app):
        """Trocar a vigência de uma oferta SEM dia comum com a outra não gera
        aviso — o recheio usa a agenda real de ambas."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda, Quarta")
        o2 = _turma_oferta(
            ids, curso="cB", dias="Quinta", ini=time(9), fim=time(11),
            principal=False, data_ini=date(2026, 8, 1), data_fim=date(2026, 9, 30),
        )
        editar_oferta(o2, data_fim=date(2026, 12, 15))
        assert o2.avisos_horario == []

    def test_aviso_recheio_na_edicao_de_vigencia_com_dia_comum(self, app):
        """Default (iii) turma_curso.py:660-662 — ao abrir a vigência sobre a
        outra oferta, o aviso sai da agenda real (uniforme: CSV + par)."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda", data_ini=date(2026, 1, 1),
                      data_fim=date(2026, 6, 30))
        o2 = _turma_oferta(
            ids, curso="cB", dias="Segunda", ini=time(10), fim=time(14),
            principal=False, data_ini=date(2026, 8, 1), data_fim=date(2026, 9, 30),
        )
        assert o2.avisos_horario == []  # vigências disjoint: sem conflito
        editar_oferta(o2, data_inicio=date(2026, 3, 2))
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda, 08:00–12:00). A oferta foi salva."
        ]

    def test_heranca_primeira_oferta_usa_agenda_da_turma(self, app):
        """Herança (iii) turma_curso.py:573-575 — turma sem nenhuma grade:
        a 1ª oferta nasce com a agenda escalar da turma."""
        ids = _base(app)
        turma = db.session.get(Turma, ids["turma"])
        oferta = adicionar_oferta(turma, curso_id=ids["cA"], programa="Teste")
        db.session.commit()
        assert _grade(oferta) == [(0, time(9, 0), time(10, 0))]
        assert oferta.dias_semana == "Segunda"

    def test_seed_oferta_inicial_da_turma_legada(self, app):
        """Seed (iii) turma_curso.py:491-493 — turma legada (curso vinculado,
        sem ofertas): grade nasce dos escalares da turma."""
        ids = _base(app, turma_legada=True)
        turma = db.session.get(Turma, ids["turma"])
        oferta = criar_oferta_inicial_da_turma(turma)
        db.session.commit()
        assert _grade(oferta) == [(0, time(9, 0), time(10, 0))]
        assert oferta.dias_semana == "Segunda"

    def test_rotulo_seletor_enturmar_usa_hora_da_grade(self, app):
        """Rótulo (iii) detalhe.html:254 — o seletor mostra o horário vindo da
        grade (para uniforme, o par projetado)."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda, Quarta", turno="Manhã")
        client = _loga(app, ids["admin"], ids["unidade"])
        resp = client.get(f"/turma/{ids['turma']}")
        assert resp.status_code == 200
        html = _norm(resp.get_data(as_text=True))
        assert "Curso A — Manhã 08:00" in html

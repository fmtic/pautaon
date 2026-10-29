"""H3f/H5a — leituras de agenda em `turma_curso.py` vêm da grade.

Histórico: o H3f migrou os leitores residuais (mensagens de conflito e de
dia-fora-da-grade, defaults de `editar_oferta`, herança da 1ª oferta e rótulo
do seletor) para a grade, deixando as colunas escalares só como projeção e
fallback.

H5a: projeção e fallback foram REMOVIDOS — a grade é a única fonte de agenda e
as colunas `dias_semana`/`hora_inicio`/`hora_fim` de `Turma`/`TurmaCurso` não
são lidas nem escritas por `app/`. Os casos que caracterizavam apenas o
fallback escalar (ou o "espelho envenenado") saíram; os casos que continuam
valendo (mensagens, defaults da grade, herança da grade, rótulo do seletor)
seguem aqui, e os estados "turma sem agenda" passaram a exigir erro de
validação.
"""

import logging
import re
from datetime import date, time

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

from _helpers import itens_grade

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
    """Semente: unidade, admin, professor, cursos A/B e 1 turma sem ofertas.

    H5a: a turma NÃO nasce com agenda (ela nasce com a oferta). Com
    `turma_legada=True` o curso A fica vinculado à turma (caminho de
    `criar_oferta_inicial_da_turma`). G1/P2: a turma tem professor — toda
    oferta exige um. Retorna ids.
    """
    unidade = Unidade(nome="U h3f", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    admin = User(
        name="Admin H3f", email="admin.h3f@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    prof = User(
        name="Prof H3f", email="prof.h3f@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    db.session.add_all([admin, prof])
    db.session.flush()
    cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
    cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
    db.session.add_all([cA, cB])
    db.session.flush()
    turma = Turma(
        nome="T h3f", unidade_id=unidade.id, ativo=True,
        curso_id=(cA.id if turma_legada else None),
        professor_id=prof.id,
        turno="Manhã",
        data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
    )
    db.session.add(turma)
    db.session.commit()
    return {
        "unidade": unidade.id, "admin": admin.id, "professor": prof.id,
        "cA": cA.id, "cB": cB.id, "turma": turma.id,
    }


def _turma_oferta(ids, *, curso="cA", dias="Segunda", ini=time(8), fim=time(12),
                  principal=True, data_ini=DATA_INI, data_fim=DATA_FIM, turno=None):
    """adicionar_oferta com defaults de conveniência (grade uniforme via agenda)."""
    turma = db.session.get(Turma, ids["turma"])
    return adicionar_oferta(
        turma, curso_id=ids[curso], principal=principal, programa="Teste",
        professor_id=ids["professor"],
        turno=turno, agenda=itens_grade(dias, ini, fim),
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
        (linha.dia_semana, linha.hora_inicio, linha.hora_fim)
        for linha in grade_da_oferta(db.session.get(type(oferta), oferta.id))
    ]


# ---------------------------------------------------------------------------
# Contrato preservado: mensagens, defaults da grade e rótulo do seletor
# ---------------------------------------------------------------------------

class TestCaracterizacao:

    def test_aviso_conflito_uniforme_texto_exato(self, app):
        """Uniforme cita o CSV dos dias da GRADE no formato do H3b."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda, Quarta")
        o2 = _turma_oferta(ids, curso="cB", dias="Segunda", ini=time(10),
                           fim=time(14), principal=False)
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda, Quarta, 08:00–12:00). A oferta foi salva."
        ]

    def test_mensagem_dia_fora_da_grade_cita_dias(self, app):
        """A mensagem do resolutor cita os dias da grade da oferta."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        terca = date(2026, 3, 3)
        with pytest.raises(ValueError) as exc:
            resolver_oferta_lancamento(ids["turma"], terca, turma_curso_id=oferta.id)
        msg = str(exc.value)
        assert "não cai em um dia de aula" in msg
        assert "(Segunda, Quarta)" in msg

    def test_editar_so_programa_preserva_grade(self, app):
        """Sem `agenda` em `dados`: a grade não é tocada."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        antes = _grade(oferta)
        editar_oferta(oferta, programa="Programa Novo")
        db.session.commit()
        assert _grade(oferta) == antes

    def test_editar_com_agenda_substitui_a_grade(self, app):
        """`agenda=` é a única forma de trocar dias/horários na edição."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        editar_oferta(
            oferta, agenda=itens_grade("Sexta", time(8), time(12)),
        )
        db.session.commit()
        assert _grade(oferta) == [(4, time(8, 0), time(12, 0))]

    def test_editar_com_escalares_e_recusado(self, app):
        """H5a: o trio escalar não é aceito como fonte de agenda na edição."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        antes = _grade(oferta)
        with pytest.raises(ValueError, match="definidos pela grade"):
            editar_oferta(oferta, dias_semana="Sexta")
        db.session.rollback()
        assert _grade(oferta) == antes

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
        """Ao abrir a vigência sobre a outra oferta, o aviso sai da agenda real."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda", data_ini=date(2026, 1, 1),
                      data_fim=date(2026, 6, 30))
        o2 = _turma_oferta(
            ids, curso="cB", dias="Segunda", ini=time(10), fim=time(14),
            principal=False, data_ini=date(2026, 8, 1), data_fim=date(2026, 9, 30),
        )
        assert o2.avisos_horario == []  # vigências disjuntas: sem conflito
        editar_oferta(o2, data_inicio=date(2026, 3, 2))
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda, 08:00–12:00). A oferta foi salva."
        ]

    def test_adicionar_oferta_sem_agenda_e_rejeitada(self, app):
        """H5a: turma sem grade nenhuma não tem agenda para herdar — cria a
        oferta sem `agenda=` passa a ser erro de validação (antes nascia dos
        escalares da turma)."""
        ids = _base(app)
        turma = db.session.get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="ao menos um dia de aula"):
            adicionar_oferta(
                turma, curso_id=ids["cA"], programa="Teste",
                professor_id=ids["professor"],
            )

    def test_seed_oferta_inicial_sem_agenda_e_rejeitada(self, app):
        """H5a: o seed da oferta inicial exige `agenda=` (grade do formulário);
        não há mais herança a partir das colunas da turma."""
        ids = _base(app, turma_legada=True)
        turma = db.session.get(Turma, ids["turma"])
        with pytest.raises(ValueError, match="não tem agenda completa"):
            criar_oferta_inicial_da_turma(turma)

    def test_seed_oferta_inicial_com_agenda_grava_grade(self, app):
        """Com `agenda=` a oferta inicial nasce com a grade informada."""
        ids = _base(app, turma_legada=True)
        turma = db.session.get(Turma, ids["turma"])
        oferta = criar_oferta_inicial_da_turma(
            turma, agenda=itens_grade("Segunda", time(9), time(10)),
        )
        db.session.commit()
        assert _grade(oferta) == [(0, time(9, 0), time(10, 0))]

    def test_rotulo_seletor_enturmar_usa_hora_da_grade(self, app):
        """detalhe.html: o seletor mostra o horário vindo da grade."""
        ids = _base(app)
        _turma_oferta(ids, dias="Segunda, Quarta", turno="Manhã")
        client = _loga(app, ids["admin"], ids["unidade"])
        resp = client.get(f"/turma/{ids['turma']}")
        assert resp.status_code == 200
        html = _norm(resp.get_data(as_text=True))
        assert "Curso A — Manhã 08:00" in html


# ---------------------------------------------------------------------------
# A grade é a fonte da verdade na edição
# ---------------------------------------------------------------------------

class TestEditarOfertaGradeNaoUniforme:
    """`editar_oferta` com grade NÃO uniforme preserva a grade quando só a
    vigência ou o programa mudam — não regrava uniforme a partir de NULL."""

    def _oferta_nao_uniforme(self, ids):
        oferta = _turma_oferta(ids, dias="Segunda")
        definir_grade(
            oferta,
            [(0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0))],
        )
        db.session.commit()
        return oferta

    def test_so_vigencia_preserva_grade_nao_uniforme(self, app):
        ids = _base(app)
        oferta = self._oferta_nao_uniforme(ids)
        antes = _grade(oferta)
        editar_oferta(oferta, data_fim=date(2026, 10, 30))
        assert _grade(oferta) == antes == [
            (0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0)),
        ]

    def test_so_programa_preserva_grade_nao_uniforme(self, app):
        ids = _base(app)
        oferta = self._oferta_nao_uniforme(ids)
        antes = _grade(oferta)
        editar_oferta(oferta, programa="Programa Novo")
        assert _grade(oferta) == antes


class TestConflitoUsaGradeReal:
    """Aviso de concomitância na edição com grade não uniforme cita os
    segmentos por dia da grade."""

    def test_aviso_por_dia_na_edicao_de_vigencia(self, app):
        ids = _base(app)
        o1 = _turma_oferta(
            ids, dias="Segunda", ini=time(8), fim=time(10),
            data_ini=date(2026, 1, 1), data_fim=date(2026, 6, 30),
        )
        # 1ª oferta vira NÃO uniforme: Segunda 08–10 + Quinta 14–16
        definir_grade(
            o1,
            [(0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0))],
        )
        db.session.commit()
        o2 = _turma_oferta(
            ids, curso="cB", dias="Quarta", ini=time(20), fim=time(21),
            principal=False,
            data_ini=date(2026, 1, 1), data_fim=date(2026, 6, 30),
        )
        # grade não uniforme com Segunda 09:00–11:00 (conflitante com a 1ª)
        definir_grade(
            o2,
            [(2, time(20, 0), time(21, 0)), (0, time(9, 0), time(11, 0))],
        )
        db.session.commit()
        editar_oferta(o2, data_fim=date(2026, 12, 15))
        # o aviso cita o(s) dia(s) em conflito com o par DO DIA na grade da
        # outra oferta (segmento por dia, estilo H3b)
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda 08:00–10:00). A oferta foi salva."
        ]


class TestHerancaDaGrade:
    """A agenda da nova oferta é herdada da GRADE de uma oferta ativa da turma
    (H3f/H5a); sem grade e sem `agenda=` a criação é recusada."""

    def _desvincula(self, turma_id):
        """Volta a turma ao estado sem vínculo legado (situação-herança)."""
        turma = db.session.get(Turma, turma_id)
        turma.curso_id = None
        db.session.commit()
        return turma

    def test_heranca_vem_da_grade_existente(self, app):
        ids = _base(app)
        _turma_oferta(ids, dias="Quarta", ini=time(13), fim=time(15))
        turma = self._desvincula(ids["turma"])
        o2 = adicionar_oferta(
            turma, curso_id=ids["cB"], programa="Teste",
            professor_id=ids["professor"],
        )
        db.session.commit()
        assert _grade(o2) == [(2, time(13, 0), time(15, 0))]

    def test_heranca_preserva_grade_nao_uniforme_da_referencia(self, app):
        ids = _base(app)
        o1 = _turma_oferta(ids, dias="Segunda")
        definir_grade(
            o1,
            [(0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0))],
        )
        db.session.commit()
        turma = self._desvincula(ids["turma"])
        o2 = adicionar_oferta(
            turma, curso_id=ids["cB"], programa="Teste",
            professor_id=ids["professor"],
        )
        db.session.commit()
        assert _grade(o2) == [
            (0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0)),
        ]

    def test_sem_grade_nenhuma_nao_ha_heranca(self, app, caplog):
        """Turma sem oferta com grade e sem `agenda=`: erro de validação e
        nenhuma leitura de coluna escalar (nada de "escalares legados")."""
        ids = _base(app)
        turma = db.session.get(Turma, ids["turma"])
        with caplog.at_level(logging.WARNING):
            with pytest.raises(ValueError):
                adicionar_oferta(
                    turma, curso_id=ids["cA"], programa="Teste",
                    professor_id=ids["professor"],
                )
        assert not any(
            "escalares" in r.getMessage() for r in caplog.records
        )


class TestRotuloSeletorSoGrade:
    """detalhe.html:254 — o rótulo usa só a grade: uniforme mostra o par;
    NÃO uniforme omite a hora."""

    def test_grade_nao_uniforme_omite_hora_no_rotulo(self, app):
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda", turno="Manhã")
        definir_grade(
            oferta,
            [(0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0))],
        )
        db.session.commit()
        client = _loga(app, ids["admin"], ids["unidade"])
        resp = client.get(f"/turma/{ids['turma']}")
        assert resp.status_code == 200
        html = _norm(resp.get_data(as_text=True))
        # o seletor NÃO pode imprimir hora alguma no rótulo quando a grade é
        # não uniforme
        assert "Curso A — Manhã" in html
        assert "Manhã 08:00" not in html
        assert "Manhã 14:00" not in html

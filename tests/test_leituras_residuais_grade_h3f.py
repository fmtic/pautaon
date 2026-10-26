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
        (linha.dia_semana, linha.hora_inicio, linha.hora_fim)
        for linha in grade_da_oferta(db.session.get(type(oferta), oferta.id))
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


# ---------------------------------------------------------------------------
# PASSO 4 — Contrato DEPOIS da migração: a grade é a fonte da verdade
# ---------------------------------------------------------------------------

class TestEditarOfertaGradeNaoUniforme:
    """`editar_oferta` com grade NÃO uniforme preserva a grade quando só a
    vigência ou o nome mudam — não regrava uniforme a partir de NULL."""

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

    def test_so_nome_preserva_grade_nao_uniforme(self, app):
        ids = _base(app)
        oferta = self._oferta_nao_uniforme(ids)
        antes = _grade(oferta)
        editar_oferta(oferta, programa="Programa Novo")
        assert _grade(oferta) == antes

    def test_campos_null_nao_regravam_uniforme(self, app):
        """Formulário atual (H4 pendente) manda a triple com NULL sobre grade
        não uniforme: recusa e grade intacta — nunca regrava uniforme."""
        ids = _base(app)
        oferta = self._oferta_nao_uniforme(ids)
        antes = _grade(oferta)
        with pytest.raises(ValueError, match="ao menos um dia"):
            editar_oferta(
                oferta,
                dias_semana=None, hora_inicio=None, hora_fim=None,
                data_fim=date(2026, 10, 30),
            )
        db.session.rollback()
        assert _grade(oferta) == antes

    def test_default_de_agenda_omissa_vem_da_grade_nao_da_projecao(self, app):
        """Projeção envenenada (dias escalares trocados à mão, grade intacta):
        editar sem campos de agenda não toca a grade; a checagem usa a grade
        real — a projeção não interfere."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda")
        db.session.expire_all()
        recarregada = db.session.get(type(oferta), oferta.id)
        recarregada.dias_semana = "Sexta"  # espelho quebrado de propósito
        db.session.commit()
        editar_oferta(recarregada, programa="Outro")
        assert _grade(recarregada) == [(0, time(8, 0), time(12, 0))]


class TestConflitoUsaGradeReal:
    """Aviso de concomitância na edição com grade não uniforme cita os
    segmentos por dia da grade (não o CSV+par da projeção)."""

    def test_aviso_por_dia_na_edicao_de_vigencia(self, app):
        ids = _base(app)
        o1 = _turma_oferta(
            ids, dias="Segunda", ini=time(8), fim=time(10),
            data_ini=date(2026, 1, 1), data_fim=date(2026, 6, 30),
        )
        # 1ª oferta vira NÃO uniforme: Segunda 08–10 + Terça 14–16
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
        # outra oferta (segmento por dia, estilo H3b) — não o CSV+par escalar
        assert o2.avisos_horario == [
            "Horário concomitante com 'Curso A' "
            "(Segunda 08:00–10:00). A oferta foi salva."
        ]

    def test_mensagem_dia_fora_cita_dias_da_grade_com_projecao_trocada(self, app):
        """Projeção envenenada: a mensagem do resolutor sai da GRADE."""
        ids = _base(app)
        oferta = _turma_oferta(ids, dias="Segunda, Quarta")
        db.session.expire_all()
        recarregada = db.session.get(type(oferta), oferta.id)
        recarregada.dias_semana = "Sexta"  # espelho quebrado de propósito
        db.session.commit()
        with pytest.raises(ValueError) as exc:
            resolver_oferta_lancamento(
                ids["turma"], date(2026, 3, 3), turma_curso_id=recarregada.id,
            )
        msg = str(exc.value)
        assert "não cai em um dia de aula" in msg
        assert "(Segunda, Quarta)" in msg  # dias da grade, não "Sexta"


class TestHerancaSoParaTurmaSemGrade:
    """Herança da oferta: escalares só são lidos em turma sem grade, com
    warning; havendo ofertas com grade, a herança vem da grade.

    A UI típica espelha `curso_id` na 1ª oferta (situação-herança da Fase 2
    congela o bloco); o estado "turma sem vínculo com oferta ativa com grade"
    é montado à mão — é exatamente a situação de risco que o H3f fecha.
    """

    def _desvincula(self, turma_id, *, dias="Sexta", ini=time(20), fim=time(21)):
        """Volta a turma ao estado sem vínculo e envenena os escalares (a
        leitura correta nunca pode cair neles quando há grade)."""
        turma = db.session.get(Turma, turma_id)
        turma.curso_id = None
        turma.dias_semana = dias
        turma.hora_inicio = ini
        turma.hora_fim = fim
        db.session.commit()
        return turma

    def test_heranca_vem_da_grade_existente_nao_dos_escalaress(self, app):
        ids = _base(app)
        # escalares da turma viram isca Sexta 20–21; a oferta ativa é Quarta 13–15
        _turma_oferta(ids, dias="Quarta", ini=time(13), fim=time(15))
        turma = self._desvincula(ids["turma"])
        o2 = adicionar_oferta(turma, curso_id=ids["cB"], programa="Teste")
        db.session.commit()
        # herdou a GRADE da oferta ativa (Quarta 13–15), não os escalares
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
        o2 = adicionar_oferta(turma, curso_id=ids["cB"], programa="Teste")
        db.session.commit()
        assert _grade(o2) == [
            (0, time(8, 0), time(10, 0)), (3, time(14, 0), time(16, 0)),
        ]

    def test_heranca_escalar_so_com_aviso_quando_nao_ha_grade(self, app, caplog):
        ids = _base(app)
        db.session.expire_all()
        turma = db.session.get(Turma, ids["turma"])
        with caplog.at_level(logging.WARNING):
            oferta = adicionar_oferta(turma, curso_id=ids["cA"], programa="Teste")
        db.session.commit()
        assert _grade(oferta) == [(0, time(9, 0), time(10, 0))]
        assert any(
            "sem grade" in r.getMessage() and "escalares" in r.getMessage()
            for r in caplog.records
        )

    def test_seed_legado_avisa_no_logger(self, app, caplog):
        """Seed a partir da turma legada: caminho explícito, com warning."""
        ids = _base(app, turma_legada=True)
        turma = db.session.get(Turma, ids["turma"])
        with caplog.at_level(logging.WARNING):
            oferta = criar_oferta_inicial_da_turma(turma)
        db.session.commit()
        assert _grade(oferta) == [(0, time(9, 0), time(10, 0))]
        assert any(
            "escalares legados" in r.getMessage()
            for r in caplog.records
        )


class TestRotuloSeletorSoGrade:
    """detalhe.html:254 — o rótulo usa só a grade: uniforme mostra o par;
    NÃO uniforme omite a hora (nunca a projeção)."""

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
        # não uniforme (a projeção escalar está NULL e nem deve ser consultada)
        assert "Curso A — Manhã" in html
        assert "Manhã 08:00" not in html
        assert "Manhã 14:00" not in html

"""H3d — dias/horários exibidos na listagem, no detalhe e na impressão.

Cobre:
    - caracterização ANTES da migração: grade UNIFORME = texto idêntico ao da
      projeção escalar (linha, sub-linha, detalhe e impressão);
    - turma sem oferta ativa e oferta sem grade (fallback escalar);
    - (P5) grade NÃO uniforme: um segmento por dia no estilo do aviso do H3b e
      coluna "C.H. por aula" = "varia";
    - (P5) sem N+1 nas consultas de grade.
"""

import re
from datetime import date, time

import pytest

from app import create_app
from app.database import db
from app.models import (
    CentroCusto,
    Curso,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.services.turma_curso_horario import definir_grade
from config import Config

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _oferta(turma, curso, principal, grade, centro="Centro A"):
    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        unidade_id=turma.unidade_id,
        ativo=True,
        principal=principal,
        programa="Teste",
        data_inicio=DATA_INI,
        data_fim=DATA_FIM,
        centro_custo=centro,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, grade)
    return oferta


def _seed(app, variavel=False):
    """Turmas com centro de custo: uniforme, multi-oferta, sem oferta, legada."""
    with app.app_context():
        unidade = Unidade(nome="U1", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="2026", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.add(CentroCusto(nome="Centro A", unidade_id=unidade.id, ativo=True))
        user = User(
            name="Coord", email="coord@example.com", role="pedagogico",
            first_login=False, unidade_id=unidade.id,
        )
        db.session.add(user)
        cursos = [
            Curso(nome=f"C{i}", unidade_id=unidade.id, ativo=True) for i in range(1, 6)
        ]
        db.session.add_all(cursos)
        db.session.flush()

        def nova_turma(nome, dias, ini, fim):
            turma = Turma(
                nome=nome, unidade_id=unidade.id, curso_id=cursos[0].id,
                periodo_letivo_id=periodo.id, ativo=True,
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                dias_semana=dias, hora_inicio=ini, hora_fim=fim,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        t_uni = nova_turma("T-UNI", "Segunda, Quarta", time(8), time(9, 30))
        _oferta(
            t_uni, cursos[1], True,
            [(0, time(8), time(9, 30)), (2, time(8), time(9, 30))],
        )

        t_multi = nova_turma("T-MULTI", "Segunda, Quarta", time(8), time(11))
        _oferta(
            t_multi, cursos[0], True,
            [(0, time(8), time(11)), (2, time(8), time(11))],
        )
        _oferta(t_multi, cursos[2], False, [(1, time(8), time(9))])

        t_sem = nova_turma("T-SEM", "Sábado", time(19), time(21))

        t_leg = nova_turma("T-LEG", "Quinta", time(10), time(11))
        db.session.add(
            TurmaCurso(
                turma_id=t_leg.id, curso_id=cursos[3].id, unidade_id=unidade.id,
                ativo=True, principal=True, programa="Teste", dias_semana="Quinta",
                hora_inicio=time(10), hora_fim=time(11),
                data_inicio=DATA_INI, data_fim=DATA_FIM, centro_custo="Centro A",
            )
        )

        ids = {
            "periodo": periodo.id, "user": user.id,
            "t_uni": t_uni.id, "t_multi": t_multi.id, "t_sem": t_sem.id,
            "t_leg": t_leg.id,
        }
        if variavel:
            t_var = nova_turma("T-VAR", "Terça, Quinta", time(14), time(16))
            o_var = _oferta(
                t_var, cursos[4], True,
                [(1, time(8), time(10)), (3, time(14), time(16))],
            )
            ids["t_var"] = t_var.id
            ids["o_var"] = o_var.id
        db.session.commit()
        return ids


def _client(app, user_id):
    client = app.test_client()
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
    return client


def _norm(html):
    """Texto visível: remove comentários HTML, tags e espaços repetidos."""
    sem_comentarios = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", sem_comentarios).split())


def _linha(html, turma_id):
    """Trecho visível da LINHA da turma na listagem (marcador: link de ação)."""
    marca = f'href="/turma/{turma_id}"'
    i = html.find(marca)
    assert i > 0, f"turma {turma_id} não está na listagem"
    return _norm(html[max(0, i - 1800): i + 200])


def _sublinha(html, turma_id):
    marca = f'id="ofertas-{turma_id}"'
    i = html.find(marca)
    assert i > 0, f"turma {turma_id} não tem sub-linha de ofertas"
    return _norm(html[i: i + 4000])


# --- Caracterização ANTES: grade uniforme = texto atual ----------------------
class TestCaracterizacaoTextoUniforme:
    def test_linha_de_uma_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["user"]).get(
            f"/turma?periodo_letivo_id={ids['periodo']}"
        ).get_data(as_text=True)
        trecho = _linha(html, ids["t_uni"])
        assert "Seg. Qua." in trecho
        assert "08:00 - 09:30" in trecho

    def test_linha_multi_une_dias_e_mostra_par_da_principal(self, app):
        ids = _seed(app)
        html = _client(app, ids["user"]).get(
            f"/turma?periodo_letivo_id={ids['periodo']}"
        ).get_data(as_text=True)
        trecho = _linha(html, ids["t_multi"])
        assert "Seg. Ter. Qua." in trecho
        assert "08:00 - 11:00" in trecho

    def test_linha_de_turma_sem_oferta_usa_escalares(self, app):
        ids = _seed(app)
        html = _client(app, ids["user"]).get(
            f"/turma?periodo_letivo_id={ids['periodo']}"
        ).get_data(as_text=True)
        trecho = _linha(html, ids["t_sem"])
        assert "Sáb." in trecho
        assert "19:00 - 21:00" in trecho

    def test_sublinha_das_ofertas(self, app):
        ids = _seed(app)
        html = _client(app, ids["user"]).get(
            f"/turma?periodo_letivo_id={ids['periodo']}"
        ).get_data(as_text=True)
        trecho = _sublinha(html, ids["t_multi"])
        assert "Segunda, Quarta" in trecho
        assert "08:00 - 11:00" in trecho
        assert "Terça" in trecho
        assert "08:00 - 09:00" in trecho

    def test_detalhe_da_oferta(self, app):
        ids = _seed(app)
        corpo = _client(app, ids["user"]).get(f"/turma/{ids['t_uni']}")
        assert corpo.status_code == 200
        texto = _norm(corpo.get_data(as_text=True))
        assert "Dias: Segunda, Quarta Horários: 08:00 às 09:30" in texto

    def test_detalhe_da_oferta_sem_grade(self, app):
        ids = _seed(app)
        corpo = _client(app, ids["user"]).get(f"/turma/{ids['t_leg']}")
        texto = _norm(corpo.get_data(as_text=True))
        assert "Dias: Quinta Horários: 10:00 às 11:00" in texto

    def test_impressao_das_ofertas(self, app):
        ids = _seed(app)
        corpo = _client(app, ids["user"]).get(
            f"/turmas/centros-custo/imprimir?periodo_letivo_id={ids['periodo']}"
        )
        assert corpo.status_code == 200
        texto = _norm(corpo.get_data(as_text=True))
        assert "Segunda, Quarta 08:00–09:30 1h30min" in texto
        assert "Segunda, Quarta 08:00–11:00 3h" in texto
        assert "Terça 08:00–09:00 1h" in texto
        assert "Quinta 10:00–11:00 1h" in texto


# --- Comportamento novo (P5) -------------------------------------------------
# Grade NÃO uniforme e ausência de N+1 são adicionados depois da migração.
def _listar(app, ids):
    prompt = f"/turma?periodo_letivo_id={ids['periodo']}"
    return _client(app, ids["user"]).get(prompt).get_data(as_text=True)


def _adicionar_ofertas(app, turma_id, quantidade, dia=4, hora=9):
    """Cria `quantidade` ofertas uniformes na mesma turma (dias/horas distintas)."""
    with app.app_context():
        turma = db.session.get(Turma, turma_id)
        for i in range(quantidade):
            curso = Curso(nome=f"E{i}", unidade_id=turma.unidade_id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            _oferta(turma, curso, False, [(dia, time(hora + i), time(hora + i + 1))])
        db.session.commit()


class TestTextoGradeNaoUniforme:
    """T-VAR: Terça 08:00–10:00 e Quinta 14:00–16:00."""

    def test_linha_da_turma_mostra_grade_por_dia(self, app):
        ids = _seed(app, variavel=True)
        trecho = _linha(_listar(app, ids), ids["t_var"])
        assert "Ter. Qui." in trecho
        assert "Terça 08:00–10:00; Quinta 14:00–16:00" in trecho
        assert "14:00 - 16:00" not in trecho  # não repete o par escalar da turma

    def test_detalhe_mostra_grade_por_dia(self, app):
        ids = _seed(app, variavel=True)
        corpo = _client(app, ids["user"]).get(f"/turma/{ids['t_var']}")
        assert corpo.status_code == 200
        texto = _norm(corpo.get_data(as_text=True))
        assert (
            "Dias: Terça, Quinta Horários: Terça 08:00–10:00; Quinta 14:00–16:00"
            in texto
        )

    def test_impressao_mostra_por_dia_e_ch_aula_varia(self, app):
        ids = _seed(app, variavel=True)
        corpo = _client(app, ids["user"]).get(
            f"/turmas/centros-custo/imprimir?periodo_letivo_id={ids['periodo']}"
        )
        assert corpo.status_code == 200
        html = corpo.get_data(as_text=True)
        texto = _norm(html)
        assert (
            "Terça, Quinta Terça 08:00–10:00; Quinta 14:00–16:00 varia" in texto
        )
        # A lista por dia da C.H. por aula vai no tooltip (não na célula).
        assert 'title="Ter 2h; Qui 2h"' in html

    def test_sublinha_multi_mostra_varia_na_oferta_nao_uniforme(self, app):
        ids = _seed(app, variavel=True)
        _adicionar_ofertas(app, ids["t_var"], 1)
        html = _listar(app, ids)
        trecho = _sublinha(html, ids["t_var"])
        assert "Terça 08:00–10:00; Quinta 14:00–16:00" in trecho
        assert "varia" in trecho
        assert "Sexta 09:00 - 10:00" in trecho
        assert 'title="Ter 2h; Qui 2h"' in html

    def test_impressao_uniforme_nao_diz_varia(self, app):
        ids = _seed(app)
        corpo = _client(app, ids["user"]).get(
            f"/turmas/centros-custo/imprimir?periodo_letivo_id={ids['periodo']}"
        )
        texto = _norm(corpo.get_data(as_text=True))
        assert "varia" not in texto
        assert "Segunda, Quarta 08:00–09:30 1h30min" in texto


# --- Sem N+1 nas telas --------------------------------------------------------
def _consultas_de_grade(client, url):
    """Nº de statements que tocam `turma_curso`/grade ao renderizar a tela."""
    from sqlalchemy import event

    engine = db.engine
    vistas = []

    def _antes(conn, cursor, statement, parameters, context, executemany):
        if "turma_curso" in statement.lower():
            vistas.append(statement)

    event.listen(engine, "before_cursor_execute", _antes)
    try:
        resposta = client.get(url)
        assert resposta.status_code == 200
    finally:
        event.remove(engine, "before_cursor_execute", _antes)
    return len(vistas)


class TestRenderSemN1:
    def test_listagem_nao_cresce_com_turmas(self, app):
        ids = _seed(app, variavel=True)
        client = _client(app, ids["user"])
        url = f"/turma?periodo_letivo_id={ids['periodo']}"
        base = _consultas_de_grade(client, url)
        assert base > 0
        _adicionar_ofertas(app, ids["t_multi"], 2)
        _adicionar_ofertas(app, ids["t_uni"], 1)
        assert _consultas_de_grade(client, url) == base

    def test_detalhe_nao_cresce_com_ofertas(self, app):
        ids = _seed(app)
        client = _client(app, ids["user"])
        url = f"/turma/{ids['t_multi']}"
        base = _consultas_de_grade(client, url)
        assert base > 0
        _adicionar_ofertas(app, ids["t_multi"], 3)
        assert _consultas_de_grade(client, url) == base

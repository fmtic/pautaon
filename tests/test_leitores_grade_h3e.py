"""H3e — leitores de dias/horário do dashboard, aluno, ficha e conselho.

Cobre:
    - caracterização ANTES da migração (grade uniforme = texto atual de cada
      tela/função) — deve continuar idêntica depois, exceto onde o H3e
      normaliza o formato (`time` cru "08:00:00" -> "08:00");
    - grade NÃO uniforme: cada tela mostra um segmento por dia (formato do
      H3d: "Terça 08:00–10:00; Quinta 14:00–16:00");
    - dashboard: a aula de uma data mostra o intervalo do weekday dela;
    - turma multi-oferta e fallback sem grade;
    - ausência de N+1 nas consultas de grade.
"""

import logging
import re
from datetime import date, time

import pytest
from sqlalchemy import event

from app import create_app
from app.database import db
from app.main.dashboard_professor import _aulas_pendentes, _entradas_professor
from app.models import (
    Aluno,
    Atendimento,
    Curso,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.services.turma_curso_horario import definir_grade, dias_da_turma
from config import Config
from _helpers import login_as, professor_semente

DATA_INI = date(2026, 3, 2)  # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
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


def _norm(html):
    """Texto visível: remove comentários HTML, tags e espaços repetidos."""
    sem_comentarios = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", sem_comentarios).split())


def _client(app, user_id, unidade_id=None):
    cli = app.test_client()
    login_as(cli, str(user_id), unidade_id)
    return cli


def _oferta(turma, curso, principal, grade, **campos):
    campos.setdefault("professor_id", professor_semente(turma.unidade_id).id)
    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        unidade_id=turma.unidade_id,
        ativo=True,
        principal=principal,
        programa="Profissionalizante",
        data_inicio=DATA_INI,
        data_fim=DATA_FIM,
        **campos,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, grade)
    return oferta


def _seed(app, variavel=False):
    """U1 com 4 turmas (uniforme, multi, não uniforme opcional e legada)."""
    with app.app_context():
        unidade = Unidade(nome="U1", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        prof = User(
            name="Prof A", email="pa@example.com", role="professor",
            first_login=False, unidade_id=unidade.id,
        )
        coord = User(
            name="Coord", email="coord@example.com", role="admin",
            first_login=False, unidade_id=unidade.id,
        )
        db.session.add_all([prof, coord])
        periodo = PeriodoLetivo(
            nome="2026", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        cursos = [
            Curso(nome=f"Curso {letra}", unidade_id=unidade.id, ativo=True)
            for letra in "ABCDE"
        ]
        db.session.add_all(cursos)
        db.session.flush()

        def nova_turma(nome, ordenacao, turno="Manhã"):
            turma = Turma(
                nome=nome, unidade_id=unidade.id, curso_id=cursos[0].id,
                professor_id=prof.id, periodo_letivo_id=periodo.id,
                ativo=True, turno=turno, programa="Profissionalizante",
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                ordenacao=ordenacao,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        # T-UNI: 1 oferta uniforme (Seg/Qua 08:00-09:30).
        t_uni = nova_turma("T-UNI", 1)
        o_uni = _oferta(
            t_uni, cursos[0], True,
            [(0, time(8), time(9, 30)), (2, time(8), time(9, 30))],
            professor_id=prof.id, turno="Manhã",
        )

        # T-MULTI: principal Seg/Qua 08:00-11:00 + secundária Ter 08:00-09:00.
        t_multi = nova_turma("T-MULTI", 2, turno="Tarde")
        o_p = _oferta(
            t_multi, cursos[0], True,
            [(0, time(8), time(11)), (2, time(8), time(11))],
            professor_id=prof.id, turno="Tarde",
        )
        o_s = _oferta(
            t_multi, cursos[1], False, [(1, time(8), time(9))],
            professor_id=prof.id, turno="Tarde",
        )

        # T-LEG: oferta ativa SEM grade (estado inválido desde o H5a — as
        # colunas escalares não são mais lidas nem gravadas).
        t_leg = nova_turma("T-LEG", 3)
        o_leg = TurmaCurso(
            turma_id=t_leg.id, curso_id=cursos[3].id, unidade_id=unidade.id,
            ativo=True, principal=True, programa="Profissionalizante",
            professor_id=prof.id,
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(o_leg)
        db.session.flush()

        ids = {
            "unidade": unidade.id, "prof": prof.id, "coord": coord.id,
            "t_uni": t_uni.id, "t_multi": t_multi.id, "t_leg": t_leg.id,
            "o_uni": o_uni.id, "o_p": o_p.id, "o_s": o_s.id,
            "o_leg": o_leg.id, "periodo": periodo.id,
            "cursos": [c.id for c in cursos],
        }
        if variavel:
            # T-VAR: Terça 08:00–10:00 e Quinta 14:00–16:00.
            t_var = nova_turma("T-VAR", 4)
            o_var = _oferta(
                t_var, cursos[4], True,
                [(1, time(8), time(10)), (3, time(14), time(16))],
                professor_id=prof.id,
            )
            ids["t_var"] = t_var.id
            ids["o_var"] = o_var.id

        aluno = Aluno(nome="Aluno Um", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        pares_inscricao = [("t_uni", "o_uni"), ("t_multi", "o_p")]
        if variavel:
            pares_inscricao.append(("t_var", "o_var"))
        for chave_turma, chave_oferta in pares_inscricao:
            db.session.add(Inscricao(
                aluno_id=aluno.id, turma_id=ids[chave_turma],
                turma_curso_id=ids[chave_oferta], ativo=True,
                data_inicio=DATA_INI,
            ))
        db.session.add(Atendimento(
            aluno_id=aluno.id, setor="pedagogico",
            data_atendimento=DATA_INI, resumo="Conversa inicial", dados={},
            unidade_id=unidade.id, atendido_por_nome="Coord",
        ))
        db.session.commit()
        ids["aluno"] = aluno.id
        return ids


# --- Caracterização ANTES (grades uniformes) ---------------------------------
# Os textos abaixo são os do ANTES, com a única diferença da normalização
# intencional do H3e: o `str(time)` cru ("08:00:00") passa ao formato HH:MM do
# H3d ("08:00"). Nenhum outro caractere visível mudou.
class TestCaracterizacaoLeitores:
    def test_dashboard_lista_dias_e_horas_da_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "T-UNI — Curso A Segunda Quarta 08:00 às 09:30" in texto

    def test_dashboard_multi_mostra_a_grade_de_cada_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "T-MULTI — Curso A Segunda Quarta 08:00 às 11:00" in texto
        assert "T-MULTI — Curso B Terça 08:00 às 09:00" in texto

    def test_dashboard_pendencias_ganham_coluna_de_horario(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "Data Horário Turma Pendentes" in texto
        assert "02/03/2026" in texto

    def test_historico_do_aluno(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/aluno/{ids['aluno']}/historico"
        ).get_data(as_text=True)
        texto = _norm(html)
        assert "T-UNI Curso A Prof A Segunda, Quarta 08:00 às 09:30" in texto
        assert "T-MULTI Curso A Prof A Segunda, Quarta 08:00 às 11:00" in texto

    def test_ficha_do_aluno(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/relatorios/alunos/{ids['aluno']}/ficha"
        ).get_data(as_text=True)
        assert "Dias e horário Segunda, Quarta · 08:00–09:30" in _norm(html)

    def test_conselho_painel(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/conselho"
        ).get_data(as_text=True)
        assert "Segunda, Quarta | 08:00 às 09:30" in _norm(html)

    def test_conselho_fechamento(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/conselho/fechamento/{ids['t_uni']}"
        ).get_data(as_text=True)
        assert "Segunda, Quarta | 08:00 às 09:30" in _norm(html)

    def test_frequencia_seletor_de_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get(
            f"/frequencia?turma_id={ids['t_multi']}"
        ).get_data(as_text=True)
        texto = _norm(html)
        assert "Curso A — Tarde (08:00–11:00)" in texto
        assert "Curso B — Tarde (08:00–09:00)" in texto

    def test_gerenciar_data_atributos(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/alunos"
        ).get_data(as_text=True)
        assert 'data-turma-horario="08:00 às 09:30"' in html
        assert 'data-turma-dias="Segunda, Quarta"' in html

    def test_atendimento_data_atributos(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/alunos/atendimentos"
        ).get_data(as_text=True)
        assert 'data-aluno-horario="08:00 - 09:30"' in html

    def test_transferir_dados_da_origem(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/aluno/transferir/{ids['aluno']}"
            f"?turma_origem_id={ids['t_uni']}&turma_curso_id={ids['o_uni']}"
        ).get_data(as_text=True)
        texto = _norm(html)
        assert "Dias: Segunda, Quarta" in texto
        assert "Horário: 08:00 às 09:30" in texto


# --- Helpers dos cenários novos (não uniforme, fallback, N+1) -----------------
def _aluno_em(app, unidade_id, turma_id, oferta_id, nome, com_atendimento=False):
    """Aluno com UMA inscrição ativa — isola as telas no caso daquela oferta."""
    with app.app_context():
        aluno = Aluno(nome=nome, unidade_id=unidade_id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        db.session.add(Inscricao(
            aluno_id=aluno.id, turma_id=turma_id, turma_curso_id=oferta_id,
            ativo=True, data_inicio=DATA_INI,
        ))
        if com_atendimento:
            db.session.add(Atendimento(
                aluno_id=aluno.id, setor="pedagogico",
                data_atendimento=DATA_INI, resumo="Conversa", dados={},
                unidade_id=unidade_id, atendido_por_nome="Coord",
            ))
        db.session.commit()
        return aluno.id


def _turma_duas_ofertas_dias_diferentes(app, ids):
    """T-DOIS: Curso D Ter 08:00-10:00 + Curso E Qui 14:00-16:00."""
    with app.app_context():
        curso_d = db.session.get(Curso, ids["cursos"][3])
        curso_e = db.session.get(Curso, ids["cursos"][4])
        turma = Turma(
            nome="T-DOIS", unidade_id=ids["unidade"], curso_id=curso_d.id,
            professor_id=ids["prof"], periodo_letivo_id=ids["periodo"],
            ativo=True, turno="Manhã", programa="Profissionalizante",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            ordenacao=9,
        )
        db.session.add(turma)
        db.session.flush()
        oferta_a = _oferta(
            turma, curso_d, True, [(1, time(8), time(10))],
            professor_id=ids["prof"], turno="Manhã",
        )
        oferta_b = _oferta(
            turma, curso_e, False, [(3, time(14), time(16))],
            professor_id=ids["prof"], turno="Tarde",
        )
        db.session.commit()
        return {
            "turma": turma.id,
            "oferta_a": oferta_a.id,
            "oferta_b": oferta_b.id,
        }


def _medir_selects_de_grade(app, funcao):
    """Nº de SELECTs em `turma_curso_horario` de `funcao`, em sessão nova."""
    contador = {"n": 0}

    def _ouvir(conn, cursor, statement, parameters, context, executemany):
        if "turma_curso_horario" in statement.lower():
            contador["n"] += 1

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _ouvir)
        try:
            funcao()
        finally:
            event.remove(db.engine, "before_cursor_execute", _ouvir)
    return contador["n"]


# --- Grade NÃO uniforme: cada tela mostra um segmento por dia -----------------
class TestNaoUniformePorDia:
    def test_dashboard_resumo_por_dia(self, app):
        ids = _seed(app, variavel=True)
        texto = _norm(
            _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        )
        assert (
            "T-VAR — Curso E Terça Quinta Terça 08:00–10:00; Quinta 14:00–16:00"
            in texto
        )

    def test_conselho_painel_e_fechamento_por_dia(self, app):
        ids = _seed(app, variavel=True)
        esperado = "Terça, Quinta | Terça 08:00–10:00; Quinta 14:00–16:00"
        painel = _norm(
            _client(app, ids["coord"], ids["unidade"])
            .get("/conselho").get_data(as_text=True)
        )
        assert esperado in painel
        fechamento = _norm(
            _client(app, ids["coord"], ids["unidade"])
            .get(f"/conselho/fechamento/{ids['t_var']}").get_data(as_text=True)
        )
        assert esperado in fechamento

    def test_historico_e_ficha_por_dia(self, app):
        ids = _seed(app, variavel=True)
        aluno = _aluno_em(app, ids["unidade"], ids["t_var"], ids["o_var"], "Aluno Var")
        cli = _client(app, ids["coord"], ids["unidade"])
        historico = _norm(cli.get(f"/aluno/{aluno}/historico").get_data(as_text=True))
        assert (
            "T-VAR Curso E Prof A Terça, Quinta Terça 08:00–10:00; Quinta 14:00–16:00"
            in historico
        )
        ficha = _norm(
            cli.get(f"/relatorios/alunos/{aluno}/ficha").get_data(as_text=True)
        )
        assert (
            "Dias e horário Terça, Quinta · Terça 08:00–10:00; Quinta 14:00–16:00"
            in ficha
        )

    def test_gerenciar_atendimento_transferir_por_dia(self, app):
        ids = _seed(app, variavel=True)
        aluno = _aluno_em(
            app, ids["unidade"], ids["t_var"], ids["o_var"], "Aluno Var",
            com_atendimento=True,
        )
        cli = _client(app, ids["coord"], ids["unidade"])
        por_dia = "Terça 08:00–10:00; Quinta 14:00–16:00"

        gerenciar = cli.get("/alunos").get_data(as_text=True)
        assert f'data-turma-horario="{por_dia}"' in gerenciar
        assert 'data-turma-dias="Terça, Quinta"' in gerenciar

        atendimento = cli.get("/alunos/atendimentos").get_data(as_text=True)
        assert f'data-aluno-horario="{por_dia}"' in atendimento

        transferir = _norm(
            cli.get(
                f"/aluno/transferir/{aluno}"
                f"?turma_origem_id={ids['t_var']}&turma_curso_id={ids['o_var']}"
            ).get_data(as_text=True)
        )
        assert "Dias: Terça, Quinta" in transferir
        assert f"Horário: {por_dia}" in transferir

    def test_frequencia_seletor_por_dia(self, app):
        ids = _seed(app)
        dois = _turma_duas_ofertas_dias_diferentes(app, ids)
        texto = _norm(
            _client(app, ids["prof"])
            .get(f"/frequencia?turma_id={dois['turma']}").get_data(as_text=True)
        )
        assert "Curso D — Manhã (08:00–10:00)" in texto
        assert "Curso E — Tarde (14:00–16:00)" in texto


# --- Dashboard: a hora exibida é a do weekday da data ------------------------
class TestDashboardPorData:
    def test_pendencia_usa_o_intervalo_do_weekday_da_data(self, app):
        ids = _seed(app, variavel=True)
        with app.app_context():
            turma = db.session.get(Turma, ids["t_var"])
            pendentes = _aulas_pendentes([turma], prazo_dias=0)
        por_data = {p["data"]: p["intervalo"] for p in pendentes}
        assert por_data[date(2026, 3, 3)] == (time(8), time(10))    # terça
        assert por_data[date(2026, 3, 5)] == (time(14), time(16))   # quinta

    def test_dashboard_html_mostra_o_horario_da_data(self, app):
        ids = _seed(app, variavel=True)
        texto = _norm(
            _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        )
        # O card exibe as 2 primeiras pendências; ambas são de 02/03 (segunda),
        # cada uma com o intervalo da grade da própria oferta. A variação da
        # hora pelo weekday da data está em
        # test_pendencia_usa_o_intervalo_do_weekday_da_data.
        assert "02/03/2026 08:00–11:00 T-MULTI — Curso A" in texto
        assert "02/03/2026 08:00–09:30 T-UNI" in texto


# --- Turma multi-oferta e fallback sem grade ---------------------------------
class TestMultiOfertaEFallback:
    def test_turma_multi_oferta_deriva_dias_da_grade(self, app):
        ids = _seed(app)
        dois = _turma_duas_ofertas_dias_diferentes(app, ids)
        with app.app_context():
            assert dias_da_turma(dois["turma"]) == {1, 3}
        # A tela do aluno mostra a grade da OFERTA dele, não a união da turma.
        _aluno_em(
            app, ids["unidade"], dois["turma"], dois["oferta_a"], "Aluno Dois",
        )
        _aluno_em(
            app, ids["unidade"], dois["turma"], dois["oferta_b"], "Aluno Tres",
        )
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/alunos"
        ).get_data(as_text=True)
        assert 'data-turma-dias="Terça"' in html
        assert 'data-turma-horario="08:00 às 10:00"' in html
        assert 'data-turma-dias="Quinta"' in html
        assert 'data-turma-horario="14:00 às 16:00"' in html

    def test_sem_grade_dashboard_nao_usa_escalar(self, app, caplog):
        ids = _seed(app)
        _aluno_em(app, ids["unidade"], ids["t_leg"], ids["o_leg"], "Aluno Leg")
        with caplog.at_level(
            logging.ERROR, logger="app.services.turma_curso_horario"
        ):
            texto = _norm(
                _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
            )
        # H5a: a linha aparece, mas sem dias/horário herdados da coluna escalar.
        assert "T-LEG — Curso D" in texto
        assert "T-LEG — Curso D Quinta" not in texto
        assert "10:00 às 11:00" not in texto
        assert any("sem grade" in r.getMessage() for r in caplog.records)

    def test_sem_grade_na_tela_do_aluno(self, app):
        ids = _seed(app)
        _aluno_em(app, ids["unidade"], ids["t_leg"], ids["o_leg"], "Aluno Leg")
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/alunos"
        ).get_data(as_text=True)
        # H5a: sem grade a tela mostra a ausência — nunca o valor escalar.
        assert 'data-turma-horario="10:00 às 11:00"' not in html
        assert 'data-turma-dias="Quinta"' not in html
        assert 'data-turma-horario="-"' in html
        assert 'data-turma-dias="-"' in html


# --- Sem N+1: consultas de grade constantes ao crescer ofertas ---------------
class TestSemN1:
    def test_consultas_de_grade_constantes_ao_crescer_ofertas(self, app):
        ids = _seed(app)

        def _entradas():
            _entradas_professor(ids["prof"])

        def _pendencias():
            turmas = Turma.query.filter(
                Turma.id.in_([ids["t_uni"], ids["t_multi"], ids["t_leg"]])
            ).all()
            _aulas_pendentes(turmas, prazo_dias=0)

        antes = (
            _medir_selects_de_grade(app, _entradas),
            _medir_selects_de_grade(app, _pendencias),
        )

        with app.app_context():
            turma = db.session.get(Turma, ids["t_multi"])
            for curso_id in ids["cursos"][2:5]:
                curso = db.session.get(Curso, curso_id)
                _oferta(
                    turma, curso, False, [(0, time(8), time(10))],
                    professor_id=ids["prof"],
                )
            db.session.commit()

        depois = (
            _medir_selects_de_grade(app, _entradas),
            _medir_selects_de_grade(app, _pendencias),
        )
        assert depois == antes

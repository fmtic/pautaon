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

import re
from datetime import date, time

import pytest

from app import create_app
from app.database import db
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
from app.services.turma_curso_horario import definir_grade
from config import Config

DATA_INI = date(2026, 3, 2)  # segunda-feira
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


def _norm(html):
    """Texto visível: remove comentários HTML, tags e espaços repetidos."""
    sem_comentarios = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    return " ".join(re.sub(r"<[^>]+>", " ", sem_comentarios).split())


def _client(app, user_id, unidade_id=None):
    cli = app.test_client()
    with cli.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id
    return cli


def _oferta(turma, curso, principal, grade, **campos):
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

        def nova_turma(nome, dias, ini, fim, ordenacao, turno="Manhã"):
            turma = Turma(
                nome=nome, unidade_id=unidade.id, curso_id=cursos[0].id,
                professor_id=prof.id, periodo_letivo_id=periodo.id,
                ativo=True, turno=turno, programa="Profissionalizante",
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                dias_semana=dias, hora_inicio=ini, hora_fim=fim,
                ordenacao=ordenacao,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        # T-UNI: 1 oferta uniforme (Seg/Qua 08:00-09:30).
        t_uni = nova_turma("T-UNI", "Segunda, Quarta", time(8), time(9, 30), 1)
        o_uni = _oferta(
            t_uni, cursos[0], True,
            [(0, time(8), time(9, 30)), (2, time(8), time(9, 30))],
            professor_id=prof.id, turno="Manhã",
            dias_semana="Segunda, Quarta", hora_inicio=time(8),
            hora_fim=time(9, 30),
        )

        # T-MULTI: principal Seg/Qua 08:00-11:00 + secundária Ter 08:00-09:00.
        t_multi = nova_turma("T-MULTI", "Segunda, Quarta", time(8), time(11), 2,
                             turno="Tarde")
        o_p = _oferta(
            t_multi, cursos[0], True,
            [(0, time(8), time(11)), (2, time(8), time(11))],
            professor_id=prof.id, turno="Tarde",
            dias_semana="Segunda, Quarta", hora_inicio=time(8),
            hora_fim=time(11),
        )
        o_s = _oferta(
            t_multi, cursos[1], False, [(1, time(8), time(9))],
            professor_id=prof.id, turno="Tarde",
            dias_semana="Terça", hora_inicio=time(8), hora_fim=time(9),
        )

        # T-LEG: oferta ativa SEM grade (projeção escalar = Qui 10:00-11:00).
        t_leg = nova_turma("T-LEG", "Quinta", time(10), time(11), 3)
        o_leg = TurmaCurso(
            turma_id=t_leg.id, curso_id=cursos[3].id, unidade_id=unidade.id,
            ativo=True, principal=True, programa="Profissionalizante",
            professor_id=prof.id, dias_semana="Quinta",
            hora_inicio=time(10), hora_fim=time(11),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(o_leg)

        ids = {
            "unidade": unidade.id, "prof": prof.id, "coord": coord.id,
            "t_uni": t_uni.id, "t_multi": t_multi.id, "t_leg": t_leg.id,
            "o_uni": o_uni.id, "o_p": o_p.id, "o_s": o_s.id,
            "o_leg": o_leg.id,
        }
        if variavel:
            # T-VAR: Terça 08:00–10:00 e Quinta 14:00–16:00.
            t_var = nova_turma("T-VAR", "Terça, Quinta", time(14), time(16), 4)
            o_var = _oferta(
                t_var, cursos[4], True,
                [(1, time(8), time(10)), (3, time(14), time(16))],
                professor_id=prof.id,
                dias_semana="Terça, Quinta", hora_inicio=time(14),
                hora_fim=time(16),
            )
            ids["t_var"] = t_var.id
            ids["o_var"] = o_var.id

        aluno = Aluno(nome="Aluno Um", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        for chave_turma, chave_oferta in (
            ("t_uni", "o_uni"), ("t_multi", "o_p"),
        ):
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
class TestCaracterizacaoLeitores:
    def test_dashboard_lista_dias_e_horas_da_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "T-UNI — Curso A Segunda Quarta 08:00:00 às 09:30:00" in texto

    def test_dashboard_multi_mostra_a_grade_de_cada_oferta(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "T-MULTI — Curso A Segunda Quarta 08:00:00 às 11:00:00" in texto
        assert "T-MULTI — Curso B Terça 08:00:00 às 09:00:00" in texto

    def test_dashboard_pendencias_sem_horario(self, app):
        ids = _seed(app)
        html = _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        texto = _norm(html)
        assert "Data Turma Pendentes" in texto
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
        assert "Segunda, Quarta | 08:00:00 às 09:30:00" in _norm(html)

    def test_conselho_fechamento(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/conselho/fechamento/{ids['t_uni']}"
        ).get_data(as_text=True)
        assert "Segunda, Quarta | 08:00:00 às 09:30:00" in _norm(html)

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
        assert 'data-turma-horario="08:00:00 às 09:30:00"' in html
        assert 'data-turma-dias="Segunda, Quarta"' in html

    def test_atendimento_data_atributos(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            "/alunos/atendimentos"
        ).get_data(as_text=True)
        assert 'data-aluno-horario="08:00:00 - 09:30:00"' in html

    def test_transferir_dados_da_origem(self, app):
        ids = _seed(app)
        html = _client(app, ids["coord"], ids["unidade"]).get(
            f"/aluno/transferir/{ids['aluno']}"
            f"?turma_origem_id={ids['t_uni']}&turma_curso_id={ids['o_uni']}"
        ).get_data(as_text=True)
        texto = _norm(html)
        assert "Dias: Segunda, Quarta" in texto
        assert "Horário: 08:00:00 às 09:30:00" in texto

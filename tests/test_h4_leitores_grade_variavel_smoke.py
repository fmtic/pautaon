"""H4 — Passo 4: smoke dos leitores migrados com grade NÃO uniforme criada
pela UI.

Fluxo: oferta da turma vira grade por dia (Seg 08:00–11:00 + Qua 14:00–17:00)
pelo POST real da tela de Cursos da Turma; depois percorre-se TODOS os
leitores migrados (H3d/H3e/H3f) — listagem com filtros dia+hora na MESMA
linha, detalhe, impressão, C.H. da oferta e da turma, concomitância,
dashboard por data, aluno/ficha/atendimento/conselho/frequência/seletor e
transferência — sempre por HTTP, sem erro e com o texto por dia correto.
Fecha com a checagem de ausência de N+1 de grade na listagem.
"""

import re
from datetime import date, time

from sqlalchemy import event

from app import create_app, db
from app.models import (
    Aluno,
    Atendimento,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from app.services.turma_curso import _conflitos_horario_concomitante
from app.services.turma_curso_horario import definir_grade
from config import Config

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)

#: Texto por dia da grade NÃO uniforme do smoke (formato H3d).
POR_DIA = "Segunda 08:00–11:00; Quarta 14:00–17:00"

GRADE_POR_DIA = {
    "horario_por_dia": "1",
    "dias_semana": ["0", "2"],
    "hora_inicio": "08:00",
    "hora_fim": "11:00",
    "hora_inicio_0": "08:00",
    "hora_fim_0": "11:00",
    "hora_inicio_2": "14:00",
    "hora_fim_2": "17:00",
}


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


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


def _seed():
    """Turma T-VAR com 1 oferta uniforme; os ids servem à UI e aos leitores."""
    app = create_app(SQLiteTestConfig)
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U1", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        coord = User(
            name="Coord", email="coord.smoke@example.com", role="admin",
            first_login=False, unidade_id=unidade.id,
        )
        prof = User(
            name="Prof A", email="prof.smoke@example.com", role="professor",
            first_login=False, unidade_id=unidade.id,
        )
        # /frequencia_relatorio é restrito ao papel pedagógico.
        pedag = User(
            name="Pedag", email="pedag.smoke@example.com", role="pedagogico",
            first_login=False, unidade_id=unidade.id,
        )
        db.session.add_all([coord, prof, pedag])
        periodo = PeriodoLetivo(
            nome="2026.1", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        curso = Curso(nome="Curso V", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        turma = Turma(
            nome="T-VAR", unidade_id=unidade.id, curso_id=curso.id,
            professor_id=prof.id, periodo_letivo_id=periodo.id, ativo=True,
            turno="Manhã", programa="Profissionalizante",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            ordenacao=1,
        )
        db.session.add(turma)
        db.session.flush()

        oferta = TurmaCurso(
            turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
            ativo=True, principal=True, professor_id=prof.id, turno="Manhã",
            data_inicio=DATA_INI, data_fim=DATA_FIM,
            programa="Profissionalizante",
        )
        db.session.add(oferta)
        db.session.flush()
        # Começa uniforme (Seg/Qua 08:00–11:00); o teste vira NÃO uniforme pela UI.
        definir_grade(
            oferta, [(0, time(8), time(11)), (2, time(8), time(11))]
        )

        aluno = Aluno(nome="Aluno Var", unidade_id=unidade.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        db.session.add(Inscricao(
            aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
            ativo=True, data_inicio=DATA_INI,
        ))
        db.session.add(Atendimento(
            aluno_id=aluno.id, setor="pedagogico", data_atendimento=DATA_INI,
            resumo="Conversa inicial", dados={}, unidade_id=unidade.id,
            atendido_por_nome="Coord",
        ))
        for dia, conceito in ((0, ConceitoFrequencia.A), (2, ConceitoFrequencia.F)):
            db.session.add(Frequencia(
                aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
                data=date(2026, 3, 2 + dia * 2),  # seg 02/03 e qua 04/03
                conceito=conceito, unidade_id=unidade.id,
            ))
        db.session.commit()
        ids = {
            "unidade": unidade.id, "coord": coord.id, "prof": prof.id,
            "pedag": pedag.id, "periodo": periodo.id, "curso": curso.id,
            "turma": turma.id, "oferta": oferta.id, "aluno": aluno.id,
        }
    return app, ids


def _torna_nao_uniforme_pela_ui(app, ids):
    """POST real da tela de Cursos da Turma: modo personalizado (Seg 08–11,
    Qua 14–17)."""
    client = _client(app, ids["coord"], ids["unidade"])
    form = {
        "curso_id": str(ids["curso"]),
        "programa": "Profissionalizante",
        "professor_id": str(ids["prof"]),
        "turno": "Manhã",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "centro_custo": "",
        **GRADE_POR_DIA,
    }
    r = client.post(f"/turma/oferta/{ids['oferta']}/editar", data=form)
    assert r.status_code == 302
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        assert oferta.carga_horaria_aula is None  # não uniforme: sem duração única


# --- leitores via HTTP ---------------------------------------------------------
class TestLeitoresSemErroComGradeVariavel:
    def test_listagem_exibe_por_dia_e_filtros_casam_na_mesma_linha(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        cli = _client(app, ids["coord"], ids["unidade"])

        lista_raw = cli.get("/turma").get_data(as_text=True)
        assert f'href="/turma/{ids["turma"]}"' in lista_raw
        assert POR_DIA in _norm(lista_raw)

        # dia + hora na MESMA linha da grade: Quarta 14:00 casa; Segunda 14:00 não.
        achou = _norm(cli.get(
            f"/turma?dia=Quarta&horario_inicio=14:00&ano_periodo=2026"
        ).get_data(as_text=True))
        assert POR_DIA in achou
        nao_achou = cli.get(
            f"/turma?dia=Segunda&horario_inicio=14:00&ano_periodo=2026"
        ).get_data(as_text=True)
        assert f'href="/turma/{ids["turma"]}"' not in nao_achou

    def test_detalhe_impressao_e_tela_de_cursos(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        cli = _client(app, ids["coord"], ids["unidade"])

        detalhe = _norm(
            cli.get(f"/turma/{ids['turma']}").get_data(as_text=True)
        )
        assert POR_DIA in detalhe

        r = cli.get(f"/turma/{ids['turma']}/imprimir-pauta")
        assert r.status_code == 200

        cursos = cli.get(f"/turma/{ids['turma']}/ofertas").get_data(as_text=True)
        assert POR_DIA in _norm(cursos)
        assert ">varia<" in cursos
        assert re.search(r'name="horario_por_dia"[^>]*checked', cursos)

    def test_carga_horaria_da_oferta_e_da_turma_sem_erro(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        cli = _client(app, ids["coord"], ids["unidade"])
        r = cli.get(f"/turmas/carga-horaria?periodo_id={ids['periodo']}")
        assert r.status_code == 200
        with app.app_context():
            oferta = db.session.get(TurmaCurso, ids["oferta"])
            turma = db.session.get(Turma, ids["turma"])
            # Seg+Qua 3h cada por semana, vigência de 2026-03-02 a 2026-12-15.
            assert oferta.carga_horaria_total and oferta.carga_horaria_total > 0
            assert turma.carga_horaria_total == oferta.carga_horaria_total
            assert oferta.carga_horaria_aula is None

    def test_concomitancia_com_agenda_por_dia_nao_gera_erro(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        with app.app_context():
            conflitos = _conflitos_horario_concomitante(
                ids["turma"],
                agenda=[(0, time(9), time(10)), (2, time(15), time(16))],
                data_inicio=DATA_INI,
                data_fim=DATA_FIM,
            )
        # Uma mensagem por oferta concorrente, com os dias por extenso —
        # alerta, nunca exceção.
        assert conflitos and any(
            "Segunda 08:00–11:00" in c and "Quarta 14:00–17:00" in c
            for c in conflitos
        )

    def test_dashboard_por_data_usa_o_intervalo_do_weekday(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        # 02/03 e 04/03 já têm frequência lançada no seed — as primeiras
        # pendências são a segunda e a quarta seguintes.
        texto = _norm(
            _client(app, ids["prof"]).get("/dashboard").get_data(as_text=True)
        )
        assert "09/03/2026 08:00–11:00 T-VAR" in texto  # segunda
        assert "11/03/2026 14:00–17:00 T-VAR" in texto  # quarta

    def test_aluno_ficha_atendimento_conselho_frequencia_seletor(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)
        cli = _client(app, ids["coord"], ids["unidade"])

        gerenciar = cli.get("/alunos").get_data(as_text=True)
        assert f'data-turma-horario="{POR_DIA}"' in gerenciar
        assert 'data-turma-dias="Segunda, Quarta"' in gerenciar

        atendimentos = _norm(
            cli.get("/alunos/atendimentos").get_data(as_text=True)
        )
        assert "Aluno Var" in atendimentos

        historico = _norm(
            cli.get(f"/aluno/{ids['aluno']}/historico").get_data(as_text=True)
        )
        assert POR_DIA in historico

        ficha = _norm(
            cli.get(
                f"/relatorios/alunos/{ids['aluno']}/ficha"
                f"?turma_id={ids['turma']}&oferta_sel={ids['oferta']}"
            ).get_data(as_text=True)
        )
        assert POR_DIA in ficha

        painel = _norm(cli.get("/conselho").get_data(as_text=True))
        assert POR_DIA in painel
        fechamento = _norm(
            cli.get(f"/conselho/fechamento/{ids['turma']}").get_data(as_text=True)
        )
        assert POR_DIA in fechamento

        transferir = _norm(
            cli.get(
                f"/aluno/transferir/{ids['aluno']}"
                f"?turma_origem_id={ids['turma']}&turma_curso_id={ids['oferta']}"
            ).get_data(as_text=True)
        )
        assert f"Horário: {POR_DIA}" in transferir

        prof_cli = _client(app, ids["prof"])
        r_freq = prof_cli.get(f"/frequencia?turma_id={ids['turma']}")
        assert r_freq.status_code == 200
        r_rel = _client(app, ids["pedag"], ids["unidade"]).get(
            f"/frequencia_relatorio?turma={ids['turma']}"
        )
        assert r_rel.status_code == 200

    def test_sem_n1_de_grade_na_listagem(self):
        app, ids = _seed()
        _torna_nao_uniforme_pela_ui(app, ids)

        def _medir_selects_de_grade():
            contador = {"n": 0}

            def _ouvir(conn, cursor, statement, parameters, context, executemany):
                if "turma_curso_horario" in statement.lower():
                    contador["n"] += 1

            cli = _client(app, ids["coord"], ids["unidade"])
            event.listen(db.engine, "before_cursor_execute", _ouvir)
            try:
                cli.get("/turma")
            finally:
                event.remove(db.engine, "before_cursor_execute", _ouvir)
            return contador["n"]

        with app.app_context():
            db.session.remove()
            antes = _medir_selects_de_grade()
            # Segunda turma com segunda oferta NÃO uniforme (mesmo esquema).
            curso2 = Curso(nome="Curso W", unidade_id=ids["unidade"], ativo=True)
            db.session.add(curso2)
            db.session.flush()
            t2 = Turma(
                nome="T-VAR2", unidade_id=ids["unidade"], curso_id=curso2.id,
                professor_id=ids["prof"], periodo_letivo_id=ids["periodo"],
                ativo=True, turno="Tarde", programa="Profissionalizante",
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                ordenacao=2,
            )
            db.session.add(t2)
            db.session.flush()
            o2 = TurmaCurso(
                turma_id=t2.id, curso_id=curso2.id, unidade_id=ids["unidade"],
                ativo=True, principal=True, professor_id=ids["prof"],
                turno="Tarde",
                data_inicio=DATA_INI, data_fim=DATA_FIM,
                programa="Profissionalizante",
            )
            db.session.add(o2)
            db.session.flush()
            definir_grade(
                o2, [(0, time(9), time(10)), (2, time(15), time(16))]
            )
            db.session.commit()
            depois = _medir_selects_de_grade()
        # O número de SELECTs em turma_curso_horario não cresce por turma/oferta.
        assert depois == antes

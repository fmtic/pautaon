"""
Onda 4 — Fase 4 (G2): editar_turma espelha oferta única e protege ofertas múltiplas.

Cobertura (só servidor, rota /turma/editar/<id>):
    - 1 oferta ativa: campos de oferta gravados na turma são espelhados na oferta.
    - 1 oferta ativa: trocar curso_id é recusado; nada muda (turma nem oferta).
    - 1 oferta com lançamentos: mudar horário exige confirmação; confirmada,
      limpa os lançamentos e a oferta acompanha.
    - 2+ ofertas: campos de oferta enviados são IGNORADOS; só nome/programa gravam.
    - 2+ ofertas: POST forjado com campos de oferta é descartado no servidor.
    - turma sem oferta: edição igual a hoje (sem espelhamento).
    - falha na validação não grava nem a turma nem a oferta (transação única).
"""

from datetime import date, time

import pytest

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from config import Config

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _novo_app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    return test_app


def _loga(app, resp_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(resp_id)
        session["_fresh"] = True
    return client


def _seed(*, ofertas=0, curso_turma=True, com_lancamentos=False):
    """App com unidade, pedagógico, 2 professores, 2 cursos, 1 turma e `ofertas`
    ofertas ativas (cursos A e B). Turma e ofertas nascem com o MESMO horário
    (09:00–10:00, Segunda, Manhã, prof P1). Retorna (app, ids)."""
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U edit", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        resp = User(
            name="Coord Edit", email="coord.edit@example.com",
            role="pedagogico", first_login=False, unidade_id=unidade.id,
        )
        p1 = User(
            name="Prof Um", email="prof1@example.com",
            role="professor", first_login=False, unidade_id=unidade.id,
        )
        p2 = User(
            name="Prof Dois", email="prof2@example.com",
            role="professor", first_login=False, unidade_id=unidade.id,
        )
        db.session.add_all([resp, p1, p2])

        cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
        cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
        db.session.add_all([cA, cB])
        db.session.flush()

        turma = Turma(
            nome="T edit", unidade_id=unidade.id, ativo=True,
            curso_id=(cA.id if curso_turma else None),
            professor_id=p1.id, turno="Manhã", dias_semana="Segunda",
            hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(turma)
        db.session.flush()

        oferta_ids = []
        for i in range(ofertas):
            o = TurmaCurso(
                turma_id=turma.id, curso_id=(cA.id if i == 0 else cB.id),
                unidade_id=unidade.id, ativo=True, principal=(i == 0),
                professor_id=p1.id, turno="Manhã", dias_semana="Segunda",
                hora_inicio=time(9, 0), hora_fim=time(10, 0),
                data_inicio=DATA_INI, data_fim=DATA_FIM,
            )
            db.session.add(o)
            db.session.flush()
            oferta_ids.append(o.id)

        aluno_id = None
        if com_lancamentos and oferta_ids:
            aluno = Aluno(nome="Aluno L", unidade_id=unidade.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            db.session.add(Frequencia(
                aluno_id=aluno.id, turma_id=turma.id,
                turma_curso_id=oferta_ids[0], data=DATA_INI,
                conceito=ConceitoFrequencia.A, unidade_id=unidade.id,
            ))
            aluno_id = aluno.id

        db.session.commit()
        ids = {
            "resp": resp.id, "unidade": unidade.id,
            "p1": p1.id, "p2": p2.id, "cA": cA.id, "cB": cB.id,
            "turma": turma.id, "ofertas": oferta_ids, "aluno": aluno_id,
        }
    return app, ids


def _post_edit(app, ids, **over):
    """POST /turma/editar/<id> com o formulário preenchido com os valores do
    seed (Mesmos da turma/oferta) e `over` aplicados por cima."""
    client = _loga(app, ids["resp"])
    form = {
        "turma": "T edit",
        "programa": "Profissionalizante",
        "turno": "Manhã",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "hora_inicio": "09:00",
        "hora_fim": "10:00",
        "professor_id": str(ids["p1"]),
        "dias_semana": "Segunda",
        "centro_custo": "",
        "curso_id": str(ids["cA"]),
        "periodo_letivo_id": "",
        "limpar_lancamentos": "0",
    }
    form.update(over)
    return client.post(f"/turma/editar/{ids['turma']}", data=form)


# --- 1 oferta: espelha professor/turno/horários/datas na oferta -------------
def test_edicao_uma_oferta_espelha_campos_na_oferta():
    app, ids = _seed(ofertas=1)
    r = _post_edit(
        app, ids,
        professor_id=str(ids["p2"]), turno="Tarde",
        data_inicio=DATA_INI.isoformat(), data_fim=DATA_FIM.isoformat(),
        hora_inicio="11:00", hora_fim="12:30", dias_semana="Terça",
    )
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert turma.professor_id == ids["p2"]
        assert turma.turno == "Tarde"
        assert turma.hora_inicio == time(11, 0)
        assert turma.hora_fim == time(12, 30)
        assert turma.dias_semana == "Terça"
        # A oferta acompanha exatamente o que foi gravado na turma.
        assert oferta.professor_id == ids["p2"]
        assert oferta.turno == "Tarde"
        assert oferta.hora_inicio == time(11, 0)
        assert oferta.hora_fim == time(12, 30)
        assert oferta.dias_semana == "Terça"
        assert oferta.curso_id == ids["cA"]  # curso não mudou


# --- 1 oferta: trocar curso_id é recusado; nada muda ------------------------
def test_edicao_uma_oferta_troca_curso_recusada_nada_muda():
    app, ids = _seed(ofertas=1)
    r = _post_edit(
        app, ids,
        turma="TRENTO",  # renomearia se fosse gravado
        curso_id=str(ids["cB"]),
        professor_id=str(ids["p2"]), turno="Noite",
    )
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        # Recusado ANTES de qualquer gravação: nem o nome foi salvo.
        assert turma.nome == "T edit"
        assert turma.curso_id == ids["cA"]
        assert turma.professor_id == ids["p1"]
        assert turma.turno == "Manhã"
        assert oferta.curso_id == ids["cA"]
        assert oferta.professor_id == ids["p1"]


# --- 1 oferta com lançamentos: exige confirmação e, confirmada, limpa -------
def test_edicao_uma_oferta_com_lancamentos_exige_confirmacao():
    app, ids = _seed(ofertas=1, com_lancamentos=True)

    # Sem confirmação: muda o horário → bloqueia, nada muda, lançamento intacto.
    r = _post_edit(app, ids, hora_inicio="14:00", hora_fim="15:00")
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert turma.hora_inicio == time(9, 0)
        assert oferta.hora_inicio == time(9, 0)
        assert Frequencia.query.filter_by(turma_id=ids["turma"]).count() == 1

    # Confirmado: limpa os lançamentos e a oferta acompanha o novo horário.
    r2 = _post_edit(
        app, ids, hora_inicio="14:00", hora_fim="15:00",
        limpar_lancamentos="1",
    )
    assert r2.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert turma.hora_inicio == time(14, 0)
        assert oferta.hora_inicio == time(14, 0)
        assert oferta.hora_fim == time(15, 0)
        assert Frequencia.query.filter_by(turma_id=ids["turma"]).count() == 0


# --- 2+ ofertas: ignora campos de oferta; só nome/programa gravam -----------
def test_edicao_duas_ofertas_ignora_campos_de_oferta():
    app, ids = _seed(ofertas=2)
    r = _post_edit(
        app, ids,
        turma="T edit NOVA", programa="Esporte",
        curso_id=str(ids["cB"]), professor_id=str(ids["p2"]), turno="Noite",
        hora_inicio="20:00", hora_fim="21:00", dias_semana="Sábado",
    )
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        # Nome/programa gravados:
        assert turma.nome == "T edit NOVA"
        assert turma.programa == "Esporte"
        # Campos de oferta IGNORADOS na turma:
        assert turma.curso_id == ids["cA"]
        assert turma.professor_id == ids["p1"]
        assert turma.turno == "Manhã"
        assert turma.hora_inicio == time(9, 0)
        assert turma.dias_semana == "Segunda"
        # Nenhuma oferta alterada:
        for oid in ids["ofertas"]:
            o = db.session.get(TurmaCurso, oid)
            assert o.professor_id == ids["p1"]
            assert o.turno == "Manhã"
            assert o.hora_inicio == time(9, 0)


# --- 2+ ofertas: POST forjado só com campos de oferta é descartado ----------
def test_edicao_duas_ofertas_post_forjado_descartado():
    app, ids = _seed(ofertas=2)
    # Mantém nome/programa idênticos e forja apenas campos de oferta.
    r = _post_edit(
        app, ids,
        professor_id=str(ids["p2"]), turno="Noite",
        hora_inicio="23:00", hora_fim="23:30", curso_id=str(ids["cB"]),
    )
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma.professor_id == ids["p1"]
        assert turma.turno == "Manhã"
        assert turma.hora_inicio == time(9, 0)
        assert turma.curso_id == ids["cA"]
        assert TurmaCurso.query.filter_by(
            turma_id=ids["turma"], hora_inicio=time(23, 0)
        ).count() == 0


# --- turma sem oferta: edição igual a hoje (sem espelhamento) ---------------
def test_edicao_sem_oferta_comportamento_atual():
    app, ids = _seed(ofertas=0, curso_turma=True)
    r = _post_edit(
        app, ids,
        professor_id=str(ids["p2"]), turno="Tarde",
        hora_inicio="11:00", hora_fim="12:00", curso_id=str(ids["cB"]),
    )
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma.professor_id == ids["p2"]
        assert turma.turno == "Tarde"
        assert turma.hora_inicio == time(11, 0)
        assert turma.curso_id == ids["cB"]  # troca de curso permitida sem oferta
        assert TurmaCurso.query.filter_by(turma_id=ids["turma"]).count() == 0


# --- falha na validação não grava nem turma nem oferta ----------------------
def test_edicao_falha_validacao_rollback_turma_e_oferta(monkeypatch):
    app, ids = _seed(ofertas=1)
    import app.registros.turmas as turmas_mod

    def _boom(*a, **k):
        raise ValueError("conflito artificial")

    monkeypatch.setattr(turmas_mod, "_validar_horario_concomitante", _boom)

    r = _post_edit(
        app, ids, turma="T edit POS-ROLLBACK",
        hora_inicio="14:00", hora_fim="15:00",
    )
    # Após o except, a rota cai no GET e re-renderiza (200).
    assert r.status_code == 200
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert turma.nome == "T edit"
        assert turma.hora_inicio == time(9, 0)
        assert oferta.hora_inicio == time(9, 0)


# =============================================================================
# ETAPA G3 — tela de edição: bloco "Cursos desta turma" e campos somente leitura
# =============================================================================

def _get_edicao(app, ids):
    client = _loga(app, ids["resp"])
    return client.get(f"/turma/editar/{ids['turma']}")


# --- G3: GET renderiza com 0, 1 e 2 ofertas ---------------------------------
def test_g3_get_edicao_renderiza_0_1_2_ofertas():
    for n in (0, 1, 2):
        app, ids = _seed(ofertas=n)
        r = _get_edicao(app, ids)
        assert r.status_code == 200, f"esperava 200 com {n} oferta(s)"


# --- G3: 0 ofertas — bloco não aparece --------------------------------------
def test_g3_sem_oferta_bloco_nao_aparece():
    app, ids = _seed(ofertas=0)
    html = _get_edicao(app, ids).get_data(as_text=True)
    assert "Cursos desta turma" not in html
    assert 'type="hidden" name="curso_id"' not in html


# --- G3: 1 oferta — hidden curso_id (da OFERTA) + botão + nota --------------
def test_g3_uma_oferta_hidden_curso_e_botao():
    app, ids = _seed(ofertas=1)
    html = _get_edicao(app, ids).get_data(as_text=True)
    assert "Cursos desta turma" in html
    assert "Adicionar curso" in html
    assert f'curso_id" value="{ids["cA"]}"' in html      # hidden = curso da oferta ativa
    assert "Para trocar o curso" in html
    assert '<select name="turno"' in html                # demais campos editáveis


# --- G3: 2+ ofertas — campos de oferta readonly -----------------------------
def test_g3_muitas_ofertas_readonly():
    app, ids = _seed(ofertas=2)
    r = _get_edicao(app, ids)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Com mais de um curso" in html
    assert "readonly" in html
    assert 'name="dias_semana" value=' in html           # hidden com valor atual
    assert 'name="professor_id" value=' in html


# --- G3: curso legado A + oferta A desativada + oferta B ativa → hidden é B -
def test_g3_oferta_desativada_e_ativa_hidden_e_ativa_e_nome_aceito():
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U mix", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        resp = User(name="Coord Mix", email="coord.mix@example.com",
                    role="pedagogico", first_login=False, unidade_id=unidade.id)
        p1 = User(name="Prof Mix", email="prof.mix@example.com",
                  role="professor", first_login=False, unidade_id=unidade.id)
        cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
        cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
        db.session.add_all([resp, p1, cA, cB])
        db.session.flush()
        turma = Turma(
            nome="T mix", unidade_id=unidade.id, ativo=True, curso_id=cA.id,
            professor_id=p1.id, turno="Manhã", dias_semana="Segunda",
            hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(turma)
        db.session.flush()
        db.session.add_all([
            TurmaCurso(turma_id=turma.id, curso_id=cA.id, unidade_id=unidade.id,
                       ativo=False, principal=False),                 # A desativada
            TurmaCurso(turma_id=turma.id, curso_id=cB.id, unidade_id=unidade.id,
                       ativo=True, principal=True),                    # B ativa
        ])
        db.session.commit()
        ids = {"resp": resp.id, "turma": turma.id, "cA": cA.id, "cB": cB.id,
               "p1": p1.id, "p2": p1.id}

    # 1 oferta ATIVA (B) → hidden curso_id deve valer B, não o legado A.
    html = _get_edicao(app, ids).get_data(as_text=True)
    assert f'curso_id" value="{ids["cB"]}"' in html
    assert 'curso_id" value="%s"' % ids["cA"] not in html

    # POST com nome novo e curso_id=B (igual à oferta ativa) é aceito.
    _post_edit(app, ids, turma="T mix RENOMEADA", curso_id=str(ids["cB"]))
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma.nome == "T mix RENOMEADA"
        assert turma.curso_id == ids["cB"]

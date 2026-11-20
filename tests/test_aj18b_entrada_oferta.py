"""AJ18-B — data de entrada do aluno na oferta.

Cobre: coluna/migration (NULL), enturmar com cada opção, janela inválida,
lote atômico, oferta não iniciada sem pergunta, transferência grava a data,
re-enturmação cria inscrição nova com corte próprio, template renderiza a
pergunta só quando a oferta já começou, funções do serviço (incl. início
herdado da turma).
"""
from datetime import date, timedelta

import pytest

from app import create_app, db
from app.models import Aluno, Curso, Inscricao, LogAcao, Turma, TurmaCurso, Unidade, User
from config import Config
from _helpers import login_as, nova_inscricao, hoje_ref

HOJE = hoje_ref()
INI_PASSADO = date(HOJE.year, 1, 2)
FIM_FUTURO = date(HOJE.year, 12, 20)
INI_FUTURO = HOJE + timedelta(days=30)
FIM_FUTURO2 = HOJE + timedelta(days=120)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
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
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _loga(app, user_id):
    client = app.test_client()
    login_as(client, str(user_id))
    return client


def _base(unidade_nome="U AJ18B"):
    unidade = Unidade(nome=unidade_nome, ativo=True)
    db.session.add(unidade)
    db.session.flush()
    resp = User(
        name="Coord AJ18B", email=f"coord.{unidade_nome}@example.com",
        role="pedagogico", first_login=False, unidade_id=unidade.id,
    )
    prof = User(
        name="Prof AJ18B", email=f"prof.{unidade_nome}@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    curso = Curso(nome="Curso AJ18B", unidade_id=unidade.id, ativo=True)
    db.session.add_all([resp, prof, curso])
    db.session.flush()
    return {"unidade": unidade.id, "resp": resp.id, "prof": prof.id, "curso": curso.id}


def _turma(i, *, data_inicio=INI_PASSADO, data_fim=FIM_FUTURO, oferta_inicio=None, oferta_fim=None):
    turma = Turma(
        nome="Turma AJ18B", unidade_id=i["unidade"], ativo=True,
        curso_id=i["curso"], professor_id=i["prof"], turno="Manhã",
        data_inicio=data_inicio, data_fim=data_fim,
    )
    db.session.add(turma)
    db.session.flush()
    oferta = TurmaCurso(
        turma_id=turma.id, curso_id=i["curso"], unidade_id=i["unidade"],
        ativo=True, principal=True, professor_id=i["prof"], turno="Manhã",
        data_inicio=oferta_inicio, data_fim=oferta_fim, programa="Teste",
    )
    db.session.add(oferta)
    db.session.flush()
    return {"turma": turma.id, "oferta": oferta.id, "turma_obj": turma, "oferta_obj": oferta}


def _aluno(i, nome="Aluno AJ18B"):
    a = Aluno(nome=nome, ativo=True, unidade_id=i["unidade"])
    db.session.add(a)
    db.session.flush()
    return a.id


# --- coluna / migração (schema em testes) ------------------------------------
def test_coluna_data_entrada_oferta_nullable(app):
    with app.app_context():
        cols = {c["name"]: c for c in db.inspect(db.engine).get_columns("inscricoes")}
        assert "data_entrada_oferta" in cols
        assert cols["data_entrada_oferta"]["nullable"] is True


def test_inscricao_antiga_permanece_null(app):
    with app.app_context():
        i = _base()
        t = _turma(i)
        a = _aluno(i)
        # criação direta, como inscrições legadas (sem campo novo)
        insc = Inscricao(
            aluno_id=a, turma_id=t["turma"], turma_curso_id=t["oferta"],
            ativo=True, data_inicio=INI_PASSADO,
        )
        db.session.add(insc)
        db.session.commit()
        assert db.session.get(Inscricao, insc.id).data_entrada_oferta is None


# --- enturmar com cada opção -------------------------------------------------
def test_enturmar_opcao_inicio_grava_null(app):
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": str(aid), f"entrada_{aid}": "inicio",
    })
    assert r.status_code == 302
    with app.app_context():
        insc = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).one()
        assert insc.data_entrada_oferta is None


def test_enturmar_opcao_hoje_grava_hoje(app):
    from app.utils.timezone import get_local_now

    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": str(aid), f"entrada_{aid}": "hoje",
    })
    assert r.status_code == 302
    with app.app_context():
        insc = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).one()
        assert insc.data_entrada_oferta == get_local_now().date()


def test_enturmar_data_especifica_grava_data(app):
    data_esp = HOJE - timedelta(days=5)
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": str(aid), f"entrada_{aid}": data_esp.isoformat(),
    })
    assert r.status_code == 302
    with app.app_context():
        insc = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).one()
        assert insc.data_entrada_oferta == data_esp


# --- janela inválida e lote atômico -----------------------------------------
def test_janela_invalida_recusa_sem_gravar(app):
    fora = INI_PASSADO - timedelta(days=10)
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": str(aid), f"entrada_{aid}": fora.isoformat(),
    }, follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "data de entrada" in body.lower() or "vig" in body.lower() or "entre" in body.lower()
    with app.app_context():
        assert Inscricao.query.filter_by(turma_id=tid, ativo=True).count() == 0


def test_lote_atomico_falta_escolha_de_um_aluno(app):
    with app.app_context():
        i = _base(); t = _turma(i)
        a1 = _aluno(i, "Aluno 1"); a2 = _aluno(i, "Aluno 2")
        db.session.commit()
        tid = t["turma"]
    client = _loga(app, i["resp"])
    # só a1 tem entrada; a2 falta -> recusa lote inteiro
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": [str(a1), str(a2)],
        f"entrada_{a1}": "hoje",
        # entrada_{a2} ausente
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert Inscricao.query.filter_by(turma_id=tid, ativo=True).count() == 0


def test_oferta_iniciada_sem_nenhum_campo_entrada_recusa_lote(app):
    with app.app_context():
        i = _base(); t = _turma(i)
        a1 = _aluno(i, "Aluno 1"); a2 = _aluno(i, "Aluno 2")
        db.session.commit()
        tid = t["turma"]
    client = _loga(app, i["resp"])
    # nenhum campo entrada_* enviado -> recusa atômica (sem compatibilidade legada)
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": [str(a1), str(a2)],
    }, follow_redirects=True)
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "data de entrada" in body.lower()
    with app.app_context():
        assert Inscricao.query.filter_by(turma_id=tid, ativo=True).count() == 0


def test_hoje_fora_da_janela_oferta_encerrada_recusado(app):
    # oferta já começou e já terminou antes de hoje -> "hoje" inválido
    fim_passado = HOJE - timedelta(days=5)
    with app.app_context():
        i = _base()
        t = _turma(i, data_inicio=INI_PASSADO, data_fim=fim_passado)
        a = _aluno(i)
        db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.post(f"/turma/enturmar/{tid}", data={
        "aluno_ids[]": str(aid), f"entrada_{aid}": "hoje",
    }, follow_redirects=True)
    assert r.status_code == 200
    with app.app_context():
        assert Inscricao.query.filter_by(turma_id=tid, ativo=True).count() == 0


# --- oferta não iniciada: sem pergunta, NULL ---------------------------------
def test_oferta_nao_iniciada_sem_pergunta_e_null(app):
    with app.app_context():
        i = _base()
        t = _turma(i, data_inicio=INI_FUTURO, data_fim=FIM_FUTURO2)
        a = _aluno(i)
        db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    # GET: não deve renderizar pergunta obrigatória
    rget = client.get(f"/turma/{tid}?oferta_sel={t['oferta']}&modal=enturmar")
    assert rget.status_code == 200
    body = rget.get_data(as_text=True)
    assert "entrada-obrigatoria-aviso" not in body
    assert f'name="entrada_{aid}"' not in body
    # POST sem entrada_* -> permitido e NULL
    r = client.post(f"/turma/enturmar/{tid}", data={"aluno_ids[]": str(aid)})
    assert r.status_code == 302
    with app.app_context():
        insc = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).one()
        assert insc.data_entrada_oferta is None


# --- transferência grava data; re-enturmação corte próprio -------------------
def test_transferencia_grava_data_entrada(app):
    with app.app_context():
        i = _base()
        # origem com oferta iniciada
        t1 = _turma(i)
        a = _aluno(i)
        nova_inscricao(a, t1["turma"], t1["oferta"])
        # destino (outra turma) iniciado
        turma2 = Turma(
            nome="Turma Dest", unidade_id=i["unidade"], ativo=True,
            curso_id=i["curso"], professor_id=i["prof"], turno="Tarde",
            data_inicio=INI_PASSADO, data_fim=FIM_FUTURO,
        )
        db.session.add(turma2); db.session.flush()
        o2 = TurmaCurso(
            turma_id=turma2.id, curso_id=i["curso"], unidade_id=i["unidade"],
            ativo=True, principal=True, professor_id=i["prof"], turno="Tarde",
            programa="Teste",
        )
        db.session.add(o2); db.session.flush()
        db.session.commit()
        aid, tid1, oid1, oid2 = a, t1["turma"], t1["oferta"], o2.id
        data_t = (HOJE - timedelta(days=3)).isoformat()

    client = _loga(app, i["resp"])
    r = client.post(f"/aluno/transferir/{aid}", data={
        "turma_origem_id": str(tid1),
        "turma_curso_id": str(oid1),
        "turma_curso_id_destino": str(oid2),
        "data_transferencia": data_t,
        "observacoes": "Motivo X",
    })
    assert r.status_code == 302
    with app.app_context():
        nova = Inscricao.query.filter_by(aluno_id=aid, turma_curso_id=oid2, ativo=True).one()
        assert nova.data_entrada_oferta.isoformat() == data_t


def test_reenturmacao_cria_inscricao_nova_com_corte_proprio(app):
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    d1 = (HOJE - timedelta(days=10)).isoformat()
    d2 = (HOJE - timedelta(days=2)).isoformat()
    client.post(f"/turma/enturmar/{tid}", data={"aluno_ids[]": str(aid), f"entrada_{aid}": d1})
    # desenturmar (sem frequência -> delete físico ou soft conforme regra; força estado inativo para reenturmar)
    with app.app_context():
        insc1 = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).one()
        insc1_id = insc1.id
        insc1.ativo = False
        db.session.commit()
    client.post(f"/turma/enturmar/{tid}", data={"aluno_ids[]": str(aid), f"entrada_{aid}": d2})
    with app.app_context():
        ativas = Inscricao.query.filter_by(turma_id=tid, aluno_id=aid, ativo=True).all()
        assert len(ativas) == 1
        assert ativas[0].id != insc1_id
        assert ativas[0].data_entrada_oferta.isoformat() == d2
        antiga = db.session.get(Inscricao, insc1_id)
        assert antiga.data_entrada_oferta.isoformat() == d1


# --- template: pergunta só quando oferta já começou ---------------------------
def test_template_pergunta_apenas_quando_oferta_ja_comecou(app):
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    r = client.get(f"/turma/{tid}?oferta_sel={t['oferta']}&modal=enturmar")
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "entrada-obrigatoria-aviso" in body
    assert f'name="entrada_{aid}"' in body
    assert 'value="hoje"' in body
    assert 'value="inicio"' in body
    # sem opção pré-selecionada
    assert 'name="entrada_' in body and "checked" not in body.split('name="entrada_')[1].split(">")[0]


# --- serviço: funções e início herdado da turma -------------------------------
def test_servico_funcoes_e_inicio_herdado_da_turma(app):
    from types import SimpleNamespace
    from app.services.entrada_oferta import (
        aula_conta_para_aluno,
        datas_esperadas_do_aluno,
        inicio_efetivo,
        vigencia_efetiva,
    )

    with app.app_context():
        i = _base()
        # oferta sem datas -> herda da turma
        t = _turma(i, data_inicio=INI_PASSADO, data_fim=FIM_FUTURO, oferta_inicio=None, oferta_fim=None)
        oferta = db.session.get(TurmaCurso, t["oferta"])
        turma = db.session.get(Turma, t["turma"])
        assert inicio_efetivo(oferta) == turma.data_inicio
        ini, fim = vigencia_efetiva(oferta)
        assert ini == turma.data_inicio and fim == turma.data_fim

        insc = SimpleNamespace(data_entrada_oferta=HOJE)
        assert aula_conta_para_aluno(insc, HOJE) is True
        assert aula_conta_para_aluno(insc, HOJE - timedelta(days=1)) is False
        assert aula_conta_para_aluno(SimpleNamespace(data_entrada_oferta=None), INI_PASSADO) is True

        datas = datas_esperadas_do_aluno(insc, oferta)
        assert all(d >= HOJE for d in datas)
        todas = datas_esperadas_do_aluno(SimpleNamespace(data_entrada_oferta=None), oferta)
        assert len(todas) >= len(datas)


def test_logacao_por_aluno_enturmado(app):
    with app.app_context():
        i = _base(); t = _turma(i); a = _aluno(i, "Aluno Log"); db.session.commit()
        tid, aid = t["turma"], a
    client = _loga(app, i["resp"])
    client.post(f"/turma/enturmar/{tid}", data={"aluno_ids[]": str(aid), f"entrada_{aid}": "hoje"})
    with app.app_context():
        logs = LogAcao.query.filter_by(acao="Enturmação de aluno na oferta").all()
        assert len(logs) == 1
        assert f"aluno_id={aid}" in (logs[0].detalhes or "")
        assert "entrada=hoje" in (logs[0].detalhes or "")

"""ETAPA D5.2 — escrita do conselho por oferta (rotas de lançamento,
fechamento e avaliação coletiva).

Regras cobertas (docs/D5_0_desenho.md D5.2 + decisões Q1/Q4/Q5):
    - Padrão M1: 1 oferta ativa = uso direto; 2+ exige escolha validada
      contra `ofertas_ativas(turma)`; 0 ofertas recusa; oferta inativa ou de
      outra turma é recusada sem gravar.
    - Todo ConselhoClasse nasce com `turma_curso_id` OBRIGATÓRIO; desde a
      D5.5 o banco recusa conselho sem oferta (o ramo legado NULL saiu).
    - Respostas tipo TURMA saem de ConselhoResposta e passam a viver em
      `TurmaCurso.avaliacao_*` (JSON da avaliação coletiva da oferta).
    - Fechamento por oferta: situacao_final/proxima_turma_id no conselho da
      oferta, próximas turmas via catálogo OpcaoProximaTurma e frequência
      filtrada por `Frequencia.turma_curso_id`.
    - `alternar_conselho` alterna SÓ a oferta (D5.5: a ponte que escrevia
      `Turma.conselho_concluido` foi removida junto com a coluna).
    - Isolamento por unidade (B3/B4) vale para todos os perfis.

Um usuário por teste (T1 §5.6): cada teste cria o próprio `test_client()` e
fixa a sessão uma única vez.
"""

import json
import re
from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from app import create_app
from app.database import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    Frequencia,
    OpcaoProximaTurma,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from config import Config
from _helpers import nova_inscricao, nova_oferta

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SERVER_NAME": "localhost",
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _loga(client, ids, unidade_id=None):
    """Simula login gravando a sessão direto (padrão do harness B4)."""
    with client.session_transaction() as sess:
        sess["_user_id"] = str(ids["user_id"])
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def _setup(app, *, ofertas=1, role="admin", turma_b=False, unidade="A"):
    """Semeia unidade A (e opcionalmente B), usuário, turma com N ofertas
    ativas (a última pode ser inativa via `ofertas='1+1i'`), 2 alunos com
    inscrição na primeira oferta e perguntas ALUNO/TURMA da etapa INICIAL.

    Retorna dicionário com ids/objetos úteis. `ofertas` é o número de
    ofertas ATIVAS na turma (cursos distintos, por causa da UNIQUE).
    """
    with app.app_context():
        un_a = Unidade(nome="Unidade A", ativo=True)
        db.session.add(un_a)
        db.session.flush()

        usuario = User(
            name=f"Usuario {role}",
            email=f"{role}.d52@example.com",
            role=role,
            first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add(usuario)

        periodo = PeriodoLetivo(
            nome="Periodo A", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_a.id, ativo=True,
        )
        db.session.add(periodo)

        turma = Turma(
            nome="Turma D52", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id, unidade_id=un_a.id,
            ativo=True,
        )
        db.session.add(turma)

        aluno_a = Aluno(nome="Aluno Ana", unidade_id=un_a.id, ativo=True)
        aluno_b = Aluno(nome="Aluno Beto", unidade_id=un_a.id, ativo=True)
        db.session.add_all([usuario, periodo, turma, aluno_a, aluno_b])
        db.session.flush()

        n_ativas = ofertas if isinstance(ofertas, int) else 1
        oferta_ids = []
        for i in range(n_ativas):
            curso = Curso(nome=f"Curso {i + 1}", unidade_id=un_a.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            o = nova_oferta(turma.id, curso.id, un_a.id,
                            programa=f"Programa {i + 1}",
                            principal=(i == 0))
            oferta_ids.append(o.id)

        oferta_inativa_id = None
        if not isinstance(ofertas, int):  # ex.: "1+1i" → 1 ativa + 1 inativa
            curso = Curso(nome="Curso Inativo", unidade_id=un_a.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            oi = nova_oferta(turma.id, curso.id, un_a.id, programa="Programa X",
                             ativo=False)
            oferta_inativa_id = oi.id

        db.session.commit()

        return {
            "user_id": usuario.id,
            "un_a": un_a.id,
            "turma": turma.id,
            "aluno_a": aluno_a.id,
            "aluno_b": aluno_b.id,
            "ofertas": oferta_ids,
            "oferta_inativa": oferta_inativa_id,
        }


def _enturma(app, ids, aluno_key, oferta_idx=0):
    with app.app_context():
        nova_inscricao(ids[aluno_key], ids["turma"], ids["ofertas"][oferta_idx])
        db.session.commit()


def _perguntas(app):
    with app.app_context():
        p_aluno = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como o aluno participa das aulas?", ativo=True,
        )
        p_turma = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="TURMA",
            texto="Como a turma como um todo evoluiu?", ativo=True,
        )
        db.session.add_all([p_aluno, p_turma])
        db.session.commit()
        return p_aluno.id, p_turma.id


# ---------------------------------------------------------------------------
# Passo 2/3 — seleção da oferta no lançamento
# ---------------------------------------------------------------------------

def test_lancamento_turma_sem_oferta_recusa(client, app):
    ids = _setup(app, ofertas=0)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_lancamento_oferta_unica_usa_direto_e_vincula(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    assert r.status_code == 200
    with app.app_context():
        conselhos = ConselhoClasse.query.filter_by(etapa=EtapaConselho.INICIAL).all()
        assert len(conselhos) == 1
        assert conselhos[0].turma_curso_id == ids["ofertas"][0]
        assert conselhos[0].turma_id == ids["turma"]
        assert conselhos[0].aluno_id == ids["aluno_a"]


def test_lancamento_duas_ofertas_exige_escolha(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    _loga(client, ids, unidade_id=ids["un_a"])

    # Sem escolha: nada é listado nem criado; página só oferece o seletor.
    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    assert r.status_code == 200
    assert b"Selecione o curso" in r.data
    with app.app_context():
        assert ConselhoClasse.query.count() == 0

    # Com escolha válida: cria conselho vinculado Àquela oferta.
    r = client.get(
        f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
        f"&oferta_sel={ids['ofertas'][1]}"
    )
    assert r.status_code == 200
    with app.app_context():
        conselhos = ConselhoClasse.query.all()
        assert len(conselhos) == 1
        assert conselhos[0].turma_curso_id == ids["ofertas"][1]


def test_lancamento_oferta_de_outra_turma_recusada(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    with app.app_context():
        curso2 = Curso(nome="Curso Z", unidade_id=ids["un_a"], ativo=True)
        db.session.add(curso2)
        db.session.flush()
        turma2 = Turma(
            nome="Turma Z", turno="Tarde", data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            unidade_id=ids["un_a"], ativo=True,
        )
        db.session.add(turma2)
        db.session.flush()
        outra_oferta = nova_oferta(turma2.id, curso2.id, ids["un_a"],
                                   programa="Programa Z")
        outra_oferta_id = outra_oferta.id
        db.session.commit()
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(
        f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
        f"&oferta_sel={outra_oferta_id}"
    )
    assert r.status_code == 302  # recusa, volta aos filtros
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_salvar_recusa_oferta_inativa_sem_gravar(client, app):
    ids = _setup(app, ofertas="1+1i")
    _enturma(app, ids, "aluno_a")
    p_aluno, _ = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["oferta_inativa"]),
        f"resp_{ids['aluno_a']}_{p_aluno}": "Resposta",
    })
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoClasse.query.count() == 0
        assert ConselhoResposta.query.count() == 0


# ---------------------------------------------------------------------------
# Passo 3 — lançamento/salvar por oferta
# ---------------------------------------------------------------------------

def test_salvar_grava_respostas_na_oferta_e_ignora_turma_type(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    p_aluno, p_turma = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    # Abre o lançamento (cria os conselhos da oferta) e depois salva.
    client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ofertas"][0]),
        f"resp_{ids['aluno_a']}_{p_aluno}": "Muito bem",
        f"resp_turma_{p_turma}": "Parecer coletivo nao deve virar resposta",
    })
    assert r.status_code == 302
    with app.app_context():
        respostas = ConselhoResposta.query.all()
        # Só a resposta tipo ALUNO é gravada; o gravador paralelo de TURMA
        # foi removido (Q5: parecer coletivo vive no JSON da oferta).
        assert len(respostas) == 1
        assert respostas[0].aluno_id == ids["aluno_a"]
        assert respostas[0].pergunta_id == p_aluno
        conselho = db.session.get(ConselhoClasse, respostas[0].conselho_id)
        assert conselho.turma_curso_id == ids["ofertas"][0]


def test_salvar_ignora_aluno_sem_inscricao_na_oferta(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")  # aluno_b NÃO está matriculado
    p_aluno, _ = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ofertas"][0]),
        f"resp_{ids['aluno_a']}_{p_aluno}": "Ok",
        f"resp_{ids['aluno_b']}_{p_aluno}": "De fora da oferta",
    })
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoResposta.query.count() == 1
        assert ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_b"]
        ).count() == 0


def test_aluno_em_duas_ofertas_tem_um_conselho_por_oferta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    _loga(client, ids, unidade_id=ids["un_a"])

    for idx in (0, 1):
        r = client.get(
            f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
            f"&oferta_sel={ids['ofertas'][idx]}"
        )
        assert r.status_code == 200
    with app.app_context():
        do_aluno = ConselhoClasse.query.filter_by(aluno_id=ids["aluno_a"]).all()
        assert len(do_aluno) == 2
        assert {c.turma_curso_id for c in do_aluno} == set(ids["ofertas"])


def test_conselho_sem_oferta_recusado_pelo_banco(client, app):
    """D5.5: conselho sem oferta deixou de existir — o fluxo por oferta nunca
    adota uma linha sem chave (antes havia linha legada com `turma_curso_id`
    NULL convivendo; agora o próprio banco recusa)."""
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")

    with app.app_context():
        db.session.add(ConselhoClasse(
            turma_id=ids["turma"], aluno_id=ids["aluno_a"],
            etapa=EtapaConselho.INICIAL, turma_curso_id=None,
            unidade_id=ids["un_a"],
        ))
        with pytest.raises(IntegrityError):
            db.session.commit()
        db.session.rollback()

    _loga(client, ids, unidade_id=ids["un_a"])
    client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    with app.app_context():
        linhas = ConselhoClasse.query.all()
        assert len(linhas) == 1
        assert linhas[0].turma_curso_id == ids["ofertas"][0]


# ---------------------------------------------------------------------------
# Passo 4 — avaliação coletiva por oferta (Q1)
# ---------------------------------------------------------------------------

def test_avaliar_grava_na_oferta_nao_na_turma(client, app):
    ids = _setup(app, ofertas=1)
    _, p_turma = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL",
        data={
            "turma_curso_id": str(ids["ofertas"][0]),
            f"resp_turma_{p_turma}": "Turma evoluiu bem",
        },
    )
    assert r.status_code == 302
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        turma = db.session.get(Turma, ids["turma"])
        dados = json.loads(oferta.avaliacao_inicial)
        assert dados[str(p_turma)] == "Turma evoluiu bem"
        assert turma.avaliacao_inicial is None  # legado intocado
        assert ConselhoResposta.query.count() == 0


def test_avaliar_duas_ofertas_exige_escolha(client, app):
    ids = _setup(app, ofertas=2)
    _, p_turma = _perguntas(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL",
        data={f"resp_turma_{p_turma}": "Sem oferta"},
    )
    assert r.status_code == 200  # re-renderiza pedindo a escolha
    with app.app_context():
        for oid in ids["ofertas"]:
            assert db.session.get(TurmaCurso, oid).avaliacao_inicial is None


def test_avaliar_turma_sem_oferta_recusa(client, app):
    ids = _setup(app, ofertas=0)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/turma/{ids['turma']}/avaliacao?etapa=INICIAL")
    assert r.status_code == 302


# ---------------------------------------------------------------------------
# Passo 5 — fechamento por oferta
# ---------------------------------------------------------------------------

def test_fechar_lista_apenas_alunos_da_oferta_com_catalogo(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=1)
    _loga(client, ids, unidade_id=ids["un_a"])
    with app.app_context():
        opt = OpcaoProximaTurma(nome="Avançado", ativo=True)
        db.session.add(opt)
        db.session.commit()
        opt_id = opt.id

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['ofertas'][0]}")
    assert r.status_code == 200
    body = r.data.decode("utf-8")
    assert "Aluno Ana" in body
    assert "Aluno Beto" not in body
    assert f'data-oferta-id="{ids["ofertas"][0]}"' in body
    # Catálogo (Passo 5): a opção próxima usa o id do catálogo, não o nome.
    assert f'<option value="{opt_id}">Avançado</option>' in body


def test_fechar_frequencia_filtrada_pela_oferta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_a", oferta_idx=1)
    with app.app_context():
        # 2 presenças na oferta A, 2 faltas na oferta B.
        for i, oid in enumerate(ids["ofertas"]):
            for d in (1, 2):
                db.session.add(Frequencia(
                    aluno_id=ids["aluno_a"], turma_id=ids["turma"],
                    turma_curso_id=oid, data=date(2026, 3, d + i),
                    conceito="A" if oid == ids["ofertas"][0] else "F",
                    unidade_id=ids["un_a"],
                ))
        db.session.commit()
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['ofertas'][0]}")
    presencas = re.findall(r'text-success">\s*([\d.]+)%', r.data.decode("utf-8"))
    assert presencas == ["100.0"]

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['ofertas'][1]}")
    presencas = re.findall(r'text-success">\s*([\d.]+)%', r.data.decode("utf-8"))
    assert presencas == ["0.0"]


def test_fechar_salvar_grava_na_oferta_correta(client, app):
    ids = _setup(app, ofertas=2)
    _enturma(app, ids, "aluno_a", oferta_idx=0)
    _enturma(app, ids, "aluno_b", oferta_idx=1)
    _loga(client, ids, unidade_id=ids["un_a"])
    with app.app_context():
        opt = OpcaoProximaTurma(nome="Avançado", ativo=True)
        db.session.add(opt)
        db.session.commit()
        opt_id = opt.id

    r = client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={
            "oferta_id": ids["ofertas"][0],
            "dados": [
                {"aluno_id": ids["aluno_a"], "situacao": "APROVADO",
                 "proxima_turma_id": str(opt_id)},
                # aluno_b é matriculado só na OUTRA oferta → ignorado
                {"aluno_id": ids["aluno_b"], "situacao": "EVADIDO",
                 "proxima_turma_id": None},
            ],
        },
    )
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    with app.app_context():
        c = ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ofertas"][0], etapa=EtapaConselho.FINAL
        ).one()
        assert c.aluno_id == ids["aluno_a"]
        assert c.situacao_final == "Aprovado"  # normalizado para o CHECK
        assert c.proxima_turma_id == opt_id
        assert c.concluido is True
        assert ConselhoClasse.query.filter_by(
            aluno_id=ids["aluno_b"]
        ).count() == 0


def test_fechar_salvar_situacao_invalida_recusa_tudo(client, app):
    ids = _setup(app, ofertas=1)
    _enturma(app, ids, "aluno_a")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={
            "oferta_id": ids["ofertas"][0],
            "dados": [
                {"aluno_id": ids["aluno_a"], "situacao": "EMPREGADO",
                 "proxima_turma_id": None},
            ],
        },
    )
    assert r.status_code == 200
    assert r.get_json()["success"] is False
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_fechar_salvar_sem_oferta_valida_recusa(client, app):
    ids = _setup(app, ofertas="1+1i")
    _enturma(app, ids, "aluno_a")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={
            "oferta_id": ids["oferta_inativa"],
            "dados": [
                {"aluno_id": ids["aluno_a"], "situacao": "APROVADO",
                 "proxima_turma_id": None},
            ],
        },
    )
    assert r.get_json()["success"] is False
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


# ---------------------------------------------------------------------------
# Passo 6 — alternar_conselho por oferta (D5.5: sem ponte para a turma)
# ---------------------------------------------------------------------------

def _turma_de_unidade_b(app, ids):
    with app.app_context():
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add(un_b)
        db.session.flush()
        turma_b = Turma(
            nome="Turma B", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            unidade_id=un_b.id, ativo=True,
        )
        db.session.add(turma_b)
        db.session.commit()
        return turma_b.id, un_b.id


def test_alternar_1_oferta_muda_so_a_oferta(client, app):
    ids = _setup(app, ofertas=1)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/turma/alternar-conselho/{ids['turma']}")
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is True
        # D5.5: a turma não guarda o encerramento — a coluna não existe mais.
        assert not hasattr(db.session.get(Turma, ids["turma"]), "conselho_concluido")

    # Segundo clique: volta a oferta a pendente.
    client.post(f"/turma/alternar-conselho/{ids['turma']}")
    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is False


def test_alternar_2_ofertas_muda_uma_por_clique(client, app):
    ids = _setup(app, ofertas=2)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/alternar-conselho/{ids['turma']}",
        data={"turma_curso_id": str(ids["ofertas"][0])},
    )
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][0]).conselho_concluido is True
        assert db.session.get(TurmaCurso, ids["ofertas"][1]).conselho_concluido is False

    client.post(
        f"/turma/alternar-conselho/{ids['turma']}",
        data={"turma_curso_id": str(ids["ofertas"][1])},
    )
    with app.app_context():
        assert db.session.get(TurmaCurso, ids["ofertas"][1]).conselho_concluido is True


def test_alternar_sem_oferta_recusa(client, app):
    ids = _setup(app, ofertas=0)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/turma/alternar-conselho/{ids['turma']}")
    assert r.status_code == 302
    with app.app_context():
        assert TurmaCurso.query.count() == 0


def test_alternar_2_ofertas_sem_escolha_recusa(client, app):
    ids = _setup(app, ofertas=2)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/turma/alternar-conselho/{ids['turma']}")
    assert r.status_code == 302
    with app.app_context():
        for oid in ids["ofertas"]:
            assert db.session.get(TurmaCurso, oid).conselho_concluido is False


# ---------------------------------------------------------------------------
# Isolamento por unidade (B3/B4) — todos os perfis, inclusive admin
# ---------------------------------------------------------------------------

def test_isolamento_lancamento_outra_unidade_403(client, app):
    ids = _setup(app, ofertas=1)
    turma_b, _ = _turma_de_unidade_b(app, ids)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.get(f"/conselho/lancamento?turma={turma_b}&etapa=INICIAL")
    assert r.status_code == 403


def test_isolamento_admin_sem_unidade_403(client, app):
    ids = _setup(app, ofertas=1)
    _loga(client, ids)  # Visão Global

    r = client.get(f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL")
    assert r.status_code == 403

    r = client.post(f"/turma/alternar-conselho/{ids['turma']}")
    assert r.status_code == 403

    r = client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={"oferta_id": ids["ofertas"][0], "dados": []},
    )
    assert r.status_code == 403

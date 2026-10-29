# ruff: noqa: F811
"""Conselho de classe lançado pelo PROFESSOR (consenso de 29/10/2026).

Regras cobertas:
    - Sidebar: professor vê apenas `Conselho > Painel de Turmas`; os itens
      de gestão (Data-Informações, Configurar Perguntas) e os de saída
      (Situação Final do Aluno, Encerrar conselho) não aparecem.
    - Escopo por OFERTA (`turma_curso.professor_id`), sem herdar o professor
      da turma — a mesma regra da pauta/I1 (PARTE B/G1). O professor da
      turma que não está na oferta não vê nem abre o conselho dela; o da
      oferta vê e abre mesmo sem ser o professor da turma.
    - Oferta alheia pedida explicitamente = 403; turma sem oferta do
      professor = 403; tudo sem gravar nada.
    - Oferta encerrada (`TurmaCurso.conselho_concluido`) é somente leitura
      para o professor: o GET não cria `ConselhoClasse` e o POST não grava.
    - Situação final (fechamento) continua fora do professor: 403 no GET e
      no POST JSON; admin segue com acesso.

Um usuário por teste (T1 §5.6): cada teste loga uma única vez via
`login_as` (que também limpa o cache do Flask-Login em `g`).
"""

from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _usuario(nome, role, unidade_id):
    user = User(
        name=nome,
        email=f"{nome.lower().replace(' ', '.')}@example.com",
        role=role,
        first_login=False,
        unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    db.session.add(user)
    return user


def _setup(app):
    """Duas turmas com o professor da TURMA e o da OFERTA cruzados.

    - turma X: professora da turma = P2; oferta `ox` é do P1.
    - turma Y: professor da turma = P1; oferta `oy` é do P2.

    Assim a regra "professor da oferta, sem herança" é observável nos dois
    sentidos: P1 abre X (não é professor da turma) e não abre Y (é professor
    da turma, mas a oferta é da P2).
    """
    with app.app_context():
        unidade = Unidade(nome="Unidade CP", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        p1 = _usuario("Professor Um", "professor", unidade.id)
        p2 = _usuario("Professor Dois", "professor", unidade.id)
        admin = _usuario("Admin CP", "admin", unidade.id)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo CP", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma_x = Turma(
            nome="Turma X", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=p2.id,
        )
        turma_y = Turma(
            nome="Turma Y", turno="Tarde", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True, professor_id=p1.id,
        )
        db.session.add_all([turma_x, turma_y])
        db.session.flush()

        curso_x = Curso(nome="Curso X", unidade_id=unidade.id, ativo=True)
        curso_y = Curso(nome="Curso Y", unidade_id=unidade.id, ativo=True)
        db.session.add_all([curso_x, curso_y])
        db.session.flush()

        ox = nova_oferta(
            turma_x.id, curso_x.id, unidade.id, programa="Programa X",
            principal=True, professor_id=p1.id,
        )
        oy = nova_oferta(
            turma_y.id, curso_y.id, unidade.id, programa="Programa Y",
            principal=True, professor_id=p2.id,
        )

        aluno_x = Aluno(nome="Aluno do X", unidade_id=unidade.id, ativo=True)
        aluno_y = Aluno(nome="Aluno do Y", unidade_id=unidade.id, ativo=True)
        db.session.add_all([aluno_x, aluno_y])
        db.session.flush()
        nova_inscricao(aluno_x.id, turma_x.id, ox.id)
        nova_inscricao(aluno_y.id, turma_y.id, oy.id)

        p_aluno = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como participa das aulas?", opcoes="", ativo=True,
        )
        p_turma = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="TURMA",
            texto="Como a turma evoluiu?", opcoes="", ativo=True,
        )
        db.session.add_all([p_aluno, p_turma])
        db.session.commit()

        return {
            "un": unidade.id,
            "p1": p1.id,
            "p2": p2.id,
            "admin": admin.id,
            "turma_x": turma_x.id,
            "turma_y": turma_y.id,
            "ox": ox.id,
            "oy": oy.id,
            "aluno_x": aluno_x.id,
            "aluno_y": aluno_y.id,
            "p_aluno": p_aluno.id,
            "p_turma": p_turma.id,
        }


def _corpo(response):
    return response.get_data(as_text=True)


# ---------------------------------------------------------------------------
# Acesso e navegação
# ---------------------------------------------------------------------------

def test_sidebar_professor_ve_painel_e_nao_ve_itens_restritos(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    corpo = _corpo(client.get("/conselho"))
    assert "Painel de Turmas" in corpo
    assert "Lançar Percurso" in corpo
    assert "Data-Informações" not in corpo
    assert "Configurar Perguntas" not in corpo
    assert "Gerenciar Perguntas" not in corpo
    assert "Situação Final do Aluno" not in corpo
    assert "Encerrar conselho da oferta" not in corpo


def test_painel_professor_lista_somente_as_ofertas_dele(client, app):
    """P1 não é professor da turma X, mas é o professor da oferta dela."""
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    corpo = _corpo(client.get("/conselho"))
    assert "Curso X" in corpo
    assert "Curso Y" not in corpo
    assert "Professor Um" in corpo  # professor da OFERTA no cartão


def test_painel_nao_herda_professor_da_turma(client, app):
    """P2 é professor da turma X, mas a oferta dela é da P1."""
    ids = _setup(app)
    login_as(client, ids["p2"], ids["un"])

    corpo = _corpo(client.get("/conselho"))
    assert "Curso X" not in corpo
    assert "Curso Y" in corpo
    assert "Nenhuma oferta ativa" not in corpo


def test_painel_admin_ve_tudo_e_mantem_os_botoes_de_gestao(client, app):
    ids = _setup(app)
    login_as(client, ids["admin"], ids["un"])

    corpo = _corpo(client.get("/conselho"))
    assert "Curso X" in corpo
    assert "Curso Y" in corpo
    assert "Situação Final do Aluno" in corpo
    assert "Encerrar conselho da oferta" in corpo
    assert "Configurar Perguntas" in corpo


# ---------------------------------------------------------------------------
# Lançamento individual (perguntas por aluno)
# ---------------------------------------------------------------------------

def test_lancamento_abre_a_oferta_do_professor(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    r = client.get(
        f"/conselho/lancamento?turma={ids['turma_x']}&etapa=INICIAL"
        f"&oferta_sel={ids['ox']}"
    )
    assert r.status_code == 200
    corpo = _corpo(r)
    assert "Aluno do X" in corpo
    assert "Como participa das aulas?" in corpo
    with app.app_context():
        assert ConselhoClasse.query.filter_by(
            turma_curso_id=ids["ox"]
        ).count() == 1


def test_lancamento_recusa_oferta_de_outro_professor(client, app):
    ids = _setup(app)
    login_as(client, ids["p2"], ids["un"])

    r = client.get(
        f"/conselho/lancamento?turma={ids['turma_x']}&etapa=INICIAL"
        f"&oferta_sel={ids['ox']}"
    )
    assert r.status_code == 403
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_lancamento_recusa_turma_sem_oferta_do_professor(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    # P1 é professor da turma Y, mas a oferta dela é da P2.
    assert client.get(
        f"/conselho/lancamento?turma={ids['turma_y']}&etapa=INICIAL"
    ).status_code == 403
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_salvar_grava_resposta_na_oferta_do_professor(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma_x"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ox"]),
        f"resp_{ids['aluno_x']}_{ids['p_aluno']}": "Participa bem",
    })
    assert r.status_code == 302
    with app.app_context():
        respostas = ConselhoResposta.query.all()
        assert len(respostas) == 1
        assert respostas[0].aluno_id == ids["aluno_x"]
        assert respostas[0].resposta == "Participa bem"
        conselho = db.session.get(ConselhoClasse, respostas[0].conselho_id)
        assert conselho.turma_curso_id == ids["ox"]


def test_salvar_recusa_oferta_de_outro_professor_sem_gravar(client, app):
    ids = _setup(app)
    login_as(client, ids["p2"], ids["un"])

    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma_x"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ox"]),
        f"resp_{ids['aluno_x']}_{ids['p_aluno']}": "Invasão",
    })
    assert r.status_code == 403
    with app.app_context():
        assert ConselhoResposta.query.count() == 0
        assert ConselhoClasse.query.count() == 0


# ---------------------------------------------------------------------------
# Oferta encerrada é somente leitura para o professor
# ---------------------------------------------------------------------------

def _encerrar(app, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        oferta.conselho_concluido = True
        db.session.commit()


def test_oferta_encerrada_bloqueia_o_get_sem_criar_conselhos(client, app):
    ids = _setup(app)
    _encerrar(app, ids["ox"])
    login_as(client, ids["p1"], ids["un"])

    r = client.get(
        f"/conselho/lancamento?turma={ids['turma_x']}&etapa=INICIAL"
        f"&oferta_sel={ids['ox']}"
    )
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_oferta_encerrada_bloqueia_o_post_sem_gravar(client, app):
    ids = _setup(app)
    _encerrar(app, ids["ox"])
    login_as(client, ids["p1"], ids["un"])

    r = client.post("/conselho/salvar", data={
        "turma_id": str(ids["turma_x"]),
        "etapa": "INICIAL",
        "turma_curso_id": str(ids["ox"]),
        f"resp_{ids['aluno_x']}_{ids['p_aluno']}": "Depois do encerramento",
    })
    assert r.status_code == 302
    with app.app_context():
        assert ConselhoResposta.query.count() == 0


# ---------------------------------------------------------------------------
# Situação final (fechamento) fora do professor
# ---------------------------------------------------------------------------

def test_fechamento_recusa_professor_no_get_e_no_post(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    assert client.get(
        f"/conselho/fechamento/{ids['turma_x']}?oferta_sel={ids['ox']}"
    ).status_code == 403

    r = client.post(
        f"/conselho/fechamento/{ids['turma_x']}/salvar",
        json={"oferta_id": ids["ox"], "dados": []},
    )
    assert r.status_code == 403
    assert r.get_json()["success"] is False


def test_fechamento_continua_disponivel_para_admin(client, app):
    ids = _setup(app)
    login_as(client, ids["admin"], ids["un"])

    r = client.get(
        f"/conselho/fechamento/{ids['turma_x']}?oferta_sel={ids['ox']}"
    )
    assert r.status_code == 200
    assert "Aluno do X" in _corpo(r)


# ---------------------------------------------------------------------------
# Avaliação coletiva da oferta (perguntas tipo TURMA)
# ---------------------------------------------------------------------------

def test_avaliacao_da_oferta_abre_e_grava_para_o_professor(client, app):
    ids = _setup(app)
    login_as(client, ids["p1"], ids["un"])

    r = client.get(
        f"/turma/{ids['turma_x']}/avaliacao?etapa=INICIAL"
        f"&oferta_sel={ids['ox']}"
    )
    assert r.status_code == 200
    assert "Como a turma evoluiu?" in _corpo(r)
    assert "Como participa das aulas?" not in _corpo(r)
    # O "Voltar ao Painel" usa a rota canônica (main.painel), que monta o
    # contexto completo do painel; a legada /professor/painel sai vazia.
    assert 'href="/painel"' in _corpo(r)

    r = client.post(
        f"/turma/{ids['turma_x']}/avaliacao?etapa=INICIAL",
        data={
            "turma_curso_id": str(ids["ox"]),
            f"resp_turma_{ids['p_turma']}": "Turma evoluiu bem",
        },
    )
    assert r.status_code == 302
    assert r.headers["Location"].endswith("/painel")
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["ox"])
        assert "Turma evoluiu bem" in (oferta.avaliacao_inicial or "")


def test_avaliacao_recusa_oferta_de_outro_e_turma_sem_oferta(client, app):
    ids = _setup(app)
    login_as(client, ids["p2"], ids["un"])

    assert client.get(
        f"/turma/{ids['turma_x']}/avaliacao?etapa=INICIAL"
        f"&oferta_sel={ids['ox']}"
    ).status_code == 403

    login_as(client, ids["p1"], ids["un"])
    assert client.get(
        f"/turma/{ids['turma_y']}/avaliacao?etapa=INICIAL"
    ).status_code == 403

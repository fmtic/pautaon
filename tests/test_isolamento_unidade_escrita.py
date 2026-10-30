"""ETAPA B4 — isolamento de unidade em rotas de escrita (auditoria B3 §4, itens 1-12).

Regra do responsável: o isolamento por unidade vale para TODOS os perfis,
inclusive ADMIN e GERENCIA; a Visão Global é somente leitura.

Um usuário por teste (T1 §5.6): cada teste cria o próprio `test_client()` e
fixa a sessão uma única vez; nenhum teste troca de usuário no meio.
"""

from _helpers import login_as

from datetime import date

import pytest

from app.database import db
from app.models import (
    CentroCusto,
    Curso,
    DiaBloqueado,
    Nivel,
    PeriodoLetivo,
    TemaAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from config import Config

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture
def app(app_com_servidor):
    """Reaproveita a variante do conftest (corpo idêntico, sem duplicar)."""
    return app_com_servidor


def _setup(app, role="admin"):
    """Semeia duas unidades com um recurso equivalente em cada lado e um
    usuário do perfil pedido. Retorna os ids úteis."""
    with app.app_context():
        un_a = Unidade(nome="Unidade A", ativo=True)
        un_b = Unidade(nome="Unidade B", ativo=True)
        db.session.add_all([un_a, un_b])
        db.session.flush()

        usuario = User(
            name=f"Usuario {role} B4",
            email=f"{role}.b4@example.com",
            role=role,
            first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add(usuario)

        curso_a = Curso(nome="Curso A", unidade_id=un_a.id, ativo=True)
        curso_b = Curso(nome="Curso B", unidade_id=un_b.id, ativo=True)
        nivel_a = Nivel(nome="Nivel A", unidade_id=un_a.id, ativo=True)
        nivel_b = Nivel(nome="Nivel B", unidade_id=un_b.id, ativo=True)
        periodo_a = PeriodoLetivo(
            nome="Periodo A", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_a.id, ativo=True,
        )
        periodo_b = PeriodoLetivo(
            nome="Periodo B", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_b.id, ativo=True,
        )
        centro_a = CentroCusto(nome="Centro A", unidade_id=un_a.id, ativo=True)
        centro_b = CentroCusto(nome="Centro B", unidade_id=un_b.id, ativo=True)
        db.session.add_all(
            [curso_a, curso_b, nivel_a, nivel_b, periodo_a, periodo_b,
             centro_a, centro_b]
        )
        db.session.flush()

        tema_a = TemaAula(curso_id=curso_a.id, unidade_id=un_a.id,
                          titulo="Tema A", ordem=1, ativo=True)
        tema_b = TemaAula(curso_id=curso_b.id, unidade_id=un_b.id,
                          titulo="Tema B", ordem=1, ativo=True)
        dia_a = DiaBloqueado(data=date(2026, 2, 5), tipo="FERIADO",
                             descricao="Feriado A", periodo_letivo_id=periodo_a.id,
                             unidade_id=un_a.id)
        dia_b = DiaBloqueado(data=date(2026, 2, 6), tipo="FERIADO",
                             descricao="Feriado B", periodo_letivo_id=periodo_b.id,
                             unidade_id=un_b.id)
        turma_a = Turma(
            nome="Turma A", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            periodo_letivo_id=periodo_a.id, unidade_id=un_a.id,
            ativo=True,
        )
        turma_b = Turma(
            nome="Turma B", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            periodo_letivo_id=periodo_b.id, unidade_id=un_b.id,
            ativo=True,
        )
        db.session.add_all([tema_a, tema_b, dia_a, dia_b, turma_a, turma_b])
        db.session.commit()

        return {
            "user_id": usuario.id,
            "un_a": un_a.id, "un_b": un_b.id,
            "curso_a": curso_a.id, "curso_b": curso_b.id,
            "tema_a": tema_a.id, "tema_b": tema_b.id,
            "nivel_a": nivel_a.id, "nivel_b": nivel_b.id,
            "periodo_a": periodo_a.id, "periodo_b": periodo_b.id,
            "centro_a": centro_a.id, "centro_b": centro_b.id,
            "dia_a": dia_a.id, "dia_b": dia_b.id,
            "turma_a": turma_a.id, "turma_b": turma_b.id,
        }


def _loga(client, ids, unidade_id=None):
    """Fixa a sessão do cliente em uma única request de setup. Admin/gerência
    usam a unidade da sessão (get_unidade_id); sem `unidade_id` é Visão Global."""
    login_as(client, str(ids["user_id"]), unidade_id)
def _form_turma(ids, periodo_id, nome="Turma A editada"):
    return {
        "turma": nome,
        "turno": "Manhã",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "hora_inicio": "",
        "hora_fim": "",
        "professor_id": "",
        "dias_semana": "Segunda",
        "centro_custo": "",
        "curso_id": "",
        "periodo_letivo_id": str(periodo_id),
        "limpar_lancamentos": "0",
    }


# ---------------------------------------------------------------------------
# Família curso (T4: gerência na rota de editar curso)
# ---------------------------------------------------------------------------

def test_gerencia_na_unidade_a_nao_edita_curso_da_unidade_b(client, app):
    ids = _setup(app, role="gerencia")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/cursos/{ids['curso_b']}/editar", json={"nome": "Invasão"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Curso, ids["curso_b"]).nome == "Curso B"


def test_gerencia_sem_unidade_nao_edita_curso(client, app):
    ids = _setup(app, role="gerencia")
    _loga(client, ids)  # Visão Global

    r = client.post(
        f"/cursos/{ids['curso_a']}/editar", json={"nome": "Invasão"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Curso, ids["curso_a"]).nome == "Curso A"


def test_gerencia_edita_curso_da_propria_unidade(client, app):
    ids = _setup(app, role="gerencia")
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/cursos/{ids['curso_a']}/editar", json={"nome": "Curso A ok"}
    )
    assert r.status_code == 200
    with app.app_context():
        assert db.session.get(Curso, ids["curso_a"]).nome == "Curso A ok"


# ---------------------------------------------------------------------------
# Família tema (itens 1-3)
# ---------------------------------------------------------------------------

def test_admin_nao_cria_tema_em_curso_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/planejamento", data={"curso_id": str(ids["curso_b"]),
                               "titulo": "Tema invasor"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert TemaAula.query.filter_by(titulo="Tema invasor").first() is None


def test_admin_sem_unidade_nao_cria_tema(client, app):
    ids = _setup(app)
    _loga(client, ids)  # Visão Global

    r = client.post(
        "/planejamento", data={"curso_id": str(ids["curso_a"]),
                               "titulo": "Tema sem unidade"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert TemaAula.query.filter_by(titulo="Tema sem unidade").first() is None


def test_admin_cria_tema_no_curso_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/planejamento", data={"curso_id": str(ids["curso_a"]),
                               "titulo": "Tema permitido"}
    )
    assert r.status_code == 302
    with app.app_context():
        tema = TemaAula.query.filter_by(titulo="Tema permitido").first()
        assert tema is not None
        assert tema.unidade_id == ids["un_a"]


def test_admin_nao_edita_tema_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/tema/editar/{ids['tema_b']}", data={"titulo": "Trocado"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(TemaAula, ids["tema_b"]).titulo == "Tema B"


def test_admin_sem_unidade_nao_edita_tema(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        f"/planejamento/tema/editar/{ids['tema_a']}", data={"titulo": "Trocado"}
    )
    assert r.status_code == 403


def test_admin_edita_e_inativa_tema_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/tema/editar/{ids['tema_a']}", data={"titulo": "Tema A ok"}
    )
    assert r.status_code == 302
    r = client.post(f"/planejamento/tema/inativar/{ids['tema_a']}")
    assert r.status_code == 302
    with app.app_context():
        tema = db.session.get(TemaAula, ids["tema_a"])
        assert tema.titulo == "Tema A ok"
        assert tema.ativo is False


def test_admin_nao_inativa_tema_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/planejamento/tema/inativar/{ids['tema_b']}")
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(TemaAula, ids["tema_b"]).ativo is True


# ---------------------------------------------------------------------------
# Família nível (itens 4-5)
# ---------------------------------------------------------------------------

def test_admin_nao_edita_nivel_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/nivel/editar/{ids['nivel_b']}",
        data={"nome_nivel": "Nivel B trocado"},
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Nivel, ids["nivel_b"]).nome == "Nivel B"


def test_admin_sem_unidade_nao_edita_nivel(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        f"/planejamento/nivel/editar/{ids['nivel_a']}",
        data={"nome_nivel": "X"},
    )
    assert r.status_code == 403


def test_admin_edita_e_inativa_nivel_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/nivel/editar/{ids['nivel_a']}",
        data={"nome_nivel": "Nivel A ok"},
    )
    assert r.status_code == 302
    r = client.post(f"/planejamento/nivel/inativar/{ids['nivel_a']}")
    assert r.status_code == 302
    with app.app_context():
        nivel = db.session.get(Nivel, ids["nivel_a"])
        assert nivel.nome == "Nivel A ok"
        assert nivel.ativo is False


def test_admin_nao_inativa_nivel_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/planejamento/nivel/inativar/{ids['nivel_b']}")
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Nivel, ids["nivel_b"]).ativo is True


# ---------------------------------------------------------------------------
# Família período letivo e calendário (itens 7-9)
# ---------------------------------------------------------------------------

def test_admin_nao_edita_periodo_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/periodo-letivo/editar/{ids['periodo_b']}",
        data={
            "nome": "Periodo B trocado",
            "data_inicio": DATA_INI.isoformat(),
            "data_fim": DATA_FIM.isoformat(),
            "estimativa_alunos": "10",
        },
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(PeriodoLetivo, ids["periodo_b"]).nome != "Periodo B trocado"


def test_admin_sem_unidade_nao_edita_periodo(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        f"/periodo-letivo/editar/{ids['periodo_a']}",
        data={
            "nome": "X",
            "data_inicio": DATA_INI.isoformat(),
            "data_fim": DATA_FIM.isoformat(),
            "estimativa_alunos": "0",
        },
    )
    assert r.status_code == 403


def test_admin_edita_periodo_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/periodo-letivo/editar/{ids['periodo_a']}",
        data={
            "nome": "Periodo A ok",
            "data_inicio": DATA_INI.isoformat(),
            "data_fim": DATA_FIM.isoformat(),
            "estimativa_alunos": "12",
        },
    )
    assert r.status_code == 302
    with app.app_context():
        periodo = db.session.get(PeriodoLetivo, ids["periodo_a"])
        assert periodo.nome == "Periodo A ok"
        assert periodo.estimativa_alunos == 12


def test_admin_nao_salva_calendario_de_periodo_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/planejamento/calendario/salvar",
        json={"periodo_id": ids["periodo_b"], "dias": []},
    )
    assert r.status_code == 403
    assert r.get_json()["success"] is False
    with app.app_context():
        # O DELETE em lote não pode ter rodado: o dia B continua lá.
        assert db.session.get(DiaBloqueado, ids["dia_b"]) is not None


def test_admin_sem_unidade_nao_salva_calendario(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        "/planejamento/calendario/salvar",
        json={"periodo_id": ids["periodo_a"], "dias": []},
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(DiaBloqueado, ids["dia_a"]) is not None


def test_admin_salva_calendario_do_periodo_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/planejamento/calendario/salvar",
        json={
            "periodo_id": ids["periodo_a"],
            "dias": [{"data": "2026-03-10", "tipo": "FERIADO",
                      "descricao": "Bloqueio novo"}],
        },
    )
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    with app.app_context():
        dias = DiaBloqueado.query.filter_by(periodo_letivo_id=ids["periodo_a"]).all()
        assert len(dias) == 1
        assert dias[0].descricao == "Bloqueio novo"
        assert dias[0].unidade_id == ids["un_a"]


def test_admin_nao_remove_dia_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/planejamento/calendario/remover/{ids['dia_b']}")
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(DiaBloqueado, ids["dia_b"]) is not None


def test_admin_sem_unidade_nao_remove_dia(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(f"/planejamento/calendario/remover/{ids['dia_a']}")
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(DiaBloqueado, ids["dia_a"]) is not None


def test_admin_remove_dia_do_proprio_periodo(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/planejamento/calendario/remover/{ids['dia_a']}")
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    with app.app_context():
        db.session.remove()
        db.session.expire_all()
        assert db.session.get(DiaBloqueado, ids["dia_a"]) is None


# ---------------------------------------------------------------------------
# Família centro de custo (item 10)
# ---------------------------------------------------------------------------

def test_admin_nao_edita_centro_de_custo_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/centros-custo/{ids['centro_b']}/editar", json={"nome": "Centro B trocado"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(CentroCusto, ids["centro_b"]).nome == "Centro B"


def test_admin_sem_unidade_nao_edita_centro_de_custo(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        f"/centros-custo/{ids['centro_a']}/editar", json={"nome": "X"}
    )
    assert r.status_code == 403


def test_admin_edita_centro_de_custo_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/centros-custo/{ids['centro_a']}/editar", json={"nome": "Centro A ok"}
    )
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    with app.app_context():
        assert db.session.get(CentroCusto, ids["centro_a"]).nome == "Centro A ok"


# ---------------------------------------------------------------------------
# Família turma nova/editar (itens 11-12)
# ---------------------------------------------------------------------------

def test_admin_nao_cria_turma_com_periodo_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/turma/nova",
        data={
            "turma": "T invasora",
            "turno": "Manhã",
            "dias_semana": "Segunda",
            "periodo_letivo_id": str(ids["periodo_b"]),
        },
    )
    assert r.status_code == 302
    with app.app_context():
        assert Turma.query.filter_by(nome="T invasora").first() is None


def test_admin_sem_unidade_nao_cria_turma(client, app):
    ids = _setup(app)
    _loga(client, ids)  # Visão Global: POST recusa em vez de Turma unidade NULL

    r = client.post(
        "/turma/nova",
        data={
            "turma": "T sem unidade",
            "turno": "Manhã",
            "dias_semana": "Segunda",
            "periodo_letivo_id": str(ids["periodo_a"]),
        },
    )
    assert r.status_code == 403
    with app.app_context():
        assert Turma.query.filter_by(nome="T sem unidade").first() is None


def test_admin_cria_turma_com_periodo_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        "/turma/nova",
        data={
            "turma": "T criada ok",
            "turno": "Manhã",
            # H4: dia marcado exige par de horários (validação do parsing).
            "dias_semana": "Segunda",
            "hora_inicio": "08:00",
            "hora_fim": "11:00",
            "periodo_letivo_id": str(ids["periodo_a"]),
        },
    )
    assert r.status_code == 302
    with app.app_context():
        turma = Turma.query.filter_by(nome="T criada ok").first()
        assert turma is not None
        assert turma.unidade_id == ids["un_a"]


def test_admin_nao_edita_turma_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/editar/{ids['turma_b']}", data=_form_turma(ids, ids["periodo_b"])
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(Turma, ids["turma_b"]).nome == "Turma B"


def test_admin_sem_unidade_nao_edita_turma(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(
        f"/turma/editar/{ids['turma_a']}", data=_form_turma(ids, ids["periodo_a"])
    )
    assert r.status_code == 403


def test_admin_nao_move_turma_para_periodo_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/editar/{ids['turma_a']}",
        data=_form_turma(ids, ids["periodo_b"], nome="Turma A movida"),
    )
    assert r.status_code == 302
    # T1 §5.6 (harness): com o AppContext do fixture ainda aberto, a rota usa
    # a MESMA sessão/conexão (StaticPool + :memory:) e o autoflush disparado
    # pelo guard antes do redirect fica pendente. O remove() tem de rodar na
    # sessão ativa do fixture (não num contexto aninhado novo) para desfazer
    # o que não foi commitado e expor o estado real do banco.
    db.session.remove()
    db.session.expire_all()
    turma = db.session.get(Turma, ids["turma_a"])
    assert turma.periodo_letivo_id == ids["periodo_a"]
    assert turma.nome == "Turma A"


def test_admin_edita_turma_da_propria_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/turma/editar/{ids['turma_a']}",
        data=_form_turma(ids, ids["periodo_a"], nome="Turma A ok"),
    )
    assert r.status_code == 302
    with app.app_context():
        db.session.remove()
        db.session.expire_all()
        assert db.session.get(Turma, ids["turma_a"]).nome == "Turma A ok"


# ---------------------------------------------------------------------------
# alternar-conselho (item 6)
# ---------------------------------------------------------------------------

def test_admin_nao_alterna_conselho_de_turma_de_outra_unidade(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(f"/turma/alternar-conselho/{ids['turma_b']}")
    assert r.status_code == 403
    with app.app_context():
        assert TurmaCurso.query.filter_by(
            turma_id=ids["turma_b"], conselho_concluido=True
        ).count() == 0


def test_admin_sem_unidade_nao_alterna_conselho(client, app):
    ids = _setup(app)
    _loga(client, ids)

    r = client.post(f"/turma/alternar-conselho/{ids['turma_a']}")
    assert r.status_code == 403
    with app.app_context():
        assert TurmaCurso.query.filter_by(
            turma_id=ids["turma_a"], conselho_concluido=True
        ).count() == 0


def test_admin_alterna_conselho_da_turma_correta(client, app):
    ids = _setup(app)
    _loga(client, ids, unidade_id=ids["un_a"])

    # ETAPA D5.2: o encerramento do conselho passou a ser da OFERTA e turma
    # sem oferta ativa é recusada. A finalidade B4 (isolamento) permanece a
    # mesma — só se dá à turma a oferta única que o fluxo novo exige.
    from _helpers import nova_oferta

    with app.app_context():
        oferta = nova_oferta(ids["turma_a"], ids["curso_a"], ids["un_a"])
        db.session.commit()
        oferta_id = oferta.id

    r = client.post(f"/turma/alternar-conselho/{ids['turma_a']}")
    assert r.status_code == 302
    with app.app_context():
        # D5.5: a flag vive SÓ na oferta — a turma não tem mais a coluna.
        assert db.session.get(TurmaCurso, oferta_id).conselho_concluido is True
        assert not hasattr(db.session.get(Turma, ids["turma_a"]), "conselho_concluido")


# ---------------------------------------------------------------------------
# ETAPA B6 — isolamento de escrita no planejamento (Passos 2a e 2b)
# ---------------------------------------------------------------------------

def test_admin_sem_unidade_nao_cria_nivel(client, app):
    """B6 (2a): criar nível exige unidade efetiva; Visão Global → 403.

    Antes, um ADMIN em Visão Global gravava um Nivel com unidade_id NULL;
    agora o `assert_unidade_context` recusa a escrita, como nos demais ramos.
    """
    ids = _setup(app)
    _loga(client, ids)  # Visão Global (sem unidade na sessão)

    r = client.post(
        "/planejamento",
        data={"tipo_post": "nivel", "nome_nivel": "Nivel global"},
    )
    assert r.status_code == 403
    with app.app_context():
        assert Nivel.query.filter_by(nome="Nivel global").first() is None


def test_admin_nao_edita_tema_de_curso_inativo_de_outra_unidade(client, app):
    """B6 (2b): o isolamento vem ANTES do cheque de curso inativo → 403 (não 302).

    Um tema de curso inativo de OUTRA unidade não pode revelar a existência
    do curso via flash+redirect (302); deve ser bloqueado por 403.
    """
    ids = _setup(app)
    with app.app_context():
        db.session.get(Curso, ids["curso_b"]).ativo = False
        db.session.commit()
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/tema/editar/{ids['tema_b']}", data={"titulo": "Trocado"}
    )
    assert r.status_code == 403
    with app.app_context():
        assert db.session.get(TemaAula, ids["tema_b"]).titulo == "Tema B"


def test_curso_inativo_da_propria_unidade_ainda_redireciona(client, app):
    """B6 (2b): mesmo curso inativo da própria unidade preserva o 302 (flash).

    Reordernar assert/curso.ativo não pode quebrar o bloqueio legítimo de
    edição de tema em curso inativo da MESMA unidade.
    """
    ids = _setup(app)
    with app.app_context():
        db.session.get(Curso, ids["curso_a"]).ativo = False
        db.session.commit()
    _loga(client, ids, unidade_id=ids["un_a"])

    r = client.post(
        f"/planejamento/tema/editar/{ids['tema_a']}", data={"titulo": "Trocado"}
    )
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(TemaAula, ids["tema_a"]).titulo == "Tema A"

"""Etapa T1 (passo 4) — Transferência de aluno entre ofertas.

Rota ``/aluno/transferir/<aluno_id>`` (app/registros/alunos.py) pós
c3d4e5f6a7b8: o vínculo do aluno é sempre uma oferta concreta
(``Inscricao.turma_curso_id`` NOT NULL), e a transferência encerra apenas a
inscrição da oferta de origem, criando nova inscrição ativa na oferta de
destino escolhida.

Regras do responsável pela transferência:
    - ``ofertas_destino`` = ofertas ativas de turmas ativas DISTINTAS da
      origem e da MESMA unidade do usuário (alunos.py L1021-1031).
    - POST exige ``turma_curso_id_destino`` + ``data_transferencia``
      (``%Y-%m-%d``) + ``observacoes``; recusas são flash + redirect (302),
      nunca 500.
    - Só admin/pedagógico/secretaria acessam; usuário de outra unidade é
      bloqueado por ``assert_unidade_context`` (403).

Cobertura:
    1. Destino com 1 oferta: tela GET lista a oferta; POST transferir com
       escolha explícita funciona.
    2. Destino com 2 ofertas: exige ``turma_curso_id_destino`` (sem ele é
       recusado; com ele grava na oferta apontada).
    3. Recusa de oferta de destino inativa.
    4. Recusa de oferta da própria turma de origem e de oferta pertencente a
       uma turma de outra unidade (não está em ``ofertas_destino``).
    5. Usuário de outra unidade → 403 (GET e POST); usuário da mesma unidade
       enxerga a tela com o destino listado.
    6. Efeitos: inscrição de origem fica inativa (motivo TRANSFERENCIA,
       data_desativacao = véspera) e a nova fica ativa na oferta escolhida;
       registro ``Transferencia`` criado; redirect para a turma de origem.

Nota de harness (por que cada teste usa um único usuário): o fixture mantém
um ``app_context`` aberto durante o teste e o Flask reutiliza esse AppContext
em cada request; como ``flask.g`` vive no AppContext, o ``_login_user``
cacheado pelo Flask-Login vaza para as requisições seguintes do mesmo teste,
fazendo o segundo cliente agir como o primeiro usuário. Em produção cada
request empurra seu próprio AppContext, então não é bug de código.
"""

from datetime import date, datetime, time

import pytest

from app import create_app, db
from app.models import Aluno, Curso, Inscricao, Transferencia, Turma, Unidade, User
from config import Config

from _helpers import login_as, nova_inscricao, nova_oferta

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)
DATA_TRANSF = date(2026, 6, 1)


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


# --- semente ------------------------------------------------------------------
def _turma(unidade_id, curso_id, professor_id, nome):
    turma = Turma(
        nome=nome, unidade_id=unidade_id, ativo=True, curso_id=curso_id,
        professor_id=professor_id, turno="Manhã",
        data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
    )
    db.session.add(turma)
    db.session.flush()
    return turma


def _oferta(turma, curso, unidade_id, **campos):
    """Oferta ativa da turma com programa (helper único da suíte)."""
    return nova_oferta(
        turma.id, curso.id, unidade_id,
        professor_id=campos.pop("professor_id", None),
        turno=campos.pop("turno", "Manhã"),
        data_inicio=campos.pop("data_inicio", DATA_INI),
        data_fim=campos.pop("data_fim", DATA_FIM),
        **campos,
    )


def _base(unidade_nome="U transf"):
    """Unidade + usuário pedagógico + 2 cursos + turma de origem com 1 oferta
    e 1 aluno inscrito ativo. Retorna ids e a oferta de origem."""
    unidade = Unidade(nome=unidade_nome, ativo=True)
    db.session.add(unidade)
    db.session.flush()
    resp = User(
        name=f"Coord {unidade_nome}", email=f"coord.{unidade_nome}@example.com",
        role="pedagogico", first_login=False, unidade_id=unidade.id,
    )
    prof = User(
        name=f"Prof {unidade_nome}", email=f"prof.{unidade_nome}@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
    cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
    cC = Curso(nome="Curso C", unidade_id=unidade.id, ativo=True)
    db.session.add_all([resp, prof, cA, cB, cC])
    db.session.flush()

    origem = _turma(unidade.id, cA.id, prof.id, "Turma Origem")
    of_origem = _oferta(origem, cA, unidade.id, professor_id=prof.id, principal=True)

    aluno = Aluno(nome="Aluno T", ativo=True, unidade_id=unidade.id)
    db.session.add(aluno)
    db.session.flush()
    nova_inscricao(aluno.id, origem.id, of_origem.id)

    return {
        "unidade": unidade.id, "resp": resp.id, "prof": prof.id,
        "cA": cA.id, "cB": cB.id, "cC": cC.id, "aluno": aluno.id,
        "origem": origem.id, "of_origem": of_origem.id,
    }


def _destino(i, n_ativas=1, n_inativas=0, nome="Turma Destino"):
    """Cria turma destino com ``n_ativas`` ofertas ativas e ``n_inativas``
    desativadas. O índice único ``uq_turma_curso`` não permite duas ofertas do
    MESMO curso na mesma turma, então os cursos alternam (cA, cB, ...).
    Retorna (turma_id, ativas, inativas)."""
    destino = _turma(i["unidade"], i["cA"], i["prof"], nome)
    cursos = [i["cA"], i["cB"], i["cC"]]
    ativas = [
        _oferta(destino, db.session.get(Curso, cursos[k % 3]), i["unidade"],
                professor_id=i["prof"]).id
        for k in range(n_ativas)
    ]
    inativas = [
        _oferta(destino, db.session.get(Curso, cursos[(n_ativas + k) % 3]),
                i["unidade"], professor_id=i["prof"], ativo=False).id
        for k in range(n_inativas)
    ]
    return destino.id, ativas, inativas


def _post(client, aluno_id, i, *, destino=None, data="2026-06-01", obs="Motivo X"):
    data_form = {
        "turma_origem_id": str(i["origem"]),
        "turma_curso_id": str(i["of_origem"]),
        "data_transferencia": data,
        "observacoes": obs,
    }
    if destino is not None:
        data_form["turma_curso_id_destino"] = str(destino)
    return client.post(f"/aluno/transferir/{aluno_id}", data=data_form)


def _ativas(aluno_id):
    return Inscricao.query.filter_by(aluno_id=aluno_id, ativo=True).all()


# --- 1) destino com 1 oferta ---------------------------------------------------
def test_destino_uma_oferta_tela_e_transferencia(app):
    with app.app_context():
        i = _base()
        _, ativas, _ = _destino(i, n_ativas=1)
        db.session.commit()
        aluno_id, of_dest = i["aluno"], ativas[0]

    client = _loga(app, i["resp"])
    r_get = client.get(
        f"/aluno/transferir/{aluno_id}",
        query_string={"turma_origem_id": i["origem"], "turma_curso_id": i["of_origem"]},
    )
    assert r_get.status_code == 200
    assert "Turma Destino" in r_get.get_data(as_text=True)

    r = _post(client, aluno_id, i, destino=of_dest)
    assert r.status_code == 302
    with app.app_context():
        novas = _ativas(aluno_id)
        assert len(novas) == 1
        assert novas[0].turma_curso_id == of_dest


# --- 2) destino com 2 ofertas: exige turma_curso_id_destino --------------------
def test_destino_duas_ofertas_exige_escolha(app):
    with app.app_context():
        i = _base()
        _, ativas, _ = _destino(i, n_ativas=2)
        db.session.commit()
        aluno_id, of2 = i["aluno"], ativas[1]

    client = _loga(app, i["resp"])
    # sem a oferta de destino: recusa com flash, nada muda
    r_sem = _post(client, aluno_id, i)
    assert r_sem.status_code == 302
    with app.app_context():
        assert _ativas(aluno_id)[0].turma_curso_id == i["of_origem"]

    # com escolha explícita: grava na oferta apontada
    r = _post(client, aluno_id, i, destino=of2)
    assert r.status_code == 302
    with app.app_context():
        novas = _ativas(aluno_id)
        assert len(novas) == 1
        assert novas[0].turma_curso_id == of2


# --- 3) recusa de oferta inativa -----------------------------------------------
def test_recusa_oferta_destino_inativa(app):
    with app.app_context():
        i = _base()
        _, ativas, inativas = _destino(i, n_ativas=1, n_inativas=1)
        db.session.commit()
        aluno_id, of_inativa = i["aluno"], inativas[0]

    client = _loga(app, i["resp"])
    r = _post(client, aluno_id, i, destino=of_inativa)
    assert r.status_code == 302
    with app.app_context():
        novas = _ativas(aluno_id)
        # origem segue ativa; nenhuma inscrição na oferta inativa
        assert len(novas) == 1
        assert novas[0].turma_curso_id == i["of_origem"]
        assert (
            Inscricao.query.filter_by(
                aluno_id=aluno_id, turma_curso_id=of_inativa
            ).first()
            is None
        )


# --- 4) recusa de oferta de outra turma (a própria origem) --------------------
def test_recusa_oferta_da_mesma_turma_origem(app):
    with app.app_context():
        i = _base()
        _destino(i, n_ativas=1)
        db.session.commit()
        aluno_id = i["aluno"]

    client = _loga(app, i["resp"])
    # apontar a oferta da própria turma de origem: não está em ofertas_destino
    r = _post(client, aluno_id, i, destino=i["of_origem"])
    assert r.status_code == 302
    with app.app_context():
        novas = _ativas(aluno_id)
        assert len(novas) == 1
        assert novas[0].turma_curso_id == i["of_origem"]
        assert novas[0].ativo is True


# --- 4b) recusa de oferta de turma de OUTRA unidade ---------------------------
def test_recusa_oferta_de_outra_unidade(app):
    with app.app_context():
        i = _base()
        _destino(i, n_ativas=1)
        estrangeira = _base(unidade_nome="U transf estranha")
        t_est, ativas_est, _ = _destino(estrangeira, n_ativas=1, nome="Turma Estranha")
        db.session.commit()
        aluno_id, of_estrangeira = i["aluno"], ativas_est[0]
        origem, of_origem = i["origem"], i["of_origem"]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/aluno/transferir/{aluno_id}",
        data={
            "turma_origem_id": str(origem),
            "turma_curso_id": str(of_origem),
            "turma_curso_id_destino": str(of_estrangeira),
            "data_transferencia": "2026-06-01",
            "observacoes": "Motivo X",
        },
    )
    assert r.status_code == 302
    with app.app_context():
        novas = _ativas(aluno_id)
        assert len(novas) == 1
        assert novas[0].turma_curso_id == of_origem
        assert (
            Inscricao.query.filter_by(
                aluno_id=aluno_id, turma_curso_id=of_estrangeira
            ).first()
            is None
        )


# --- 5) usuário de outra unidade → 403 -----------------------------------------
# Um único usuário por teste: ver nota de harness no docstring do módulo.
def test_usuario_de_outra_unidade_403(app):
    with app.app_context():
        i = _base()
        _destino(i, n_ativas=1)
        outra = Unidade(nome="U transf outra", ativo=True)
        db.session.add(outra)
        db.session.flush()
        intruso = User(
            name="Coord Intrusa", email="coord.intrusa@example.com",
            role="pedagogico", first_login=False, unidade_id=outra.id,
        )
        db.session.add(intruso)
        db.session.commit()
        aluno_id, intruso_id = i["aluno"], intruso.id
        origem, of_origem = i["origem"], i["of_origem"]

    client = _loga(app, intruso_id)
    r = client.get(
        f"/aluno/transferir/{aluno_id}",
        query_string={"turma_origem_id": origem, "turma_curso_id": of_origem},
    )
    assert r.status_code == 403
    # POST também é bloqueado antes de qualquer escrita
    r_post = client.post(
        f"/aluno/transferir/{aluno_id}",
        data={
            "turma_origem_id": str(origem),
            "turma_curso_id": str(of_origem),
            "data_transferencia": "2026-06-01",
            "observacoes": "Intrusa",
        },
    )
    assert r_post.status_code == 403
    with app.app_context():
        assert len(_ativas(aluno_id)) == 1


# --- 5b) usuário da própria unidade enxerga a tela com o destino --------------
def test_usuario_da_mesma_unidade_ve_tela(app):
    with app.app_context():
        i = _base()
        _, ativas, _ = _destino(i, n_ativas=1)
        db.session.commit()
        aluno_id, resp_id = i["aluno"], i["resp"]
        origem, of_origem = i["origem"], i["of_origem"]
        of_dest = ativas[0]

    client = _loga(app, resp_id)
    r = client.get(
        f"/aluno/transferir/{aluno_id}",
        query_string={"turma_origem_id": origem, "turma_curso_id": of_origem},
    )
    assert r.status_code == 200
    body = r.get_data(as_text=True)
    assert "Turma Destino" in body
    assert f'value="{of_dest}"' in body


# --- 6) efeitos: origem inativa + nova ativa na oferta escolhida ---------------
def test_efeitos_inativa_origem_cria_ativa_destino(app):
    with app.app_context():
        i = _base()
        destino_id, ativas, _ = _destino(i, n_ativas=1)
        db.session.commit()
        aluno_id, of_dest = i["aluno"], ativas[0]

    client = _loga(app, i["resp"])
    r = _post(client, aluno_id, i, destino=of_dest)
    assert r.status_code == 302

    with app.app_context():
        origem = Inscricao.query.filter_by(
            aluno_id=aluno_id, turma_curso_id=i["of_origem"]
        ).one()
        assert origem.ativo is False
        assert origem.motivo_desativacao == "TRANSFERENCIA"
        # data_desativacao = véspera da transferência (alunos.py L1094-1096)
        assert origem.data_desativacao == datetime.combine(
            date(2026, 5, 31), datetime.min.time()
        )

        nova = Inscricao.query.filter_by(
            aluno_id=aluno_id, turma_curso_id=of_dest, ativo=True
        ).one()
        assert nova.turma_id == destino_id
        assert nova.data_inicio == DATA_TRANSF

        registro = Transferencia.query.filter_by(aluno_id=aluno_id).one()
        assert registro.turma_origem_id == i["origem"]
        assert registro.turma_destino_id == destino_id
        assert registro.observacoes == "Motivo X"

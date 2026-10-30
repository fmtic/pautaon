"""Etapa M1 — Enturmação por curso (oferta).

Regras do responsável:
    - Aluno só é enturmado em curso (oferta). Turma sem oferta ativa não
      recebe alunos.
    - O mesmo aluno pode estar em duas ofertas da mesma turma (duas
      inscrições ativas, uma por oferta). Não pode estar duas vezes na
      mesma oferta.

Cobertura (roteiro do passo 6, pós c3d4e5f6a7b8):
    1 oferta grava a oferta sem escolha; 2 ofertas sem escolha recusa; com
    escolha grava; oferta de outra turma recusada; oferta desativada recusada;
    0 ofertas recusa; mesmo aluno nas duas ofertas permitido; duplicata na
    mesma oferta recusada (rota mostra flash, sem 500) e bloqueada pelo índice
    uix_inscricao_ativa_aluno_oferta; aluno enturmado aparece na pauta da
    oferta correta (_alunos_da_oferta); usuário de outra unidade recusado.

    Os testes de adoção/vínculo de inscrição NULL (Etapa M1.1) foram removidos:
    o NOT NULL de Inscricao.turma_curso_id extinguiu esse estado.
"""

from datetime import date, time

import pytest

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.services.turma_curso import _alunos_da_oferta
from config import Config
from _helpers import login_as, professor_semente

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
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


def _base(unidade_nome="U M1"):
    """Semeia unidade + pedagógico + 2 cursos + 2 professores. Retorna IDs."""
    unidade = Unidade(nome=unidade_nome, ativo=True)
    db.session.add(unidade)
    db.session.flush()
    resp = User(
        name="Coord M1", email=f"coord.{unidade_nome}@example.com",
        role="pedagogico", first_login=False, unidade_id=unidade.id,
    )
    p1 = User(
        name="Prof Um", email=f"p1.{unidade_nome}@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    p2 = User(
        name="Prof Dois", email=f"p2.{unidade_nome}@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    db.session.add_all([resp, p1, p2])
    cA = Curso(nome="Curso A", unidade_id=unidade.id, ativo=True)
    cB = Curso(nome="Curso B", unidade_id=unidade.id, ativo=True)
    cC = Curso(nome="Curso C", unidade_id=unidade.id, ativo=True)
    db.session.add_all([cA, cB, cC])
    db.session.flush()
    return {
        "unidade": unidade.id, "resp": resp.id,
        "p1": p1.id, "p2": p2.id, "cA": cA.id, "cB": cB.id, "cC": cC.id,
    }


def _turma(i, *, curso_id=None, ativo_ofertas=0, inativa_ofertas=0):
    """Cria uma turma e `ativo_ofertas` ofertas ativas (cA, cB, ...) +
    `inativa_ofertas` ofertas desativadas. Retorna ids (turma, ofertas)."""
    turma = Turma(
        nome="Turma M1", unidade_id=i["unidade"], ativo=True,
        curso_id=curso_id, professor_id=i["p1"], turno="Manhã",
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()

    cursos = [i["cA"], i["cB"], i["cC"]]
    ids_ativas = []
    for k in range(ativo_ofertas):
        o = TurmaCurso(
            turma_id=turma.id, curso_id=cursos[k % 3], unidade_id=i["unidade"],
            ativo=True, principal=(k == 0), professor_id=i["p1"],
            turno="Manhã",
            data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
        )
        db.session.add(o)
        db.session.flush()
        ids_ativas.append(o.id)

    ids_inativas = []
    for k in range(inativa_ofertas):
        o = TurmaCurso(
            turma_id=turma.id, curso_id=cursos[(ativo_ofertas + k) % 3],
            unidade_id=i["unidade"], ativo=False, principal=False,
            professor_id=i["p1"],
            data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
        )
        db.session.add(o)
        db.session.flush()
        ids_inativas.append(o.id)

    return {"turma": turma.id, "ativas": ids_ativas, "inativas": ids_inativas}


def _aluno(i, nome="Aluno X"):
    a = Aluno(nome=nome, ativo=True, unidade_id=i["unidade"])
    db.session.add(a)
    db.session.flush()
    return a.id


def _inscricoes_ativas(turma_id):
    return Inscricao.query.filter_by(turma_id=turma_id, ativo=True).all()


# --- 1 oferta: grava a oferta sem escolha na tela ----------------------------
def test_uma_oferta_grava_sem_escolha(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=i["cA"], ativo_ofertas=1)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, oferta_id = t["turma"], t["ativas"][0]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    assert r.status_code == 302
    with app.app_context():
        inscs = _inscricoes_ativas(turma_id)
        assert len(inscs) == 1
        assert inscs[0].turma_curso_id == oferta_id


# --- 0 ofertas: recusa e não grava -------------------------------------------
def test_zero_ofertas_recusa(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=0)
        aluno = _aluno(i)
        db.session.commit()
        turma_id = t["turma"]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    assert r.status_code == 302
    with app.app_context():
        assert _inscricoes_ativas(turma_id) == []


# --- 2 ofertas sem escolha: recusa -------------------------------------------
def test_duas_ofertas_sem_escolha_recusa(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=2)
        aluno = _aluno(i)
        db.session.commit()
        turma_id = t["turma"]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    assert r.status_code == 302
    with app.app_context():
        assert _inscricoes_ativas(turma_id) == []


# --- 2 ofertas com escolha: grava na oferta apontada -------------------------
def test_duas_ofertas_com_escolha_grava(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=2)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, seg = t["turma"], t["ativas"][1]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(seg)},
    )
    assert r.status_code == 302
    with app.app_context():
        inscs = _inscricoes_ativas(turma_id)
        assert len(inscs) == 1
        assert inscs[0].turma_curso_id == seg


# --- oferta de OUTRA turma: recusa -------------------------------------------
def test_oferta_de_outra_turma_recusada(app):
    with app.app_context():
        i = _base()
        t1 = _turma(i, curso_id=None, ativo_ofertas=2)
        # oferta de outra turma: cria manualmente uma oferta ligada a outra.
        outra = Turma(
            nome="Turma Outra", unidade_id=i["unidade"], ativo=True,
            curso_id=i["cA"], data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(outra)
        db.session.flush()
        oferta_outra = TurmaCurso(
            turma_id=outra.id, curso_id=i["cA"], unidade_id=i["unidade"],
            ativo=True, principal=True, programa="Teste",
            professor_id=professor_semente(i["unidade"]).id,
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(oferta_outra)
        db.session.flush()
        aluno = _aluno(i)
        db.session.commit()
        turma_id, of_outra = t1["turma"], oferta_outra.id

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(of_outra)},
    )
    assert r.status_code == 302
    with app.app_context():
        assert _inscricoes_ativas(turma_id) == []


# --- oferta DESATIVADA: recusa -----------------------------------------------
def test_oferta_desativada_recusada(app):
    with app.app_context():
        i = _base()
        # 2 ativas (para exigir escolha) + 1 desativada (a que vamos apontar).
        t = _turma(i, curso_id=None, ativo_ofertas=2, inativa_ofertas=1)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, of_inativa = t["turma"], t["inativas"][0]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(of_inativa)},
    )
    assert r.status_code == 302
    with app.app_context():
        assert _inscricoes_ativas(turma_id) == []


# --- mesmo aluno em DUAS ofertas da mesma turma: permitido -------------------
def test_mesmo_aluno_em_duas_ofertas_permitido(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=2)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, o1, o2 = t["turma"], t["ativas"][0], t["ativas"][1]

    client = _loga(app, i["resp"])
    client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(o1)},
    )
    client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(o2)},
    )
    with app.app_context():
        inscs = _inscricoes_ativas(turma_id)
        assert len(inscs) == 2
        assert {x.turma_curso_id for x in inscs} == {o1, o2}


# --- duplicata na MESMA oferta: rota recusa com flash, sem 500 ---------------
def test_duplicata_mesma_oferta_recusada(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=i["cA"], ativo_ofertas=1)
        aluno = _aluno(i)
        db.session.commit()
        turma_id = t["turma"]

    client = _loga(app, i["resp"])
    r1 = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    r2 = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    # A rota redireciona (flash) em vez de estourar 500 ao reenturmar.
    assert r1.status_code == 302
    assert r2.status_code == 302
    with app.app_context():
        assert len(_inscricoes_ativas(turma_id)) == 1


# --- duplicata ativa na mesma oferta: recusada pelo índice único -------------
def test_indice_unicidade_bloqueia_duplicata_ativa_mesma_oferta(app):
    """uix_inscricao_ativa_aluno_oferta: duas ativas do mesmo aluno na mesma
    oferta são recusadas pelo índice único parcial (rede de segurança do DB)."""
    from sqlalchemy.exc import IntegrityError

    from _helpers import nova_inscricao

    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=i["cA"], ativo_ofertas=1)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, oferta_id = t["turma"], t["ativas"][0]

        nova_inscricao(aluno, turma_id, oferta_id)
        db.session.commit()
        with pytest.raises(IntegrityError):
            nova_inscricao(aluno, turma_id, oferta_id)
            db.session.commit()
        db.session.rollback()
        assert len(_inscricoes_ativas(turma_id)) == 1


# --- aluno em DUAS ofertas da mesma turma: permitido (índice por oferta) -----
def test_duas_ofertas_diferentes_mesma_turma_nao_violam_indice(app):
    """O índice é (aluno_id, turma_curso_id): o mesmo aluno pode ter duas
    ativas em ofertas distintas da mesma turma sem violá-lo."""
    from _helpers import nova_inscricao

    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=2)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, o1, o2 = t["turma"], t["ativas"][0], t["ativas"][1]

        nova_inscricao(aluno, turma_id, o1)
        nova_inscricao(aluno, turma_id, o2)
        db.session.commit()
        assert len(_inscricoes_ativas(turma_id)) == 2


# --- aluno enturmado aparece na pauta da oferta correta ----------------------
def test_pauta_por_oferta_correta(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=None, ativo_ofertas=2)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, o1, o2 = t["turma"], t["ativas"][0], t["ativas"][1]

    client = _loga(app, i["resp"])
    client.post(
        f"/turma/enturmar/{turma_id}",
        data={"aluno_ids[]": str(aluno), "turma_curso_id": str(o1)},
    )
    with app.app_context():
        na_o1 = _alunos_da_oferta(turma_id, o1)
        na_o2 = _alunos_da_oferta(turma_id, o2)
        assert [a.id for a in na_o1] == [aluno]
        assert na_o2 == []


# --- usuário de OUTRA unidade: recusado (403) --------------------------------
def test_usuario_de_outra_unidade_recusado(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=i["cA"], ativo_ofertas=1)
        aluno = _aluno(i)
        # usuário pedagógico de outra unidade.
        i2 = _base(unidade_nome="U M1 Outra")
        db.session.commit()
        turma_id, outra_resp = t["turma"], i2["resp"]

    client = _loga(app, outra_resp)
    r = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    assert r.status_code == 403
    with app.app_context():
        assert _inscricoes_ativas(turma_id) == []


# --- Etapa M1.1 removida: adoção/vínculo de inscrição NULL ------------------
# O NOT NULL de Inscricao.turma_curso_id (c3d4e5f6a7b8) extinguiu o estado
# NULL; _null_ativa, test_adota_null_ativa_com_uma_oferta,
# test_adota_null_ativa_com_duas_ofertas, test_nao_adota_null_inativa e
# test_adota_apenas_menor_id_entre_duas_null foram removidos. O leitor
# defensivo incluir_inscricoes_null tornou-se código morto e foi removido
# na ETAPA B6 (parâmetro de _alunos_da_oferta e todos os call-sites),
# juntamente com o ramo NULL de cond_inscricao_enturmada.

# Criação normal na oferta (data_inicio = hoje). O nome "sem_null" é
# histórico: referia-se à ausência do estado NULL, extinto pelo NOT NULL.
def test_sem_null_cria_normalmente(app):
    with app.app_context():
        i = _base()
        t = _turma(i, curso_id=i["cA"], ativo_ofertas=1)
        aluno = _aluno(i)
        db.session.commit()
        turma_id, oferta_id = t["turma"], t["ativas"][0]

    client = _loga(app, i["resp"])
    r = client.post(
        f"/turma/enturmar/{turma_id}", data={"aluno_ids[]": str(aluno)}
    )
    assert r.status_code == 302
    with app.app_context():
        inscs = _inscricoes_ativas(turma_id)
        assert len(inscs) == 1
        assert inscs[0].turma_curso_id == oferta_id
        assert inscs[0].data_inicio == date.today()

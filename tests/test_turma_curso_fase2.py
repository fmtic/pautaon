"""
Testes da Onda 4 — Fase 2: regras de aplicação das ofertas de curso na turma
(`app/services/turma_curso.py`) e rotas de cadastro incremental
(`/turma/<id>/ofertas*`).

Cobre os cenários do plano (§16) pertinentes à Fase 2:
    - Adição da primeira oferta (sem principal obrigatório) e espelhamento
      controlado do vínculo legado em turma sem curso.
    - Bloqueio de curso repetido na mesma turma (mensagem de regra de negócio).
    - Bloqueio de curso de outra unidade.
    - Principal obrigatório ao passar a ter 2+ ofertas (nenhum marcado).
    - Troca atômica de principal (sempre exatamente um ativo).
    - Desativação com guarda do principal remanescente; histórico preservado.
    - Edição de oferta com 2+ ofertas não toca as colunas legadas.
    - Rotas: tela lista ofertas; POST nova cria oferta; POST duplicado é
      rejeitado com flash e nada cria.
"""

import pytest

from app import create_app, db
from app.models import Curso, Turma, TurmaCurso, Unidade, User
from app.services.turma_curso import (
    adicionar_oferta,
    definir_principal,
    desativar_oferta,
    editar_oferta,
    ofertas_ativas,
)
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    """Unidade A com 2 cursos e 1 turma sem curso; unidade B com 1 curso."""
    unidade_a = Unidade(nome="Unidade A", ativo=True)
    unidade_b = Unidade(nome="Unidade B", ativo=True)
    db.session.add_all([unidade_a, unidade_b])
    db.session.flush()

    admin = User(
        name="Admin testes", email="admin.fase2@example.com",
        role="admin", first_login=False, unidade_id=unidade_a.id,
    )
    professor = User(
        name="Professor A", email="prof.a@example.com",
        role="professor", first_login=False, unidade_id=unidade_a.id,
    )
    db.session.add_all([admin, professor])

    curso1 = Curso(nome="Carpintaria", unidade_id=unidade_a.id, ativo=True)
    curso2 = Curso(nome="Mecânica", unidade_id=unidade_a.id, ativo=True)
    curso_b = Curso(nome="Natação B", unidade_id=unidade_b.id, ativo=True)
    db.session.add_all([curso1, curso2, curso_b])

    turma = Turma(nome="Turma sem curso", unidade_id=unidade_a.id, ativo=True)
    db.session.add(turma)
    db.session.commit()

    return {
        "admin_id": admin.id,
        "professor_id": professor.id,
        "unidade_a": unidade_a.id,
        "turma_id": turma.id,
        "curso1": curso1.id,
        "curso2": curso2.id,
        "curso_b": curso_b.id,
    }


def _turma(base):
    return db.session.get(Turma, base["turma_id"])


# ---------------------------------------------------------------------------
# Serviço: regras de negócio
# ---------------------------------------------------------------------------

def test_primeira_oferta_sem_principal_e_espelhamento_legado(base):
    """Primeira oferta não exige principal; turma sem curso legado espelha."""
    turma = _turma(base)
    oferta = adicionar_oferta(turma, curso_id=base["curso1"])

    assert oferta.id is not None
    assert oferta.principal is False
    assert turma.curso_id == base["curso1"]
    assert len(ofertas_ativas(turma.id)) == 1


def test_curso_repetido_na_mesma_turma_e_bloqueado(base):
    turma = _turma(base)
    adicionar_oferta(turma, curso_id=base["curso1"])

    with pytest.raises(ValueError, match="já é ofertado"):
        adicionar_oferta(turma, curso_id=base["curso1"])
    assert len(ofertas_ativas(turma.id)) == 1


def test_curso_de_outra_unidade_e_bloqueado(base):
    turma = _turma(base)
    with pytest.raises(ValueError, match="não pertence à unidade"):
        adicionar_oferta(turma, curso_id=base["curso_b"])


def test_segunda_oferta_exige_principal_quando_nenhuma_tem(base):
    """Backfill/legado sem principal: ao entrar o 2º curso, a marca é obrigatória."""
    turma = _turma(base)
    adicionar_oferta(turma, curso_id=base["curso1"])

    with pytest.raises(ValueError, match="curso principal"):
        adicionar_oferta(turma, curso_id=base["curso2"])

    oferta2 = adicionar_oferta(turma, curso_id=base["curso2"], principal=True)
    assert oferta2.principal is True
    assert len(ofertas_ativas(turma.id)) == 2


def test_segunda_oferta_livre_quando_existe_principal(base):
    """Já havendo principal marcado, a nova oferta pode entrar sem marca."""
    turma = _turma(base)
    primeira = adicionar_oferta(turma, curso_id=base["curso1"], principal=True)
    segunda = adicionar_oferta(turma, curso_id=base["curso2"])

    assert segunda.principal is False
    assert primeira.principal is True


def test_definir_principal_faz_swap_atomico(base):
    turma = _turma(base)
    primeira = adicionar_oferta(turma, curso_id=base["curso1"], principal=True)
    segunda = adicionar_oferta(turma, curso_id=base["curso2"])

    definir_principal(segunda)
    db.session.expire_all()

    principais = [o for o in ofertas_ativas(turma.id) if o.principal]
    assert len(principais) == 1
    assert principais[0].id == segunda.id
    assert primeira.principal is False


def test_desativar_oferta_preserva_historico_e_espeleo_nao_regressa(base):
    turma = _turma(base)
    oferta = adicionar_oferta(turma, curso_id=base["curso1"])

    desativar_oferta(oferta)
    db.session.expire_all()

    assert oferta.ativo is False
    # Espelhamento não é revertido: turma manteve o vínculo histórico.
    assert turma.curso_id == base["curso1"]
    assert len(ofertas_ativas(turma.id)) == 0


def test_desativar_oferta_bloqueada_se_deixaria_2_ativas_sem_principal(base):
    """Remover a única principal deixaria 2+ ativas sem principal — bloqueado."""
    turma = _turma(base)
    principal = adicionar_oferta(turma, curso_id=base["curso1"], principal=True)
    segunda = adicionar_oferta(turma, curso_id=base["curso2"])
    curso3 = Curso(
        nome="Eletrônica", unidade_id=base["unidade_a"], ativo=True,
    )
    db.session.add(curso3)
    db.session.commit()
    terceira = adicionar_oferta(turma, curso_id=curso3.id)

    # Desativar uma não-principal é sempre livre (principal permanece).
    desativar_oferta(segunda)
    assert segunda.ativo is False

    # Com 1 ativa sobrando, remover a principal é livre (regra só vale para 2+).
    definir_principal(terceira)
    desativar_oferta(principal)
    assert principal.ativo is False

    # Reconstroi 2 ativas sem principal via reativação direta (o UNIQUE pleno
    # impede reinserir o mesmo curso; reativar o registro histórico é válido).
    segunda.ativo = True
    principal.ativo = True
    principal.principal = False
    db.session.commit()
    assert len(ofertas_ativas(turma.id)) == 3
    with pytest.raises(ValueError, match="sem principal"):
        desativar_oferta(terceira)


def test_editar_oferta_com_duas_ativas_nao_toca_legado(base):
    turma = _turma(base)
    primeira = adicionar_oferta(turma, curso_id=base["curso1"], principal=True)
    adicionar_oferta(turma, curso_id=base["curso2"])

    editar_oferta(primeira, turno="Noite", professor_id=base["professor_id"])
    db.session.expire_all()

    assert primeira.turno == "Noite"
    assert primeira.professor_id == base["professor_id"]
    # Dual-write proibido com 2+ ofertas: colunas legadas intocadas.
    assert turma.turno is None
    assert turma.professor_id is None


def test_edicao_de_oferta_rejeita_professor_de_outra_unidade(base):
    turma = _turma(base)
    oferta = adicionar_oferta(turma, curso_id=base["curso1"])
    outro = User(
        name="Prof B", email="prof.b@example.com",
        role="professor", first_login=False, unidade_id=base["unidade_a"] + 1,
    )
    db.session.add(outro)
    db.session.commit()

    with pytest.raises(ValueError, match="Professor inválido"):
        editar_oferta(oferta, professor_id=outro.id)


# ---------------------------------------------------------------------------
# Rotas: cadastro incremental pela UI
# ---------------------------------------------------------------------------

def _client_admin(app, base):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(base["admin_id"])
        session["_fresh"] = True
        session["unidade_id"] = base["unidade_a"]
    return client


def test_rota_ofertas_lista_cursosDisponiveis(app, base):
    client = _client_admin(app, base)
    resposta = client.get(f"/turma/{base['turma_id']}/ofertas")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)
    assert "Carpintaria" in html
    assert "Mecânica" in html


def test_rota_nova_oferta_cria_incremental(app, base):
    client = _client_admin(app, base)
    resposta = client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso1"], "turno": "Manhã"},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "adicionado à turma" in resposta.get_data(as_text=True)

    turma = db.session.get(Turma, base["turma_id"])
    assert len(ofertas_ativas(turma.id)) == 1

    # Incremental: segundo curso entra marcado como principal.
    client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso2"], "principal": "on"},
    )
    assert len(ofertas_ativas(base["turma_id"])) == 2


def test_rota_curso_duplicado_rejeitada_com_flash(app, base):
    client = _client_admin(app, base)
    client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso1"]},
    )
    resposta = client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso1"]},
        follow_redirects=True,
    )
    assert "já é ofertado" in resposta.get_data(as_text=True)
    assert len(ofertas_ativas(base["turma_id"])) == 1


def test_rota_segunda_oferta_sem_principal_rejeitada(app, base):
    client = _client_admin(app, base)
    client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso1"]},
    )
    resposta = client.post(
        f"/turma/{base['turma_id']}/ofertas/nova",
        data={"curso_id": base["curso2"]},
        follow_redirects=True,
    )
    assert "curso principal" in resposta.get_data(as_text=True)
    assert len(ofertas_ativas(base["turma_id"])) == 1

"""
I1 (E3) — regra por OFERTA nos guardas restantes + detalhe sem link 403.

Guardas migradas de `turma.professor_id` para `professor_da_oferta` /
`condicao_professor_da_oferta` (sem herança, MER §8.12/§8.22):
`ver_turma`, `ver_observacoes`, GET e POST `/frequencia`, `historico_aluno`
e `/aluno/<id>/foto`.

Matriz coberta:
    - Professor da OFERTA (sem ser o da turma) GANHA acesso.
    - Professor da TURMA sem oferta própria PERDE o acesso (403 / flash).
    - Trocar o professor da oferta TRANSFERE o acesso (novo 200, antigo 403)
      em pauta, Diário, histórico e foto.
    - `detalhe.html`: o professor só vê links das ofertas dele e nenhum link
      da tela leva a 403.
"""

from _helpers import login_as

import re
from datetime import date, time

import pytest

from app import db
from app.models import Aluno, Curso, Inscricao, Turma, TurmaCurso, Unidade, User
from app.services.turma_curso import adicionar_oferta
from config import Config

AGENDA = [(0, time(9), time(10))]
AGENDA_2 = [(1, time(9), time(10))]
FORM_AGENDA = {"dias_semana": "0", "hora_inicio": "09:00", "hora_fim": "10:00"}
DATA_INI = date(2026, 3, 9)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def cenario(app):
    """Turma cujo professor cadastrado (p_turma) NÃO é o professor de nenhuma oferta.

    - oferta o1 (curso 1): professor p_oferta — o "professor da oferta";
    - oferta o2 (curso 2): professor p_outro;
    - `turma.professor_id` = p_turma (só a turma; é quem perde acesso na E3);
    - aluno inscrito em o1 (para histórico e foto).
    """
    unidade = Unidade(nome="U i1e3", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    def _user(nome, id_slug):
        u = User(
            name=nome, email=f"{id_slug}.i1e3@example.com",
            role="professor", first_login=False, unidade_id=unidade.id,
        )
        db.session.add(u)
        return u

    p_oferta = _user("Prof Oferta", "of")
    p_turma = _user("Prof Turma", "tu")
    p_outro = _user("Prof Outro", "ou")
    admin = User(
        name="Admin I1E3", email="admin.i1e3@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    db.session.add(admin)
    db.session.flush()

    c1 = Curso(nome="Curso 1", unidade_id=unidade.id, ativo=True)
    c2 = Curso(nome="Curso 2", unidade_id=unidade.id, ativo=True)
    db.session.add_all([c1, c2])

    turma = Turma(
        nome="T i1e3", unidade_id=unidade.id, ativo=True,
        turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
        programa="Teste", professor_id=p_turma.id,
    )
    db.session.add(turma)
    db.session.commit()

    o1 = adicionar_oferta(
        turma, curso_id=c1.id, principal=True, programa="Teste",
        professor_id=p_oferta.id, agenda=AGENDA,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    o2 = adicionar_oferta(
        turma, curso_id=c2.id, principal=False, programa="Teste",
        professor_id=p_outro.id, agenda=AGENDA_2,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )

    aluno = Aluno(
        nome="Aluno I1E3", nome_social="Aluno",
        ativo=True, unidade_id=unidade.id,
    )
    db.session.add(aluno)
    db.session.flush()
    db.session.add(Inscricao(
        aluno_id=aluno.id, turma_id=turma.id,
        turma_curso_id=o1.id, ativo=True,
    ))
    db.session.commit()

    return {
        "unidade": unidade.id, "turma": turma.id,
        "o1": o1.id, "o2": o2.id, "aluno": aluno.id, "c1": c1.id,
        "p_oferta": p_oferta.id, "p_turma": p_turma.id,
        "p_outro": p_outro.id, "admin": admin.id,
    }


def _login(app, cenario, usuario):
    """Cliente logado com `cenario[usuario]`.

    Delega a `tests/_helpers.login_as`: o fixture segura um
    app context durante o teste inteiro e o Flask-Login cachea o usuário em `g`
    — sem a limpeza, o segundo cliente agia como o primeiro (armadilha
    documentada no MER, auditoria L4.2).
    """
    client = app.test_client()
    login_as(client, str(cenario[usuario]), cenario["unidade"])
    return client


def _acessos(client, cenario):
    """(ver_turma, Diário, GET pauta, POST pauta, histórico, foto) de um professor."""
    t = cenario["turma"]
    a = cenario["aluno"]
    return {
        "ver_turma": client.get(f"/turma/{t}").status_code,
        "diario": client.get(f"/turma/{t}/observacoes").status_code,
        "get_frequencia": client.get(f"/frequencia?turma_id={t}").status_code,
        "post_frequencia": client.post(
            "/frequencia", data={"turma": str(t)},
        ).status_code,
        "historico": client.get(f"/aluno/{a}/historico").status_code,
        # Sem foto gravada o acesso liberado termina em redirect para o padrão.
        "foto": client.get(f"/aluno/{a}/foto").status_code,
    }


def _troca_professor_da_oferta(app, cenario, novo_key):
    """Troca pela rota real (admin), como na E2 — escrita dentro do request.

    A o1 não tem lançamentos, então a confirmação não é exigida; o hidden vai
    mesmo assim para valer o caminho "confirmado".
    """
    client = _login(app, cenario, "admin")
    resposta = client.post(
        f"/turma/oferta/{cenario['o1']}/editar",
        data={
            "curso_id": cenario["c1"],
            "professor_id": cenario[novo_key],
            "turno": "Manhã", "programa": "Teste",
            "data_inicio": DATA_INI.isoformat(),
            "data_fim": DATA_FIM.isoformat(),
            "confirmar_troca_professor": "1",
            **FORM_AGENDA,
        },
    )
    assert resposta.status_code == 302
    with app.app_context():
        db.session.expire_all()
        assert db.session.get(TurmaCurso, cenario["o1"]).professor_id == cenario[novo_key]


# ---------------------------------------------------------------------------
# Efeito da migração: quem ganha e quem perde
# ---------------------------------------------------------------------------

def test_professor_da_oferta_ganha_acesso_sem_ser_da_turma(app, cenario):
    """p_oferta não é `turma.professor_id`, mas leciona a oferta o1 → entra."""
    client = _login(app, cenario, "p_oferta")
    acessos = _acessos(client, cenario)

    assert acessos["ver_turma"] == 200
    assert acessos["diario"] == 200
    assert acessos["get_frequencia"] == 200
    # Passa da guarda e cai na validação seguinte (data ausente → flash + 302).
    assert acessos["post_frequencia"] == 302
    assert acessos["historico"] == 200
    assert acessos["foto"] != 403


def test_professor_da_turma_sem_oferta_propria_perde_acesso(app, cenario):
    """Antigo × novo × motivo: p_turma entrava via `turma.professor_id` (200);
    pela regra por oferta sem herança, sem oferta própria ele recebe 403 — e no
    GET /frequencia a turma some da lista dele (flash + redirect, sem 403 puro).
    """
    client = _login(app, cenario, "p_turma")
    acessos = _acessos(client, cenario)

    assert acessos["ver_turma"] == 403
    assert acessos["diario"] == 403
    assert acessos["get_frequencia"] == 302
    resposta = client.get(
        f"/frequencia?turma_id={cenario['turma']}", follow_redirects=True,
    )
    assert "não tem permissão para acessar esta turma" in resposta.get_data(as_text=True)
    assert acessos["post_frequencia"] == 403
    assert acessos["historico"] == 403
    assert acessos["foto"] == 403


def test_gestao_e_admin_mantem_acesso(app, cenario):
    client = _login(app, cenario, "admin")
    assert client.get(f"/turma/{cenario['turma']}").status_code == 200
    assert client.get(f"/turma/{cenario['turma']}/observacoes").status_code == 200
    assert client.get(f"/aluno/{cenario['aluno']}/historico").status_code == 200


# ---------------------------------------------------------------------------
# Troca de professor transfere o acesso
# ---------------------------------------------------------------------------

def _pauta_troca(client, cenario):
    t = cenario["turma"]
    a = cenario["aluno"]
    return {
        "pauta": client.get(
            f"/turma/{t}/imprimir-pauta?turma_curso={cenario['o1']}"
        ).status_code,
        "diario": client.get(f"/turma/{t}/observacoes").status_code,
        "historico": client.get(f"/aluno/{a}/historico").status_code,
        "foto": client.get(f"/aluno/{a}/foto").status_code,
    }


def test_troca_de_professor_transfere_acesso(app, cenario):
    """o1: p_oferta → p_turma. Novo professor entra em tudo; o antigo leva 403."""
    antes_novo = _pauta_troca(_login(app, cenario, "p_turma"), cenario)
    assert antes_novo == {
        "pauta": 403, "diario": 403, "historico": 403, "foto": 403,
    }

    _troca_professor_da_oferta(app, cenario, "p_turma")

    depois_antigo = _pauta_troca(_login(app, cenario, "p_oferta"), cenario)
    assert depois_antigo == {
        "pauta": 403, "diario": 403, "historico": 403, "foto": 403,
    }

    depois_novo = _pauta_troca(_login(app, cenario, "p_turma"), cenario)
    assert depois_novo["pauta"] == 200
    assert depois_novo["diario"] == 200
    assert depois_novo["historico"] == 200
    assert depois_novo["foto"] != 403


# ---------------------------------------------------------------------------
# detalhe.html — links por oferta do professor, nenhum link a 403
# ---------------------------------------------------------------------------

def _extrair_links(html, cenario):
    t = cenario["turma"]
    padrao = re.compile(
        rf'href="/turma/{t}/(imprimir-pauta|observacoes)(\?turma_curso=(\d+))?"'
    )
    return [
        (rota, oferta and int(oferta))
        for rota, _, oferta in padrao.findall(html)
    ]


def test_detalhe_professor_mostra_so_as_proprias_ofertas_sem_link_403(app, cenario):
    client = _login(app, cenario, "p_oferta")
    resposta = client.get(f"/turma/{cenario['turma']}")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)

    links = _extrair_links(html, cenario)
    assert links, "detalhe deve oferecer links de pauta/Diário ao professor"
    # Só a oferta dele (o1), sempre com o parâmetro turma_curso; nenhum link de
    # pauta/Diário aponta para a oferta de outro professor.
    assert all(oferta == cenario["o1"] for _, oferta in links)
    assert not any(oferta == cenario["o2"] for _, oferta in links)

    # Conferência real: todo link coletado abre 200 (nenhum leva a 403).
    for rota, oferta in links:
        url = f"/turma/{cenario['turma']}/{rota}"
        if oferta:
            url += f"?turma_curso={oferta}"
        assert client.get(url).status_code == 200, url


def test_detalhe_admin_ve_todas_as_ofertas_sem_link_403(app, cenario):
    client = _login(app, cenario, "admin")
    resposta = client.get(f"/turma/{cenario['turma']}")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)

    links = _extrair_links(html, cenario)
    ofertas_linkadas = {oferta for _, oferta in links if oferta}
    assert {cenario["o1"], cenario["o2"]} <= ofertas_linkadas
    for rota, oferta in links:
        url = f"/turma/{cenario['turma']}/{rota}"
        if oferta:
            url += f"?turma_curso={oferta}"
        assert client.get(url).status_code == 200, url


def test_detalhe_transferencia_reflete_na_troca(app, cenario):
    """Depois de trocar o1 para p_turma, o detalhe dele aponta para o1 e o
    antigo professor não recebe mais link nenhum."""
    _troca_professor_da_oferta(app, cenario, "p_turma")

    novo = _login(app, cenario, "p_turma")
    resposta = novo.get(f"/turma/{cenario['turma']}")
    assert resposta.status_code == 200
    links = _extrair_links(resposta.get_data(as_text=True), cenario)
    assert links and all(oferta == cenario["o1"] for _, oferta in links)

    antigo = _login(app, cenario, "p_oferta")
    assert antigo.get(f"/turma/{cenario['turma']}").status_code == 403

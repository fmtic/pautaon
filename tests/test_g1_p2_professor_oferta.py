"""
G1/P2 (E2) — professor obrigatório na oferta + troca com confirmação e log.

Cobertura:
    - Serviço: `adicionar_oferta`, `editar_oferta` e `criar_oferta_inicial_da_turma`
      recusam professor vazio (ValueError em português); trocar é permitido e a
      herança do professor da turma continua valendo para a primeira oferta.
    - Formulários: POST de nova oferta e de edição sem professor são recusados
      (flash + nada gravado) e a tela não oferece mais a opção "-- Sem professor --".
    - Troca em oferta com lançamento gravado exige confirmação explícita (mesmo
      padrão do bloco de limpeza de lançamentos) e fica registrada em `log_acao`
      com o professor anterior e o novo (id e nome).
    - Edição da turma não propaga NULL para a oferta: a oferta é a fonte.
"""

import re
from datetime import date, time

import pytest

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    LogAcao,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.services.turma_curso import (
    ACAO_TROCA_PROFESSOR_OFERTA,
    adicionar_oferta,
    criar_oferta_inicial_da_turma,
    editar_oferta,
    formatar_detalhe_troca_professor,
    oferta_tem_lancamentos,
    ofertas_com_lancamentos,
    parsear_detalhe_troca_professor,
)
from config import Config

from _helpers import login_as, itens_grade

AGENDA = itens_grade("Segunda", time(9), time(10))
FORM_AGENDA = {"dias_semana": "0", "hora_inicio": "09:00", "hora_fim": "10:00"}
DATA_INI = date(2026, 3, 9)   # segunda-feira
DATA_FIM = date(2026, 12, 15)
RECURSA_VAZIO = "toda oferta precisa de um professor"


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
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    """Unidade com 2 cursos, admin, 2 professores e 1 turma SEM oferta.

    A turma nasce sem professor de propósito: é justamente o estado que o G1/P2
    passou a recusar na oferta. Quem precisa de oferta informa o professor.
    """
    unidade = Unidade(nome="U g1p2", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    admin = User(
        name="Admin G1P2", email="admin.g1p2@example.com",
        role="admin", first_login=False, unidade_id=unidade.id,
    )
    p1 = User(
        name="Prof Um", email="prof1.g1p2@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    p2 = User(
        name="Prof Dois", email="prof2.g1p2@example.com",
        role="professor", first_login=False, unidade_id=unidade.id,
    )
    db.session.add_all([admin, p1, p2])
    db.session.flush()

    c1 = Curso(nome="Curso 1", unidade_id=unidade.id, ativo=True)
    c2 = Curso(nome="Curso 2", unidade_id=unidade.id, ativo=True)
    db.session.add_all([c1, c2])

    turma = Turma(
        nome="T g1p2", unidade_id=unidade.id, ativo=True,
        turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
        programa="Teste",
    )
    db.session.add(turma)
    db.session.commit()

    return {
        "unidade": unidade.id, "admin": admin.id,
        "p1": p1.id, "p2": p2.id, "c1": c1.id, "c2": c2.id,
        "turma": turma.id,
    }


def _turma(base):
    return db.session.get(Turma, base["turma"])


def _oferta(base, *, curso="c1", professor="p1", principal=True):
    """Oferta válida (professor + agenda) criada pelo serviço."""
    return adicionar_oferta(
        _turma(base), curso_id=base[curso], principal=principal,
        programa="Teste", professor_id=base[professor], agenda=AGENDA,
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )


def _client(app, base):
    client = app.test_client()
    login_as(client, str(base["admin"]), base["unidade"])
    return client


def _form_oferta(oferta, **extra):
    """POST de edição de oferta completo (mesmo contrato da tela).

    Valor `None` significa campo vazio — é assim que a tela envia um select sem
    escolha.
    """
    form = {
        "curso_id": oferta.curso_id,
        "professor_id": oferta.professor_id,
        "turno": "Manhã",
        "programa": "Teste",
        "data_inicio": DATA_INI.isoformat(),
        "data_fim": DATA_FIM.isoformat(),
        "confirmar_troca_professor": "0",
        **FORM_AGENDA,
        **extra,
    }
    return {chave: ("" if valor is None else valor) for chave, valor in form.items()}


def _form_turma(turma, oferta, **extra):
    """POST de edição da turma com a agenda atual (não mexe na grade)."""
    form = {
        "turma": turma.nome,
        "turno": turma.turno,
        "curso_id": oferta.curso_id,
        "programa": "Teste",
        "professor_id": oferta.professor_id,
        "data_inicio": (turma.data_inicio or DATA_INI).isoformat(),
        "data_fim": (turma.data_fim or DATA_FIM).isoformat(),
        "limpar_lancamentos": "0",
        "confirmar_troca_professor": "0",
        **FORM_AGENDA,
        **extra,
    }
    return {chave: ("" if valor is None else valor) for chave, valor in form.items()}


def _lancamento(base, oferta):
    """Semeia um lançamento de frequência na oferta (gatilho da confirmação)."""
    aluno = Aluno(nome="Aluno G1P2", unidade_id=base["unidade"], ativo=True)
    db.session.add(aluno)
    db.session.flush()
    db.session.add(Frequencia(
        aluno_id=aluno.id, turma_id=base["turma"], turma_curso_id=oferta.id,
        data=DATA_INI, conceito="A", unidade_id=base["unidade"],
    ))
    db.session.commit()


def _logs_troca():
    return LogAcao.query.filter_by(acao=ACAO_TROCA_PROFESSOR_OFERTA).all()


def _norm(html: str) -> str:
    return re.sub(r"\s+", " ", html)


# ---------------------------------------------------------------------------
# Serviço: professor obrigatório (G1/P2)
# ---------------------------------------------------------------------------

def test_adicionar_oferta_sem_professor_recusada(base):
    turma = _turma(base)
    antes = TurmaCurso.query.count()
    with pytest.raises(ValueError, match=RECURSA_VAZIO):
        adicionar_oferta(
            turma, curso_id=base["c1"], principal=True, programa="Teste",
            agenda=AGENDA,
        )
    assert TurmaCurso.query.count() == antes


def test_adicionar_oferta_herda_professor_da_turma_na_primeira(base):
    """Herança revisada: turma sem vínculo legado empresta o professor à 1ª
    oferta — a ausência é que passou a ser recusada."""
    turma = _turma(base)
    turma.professor_id = base["p1"]
    db.session.commit()

    oferta = adicionar_oferta(
        turma, curso_id=base["c1"], principal=True, programa="Teste",
        agenda=AGENDA,
    )
    assert oferta.professor_id == base["p1"]


def test_editar_oferta_recusa_esvaziar_professor(base):
    oferta = _oferta(base)
    with pytest.raises(ValueError, match=RECURSA_VAZIO):
        editar_oferta(oferta, professor_id=None)
    db.session.rollback()
    assert oferta.professor_id == base["p1"]


def test_editar_oferta_permite_trocar_professor(base):
    oferta = _oferta(base)
    editar_oferta(oferta, professor_id=base["p2"])
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p2"]


def test_criar_oferta_inicial_exige_professor_na_turma(base):
    """Turma com curso legado e sem professor não gera oferta inicial."""
    turma = _turma(base)
    turma.curso_id = base["c1"]
    db.session.commit()

    with pytest.raises(ValueError, match=RECURSA_VAZIO):
        criar_oferta_inicial_da_turma(turma, agenda=AGENDA)
    db.session.rollback()
    assert TurmaCurso.query.count() == 0


def test_detalhe_do_log_contem_ids_e_nomes(base):
    """Round-trip `formatar`/`parsear` com os nomes reais dos professores."""
    texto = formatar_detalhe_troca_professor(7, base["p1"], base["p2"])
    assert texto == (
        f'oferta_id=7 anterior_id={base["p1"]} anterior_nome="Prof Um" '
        f'novo_id={base["p2"]} novo_nome="Prof Dois"'
    )
    assert parsear_detalhe_troca_professor(texto) == {
        "oferta_id": 7,
        "anterior_id": base["p1"], "anterior_nome": "Prof Um",
        "novo_id": base["p2"], "novo_nome": "Prof Dois",
    }
    # Oferta que estava sem professor: o anterior vira o token `none`.
    sem_anterior = formatar_detalhe_troca_professor(7, None, base["p2"])
    lido = parsear_detalhe_troca_professor(sem_anterior)
    assert lido["anterior_id"] is None and lido["anterior_nome"] == ""
    # Texto de outra ação não é confundido com a troca.
    assert parsear_detalhe_troca_professor("aluno_id=1") is None


# ---------------------------------------------------------------------------
# Formulário: recusa sem professor e sem a opção "-- Sem professor --"
# ---------------------------------------------------------------------------

def test_rota_nova_oferta_sem_professor_recusada(app, base):
    client = _client(app, base)
    resposta = client.post(
        f"/turma/{base['turma']}/ofertas/nova",
        data={
            "curso_id": base["c1"], "programa": "Teste",
            "professor_id": "", **FORM_AGENDA,
        },
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert RECURSA_VAZIO in _norm(resposta.get_data(as_text=True))
    assert TurmaCurso.query.count() == 0


def test_rota_edicao_oferta_recusa_esvaziar_professor(app, base):
    oferta = _oferta(base)
    client = _client(app, base)
    resposta = client.post(
        f"/turma/oferta/{oferta.id}/editar",
        data=_form_oferta(oferta, professor_id=None),
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert RECURSA_VAZIO in _norm(resposta.get_data(as_text=True))
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p1"]


def test_tela_de_ofertas_nao_oferece_sem_professor(app, base):
    _oferta(base)
    client = _client(app, base)
    html = client.get(f"/turma/{base['turma']}/ofertas").get_data(as_text=True)
    assert "-- Sem professor --" not in html
    selecoes = re.findall(r'<select[^>]*name="professor_id"[^>]*>', html)
    assert selecoes, "formulários de oferta precisam do campo professor"
    assert all("required" in sel for sel in selecoes)


def test_tela_de_edicao_da_turma_exige_professor_com_oferta_unica(app, base):
    oferta = _oferta(base)
    client = _client(app, base)
    html = client.get(f"/turma/editar/{base['turma']}").get_data(as_text=True)
    assert "-- Sem professor --" not in html
    selecoes = re.findall(r'<select[^>]*name="professor_id"[^>]*>', html)
    assert len(selecoes) == 1
    assert "required" in selecoes[0]
    assert oferta.professor_id == base["p1"]


# ---------------------------------------------------------------------------
# Troca de professor: confirmação quando há lançamento + registro no log
# ---------------------------------------------------------------------------

def test_oferta_tem_lancamentos_reflete_frequencia(base):
    oferta = _oferta(base)
    assert oferta_tem_lancamentos(oferta.id) is False
    _lancamento(base, oferta)
    assert oferta_tem_lancamentos(oferta.id) is True


def test_ofertas_com_lancamentos_em_lote(base):
    """Leitura em lote usada pela tela: só as ofertas lançadas saem."""
    primeira = _oferta(base)
    segunda = _oferta(base, curso="c2", principal=False)
    _lancamento(base, segunda)
    assert ofertas_com_lancamentos([primeira.id, segunda.id]) == {segunda.id}
    assert ofertas_com_lancamentos([]) == set()


def test_tela_sinaliza_oferta_com_lancamento(app, base):
    """A confirmação da tela é pedida só onde há lançamento (padrão da limpeza)."""
    oferta = _oferta(base)
    client = _client(app, base)
    url = f"/turma/{base['turma']}/ofertas"
    assert 'data-com-lancamento="0"' in client.get(url).get_data(as_text=True)

    _lancamento(base, oferta)
    assert 'data-com-lancamento="1"' in client.get(url).get_data(as_text=True)


def test_troca_sem_lancamento_grava_log_com_anterior_e_novo(app, base):
    oferta = _oferta(base)
    client = _client(app, base)
    resposta = client.post(
        f"/turma/oferta/{oferta.id}/editar",
        data=_form_oferta(oferta, professor_id=base["p2"]),
    )
    assert resposta.status_code == 302

    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p2"]
    logs = _logs_troca()
    assert len(logs) == 1
    assert logs[0].usuario_id == base["admin"]
    lido = parsear_detalhe_troca_professor(logs[0].detalhes)
    assert lido == {
        "oferta_id": oferta.id,
        "anterior_id": base["p1"], "anterior_nome": "Prof Um",
        "novo_id": base["p2"], "novo_nome": "Prof Dois",
    }


def test_troca_com_lancamento_exige_confirmacao(app, base):
    oferta = _oferta(base)
    _lancamento(base, oferta)
    client = _client(app, base)

    resposta = client.post(
        f"/turma/oferta/{oferta.id}/editar",
        data=_form_oferta(oferta, professor_id=base["p2"]),
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Trocar o professor de uma oferta com lançamentos exige" in _norm(
        resposta.get_data(as_text=True)
    )
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p1"]
    assert _logs_troca() == []

    # Confirmada a troca, ela acontece e fica registrada.
    resposta = client.post(
        f"/turma/oferta/{oferta.id}/editar",
        data=_form_oferta(
            oferta, professor_id=base["p2"],
            confirmar_troca_professor="1",
        ),
    )
    assert resposta.status_code == 302
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p2"]
    assert len(_logs_troca()) == 1


def test_troca_para_o_mesmo_professor_nao_registra_nada(app, base):
    oferta = _oferta(base)
    _lancamento(base, oferta)
    client = _client(app, base)
    resposta = client.post(
        f"/turma/oferta/{oferta.id}/editar",
        data=_form_oferta(oferta, professor_id=base["p1"]),
    )
    assert resposta.status_code == 302
    assert _logs_troca() == []


def test_log_de_troca_nao_altera_formato_das_outras_entradas(base):
    """A entrada nova convive com as existentes: `detalhes` próprios continuam
    intactos e o parser só reconhece o texto da troca."""
    db.session.add(LogAcao(
        usuario_id=base["admin"], usuario_nome="Admin G1P2",
        acao="Editar Turma", detalhes="<Turma id=1 nome='T'>",
        unidade_id=base["unidade"],
    ))
    oferta = _oferta(base)
    gravar = formatar_detalhe_troca_professor(oferta.id, base["p1"], base["p2"])
    db.session.add(LogAcao(
        usuario_id=base["admin"], usuario_nome="Admin G1P2",
        acao=ACAO_TROCA_PROFESSOR_OFERTA, detalhes=gravar,
        unidade_id=base["unidade"],
    ))
    db.session.commit()

    antiga = LogAcao.query.filter_by(acao="Editar Turma").one()
    assert antiga.detalhes == "<Turma id=1 nome='T'>"
    assert parsear_detalhe_troca_professor(antiga.detalhes) is None
    assert parsear_detalhe_troca_professor(gravar)["novo_id"] == base["p2"]


# ---------------------------------------------------------------------------
# Edição da turma: nunca propaga NULL para a oferta (a oferta é a fonte)
# ---------------------------------------------------------------------------

def test_editar_turma_sem_professor_nao_zera_a_oferta(app, base):
    turma = _turma(base)
    oferta = _oferta(base)
    client = _client(app, base)
    resposta = client.post(
        f"/turma/editar/{turma.id}",
        data=_form_turma(turma, oferta, professor_id=None),
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    db.session.expire_all()
    oferta_db = db.session.get(TurmaCurso, oferta.id)
    turma_db = db.session.get(Turma, turma.id)
    assert oferta_db.professor_id == base["p1"]
    # O vazio do formulário volta a ser o professor da oferta, não NULL.
    assert turma_db.professor_id == base["p1"]


def test_editar_turma_troca_professor_da_oferta_unica_com_log(app, base):
    turma = _turma(base)
    oferta = _oferta(base)
    client = _client(app, base)
    resposta = client.post(
        f"/turma/editar/{turma.id}",
        data=_form_turma(turma, oferta, professor_id=base["p2"]),
    )
    assert resposta.status_code == 302
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p2"]
    assert db.session.get(Turma, turma.id).professor_id == base["p2"]
    logs = _logs_troca()
    assert len(logs) == 1
    lido = parsear_detalhe_troca_professor(logs[0].detalhes)
    assert (lido["anterior_id"], lido["novo_id"]) == (base["p1"], base["p2"])
    assert (lido["anterior_nome"], lido["novo_nome"]) == ("Prof Um", "Prof Dois")


def test_editar_turma_com_lancamento_exige_confirmacao_na_troca(app, base):
    turma = _turma(base)
    oferta = _oferta(base)
    _lancamento(base, oferta)
    client = _client(app, base)

    resposta = client.post(
        f"/turma/editar/{turma.id}",
        data=_form_turma(turma, oferta, professor_id=base["p2"]),
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    assert "Trocar o professor de uma oferta com lançamentos exige" in _norm(
        resposta.get_data(as_text=True)
    )
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p1"]
    assert _logs_troca() == []

    resposta = client.post(
        f"/turma/editar/{turma.id}",
        data=_form_turma(
            turma, oferta, professor_id=base["p2"],
            confirmar_troca_professor="1",
        ),
    )
    assert resposta.status_code == 302
    db.session.expire_all()
    assert db.session.get(TurmaCurso, oferta.id).professor_id == base["p2"]
    assert len(_logs_troca()) == 1

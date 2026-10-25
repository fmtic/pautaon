"""Etapa M2 — Desenturmar por oferta + serviço único de criação de inscrição.

Roteiro do Passo 5:

Rota ``registros.desenturmar_alunos`` (POST /turma/desenturmar/<aluno>):
    1 inscrição ativa desenturma como antes (delete físico sem Frequencia;
    soft ``DESENTURMADO`` com Frequencia conceituada); 2 ofertas sem escolha
    recusa e não grava; 2 ofertas com escolha desativa só a apontada; oferta/
    inscrição de outra turma recusada (incl. inscrição inconsistente, guarda
    ``oferta_alvo.turma_id != turma.id``); inscrição inativa não é alvo;
    usuário de outra unidade → 403; admin sem unidade na sessão → 403.

Serviço ``app.services.enturmacao.enturmar_aluno`` (unitários):
    0 ofertas; 1 oferta sem id (auto-seleção); 2+ sem id (exige escolha);
    2+ com id (cria na apontada); oferta inativa; oferta de outra turma;
    duplicata. O serviço não commita.

Um usuário por teste (regra do responsável).
"""

from datetime import date, time

import pytest

from app import create_app
from app.database import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from app.services.enturmacao import (
    MSG_JA_ENTURMADO,
    MSG_SELECIONE_OFERTA,
    MSG_TURMA_SEM_OFERTA,
    enturmar_aluno,
)
from config import Config

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


@pytest.fixture
def client(app):
    return app.test_client()


def _loga(client, user_id, unidade_id=None):
    """Cria sessão de teste. unidade_id=None não grava a chave na sessão
    (caso do admin em Visão Global)."""
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        if unidade_id is not None:
            session["unidade_id"] = unidade_id
    return client


def _seed_turma(unidade, curso, nome="Turma M2"):
    turma = Turma(
        nome=nome, unidade_id=unidade.id, ativo=True,
        professor_id=None, turno="Manhã", dias_semana="Segunda",
        hora_inicio=time(9, 0), hora_fim=time(10, 0),
        data_inicio=DATA_INI, data_fim=DATA_FIM,
    )
    db.session.add(turma)
    db.session.flush()
    return turma


def _seed_oferta(turma, curso, unidade, *, ativo=True, principal=False):
    oferta = TurmaCurso(
        turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
        ativo=ativo, principal=principal, professor_id=None,
        turno="Manhã", dias_semana="Segunda",
        hora_inicio=time(9, 0), hora_fim=time(10, 0),
        data_inicio=DATA_INI, data_fim=DATA_FIM, programa="Teste",
    )
    db.session.add(oferta)
    db.session.flush()
    return oferta


def _seed_inscricao(aluno, turma, oferta, *, ativo=True):
    inscricao = Inscricao(
        aluno_id=aluno.id, turma_id=turma.id,
        turma_curso_id=oferta.id, ativo=ativo,
    )
    db.session.add(inscricao)
    db.session.flush()
    return inscricao


def _seed_cenario(roles=("pedagogico",), alunos=1, ofertas=1):
    """Unidade local + 1 curso por oferta + turma com `ofertas` ofertas
    ativas + `alunos` alunos enturmados em todas as ofertas.

    Cada item de ``roles`` gera um usuário na MESMA unidade (um usuário por
    teste: chame com uma role só). Retorna dict de ids."""
    unidade = Unidade(nome="U M2", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    users = []
    for role in roles:
        u = User(
            name=f"Usuário {role}", email=f"{role}.m2.{len(users)}@example.com",
            role=role, first_login=False, unidade_id=unidade.id,
        )
        db.session.add(u)
        users.append(u)

    alunos = [
        Aluno(nome=f"Aluno {k + 1}", ativo=True, unidade_id=unidade.id)
        for k in range(alunos)
    ]
    db.session.add_all(alunos)

    # TurmaCurso tem UNIQUE (turma_id, curso_id): cada oferta da mesma
    # turma precisa apontar para um curso distinto.
    cursos = [
        Curso(nome=f"Curso {k + 1}", unidade_id=unidade.id, ativo=True)
        for k in range(max(ofertas, 1))
    ]
    db.session.add_all(cursos)
    db.session.flush()

    turma = _seed_turma(unidade, cursos[0])
    ofert = [
        _seed_oferta(turma, cursos[k], unidade, ativo=True, principal=(k == 0))
        for k in range(ofertas)
    ]
    inscricoes = [
        _seed_inscricao(aluno, turma, oferta)
        for aluno in alunos
        for oferta in ofert
    ]
    db.session.commit()
    return {
        "unidade": unidade.id,
        "users": [u.id for u in users],
        "alunos": [a.id for a in alunos],
        "turma": turma.id,
        "ofertas": [o.id for o in ofert],
        "inscricoes": [i.id for i in inscricoes],
    }


def _post_desenturmar(client, c, oferta=None):
    url = f"/turma/desenturmar/{c['alunos'][0]}?turma_id={c['turma']}"
    if oferta is not None:
        url += f"&turma_curso_id={oferta}"
    return client.post(url, follow_redirects=False)


# =============================================================================
# Rota — comportamento preservado (1 inscrição ativa)
# =============================================================================


def test_unica_inscricao_sem_frequencia_desenturma_com_delete_fisico(client, app):
    """Sem Frequencia conceituada: delete físico, como antes do M2."""
    c = _seed_cenario(roles=("pedagogico",))
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c)

    assert resp.status_code == 302
    assert f"/turma/{c['turma']}" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Inscricao, c["inscricoes"][0]) is None


def test_unica_inscricao_com_frequencia_desenturma_com_soft_delete(client, app):
    """Com Frequencia conceituada: ativo=False, motivo DESENTURMADO e
    data_desativacao preenchida (semântica preservada pelo M2)."""
    c = _seed_cenario(roles=("pedagogico",))
    with app.app_context():
        db.session.add(Frequencia(
            aluno_id=c["alunos"][0], turma_id=c["turma"],
            turma_curso_id=c["ofertas"][0], data=DATA_INI,
            conceito=ConceitoFrequencia.A, unidade_id=c["unidade"],
        ))
        db.session.commit()
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c)

    assert resp.status_code == 302
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        assert insc is not None
        assert insc.ativo is False
        assert insc.motivo_desativacao == "DESENTURMADO"
        assert insc.data_desativacao is not None


# =============================================================================
# Rota — 2+ inscrições ativas exigem escolha explícita da oferta
# =============================================================================


def test_duas_ofertas_sem_escolha_recusa_e_nao_grava(client, app):
    """Nunca usar .first() para escolher: sem turma_curso_id a rota recusa
    e nenhuma inscrição é alterada."""
    c = _seed_cenario(roles=("pedagogico",), ofertas=2)
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c)

    assert resp.status_code == 302
    with app.app_context():
        for iid in c["inscricoes"]:
            insc = db.session.get(Inscricao, iid)
            assert insc is not None and insc.ativo is True
        # Nada foi gravado além do estado inicial
        assert Inscricao.query.filter_by(ativo=True).count() == 2


def test_duas_ofertas_com_escolha_desativa_so_a_apontada(client, app):
    """Com turma_curso_id, sai apenas a inscrição daquela oferta; a outra
    segue ativa."""
    c = _seed_cenario(roles=("pedagogico",), ofertas=2)
    alvo, preservada = c["inscricoes"][0], c["inscricoes"][1]
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c, oferta=c["ofertas"][0])

    assert resp.status_code == 302
    assert f"oferta_sel={c['ofertas'][0]}" in resp.headers["Location"]
    with app.app_context():
        assert db.session.get(Inscricao, alvo) is None
        insc = db.session.get(Inscricao, preservada)
        assert insc is not None and insc.ativo is True


def test_oferta_de_outra_turma_recusada(client, app):
    """turma_curso_id de outra turma não é aceito, mesmo havendo inscrição
    ativa do aluno nessa outra oferta."""
    c = _seed_cenario(roles=("pedagogico",))
    with app.app_context():
        unidade = db.session.get(Unidade, c["unidade"])
        curso2 = Curso(nome="Curso Outra Turma", unidade_id=c["unidade"], ativo=True)
        db.session.add(curso2)
        db.session.flush()
        turma2 = _seed_turma(unidade, curso2, nome="Turma M2 (outra)")
        oferta2 = _seed_oferta(turma2, curso2, unidade)
        _seed_inscricao(db.session.get(Aluno, c["alunos"][0]), turma2, oferta2)
        db.session.commit()
        oferta2_id = oferta2.id
        insc_turma2_id = Inscricao.query.filter_by(
            turma_id=turma2.id
        ).first().id
    _loga(client, c["users"][0])

    # Alvo: turma do cenário 1, mas com oferta pertencente à outra turma.
    resp = client.post(
        f"/turma/desenturmar/{c['alunos'][0]}"
        f"?turma_id={c['turma']}&turma_curso_id={oferta2_id}",
        follow_redirects=False,
    )

    assert resp.status_code == 302
    with app.app_context():
        # Nada mudou: nenhuma das duas inscrições ativas foi tocada.
        assert db.session.get(Inscricao, c["inscricoes"][0]).ativo is True
        assert db.session.get(Inscricao, insc_turma2_id).ativo is True


def test_inscricao_inconsistente_com_oferta_de_outra_turma_recusada(client, app):
    """Guarda nova do M2: se a linha inscrita aponta turma de uma turma mas
    turma_curso_id pertence a outra, a rota recusa em vez de apagar."""
    c = _seed_cenario(roles=("pedagogico",))
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        curso_estranho = Curso(
            nome="Curso Estranho", unidade_id=c["unidade"], ativo=True,
        )
        db.session.add(curso_estranho)
        db.session.flush()
        turma_estranha = _seed_turma(
            db.session.get(Unidade, c["unidade"]), curso_estranho,
            nome="Turma Estranha",
        )
        oferta_estranha = _seed_oferta(turma_estranha, curso_estranho, db.session.get(Unidade, c["unidade"]))
        # Corrompe a inscrição: turma da Turma M2, oferta de outra turma.
        insc.turma_curso_id = oferta_estranha.id
        db.session.commit()
        oferta_estranha_id = oferta_estranha.id
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c, oferta=oferta_estranha_id)

    assert resp.status_code == 302
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        assert insc is not None and insc.ativo is True


def test_inscricao_inativa_nao_e_alvo(client, app):
    """Inscrição desativada permanece intacta (ativa/motivo/data)."""
    c = _seed_cenario(roles=("pedagogico",))
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        insc.ativo = False
        insc.motivo_desativacao = "DESENTURMADO"
        db.session.commit()
    _loga(client, c["users"][0])

    resp = _post_desenturmar(client, c, oferta=c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        assert insc is not None
        assert insc.ativo is False
        assert insc.motivo_desativacao == "DESENTURMADO"


# =============================================================================
# Rota — isolamento por unidade (regra do responsável, vale p/ ADMIN)
# =============================================================================


def test_usuario_de_outra_unidade_recebe_403(client, app):
    """Pedagógico da Unidade B tenta desenturmar aluno da Unidade A: a
    unidade efetiva é a do cadastro (get_unidade_id) → mismatch → 403."""
    c = _seed_cenario(roles=("pedagogico",))
    with app.app_context():
        outra = Unidade(nome="U M2 Outra", ativo=True)
        db.session.add(outra)
        db.session.flush()
        intruso = User(
            name="Intruso", email="intruso.m2@example.com",
            role="pedagogico", first_login=False, unidade_id=outra.id,
        )
        db.session.add(intruso)
        db.session.commit()
        intruso_id = intruso.id
        outra_id = outra.id
    # Depois do commit os objetos ficam expirados; usa só ids capturados
    # dentro do contexto da app.
    _loga(client, intruso_id, unidade_id=outra_id)

    resp = _post_desenturmar(client, c, oferta=c["ofertas"][0])

    assert resp.status_code == 403
    with app.app_context():
        insc = db.session.get(Inscricao, c["inscricoes"][0])
        assert insc is not None and insc.ativo is True


def test_admin_sem_unidade_na_sessao_recebe_403(client, app):
    """ADMIN em Visão Global (sessão sem unidade_id) não desenturma —
    assert_unidade_context bloqueia unidade None até para ADMIN."""
    c = _seed_cenario(roles=("pedagogico", "admin"))
    # O admin é users[1]; pedagogico users[0] não é usado aqui.
    admin_id = c["users"][1]
    _loga(client, admin_id)  # sem unidade_id na sessão

    resp = _post_desenturmar(client, c, oferta=c["ofertas"][0])

    assert resp.status_code == 403
    with app.app_context():
        for iid in c["inscricoes"]:
            assert db.session.get(Inscricao, iid).ativo is True


# =============================================================================
# Serviço enturmar_aluno — unitários (0 / 1 / 2+ ofertas; validações)
# =============================================================================


def _seed_servico(ofertas_ativas=0, ofertas_inativas=0, turma_extra=False):
    """Semeia unidade+curso+turma com as ofertas pedidas; se ``turma_extra``,
    cria segunda turma com oferta própria. Retorna (turma, ofertas,
    oferta_extra_ou_None, aluno)."""
    unidade = Unidade(nome="U SERV", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    turma_cursos = [
        Curso(nome=f"Curso S{k + 1}", unidade_id=unidade.id, ativo=True)
        for k in range(ofertas_ativas + ofertas_inativas)
    ]
    db.session.add_all(turma_cursos)
    db.session.flush()
    curso = turma_cursos[0] if turma_cursos else Curso(
        nome="Curso Sem Oferta", unidade_id=unidade.id, ativo=True,
    )
    db.session.add(curso)
    db.session.flush()
    turma = _seed_turma(unidade, curso)
    ativas = [
        _seed_oferta(turma, turma_cursos[k], unidade, ativo=True)
        for k in range(ofertas_ativas)
    ]
    inativas = [
        _seed_oferta(turma, turma_cursos[ofertas_ativas + k], unidade,
                     ativo=False)
        for k in range(ofertas_inativas)
    ]
    aluno = Aluno(nome="Aluno S", ativo=True, unidade_id=unidade.id)
    db.session.add(aluno)
    db.session.flush()
    oferta_extra = None
    if turma_extra:
        turma2 = _seed_turma(unidade, curso, nome="Turma S2")
        oferta_extra = _seed_oferta(turma2, curso, unidade)
    db.session.commit()
    return turma, ativas + inativas, oferta_extra, aluno


def test_servico_turma_sem_oferta_recusa(app):
    with app.app_context():
        turma, _, _, aluno = _seed_servico(ofertas_ativas=0)
        with pytest.raises(ValueError) as exc:
            enturmar_aluno(aluno, turma)
        assert str(exc.value) == MSG_TURMA_SEM_OFERTA


def test_servico_uma_oferta_sem_id_auto_seleciona(app):
    with app.app_context():
        turma, ofertas, _, aluno = _seed_servico(ofertas_ativas=1)
        insc = enturmar_aluno(aluno, turma, nivel="Basico",
                              data_inicio=DATA_INI)
        db.session.flush()
        assert insc.turma_curso_id == ofertas[0].id
        assert insc.ativo is True
        assert insc.nivel == "Basico"
        assert insc.data_inicio == DATA_INI


def test_servico_duas_ofertas_sem_id_exige_escolha(app):
    with app.app_context():
        turma, _, _, aluno = _seed_servico(ofertas_ativas=2)
        with pytest.raises(ValueError) as exc:
            enturmar_aluno(aluno, turma)
        assert str(exc.value) == MSG_SELECIONE_OFERTA


def test_servico_duas_ofertas_com_id_cria_na_apontada(app):
    with app.app_context():
        turma, ofertas, _, aluno = _seed_servico(ofertas_ativas=2)
        insc = enturmar_aluno(aluno, turma, ofertas[1].id)
        db.session.flush()
        assert insc.turma_curso_id == ofertas[1].id


def test_servico_oferta_inativa_recusa(app):
    """Turma com 1 ativa + 1 inativa: escolher a inativa é oferta inválida
    (ofertas_ativas só devolve ativas), inclusive por auto-seleção."""
    with app.app_context():
        turma, ofertas, _, aluno = _seed_servico(
            ofertas_ativas=1, ofertas_inativas=1,
        )
        inativa = next(o for o in ofertas if o.ativo is False)
        with pytest.raises(ValueError) as exc:
            enturmar_aluno(aluno, turma, inativa.id)
        assert str(exc.value) == MSG_SELECIONE_OFERTA


def test_servico_oferta_de_outra_turma_recusa(app):
    with app.app_context():
        turma, _, oferta_extra, aluno = _seed_servico(
            ofertas_ativas=1, turma_extra=True,
        )
        with pytest.raises(ValueError) as exc:
            enturmar_aluno(aluno, turma, oferta_extra.id)
        assert str(exc.value) == MSG_SELECIONE_OFERTA


def test_servico_duplicata_recusa(app):
    with app.app_context():
        turma, ofertas, _, aluno = _seed_servico(ofertas_ativas=1)
        enturmar_aluno(aluno, turma, ofertas[0].id)
        db.session.flush()
        with pytest.raises(ValueError) as exc:
            enturmar_aluno(aluno, turma, ofertas[0].id)
        assert str(exc.value) == MSG_JA_ENTURMADO
        # Apenas a primeira inscrição existe para o par aluno+oferta.
        assert Inscricao.query.filter_by(
            aluno_id=aluno.id, turma_curso_id=ofertas[0].id,
        ).count() == 1

"""
Onda 4 — Fase 4 (Etapa I): excluir_turma conforme a regra do responsável.

Regra:
    - SEM histórico (nenhum Frequencia/RegistroAula/ConselhoClasse/Transferencia):
      exclusão FÍSICA de inscrições, ofertas e turma.
    - COM histórico: exclusão LÓGICA — turma, ofertas e inscrições ativas viram
      ativo=False (inscrições com data_desativacao + motivo "DESENTURMACAO");
      lançamentos/diário/conselho/transferências são preservados.
"""

from datetime import date, time

from app import create_app, db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    Frequencia,
    Inscricao,
    LogAcao,
    RegistroAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia, EtapaConselho
from config import Config

DATA_INI = date(2026, 3, 2)   # segunda-feira
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _novo_app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    return test_app


def _loga(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _seed(*, ofertas=1, com_inscrito=False, historico=None):
    """Cenário padrão: unidade U1 com pedagógico `resp`, professor, 2 cursos e
    1 turma; outra unidade U2 com `outro`. `ofertas` ofertas ativas; aluno +
    inscrição ativa quando `com_inscrito` ou quando `historico` exige aluno.

    `historico` em {None, 'frequencia', 'registro_aula', 'conselho'}.
    Retorna (app, ids)."""
    app = _novo_app()
    with app.app_context():
        db.create_all()

        u1 = Unidade(nome="U1", ativo=True)
        u2 = Unidade(nome="U2", ativo=True)
        db.session.add_all([u1, u2])
        db.session.flush()

        resp = User(
            name="Coord U1", email="coord1@example.com",
            role="pedagogico", first_login=False, unidade_id=u1.id,
        )
        outro = User(
            name="Coord U2", email="coord2@example.com",
            role="pedagogico", first_login=False, unidade_id=u2.id,
        )
        p1 = User(
            name="Prof Um", email="prof1@example.com",
            role="professor", first_login=False, unidade_id=u1.id,
        )
        db.session.add_all([resp, outro, p1])

        cA = Curso(nome="Curso A", unidade_id=u1.id, ativo=True)
        cB = Curso(nome="Curso B", unidade_id=u1.id, ativo=True)
        db.session.add_all([cA, cB])
        db.session.flush()

        turma = Turma(
            nome="T excl", unidade_id=u1.id, ativo=True, curso_id=cA.id,
            professor_id=p1.id, turno="Manhã", dias_semana="Segunda",
            hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(turma)
        db.session.flush()

        oferta_ids = []
        for i in range(ofertas):
            o = TurmaCurso(
                turma_id=turma.id, curso_id=(cA.id if i == 0 else cB.id),
                unidade_id=u1.id, ativo=True, principal=(i == 0),
                professor_id=p1.id, turno="Manhã", dias_semana="Segunda",
                hora_inicio=time(9, 0), hora_fim=time(10, 0),
                data_inicio=DATA_INI, data_fim=DATA_FIM,
            )
            db.session.add(o)
            db.session.flush()
            oferta_ids.append(o.id)

        # Aluno + inscrição ativa (necessária para o histórico com aluno).
        aluno_id = None
        precisa_aluno = com_inscrito or historico in ("frequencia", "conselho")
        if precisa_aluno and oferta_ids:
            aluno = Aluno(nome="Aluno X", unidade_id=u1.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            db.session.add(Inscricao(
                aluno_id=aluno.id, turma_id=turma.id,
                turma_curso_id=oferta_ids[0],
                data_inicio=DATA_INI, ativo=True,
            ))
            aluno_id = aluno.id

        if historico == "frequencia":
            db.session.add(Frequencia(
                aluno_id=aluno_id, turma_id=turma.id,
                turma_curso_id=oferta_ids[0], data=DATA_INI,
                conceito=ConceitoFrequencia.A, unidade_id=u1.id,
            ))
        elif historico == "registro_aula":
            db.session.add(RegistroAula(
                turma_id=turma.id, turma_curso_id=oferta_ids[0],
                data=DATA_INI, unidade_id=u1.id,
            ))
        elif historico == "conselho":
            db.session.add(ConselhoClasse(
                turma_id=turma.id, aluno_id=aluno_id,
                etapa=EtapaConselho.INICIAL, unidade_id=u1.id,
            ))

        db.session.commit()

        ids = {
            "resp": resp.id, "outro": outro.id, "p1": p1.id,
            "u1": u1.id, "u2": u2.id, "cA": cA.id, "cB": cB.id,
            "turma": turma.id, "ofertas": oferta_ids, "aluno": aluno_id,
        }
    return app, ids


def _excluir(app, user_id, turma_id):
    client = _loga(app, user_id)
    return client.post(f"/turma/excluir/{turma_id}")


# --- SEM histórico: exclusão física ----------------------------------------
def test_exclusao_fisica_1_oferta_inscritos_sem_lancamento():
    app, ids = _seed(ofertas=1, com_inscrito=True)
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302
    with app.app_context():
        assert db.session.get(Turma, ids["turma"]) is None
        assert db.session.get(TurmaCurso, ids["ofertas"][0]) is None
        assert Inscricao.query.filter_by(turma_id=ids["turma"]).count() == 0
        # O aluno NÃO é apagado — permanece disponível.
        assert db.session.get(Aluno, ids["aluno"]) is not None


# --- COM frequência: exclusão lógica, lançamentos intactos -------------------
def test_desativacao_logica_turma_com_frequencia():
    app, ids = _seed(ofertas=1, com_inscrito=True, historico="frequencia")
    with app.app_context():
        freq_antes = Frequencia.query.filter_by(turma_id=ids["turma"]).count()
        diario_antes = RegistroAula.query.filter_by(turma_id=ids["turma"]).count()

    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["ofertas"][0])
        assert turma is not None and turma.ativo is False
        assert oferta.ativo is False
        insc = Inscricao.query.filter_by(turma_id=ids["turma"]).all()
        assert all(i.ativo is False for i in insc)
        assert insc[0].data_desativacao is not None
        assert insc[0].motivo_desativacao == "TURMA_DESATIVADA"
        # Histórico preservado (mesma contagem).
        assert Frequencia.query.filter_by(turma_id=ids["turma"]).count() == freq_antes
        assert RegistroAula.query.filter_by(turma_id=ids["turma"]).count() == diario_antes


# --- Só RegistroAula (diário) conta como histórico ---------------------------
def test_registro_aula_sozinho_conta_como_historico():
    app, ids = _seed(ofertas=1, historico="registro_aula")
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302
    with app.app_context():
        # Lógica: turma permanece, mas desativada.
        turma = db.session.get(Turma, ids["turma"])
        assert turma is not None and turma.ativo is False


# --- Conselho conta como histórico ------------------------------------------
def test_conselho_conta_como_historico():
    app, ids = _seed(ofertas=1, historico="conselho")
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma is not None and turma.ativo is False
        # Conselho preservado.
        assert ConselhoClasse.query.filter_by(turma_id=ids["turma"]).count() == 1


# --- 2 ofertas, lançamento em apenas uma: histórico para a turma inteira -----
def test_duas_ofertas_lancamento_em_uma_desativa_tudo():
    app, ids = _seed(ofertas=2, com_inscrito=True, historico="frequencia")
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma is not None and turma.ativo is False
        for oid in ids["ofertas"]:
            assert db.session.get(TurmaCurso, oid).ativo is False


# --- Usuário de outra unidade não consegue excluir ---------------------------
def test_outra_unidade_bloqueada():
    app, ids = _seed(ofertas=1, com_inscrito=True)
    r = _excluir(app, ids["outro"], ids["turma"])
    assert r.status_code == 403
    with app.app_context():
        # Nada mudou: turma ainda ativa e presente.
        turma = db.session.get(Turma, ids["turma"])
        assert turma is not None and turma.ativo is True
        assert Inscricao.query.filter_by(turma_id=ids["turma"], ativo=True).count() == 1


# --- Aluno de turma desativada continua disponível para nova enturmação ------
def test_aluno_disponivel_apos_desativacao():
    app, ids = _seed(ofertas=1, com_inscrito=True, historico="frequencia")
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302

    with app.app_context():
        assert db.session.get(Aluno, ids["aluno"]).ativo is True

        # Enturma o mesmo aluno em OUTRA turma nova.
        outra = Turma(
            nome="T vaga", unidade_id=ids["u1"], ativo=True,
            curso_id=ids["cA"], data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(outra)
        db.session.flush()
        db.session.add(Inscricao(
            aluno_id=ids["aluno"], turma_id=outra.id,
            data_inicio=DATA_INI, ativo=True,
        ))
        db.session.commit()

        assert Inscricao.query.filter_by(
            aluno_id=ids["aluno"], turma_id=outra.id, ativo=True
        ).count() == 1


# --- Exclusão física grava o log de ação (LogAcao) ---------------------------
def test_exclusao_fisica_grava_log_acao():
    app, ids = _seed(ofertas=1, com_inscrito=True)
    r = _excluir(app, ids["resp"], ids["turma"])
    assert r.status_code == 302
    with app.app_context():
        logs = LogAcao.query.filter_by(acao="Exclusão de Turma").all()
        assert len(logs) == 1
        assert f"id={ids['turma']}" in (logs[0].detalhes or "")
        assert "T excl" in (logs[0].detalhes or "")

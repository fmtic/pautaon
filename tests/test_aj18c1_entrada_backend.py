
# ruff: noqa: F811
"""AJ18-C1 backend: entrada do aluno na oferta respeita data de entrada."""

from datetime import date, time, timedelta

import pytest

from _helpers import (
    dia_de_aula_ate, hoje_ref, login_as, nova_inscricao, nova_oferta,
)

from app import db
from app.models import (
    Aluno, Curso, Frequencia, LogAcao, PeriodoLetivo, Turma,
    TurmaCurso, Unidade, User,
)
from app.models.enums import ConceitoFrequencia
from app.services.estatisticas_professor import obter_estatisticas_professor
from app.services.turma_curso import datas_aula_oferta
from app.utils.frequencia import (
    datas_bloqueadas_str, situacao_datas_oferta,
)
from app.utils.logica import salvar_frequencia
from config import Config

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())
DIAS_GRADE = "Segunda, Quarta"
DATA_ENTRADA_DOIS = date(2026, 10, 12)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-aj18c1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app, *, entrada_dois=DATA_ENTRADA_DOIS):
    with app.app_context():
        un = Unidade(nome="Unidade AJ18C1", ativo=True)
        db.session.add(un)
        db.session.flush()
        prof = _usuario("Prof AJ18C1", "prof.aj18c1@x.com", "professor", un.id)
        admin = _usuario("Admin AJ18C1", "admin.aj18c1@x.com", "admin", un.id)
        db.session.add_all([prof, admin])
        db.session.flush()
        ini = HOJE - timedelta(days=40)
        fim = HOJE + timedelta(days=40)
        periodo = PeriodoLetivo(
            nome="P AJ18C1", data_inicio=ini, data_fim=fim, unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(
            nome="Turma AJ18C1", unidade_id=un.id,
            periodo_letivo_id=periodo.id, professor_id=prof.id, ativo=True,
            data_inicio=ini, data_fim=fim,
        )
        db.session.add(turma)
        db.session.flush()
        curso = Curso(nome="Curso AJ18C1", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, un.id, principal=True,
            professor_id=prof.id, dias_semana=DIAS_GRADE,
            hora_inicio=time(8), hora_fim=time(10),
        )
        aluno_um = Aluno(nome="Aluno Um", unidade_id=un.id, ativo=True)
        aluno_dois = Aluno(nome="Aluno Dois", unidade_id=un.id, ativo=True)
        db.session.add_all([aluno_um, aluno_dois])
        db.session.flush()
        nova_inscricao(aluno_um.id, turma.id, oferta.id)
        nova_inscricao(aluno_dois.id, turma.id, oferta.id,
                       data_entrada_oferta=entrada_dois)
        db.session.commit()
        return {
            "un": un.id, "prof": prof.id, "admin": admin.id,
            "turma": turma.id, "oferta": oferta.id,
            "aluno_um": aluno_um.id, "aluno_dois": aluno_dois.id,
            "alunos": [aluno_um.id, aluno_dois.id],
        }


def _datas_ate_hoje(app, ids, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        turma = db.session.get(Turma, ids["turma"])
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        return [
            d for d in datas_aula_oferta(oferta, blocked=blocked) if d <= HOJE
        ]


def _iso(d):
    return d.strftime("%Y-%m-%d")


def _lancar_direto(app, ids, oferta_id, data_alvo, *, alunos=None):
    with app.app_context():
        for aluno_id in (alunos or ids["alunos"]):
            db.session.add(Frequencia(
                aluno_id=aluno_id, turma_id=ids["turma"],
                turma_curso_id=oferta_id, data=data_alvo,
                conceito=ConceitoFrequencia.A, unidade_id=ids["un"],
            ))
        db.session.commit()


def _situacao(app, ids, oferta_id):
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, oferta_id)
        return situacao_datas_oferta(turma, oferta)


def _datas_ate_hoje(app, ids, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        turma = db.session.get(Turma, ids["turma"])
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        return [
            d for d in datas_aula_oferta(oferta, blocked=blocked) if d <= HOJE
        ]


def _iso(d):
    return d.strftime("%Y-%m-%d")


def _lancar_direto(app, ids, oferta_id, data_alvo, *, alunos=None):
    with app.app_context():
        for aluno_id in (alunos or ids["alunos"]):
            db.session.add(Frequencia(
                aluno_id=aluno_id, turma_id=ids["turma"],
                turma_curso_id=oferta_id, data=data_alvo,
                conceito=ConceitoFrequencia.A, unidade_id=ids["un"],
            ))
        db.session.commit()


def _situacao(app, ids, oferta_id):
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, oferta_id)
        return situacao_datas_oferta(turma, oferta)

# 1) POST /frequencia
def test_post_ignora_aluno_entrada_posterior_salva_demais(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < DATA_ENTRADA_DOIS)
    data_apos = next(d for d in datas if d >= DATA_ENTRADA_DOIS)

    login_as(client, ids["prof"], ids["un"])

    dados = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": _iso(data_antes),
    }
    dados["aluno_" + str(ids["aluno_um"])] = "A"
    dados["aluno_" + str(ids["aluno_dois"])] = "A"
    resposta = client.post("/frequencia", data=dados, follow_redirects=False)
    assert resposta.status_code == 302

    with app.app_context():
        f_um = Frequencia.query.filter_by(
            aluno_id=ids["aluno_um"], data=data_antes,
            turma_curso_id=ids["oferta"]).first()
        f_dois = Frequencia.query.filter_by(
            aluno_id=ids["aluno_dois"], data=data_antes,
            turma_curso_id=ids["oferta"]).first()
        assert f_um is not None and f_um.conceito == "A"
        assert f_dois is None

        log = LogAcao.query.filter_by(
            acao="Lançamento de frequência ignorado (entrada futura)").first()
        assert log is not None
        assert "aluno_id=" + str(ids["aluno_dois"]) in log.detalhes
        assert "oferta_id=" + str(ids["oferta"]) in log.detalhes
        assert "turma_id=" + str(ids["turma"]) in log.detalhes
        assert "data=" + _iso(data_antes) in log.detalhes
        assert "conceito_recebido=A" in log.detalhes
        assert "entrada=" + _iso(DATA_ENTRADA_DOIS) in log.detalhes

    dados2 = {
        "turma": str(ids["turma"]),
        "turma_curso": str(ids["oferta"]),
        "data": _iso(data_apos),
    }
    for aid in ids["alunos"]:
        dados2["aluno_" + str(aid)] = "A"
    resposta2 = client.post("/frequencia", data=dados2, follow_redirects=False)
    assert resposta2.status_code == 302

    with app.app_context():
        f_um2 = Frequencia.query.filter_by(
            aluno_id=ids["aluno_um"], data=data_apos,
            turma_curso_id=ids["oferta"]).first()
        f_dois2 = Frequencia.query.filter_by(
            aluno_id=ids["aluno_dois"], data=data_apos,
            turma_curso_id=ids["oferta"]).first()
        assert f_um2 is not None and f_um2.conceito == "A"
        assert f_dois2 is not None and f_dois2.conceito == "A"

# 2) Defesa em salvar_frequencia (chamada direta)
def test_salvar_frequencia_defesa_entrada_posterior(app, client):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < DATA_ENTRADA_DOIS)

    _lancar_direto(app, ids, ids["oferta"], data_antes,
                   alunos=[ids["aluno_um"]])

    with app.test_request_context():
        user = User.query.get(ids["prof"])
        from flask_login import login_user
        login_user(user)
        form = {
            "turma": str(ids["turma"]),
            "turma_curso": str(ids["oferta"]),
            "data": _iso(data_antes),
            "aluno_" + str(ids["aluno_dois"]): "A",
        }
        turma_id, data = salvar_frequencia(form)
        assert turma_id == ids["turma"]
        assert data == _iso(data_antes)
        f_dois = Frequencia.query.filter_by(
            aluno_id=ids["aluno_dois"], data=data_antes,
            turma_curso_id=ids["oferta"]).first()
        assert f_dois is None

    with app.app_context():
        f_um = Frequencia.query.filter_by(
            aluno_id=ids["aluno_um"], data=data_antes,
            turma_curso_id=ids["oferta"]).first()
        assert f_um is not None
        assert f_um.conceito == "A"


# 3) situacao_datas_oferta
def test_situacao_datas_aluno_entrada_tardia(app):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    datas_antes = [d for d in datas if d < DATA_ENTRADA_DOIS]
    datas_apos = [d for d in datas if d >= DATA_ENTRADA_DOIS]
    assert datas_antes and datas_apos

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["pendentes"] == len(datas)
    assert situacao["lancadas"] == 0
    assert situacao["total_ate_hoje"] == len(datas)
    assert situacao["proxima_pendente"] == _iso(datas[0])
    for d in datas:
        assert situacao["status"][_iso(d)] == "pendente"

    for d in datas:
        _lancar_direto(app, ids, ids["oferta"], d,
                       alunos=[ids["aluno_um"]])
    situacao = _situacao(app, ids, ids["oferta"])

    for d in datas_antes:
        assert situacao["status"][_iso(d)] == "lancada", _iso(d)
    for d in datas_apos:
        assert situacao["status"][_iso(d)] == "pendente", _iso(d)
    assert situacao["lancadas"] == len(datas_antes)
    assert situacao["pendentes"] == len(datas_apos)
    assert situacao["proxima_pendente"] == _iso(datas_apos[0])

    for d in datas_apos:
        _lancar_direto(app, ids, ids["oferta"], d,
                       alunos=[ids["aluno_dois"]])
    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["pendentes"] == 0
    assert situacao["lancadas"] == len(datas)
    assert situacao["proxima_pendente"] is None
    for d in datas:
        assert situacao["status"][_iso(d)] == "lancada", _iso(d)


def test_proxima_pendente_nao_aponta_nao_entrado(app):
    ids = _seed(app, entrada_dois=HOJE + timedelta(days=5))
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    assert datas

    for d in datas:
        _lancar_direto(app, ids, ids["oferta"], d,
                       alunos=[ids["aluno_um"]])

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["pendentes"] == 0
    assert situacao["lancadas"] == len(datas)
    assert situacao["proxima_pendente"] is None
    for d in datas:
        assert situacao["status"][_iso(d)] == "lancada", _iso(d)


def test_data_sem_aluno_esperado_nao_eh_pendente(app):
    entrada_tardia = HOJE + timedelta(days=5)
    ids = _seed(app, entrada_dois=entrada_tardia)
    from app.models import Inscricao
    with app.app_context():
        insc_um = db.session.get(Inscricao,
                                 db.session.query(Inscricao.id).filter_by(
                                     aluno_id=ids["aluno_um"],
                                     turma_curso_id=ids["oferta"],
                                     ativo=True).one()[0])
        insc_um.data_entrada_oferta = entrada_tardia
        db.session.commit()

    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    assert datas

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["lancadas"] == 0
    assert situacao["pendentes"] == 0
    assert situacao["total_ate_hoje"] == 0
    assert situacao["proxima_pendente"] is None
    assert situacao["status"] == {}


# 6) estatisticas_professor
def test_estatisticas_professor_cobertura_entrada_tardia(app):
    ids = _seed(app, entrada_dois=DATA_ENTRADA_DOIS)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    datas_apos = [d for d in datas if d >= DATA_ENTRADA_DOIS]
    assert datas_apos

    for d in datas:
        _lancar_direto(app, ids, ids["oferta"], d,
                       alunos=[ids["aluno_um"]])

    stats = obter_estatisticas_professor(
        ids["prof"], turma_id=ids["turma"],
        turma_curso_id=ids["oferta"],
    )
    cob = stats["cobertura_pauta"]
    assert cob["aulas_esperadas"] == len(datas)
    datas_antes = [d for d in datas if d < DATA_ENTRADA_DOIS]
    assert cob["aulas_lancadas"] == len(datas_antes)
    assert cob["aulas_pendentes"] == len(datas_apos)
    assert cob["taxa_cumprimento_pauta"] == round(
        len(datas_antes) / len(datas) * 100, 1)


# 7) Regressao
def test_regressao_sem_data_entrada_igual_antes(app):
    ids = _seed(app, entrada_dois=None)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    assert len(datas) >= 4

    _lancar_direto(app, ids, ids["oferta"], datas[0])

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["status"][_iso(datas[0])] == "lancada"
    assert situacao["status"][_iso(datas[1])] == "pendente"
    assert situacao["lancadas"] == 1
    assert situacao["total_ate_hoje"] == len(datas)
    assert situacao["pendentes"] == len(datas) - 1
    assert situacao["proxima_pendente"] == _iso(datas[1])


# 8) Re-enturmao
def test_re_enturmatacao_usa_inscricao_ativa(app):
    ids = _seed(app, entrada_dois=None)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < date(2026, 10, 12))
    assert data_antes

    from app.models import Inscricao
    with app.app_context():
        antiga = Inscricao(
            aluno_id=ids["aluno_dois"], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], ativo=False,
            data_entrada_oferta=None,
            data_desativacao=HOJE,
            motivo_desativacao="re-enturmao",
        )
        db.session.add(antiga)
        db.session.flush()
        antiga_id = antiga.id

        nova = Inscricao(
            aluno_id=ids["aluno_dois"], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], ativo=True,
            data_entrada_oferta=date(2026, 10, 12),
        )
        db.session.add(nova)
        db.session.commit()

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["status"][_iso(data_antes)] == "pendente"

    _lancar_direto(app, ids, ids["oferta"], data_antes,
                   alunos=[ids["aluno_um"]])
    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["status"][_iso(data_antes)] == "lancada"

    with app.app_context():
        db.session.delete(db.session.get(Inscricao, antiga_id))
        db.session.commit()

# 8) Re-enturmao
def test_re_enturmatacao_usa_inscricao_ativa(app):
    ids = _seed(app, entrada_dois=None)
    datas = _datas_ate_hoje(app, ids, ids["oferta"])
    data_antes = next(d for d in datas if d < date(2026, 10, 12))
    assert data_antes

    from app.models import Inscricao
    with app.app_context():
        # Remove a inscricao antiga ativa do seed e criar nova com entrada tardia.
        antiga = db.session.query(Inscricao).filter_by(
            aluno_id=ids["aluno_dois"], turma_curso_id=ids["oferta"],
            ativo=True).one()
        antiga.ativo = False
        antiga.data_desativacao = HOJE
        antiga.motivo_desativacao = "re-enturmao"
        db.session.add(antiga)

        # Nova inscricao ativa com entrada tardia.
        nova = Inscricao(
            aluno_id=ids["aluno_dois"], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], ativo=True,
            data_entrada_oferta=date(2026, 10, 12),
        )
        db.session.add(nova)
        db.session.commit()

    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["status"][_iso(data_antes)] == "pendente"

    _lancar_direto(app, ids, ids["oferta"], data_antes,
                   alunos=[ids["aluno_um"]])
    situacao = _situacao(app, ids, ids["oferta"])
    assert situacao["status"][_iso(data_antes)] == "lancada"

"""AJ18-E — correção da data de entrada de um aluno já enturmado.

Cobre: NULL → data remove as pendências por data (situacao/contador do
dashboard) e desabilita o aluno nas datas anteriores no lançamento; voltar
para "desde o início" restaura; janela recusada; oferta não iniciada só aceita
NULL; no-op sem log; frequência anterior exige confirmação e é preservada;
perfis/unidade; 404 de inscrição/oferta/turma; CSRF; log com anterior/nova;
atomicidade; botão visível só para os perfis certos; sem N+1 na lista.
"""

from datetime import time, timedelta

import pytest
from sqlalchemy import event

from _helpers import dia_de_aula_ate, hoje_ref, login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    LogAcao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from app.services.turma_curso import datas_aula_oferta
from app.utils.frequencia import contar_pendencias_frequencia, situacao_datas_oferta

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())
INI = HOJE - timedelta(days=40)
FIM = HOJE + timedelta(days=40)
DIAS = "Segunda, Quarta"
ACAO = "Alteração da data de entrada na oferta"


def _usuario(nome, email, role, unidade_id):
    return User(
        name=nome,
        email=email,
        role=role,
        first_login=False,
        unidade_id=unidade_id,
    )


def _seed(app, *, entrada=None, oferta_inicio=None, oferta_fim=None,
          segunda_oferta=False):
    """Semente mínima: unidade A (+B), perfis, turma/oferta e um aluno."""
    with app.app_context():
        un = Unidade(nome="Unidade AJ18E", ativo=True)
        un_b = Unidade(nome="Unidade B AJ18E", ativo=True)
        db.session.add_all([un, un_b])
        db.session.flush()

        admin = _usuario("Admin AJ18E", "admin.aj18e@x.com", "admin", un.id)
        ped = _usuario("Ped AJ18E", "ped.aj18e@x.com", "pedagogico", un.id)
        sec = _usuario("Sec AJ18E", "sec.aj18e@x.com", "secretaria", un.id)
        sec_b = _usuario("Sec B AJ18E", "secb.aj18e@x.com", "secretaria", un_b.id)
        ger = _usuario("Ger AJ18E", "ger.aj18e@x.com", "gerencia", un.id)
        prof = _usuario("Prof AJ18E", "prof.aj18e@x.com", "professor", un.id)
        db.session.add_all([admin, ped, sec, sec_b, ger, prof])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P AJ18E", data_inicio=INI, data_fim=FIM,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma AJ18E", unidade_id=un.id, periodo_letivo_id=periodo.id,
            professor_id=prof.id, ativo=True, data_inicio=INI, data_fim=FIM,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso AJ18E", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        oferta = nova_oferta(
            turma.id, curso.id, un.id, principal=True, professor_id=prof.id,
            dias_semana=DIAS, hora_inicio=time(8), hora_fim=time(10),
            data_inicio=oferta_inicio, data_fim=oferta_fim,
        )

        if segunda_oferta:
            curso2 = Curso(nome="Curso 2 AJ18E", unidade_id=un.id, ativo=True)
            db.session.add(curso2)
            db.session.flush()
            nova_oferta(
                turma.id, curso2.id, un.id, principal=False, professor_id=prof.id,
                dias_semana=DIAS, hora_inicio=time(8), hora_fim=time(10),
            )

        aluno = Aluno(nome="Aluno AJ18E", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        insc = nova_inscricao(
            aluno.id, turma.id, oferta.id, data_entrada_oferta=entrada,
        )
        db.session.commit()

        return {
            "un": un.id, "un_b": un_b.id,
            "admin": admin.id, "ped": ped.id, "sec": sec.id,
            "sec_b": sec_b.id, "ger": ger.id, "prof": prof.id,
            "turma": turma.id, "oferta": oferta.id,
            "aluno": aluno.id, "insc": insc.id,
        }


def _datas(app, ids, *, ate_hoje=True):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        datas = datas_aula_oferta(oferta)
        return [d for d in datas if d <= HOJE] if ate_hoje else datas


def _url(ids, *, turma=None, oferta=None, insc=None):
    return (
        f"/turma/{turma or ids['turma']}/oferta/{oferta or ids['oferta']}"
        f"/inscricao/{insc or ids['insc']}/entrada"
    )


def _lancar(app, ids, datas, *, aluno=None):
    with app.app_context():
        for data_alvo in datas:
            db.session.add(Frequencia(
                aluno_id=aluno or ids["aluno"], turma_id=ids["turma"],
                turma_curso_id=ids["oferta"], data=data_alvo,
                conceito=ConceitoFrequencia.A, unidade_id=ids["un"],
            ))
        db.session.commit()


def _entrada(app, ids):
    with app.app_context():
        return db.session.get(Inscricao, ids["insc"]).data_entrada_oferta


def _logs(app):
    with app.app_context():
        return LogAcao.query.filter_by(acao=ACAO).all()


def _iso(valor):
    return valor.isoformat() if valor is not None else None


# ---------------------------------------------------------------------------
# Efeito nas pendências e no lançamento
# ---------------------------------------------------------------------------

def test_null_para_data_remove_pendencias_e_desabilita_lancamento(app, client):
    ids = _seed(app, segunda_oferta=True)
    datas = _datas(app, ids)
    assert len(datas) >= 4
    entrada = datas[len(datas) // 2]
    datas_antes = [d for d in datas if d < entrada]
    assert datas_antes

    # Só há lançamento da data de entrada em diante: as datas anteriores ficam
    # pendentes enquanto o aluno é "esperado" nelas (entrada NULL).
    _lancar(app, ids, [d for d in datas if d >= entrada])

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        antes_situacao = situacao_datas_oferta(turma, oferta)
        antes_contador = contar_pendencias_frequencia([turma])
    assert antes_situacao["pendentes"] == len(datas_antes)
    assert antes_contador == len(datas_antes)

    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(_url(ids), data={"escolha": entrada.isoformat()})
    assert resposta.status_code == 302

    assert _entrada(app, ids) == entrada
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        depois_situacao = situacao_datas_oferta(turma, oferta)
        depois_contador = contar_pendencias_frequencia([turma])
    assert depois_situacao["pendentes"] == 0
    assert depois_contador == 0
    for dia in datas_antes:
        assert depois_situacao["status"].get(dia.isoformat()) != "pendente"

    # No lançamento, as datas anteriores à entrada desabilitam o aluno.
    body = client.get(
        f"/frequencia?turma_id={ids['turma']}&turma_curso={ids['oferta']}"
        f"&data={datas_antes[0].isoformat()}"
    ).get_data(as_text=True)
    assert f"Entrou em {entrada.strftime('%d/%m')}" in body
    import re
    assert re.search(
        rf'id="aluno_{ids["aluno"]}_A"[^>]*disabled', body
    ), "aluno deveria estar desabilitado na data anterior à entrada"

    with app.app_context():
        log = LogAcao.query.filter_by(acao=ACAO).one()
        assert f"aluno_id={ids['aluno']}" in log.detalhes
        assert f"oferta_id={ids['oferta']}" in log.detalhes
        assert "entrada_anterior=desde o início" in log.detalhes
        assert f"entrada_nova={entrada.isoformat()}" in log.detalhes


def test_voltar_para_inicio_restaura_pendencias(app, client):
    entrada = HOJE - timedelta(days=5)
    ids = _seed(app, entrada=entrada)
    datas = _datas(app, ids)
    datas_antes = [d for d in datas if d < entrada]
    assert datas_antes
    _lancar(app, ids, [d for d in datas if d >= entrada])

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        assert situacao_datas_oferta(turma, oferta)["pendentes"] == 0

    login_as(client, ids["ped"], ids["un"])
    resposta = client.post(_url(ids), data={"escolha": "inicio"})
    assert resposta.status_code == 302
    assert _entrada(app, ids) is None

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        situacao = situacao_datas_oferta(turma, oferta)
    for dia in datas_antes:
        assert situacao["status"][dia.isoformat()] == "pendente"
    assert situacao["pendentes"] >= len(datas_antes)


# ---------------------------------------------------------------------------
# Validações e no-op
# ---------------------------------------------------------------------------

def test_data_fora_da_vigencia_recusada(app, client):
    ids = _seed(app)
    login_as(client, ids["sec"], ids["un"])
    resposta = client.post(
        _url(ids),
        data={"escolha": (INI - timedelta(days=1)).isoformat()},
        follow_redirects=True,
    )
    assert resposta.status_code == 200
    body = resposta.get_data(as_text=True)
    assert "deve estar entre" in body
    assert _entrada(app, ids) is None
    assert _logs(app) == []


def test_oferta_nao_iniciada_recusa_data_especifica(app, client):
    inicio_futuro = HOJE + timedelta(days=10)
    ids = _seed(
        app, entrada=None, oferta_inicio=inicio_futuro,
        oferta_fim=inicio_futuro + timedelta(days=60),
    )
    login_as(client, ids["admin"], ids["un"])
    for escolha in ("hoje", inicio_futuro.isoformat()):
        resposta = client.post(
            _url(ids), data={"escolha": escolha}, follow_redirects=True
        )
        assert resposta.status_code == 200
        assert "ainda não iniciou" in resposta.get_data(as_text=True)
        assert _entrada(app, ids) is None
    assert _logs(app) == []


def test_noop_sem_log(app, client):
    ids = _seed(app, entrada=None)
    login_as(client, ids["sec"], ids["un"])
    resposta = client.post(_url(ids), data={"escolha": "inicio"})
    assert resposta.status_code == 302
    assert _entrada(app, ids) is None
    assert _logs(app) == []


# ---------------------------------------------------------------------------
# Frequências anteriores: confirmação e preservação
# ---------------------------------------------------------------------------

def test_frequencia_anterior_exige_confirmacao_e_preserva_linhas(app, client):
    datas = None
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    datas = _datas(app, ids)
    datas_antes = [d for d in datas if d < HOJE]
    assert len(datas_antes) >= 2
    _lancar(app, ids, datas_antes[:2])

    nova = datas_antes[-1]
    login_as(client, ids["ped"], ids["un"])

    recusa = client.post(_url(ids), data={"escolha": nova.isoformat()})
    assert recusa.status_code == 302
    assert "entrada_pendentes=2" in recusa.headers["Location"]
    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    assert _logs(app) == []
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 2

    # A reabertura mostra a contagem e a confirmação explícita.
    body = client.get(recusa.headers["Location"]).get_data(as_text=True)
    assert "frequência(s)" in body
    assert 'name="confirmar"' in body

    confirma = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "confirmar": "1"}
    )
    assert confirma.status_code == 302
    assert _entrada(app, ids) == nova
    with app.app_context():
        linhas = Frequencia.query.filter_by(aluno_id=ids["aluno"]).all()
        assert len(linhas) == 2
        assert {linha.data for linha in linhas} == set(datas_antes[:2])
        assert all(linha.conceito == "A" for linha in linhas)
    assert len(_logs(app)) == 1


def test_mover_data_para_tras_nao_exige_confirmacao(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=2))
    datas = _datas(app, ids)
    datas_antes = [d for d in datas if d < HOJE - timedelta(days=2)]
    assert len(datas_antes) >= 3
    _lancar(app, ids, datas_antes[:2])

    nova = datas_antes[-1]  # ainda depois das linhas, mas antes da entrada atual
    login_as(client, ids["sec"], ids["un"])
    resposta = client.post(_url(ids), data={"escolha": nova.isoformat()})
    assert resposta.status_code == 302
    assert _entrada(app, ids) == nova
    assert len(_logs(app)) == 1
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 2


# ---------------------------------------------------------------------------
# Perfis, unidade, 404 e CSRF
# ---------------------------------------------------------------------------

def test_professor_recebe_403(app, client):
    ids = _seed(app)
    login_as(client, ids["prof"], ids["un"])
    assert client.post(_url(ids), data={"escolha": "hoje"}).status_code == 403


def test_outra_unidade_bloqueada(app, client):
    ids = _seed(app)
    login_as(client, ids["sec_b"], ids["un_b"])
    assert client.post(_url(ids), data={"escolha": "hoje"}).status_code == 403


def test_inscricao_inativa_404(app, client):
    ids = _seed(app)
    with app.app_context():
        insc = db.session.get(Inscricao, ids["insc"])
        insc.ativo = False
        db.session.commit()
    login_as(client, ids["admin"], ids["un"])
    assert client.post(_url(ids), data={"escolha": "hoje"}).status_code == 404


def test_oferta_ou_turma_errada_404(app, client):
    ids = _seed(app)
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        curso2 = Curso(nome="Curso 3 AJ18E", unidade_id=ids["un"], ativo=True)
        db.session.add(curso2)
        db.session.flush()
        outra = nova_oferta(
            turma.id, curso2.id, ids["un"], principal=False,
            professor_id=ids["prof"],
        )
        outra_oferta_id = outra.id
        outra_turma = Turma(
            nome="Turma Alheia AJ18E", unidade_id=ids["un"],
            professor_id=ids["prof"], ativo=True,
            data_inicio=INI, data_fim=FIM,
        )
        db.session.add(outra_turma)
        db.session.flush()
        outra_turma_id = outra_turma.id
        db.session.commit()

    login_as(client, ids["admin"], ids["un"])
    assert client.post(
        _url(ids, oferta=outra_oferta_id), data={"escolha": "hoje"}
    ).status_code == 404
    assert client.post(
        _url(ids, turma=outra_turma_id), data={"escolha": "hoje"}
    ).status_code == 404


def test_csrf_obrigatorio(app, client):
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])
    app.config["WTF_CSRF_ENABLED"] = True
    resposta = client.post(_url(ids), data={"escolha": "hoje"})
    assert resposta.status_code == 400
    assert _entrada(app, ids) is None


# ---------------------------------------------------------------------------
# Atomicidade
# ---------------------------------------------------------------------------

def test_atomicidade_erro_no_log_nao_grava_data(app, client, monkeypatch):
    ids = _seed(app, entrada=HOJE - timedelta(days=10))

    class LogQuebrado:
        def __init__(self, **kwargs):
            raise RuntimeError("falha proposital no log")

    monkeypatch.setattr("app.models.LogAcao", LogQuebrado)
    login_as(client, ids["admin"], ids["un"])
    with pytest.raises(RuntimeError):
        client.post(_url(ids), data={"escolha": "hoje"})
    assert _entrada(app, ids) == HOJE - timedelta(days=10)


# ---------------------------------------------------------------------------
# Tela
# ---------------------------------------------------------------------------

def test_botao_visivel_so_para_os_perfis_certos(app, client):
    ids = _seed(app)
    url = f"/turma/{ids['turma']}?oferta_sel={ids['oferta']}"

    for perfil in ("admin", "ped", "sec"):
        login_as(client, ids[perfil], ids["un"])
        body = client.get(url).get_data(as_text=True)
        assert 'data-bs-target="#modalEntrada"' in body, perfil

    for perfil in ("prof", "ger"):
        login_as(client, ids[perfil], ids["un"])
        body = client.get(url).get_data(as_text=True)
        assert 'data-bs-target="#modalEntrada"' not in body, perfil


def test_botao_ausente_com_oferta_nao_iniciada(app, client):
    inicio_futuro = HOJE + timedelta(days=10)
    ids = _seed(
        app, oferta_inicio=inicio_futuro,
        oferta_fim=inicio_futuro + timedelta(days=60),
    )
    login_as(client, ids["admin"], ids["un"])
    body = client.get(
        f"/turma/{ids['turma']}?oferta_sel={ids['oferta']}"
    ).get_data(as_text=True)
    assert 'data-bs-target="#modalEntrada"' not in body


def test_lista_sem_n_mais_1(app, client):
    ids = _seed(app)
    url = f"/turma/{ids['turma']}?oferta_sel={ids['oferta']}"
    login_as(client, ids["admin"], ids["un"])

    def _contar_consultas():
        consultas = []

        def _registrar(conn, cursor, statement, parameters, context, many):
            consultas.append(statement)

        engine = db.engine
        event.listen(engine, "before_cursor_execute", _registrar)
        try:
            assert client.get(url).status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", _registrar)
        return len(consultas)

    uma = _contar_consultas()
    with app.app_context():
        for numero in range(4):
            aluno = Aluno(
                nome=f"Aluno extra {numero}", unidade_id=ids["un"], ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(
                aluno.id, ids["turma"], ids["oferta"],
                data_entrada_oferta=HOJE - timedelta(days=1),
            )
        db.session.commit()

    cinco = _contar_consultas()
    assert cinco == uma, (uma, cinco)

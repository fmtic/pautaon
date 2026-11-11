"""AJ18-F — remover as frequências anteriores ao avançar a data de entrada.

Estende a edição da entrada (AJ18-E) com a escolha explícita entre MANTER e
REMOVER as frequências já gravadas antes da nova data. Cobre:

    - escopo da remoção: só o aluno, a oferta e as datas < nova;
    - regressão do "manter" (nada é apagado);
    - LogAcao com contagem e intervalo (e "mantidas N" no outro caminho);
    - atomicidade: falha no log desfaz data e remoção;
    - perfis (admin/pedagógico/secretaria OK; professor/gerência/outra
      unidade 403);
    - ``acao_anteriores`` inválida → 400;
    - recuar/igualar a data: sem pergunta e sem remoção;
    - pauta, pendências e agregados recalculados a partir das linhas;
    - legado com ``turma_curso_id`` NULL na oferta única (regra D2);
    - tela de confirmação com contagem, intervalo e dois botões.

Nomes e dados são sintéticos. Sem migration.
"""

from datetime import timedelta

import pytest

from _helpers import dia_de_aula_ate, hoje_ref, login_as, nova_inscricao, nova_oferta
from test_aj18e_editar_entrada import (
    _datas,
    _entrada,
    _lancar,
    _logs,
    _seed,
    _url,
)

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Turma,
    TurmaCurso,
)
from app.models.enums import ConceitoFrequencia
from app.utils.frequencia import contar_pendencias_frequencia, situacao_datas_oferta

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())


# ---------------------------------------------------------------------------
# Helpers locais
# ---------------------------------------------------------------------------

def _oferta_secundaria(app, ids):
    """Cria uma segunda oferta ativa na mesma turma (tira o legado do escopo)."""
    with app.app_context():
        curso = Curso(nome="Curso B AJ18F", unidade_id=ids["un"], ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = nova_oferta(
            ids["turma"], curso.id, ids["un"], principal=False,
            professor_id=ids["prof"],
        )
        db.session.commit()
        return oferta.id


def _novo_aluno(app, ids, nome, oferta_id, *, entrada=None):
    with app.app_context():
        aluno = Aluno(nome=nome, unidade_id=ids["un"], ativo=True)
        db.session.add(aluno)
        db.session.flush()
        insc = nova_inscricao(
            aluno.id, ids["turma"], oferta_id, data_entrada_oferta=entrada,
        )
        db.session.commit()
        return aluno.id, insc.id


def _add_freqs(app, ids, registros):
    """``registros`` = [(aluno_id, oferta_id|None, data, conceito), ...]."""
    with app.app_context():
        for aluno_id, oferta_id, data_alvo, conceito in registros:
            db.session.add(Frequencia(
                aluno_id=aluno_id,
                turma_id=ids["turma"],
                turma_curso_id=oferta_id,
                data=data_alvo,
                conceito=conceito,
                unidade_id=ids["un"],
            ))
        db.session.commit()


def _linhas(app, ids, *, aluno_id=None):
    with app.app_context():
        query = Frequencia.query.filter_by(turma_id=ids["turma"])
        if aluno_id is not None:
            query = query.filter_by(aluno_id=aluno_id)
        return [
            (f.aluno_id, f.turma_curso_id, f.data)
            for f in query.order_by(Frequencia.id).all()
        ]


def _chave(linhas):
    return {(aluno, oferta, data) for aluno, oferta, data in linhas}


def _escolha_mover_para(app, ids, indice=-1):
    datas = _datas(app, ids)
    return datas[indice], [d for d in datas if d < datas[indice]]


# ---------------------------------------------------------------------------
# Escopo da remoção
# ---------------------------------------------------------------------------

def test_remove_so_linhas_anteriores_da_oferta_do_aluno(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    assert len(antes) >= 2

    oferta_b = _oferta_secundaria(app, ids)
    aluno_b, _ = _novo_aluno(app, ids, "Aluno B AJ18F", ids["oferta"])
    aluno_c, _ = _novo_aluno(app, ids, "Aluno C AJ18F", oferta_b)
    aluno_d, _ = _novo_aluno(app, ids, "Aluno D AJ18F", oferta_b)
    depois_de_nova = nova + timedelta(days=2)

    _add_freqs(app, ids, [
        # Alvo: aluno da inscrição, oferta dela, datas < nova → removidas.
        (ids["aluno"], ids["oferta"], antes[0], ConceitoFrequencia.A),
        (ids["aluno"], ids["oferta"], antes[1], ConceitoFrequencia.F),
        # Mesmo aluno/oferta, datas >= nova → preservadas.
        (ids["aluno"], ids["oferta"], nova, ConceitoFrequencia.A),
        (ids["aluno"], ids["oferta"], depois_de_nova, ConceitoFrequencia.A),
        # Outro aluno na MESMA oferta → preservado.
        (aluno_b, ids["oferta"], antes[0], ConceitoFrequencia.A),
        # Mesmo aluno em OUTRA oferta → preservado.
        (ids["aluno"], oferta_b, antes[0], ConceitoFrequencia.A),
        # Outro aluno em outra oferta → preservado.
        (aluno_c, oferta_b, antes[0], ConceitoFrequencia.A),
        (aluno_d, oferta_b, antes[1], ConceitoFrequencia.A),
    ])

    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "remover"}
    )
    assert resposta.status_code == 302
    assert _entrada(app, ids) == nova

    restantes = _chave(_linhas(app, ids))
    assert (ids["aluno"], ids["oferta"], antes[0]) not in restantes
    assert (ids["aluno"], ids["oferta"], antes[1]) not in restantes
    assert (ids["aluno"], ids["oferta"], nova) in restantes
    assert (ids["aluno"], ids["oferta"], depois_de_nova) in restantes
    assert (aluno_b, ids["oferta"], antes[0]) in restantes
    assert (ids["aluno"], oferta_b, antes[0]) in restantes
    assert (aluno_c, oferta_b, antes[0]) in restantes
    assert (aluno_d, oferta_b, antes[1]) in restantes
    assert len(restantes) == 6

    log = _logs(app)[0]
    assert log.detalhes.count("removidas") == 1
    assert "removidas 2 frequências anteriores a" in log.detalhes
    assert nova.strftime("%d/%m/%Y") in log.detalhes
    assert (
        f"(de {antes[0].strftime('%d/%m/%Y')} a {antes[1].strftime('%d/%m/%Y')})"
        in log.detalhes
    )


def test_remove_legado_null_quando_oferta_e_a_unica_ativa(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    assert len(antes) >= 1

    _add_freqs(app, ids, [
        # Legado (turma_curso_id NULL) antes da nova entrada → removido (D2).
        (ids["aluno"], None, antes[0], ConceitoFrequencia.A),
        # Legado depois da nova entrada → preservado.
        (ids["aluno"], None, nova, ConceitoFrequencia.A),
        # Linha da oferta antes da nova entrada → removida.
        (ids["aluno"], ids["oferta"], antes[-1], ConceitoFrequencia.A),
        # Linha da oferta na nova data → preservada.
        (ids["aluno"], ids["oferta"], nova, ConceitoFrequencia.A),
    ])

    login_as(client, ids["sec"], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "remover"}
    )
    assert resposta.status_code == 302

    restantes = _chave(_linhas(app, ids))
    assert (ids["aluno"], None, antes[0]) not in restantes
    assert (ids["aluno"], ids["oferta"], antes[-1]) not in restantes
    assert (ids["aluno"], None, nova) in restantes
    assert (ids["aluno"], ids["oferta"], nova) in restantes
    assert len(restantes) == 2


# ---------------------------------------------------------------------------
# Manter / confirmação (regressão AJ18-E)
# ---------------------------------------------------------------------------

def test_manter_preserva_tudo_e_loga_mantidas(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:2])

    login_as(client, ids["ped"], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "manter"}
    )
    assert resposta.status_code == 302
    assert _entrada(app, ids) == nova
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 2

    detalhes = _logs(app)[0].detalhes
    assert "mantidas 2" in detalhes
    assert "removidas" not in detalhes


def test_sem_acao_reabre_confirmacao_com_dois_botoes(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:2])

    login_as(client, ids["admin"], ids["un"])
    recusa = client.post(_url(ids), data={"escolha": nova.isoformat()})
    assert recusa.status_code == 302
    location = recusa.headers["Location"]
    assert "entrada_pendentes=2" in location
    assert "entrada_pendentes_ini=" in location
    assert "entrada_pendentes_fim=" in location
    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    assert _logs(app) == []
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 2

    body = client.get(location).get_data(as_text=True)
    assert 'id="entradaPendentesAviso"' in body
    assert "<strong>2</strong>" in body
    assert antes[0].strftime("%d/%m/%Y") in body
    assert antes[1].strftime("%d/%m/%Y") in body
    assert 'name="acao_anteriores" value="manter"' in body
    assert 'name="acao_anteriores" value="remover"' in body
    assert "Remover é irreversível" in body
    assert 'name="confirmar"' not in body


# ---------------------------------------------------------------------------
# Atomicidade
# ---------------------------------------------------------------------------

def test_atomicidade_falha_no_log_desfaz_remocao_e_data(app, client, monkeypatch):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:2])
    antes_das_linhas = _chave(_linhas(app, ids))

    class LogQuebrado:
        def __init__(self, **kwargs):
            raise RuntimeError("falha proposital no log")

    monkeypatch.setattr("app.models.LogAcao", LogQuebrado)
    login_as(client, ids["admin"], ids["un"])
    with pytest.raises(RuntimeError):
        client.post(
            _url(ids),
            data={"escolha": nova.isoformat(), "acao_anteriores": "remover"},
        )

    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    assert _chave(_linhas(app, ids)) == antes_das_linhas
    assert _logs(app) == []


# ---------------------------------------------------------------------------
# Perfis e validação da ação
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("perfil", ["admin", "ped", "sec"])
def test_perfis_permitidos_removem(app, client, perfil):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:1])

    login_as(client, ids[perfil], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "remover"}
    )
    assert resposta.status_code == 302
    assert _entrada(app, ids) == nova
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 0


@pytest.mark.parametrize("chave", ["prof", "ger", "sec_b"])
def test_professor_gerencia_e_outra_unidade_403(app, client, chave):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:1])

    unidade = ids["un_b"] if chave == "sec_b" else ids["un"]
    login_as(client, ids[chave], unidade)
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "remover"}
    )
    assert resposta.status_code == 403
    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1


@pytest.mark.parametrize("valor", ["apagar", "", "REMOVER", "manter_ou_remover"])
def test_acao_anteriores_invalida_400(app, client, valor):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    nova, antes = _escolha_mover_para(app, ids)
    _lancar(app, ids, antes[:1])

    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": valor}
    )
    assert resposta.status_code == 400
    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1


# ---------------------------------------------------------------------------
# Recuar / igualar: sem pergunta, sem remoção
# ---------------------------------------------------------------------------

def test_recuar_e_igualar_nao_perguntam_nem_removem(app, client):
    entrada_atual = HOJE - timedelta(days=2)
    ids = _seed(app, entrada=entrada_atual)
    datas = _datas(app, ids)
    anteriores = [d for d in datas if d < entrada_atual]
    assert len(anteriores) >= 1
    _lancar(app, ids, anteriores[:1])

    login_as(client, ids["sec"], ids["un"])
    alvo = anteriores[-1]
    recuo = client.post(
        _url(ids), data={"escolha": alvo.isoformat(), "acao_anteriores": "remover"}
    )
    assert recuo.status_code == 302
    assert "entrada_pendentes" not in recuo.headers["Location"]
    assert _entrada(app, ids) == alvo
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1
    assert len(_logs(app)) == 1

    # Data igual: no-op silencioso (sem log novo), mesmo com "remover".
    igual = client.post(
        _url(ids), data={"escolha": alvo.isoformat(), "acao_anteriores": "remover"}
    )
    assert igual.status_code == 302
    assert "entrada_pendentes" not in igual.headers["Location"]
    assert _entrada(app, ids) == alvo
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1
    assert len(_logs(app)) == 1


# ---------------------------------------------------------------------------
# Pauta, pendências e agregados (recalculados das linhas, sem cache)
# ---------------------------------------------------------------------------

def test_pauta_pendencias_e_agregados_refletem_remocao(app, client):
    ids = _seed(app, entrada=None)
    datas = _datas(app, ids)
    assert len(datas) >= 3
    nova = datas[-1]

    # Uma falta antes da nova data e presenças no restante.
    _add_freqs(app, ids, [
        (ids["aluno"], ids["oferta"], data_alvo,
         ConceitoFrequencia.F if indice == 0 else ConceitoFrequencia.A)
        for indice, data_alvo in enumerate(datas)
    ])

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        antes_situacao = situacao_datas_oferta(turma, oferta)
        antes_pendencias = contar_pendencias_frequencia([turma])
        antes_freq = turma.freq_geral
        antes_freq_oferta = turma.freq_geral_oferta(ids["oferta"])
        assert antes_situacao["total_ate_hoje"] == len(datas)
        assert antes_situacao["lancadas"] == len(datas)
        assert antes_situacao["pendentes"] == 0
        assert antes_pendencias == 0
        assert antes_freq < 100.0

    login_as(client, ids["admin"], ids["un"])
    resposta = client.post(
        _url(ids), data={"escolha": nova.isoformat(), "acao_anteriores": "remover"}
    )
    assert resposta.status_code == 302

    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        oferta = db.session.get(TurmaCurso, ids["oferta"])
        depois_situacao = situacao_datas_oferta(turma, oferta)
        depois_pendencias = contar_pendencias_frequencia([turma])
        depois_freq = turma.freq_geral
        depois_freq_oferta = turma.freq_geral_oferta(ids["oferta"])
        restantes = Frequencia.query.filter_by(
            aluno_id=ids["aluno"], turma_curso_id=ids["oferta"],
        ).all()

    assert len(restantes) == 1
    assert restantes[0].data == nova
    assert depois_situacao["total_ate_hoje"] == 1
    assert depois_situacao["lancadas"] == 1
    assert depois_situacao["pendentes"] == 0
    assert depois_situacao["status"][nova.isoformat()] == "lancada"
    assert depois_pendencias == len(datas) - 1
    assert depois_pendencias > antes_pendencias
    assert depois_freq == 100.0
    assert depois_freq_oferta == 100.0
    assert depois_freq > antes_freq
    assert depois_freq_oferta > antes_freq_oferta


# ---------------------------------------------------------------------------
# Tela: sem botão/modal para quem não edita
# ---------------------------------------------------------------------------

def test_gerencia_nao_ganha_botao_nem_modal(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    login_as(client, ids["ger"], ids["un"])
    body = client.get(
        f"/turma/{ids['turma']}?oferta_sel={ids['oferta']}"
    ).get_data(as_text=True)
    assert 'data-bs-target="#modalEntrada"' not in body
    assert 'name="acao_anteriores"' not in body


# ---------------------------------------------------------------------------
# Trava opção A (F2): conselho concluído bloqueia "Remover", permite "Manter"
# ---------------------------------------------------------------------------

def _concluir_conselho(app, oferta_id):
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        oferta.conselho_concluido = True
        db.session.commit()


def test_conselho_concluido_bloqueia_remocao_sem_alterar(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    datas = _datas(app, ids)
    anteriores = [d for d in datas if d < HOJE - timedelta(days=30)]
    # nova: uma data de aula após a entrada atual que ainda tem anteriores
    posteriores = [d for d in datas if d > HOJE - timedelta(days=30)]
    assert anteriores and len(posteriores) >= 2
    nova = posteriores[1]
    _lancar(app, ids, anteriores[:1])
    _concluir_conselho(app, ids["oferta"])

    login_as(client, ids["admin"], ids["un"])
    resp = client.post(
        _url(ids),
        data={"escolha": nova.isoformat(), "acao_anteriores": "remover"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "conselho" in corpo.lower()
    assert _entrada(app, ids) == HOJE - timedelta(days=30)
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1
    assert len(_logs(app)) == 0


def test_conselho_concluido_permite_manter(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    datas = _datas(app, ids)
    anteriores = [d for d in datas if d < HOJE - timedelta(days=30)]
    posteriores = [d for d in datas if d > HOJE - timedelta(days=30)]
    assert anteriores and len(posteriores) >= 2
    nova = posteriores[1]
    _lancar(app, ids, anteriores[:1])
    _concluir_conselho(app, ids["oferta"])

    login_as(client, ids["admin"], ids["un"])
    resp = client.post(
        _url(ids),
        data={"escolha": nova.isoformat(), "acao_anteriores": "manter"},
    )
    assert resp.status_code == 302
    assert _entrada(app, ids) == nova
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 1
    logs = _logs(app)
    assert len(logs) == 1
    assert "mantidas 1" in (logs[0].detalhes or "")


def test_sem_conselho_remocao_liberada(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    datas = _datas(app, ids)
    anteriores = [d for d in datas if d < HOJE - timedelta(days=30)]
    posteriores = [d for d in datas if d > HOJE - timedelta(days=30)]
    assert anteriores and len(posteriores) >= 2
    nova = posteriores[1]
    _lancar(app, ids, anteriores[:1])

    login_as(client, ids["admin"], ids["un"])
    resp = client.post(
        _url(ids),
        data={"escolha": nova.isoformat(), "acao_anteriores": "remover"},
    )
    assert resp.status_code == 302
    assert _entrada(app, ids) == nova
    with app.app_context():
        assert Frequencia.query.filter_by(aluno_id=ids["aluno"]).count() == 0


def test_modal_oculta_remover_quando_conselho_concluido(app, client):
    ids = _seed(app, entrada=HOJE - timedelta(days=30))
    datas = _datas(app, ids)
    anteriores = [d for d in datas if d < HOJE - timedelta(days=30)]
    posteriores = [d for d in datas if d > HOJE - timedelta(days=30)]
    assert anteriores and len(posteriores) >= 2
    nova = posteriores[1]
    _lancar(app, ids, anteriores[:1])
    _concluir_conselho(app, ids["oferta"])

    login_as(client, ids["admin"], ids["un"])
    # dispara reabertura do modal (tenta avançar sem decisão -> pendentes)
    resp = client.post(
        _url(ids), data={"escolha": nova.isoformat()}, follow_redirects=True
    )
    assert resp.status_code == 200
    corpo = resp.get_data(as_text=True)
    assert "entradaManter" in corpo
    assert "Remover frequências" not in corpo
    assert "conselho" in corpo.lower()

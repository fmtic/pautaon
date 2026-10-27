"""ETAPA L4.1 — reativação só das ofertas desativadas junto com a turma.

Defeito caracterizado (P2): `reativar_turma` reativava TODAS as ofertas
inativas da turma, assumindo que todas tinham caído com a exclusão lógica.
Uma oferta removida antes por `desativar_oferta` (rota
`turma_oferta_desativar`) era ressuscitada — e, se outra oferta tinha assumido
o principal, a volta violava `uix_turma_curso_principal` e a regra
"2+ ativas => exatamente 1 principal".

Marcador adotado (P1/P3): nenhum `updated_at` é confiável — o listener de
auditoria carimba `updated_at = now()` em TODAS as ofertas tocadas pela
exclusão, inclusive as que já estavam inativas (medido em PostgreSQL scratch
e em SQLite; evidência em docs/Relatórios/L4_1_ReativacaoOfertasElegiveis.md).
O marcador passa a ser um `LogAcao` explícito gravado por `excluir_turma`
(caminho lógico) com a lista das ofertas que estavam ativas; pré-visualização e
reativação usam essa lista e o operador ajusta por checkbox.

Estes testes de caracterização foram escritos CONTRA O CÓDIGO ATUAL
expressando o comportamento-alvo: falham antes da regra da P3, passam depois.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitadas do harness D5.

from datetime import date, timedelta

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app.database import db
from app.models import (
    Aluno, Curso, Frequencia, PeriodoLetivo, Turma, TurmaCurso, Unidade, User,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _login(client, uid, unidade_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def _setup(app, client, *, b_com_aluno=False, b_principal=False, encerrar_periodo=False):
    """Semeia turma com ofertas A e B + histórico (garante exclusão LÓGICA).

    A oferta B é DESATIVADA MANUALMENTE antes da exclusão (rota real
    `turma_oferta_desativar`) — é o que a reativação não pode ressuscitar.
    `b_com_aluno` mantém um aluno ativo em B (exige período encerrado);
    `b_principal` marca B como principal; `encerrar_periodo` põe `data_fim` no
    passado (libera desativar oferta com alunos ativos e exige confirmação na
    reativação).
    """
    with app.app_context():
        un = Unidade(nome="Unidade L41", ativo=True)
        admin = User(
            name="Admin L41", email="admin.l41@example.com", role="admin",
            first_login=False,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add_all([un, admin])
        db.session.flush()

        fim = date.today() - timedelta(days=5) if encerrar_periodo else DATA_FIM
        periodo = PeriodoLetivo(
            nome="Periodo L41", data_inicio=DATA_INI, data_fim=fim,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma L41", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        def _oferta(nome, principal):
            curso = Curso(nome=f"Curso {nome}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            return nova_oferta(turma.id, curso.id, un.id, principal=principal)

        a = _oferta("A", not b_principal)
        b = _oferta("B", b_principal)

        ana = Aluno(nome="Ana L41", unidade_id=un.id, ativo=True)
        db.session.add(ana)
        db.session.flush()
        insc_a = nova_inscricao(ana.id, turma.id, a.id)

        bo = None
        if b_com_aluno:
            bo = Aluno(nome="Bo L41", unidade_id=un.id, ativo=True)
            db.session.add(bo)
            db.session.flush()
            nova_inscricao(bo.id, turma.id, b.id)

        # Histórico: força o caminho da exclusão LÓGICA em excluir_turma.
        db.session.add(Frequencia(
            aluno_id=ana.id, turma_id=turma.id, turma_curso_id=a.id,
            data=date(2026, 3, 2), conceito="A", unidade_id=un.id,
        ))
        db.session.commit()
        dados = {
            "un": un.id, "admin": admin.id, "periodo": periodo.id,
            "turma": turma.id, "a": a.id, "b": b.id,
            "ana": ana.id, "bo": bo.id if bo else None, "insc_a": insc_a.id,
        }

    _login(client, dados["admin"], dados["un"])
    resp = client.post(f"/turma/oferta/{dados['b']}/desativar")
    assert resp.status_code == 302, "desativação manual de B precisa ser aceita"
    return dados


def _excluir(app, client, dados):
    """Exclusão lógica pela rota real e conferência do estado na lixeira."""
    client.post(f"/turma/excluir/{dados['turma']}")
    with app.app_context():
        assert Turma.query.get(dados["turma"]).ativo is False


def _reativar(client, dados, *, marcar=None, confirmar=True):
    """Reativação pela rota; `marcar=None` usa a pré-seleção do marcador."""
    form = {}
    if confirmar:
        form["confirmar_periodo"] = "1"
    if marcar is not None:
        form["oferta_ids"] = [str(oid) for oid in marcar]
    return client.post(
        f"/turmas/reativar/{dados['turma']}", data=form, follow_redirects=True
    )


def test_p2_oferta_desativada_antes_da_exclusao_nao_reativada(app, client):
    """B saiu da turma ANTES da exclusão: tem de voltar inativa."""
    dados = _setup(app, client)
    _excluir(app, client, dados)

    resp = _reativar(client, dados)
    assert resp.status_code == 200
    with app.app_context():
        assert Turma.query.get(dados["turma"]).ativo is True
        assert TurmaCurso.query.get(dados["a"]).ativo is True
        # Comportamento atual: B volta ativa (o defeito). Alvo: permanece inativa.
        assert TurmaCurso.query.get(dados["b"]).ativo is False


def test_p2_variante_principal_mudou_apos_remover_b(app, client):
    """B era a principal, A assumiu: a conta de B derruba a reativação inteira.

    `definir_principal` só desmarca as ofertas ATIVAS, então B inativa
    conserva `principal=True` (o índice parcial `uix_turma_curso_principal`
    filtra por `principal AND ativo`, portanto permite). Como `reativar_turma`
    coloca TODAS as inativas no conjunto final, A + B resultam em duas ativas
    com duas marcas de principal e a regra recusa a operação por inteiro
    (mediido: flash "Reativação violaria a regra de curso principal…") — a
    turma não volta nem com a oferta que estava ativa na exclusão.
    """
    dados = _setup(app, client, b_principal=True)
    with app.app_context():
        from app.services.turma_curso import definir_principal

        definir_principal(TurmaCurso.query.get(dados["a"]))
        b = TurmaCurso.query.get(dados["b"])
        assert b.principal is True and b.ativo is False

    _excluir(app, client, dados)
    resp = _reativar(client, dados)
    assert resp.status_code == 200
    with app.app_context():
        assert Turma.query.get(dados["turma"]).ativo is True
        assert TurmaCurso.query.get(dados["a"]).ativo is True
        assert TurmaCurso.query.get(dados["b"]).ativo is False
        assert TurmaCurso.query.get(dados["a"]).principal is True

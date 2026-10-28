"""ETAPA L4.2 — `Turma.programa` acompanha a reativação da turma.

Regra (MER §8.10): `Turma.programa` é **projeção** do programa da oferta
principal ativa; com uma única oferta ativa ela é a referência mesmo sem a
marca de principal, e sem ofertas ativas a projeção fica vazia. Quem grava a
projeção é `sincronizar_programa_turma`, chamado por `adicionar_oferta`,
`editar_oferta`, `definir_principal` e `desativar_oferta`.

Defeito caracterizado (P2): `reativar_turma` devolvia turma e ofertas à vida
sem reprojetar o programa. Se a seleção da lixeira deixava ativa uma oferta
diferente da que era a principal antes da exclusão, `Turma.programa` ficava
apontando para o programa de uma oferta que não voltou — e a listagem/filtros
de turma passavam a exibir um programa que a turma não oferta mais.

Cenários fixados:
    1. reativar as duas ofertas → programa da principal (A) — guarda contra
       regressão (o valor já era X antes da exclusão);
    2. reativar SÓ B (oferta não principal) → programa de B, pela mesma regra
       de `sincronizar_programa_turma` (oferta única ativa é a referência);
    3. `Turma.programa` desatualizado de propósito → corrigido na reativação;
    4. recusa atômica (regra do principal) não altera o programa;
    5. turma sem oferta reativada não tem projeção a recalcular (não zera o
       programa legado de turma sem ofertas).

Estes testes de caracterização foram escritos CONTRA O CÓDIGO ATUAL
expressando o comportamento-alvo: os casos 2 e 3 falham antes da P3.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitadas do harness D5.

from datetime import date

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app.database import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _login(client, uid, unidade_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(uid)
        sess["_fresh"] = True
        if unidade_id is not None:
            sess["unidade_id"] = unidade_id


def _seed(
    app, client, *,
    programa_a="X", programa_b="Y",
    turma_programa=None, b_principal=False, desativar_b=False,
):
    """Turma com A (principal, programa X) e B (programa Y) + histórico.

    A oferta A é a principal; `turma_programa` fixa a projeção na semente
    (default: programa de A). `desativar_b` remove B pela rota real antes da
    exclusão (B sai da turma ANTES — não está no marcador L4.1).
    O histórico (Frequencia) força o caminho da exclusão LÓGICA.
    """
    with app.app_context():
        un = Unidade(nome="Unidade L42", ativo=True)
        admin = User(
            name="Admin L42", email="admin.l42@example.com", role="admin",
            first_login=False,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add_all([un, admin])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo L42", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma L42", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
            programa=turma_programa if turma_programa is not None else programa_a,
        )
        db.session.add(turma)
        db.session.flush()

        def _oferta(nome, programa, principal):
            curso = Curso(nome=f"Curso {nome}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            return nova_oferta(
                turma.id, curso.id, un.id,
                programa=programa, principal=principal,
            )

        a = _oferta("A", programa_a, not b_principal)
        b = _oferta("B", programa_b, b_principal)

        ana = Aluno(nome="Ana L42", unidade_id=un.id, ativo=True)
        db.session.add(ana)
        db.session.flush()
        nova_inscricao(ana.id, turma.id, a.id)

        # Histórico: o excluir_turma cai no ramo LÓGICO (preserva lançamentos).
        db.session.add(Frequencia(
            aluno_id=ana.id, turma_id=turma.id, turma_curso_id=a.id,
            data=date(2026, 3, 2), conceito="A", unidade_id=un.id,
        ))
        db.session.commit()
        dados = {
            "un": un.id, "admin": admin.id, "turma": turma.id,
            "a": a.id, "b": b.id, "ana": ana.id,
        }

    _login(client, dados["admin"], dados["un"])
    if desativar_b:
        resp = client.post(f"/turma/oferta/{dados['b']}/desativar")
        assert resp.status_code == 302, "desativação manual de B precisa ser aceita"
    return dados


def _excluir(client, dados):
    """Exclusão lógica pela rota real (a turma sai com as ofertas ativas)."""
    resp = client.post(f"/turma/excluir/{dados['turma']}")
    assert resp.status_code == 302


def _reativar(client, dados, *, marcar=None):
    """POST da lixeira; `marcar=None` usa a pré-seleção do marcador."""
    form = {"confirmar_periodo": "1"}
    if marcar is not None:
        form["selecao_explicita"] = "1"
        form["oferta_ids"] = [str(oid) for oid in marcar]
    return client.post(
        f"/turmas/reativar/{dados['turma']}", data=form, follow_redirects=True
    )


def _programa(app, turma_id):
    """Lê `Turma.programa` do BANCO (expira o cache da sessão do harness)."""
    with app.app_context():
        db.session.expire_all()
        return db.session.get(Turma, turma_id).programa


def _inativa_direto(app, client, *, programa, nome="Turma sem oferta L42"):
    """Semeia a identidade e uma turma já na lixeira, SEM nenhuma oferta."""
    with app.app_context():
        un = Unidade(nome="Unidade L42 sem oferta", ativo=True)
        admin = User(
            name="Admin L42 sem oferta", email="admin.l42s@example.com",
            role="admin", first_login=False,
        )
        admin.set_password("SenhaLocal!123")
        db.session.add_all([un, admin])
        db.session.flush()
        turma = Turma(
            nome=nome, turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=False, programa=programa,
        )
        db.session.add(turma)
        db.session.commit()
        ids = (turma.id, admin.id, un.id)

    _login(client, ids[1], ids[2])
    return ids[0]


# ---------------------------------------------------------------------------
# P2 — caracterização
# ---------------------------------------------------------------------------

def test_p2_reativar_as_duas_ofertas_mantem_programa_da_principal(app, client):
    """Cenário 1: A (principal, X) e B (Y) voltam → programa da principal (X).

    Guarda contra regressão: antes da exclusão a turma já tinha X, então este
    caso passava antes da P3 — ele protege a correção de quebrar o caminho
    "tudo volta como estava".
    """
    dados = _seed(app, client)
    assert _programa(app, dados["turma"]) == "X"
    _excluir(client, dados)

    resp = _reativar(client, dados)
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(Turma, dados["turma"]).ativo is True
        assert db.session.get(TurmaCurso, dados["a"]).ativo is True
        assert db.session.get(TurmaCurso, dados["b"]).ativo is True
    assert _programa(app, dados["turma"]) == "X"


def test_p2_reativar_so_b_reprojeta_programa_de_b(app, client):
    """Cenário 2: volta SÓ B (não principal) → programa de B, a única ativa.

    B saiu da turma ANTES da exclusão (marcador L4.1 traz só A), mas o operador
    marca B na lixeira. `sincronizar_programa_turma` fixa: com uma oferta ativa,
    ela é a referência mesmo sem a marca de principal ⇒ `Turma.programa = Y`.
    """
    dados = _seed(app, client, desativar_b=True)
    _excluir(client, dados)

    resp = _reativar(client, dados, marcar=[dados["b"]])
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(TurmaCurso, dados["b"]).ativo is True
        assert db.session.get(TurmaCurso, dados["a"]).ativo is False
    assert _programa(app, dados["turma"]) == "Y"


def test_p2_reativar_so_b_com_marcador_da_exclusao(app, client):
    """Cenário 2 (variante): A e B caíram juntas; só B volta → programa de B."""
    dados = _seed(app, client)
    _excluir(client, dados)

    resp = _reativar(client, dados, marcar=[dados["b"]])
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(TurmaCurso, dados["b"]).ativo is True
        assert db.session.get(TurmaCurso, dados["a"]).ativo is False
    assert _programa(app, dados["turma"]) == "Y"


def test_p2_programa_desatualizado_e_corrigido_na_reativacao(app, client):
    """Cenário 3: projeção suja ("PROGRAMA ANTIGO") é reescrita pela regra."""
    dados = _seed(app, client, turma_programa="PROGRAMA ANTIGO")
    _excluir(client, dados)
    assert _programa(app, dados["turma"]) == "PROGRAMA ANTIGO"

    resp = _reativar(client, dados)
    assert resp.status_code == 200
    assert _programa(app, dados["turma"]) == "X"


# ---------------------------------------------------------------------------
# P4 — recusas e limites da chamada
# ---------------------------------------------------------------------------

def test_p4_recusa_atomica_nao_altera_programa(app, client):
    """Seleção que viola a regra do principal não toca `Turma.programa`.

    B é a principal, sai da turma antes da exclusão (conserva a marca, porque
    `definir_principal` só desmarca ofertas ATIVAS) e A assume; reativar as duas
    pelo checkbox resulta em duas marcas de principal e a recusa é total.
    """
    from app.services.turma_curso import definir_principal

    dados = _seed(app, client, b_principal=True, desativar_b=True)
    with app.app_context():
        definir_principal(db.session.get(TurmaCurso, dados["a"]))
        # `definir_principal` reprojeta; a projeção suja entra DEPOIS dele.
        db.session.get(Turma, dados["turma"]).programa = "DESATUALIZADO"
        db.session.commit()
    _excluir(client, dados)

    resp = _reativar(client, dados, marcar=[dados["a"], dados["b"]])
    assert "curso principal" in resp.get_data(as_text=True)

    with app.app_context():
        turma = db.session.get(Turma, dados["turma"])
        assert turma.ativo is False
        assert db.session.get(TurmaCurso, dados["a"]).ativo is False
        assert db.session.get(TurmaCurso, dados["b"]).ativo is False
    assert _programa(app, dados["turma"]) == "DESATUALIZADO"


def test_p4_turma_sem_oferta_reativada_nao_zera_programa(app, client):
    """Sem oferta reativada não há projeção a recalcular (não vira NULL).

    Turma sem ofertas é estado legado: zerar o programa apagaria o dado que
    ainda alimenta listagem e filtros de turma. A P3 só chama a sincronização
    quando ao menos uma oferta volta.
    """
    turma_id = _inativa_direto(app, client, programa="MANTER")
    resp = client.post(
        f"/turmas/reativar/{turma_id}",
        data={"confirmar_periodo": "1", "selecao_explicita": "1"},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        assert db.session.get(Turma, turma_id).ativo is True
        assert db.session.get(Turma, turma_id).ofertas_curso == []
    assert _programa(app, turma_id) == "MANTER"


def test_p4_servico_reprojeta_sem_commit(app, client):
    """A reprojeção acontece na transação do chamador (o serviço não commita)."""
    from app.services.turma_curso import reativar_turma

    dados = _seed(app, client, turma_programa="PROGRAMA ANTIGO")
    _excluir(client, dados)

    with app.app_context():
        turma = db.session.get(Turma, dados["turma"])
        resultado = reativar_turma(turma, confirmar_periodo_encerrado=True)
        assert resultado["ofertas_reativadas"] == 2
        assert turma.programa == "X", "reprojeção na MESMA transação"
        db.session.rollback()

    assert _programa(app, dados["turma"]) == "PROGRAMA ANTIGO"
    with app.app_context():
        assert db.session.get(Turma, dados["turma"]).ativo is False

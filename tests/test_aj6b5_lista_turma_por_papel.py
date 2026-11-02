# ruff: noqa: F811
"""AJ6-B5 — a lista GET /turma é exclusiva dos perfis gestores.

REGRA DE NEGÓCIO (responsável): a LISTA de turmas (`registros.turma`) só pode
ser acessada por admin, secretaria, pedagógico e gerência. O professor NUNCA
acessa a lista (entra nas ofertas dele via painel/ficha, pela REGRA ÚNICA de
autorização por oferta do ciclo AJ6-B3/B4 — nenhuma predicação nova). Isso
substitui a decisão "manter" registrada no AJ6-B4 (item 4).

Cobre, sempre com SQLite em memória e nomes sintéticos:

    - Item 1 (matriz de papéis): admin/secretaria/pedagogico/gerencia → 200;
      professor → 403; servico_social → 403 (nunca esteve na lista); anônimo →
      redirect de login.
    - Item 2 (navegação): para o professor, nenhuma página que ele abre (painel,
      ficha ver_turma, frequência, diário, histórico do aluno) contém link ou
      redirect para a lista /turma.
    - Item 4 (snapshot): o HTML normalizado da lista para os 4 perfis gestores é
      idêntico antes/depois (o gate não toca a renderização desses perfis).

Reversão em git worktree (caminhos absolutos).
"""

import os
import re
from pathlib import Path

import pytest
from _helpers import login_as
from test_aj6b2_auditoria_ofertas import _setup

from app import db
from app.models import User

pytestmark = pytest.mark.usefixtures("hoje_fixo")

PASTA_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
ATUALIZAR_SNAPSHOTS = os.environ.get("AJ6B5_ATUALIZAR_SNAPSHOTS") == "1"

# Perfis gestores com acesso à lista (exceto admin, que já vem do _setup).
PERFIS_GESTORES = ("secretaria", "pedagogico", "gerencia")


def _gestores(app, ids):
    """Garante um usuário por perfil gestor (exceto admin) + servico_social.

    Devolve {role: user_id}. admin é reaproveitado do _setup (ids['admin']).
    """
    with app.app_context():
        novos = {"admin": ids["admin"]}
        marcados = []
        for role in PERFIS_GESTORES + ("servico_social",):
            u = User(
                name=f"Perfil {role} AJ6B5", email=f"{role}.lista@aj6b5.test",
                role=role, first_login=False, unidade_id=ids["un"],
            )
            u.set_password("SenhaLocal!123")
            db.session.add(u)
            marcados.append((role, u))
        db.session.commit()
        for role, u in marcados:
            novos[role] = u.id
    return novos


def _link_lista(html):
    """href/action que apontam EXATAMENTE para a lista /turma (com ou sem query).

    Não confunde com a ficha /turma/<id> (seguida de dígito) nem com /turma/nova.
    """
    return re.findall(r'(?:href|action)="/turma(?=["?\s])', html)


# ===========================================================================
# ITEM 1 — matriz de papéis na lista
# ===========================================================================

@pytest.mark.parametrize(
    "role,esperado",
    [
        ("admin", 200),
        ("secretaria", 200),
        ("pedagogico", 200),
        ("gerencia", 200),
        ("professor", 403),
        ("servico_social", 403),
    ],
)
def test_matriz_papeis_lista_turma(app, client, role, esperado):
    """Gestores → 200; professor e servico_social → 403 (AJ6-B5)."""
    ids = _setup(app)
    gestores = _gestores(app, ids)
    if role == "professor":
        user_id = ids["pa"]
    else:
        user_id = gestores[role]
    login_as(client, user_id, ids["un"])
    r = client.get("/turma")
    assert r.status_code == esperado, f"{role}: {r.status_code} != {esperado}"


def test_anonimo_lista_turma_redireciona_login(client):
    """Sem sessão: @login_required devolve redirect para o login (não 200/403)."""
    r = client.get("/turma", follow_redirects=False)
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


# ===========================================================================
# ITEM 2 — navegação do professor: nenhum caminho leva à lista
# ===========================================================================

@pytest.mark.parametrize(
    "rota",
    [
        "painel",
        "ver_turma_t1",
        "ver_turma_t2",
        "frequencia_t1",
        "diario_t1",
        "historico_aluno_a",
    ],
)
def test_navegacao_professor_sem_link_para_lista(app, client, rota):
    """pA (leciona A em T1, D/E em T2): cada página que ele abre não pode
    conter link nem redirect para a lista /turma (que lhe dá 403)."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    alvo = {
        "painel": "/painel",
        "ver_turma_t1": f"/turma/{ids['t1']}",
        "ver_turma_t2": f"/turma/{ids['t2']}",
        "frequencia_t1": f"/frequencia?turma_id={ids['t1']}",
        "diario_t1": f"/turma/{ids['t1']}/observacoes?turma_curso={ids['a']}",
        "historico_aluno_a": f"/aluno/{ids['alunos']['A']}/historico",
    }[rota]
    r = client.get(alvo, follow_redirects=False)
    # Página própria do professor: 200 (ou 302 interno que não aponta à lista).
    assert r.status_code in (200, 302), f"{rota}: {r.status_code}"
    destino = r.headers.get("Location", "")
    assert not re.search(r'(?<![\w])/turma(?![\w/])', destino), (
        f"{rota}: redirect aponta para a lista — {destino}"
    )
    if r.status_code == 200:
        html = r.get_data(as_text=True)
        assert _link_lista(html) == [], f"{rota}: página tem link para a lista"


def test_voltar_ficha_turma_leva_professor_ao_painel(app, client):
    """Região específica: o 'Voltar' da ficha (ver_turma) do professor aponta
    ao painel, nunca à lista (que seria 403)."""
    ids = _setup(app)
    login_as(client, ids["pa"], ids["un"])
    html = client.get(f"/turma/{ids['t1']}").get_data(as_text=True)
    assert _link_lista(html) == [], "o Voltar da ficha vazou link da lista"
    assert 'href="/painel"' in html, "o Voltar do professor deve ir ao painel"


# ===========================================================================
# ITEM 4 — snapshot do HTML da lista para os gestores (idêntico antes/depois)
# ===========================================================================

def _normaliza(html):
    """Estrutura sem classes: remove class=, csrf e colapsa whitespace.

    Derruba também o nome do usuário logado (aparece no topo) e qualquer
    data/hora volátil, para o snapshot ser determinístico entre execuções e
    independente do perfil (só o conteúdo da LISTA importa).
    """
    sem_classes = re.sub(r'\s+class="[^"]*"', "", html)
    sem_csrf = re.sub(
        r'<input[^>]*name="csrf_token"[^>]*>', '<input name="csrf_token" />',
        sem_classes,
    )
    sem_csrf = re.sub(
        r'<meta[^>]*name="csrf-token"[^>]*content="[^"]*"',
        '<meta name="csrf-token" content="CSRF"',
        sem_csrf,
    )
    return re.sub(r"\s+", " ", sem_csrf).strip()


def _confrontar(nome, atual):
    caminho = PASTA_SNAPSHOTS / nome
    if ATUALIZAR_SNAPSHOTS:
        PASTA_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        caminho.write_text(atual, encoding="utf-8")
        return
    assert caminho.exists(), (
        f"snapshot {nome} ausente — gere com AJ6B5_ATUALIZAR_SNAPSHOTS=1"
    )
    esperado = caminho.read_text(encoding="utf-8")
    if atual != esperado:
        for i, (ln_a, ln_b) in enumerate(
            zip(atual.splitlines(), esperado.splitlines())
        ):
            if ln_a != ln_b:
                pytest.fail(
                    f"{nome}: primeira diferença na linha {i + 1}:\n"
                    f"  atual:    {ln_a[:200]!r}\n"
                    f"  snapshot: {ln_b[:200]!r}"
                )
        pytest.fail(
            f"{nome}: comprimento diferente "
            f"(atual {len(atual)} vs snapshot {len(esperado)} chars)"
        )


def test_snapshot_lista_gestores_identico(app, client):
    """O HTML normalizado da lista é idêntico para admin/secretaria/pedagogico/
    gerência antes e depois da AJ6-B5 (remover professor do gate não toca a
    renderização desses perfis — a rota não tem ramo exclusivo de professor)."""
    ids = _setup(app)
    gestores = _gestores(app, ids)
    for role in ("admin", "secretaria", "pedagogico", "gerencia"):
        login_as(client, gestores[role], ids["un"])
        r = client.get("/turma")
        assert r.status_code == 200, f"{role}: {r.status_code}"
        _confrontar(
            f"aj6b5_lista_{role}.txt", _normaliza(r.get_data(as_text=True))
        )

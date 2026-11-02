# AJ6-B3 (conversão AJ6-B4) — snapshot golden do HTML de /turma/<id> para
# perfis NÃO-professor. Antes era um script manual com `skipif` (só escrevia
# arquivos sob AJ6B3_SNAP e nunca asseria): agora é um teste que RODA sempre e
# compara a estrutura normalizada contra o snapshot canônico em
# `tests/snapshots/`. A normalização derruba `class="..."`, csrf e whitespace,
# então compara ESTRUTURA/CONTEÚDO (não a maquete). Se o HTML de um perfil
# não-professor mudar, o teste falha — que é exatamente o que se quer de um
# snapshot de não-regressão.
#
#   pytest tests/test_aj6b3_snapshot_nao_professor.py -q            # confere
#   $env:AJ6B4_ATUALIZAR_SNAPSHOTS="1"; pytest tests/test_aj6b3_snapshot_nao_professor.py -q
#       (regenera os snapshots; usar só quando a mudança de saída for intencional)
import os
import re
from pathlib import Path

import pytest
from _helpers import login_as
from test_aj6b2_auditoria_ofertas import _setup

from app import db
from app.models import Unidade, User

PASTA_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
ATUALIZAR_SNAPSHOTS = os.environ.get("AJ6B4_ATUALIZAR_SNAPSHOTS") == "1"

PERFIS = ("admin", "pedagogico", "secretaria", "gerencia", "servico_social")


def _normaliza(html: str) -> str:
    """Estrutura sem classes: remove class=, csrf/tokens e colapsa espaço.

    Os tokens (campo oculto csrf_token e a meta de mesmo nome) nascem por
    sessão e variam entre execuções; sem derrubá-los os snapshots nunca seriam
    iguais. Nada mais do HTML é tocado.
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


def _perfis_nao_professor(app, ids):
    """Cria um usuário por perfil não-professor e devolve {role: user_id}."""
    with app.app_context():
        un = db.session.get(Unidade, ids["un"])
        novos = {"admin": ids["admin"]}
        criar = []
        for role in PERFIS:
            if role == "admin":
                continue
            u = User(
                name=f"Perfil {role}", email=f"{role}.snap@aj6b3.test",
                role=role, first_login=False, unidade_id=un.id,
            )
            u.set_password("SenhaLocal!123")
            db.session.add(u)
            criar.append((role, u))
        db.session.commit()
        # id autoincrementado só é confiável depois do commit
        for role, u in criar:
            novos[role] = u.id
    return novos


def _confrontar(nome, atual):
    caminho = PASTA_SNAPSHOTS / nome
    if ATUALIZAR_SNAPSHOTS:
        PASTA_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        caminho.write_text(atual, encoding="utf-8")
        return
    assert caminho.exists(), (
        f"snapshot {nome} ausente — gere com AJ6B4_ATUALIZAR_SNAPSHOTS=1"
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


def test_snapshot_ver_turma_nao_professor(app, client, hoje_fixo):
    """Roda SEMPRE: para cada perfil não-professor e cada turma da semente, o
    HTML normalizado de /turma/<id> deve bater com o snapshot canônico. Prova
    que a saída não-professor é idêntica antes/depois das correções AJ6-B4
    (item 4: /turma intocado; demais perfis inalterados em 1/2/3)."""
    ids = _setup(app)
    perfis = _perfis_nao_professor(app, ids)
    marcadores = []
    for role, user_id in perfis.items():
        login_as(client, user_id, ids["un"])
        for turma in ("t1", "t2"):
            r = client.get(f"/turma/{ids[turma]}")
            destino = r.headers.get("Location", "")
            marcadores.append(f"{role}/{turma}={r.status_code}@{destino}")
            assert r.status_code == 200, " | ".join(marcadores)
            corpo = _normaliza(r.get_data(as_text=True))
            _confrontar(f"aj6b3_{role}_{turma}.txt", corpo)

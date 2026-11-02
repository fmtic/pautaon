# AJ6-B3 — snapshot comparável do HTML de /turma/<id> para perfis NÃO-professor.
# Roda como teste (usa o fixture hoje_fixo para determinístico) e só escreve os
# arquivos quando AJ6B3_SNAP=antes|depois. A normalização derruba `class="..."`,
# csrf e ruído de whitespace: compara a ESTRUTURA/CONTEÚDO, não a maquete.
#
#   $env:AJ6B3_SNAP="antes";  pytest tests/test_aj6b3_snapshot_nao_professor.py -q
#   $env:AJ6B3_SNAP="depois"; pytest tests/test_aj6b3_snapshot_nao_professor.py -q
#   fc /l .tmp\aj6b3_snap_antes\admin_t1.html .tmp\aj6b3_snap_depois\admin_t1.html
import os
import re

import pytest
from _helpers import login_as
from test_aj6b2_auditoria_ofertas import _setup

from app import db
from app.models import Unidade, User

PERFIS = ("admin", "pedagogico", "secretaria", "gerencia", "servico_social")


def _normaliza(html: str) -> str:
    """Estrutura sem classes: remove class=, csrf/tokens e colapsa espaço.

    Os tokens (campo oculto csrf_token e a meta de mesmo nome) nascem por
    sessio e variam entre execucoes; sem derruba-los os snapshots nunca
    seriam iguais. Nada mais do HTML e tocado.
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


@pytest.mark.skipif(
    os.environ.get("AJ6B3_SNAP") not in ("antes", "depois"),
    reason="snapshot manual: exigir AJ6B3_SNAP=antes|depois",
)
def test_snapshot_ver_turma_nao_professor(app, client, hoje_fixo):
    rotulo = os.environ["AJ6B3_SNAP"]
    ids = _setup(app)
    perfis = _perfis_nao_professor(app, ids)
    pasta = os.path.join(".tmp", f"aj6b3_snap_{rotulo}")
    os.makedirs(pasta, exist_ok=True)
    marcadores = []
    for role, user_id in perfis.items():
        login_as(client, user_id, ids["un"])
        for turma in ("t1", "t2"):
            r = client.get(f"/turma/{ids[turma]}")
            destino = r.headers.get("Location", "")
            marcadores.append(f"{role}/{turma}={r.status_code}@{destino}")
            assert r.status_code == 200, " | ".join(marcadores)
            corpo = _normaliza(r.get_data(as_text=True))
            with open(os.path.join(pasta, f"{role}_{turma}.html"), "w",
                      encoding="utf-8") as f:
                f.write(corpo)

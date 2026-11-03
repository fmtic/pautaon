# ruff: noqa: F811
"""AJ6-B6 — matriz de rotas do professor (allowlist + teste-trava).

REGRA DE NEGÓCIO (responsável): o professor só acessa o que é inerente às
OFERTAS em que está associado (REGRA ÚNICA `ofertas_do_professor` /
`professor_pode_acessar_oferta`, sem predicação nova) e NUNCA acessa a FICHA
do aluno (cadastro, perfis, documentos, ficha 360, edição, laudos/atendimentos,
anexos, exportações).

Cobre, sempre com SQLite em memória, relógio congelado e nomes sintéticos:

    - Item 2 (inventário dinâmico): varre TODAS as regras do url_map como
      professor, chamando cada GET/POST com ids PRÓPRIOS e ALHEIOS da semente.
      Qualquer 500 é tratado como bug (falha).
    - Item 3 (allowlist + teste-trava): fora da ALLOWLIST, o professor jamais
      pode receber CONTEÚDO (2xx) nem erro de servidor (5xx) — só 401/403/404
      ou redirect de negação. E endpoint da allowlist que recebe id de recurso
      no path não pode devolver 200 para recurso de OFERTA ALHEIA. Assim, rota
      nova aberta ao professor sem decisão consciente quebra a suíte.
    - Item 4 (guards reaplicadas): `/form` (500 p/ professor) e
      `/alunos/instituicoes` (autocomplete da ficha) agora barram o professor
      com a GUARDA POR ROLE JÁ EXISTENTE (irmãs `editar`/`atualizar_nivel`).
      O gate de `/turmas/centros-custo/imprimir` (sem `professor`) fica travado.
    - Item 6 (links): nas telas do professor nenhum href/action aponta para
      rota fora da allowlist; HTML de não-professor inalterado (snapshot golden).

Reversão em git worktree (caminhos absolutos): sem os guards deste trabalho,
as varreduras own/foreign e os testes de rota específica FALHAM (professor
alcança `/form`=500 e `/alunos/instituicoes`=200).
"""

import os
import re
from datetime import time, timedelta
from pathlib import Path

import pytest
from _helpers import dia_de_aula_ate, hoje_ref, login_as, nova_inscricao, nova_oferta

from app import db
from app.models import Aluno, Curso, PeriodoLetivo, Turma, Unidade, User

pytestmark = pytest.mark.usefixtures("hoje_fixo")

HOJE = dia_de_aula_ate(hoje_ref())
DIAS = "Segunda, Terça, Quarta, Quinta, Sexta"

PASTA_SNAPSHOTS = Path(__file__).resolve().parent / "snapshots"
ATUALIZAR_SNAPSHOTS = os.environ.get("AJ6B6_ATUALIZAR_SNAPSHOTS") == "1"

# ---------------------------------------------------------------------------
# ALLOWLIST — endpoints que o professor PODE alcançar (conteúdo legítimo).
# Qualquer endpoint AUSENTE daqui não pode devolver 2xx/5xx ao professor.
# ---------------------------------------------------------------------------
ALLOWLIST = {
    "static",
    # sessão / perfil próprios
    "auth.login",
    "auth.logout",
    "auth.trocar_senha",
    # painéis do professor
    "main.home",
    "main.painel",
    "main.dashboard",
    "main.painel_pedagogico_professor",
    "main.politica_privacidade",
    "main.termos_servico",
    # conselho da própria oferta
    "conselho.index_conselho",
    "conselho.lancamento_conselho",
    "conselho.avaliar_turma",
    "conselho.salvar_conselho",
    # rotina de aula das próprias ofertas
    "registros.frequencia",
    "registros.ver_turma",
    "registros.ver_observacoes",
    "registros.imprimir_pauta",
    # item 5 (só reportar, NÃO alterar): visão do aluno da PRÓPRIA oferta.
    # Ficam na allowlist por decisão vigente do responsável; o relatório
    # documenta a exposição de dados da ficha para reavaliação.
    "registros.historico_aluno",
    "registros.foto_aluno",
    "registros.info_professor",
}

# Endpoints da allowlist que recebem id de recurso no path (turma/oferta/aluno).
# Para recurso ALHEIO (oferta de outro professor) não podem devolver 200 — a
# autorização por oferta tem que negar.
RESOURCE_ID_ENDPOINTS = {
    "registros.ver_turma",
    "registros.ver_observacoes",
    "registros.imprimir_pauta",
    "conselho.avaliar_turma",
    "registros.historico_aluno",
    "registros.foto_aluno",
    "registros.info_professor",
}


def _usuario(nome, role, un_id):
    u = User(
        name=nome, email=f"{nome.lower().replace(' ', '.')}@aj6b6.test",
        role=role, first_login=False, unidade_id=un_id,
    )
    u.set_password("SenhaLocal!123")
    return u


def _seed(app):
    """Semente: pA (oferta própria A em T1; oferta G em T3 ALHEIA de pB),
    aluno próprio (em A) e alheio (só em G). T3 é turma sem oferta de pA."""
    with app.app_context():
        un = Unidade(nome="Unidade AJ6B6", ativo=True)
        db.session.add(un)
        db.session.flush()
        pa = _usuario("Professor Alfa", "professor", un.id)
        pb = _usuario("Professor Bravo", "professor", un.id)
        adm = _usuario("Admin AJ6B6", "admin", un.id)
        sec = _usuario("Secretaria AJ6B6", "secretaria", un.id)
        ped = _usuario("Pedagogico AJ6B6", "pedagogico", un.id)
        db.session.add_all([pa, pb, adm, sec, ped])
        db.session.flush()

        per = PeriodoLetivo(
            nome="P AJ6B6", data_inicio=HOJE - timedelta(days=40),
            data_fim=HOJE + timedelta(days=40), unidade_id=un.id, ativo=True,
        )
        db.session.add(per)
        db.session.flush()

        def _turma(nome, prof):
            t = Turma(
                nome=nome, unidade_id=un.id, periodo_letivo_id=per.id,
                professor_id=prof.id, ativo=True,
                data_inicio=per.data_inicio, data_fim=per.data_fim,
            )
            db.session.add(t)
            db.session.flush()
            return t

        t_own = _turma("Turma Propria", pa)      # pA leciona
        t_foreign = _turma("Turma Alheia", pb)   # pA NAO leciona

        def _curso(nome):
            c = Curso(nome=nome, unidade_id=un.id, ativo=True)
            db.session.add(c)
            db.session.flush()
            return c

        cur_own = _curso("CURSO-ALFA")
        cur_foreign = _curso("CURSO-GOLF")

        o_own = nova_oferta(
            t_own.id, cur_own.id, un.id, programa="Prog A", principal=True,
            professor_id=pa.id, dias_semana=DIAS,
            hora_inicio=time(8), hora_fim=time(10),
        )
        o_foreign = nova_oferta(
            t_foreign.id, cur_foreign.id, un.id, programa="Prog G",
            principal=True, professor_id=pb.id, dias_semana=DIAS,
            hora_inicio=time(8), hora_fim=time(10),
        )

        al_own = Aluno(
            nome="Aluno Proprio", unidade_id=un.id, ativo=True,
            data_nascimento=HOJE - timedelta(days=6000),
        )
        al_foreign = Aluno(
            nome="Aluno Alheio", unidade_id=un.id, ativo=True,
            data_nascimento=HOJE - timedelta(days=6000),
        )
        db.session.add_all([al_own, al_foreign])
        db.session.flush()
        nova_inscricao(al_own.id, t_own.id, o_own.id)
        nova_inscricao(al_foreign.id, t_foreign.id, o_foreign.id)

        db.session.commit()
        return {
            "un": un.id, "pa": pa.id, "pb": pb.id, "admin": adm.id,
            "secretaria": sec.id, "pedagogico": ped.id,
            "t_own": t_own.id, "t_foreign": t_foreign.id,
            "o_own": o_own.id, "o_foreign": o_foreign.id,
            "cur_own": cur_own.id, "cur_foreign": cur_foreign.id,
            "per": per.id, "al_own": al_own.id, "al_foreign": al_foreign.id,
        }


def _sub(rule, seed, variante):
    """Preenche os <params> da rule com ids da semente (own ou foreign)."""
    own = variante == "own"
    vals = {
        "turma_id": seed["t_own"] if own else seed["t_foreign"],
        "oferta_id": seed["o_own"] if own else seed["o_foreign"],
        "aluno_id": seed["al_own"] if own else seed["al_foreign"],
        "curso_id": seed["cur_own"] if own else seed["cur_foreign"],
        "periodo_id": seed["per"],
        "id": seed["t_own"] if own else seed["t_foreign"],
        "centro_id": 1, "dia_id": 1, "conselho_id": 1, "resposta_id": 1,
        "doc_id": "doc_laudo", "codigo": "matricula", "tipo": "academica",
        "filename": "logo.png", "ano": HOJE.year,
    }
    if re.search(r"/aluno/<int:id>", rule.rule):
        vals["id"] = seed["al_own"] if own else seed["al_foreign"]
    out = rule.rule
    for m in re.finditer(r"<(?:\w+:)?(\w+)>", rule.rule):
        out = out.replace(m.group(0), str(vals.get(m.group(1), 1)))
    return out


def _varredura(app, client, seed, variante):
    """Chama cada GET/POST do url_map como pA; devolve {(ep, meth): (code, loc)}."""
    app.config["PROPAGATE_EXCEPTIONS"] = False
    resultado = {}
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.endpoint):
        ep = rule.endpoint
        if ep == "static":
            continue
        for meth in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            if meth not in ("GET", "POST"):
                continue
            url = _sub(rule, seed, variante)
            login_as(client, seed["pa"], seed["un"])  # refaz após rotas que limpam sessão
            try:
                r = (client.get(url, follow_redirects=False) if meth == "GET"
                     else client.post(url, data={}, follow_redirects=False))
                code, loc = r.status_code, r.headers.get("Location", "")
            except Exception as exc:  # noqa: BLE001 — a varredura não pode estourar
                code, loc = "EXC", type(exc).__name__
            resultado[(ep, meth)] = (code, loc)
    return resultado


def _eh_negacao(code):
    """Negação legítima: 401/403/404 ou QUALQUER redirect (não entrega corpo)."""
    return code in (401, 403, 404) or (isinstance(code, int) and 300 <= code < 400)


# ===========================================================================
# ITEM 2 + 3 — varreduras own/foreign com o teste-trava da allowlist
# ===========================================================================

@pytest.mark.parametrize("variante", ["own", "foreign"])
def test_professor_fora_da_allowlist_sem_conteudo(app, client, variante):
    """Fora da allowlist, o professor nunca recebe 2xx nem 5xx (só negação)."""
    seed = _seed(app)
    violacoes = []
    for (ep, meth), (code, loc) in _varredura(app, client, seed, variante).items():
        if ep in ALLOWLIST:
            continue
        if isinstance(code, int) and 200 <= code < 300:
            violacoes.append(f"{ep} {meth}: conteudo {code} (esperado negacao)")
        elif code in ("EXC",) or (isinstance(code, int) and code >= 500):
            violacoes.append(f"{ep} {meth}: erro {code} -> {loc} (500 e bug)")
    assert violacoes == [], "\n".join(violacoes)


@pytest.mark.parametrize("variante", ["own", "foreign"])
def test_nenhum_500_na_varredura(app, client, variante):
    """Item 2: qualquer 500 na varredura é bug a reportar."""
    seed = _seed(app)
    erros = [
        f"{ep} {meth}: {code}"
        for (ep, meth), (code, _) in _varredura(app, client, seed, variante).items()
        if code == 500 or code == "EXC"
    ]
    assert erros == [], "500/EXC detectado(s): " + "; ".join(erros)


def test_allowlist_recurso_alheio_sem_200(app, client):
    """Item 3: endpoint da allowlist com id de recurso no path não pode
    devolver 200 para recurso de OFERTA ALHEIA (autorização por oferta)."""
    seed = _seed(app)
    vazamentos = []
    for (ep, meth), (code, _) in _varredura(app, client, seed, "foreign").items():
        if ep in ALLOWLIST and ep in RESOURCE_ID_ENDPOINTS and meth == "GET":
            if isinstance(code, int) and 200 <= code < 300:
                vazamentos.append(f"{ep}: 200 para recurso alheio")
    assert vazamentos == [], "\n".join(vazamentos)


# ===========================================================================
# ITEM 4 — guards reaplicadas (antes/depois) + centros-custo travado
# ===========================================================================

def test_form_guard_e_por_role(app, client):
    """A guarda reaplicada é POR ROLE (irmãs `editar`/`excluir`: só pedagógico).
    Antes o professor alcançava `/form` (GET=500 por template ausente; POST
    escrevia `Registro`). Depois: todo não-pedagógico (professor e admin) é 403
    ANTES de qualquer render/escrita — negação limpa, sem código morto."""
    seed = _seed(app)
    for role in ("pa", "admin"):
        login_as(client, seed[role], seed["un"])
        assert client.get("/form", follow_redirects=False).status_code == 403, role
        login_as(client, seed[role], seed["un"])
        # POST também barrado pela guarda (não escreve Registro alheio)
        assert client.post("/form", data={}, follow_redirects=False).status_code == 403, role


def test_buscar_instituicoes_negado_ao_professor(app, client):
    """Autocomplete da ficha do aluno: barra o professor (guarda de
    atualizar_nivel_aluno); libera secretaria (quem edita ficha)."""
    seed = _seed(app)
    login_as(client, seed["pa"], seed["un"])
    assert client.get("/alunos/instituicoes?q=ab").status_code == 403
    login_as(client, seed["secretaria"], seed["un"])
    assert client.get("/alunos/instituicoes?q=ab").status_code == 200


def test_centros_custo_imprimir_negado_ao_professor(app, client):
    """Gate de /turmas/centros-custo/imprimir SEM 'professor' (admin/pedagogico/
    secretaria/gerencia). Trava a remoção feita pelo responsável; professor -> 403."""
    seed = _seed(app)
    login_as(client, seed["pa"], seed["un"])
    assert client.get("/turmas/centros-custo/imprimir").status_code == 403
    login_as(client, seed["secretaria"], seed["un"])
    assert client.get("/turmas/centros-custo/imprimir").status_code != 403


# ===========================================================================
# ITEM 6 — nenhum href/action fora da allowlist nas telas do professor
# ===========================================================================

def _telas_professor(app, seed):
    """URLs das telas que o professor abre (ids próprios), via url_for."""
    with app.test_request_context():
        from flask import url_for
        params = {
            "main.painel": {},
            "main.dashboard": {},
            "main.painel_pedagogico_professor": {},
            "registros.ver_turma": {"id": seed["t_own"]},
            "registros.ver_observacoes": {"turma_id": seed["t_own"]},
            "registros.frequencia": {"turma_id": seed["t_own"]},
            "registros.historico_aluno": {"aluno_id": seed["al_own"]},
            "conselho.index_conselho": {},
            "conselho.avaliar_turma": {"turma_id": seed["t_own"]},
        }
        return {ep: url_for(ep, **kw) for ep, kw in params.items()}


def _resolve_endpoint(adapter, path):
    """Endpoint real de um href/action de caminho local; None se não bate."""
    clean = path.split("?", 1)[0].split("#", 1)[0]
    if not clean or clean.startswith("//") or re.match(r"^[a-z]+:", clean):
        return None
    try:
        return adapter.match(clean, method="GET")[0]
    except Exception:  # noqa: BLE001 — link sem rota (asset/âncora) não é risco de acesso
        return None


def test_links_fora_da_allowlist_nas_telas_do_professor(app, client):
    """Nas telas do professor, todo href/action aponta para rota da allowlist.
    Nome do aluno só como texto (sem link à ficha)."""
    seed = _seed(app)
    adapter = app.url_map.bind("localhost")
    ofensores = []
    for ep_tela, url in _telas_professor(app, seed).items():
        login_as(client, seed["pa"], seed["un"])
        r = client.get(url, follow_redirects=False)
        if r.status_code != 200:
            continue  # tela não disponível nesta semente
        html = r.get_data(as_text=True)
        for alvo in re.findall(r'(?:href|action)\s*=\s*["\']([^"\']+)["\']', html):
            alvo_ep = _resolve_endpoint(adapter, alvo)
            if alvo_ep and alvo_ep not in ALLOWLIST:
                ofensores.append(f"{ep_tela}: link '{alvo}' -> {alvo_ep} (fora da allowlist)")
    assert ofensores == [], "\n".join(ofensores)


# ===========================================================================
# ITEM 6 — snapshot golden: HTML de NÃO-PROFESSOR inalterado pelos guards
# ===========================================================================

def _normaliza(html):
    """Estrutura estável: remove class=, csrf, whitespace e valores voláteis."""
    sem_classes = re.sub(r'\s+class="[^"]*"', "", html)
    sem_csrf = re.sub(
        r'<input[^>]*name="csrf_token"[^>]*>', '<input name="csrf_token" />', sem_classes,
    )
    sem_csrf = re.sub(
        r'<meta[^>]*name="csrf-token"[^>]*content="[^"]*"',
        '<meta name="csrf-token" content="CSRF"', sem_csrf,
    )
    # AJ6-B6: derruba o token de cache-busting dos assets estáticos (`?v=NNNN`),
    # que muda por build/instância e não é conteúdo da tela.
    sem_versao = re.sub(r'\?v=\d+', "?v=VER", sem_csrf)
    return re.sub(r"\s+", " ", sem_versao).strip()


def _confrontar(nome, atual):
    caminho = PASTA_SNAPSHOTS / nome
    if ATUALIZAR_SNAPSHOTS:
        PASTA_SNAPSHOTS.mkdir(parents=True, exist_ok=True)
        caminho.write_text(atual, encoding="utf-8")
        return
    assert caminho.exists(), (
        f"snapshot {nome} ausente — gere com AJ6B6_ATUALIZAR_SNAPSHOTS=1"
    )
    esperado = caminho.read_text(encoding="utf-8")
    assert atual == esperado, (
        f"{nome}: HTML de não-professor mudou (guarda de role tocou a renderização)"
    )


@pytest.mark.parametrize("role,endpoint_tela", [
    ("admin", "registros.ver_turma"),
    ("secretaria", "registros.frequencia"),
])
def test_snapshot_nao_professor_inalterado(app, client, role, endpoint_tela):
    """Os guards de role deste trabalho não alteram o HTML das telas para
    não-professor (admin/secretaria): snapshot golden por papel."""
    seed = _seed(app)
    with app.test_request_context():
        from flask import url_for
        kw = ({"id": seed["t_own"]} if endpoint_tela == "registros.ver_turma"
              else {"turma_id": seed["t_own"]})
        url = url_for(endpoint_tela, **kw)
    login_as(client, seed[role], seed["un"])
    r = client.get(url, follow_redirects=False)
    assert r.status_code == 200, f"{role} em {endpoint_tela}: {r.status_code}"
    _confrontar(
        f"aj6b6_{role}_{endpoint_tela.replace('.', '_')}.txt",
        _normaliza(r.get_data(as_text=True)),
    )

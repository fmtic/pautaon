# ruff: noqa: F811
"""AJ6-B7 — complemento da matriz de rotas do professor (base: AJ6-B6).

Cobre os quatro pontos que o B6 deixou em aberto, sempre em SQLite com
relógio congelado e nomes sintéticos:

    - Item 1 (métodos): DELETE/PUT/PATCH entram no inventário. O único
      endpoint fora de GET/POST do url_map é `conselho.deletar_periodo_conselho`
      (DELETE) — travado aqui, com professor 403 sobre JANELA EXISTENTE.
    - Item 2 (semente real): os 404 do B6 mascaravam falta de guarda. A
      semente B7 cria agendamento, janela de conselho, centro de custo,
      período e OFERTAS EXISTENTES; toda rota antes ambígua tem que negar
      por ROLE (403/redirect), nunca por 404 de recurso ausente.
    - Item 3 (detector de escrita): um 3xx não prova negação. Para cada
      requisição fora da allowlist (qualquer método) o teste compara a
      CONTAGEM DE LINHAS DE TODAS AS TABELAS antes/depois; qualquer
      movimento falha.
    - Item 4 (código morto): `/form` saiu do url_map (removido no B7); a
      trava vive em `test_aj6b6_matriz_rotas_professor.test_form_rota_morta_removida`.

Fixes travados por estes testes (antes/depois no relatório AJ6B7):
`servico_social.excluir_agendamento` (guarda SEC-04 referenciava
`responsavel_id`, atributo inexistente → 500 no próprio / exclusão alheia
liberada) e a remoção da rota morta `registros.form`.
"""

from datetime import timedelta

import pytest
import test_aj6b6_matriz_rotas_professor as aj6b6
from _helpers import login_as
from sqlalchemy import func, select

from app import db
from app.models import (
    AgendaServicoSocial,
    CentroCusto,
    PeriodoConselho,
)

pytestmark = pytest.mark.usefixtures("hoje_fixo")


def _seed_b7(app):
    """Semente B6 + RECURSOS EXISTENTES nos recursos que o B6 sondou com id
    ausente (404): agendamento do serviço social, janela de período de
    conselho e centro de custo da unidade (modelo de certificado)."""
    seed = aj6b6._seed(app)
    with app.app_context():
        ag = AgendaServicoSocial(
            titulo="[AJ6B7] Entrevista propria", categoria="rotina",
            data=aj6b6.HOJE, hora="09:00", user_id=seed["pa"],
        )
        ag_alheio = AgendaServicoSocial(
            titulo="[AJ6B7] Entrevista de outro", categoria="rotina",
            data=aj6b6.HOJE, hora="10:00", user_id=seed["pb"],
        )
        pc = PeriodoConselho(
            nome="[AJ6B7] Janela", data_inicio=aj6b6.HOJE,
            data_fim=aj6b6.HOJE + timedelta(days=7),
            conselho_final=False, periodo_letivo_id=seed["per"],
            unidade_id=seed["un"],
        )
        cc = CentroCusto(
            nome="[AJ6B7] Centro", ativo=True, unidade_id=seed["un"],
        )
        db.session.add_all([ag, ag_alheio, pc, cc])
        db.session.commit()
        seed.update(
            agendamento=ag.id, agendamento_alheio=ag_alheio.id,
            periodo_conselho=pc.id, centro_id=cc.id,
        )
    return seed


def _contar_tabelas(app):
    """{tabela: nº de linhas} para TODAS as tabelas do metadata."""
    with app.app_context():
        contagem = {}
        for nome, tabela in db.metadata.tables.items():
            if nome == "sqlite_master":  # artefato do reflexo no SQLite
                continue
            # COUNT(*) sobre a tabela inteira: funciona também em tabelas
            # de vínculo sem coluna `id`.
            contagem[nome] = db.session.execute(
                select(func.count()).select_from(tabela)
            ).scalar()
        return contagem


# ===========================================================================
# ITEM 1 — métodos fora de GET/POST
# ===========================================================================

def test_unico_endpoint_fora_de_get_post(app):
    """DELETE/PUT/PATCH: no url_map inteiro só existe UM endpoint fora de
    GET/POST — `conselho.deletar_periodo_conselho` (DELETE). A trava garante
    que rota nova com método exótico não entra de gaiota na varredura."""
    exoticos = set()
    for rule in app.url_map.iter_rules():
        extras = rule.methods - {"GET", "HEAD", "OPTIONS", "POST"}
        if extras:
            assert extras == {"DELETE"}
            exoticos.add(rule.endpoint)
    assert exoticos == {"conselho.deletar_periodo_conselho"}


def test_deletar_periodo_conselho_delete_negado_ao_professor(app, client):
    """Com a JANELA EXISTENTE (não 404 de recurso ausente), DELETE nega por
    ROLE: `_exigir_gestao_periodos_conselho` -> 403 (app/conselho.py:81-82,
    via :1234), e a linha de `periodo_conselho` sobrevive intacta."""
    seed = _seed_b7(app)
    antes = _contar_tabelas(app)
    login_as(client, seed["pa"], seed["un"])
    r = client.open(
        f"/api/conselho-periodo/{seed['periodo_conselho']}",
        method="DELETE", follow_redirects=False,
    )
    assert r.status_code == 403
    assert _contar_tabelas(app) == antes


# ===========================================================================
# ITEM 2 — negação por role sobre RECURSOS EXISTENTES (fim do 404-mascarado)
# ===========================================================================

# (endpoint, método, chave da semente para compor a URL)
# Todos exigem 403 LIMPO: recurso existe, e quem nega é a guarda de role.
RECURSOS_EXISTENTES = [
    ("servico_social.excluir_agendamento", "POST", "agendamento"),
    ("servico_social.excluir_agendamento", "POST", "agendamento_alheio"),
    ("registros.turma_ofertas", "GET", "t_own"),
    ("registros.turma_ofertas", "GET", "t_foreign"),
    ("registros.turma_oferta_nova", "POST", "t_own"),
    ("registros.turma_oferta_nova", "POST", "t_foreign"),
    ("registros.turma_oferta_editar", "POST", "o_own"),
    ("registros.turma_oferta_editar", "POST", "o_foreign"),
    ("registros.turma_oferta_principal", "POST", "o_own"),
    ("registros.turma_oferta_desativar", "POST", "o_own"),
    ("registros.enviar_modelo_certificado", "POST", "per"),
    ("registros.remover_modelo_certificado", "POST", "per"),
    ("registros.arquivo_modelo_certificado", "GET", "per"),
    ("conselho.informacoes", "GET", None),
    ("conselho.salvar_periodo_conselho", "POST", None),
    ("conselho.salvar_fechamento_data", "POST", "t_own"),
    ("conselho.salvar_fechamento_data", "POST", "t_foreign"),
    ("registros.turma_listar", "GET", None),
    ("registros.ver_documento_aluno", "GET", "al_own"),
    ("registros.ver_documento_aluno", "GET", "al_foreign"),
    ("registros.novo_aluno", "GET", None),
    ("registros.editar_aluno", "GET", "al_own"),
    ("registros.transferir_aluno", "GET", "al_own"),
    ("registros.excluir_aluno", "POST", "al_own"),
    ("registros.buscar_instituicoes", "GET", None),
]


# (endpoint -> parâmetros do url_map que não seguem a convenção da chave)
def _argumentos(endpoint, chave, seed):
    argumentos = {}
    if chave in ("t_own", "t_foreign"):
        nome = "turma_id" if endpoint.startswith("conselho.") else "id"
        argumentos[nome] = seed[chave]
    elif chave in ("o_own", "o_foreign"):
        argumentos["oferta_id"] = seed[chave]
    elif chave in ("al_own", "al_foreign"):
        if endpoint == "registros.ver_documento_aluno":
            argumentos["aluno_id"] = seed[chave]
            argumentos["doc_id"] = "doc_laudo"
        elif endpoint in ("registros.editar_aluno", "registros.excluir_aluno"):
            argumentos["id"] = seed[chave]
        else:
            argumentos["aluno_id"] = seed[chave]
    return argumentos


@pytest.mark.parametrize("endpoint,metodo,chave", RECURSOS_EXISTENTES)
def test_recurso_existente_negado_por_role(app, client, endpoint, metodo, chave):
    """Nada aqui é 404 de 'recurso que não existe': a semente criou o recurso.
    A negação tem vir por ROLE (403) — e sem escrever linha alguma."""
    seed = _seed_b7(app)
    if "modelo_certificado" in endpoint:
        url = f"/periodo-letivo/{seed['per']}/certificado-modelo/{seed['centro_id']}"
        if endpoint == "registros.remover_modelo_certificado":
            url += "/remover"
        elif endpoint == "registros.arquivo_modelo_certificado":
            url += "/arquivo"
    elif endpoint == "servico_social.excluir_agendamento":
        url = f"/servico-social/excluir-agendamento/{seed[chave]}"
    else:
        argumentos = _argumentos(endpoint, chave, seed)
        with app.test_request_context():
            from flask import url_for
            url = url_for(endpoint, **argumentos) if argumentos else url_for(endpoint)
    assert url, endpoint

    antes = _contar_tabelas(app)
    login_as(client, seed["pa"], seed["un"])
    if metodo == "GET":
        r = client.get(url, follow_redirects=False)
    else:
        r = client.post(url, data={}, follow_redirects=False)
    assert r.status_code == 403, f"{endpoint} {metodo}: {r.status_code} (esperado 403)"
    assert _contar_tabelas(app) == antes, f"{endpoint} {metodo} escreveu linhas"


# Negação por REDIRECT (flash + volta ao painel/página própria): o endpoint
# não serve corpo, mas a lista fica explícita para o detector não tratar 3xx
# como conteúdo. São os mesmos 302 da semente real do B7 (sonda B7).
REDIRECIONAM_NEGANDO = {
    "auth.aguardando_aprovacao",
    "auth.google_callback",
    "auth.google_confirmar_vinculo",
    "auth.google_login",
    "auth.painel_admin",
    "main.trocar_unidade",
    "registros.painel_professor",          # atalho legado -> painel canônico
    "servico_social.agendar_entrevista",   # flash "sem permissão" -> /painel
}


# ===========================================================================
# ITEM 3 — detector de escrita: 3xx não prova negação; contagem de linhas
# ===========================================================================

def test_varredura_full_methods_sem_escrita(app, client):
    """Para TODO endpoint fora da allowlist e TODO método do url_map: a
    resposta é negação (401/403/404/405 ou redirect) e a contagem de linhas
    de TODAS as tabelas é idêntica antes e depois da requisição. Um 200 com
    corpo, um 5xx ou QUALQUER linha movida (INSERT/UPDATE/DELETE) falha."""
    app.config["PROPAGATE_EXCEPTIONS"] = False
    seed = _seed_b7(app)
    violacoes = []
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.endpoint):
        ep = rule.endpoint
        if ep == "static" or ep in aj6b6.ALLOWLIST:
            continue
        for meth in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            url = aj6b6._sub(rule, seed, "own")
            if "excluir-agendamento" in rule.rule:
                url = f"/servico-social/excluir-agendamento/{seed['agendamento']}"
            login_as(client, seed["pa"], seed["un"])
            antes = _contar_tabelas(app)
            try:
                if meth == "GET":
                    r = client.get(url, follow_redirects=False)
                elif meth == "POST":
                    r = client.post(url, data={}, follow_redirects=False)
                else:
                    r = client.open(url, method=meth, follow_redirects=False)
                code = r.status_code
            except Exception as exc:  # noqa: BLE001 — a varredura não estoura
                violacoes.append(f"{ep} {meth}: EXC {type(exc).__name__}")
                continue
            depois = _contar_tabelas(app)
            if antes != depois:
                delta = {
                    t: (antes[t], depois[t])
                    for t in antes
                    if antes[t] != depois.get(t)
                }
                violacoes.append(f"{ep} {meth}: ESCRITA {delta}")
            negou = code in (401, 403, 404, 405) or 300 <= code < 400
            if not negou:
                violacoes.append(f"{ep} {meth}: status {code}")
    assert violacoes == [], "\n".join(violacoes)


def test_redirects_de_negacao_sao_os_conhecidos(app, client):
    """Os únicos não-403 fora da allowlist na semente real são redirects de
    negação (sem corpo) — lista fechada, travada contra novas surpresas."""
    app.config["PROPAGATE_EXCEPTIONS"] = False
    seed = _seed_b7(app)
    vistos = set()
    for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.endpoint):
        ep = rule.endpoint
        if ep == "static" or ep in aj6b6.ALLOWLIST:
            continue
        for meth in sorted(rule.methods - {"HEAD", "OPTIONS"}):
            url = aj6b6._sub(rule, seed, "own")
            login_as(client, seed["pa"], seed["un"])
            r = (client.get(url, follow_redirects=False) if meth == "GET"
                 else client.post(url, data={}, follow_redirects=False))
            if 300 <= r.status_code < 400:
                vistos.add(ep)
    assert vistos <= REDIRECIONAM_NEGANDO, vistos - REDIRECIONAM_NEGANDO

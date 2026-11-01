"""AJ3-E1 — Serviço Social acessa Relatórios (paridade com o pedagógico).

Cobertura do commit 8598145 (`ROLES_RELATORIOS` passou a incluir
`servico_social`). As regras verificadas aqui:

    T1 paridade de status: em TODA rota GET do blueprint `relatorios`, o
       `servico_social` da unidade A recebe o MESMO status que o `pedagogico`
       da unidade A (a decisão do AJ1 bloco A é "igual ao pedagógico").
    T2 nenhuma rota diverge nos dois sentidos proibidos: pedagógico 403 com
       serviço social 200, nem pedagógico 200 com serviço social 403.
    T3 isolamento de unidade: ficha 360° de aluno da unidade B = 404 (igual ao
       pedagógico); BI pedindo `unidade_id` de B = 403; painel e diário de
       bordo só mostram dados de A.
    T4 exportação XLSX (BI e relatório de alunos) pelo serviço social traz os
       dados de A e nenhum dado de B.
    T5 menu: o HTML do /painel do serviço social tem o link de Relatórios; o
       do professor não tem.
    T6 perfis que já eram bloqueados continuam bloqueados (professor 403 em
       todas as rotas; pendente nunca abre nenhuma). A secretaria está em
       `ROLES_RELATORIOS` hoje, então ela é coberta por paridade com o
       pedagógico — não por 403.
    T7 nenhuma rota GET ficou sem `@login_required`: o conjunto anônimo é
       exatamente o de 8 rotas públicas do S1 (mais `/static`).

Semente: duas unidades (A e B), usuários dos cinco perfis em A, um
serviço social em B, alunos/turmas/ofertas nos dois tenant. SQLite em memória
(fixtures `app`/`client` do conftest); nenhuma leitura dos bancos reais.
"""

import io
import zipfile
from datetime import date, time, timedelta

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    Unidade,
    User,
)

#: Nome sintético da unidade A/B — aparece (ou não) nos relatórios e XLSX.
UN_A_NOME = "Alfa AJ3 Unid"
UN_B_NOME = "Beta AJ3 Unid"
#: Turma e aluno da unidade B: se aparecerem em qualquer tela de A, há vazamento.
TURMA_B_SINTETICA = "TurmaBETAaj3NaoAparece"
ALUNO_A_SINTETICO = "AlunoALFAaj3Presente"
ALUNO_B_SINTETICO = "AlunoBETAaj3NaoAparece"

#: Rotas públicas históricas do S1 (as únicas que dispensam `@login_required`).
PUBLICAS_GET = {
    "/",
    "/login",
    "/auth/google/login",
    "/auth/google/callback",
    "/auth/google/confirmar-vinculo",
    "/politica_privacidade",
    "/termos_servico",
    "/logout",
}

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 12, 30)


# ---------------------------------------------------------------------------
# Semente
# ---------------------------------------------------------------------------

def _usuario(nome, email, role, unidade_id):
    user = User(
        name=nome, email=email, role=role, first_login=False,
        unidade_id=unidade_id,
    )
    user.set_password("SenhaLocal!123")
    db.session.add(user)
    db.session.flush()
    return user


def _turma(nome, periodo, professor, unidade):
    turma = Turma(
        nome=nome, turno="Manhã", data_inicio=periodo.data_inicio,
        data_fim=periodo.data_fim, periodo_letivo_id=periodo.id,
        unidade_id=unidade.id, professor_id=professor.id, ativo=True,
    )
    db.session.add(turma)
    db.session.flush()
    return turma


def _aluno(nome, unidade):
    aluno = Aluno(nome=nome, unidade_id=unidade.id, ativo=True)
    db.session.add(aluno)
    db.session.flush()
    return aluno


def _completa(app):
    """Unidades A e B com período, turma, oferta e aluno em cada uma."""
    with app.app_context():
        un_a = Unidade(nome=UN_A_NOME, ativo=True)
        un_b = Unidade(nome=UN_B_NOME, ativo=True)
        db.session.add_all([un_a, un_b])
        db.session.flush()

        ss_a = _usuario("SS Alfa", "ss.a.aj3@x.invalid", "servico_social", un_a.id)
        ped_a = _usuario("Ped Alfa", "ped.a.aj3@x.invalid", "pedagogico", un_a.id)
        prof_a = _usuario("Prof Alfa", "prof.a.aj3@x.invalid", "professor", un_a.id)
        sec_a = _usuario("Sec Alfa", "sec.a.aj3@x.invalid", "secretaria", un_a.id)
        adm_a = _usuario("Adm Alfa", "adm.a.aj3@x.invalid", "admin", un_a.id)
        pend_a = _usuario("Pendente Alfa", "pend.a.aj3@x.invalid", "pendente", un_a.id)
        ss_b = _usuario("SS Beta", "ss.b.aj3@x.invalid", "servico_social", un_b.id)

        per_a = PeriodoLetivo(
            nome="Periodo Alfa", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_a.id, ativo=True,
        )
        per_b = PeriodoLetivo(
            nome="Periodo Beta", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un_b.id, ativo=True,
        )
        db.session.add_all([per_a, per_b])
        db.session.flush()

        turma_a = _turma("TurmaALFAaj3", per_a, prof_a, un_a)
        turma_b = _turma(TURMA_B_SINTETICA, per_b, prof_a, un_b)

        curso_a = Curso(nome="Curso Alfa", unidade_id=un_a.id, ativo=True)
        curso_b = Curso(nome="Curso Beta", unidade_id=un_b.id, ativo=True)
        db.session.add_all([curso_a, curso_b])
        db.session.flush()

        oferta_a = nova_oferta(
            turma_a.id, curso_a.id, un_a.id, principal=True, professor_id=prof_a.id,
            dias_semana="Segunda, Quarta", hora_inicio=time(8), hora_fim=time(10),
        )
        oferta_b = nova_oferta(
            turma_b.id, curso_b.id, un_b.id, principal=True, professor_id=prof_a.id,
            dias_semana="Terça, Quinta", hora_inicio=time(14), hora_fim=time(16),
        )

        aluno_a = _aluno(ALUNO_A_SINTETICO, un_a)
        aluno_b = _aluno(ALUNO_B_SINTETICO, un_b)
        nova_inscricao(aluno_a.id, turma_a.id, oferta_a.id)
        nova_inscricao(aluno_b.id, turma_b.id, oferta_b.id)

        # Diário de bordo com texto sintético por unidade (T3 de isolamento).
        hoje = date.today()
        db.session.add_all([
            RegistroAula(
                turma_id=turma_a.id, turma_curso_id=oferta_a.id,
                data=hoje - timedelta(days=1),
                observacoes="DIARIO-AJ3-UNIDADE-A", unidade_id=un_a.id,
            ),
            RegistroAula(
                turma_id=turma_b.id, turma_curso_id=oferta_b.id,
                data=hoje - timedelta(days=1),
                observacoes="DIARIO-AJ3-UNIDADE-B", unidade_id=un_b.id,
            ),
        ])
        db.session.commit()

        return {
            "un_a": un_a.id, "un_b": un_b.id,
            "ss_a": ss_a.id, "ped_a": ped_a.id, "prof_a": prof_a.id,
            "sec_a": sec_a.id, "adm_a": adm_a.id, "pend_a": pend_a.id,
            "ss_b": ss_b.id,
            "per_a": per_a.id, "per_b": per_b.id,
            "turma_a": turma_a.id, "turma_b": turma_b.id,
            "oferta_a": oferta_a.id, "oferta_b": oferta_b.id,
            "aluno_a": aluno_a.id, "aluno_b": aluno_b.id,
        }


# ---------------------------------------------------------------------------
# Enumeração programática das rotas GET do blueprint `relatorios`
# ---------------------------------------------------------------------------

def _rotas_relatorios(app, ids):
    """`[(endpoint, url)]` de toda rota GET do blueprint `relatorios`.

    Parâmetros obrigatórios são preenchidos com ids da semente (ficha 360° de
    aluno de A) ou com um código de indicador real do catálogo; rota que
    permanecer com `<` no caminho é erro de teste (lista incompleta).
    """
    rotas = []
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods:
            continue
        if rule.endpoint.split(".")[0] != "relatorios":
            continue
        caminho = rule.rule
        if "<int:aluno_id>" in caminho:
            caminho = caminho.replace("<int:aluno_id>", str(ids["aluno_a"]))
        elif "<codigo>" in caminho:
            caminho = caminho.replace("<codigo>", "ALU-008")
        assert "<" not in caminho, f"rota sem id de teste: {rule.rule}"
        rotas.append((rule.endpoint, caminho))
    assert rotas, "nenhuma rota GET encontrada no blueprint relatorios"
    return sorted(rotas, key=lambda item: item[1])


def _dois_clientes(app, ids, ss_key="ss_a", ped_key="ped_a"):
    """Clientes autenticados do serviço social (A) e do pedagógico (A)."""
    cliente_ss = app.test_client()
    login_as(cliente_ss, ids[ss_key], ids["un_a"])
    cliente_ped = app.test_client()
    login_as(cliente_ped, ids[ped_key], ids["un_a"])
    return cliente_ss, cliente_ped


def _varrer(app, ids, clientes_fn):
    """Compara os status de dois clientes em cada rota; devolve a tabela."""
    rotas = _rotas_relatorios(app, ids)
    cliente_a, cliente_b = clientes_fn(app, ids)
    tabela = []
    for endpoint, url in rotas:
        tabela.append((endpoint, url, cliente_a.get(url).status_code,
                       cliente_b.get(url).status_code))
    return tabela


def _cliente(app, ids, chave):
    """Cliente autenticado para o usuário indicado pela chave da semente."""
    cliente = app.test_client()
    login_as(cliente, ids[chave], ids["un_a"])
    return cliente


def client_ok(cliente, url):
    """Auxílio de leitura: status 200 (a rota usa a unidade da sessão)."""
    assert cliente.get(url).status_code == 200, url


def corpo_painel(cliente):
    """Corpo do /painel (o perfil secretaria é redirecionado; o resto abre)."""
    resposta = cliente.get("/painel")
    if resposta.status_code in (301, 302):
        resposta = cliente.get(resposta.headers["Location"])
    assert resposta.status_code == 200, resposta.status_code
    return resposta.get_data(as_text=True)


# ---------------------------------------------------------------------------
# T1/T2 — paridade de acesso
# ---------------------------------------------------------------------------

def test_T1_servico_social_tem_o_mesmo_status_do_pedagogico_em_cada_rota(app):
    """Nenhuma rota do blueprint diverge entre serviço social e pedagógico."""
    tabela = _varrer(app, _completa(app), _dois_clientes)

    divergentes = [
        f"{url}: servico_social={ss} pedagogico={ped}"
        for _, url, ss, ped in tabela
        if ss != ped
    ]
    assert not divergentes, (
        "rotas com status diferente entre servico_social e pedagogico "
        f"(esperado paridade): {divergentes}"
    )
    # Paridade só é significativa se o pedagógico de fato entra nas rotas.
    assert all(ped != 403 for _, _, _, ped in tabela), (
        f"pedagogico recebeu 403 em alguma rota: {tabela}"
    )
    assert len(tabela) >= 13, f"lista de rotas pequena demais: {len(tabela)}"


def test_T2_nao_ha_rota_com_permissao_divergente_nos_dois_sentidos(app):
    """Nem 'só serviço social entra' nem 'só pedagógico entra' (T2)."""
    tabela = _varrer(app, _completa(app), _dois_clientes)

    so_ss = [url for _, url, ss, ped in tabela if ped == 403 and ss == 200]
    so_ped = [url for _, url, ss, ped in tabela if ped == 200 and ss == 403]
    print("\nrotas avaliadas:", [(url, ss, ped) for _, url, ss, ped in tabela])
    assert not so_ss, f"servico_social com acesso que o pedagogico nao tem: {so_ss}"
    assert not so_ped, f"pedagogico com acesso que o servico_social nao tem: {so_ped}"


def test_T2b_gerencia_e_admin_continuam_com_acesso_e_bloqueio_inalterado(app):
    """Perfis da lista original não mudaram: gerência entra, pendente não."""
    ids = _completa(app)

    def _gerencia_e_pendente(app_, ids_):
        de_gerencia = User(
            name="Ger Alfa", email="ger.a.aj3@x.invalid", role="gerencia",
            first_login=False, unidade_id=ids_["un_a"],
        )
        with app_.app_context():
            de_gerencia.set_password("SenhaLocal!123")
            db.session.add(de_gerencia)
            db.session.commit()
            ids_["ger_a"] = de_gerencia.id
        return _dois_clientes(app_, ids_, ss_key="ger_a", ped_key="ped_a")

    tabela = _varrer(app, ids, _gerencia_e_pendente)
    assert all(ger == ped for _, _, ger, ped in tabela), (
        f"gerencia divergiu do pedagogico: {tabela}"
    )

    # O perfil pendente é barrado pelo `before_request` global (redireciona
    # para a tela de espera), não pelo 403 da rota: o invariante é "nunca abre".
    cliente_pend = _cliente(app, ids, "pend_a")
    for endpoint, url in _rotas_relatorios(app, ids):
        resposta = cliente_pend.get(url)
        assert resposta.status_code in (301, 302, 403), (
            f"{endpoint} {url} abriu para o perfil pendente "
            f"({resposta.status_code})"
        )
        if resposta.status_code in (301, 302):
            destino = resposta.headers.get("Location", "")
            assert "aguardando" in destino, (
                f"{endpoint} redirecionou pendente para {destino!r}"
            )


# ---------------------------------------------------------------------------
# T3 — isolamento de unidade
# ---------------------------------------------------------------------------

def test_T3_ficha_de_aluno_da_unidade_b_e_404_para_os_dois_perfis(app):
    """Ficha 360° de aluno de B: 404 para o serviço social e para o pedagógico de A."""
    ids = _completa(app)
    cliente_ss, cliente_ped = _dois_clientes(app, ids)
    url = f"/relatorios/alunos/{ids['aluno_b']}/ficha"

    assert cliente_ped.get(url).status_code == 404
    assert cliente_ss.get(url).status_code == 404
    # O aluno da própria unidade continua abrindo para os dois.
    url_a = f"/relatorios/alunos/{ids['aluno_a']}/ficha"
    client_ok(cliente_ped, url_a)
    client_ok(cliente_ss, url_a)


def test_T3_bi_pedindo_unidade_b_e_recusado_para_os_dois_perfis(app):
    """`_escopar_unidade`: pedagógico e serviço social levam 403 na unidade alheia."""
    ids = _completa(app)
    cliente_ss, cliente_ped = _dois_clientes(app, ids)
    url = f"/relatorios/bi/indicador/ALU-008?unidade_id={ids['un_b']}"

    assert cliente_ped.get(url).status_code == 403
    assert cliente_ss.get(url).status_code == 403
    # Sem pedir unidade, a própria unidade é forçada e a rota abre.
    client_ok(cliente_ss, "/relatorios/bi/indicador/ALU-008")


def test_T3_painel_e_observacoes_so_mostram_a_unidade_a(app):
    """Nem o painel nem o diário global vazam turma/diário da unidade B."""
    ids = _completa(app)
    cliente_ss, cliente_ped = _dois_clientes(app, ids)
    painel = f"/relatorios/painel?periodo_letivo_id={ids['per_a']}"
    observacoes = f"/relatorios/observacoes?periodo_letivo_id={ids['per_a']}"

    for url in (painel, observacoes):
        for cliente, rotulo in ((cliente_ped, "pedagogico"), (cliente_ss, "servico_social")):
            resposta = cliente.get(url)
            assert resposta.status_code == 200, f"{rotulo} {url}"
            corpo = resposta.get_data(as_text=True)
            assert TURMA_B_SINTETICA not in corpo, f"{rotulo} viu turma B em {url}"
            assert "DIARIO-AJ3-UNIDADE-B" not in corpo, f"{rotulo} viu diário B em {url}"
    # A unidade A está de fato presente (sem isso a asserção acima seria vazia).
    corpo = cliente_ss.get(observacoes).get_data(as_text=True)
    assert "DIARIO-AJ3-UNIDADE-A" in corpo
    corpo_painel = cliente_ss.get(painel).get_data(as_text=True)
    assert "TurmaALFAaj3" in corpo_painel


def test_T3_servico_social_da_unidade_b_nao_ve_dados_da_a(app):
    """O serviço social de B é tratado igual: só vê a unidade dele."""
    ids = _completa(app)
    cliente_b = app.test_client()
    login_as(cliente_b, ids["ss_b"], ids["un_b"])

    corpo = cliente_b.get(
        f"/relatorios/observacoes?periodo_letivo_id={ids['per_b']}"
    ).get_data(as_text=True)
    assert "DIARIO-AJ3-UNIDADE-A" not in corpo
    assert "DIARIO-AJ3-UNIDADE-B" in corpo


# ---------------------------------------------------------------------------
# T4 — exportação XLSX pelo serviço social
# ---------------------------------------------------------------------------

def _textos_xlsx(resposta):
    """Concatena o XML do .xlsx (shared strings + sheets) para buscar rótulos."""
    assert resposta.status_code == 200, resposta.status_code
    with zipfile.ZipFile(io.BytesIO(resposta.data)) as pacote:
        textos = []
        for nome in pacote.namelist():
            if nome.endswith(".xml"):
                textos.append(pacote.read(nome).decode("utf-8", "replace"))
    return "\n".join(textos)


def test_T4_exportacao_xlsx_do_bi_traz_somente_a_unidade_a(app):
    """Exportação XLSX do indicador ALU-008 pelo serviço social de A."""
    ids = _completa(app)
    cliente_ss, cliente_ped = _dois_clientes(app, ids)
    url = "/relatorios/bi/exportar/xlsx?codigo=ALU-008"

    texto = _textos_xlsx(cliente_ss.get(url))
    assert UN_A_NOME in texto, "unidade A ausente do XLSX do BI"
    assert UN_B_NOME not in texto, "unidade B vazou no XLSX do BI"
    # O pedagógico recebe o mesmo recorte (o BI força a unidade da sessão).
    texto_ped = _textos_xlsx(cliente_ped.get(url))
    assert UN_A_NOME in texto_ped
    assert UN_B_NOME not in texto_ped


def test_T4_exportacao_xlsx_de_alunos_traz_somente_a_unidade_a(app):
    """Exportação XLSX do relatório de alunos pelo serviço social de A."""
    ids = _completa(app)
    cliente_ss, cliente_ped = _dois_clientes(app, ids)
    url = (
        f"/relatorios/relatorio_alunos/exportar?colunas=nome&colunas=nivel"
        f"&periodo_letivo_id={ids['per_a']}"
    )

    texto = _textos_xlsx(cliente_ss.get(url))
    assert ALUNO_A_SINTETICO in texto, "aluno de A ausente do XLSX"
    assert ALUNO_B_SINTETICO not in texto, "aluno de B vazou no XLSX"
    texto_ped = _textos_xlsx(cliente_ped.get(url))
    assert ALUNO_A_SINTETICO in texto_ped
    assert ALUNO_B_SINTETICO not in texto_ped


# ---------------------------------------------------------------------------
# T5 — menu lateral
# ---------------------------------------------------------------------------

def test_T5_menu_do_servico_social_tem_relatorios_e_o_professor_nao(app):
    """O serviço social vê o item Relatórios no painel; o professor não."""
    ids = _completa(app)

    corpo_ss = corpo_painel(_cliente(app, ids, "ss_a"))
    assert 'href="/relatorios' in corpo_ss, "servico_social sem link de Relatorios"
    assert "Painel Pedagógico" in corpo_ss

    corpo_prof = corpo_painel(_cliente(app, ids, "prof_a"))
    assert 'href="/relatorios' not in corpo_prof, "professor ganhou link de Relatorios"


# ---------------------------------------------------------------------------
# T6 — perfis que já eram 403
# ---------------------------------------------------------------------------

def test_T6_professor_e_secretaria_sem_mudanca_de_comportamento(app):
    """Professor segue de fora de todas as rotas; secretaria tem paridade."""
    ids = _completa(app)

    def _professor_contra_pedagogico(app_, ids_):
        return _dois_clientes(app_, ids_, ss_key="prof_a", ped_key="ped_a")

    tabela = _varrer(app, ids, _professor_contra_pedagogico)
    assert all(prof == 403 for _, _, prof, _ in tabela), (
        f"professor entrou em alguma rota de relatorio: {tabela}"
    )
    assert all(ped != 403 for _, _, _, ped in tabela)

    def _secretaria_contra_pedagogico(app_, ids_):
        return _dois_clientes(app_, ids_, ss_key="sec_a", ped_key="ped_a")

    tabela_sec = _varrer(app, ids, _secretaria_contra_pedagogico)
    # A secretaria ja estava em ROLES_RELATORIOS antes do AJ1: paridade total.
    assert all(sec == ped for _, _, sec, ped in tabela_sec), (
        f"secretaria divergiu do pedagogico: {tabela_sec}"
    )


# ---------------------------------------------------------------------------
# T7 — nenhuma rota sem @login_required
# ---------------------------------------------------------------------------

def test_T7_toda_rota_de_relatorio_exige_login(app):
    """Acesso anônimo a qualquer rota do blueprint cai na página de login."""
    ids = _completa(app)
    anonimo = app.test_client()
    for endpoint, url in _rotas_relatorios(app, ids):
        resposta = anonimo.get(url)
        assert resposta.status_code in (301, 302), (
            f"{endpoint} {url} respondeu {resposta.status_code} sem login"
        )
        assert "/login" in resposta.headers.get("Location", ""), (
            f"{endpoint} {url} nao redirecionou para /login"
        )


def test_T7_conjunto_de_rotas_publicas_nao_cresceu(app):
    """As únicas GET sem `@login_required` continuam sendo as 8 rotas do S1."""
    sem_login = set()
    for rule in app.url_map.iter_rules():
        if "GET" not in rule.methods or rule.endpoint == "static":
            continue
        if getattr(app.view_functions[rule.endpoint], "__wrapped__", None) is None:
            sem_login.add(rule.rule)

    assert sem_login == PUBLICAS_GET, (
        "conjunto de rotas publicas mudou; esperadas "
        f"{sorted(PUBLICAS_GET)}, obtidas {sorted(sem_login)}"
    )

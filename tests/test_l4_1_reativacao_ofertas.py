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

import pytest
from sqlalchemy import func

from _helpers import login_as, nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app.database import db
from app.models import (
    Aluno, ConselhoClasse, Curso, Frequencia, LogAcao, PeriodoLetivo, RegistroAula,
    Turma, TurmaCurso, Unidade, User,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _login(client, uid, unidade_id):
    login_as(client, str(uid), unidade_id)
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
        # G1/P2 (d6e7f8a9b0c1): oferta exige professor — a semente garante um.
        prof = User(
            name="Prof L41", email="prof.l41@example.com", role="professor",
            first_login=False,
        )
        db.session.add_all([un, admin, prof])
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
            return nova_oferta(
                turma.id, curso.id, un.id, principal=principal, professor_id=prof.id,
            )

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
            "prof": prof.id,
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
    """Reativação pela rota; `marcar=None` usa a pré-seleção do marcador.

    `marcar` enviado reproduz o formulário da lixeira: `selecao_explicita=1` +
    um `oferta_ids` por caixa marcada (lista vazia = nada marcado).
    """
    form = {}
    if confirmar:
        form["confirmar_periodo"] = "1"
    if marcar is not None:
        form["selecao_explicita"] = "1"
        form["oferta_ids"] = [str(oid) for oid in marcar]
    return client.post(
        f"/turmas/reativar/{dados['turma']}", data=form, follow_redirects=True
    )


def _estado(app, dados):
    """Leitura simples de turma/ofertas/inscrições depois da operação."""
    from app.models import Inscricao

    with app.app_context():
        return {
            "turma": Turma.query.get(dados["turma"]).ativo,
            "a": TurmaCurso.query.get(dados["a"]).ativo,
            "b": TurmaCurso.query.get(dados["b"]).ativo,
            "b_principal": TurmaCurso.query.get(dados["b"]).principal,
            "a_principal": TurmaCurso.query.get(dados["a"]).principal,
            "insc_a": Inscricao.query.get(dados["insc_a"]).ativo,
        }


def _preview(app, turma_id):
    from app.services.turma_curso import preview_reativacao

    with app.app_context():
        return preview_reativacao(Turma.query.get(turma_id))


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


# ---------------------------------------------------------------------------
# P4 — regras novas da reativação seletiva
# ---------------------------------------------------------------------------

def _marcador_de(app, turma_id):
    from app.services.turma_curso import ACAO_EXCLUSAO_LOGICA_TURMA, marcador_exclusao_turma

    with app.app_context():
        assert LogAcao.query.filter_by(acao=ACAO_EXCLUSAO_LOGICA_TURMA).count() == 1
        return marcador_exclusao_turma(turma_id)


def test_p4_marcador_grava_so_a_oferta_que_estava_ativa(app, client):
    """P1/P3: o LogAcao-marcador da exclusão lista só A (B já estava fora)."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    marcador = _marcador_de(app, dados["turma"])
    assert marcador is not None
    assert marcador["turma_id"] == dados["turma"]
    assert marcador["ofertas"] == [dados["a"]]
    assert dados["insc_a"] in marcador["inscricoes"]


def test_p4_preview_marca_somente_a_oferta_da_exclusao(app, client):
    """Pré-visualização (MESMA regra): B aparece, mas desmarcada e com a origem."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    pv = _preview(app, dados["turma"])
    por_id = {o["id"]: o for o in pv["ofertas"]}
    assert set(por_id) == {dados["a"], dados["b"]}
    assert por_id[dados["a"]]["reativar"] is True
    assert por_id[dados["a"]]["na_exclusao"] is True
    assert por_id[dados["b"]]["reativar"] is False
    assert por_id[dados["b"]]["na_exclusao"] is False
    assert pv["ofertas_reativar"] == 1
    assert pv["inscricoes_reativar"] == 1
    assert pv["tem_marcador"] is True
    assert pv["viola_principal"] is False


def test_p4_escolha_explicita_pode_reincluir_oferta_removida_antes(app, client):
    """O operador pode marcar B (aviso visível na UI): aí ela volta também."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    resp = _reativar(client, dados, marcar=[dados["a"], dados["b"]])
    assert resp.status_code == 200
    estado = _estado(app, dados)
    assert estado["turma"] is True
    assert estado["a"] is True and estado["b"] is True


def test_p4_sem_marca_nenhum_curso_recusa(app, client):
    """Desmarcar tudo na lixeira é recusa — a turma não volta "a meio"."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    resp = _reativar(client, dados, marcar=[])
    corpo = resp.get_data(as_text=True)
    assert "ao menos um curso" in corpo
    estado = _estado(app, dados)
    assert estado["turma"] is False and estado["a"] is False and estado["insc_a"] is False


def test_p4_inscricao_transferencia_e_desenturmada_nao_reativadas(app, client):
    """Só volta inscrição com motivo TURMA_DESATIVADA (regra do L4).

    Desenturmação manual (`DESENTURMADO`) e transferência (`TRANSFERENCIA`)
    já estavam inativas ANTES da exclusão e não foram tocadas por ela —
    reativá-las desfaria a decisão do responsável.
    """
    dados = _setup(app, client)
    with app.app_context():
        from app.models import Inscricao
        from app.utils.timezone import get_local_now

        carlos = Aluno(nome="Carlos L41", unidade_id=dados["un"], ativo=True)
        daniela = Aluno(nome="Daniela L41", unidade_id=dados["un"], ativo=True)
        db.session.add_all([carlos, daniela])
        db.session.flush()
        i_tr = nova_inscricao(
            carlos.id, dados["turma"], dados["a"], ativo=False,
            motivo_desativacao="TRANSFERENCIA", data_desativacao=get_local_now(),
        )
        i_de = nova_inscricao(
            daniela.id, dados["turma"], dados["a"], ativo=False,
            motivo_desativacao="DESENTURMADO", data_desativacao=get_local_now(),
        )
        ids = (i_tr.id, i_de.id)
        db.session.commit()
    _excluir(app, client, dados)

    pv = _preview(app, dados["turma"])
    assert pv["inscricoes_reativar"] == 1, "só a inscrição da Ana é candidata"

    resp = _reativar(client, dados)
    assert resp.status_code == 200
    with app.app_context():
        from app.models import Inscricao

        assert Inscricao.query.get(dados["insc_a"]).ativo is True
        assert Inscricao.query.get(ids[0]).ativo is False
        assert Inscricao.query.get(ids[1]).ativo is False


def test_p4_aluno_inativo_permanece_inativo(app, client):
    """Aluno inativo é conflito: a inscrição não volta e ele continua inativo."""
    dados = _setup(app, client)
    with app.app_context():
        evadido = Aluno(
            nome="Evadido L41", unidade_id=dados["un"], ativo=False,
        )
        db.session.add(evadido)
        db.session.flush()
        i_ev = nova_inscricao(evadido.id, dados["turma"], dados["a"])
        aluno_id, insc_id = evadido.id, i_ev.id
        db.session.commit()

    _excluir(app, client, dados)
    pv = _preview(app, dados["turma"])
    assert pv["conflitos"] == 1

    resp = _reativar(client, dados)
    assert resp.status_code == 200
    assert "permaneceram inativas" in resp.get_data(as_text=True)
    with app.app_context():
        from app.models import Inscricao

        assert Aluno.query.get(aluno_id).ativo is False
        assert Inscricao.query.get(insc_id).ativo is False
        assert Inscricao.query.get(insc_id).motivo_desativacao == "TURMA_DESATIVADA"
        assert Inscricao.query.get(dados["insc_a"]).ativo is True


def test_p4_principal_violado_recusa_tudo_sem_alteracao_parcial(app, client):
    """Seleção explícita que quebra o principal único não muda NADA."""
    dados = _setup(app, client, b_principal=True)
    with app.app_context():
        from app.services.turma_curso import definir_principal

        definir_principal(TurmaCurso.query.get(dados["a"]))

    _excluir(app, client, dados)
    resp = _reativar(client, dados, marcar=[dados["a"], dados["b"]])
    corpo = resp.get_data(as_text=True)
    assert "curso principal" in corpo
    estado = _estado(app, dados)
    assert estado["turma"] is False
    assert estado["a"] is False and estado["b"] is False
    assert estado["insc_a"] is False, "sem alteração parcial das inscrições"


def test_p4_oferta_de_outra_turma_na_selecao_recusada(app, client):
    """`oferta_ids` forjado (outra turma / oferta ativa) é recusa total."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    resp = _reativar(client, dados, marcar=[dados["a"], 999999])
    corpo = resp.get_data(as_text=True)
    assert "não são ofertas inativas desta turma" in corpo
    estado = _estado(app, dados)
    assert estado["turma"] is False and estado["a"] is False


def test_p4_lancamentos_diario_conselho_preservados_no_ciclo(app, client):
    """Excluir → reativar não apaga nem remapeia o histórico da turma."""
    dados = _setup(app, client)
    with app.app_context():
        from app.models.enums import EtapaConselho

        db.session.add(RegistroAula(
            turma_id=dados["turma"], turma_curso_id=dados["a"],
            data=date(2026, 3, 2), observacoes="Diário L41",
            unidade_id=dados["un"],
        ))
        db.session.add(ConselhoClasse(
            turma_id=dados["turma"], turma_curso_id=dados["a"],
            aluno_id=dados["ana"], etapa=EtapaConselho.INICIAL,
            unidade_id=dados["un"],
        ))
        db.session.commit()
        antes = {
            "freq": db.session.query(func.count(Frequencia.id)).scalar(),
            "diag": db.session.query(func.count(RegistroAula.id)).scalar(),
            "cons": db.session.query(func.count(ConselhoClasse.id)).scalar(),
        }

    _excluir(app, client, dados)
    resp = _reativar(client, dados)
    assert resp.status_code == 200

    with app.app_context():
        depois = {
            "freq": db.session.query(func.count(Frequencia.id)).scalar(),
            "diag": db.session.query(func.count(RegistroAula.id)).scalar(),
            "cons": db.session.query(func.count(ConselhoClasse.id)).scalar(),
        }
        assert depois == antes
        freq = Frequencia.query.filter_by(turma_id=dados["turma"]).one()
        assert freq.turma_curso_id == dados["a"] and freq.conceito == "A"
        conselho = ConselhoClasse.query.filter_by(turma_id=dados["turma"]).one()
        assert conselho.etapa == EtapaConselho.INICIAL


def _contar_selects(app, client, url):
    """Nº de SELECTs de uma requisição (guarda contra N+1 na lixeira)."""
    from sqlalchemy import event

    contador = {"n": 0}

    def _antes(conn, cursor, statement, params, context, executemany):
        if statement.strip()[:6].upper() == "SELECT":
            contador["n"] += 1

    with app.app_context():
        event.listen(db.engine, "before_cursor_execute", _antes)
        try:
            client.get(url)
        finally:
            event.remove(db.engine, "before_cursor_execute", _antes)
    return contador["n"]


def _excluida_sem_rota(app, dados, nome):
    """Outra turma já na lixeira (estado final da exclusão lógica)."""
    with app.app_context():
        turma = Turma(
            nome=nome, turno="Manhã", data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=dados["periodo"], unidade_id=dados["un"], ativo=False,
        )
        db.session.add(turma)
        db.session.flush()
        curso = Curso(nome=f"Curso {nome}", unidade_id=dados["un"], ativo=True)
        db.session.add(curso)
        db.session.flush()
        nova_oferta(
            turma.id, curso.id, dados["un"],
            principal=True, ativo=False, professor_id=dados["prof"],
        )
        db.session.commit()


def test_p4_selects_da_listagem_constantes_com_2_e_6_turmas(app, client):
    """A lixeira carrega ofertas/inscrições/marcadores em lote (sem N+1)."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    _excluida_sem_rota(app, dados, "Turma extra 2")

    _login(client, dados["admin"], dados["un"])
    client.get("/turmas/lixeira")  # aquece caches de conexão/schema
    com_2 = _contar_selects(app, client, "/turmas/lixeira")

    for i in range(3, 7):
        _excluida_sem_rota(app, dados, f"Turma extra {i}")
    com_6 = _contar_selects(app, client, "/turmas/lixeira")

    assert com_2 == com_6, (
        f"listagem subiu de {com_2} para {com_6} SELECTs ao passar de 2 para 6 "
        "turmas — N+1 de volta na lixeira"
    )


def test_p4_turma_sem_marcador_exige_escolha_explicita(app, client):
    """Turma excluída ANTES desta versão: nada pré-marcado, escolha obrigatória."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    with app.app_context():
        from app.services.turma_curso import ACAO_EXCLUSAO_LOGICA_TURMA

        LogAcao.query.filter_by(acao=ACAO_EXCLUSAO_LOGICA_TURMA).delete()
        db.session.commit()

    pv = _preview(app, dados["turma"])
    assert pv["tem_marcador"] is False
    assert pv["ofertas_reativar"] == 0, "sem marcador nada vem pré-marcado"
    assert all(o["na_exclusao"] is False for o in pv["ofertas"])

    resp = _reativar(client, dados)
    corpo = resp.get_data(as_text=True)
    assert "Escolha explicitamente" in corpo
    assert _estado(app, dados)["turma"] is False

    resp = _reativar(client, dados, marcar=[dados["a"]])
    assert resp.status_code == 200
    estado = _estado(app, dados)
    assert estado["turma"] is True and estado["a"] is True and estado["b"] is False


def test_p4_marcador_nao_altera_comportamento_do_excluir_turma(app, client):
    """O LogAcao-marcador é só leitura de estado: nada do L4 muda por causa dele.

    - exclusão LÓGICA: turma/ofertas/inscrições desativadas como antes,
      lançamentos preservados, destino da rota inalterado;
    - exclusão FÍSICA (turma sem histórico) não grava marcador — a turma
      some e não há nada a reativar.
    """
    from app.services.turma_curso import ACAO_EXCLUSAO_LOGICA_TURMA

    dados = _setup(app, client)
    resp = client.post(f"/turma/excluir/{dados['turma']}")
    assert resp.status_code == 302
    with app.app_context():
        from app.models import Inscricao

        assert Turma.query.get(dados["turma"]).ativo is False
        ofertas = TurmaCurso.query.filter_by(turma_id=dados["turma"]).all()
        assert len(ofertas) == 2 and all(not o.ativo for o in ofertas)
        insc = Inscricao.query.get(dados["insc_a"])
        assert insc.ativo is False and insc.motivo_desativacao == "TURMA_DESATIVADA"
        assert Frequencia.query.filter_by(turma_id=dados["turma"]).count() == 1
        assert LogAcao.query.filter_by(acao=ACAO_EXCLUSAO_LOGICA_TURMA).count() == 1

    # agora a física: outra turma, sem nenhum lançamento
    with app.app_context():
        turma = Turma(
            nome="Turma sem histórico", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=dados["periodo"],
            unidade_id=dados["un"], ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        curso = Curso(nome="Curso exclusão física", unidade_id=dados["un"], ativo=True)
        db.session.add(curso)
        db.session.flush()
        nova_oferta(
            turma.id, curso.id, dados["un"],
            principal=True, professor_id=dados["prof"],
        )
        tid = turma.id
        db.session.commit()
    client.post(f"/turma/excluir/{tid}")
    with app.app_context():
        assert db.session.get(Turma, tid) is None
        assert TurmaCurso.query.filter_by(turma_id=tid).count() == 0
        assert LogAcao.query.filter_by(acao=ACAO_EXCLUSAO_LOGICA_TURMA).count() == 1


def test_p4_reativar_duas_vezes_nao_duplica_marcador_de_exclusao(app, client):
    """Reativar não escreve marcador novo (e o 2º POST é recusado pela rota)."""
    dados = _setup(app, client)
    _excluir(app, client, dados)
    _marcador_de(app, dados["turma"])

    _reativar(client, dados)
    resp = _reativar(client, dados)
    assert "não encontrada na lixeira" in resp.get_data(as_text=True)

    with app.app_context():
        from app.services.turma_curso import ACAO_EXCLUSAO_LOGICA_TURMA

        assert LogAcao.query.filter_by(acao=ACAO_EXCLUSAO_LOGICA_TURMA).count() == 1
        assert LogAcao.query.filter_by(acao="Reativação de Turma").count() == 1


def _seed_perfil(app, role):
    """Semeia a turma e a IDENTIDADE que opera no teste (uma só por teste).

    O `app` do harness mantém um app context aberto durante o teste, então o
    `flask_login` guarda `current_user` no MESMO `g` de todas as requisições:
    trocar de usuário no meio não funciona (convenção T1 §5.6). Por isso quem
    executa a exclusão lógica é o próprio perfil sob teste — admin,
    secretaria e pedagógico têm essa permissão; para o professor a turma já
    entra na lixeira pela semente.
    """
    from app.services.turma_curso import MOTIVO_TURMA_DESATIVADA
    from app.utils.timezone import get_local_now

    inativa = role == "professor"
    with app.app_context():
        un = Unidade(nome="Unidade Perfil", ativo=True)
        db.session.add(un)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="Periodo Perfil", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()
        turma = Turma(
            nome="Turma Perfil", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=not inativa,
        )
        db.session.add(turma)
        db.session.flush()
        curso = Curso(nome="Curso Perfil", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        # A identidade do teste nasce antes da oferta: G1/P2 (d6e7f8a9b0c1)
        # exige professor na oferta — quem opera é o usuário do cenário.
        usuario = User(
            name=f"Perfil {role}", email=f"perfil.{role}.l41@example.com",
            role=role, first_login=False, unidade_id=un.id,
        )
        db.session.add(usuario)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, un.id,
            principal=True, ativo=inativa, professor_id=usuario.id,
        )
        aluno = Aluno(nome="Aluno Perfil", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        campos = (
            {"motivo_desativacao": MOTIVO_TURMA_DESATIVADA, "data_desativacao": get_local_now()}
            if inativa else {}
        )
        insc = nova_inscricao(aluno.id, turma.id, oferta.id, ativo=not inativa, **campos)
        db.session.add(Frequencia(
            aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
            data=date(2026, 3, 2), conceito="A", unidade_id=un.id,
        ))
        db.session.commit()
        return {
            "un": un.id, "turma": turma.id, "oferta": oferta.id,
            "insc": insc.id, "user": usuario.id,
        }


@pytest.mark.parametrize(
    "role,esperado",
    [("admin", 200), ("secretaria", 200), ("pedagogico", 200), ("professor", 403)],
)
def test_p4_perfis_da_lixeira_e_da_reativacao(app, client, role, esperado):
    """Secretaria/pedagógico/admin operam; professor é barrado (403)."""
    ids = _seed_perfil(app, role)
    _login(client, ids["user"], ids["un"])

    if esperado == 200:
        assert client.post(f"/turma/excluir/{ids['turma']}").status_code == 302

    assert client.get("/turmas/lixeira").status_code == esperado

    resp = client.post(f"/turmas/reativar/{ids['turma']}", data={
        "confirmar_periodo": "1", "selecao_explicita": "1",
        "oferta_ids": str(ids["oferta"]),
    })
    assert resp.status_code == (302 if esperado == 200 else 403)
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        assert turma.ativo is (esperado == 200)
        if esperado == 200:
            from app.models import Inscricao

            assert db.session.get(TurmaCurso, ids["oferta"]).ativo is True
            assert Inscricao.query.get(ids["insc"]).ativo is True

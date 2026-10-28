"""ETAPA D3b.2 — serviço único de frequência por oferta.

Cenário comum (semeado em `_base`):
    - Turma **Alfa** com 2 ofertas ativas (o1, o2):
        * Ana só na o1: A, A, J (J fora de tudo)
        * Beto só na o2: F
        * Caia nas duas: A, F na o1 e F na o2
    - Turma **Gema** com 1 oferta ativa (g) + 2 linhas LEGADAS
      (`turma_curso_id IS NULL`) do mesmo aluno: A(oferta), F(oferta), A, A
    - Turma **Zeta** com 1 oferta e NENHUMA frequência.

Parte 1 — CARACTERIZAÇÃO (escrita contra o código ATUAL, antes do refactor):
fixa os números de `Turma.freq_geral`, `Turma.freq_geral_oferta`,
`painel_pedagogico.frequencia.agregar_por_turma` e das visões por turma/período.
Depois da migração estes números não mudam — exceto os casos DECIDIDOS da
etapa (regra do legado na oferta única, faixas sobre valor arredondado e
"frequência da turma" da ficha = acumulado da oferta), cada um marcado no
teste com o motivo.

Parte 2 — REGRAS NOVAS (fronteiras de faixa, legado, lote, N+1, ficha,
relatório de frequência) adicionadas no passo 5.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitados do harness D5.2.

from datetime import date

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app.database import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    TemaAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


# ---------------------------------------------------------------------------
# Semente do cenário
# ---------------------------------------------------------------------------

def _base(app):
    """Unidade A + período + Alfa (2 ofertas), Gema (1 oferta + legado), Zeta."""
    with app.app_context():
        un = Unidade(nome="Unidade A", ativo=True)
        usuario = User(
            name="Admin Freq", email="admin.freq@example.com",
            role="admin", first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add_all([un, usuario])
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="Periodo Freq", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        def _turma(nome):
            t = Turma(
                nome=nome, turno="Manhã", data_inicio=DATA_INI,
                data_fim=DATA_FIM,
                periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
            )
            db.session.add(t)
            db.session.flush()
            return t

        def _oferta(turma, nome_curso):
            curso = Curso(nome=nome_curso, unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            return nova_oferta(turma.id, curso.id, un.id)

        alfa = _turma("Turma Alfa")
        o1 = _oferta(alfa, "Curso Alfa 1")
        o2 = _oferta(alfa, "Curso Alfa 2")
        gema = _turma("Turma Gema")
        g = _oferta(gema, "Curso Gema")
        zeta = _turma("Turma Zeta")
        z = _oferta(zeta, "Curso Zeta")

        ana = Aluno(nome="Ana", unidade_id=un.id, ativo=True)
        beto = Aluno(nome="Beto", unidade_id=un.id, ativo=True)
        caia = Aluno(nome="Caia", unidade_id=un.id, ativo=True)
        dan = Aluno(nome="Dan", unidade_id=un.id, ativo=True)
        db.session.add_all([ana, beto, caia, dan])
        db.session.flush()

        nova_inscricao(ana.id, alfa.id, o1.id)
        nova_inscricao(beto.id, alfa.id, o2.id)
        nova_inscricao(caia.id, alfa.id, o1.id)
        nova_inscricao(caia.id, alfa.id, o2.id)
        nova_inscricao(dan.id, gema.id, g.id)

        def _freq(aluno, turma, oferta_id, dia, conceito):
            db.session.add(Frequencia(
                aluno_id=aluno.id, turma_id=turma.id,
                turma_curso_id=oferta_id, data=dia,
                conceito=conceito, unidade_id=un.id,
            ))

        # Alfa/o1: Ana A, A, J; Caia A, F.
        _freq(ana, alfa, o1.id, date(2026, 3, 2), "A")
        _freq(ana, alfa, o1.id, date(2026, 3, 3), "A")
        _freq(ana, alfa, o1.id, date(2026, 3, 4), "J")
        _freq(caia, alfa, o1.id, date(2026, 3, 2), "A")
        _freq(caia, alfa, o1.id, date(2026, 3, 3), "F")
        # Alfa/o2: Beto F; Caia F.
        _freq(beto, alfa, o2.id, date(2026, 3, 2), "F")
        _freq(caia, alfa, o2.id, date(2026, 3, 9), "F")
        # Gema: oferta A, F + LEGADO (turma_curso_id NULL) A, A.
        _freq(dan, gema, g.id, date(2026, 3, 2), "A")
        _freq(dan, gema, g.id, date(2026, 3, 3), "F")
        db.session.add_all([
            Frequencia(aluno_id=dan.id, turma_id=gema.id, turma_curso_id=None,
                       data=date(2026, 3, 4), conceito="A", unidade_id=un.id),
            Frequencia(aluno_id=dan.id, turma_id=gema.id, turma_curso_id=None,
                       data=date(2026, 3, 5), conceito="A", unidade_id=un.id),
        ])
        db.session.commit()

        return {
            "un": un.id, "periodo": periodo.id, "user_id": usuario.id,
            "alfa": alfa.id, "o1": o1.id, "o2": o2.id,
            "gema": gema.id, "g": g.id,
            "zeta": zeta.id, "z": z.id,
            "ana": ana.id, "beto": beto.id, "caia": caia.id, "dan": dan.id,
        }


# ---------------------------------------------------------------------------
# Parte 1 — caracterização (números do código ATUAL)
# ---------------------------------------------------------------------------

def test_caracterizacao_freq_geral_e_por_oferta(app):
    """`freq_geral` soma TODAS as linhas da turma (refactor puro: número igual).
    `freq_geral_oferta` passa pela regra POR OFERTA + legado na oferta única
    (CASO DECIDIDO da etapa): o valor de Gema mudou de 50.0 (legado fora, no
    código anterior) para 75.0 (legado dentro, oferta única ativa)."""
    ids = _base(app)
    with app.app_context():
        alfa = db.session.get(Turma, ids["alfa"])
        gema = db.session.get(Turma, ids["gema"])
        zeta = db.session.get(Turma, ids["zeta"])

        # Alfa: presentes 3 (Ana 2A + Caia 1A) / contáveis 6 (3 F) = 50,0.
        assert alfa.freq_geral == 50.0
        assert alfa.freq_geral_oferta(ids["o1"]) == 75.0   # 3 pres / 4 (A,A,A,F)
        assert alfa.freq_geral_oferta(ids["o2"]) == 0.0    # 2 faltas
        # Gema: turma vê oferta+legado (3/4 = 75,0); a oferta é a única ativa
        # da turma, então o legado entra (regra D2 — caso decidido na etapa).
        assert gema.freq_geral == 75.0
        assert gema.freq_geral_oferta(ids["g"]) == 75.0
        # Zeta: sem registros contáveis → 0.0 dos dois lados.
        assert zeta.freq_geral == 0.0
        assert zeta.freq_geral_oferta(ids["z"]) == 0.0


def test_caracterizacao_agregar_por_turma_painel(app):
    """Código atual do agregador do painel (lista por aluno com J incluído
    na lista, fora das contagens)."""
    ids = _base(app)
    from app.relatorios.painel_pedagogico import frequencia as freq_painel

    with app.app_context():
        agg = freq_painel.agregar_por_turma([ids["alfa"], ids["gema"], ids["zeta"]])

    assert set(agg) == {ids["alfa"], ids["gema"]}  # Zeta sem linha não aparece
    alfa = agg[ids["alfa"]]
    assert (alfa.presentes, alfa.total, alfa.pct_turma) == (3, 6, 50.0)
    assert alfa.por_aluno_pct == {ids["ana"]: 100.0, ids["beto"]: 0.0,
                                  ids["caia"]: 33.3}
    # Lista por aluno preserva (data, conceito) inclusive o J.
    assert [c for _, c in alfa.por_aluno[ids["ana"]]] == ["A", "A", "J"]
    gema = agg[ids["gema"]]
    assert (gema.presentes, gema.total, gema.pct_turma) == (3, 4, 75.0)
    assert gema.por_aluno_pct == {ids["dan"]: 75.0}


def test_caracterizacao_visao_por_turma(app):
    ids = _base(app)
    from app.relatorios.painel_pedagogico import turma as turma_view

    with app.app_context():
        t = db.session.get(Turma, ids["alfa"])
        viz = turma_view.montar(t, ids["un"])

    assert viz["pct_turma"] == 50.0
    assert viz["pct_turma_str"] == "50.0%"
    assert viz["presencas"] == 3 and viz["faltas"] == 3 and viz["total_aulas"] == 6
    assert viz["faixas"] == {"hi": 1, "mid": 0, "lo": 2, "total": 3}
    assert [a["nome"] for a in viz["alunos"]] == ["Beto", "Caia", "Ana"]
    assert [a["pct"] for a in viz["alunos"]] == [0.0, 33.3, 100.0]


def test_caracterizacao_visao_por_periodo(app):
    ids = _base(app)
    from app.relatorios.painel_pedagogico import periodo as periodo_view

    with app.app_context():
        p = db.session.get(PeriodoLetivo, ids["periodo"])
        viz = periodo_view.montar(p, ids["un"])

    # Zeta sem frequência não entra no comparativo (§12.21).
    assert [t["nome"] for t in viz["turmas"]] == ["Turma Alfa", "Turma Gema"]
    assert [t["pct_turma"] for t in viz["turmas"]] == [50.0, 75.0]
    assert viz["totais"]["alunos"] == 4
    assert viz["totais"]["pct_geral"] == 60.0  # (3+3)/(6+4)
    assert viz["totais"]["faixas"] == {"hi": 1, "mid": 1, "lo": 2, "total": 4}


# ---------------------------------------------------------------------------
# Parte 2 — regras da etapa (serviço novo; escrita após o passo 3/4)
# ---------------------------------------------------------------------------

def test_percentual_regra_unica(app):
    """percentual(presentes, faltas): J fora, 1 casa, 0.0 sem contável."""
    from app.services.frequencia_oferta import percentual

    assert percentual(3, 0) == 100.0
    assert percentual(0, 2) == 0.0
    assert percentual(0, 0) == 0.0
    assert percentual(1, 2) == 33.3
    assert percentual(2, 1) == 66.7


def test_faixa_fronteiras_sobre_valor_arredondado(app):
    """Casos decididos: faixas comparam o valor JÁ ARREDONDADO a 1 casa
    (fecha a brecha do 89,96 que ficava fora das faixas)."""
    from app.services.frequencia_oferta import faixa

    assert faixa(74.9) == "lo"
    assert faixa(75.0) == "mid"
    assert faixa(89.94) == "mid"     # 89,9 → ainda mid
    assert faixa(89.95) == "hi"      # round(89.95,1)=90.0 (verificado no env)
    assert faixa(89.96) == "hi"      # 90,0 → fecha a brecha (antes: fora/sem)
    assert faixa(90.0) == "hi"
    # O arredondamento é aplicado sobre o valor cru:
    assert faixa(74.96) == "mid"     # 75,0 após arredondar


def test_legado_entra_so_na_oferta_unica_ativa(app):
    """Caso decidido (regra D2 da pauta): as linhas `turma_curso_id IS NULL`
    contam na oferta quando ela é a ÚNICA ativa da turma — e só nelas.

    Era `50.0` no código anterior (legado fora de `freq_geral_oferta`); o
    número passa a `75.0` em Gema por decisão da etapa, não por refactor.
    Alfa (2 ofertas) permanece inalterada.
    """
    ids = _base(app)
    with app.app_context():
        gema = db.session.get(Turma, ids["gema"])
        alfa = db.session.get(Turma, ids["alfa"])
        assert gema.freq_geral_oferta(ids["g"]) == 75.0   # 3 pres / 4 (com legado)
        assert gema.freq_geral == 75.0                    # por turma: como hoje
        assert alfa.freq_geral_oferta(ids["o1"]) == 75.0  # legado não migra p/ Alfa
        assert alfa.freq_geral_oferta(ids["o2"]) == 0.0


def test_percentuais_distintos_por_oferta_para_o_mesmo_aluno(app):
    """Caia: 1/2 na o1 (50,0) e 0/1 na o2 (0,0) — por oferta não se somam."""
    ids = _base(app)
    from app.services.frequencia_oferta import agregar_por_oferta

    with app.app_context():
        agg = agregar_por_oferta([ids["o1"], ids["o2"]])
    assert agg[ids["o1"]].por_aluno[ids["caia"]].pct == 50.0
    assert agg[ids["o2"]].por_aluno[ids["caia"]].pct == 0.0
    assert agg[ids["o1"]].pct == 75.0
    assert agg[ids["o2"]].pct == 0.0


def test_agregar_por_oferta_uma_consulta_de_frequencia(app):
    """Sem N+1: em lote, UMA consulta na tabela `frequencia`."""
    ids = _base(app)
    from sqlalchemy import event
    from app import db as _db
    from app.services.frequencia_oferta import agregar_por_oferta

    contadas: list[str] = []

    def _anota(conn, cursor, statement, *a):
        if "frequencia" in statement.lower():
            contadas.append(statement)

    engine = _db.engine
    event.listen(engine, "before_cursor_execute", _anota)
    try:
        with app.app_context():
            agg = agregar_por_oferta([ids["o1"], ids["o2"], ids["g"], ids["z"]])
    finally:
        event.remove(engine, "before_cursor_execute", _anota)

    assert set(agg) == {ids["o1"], ids["o2"], ids["g"], ids["z"]}
    assert agg[ids["z"]].total == 0
    assert len(contadas) == 1, f"esperava 1 consulta de frequência, houve {len(contadas)}"


def test_visao_por_periodo_uma_consulta_de_frequencia(app):
    """A visão por período lê frequência de todas as turmas em UMA consulta."""
    ids = _base(app)
    from sqlalchemy import event
    from app import db as _db
    from app.relatorios.painel_pedagogico import periodo as periodo_view

    contadas: list[str] = []

    def _anota(conn, cursor, statement, *a):
        if "from frequencia" in statement.lower():
            contadas.append(statement)

    engine = _db.engine
    event.listen(engine, "before_cursor_execute", _anota)
    try:
        with app.app_context():
            p = db.session.get(PeriodoLetivo, ids["periodo"])
            viz = periodo_view.montar(p, ids["un"])
    finally:
        event.remove(engine, "before_cursor_execute", _anota)

    assert len(contadas) == 1, f"esperava 1 leitura de frequência, houve {len(contadas)}"
    assert [t["pct_turma"] for t in viz["turmas"]] == [50.0, 75.0]


def test_ficha_pct_turma_usa_acumulado_da_oferta(app, client):
    """Caso decidido (passo 2.4 do desenho): "frequência da turma" da ficha é o
    ACUMULADO da oferta, não o último ponto da série semanal (que é 0.0 quando
    a última semana do período não tem aula lançada).

    Ana na o1: aulas em 02-03 (semana 1); semanas seguintes vazias → série
    semanal termina em 0.0. Acumulado da oferta p1: presentes 3 (Ana A,A +
    Caia A) / contáveis 4 → 75,0.
    """
    ids = _base(app)
    from test_conselho_oferta import _loga

    _loga(client, ids, unidade_id=ids["un"])
    with app.app_context():
        from app.models import Inscricao

        insc = Inscricao.query.filter_by(
            aluno_id=ids["ana"], turma_curso_id=ids["o1"]
        ).first()
        insc_id = insc.id
    resposta = client.get(
        f"/relatorios/alunos/{ids['ana']}/ficha?turma_id={ids['alfa']}"
        f"&oferta_sel={ids['o1']}"
    )
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    with app.app_context():
        from app.relatorios.painel_pedagogico import ficha_aluno
        from app.models import Aluno as _Aluno, Turma as _Turma

        aluno = db.session.get(_Aluno, ids["ana"])
        turma = db.session.get(_Turma, ids["alfa"])
        insc = db.session.get(Inscricao, insc_id)
        ctx = ficha_aluno.montar(aluno, turma, insc)
    freq = ctx["frequencia"]
    # Último ponto da série seria 0.0 (semana final sem aula); acumulado = 75,0.
    assert freq["serie_turma"][-1] == 0.0
    assert freq["pct_turma"] == 75.0
    assert "75.0%" in corpo


def test_frequencia_relatorio_turma_invalida_nao_eh_500(app, client):
    """`?turma=abc` não derruba a página (500); responde 200 sem seleção."""
    ids = _base(app)
    from test_conselho_oferta import _loga

    with app.app_context():
        usuario = db.session.get(User, ids["user_id"])
        usuario.role = "pedagogico"  # a rota é exclusiva do perfil pedagógico
        db.session.commit()

    _loga(client, ids, unidade_id=ids["un"])
    resposta = client.get("/frequencia_relatorio?turma=abc")
    assert resposta.status_code == 200


def test_frequencia_relatorio_aluno_em_2_ofertas_sem_duplicar(app, client):
    """Caia tem inscrição ativa nas 2 ofertas da Alfa: UMA linha por aluno no
    relatório (antes o join sem distinct duplicava a linha)."""
    ids = _base(app)
    from test_conselho_oferta import _loga

    with app.app_context():
        usuario = db.session.get(User, ids["user_id"])
        usuario.role = "pedagogico"
        db.session.commit()

    _loga(client, ids, unidade_id=ids["un"])
    resposta = client.get(f"/frequencia_relatorio?turma={ids['alfa']}")
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    assert corpo.count("Caia") == 1
    assert corpo.count("Ana") == 1


# ---------------------------------------------------------------------------
# Regression — temas marcados do dia NUNCA são None na pauta
# (TypeError: argument of type 'NoneType' is not a container or iterable)
# ---------------------------------------------------------------------------

def _tema_da_oferta(app, oferta_id, titulo):
    """Cria um `TemaAula` ativo no curso da oferta — é a lista que a pauta
    percorre em `tema.id in tema_selecionado`. Sem tema, o loop não executa e a
    tela nem chegava a quebrar."""
    with app.app_context():
        oferta = db.session.get(TurmaCurso, oferta_id)
        tema = TemaAula(
            curso_id=oferta.curso_id, unidade_id=oferta.unidade_id,
            titulo=titulo, ordem=1, ativo=True,
        )
        db.session.add(tema)
        db.session.commit()
        return tema.id


def _linha_do_tema(corpo, tema_id):
    """Tag `<input>` do checkbox do tema (para afirmar marcado/desmarcado)."""
    import re

    match = re.search(rf'<input[^>]*id="tema-aula-{tema_id}"[^>]*>', corpo)
    assert match, f"checkbox do tema {tema_id} não foi renderizado"
    return match.group(0)


def test_pauta_dia_sem_diario_com_temas_nao_eh_500(app, client):
    """Dia ainda não lançado é o estado mais comum da pauta, e era o que
    quebrava: sem `RegistroAula`, `carregar_frequencias` devolvia `None` como
    temas marcados e o template testava `tema.id in None`.

    Gema tem 1 oferta ativa (uso automático, sem seletor) e agora 1 tema no
    curso da oferta."""
    ids = _base(app)
    from test_conselho_oferta import _loga

    tema_id = _tema_da_oferta(app, ids["g"], "Tema Gema sem diario")
    _loga(client, ids, unidade_id=ids["un"])

    resposta = client.get(f"/frequencia?turma_id={ids['gema']}&data=2026-03-10")
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    # O loop de temas executou (sem isso o teste passaria mesmo com o bug).
    assert "Tema Gema sem diario" in corpo
    assert "checked" not in _linha_do_tema(corpo, tema_id)


def test_pauta_data_fora_do_formato_iso_nao_eh_500(app, client):
    """`parse_date` só aceita `YYYY-MM-DD`; `?data=10/03/2026` cai no
    early-return de `carregar_frequencias`, que também devolvia `None`. A tela
    deve responder 200 com a pauta vazia e o tema desmarcado."""
    ids = _base(app)
    from test_conselho_oferta import _loga

    tema_id = _tema_da_oferta(app, ids["g"], "Tema Gema data invalida")
    _loga(client, ids, unidade_id=ids["un"])

    resposta = client.get(f"/frequencia?turma_id={ids['gema']}&data=10/03/2026")
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    assert "Tema Gema data invalida" in corpo
    assert "checked" not in _linha_do_tema(corpo, tema_id)


def test_carregar_frequencias_sempre_devolve_lista_de_temas(app):
    """Contrato da função (fonte do bug acima): o segundo elemento é sempre
    sequência — inclusive sem diário e com data inválida."""
    from app.utils.logica import carregar_frequencias

    ids = _base(app)
    _tema_da_oferta(app, ids["g"], "Tema do contrato")
    with app.app_context():
        # Dia sem RegistroAula:
        _, temas, _ = carregar_frequencias(
            ids["gema"], date(2026, 3, 11), turma_curso_id=ids["g"],
        )
        assert temas == []
        # Data não parseável (early-return):
        _, temas_ruim, _ = carregar_frequencias(ids["gema"], "11/03/2026")
        assert temas_ruim == []

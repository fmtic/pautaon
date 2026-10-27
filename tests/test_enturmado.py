"""ETAPA D3b.3 — definição única de "enturmado".

Cenário comum (semeado em `_base`), unidade A (e uma turma/aluno na unidade B):
    - Período **P1** em andamento (2026-01-01 → 2027-12-30).
    - Período **P2** encerrado (2025; `data_fim` no passado → regra M4).
    - Período **P3** na unidade B.
    - Turma **Alfa** (P1, ativa): ofertas ativas o1, o2.
    - Turma **Beta** (P1, INATIVA — turma desativada): oferta ob ativa.
    - Turma **Delta** (P1, ativa): oferta od INATIVA em período EM ANDAMENTO.
    - Turma **Gema** (P2, ativa): oferta og INATIVA em período ENCERRADO (M4).
    - Turma **Bela** (un B, P3, ativa): oferta b1 ativa.
    - Ana: ativa, inscrição ativa na o1                       → enturmada.
    - Beto: ativo, inscrição INATIVA na o1 (turma ativa)      → fora.
    - Caio: cadastro INATIVO (Aluno.ativo=False) com inscrição ativa na o1 → fora.
    - Enzo: ativo, inscrição ativa na turma DESATIVADA (Beta) → fora.
    - Fanny: ativo, inscrição ativa em oferta INATIVA em período EM ANDAMENTO → fora.
    - Gaby: ativo, inscrição ativa em oferta INATIVA em período ENCERRADO → dentro (M4).
    - Henry: ativo, inscrição ativa nas DUAS ofertas da Alfa (mesma turma).
    - Iris: ativo, inscrição ativa na o1 (Alfa/P1) E na og (Gema/P2) — duas turmas.
    - Jack: unidade B, inscrição ativa na b1.

Parte 1 — CARACTERIZAÇÃO (escrita contra o código ATUAL, antes do refactor):
fixa os números dos consumidores do Passo 1(a) — card "Enturmados" de `/alunos`,
`PeriodoLetivo.alunos_enturmados()`, `total_alunos` do `/professor/painel`, o
filtro de período de `relatorios/shared.py`, o BI (ALU-008 com período) e o
status canônico (`status_alunos`, que NÃO deve mudar).

Parte 2 — EQUIVALÊNCIA (adicionada no passo 5): todos os consumidores migrados
devem retornar o MESMO conjunto de alunos que o predicado canônico.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitados do harness D5.2.

import re
from datetime import date, datetime

from _helpers import nova_inscricao, nova_oferta
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app.database import db
from app.models import (
    Aluno,
    Curso,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)

INI_ANDAMENTO = date(2026, 1, 1)
FIM_ANDAMENTO = date(2027, 12, 30)
INI_ENCERRADO = date(2025, 1, 1)
FIM_ENCERRADO = date(2025, 12, 31)


# ---------------------------------------------------------------------------
# Semente do cenário
# ---------------------------------------------------------------------------

def _base(app):
    """Unidades A/B + 3 períodos + 5 turmas + 9 alunos (ver docstring)."""
    with app.app_context():
        un = Unidade(nome="Unidade A", ativo=True)
        un_b = Unidade(nome="Unidade B", ativo=True)
        usuario = User(
            name="Admin Ent", email="admin.ent@example.com",
            role="admin", first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        db.session.add_all([un, un_b, usuario])
        db.session.flush()

        p1 = PeriodoLetivo(
            nome="P1 Andamento", data_inicio=INI_ANDAMENTO,
            data_fim=FIM_ANDAMENTO, unidade_id=un.id, ativo=True,
        )
        p2 = PeriodoLetivo(
            nome="P2 Encerrado", data_inicio=INI_ENCERRADO,
            data_fim=FIM_ENCERRADO, unidade_id=un.id, ativo=True,
        )
        p3 = PeriodoLetivo(
            nome="P3 Unidade B", data_inicio=INI_ANDAMENTO,
            data_fim=FIM_ANDAMENTO, unidade_id=un_b.id, ativo=True,
        )
        db.session.add_all([p1, p2, p3])
        db.session.flush()

        def _turma(nome, periodo, unidade, ativo=True):
            t = Turma(
                nome=nome, turno="Manhã", data_inicio=periodo.data_inicio,
                data_fim=periodo.data_fim,
                periodo_letivo_id=periodo.id, unidade_id=unidade.id,
                ativo=ativo,
            )
            db.session.add(t)
            db.session.flush()
            return t

        def _oferta(turma, nome_curso, unidade, ativo=True):
            curso = Curso(nome=nome_curso, unidade_id=unidade.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            return nova_oferta(turma.id, curso.id, unidade.id, ativo=ativo)

        alfa = _turma("Turma Alfa", p1, un)
        beta = _turma("Turma Beta", p1, un, ativo=False)
        delta = _turma("Turma Delta", p1, un)
        gema = _turma("Turma Gema", p2, un)
        bela = _turma("Turma Bela", p3, un_b)

        o1 = _oferta(alfa, "Curso Alfa 1", un)
        o2 = _oferta(alfa, "Curso Alfa 2", un)
        ob = _oferta(beta, "Curso Beta", un)
        od = _oferta(delta, "Curso Delta", un, ativo=False)
        og = _oferta(gema, "Curso Gema", un, ativo=False)
        b1 = _oferta(bela, "Curso Bela", un_b)

        alunos = {}
        for nome, ativo in [
            ("Ana", True), ("Beto", True), ("Caio", False), ("Enzo", True),
            ("Fanny", True), ("Gaby", True), ("Henry", True), ("Iris", True),
        ]:
            alunos[nome.lower()] = Aluno(
                nome=nome, unidade_id=un.id, ativo=ativo,
            )
        alunos["jack"] = Aluno(nome="Jack", unidade_id=un_b.id, ativo=True)
        db.session.add_all(list(alunos.values()))
        db.session.flush()

        # Inscrições (ver tabela do docstring do módulo).
        nova_inscricao(alunos["ana"].id, alfa.id, o1.id)
        nova_inscricao(
            alunos["beto"].id, alfa.id, o1.id,
            ativo=False, data_desativacao=datetime(2026, 3, 1),
            motivo_desativacao="DESISTENCIA",
        )
        nova_inscricao(alunos["caio"].id, alfa.id, o1.id)
        nova_inscricao(alunos["enzo"].id, beta.id, ob.id)
        nova_inscricao(alunos["fanny"].id, delta.id, od.id)
        nova_inscricao(alunos["gaby"].id, gema.id, og.id)
        nova_inscricao(alunos["henry"].id, alfa.id, o1.id)
        nova_inscricao(alunos["henry"].id, alfa.id, o2.id)
        nova_inscricao(alunos["iris"].id, alfa.id, o1.id)
        nova_inscricao(alunos["iris"].id, gema.id, og.id)
        nova_inscricao(alunos["jack"].id, bela.id, b1.id)

        db.session.commit()
        return {
            "un": un.id, "un_b": un_b.id,
            "p1": p1.id, "p2": p2.id, "p3": p3.id,
            "user_id": usuario.id,
            "alfa": alfa.id, "o1": o1.id, "o2": o2.id,
            "beta": beta.id, "ob": ob.id,
            "delta": delta.id, "od": od.id,
            "gema": gema.id, "og": og.id,
            "bela": bela.id, "b1": b1.id,
            **{k: a.id for k, a in alunos.items()},
        }


def _numeiro(corpo, padrao):
    m = re.search(padrao, corpo)
    assert m, f"padrão {padrao!r} não encontrado na página"
    return int(m.group(1))


# ---------------------------------------------------------------------------
# Parte 1 — caracterização (números do código ATUAL)
# ---------------------------------------------------------------------------

def test_caracterizacao_card_enturmados_alunos(app, client):
    """`/alunos`: card "Enturmados" — ANTES usava `Aluno.turmas.any(Turma.ativo)`:
    QUALQUER linha de inscrição (até inativa) em turma ativa contava.

    Antes (código anterior à D3b.3): 6 (Ana, Beto-inativa!, Fanny-oferta
    inativa!, Gaby, Henry, Iris). Depois (definição única): 4 — Ana, Gaby
    (M4), Henry, Iris; saem Beto (inscrição inativa) e Fanny (oferta
    inativa em período em andamento). Cadastros ativos da unidade A: 7 (não
    muda — é o outro número do card).
    """
    ids = _base(app)
    from test_conselho_oferta import _loga

    _loga(client, ids, unidade_id=ids["un"])
    resposta = client.get("/alunos")
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    assert _numeiro(corpo, r'text-primary">(\d+)</strong>') == 7
    assert _numeiro(corpo, r'text-success">(\d+)</strong>') == 4


def test_caracterizacao_alunos_enturmados_periodos(app):
    """`PeriodoLetivo.alunos_enturmados()` — ANTES não filtrava `Aluno.ativo`,
    `Inscricao.ativo` nem `Turma.ativo` (a definição mais frouxa, Fonte B).

    P1: antes 7 (Ana, Beto, Caio-cadastro inativo!, Enzo-turma
    desativada!, Fanny, Henry, Iris) → depois 3 (Ana, Henry, Iris).
    P2: 2 (Gaby-M4, Iris) em ambos — nenhuma linha do P2 era espúria.
    P3: 1 (Jack) em ambos.
    """
    ids = _base(app)
    with app.app_context():
        assert db.session.get(PeriodoLetivo, ids["p1"]).alunos_enturmados() == 3
        assert db.session.get(PeriodoLetivo, ids["p2"]).alunos_enturmados() == 2
        assert db.session.get(PeriodoLetivo, ids["p3"]).alunos_enturmados() == 1


def test_caracterizacao_total_alunos_painel_professor(app, client):
    """/professor/painel: ANTES `Inscricao.ativo` + `Aluno.ativo` + turma da
    lista, SEM oferta efetiva.

    Antes: 5 (Ana, Fanny-oferta inativa em andamento!, Gaby, Henry, Iris).
    Depois: 4 — sai Fanny (oferta od não é efetiva); entra ninguém.
    """
    ids = _base(app)
    from test_conselho_oferta import _loga

    _loga(client, ids, unidade_id=ids["un"])
    resposta = client.get("/professor/painel")
    assert resposta.status_code == 200
    corpo = resposta.data.decode("utf-8")
    assert _numeiro(
        corpo, r'Meus Alunos</div>\s*<div class="fs-3 fw-bold lh-sm">(\d+)</div>'
    ) == 4


def test_caracterizacao_filtro_periodo_shared(app):
    """`relatorios/shared.aplicar_filtros_alunos` (período) — ANTES join por
    `Aluno.turmas` sem `ativo` em inscrição/turma/oferta.

    Antes (com o filtro P1 sobre a query dos consumidores, `Aluno.ativo=True`):
    6 ids — Ana, Beto, Enzo, Fanny, Henry, Iris. Depois: 3 — Ana, Henry,
    Iris (Beto sem inscrição ativa; Enzo em turma desativada; Fanny com
    oferta não efetiva). O join que duplicava Henry foi trocado por EXISTS.
    """
    ids = _base(app)
    with app.app_context():
        from app.relatorios.shared import aplicar_filtros_alunos

        query = aplicar_filtros_alunos(
            Aluno.query.filter_by(ativo=True),
            {"periodo_letivo_id": ids["p1"]},
        )
        obtidos = {a.id for a in query}
        esperado = {ids["ana"], ids["henry"], ids["iris"]}
        assert obtidos == esperado


def test_caracterizacao_bi_alu008(app):
    """BI ALU-008 COM período usa `cond_inscricao_enturmada` (pré-D3b.3):
    inscrição ativa + turma ativa + oferta efetiva, mas NÃO filtra
    `Aluno.ativo` — Caio (cadastro inativo) continua dentro.

    P1: Ana, Caio, Henry, Iris → 4. P2: Gaby, Iris → 2 (Gaby entra pela
    regra M4: oferta inativa em período encerrado conta).
    """
    ids = _base(app)
    with app.app_context():
        from app.relatorios.bi_alunos import alunos_por_unidade

        res1 = alunos_por_unidade(unidade_id=ids["un"], periodo_letivo_id=ids["p1"])
        assert res1 and res1[0]["valor"] == 4
        res2 = alunos_por_unidade(unidade_id=ids["un"], periodo_letivo_id=ids["p2"])
        assert res2 and res2[0]["valor"] == 2


def test_caracterizacao_status_canonico(app):
    """Status canônico (`status_alunos`) — NÃO pode mudar na D3b.3 (o espelho
    `_cond_oferta_efetiva` é substituído pelo predicado do módulo neutro com
    comportamento idêntico).

    P1: Ana/Henry Novo; Iris Retornante (histórico no P2, fora da janela);
    Beto/Fanny Desenturmado; Gaby Não Renovado; Enzo Outros (turma desativada
    não gera vínculo nem histórico). Caio nem entra (cadastro inativo).
    Enturmados (Novo+Renovado+Retornante) = {Ana, Henry, Iris} → 3.
    """
    ids = _base(app)
    with app.app_context():
        from app.models.enums import StatusAluno
        from app.services.aluno_status import status_alunos

        resultado = status_alunos(ids["p1"])
        assert resultado[ids["ana"]] is StatusAluno.NOVO
        assert resultado[ids["henry"]] is StatusAluno.NOVO
        assert resultado[ids["iris"]] is StatusAluno.RETORNANTE
        assert resultado[ids["beto"]] is StatusAluno.DESENTURMADO
        assert resultado[ids["fanny"]] is StatusAluno.DESENTURMADO
        assert resultado[ids["gaby"]] is StatusAluno.NAO_RENOVADO
        assert resultado[ids["enzo"]] is StatusAluno.OUTROS
        assert ids["caio"] not in resultado  # Aluno.ativo=False fica fora

        enturmados = {
            aluno_id
            for aluno_id, st in resultado.items()
            if st in (StatusAluno.NOVO, StatusAluno.RENOVADO, StatusAluno.RETORNANTE)
        }
        assert enturmados == {ids["ana"], ids["henry"], ids["iris"]}


# ---------------------------------------------------------------------------
# Parte 2 — equivalência da definição única (Passo 5)
# ---------------------------------------------------------------------------

def test_bi_filtros_reexporta_os_mesmos_predicados(app):
    """Nenhum chamador do BI mudou: `bi_filtros` reexporta os objetos
    originais do módulo neutro (mesma identidade)."""
    from app.relatorios import bi_filtros
    from app.services import enturmado

    assert bi_filtros.cond_oferta_efetiva is enturmado.cond_oferta_efetiva
    assert (
        bi_filtros.cond_inscricao_enturmada is enturmado.cond_inscricao_enturmada
    )


def test_consumidores_migrados_equivalem_ao_servico(app, client):
    """TODOS os consumidores migrados retornam o MESMO conjunto do serviço:
    card de `/alunos`, `PeriodoLetivo.alunos_enturmados`, painel do professor
    e filtro de período de `relatorios/shared`.

    Com o BI a igualdade é pelo predicado: `cond_inscricao_enturmada` +
    `Aluno.ativo` fecha com o serviço; o número puro do ALU-008 (sem
    `Aluno.ativo`) ainda diverge só por Caio — população cadastral que a
    etapa NÃO toca (indicadores do BI ficam para a D3b.4).
    """
    ids = _base(app)
    from test_conselho_oferta import _loga

    esperado_un_a = {ids["ana"], ids["gaby"], ids["henry"], ids["iris"]}
    esperado_p1 = {ids["ana"], ids["henry"], ids["iris"]}
    esperado_p2 = {ids["gaby"], ids["iris"]}

    with app.app_context():
        from app.services.enturmado import ids_alunos_enturmados

        assert ids_alunos_enturmados(unidade_id=ids["un"]) == esperado_un_a
        assert ids_alunos_enturmados(
            unidade_id=ids["un"], periodo_letivo_id=ids["p1"]
        ) == esperado_p1
        assert ids_alunos_enturmados(
            unidade_id=ids["un"], periodo_letivo_id=ids["p2"]
        ) == esperado_p2
        # unidade B só aparece sem o filtro de unidade (Jack) — e no P3.
        assert ids_alunos_enturmados() == esperado_un_a | {ids["jack"]}
        assert ids_alunos_enturmados(
            periodo_letivo_id=ids["p3"]
        ) == {ids["jack"]}

        # BI: mesmo predicado, somando o aperto de cadastro, dá o mesmo set.
        from app.models import Inscricao
        from app.services.enturmado import cond_inscricao_enturmada

        via_bi = {
            row[0]
            for row in db.session.query(Aluno.id)
            .join(Inscricao, Inscricao.aluno_id == Aluno.id)
            .filter(
                cond_inscricao_enturmada(),
                Aluno.unidade_id == ids["un"],
                Aluno.ativo.is_(True),
            )
            .distinct()
            .all()
        }
        assert via_bi == esperado_un_a

    # Rota /alunos: card "Enturmados" == len(esperado_un_a).
    _loga(client, ids, unidade_id=ids["un"])
    corpo = client.get("/alunos").data.decode("utf-8")
    assert _numeiro(corpo, r'text-success">(\d+)</strong>') == len(esperado_un_a)
    # /professor/painel: mesmo conjunto (turmas ativas da unidade cobrem o P1/P2).
    corpo = client.get("/professor/painel").data.decode("utf-8")
    assert _numeiro(
        corpo, r'Meus Alunos</div>\s*<div class="fs-3 fw-bold lh-sm">(\d+)</div>'
    ) == len(esperado_un_a)

    with app.app_context():
        # Property do período == contagem do serviço para o mesmo período.
        from app.services.enturmado import contar_alunos_enturmados

        p1 = db.session.get(PeriodoLetivo, ids["p1"])
        assert p1.alunos_enturmados() == contar_alunos_enturmados(
            periodo_letivo_id=ids["p1"]
        ) == len(esperado_p1)

        # Filtro de período dos relatórios (shared) == mesmo conjunto.
        from app.relatorios.shared import aplicar_filtros_alunos

        obtidos = {
            a.id
            for a in aplicar_filtros_alunos(
                Aluno.query.filter_by(ativo=True),
                {"periodo_letivo_id": ids["p1"]},
            )
        }
        assert obtidos == esperado_p1

        # ALU-008 com período: igual ao serviço + Caio (BI não filtra cadastro
        # — divergência remanescente que a D3b.4 cuida; nada aqui foi alterado).
        from app.relatorios.bi_alunos import alunos_por_unidade

        res = alunos_por_unidade(unidade_id=ids["un"], periodo_letivo_id=ids["p1"])
        assert res[0]["valor"] == len(esperado_p1 | {ids["caio"]})


def test_ids_alunos_enturmados_uma_sozinha_consulta(app):
    """Sem N+1: `ids_alunos_enturmados` emite UMA única consulta, com ou sem
    filtros de unidade/período."""
    from sqlalchemy import event

    ids = _base(app)
    with app.app_context():
        from app.services.enturmado import ids_alunos_enturmados

        consultas = []

        def _conta(conn, cursor, statement, params, context, executemany):
            if "inscricoes" in statement.lower():
                consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", _conta)
        try:
            resultado = ids_alunos_enturmados(
                unidade_id=ids["un"], periodo_letivo_id=ids["p1"]
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", _conta)

        assert resultado == {ids["ana"], ids["henry"], ids["iris"]}
        assert len(consultas) == 1, consultas


def test_import_modulo_neutro_sem_ciclo(app):
    """O módulo neutro pode ser importado isoladamente: não puxa
    `app.relatorios` nem `app.registros` (o ciclo do MER §12.13 morreu com o
    espelho `_cond_oferta_efetiva`). Roda em subprocess para observar o
    estado limpo do `sys.modules`."""
    import subprocess
    import sys
    from pathlib import Path

    raiz = Path(__file__).resolve().parents[1]
    codigo = (
        "import sys;"
        "import app.services.enturmado as m;"
        "assert m.cond_aluno_enturmado is not None;"
        "sys.exit(1 if ('app.relatorios' in sys.modules or"
        "'app.registros' in sys.modules) else 0)"
    )
    res = subprocess.run(
        [sys.executable, "-c", codigo],
        cwd=raiz,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr

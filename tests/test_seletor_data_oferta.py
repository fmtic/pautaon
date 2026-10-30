# ruff: noqa: F811
"""T2 — seletor "Data da Aula" filtrado pelo calendário da oferta escolhida.

GET /frequencia com oferta selecionada (2+ ofertas) ou única automática lista
SOMENTE as datas do calendário da oferta até hoje (`datas_aula_oferta`:
vigência + grade da oferta, dias bloqueados/feriados descontados — mesma fonte
das marcas ✔/○ e do resumo X de Y · Z da V3a).

Casos cobertos:
- 2 ofertas (seg/qua × ter/qui): cada oferta lista só as datas dela;
- troca de oferta com `data` inválida para a oferta escolhida: cai na data
  mais recente da oferta, sem erro;
- sem oferta escolhida em 2+ (exigir_escolha): seletor segue com a união da
  turma, sem marcas (inalterado);
- SELECTs constantes quando o período da oferta cresce (filtro em memória,
  sem consulta extra).

Reaproveita a semente e os helpers de `test_v3a_datas_lancadas`.
"""

import re
from datetime import timedelta

from sqlalchemy import event

from _helpers import login_as

from app import db
from app.models import TurmaCurso
from test_v3a_datas_lancadas import (
    HOJE,
    SQLiteTestConfig,  # noqa: F401 — V3a reusa a config; aqui o que interessa são as fixtures
    _abrev,
    _br,
    _datas_ate_hoje,
    _get,
    _iso,
    _lancar_direto,
    _seed,
    app,      # noqa: F401 — fixture reaproveitada do módulo V3a
    client,   # noqa: F401 — fixture reaproveitada do módulo V3a
)


def _opcoes_seletor(html):
    """Datas (ISO) presentes como <option> do seletor "Data da Aula"."""
    bloco = re.search(
        r'id="select-data".*?</select>', html, flags=re.S
    )
    assert bloco, "seletor de data não encontrado"
    return re.findall(r'<option value="(\d{4}-\d{2}-\d{2})"', bloco.group(0))


# ---------------------------------------------------------------------------
# Seletor por oferta
# ---------------------------------------------------------------------------

def test_seletor_lista_so_datas_da_oferta_escolhida(app, client):
    """2 ofertas (seg/qua × ter/qui): escolhida a O1, o seletor não pode
    conter nenhuma data do calendário da O2 (e vice-versa)."""
    ids = _seed(app)
    datas_o1 = _datas_ate_hoje(app, ids, ids["o1"])
    datas_o2 = _datas_ate_hoje(app, ids, ids["o2"])
    assert datas_o1 and datas_o2
    assert not (set(datas_o1) & set(datas_o2)), "dias da grade deveriam ser disjuntos"

    login_as(client, ids["admin"], ids["un"])

    status, html = _get(client, ids, turma_curso=ids["o1"])
    assert status == 200
    opcoes = _opcoes_seletor(html)
    assert sorted(opcoes) == sorted(_iso(d) for d in datas_o1)
    for d in datas_o2:
        assert _iso(d) not in opcoes

    status, html = _get(client, ids, turma_curso=ids["o2"])
    assert status == 200
    assert sorted(_opcoes_seletor(html)) == sorted(_iso(d) for d in datas_o2)


def test_troca_de_oferta_com_data_invalida_cai_na_mais_recente(app, client):
    """> `data` da URL pertence à O2 mas a oferta escolhida é a O1 (troca de
    oferta): cai na data mais recente da O1, sem erro (200, opção selected)."""
    ids = _seed(app)
    datas_o1 = _datas_ate_hoje(app, ids, ids["o1"])
    datas_o2 = _datas_ate_hoje(app, ids, ids["o2"])
    mais_recente_o1 = _iso(datas_o1[-1])
    data_da_o2 = next(
        _iso(d) for d in datas_o2 if _iso(d) != mais_recente_o1
    )

    login_as(client, ids["admin"], ids["un"])
    status, html = _get(
        client, ids, turma_curso=ids["o1"], data=data_da_o2
    )

    assert status == 200
    assert f'<option value="{data_da_o2}"' not in html
    assert f'<option value="{mais_recente_o1}" selected' in html


def test_sem_oferta_escolhida_seletor_segue_com_uniao(app, client):
    """2+ ofertas sem escolha (exigir_escolha): seletor mantém a união da
    turma — datas das duas ofertas presentes, sem marcas (comportamento da V3a
    inalterado)."""
    ids = _seed(app)
    datas_o1 = _datas_ate_hoje(app, ids, ids["o1"])
    datas_o2 = _datas_ate_hoje(app, ids, ids["o2"])

    login_as(client, ids["admin"], ids["un"])
    status, html = _get(client, ids)

    assert status == 200
    opcoes = _opcoes_seletor(html)
    assert set(opcoes) >= {_iso(d) for d in datas_o1} | {_iso(d) for d in datas_o2}
    assert "— pendente" not in html
    assert "✔" not in html


def test_marcas_e_resumo_preservados_com_filtro(app, client):
    """O filtro não quebra as marcas ✔/○ nem o resumo X de Y · Z (Z igual às
    pendências — mesma fonte `situacao_datas_oferta`)."""
    ids = _seed(app)
    datas = _datas_ate_hoje(app, ids, ids["o1"])
    assert len(datas) >= 2
    _lancar_direto(app, ids, ids["o1"], datas[0])

    login_as(client, ids["prof"], ids["un"])
    status, html = _get(client, ids, turma_curso=ids["o1"])

    assert status == 200
    assert f"✔ {_br(datas[0])} ({_abrev(datas[0])})" in html
    assert f"○ {_br(datas[1])} ({_abrev(datas[1])}) — pendente" in html
    assert (
        f"1 de {len(datas)} aulas até hoje lançadas · {len(datas) - 1} pendente(s)"
        in html
    )
    assert "Ir para a próxima pendente" in html


def test_selects_constantes_com_periodo_maior(app, client):
    """O filtro do seletor é em memória (`datas_aula_oferta` já carregada):
    ampliar a vigência da oferta aumenta as opções sem alterar o nº de
    SELECTs do GET /frequencia."""
    ids = _seed(app)
    login_as(client, ids["admin"], ids["un"])

    def _contar_get():
        consultas = []

        def _registra(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                # Normaliza placeholders: o nº de `?` do IN cresce com o
                # calendário da oferta; o que não pode mudar é a QUANTIDADE
                # e a IDENTIDADE das consultas.
                consultas.append(re.sub(r"\(\?[,? ]*\)", "(...)", statement))

        event.listen(db.engine, "before_cursor_execute", _registra)
        try:
            status, html = _get(client, ids, turma_curso=ids["o1"])
        finally:
            event.remove(db.engine, "before_cursor_execute", _registra)
        assert status == 200
        return consultas, _opcoes_seletor(html)

    # Aquece o pedido (carga do usuário da sessão, planos) fora da medição:
    # o que se mede é o custo POR DATA, não artefatos da primeira chamada.
    _contar_get()
    statements_antes, opcoes_antes = _contar_get()

    with app.app_context():
        oferta = db.session.get(TurmaCurso, ids["o1"])
        turma = oferta.turma
        turma.data_inicio = HOJE - timedelta(days=160)
        db.session.commit()
        # Aquece o relacionamento do período fora da medição.
        turma.periodo_letivo.data_inicio = HOJE - timedelta(days=160)
        db.session.commit()
        oferta.data_inicio = HOJE - timedelta(days=160)
        db.session.commit()

    statements_depois, opcoes_depois = _contar_get()

    assert len(opcoes_depois) > len(opcoes_antes), (
        "a vigência ampliada deveria adicionar datas ao seletor"
    )
    # A quantidade de consultas do GET não muda com o nº de datas: o filtro é
    # em memória (mesma `datas_aula_oferta` já carregada pelas marcas da V3a).
    assert len(statements_depois) == len(statements_antes), (
        "nº de SELECTs mudou com o período maior:"
        f" {len(statements_antes)} → {len(statements_depois)}"
    )

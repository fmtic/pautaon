# ruff: noqa: F811
"""A1 — "Atividades da aula" no diário de frequência.

O campo é um texto ADICIONAL ao lado de Observações da Aula:
grava em `registro_aula.atividades`, é independente das observações e não
participa de frequência, estatísticas, pauta impressa, BI ou relatórios.
O Diário de Bordo da turma passou a exibir as duas seções e a listar
aulas que tenham qualquer um dos dois textos.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import time, timedelta
from pathlib import Path

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
from app.utils.logica import carregar_contexto_turma, get_local_now

RAIZ = Path(__file__).resolve().parents[1]
TEXTO_ATIV = "ATIV_MARCADOR_Aquecimento e jogo reduzido"
TEXTO_OBS = "OBS_MARCADOR_Vento forte no campo"


def _cenario(app, *, ofertas=1):
    """Unidade + período vigente + turma com N ofertas + 1 aluno inscrito."""
    hoje = get_local_now().date()
    with app.app_context():
        un = Unidade(nome="Unidade ATV", ativo=True)
        user = User(
            name="Admin ATV", email="admin.atv@x.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        user.set_password("SenhaLocal!123")
        # G1/P2 (d6e7f8a9b0c1): oferta exige professor — a semente garante um.
        prof = User(
            name="Prof ATV", email="prof.atv@x.com", role="professor",
            first_login=False, unidade_id=un.id,
        )
        db.session.add_all([un, user, prof])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P ATV",
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=30),
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma ATV", turno="Manhã",
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_ofertas = []
        for i in range(ofertas):
            curso = Curso(nome=f"Curso ATV {i}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            ids_ofertas.append(
                nova_oferta(
                    turma.id, curso.id, un.id, principal=(i == 0),
                    professor_id=prof.id,
                    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
                    hora_inicio=time(8), hora_fim=time(10),
                ).id
            )

        aluno = Aluno(nome="Aluno ATV", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, ids_ofertas[0])
        if ofertas >= 2:
            nova_inscricao(aluno.id, turma.id, ids_ofertas[1])
        db.session.commit()

        return {
            "un": un.id, "user": user.id, "turma": turma.id,
            "ofertas": ids_ofertas, "aluno": aluno.id,
            "data": carregar_contexto_turma(turma.id)["datas"][0],
        }


def _post(client, ids, *, atividades=None, observacoes=None,
          conceito="A", extras=None):
    dados = {"turma": str(ids["turma"]), "data": ids["data"]}
    if conceito is not None:
        dados[f"aluno_{ids['aluno']}"] = conceito
    if atividades is not None:
        dados["atividades"] = atividades
    if observacoes is not None:
        dados["observacoes"] = observacoes
    if extras:
        dados.update(extras)
    return client.post("/frequencia", data=dados, follow_redirects=False)


def _diario(app, ids, oferta_idx=0):
    with app.app_context():
        if oferta_idx is None:
            return RegistroAula.query.filter_by(
                turma_id=ids["turma"], turma_curso_id=None,
            ).first()
        return RegistroAula.query.filter_by(
            turma_id=ids["turma"], turma_curso_id=ids["ofertas"][oferta_idx],
        ).first()


def _url_pauta(ids):
    return f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"


def _textarea(corpo, nome):
    achado = re.search(
        r'<textarea[^>]*name="%s"[^>]*>(.*?)</textarea>' % nome, corpo, re.S,
    )
    assert achado, f"textarea {nome} nao renderizou"
    return achado


def _estatisticas(corpo):
    padrao = re.compile(
        r"P:\s*([\d.]+)%\s*</span>.*?F:\s*([\d.]+)%\s*</span>"
        r".*?J:\s*(\d+)\s*</span>.*?\((\d+)\s*aulas\)",
        re.S,
    )
    return padrao.findall(corpo)


# ---------------------------------------------------------------------------
# Gravação e leitura
# ---------------------------------------------------------------------------

def test_salva_atividades_no_diario(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    resposta = _post(client, ids, atividades=TEXTO_ATIV)
    assert resposta.status_code == 302

    diario = _diario(app, ids)
    assert diario is not None
    assert diario.atividades == TEXTO_ATIV
    assert diario.observacoes is None


def test_get_exibe_atividades_salvas(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV)

    corpo = client.get(_url_pauta(ids)).get_data(as_text=True)
    assert TEXTO_ATIV in _textarea(corpo, "atividades").group(1)


def test_atividades_ficam_acima_das_observacoes_no_mesmo_card(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    corpo = client.get(_url_pauta(ids)).get_data(as_text=True)

    assert corpo.index('name="atividades"') < corpo.index('name="observacoes"')
    # AJ16-D: atividades e observações agora ficam lado a lado (dois
    # col-md-6) dentro do MESMO card de dados da aula. Em vez de exigir a
    # ausência de col-md-, garante que os dois campos estão dentro do mesmo
    # card-dados-aula (o card fecha antes do "QUADRO DE FREQUÊNCIA").
    ini_card = corpo.index('card-dados-aula')
    fim_card = corpo.index('<div class="card p-3">', ini_card)
    trecho_card = corpo[ini_card:fim_card]
    assert 'name="atividades"' in trecho_card
    assert 'name="observacoes"' in trecho_card


def test_editar_substitui_atividades(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades="Primeira versao")
    _post(client, ids, atividades="Segunda versao")

    assert _diario(app, ids).atividades == "Segunda versao"
    assert _diario(app, ids).observacoes is None


def test_limpar_atividades_grava_null(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV, observacoes=TEXTO_OBS)
    _post(client, ids, atividades="   ", observacoes=TEXTO_OBS)

    diario = _diario(app, ids)
    assert diario.atividades is None
    assert diario.observacoes == TEXTO_OBS  # não interfere no outro campo


def test_atividades_e_observacoes_sao_independentes(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV, observacoes=TEXTO_OBS)
    _post(client, ids, atividades=TEXTO_ATIV, observacoes="Nova observacao")

    diario = _diario(app, ids)
    assert diario.atividades == TEXTO_ATIV
    assert diario.observacoes == "Nova observacao"


def test_duas_ofertas_gravam_na_oferta_certa(app, client):
    ids = _cenario(app, ofertas=2)
    login_as(client, ids["user"], ids["un"])
    _post(
        client, ids, atividades=TEXTO_ATIV,
        extras={"turma_curso": str(ids["ofertas"][1])},
    )
    assert _diario(app, ids, oferta_idx=1).atividades == TEXTO_ATIV
    assert _diario(app, ids, oferta_idx=0) is None


# ---------------------------------------------------------------------------
# Não regressão
# ---------------------------------------------------------------------------

def test_atividades_nao_alteram_estatisticas(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])

    _post(client, ids, conceito="A")
    antes = _estatisticas(client.get(_url_pauta(ids)).get_data(as_text=True))

    _post(client, ids, conceito="A", atividades=TEXTO_ATIV)
    depois = _estatisticas(client.get(_url_pauta(ids)).get_data(as_text=True))

    assert antes == depois
    assert antes


def test_atividades_nao_saem_na_pauta_impressa(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV)

    resposta = client.get(f"/turma/{ids['turma']}/imprimir-pauta")
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)
    assert TEXTO_ATIV not in corpo


# ---------------------------------------------------------------------------
# Diário de Bordo da turma
# ---------------------------------------------------------------------------

def test_diario_lista_aula_so_com_atividades(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV)

    corpo = client.get(f"/turma/{ids['turma']}/observacoes").get_data(as_text=True)
    assert TEXTO_ATIV in corpo
    assert "Atividades da aula" in corpo
    assert "Nenhuma observação ou atividade" not in corpo


def test_diario_exibe_as_duas_secoes(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, atividades=TEXTO_ATIV, observacoes=TEXTO_OBS)

    corpo = client.get(f"/turma/{ids['turma']}/observacoes").get_data(as_text=True)
    assert corpo.index(TEXTO_ATIV) < corpo.index(TEXTO_OBS)
    assert "Observações da aula" in corpo


def test_diario_sem_textos_continua_vazio(app, client):
    ids = _cenario(app)
    login_as(client, ids["user"], ids["un"])
    _post(client, ids, conceito="A")  # sem atividades nem observações

    corpo = client.get(f"/turma/{ids['turma']}/observacoes").get_data(as_text=True)
    assert "Nenhuma observação ou atividade registrada" in corpo


# ---------------------------------------------------------------------------
# Migration
# ---------------------------------------------------------------------------

def _carregar_migration():
    espec = importlib.util.spec_from_file_location(
        "mig_atividades_aula",
        RAIZ / "migrations" / "versions" / "c8d9e0f1a2b3_atividades_aula.py",
    )
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


MIG = _carregar_migration()


def test_migration_encadeada_no_head_atual():
    assert MIG.revision == "c8d9e0f1a2b3"
    assert MIG.down_revision == "b7c8d9e0f1a2"


def test_migration_upgrade_e_downgrade_preservam_linhas():
    import sqlalchemy as sa

    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE registro_aula ("
            "id INTEGER PRIMARY KEY, observacoes TEXT)"
        ))
        conn.execute(sa.text(
            "INSERT INTO registro_aula (id, observacoes) VALUES (1, 'legado')"
        ))

        MIG._adicionar_coluna(conn)
        colunas = [r[1] for r in conn.execute(
            sa.text("PRAGMA table_info(registro_aula)")
        )]
        assert "atividades" in colunas
        conn.execute(sa.text(
            "UPDATE registro_aula SET atividades = 'aula 1' WHERE id = 1"
        ))
        assert conn.execute(sa.text(
            "SELECT atividades FROM registro_aula WHERE id = 1"
        )).scalar() == "aula 1"

        MIG._dropar_coluna(conn)
        colunas = [r[1] for r in conn.execute(
            sa.text("PRAGMA table_info(registro_aula)")
        )]
        assert "atividades" not in colunas
        assert conn.execute(sa.text(
            "SELECT observacoes FROM registro_aula WHERE id = 1"
        )).scalar() == "legado"

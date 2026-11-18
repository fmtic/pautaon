"""AJ22-B — Próximo curso (curso) + nível no fechamento do conselho.

Cobre as decisões da AJ22-B:
    - `curso.programa` e `nivel.programa` (colunas novas, sem backfill;
      nível sem programa nunca aparece no fechamento).
    - `conselho_classe.proximo_curso_id` FK → `curso` (RESTRICT) e
      `proximo_nivel_id` FK → `nivel` (RESTRICT); NULL = "Não se aplica".
    - `opcao_proxima_turma`/`proxima_turma_id` são LEGADO: sem UI, sem
      novas escritas, usados apenas como fallback de leitura.
    - Unicidade do nível por (nome, unidade, COALESCE(programa,'')):
      mesmo nome repete entre programas; duplicata no mesmo
      programa/legado recusa.
    - Validação atômica do `salvar_fechamento_data`: qualquer erro →
      rollback, nada gravado, mensagem em português.
    - Tela de fechamento: "Próximo Curso" (curso) + coluna "Nível" com
      "Não se aplica" default, select habilitado só com programa com
      níveis, dados embutidos via tojson (sem requisição extra).
    - Cadastro: `curso.programa` editável no modal de cursos; cadastro de
      níveis ganha Programa; avisos "cursos sem programa" e "programas sem
      nível"; aba/rotas legadas de "Próximos Cursos" removidas (404).
    - Leitores: resultado do conselho, ficha, resumo e painel mostram
      curso + nível em lote (sem N+1), com fallback legado.

Um usuário por teste (padrão do harness): cada teste cria o próprio
client e fixa a sessão uma única vez.
"""

from __future__ import annotations

import importlib.util
import re
from datetime import date
from pathlib import Path

import pytest
from sqlalchemy import event, inspect

from app.database import db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    Nivel,
    OpcaoProximaTurma,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from _helpers import login_as, nova_inscricao, nova_oferta

RAIZ = Path(__file__).resolve().parents[1]
DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _carregar_migration():
    espec = importlib.util.spec_from_file_location(
        "mig_aj22", RAIZ / "migrations" / "versions"
        / "a7b8c9d0e1f2_aj22_proximo_curso_nivel.py"
    )
    modulo = importlib.util.module_from_spec(espec)
    espec.loader.exec_module(modulo)
    return modulo


mig = _carregar_migration()


# ---------------------------------------------------------------------------
# Semeadura
# ---------------------------------------------------------------------------

def _setup(app, *, role="admin", alunos=2, unidade="A"):
    """Unidade + usuário + turma com 1 oferta ativa + N alunos inscritos.

    O curso da oferta já nasce com programa "Esporte" (destino padrão dos
    testes de nível).
    """
    with app.app_context():
        un = Unidade(nome=f"Unidade {unidade}", ativo=True)
        db.session.add(un)
        db.session.flush()
        usuario = User(
            name=f"User {role}", email=f"{role}.aj22@example.com",
            role=role, first_login=False,
        )
        usuario.set_password("SenhaLocal!123")
        periodo = PeriodoLetivo(
            nome="Periodo AJ22", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso = Curso(
            nome="Curso AJ22", unidade_id=un.id, ativo=True,
            programa="Esporte",
        )
        db.session.add_all([usuario, periodo, curso])
        db.session.flush()
        turma = Turma(
            nome="Turma AJ22", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, un.id, programa="Esporte",
            principal=True,
        )
        ids_alunos = []
        for i in range(alunos):
            aluno = Aluno(
                nome=f"Aluno {i:02d}", unidade_id=un.id, ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, turma.id, oferta.id)
            ids_alunos.append(aluno.id)
        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": un.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "curso": curso.id,
            "alunos": ids_alunos,
        }


def _login(client, ids):
    login_as(client, str(ids["user_id"]), ids["unidade"])


def _salvar(client, turma_id, oferta_id, dados):
    return client.post(
        f"/conselho/fechamento/{turma_id}/salvar",
        json={"oferta_id": oferta_id, "dados": dados},
    )


def _item(aluno_id, situacao="APROVADO", curso=None, nivel=None):
    return {
        "aluno_id": aluno_id,
        "situacao": situacao,
        "proximo_curso_id": curso,
        "proximo_nivel_id": nivel,
    }


def _curso(app, nome="Avançado", unidade_id=None, programa=None, ativo=True):
    with app.app_context():
        c = Curso(
            nome=nome, unidade_id=unidade_id, programa=programa, ativo=ativo,
        )
        db.session.add(c)
        db.session.commit()
        return c.id


def _opcao_legado(app, nome="Avançado"):
    with app.app_context():
        o = OpcaoProximaTurma(nome=nome, ativo=True)
        db.session.add(o)
        db.session.commit()
        return o.id


def _nivel(app, nome, programa=None, unidade_id=None, ativo=True):
    with app.app_context():
        n = Nivel(
            nome=nome, programa=programa, unidade_id=unidade_id,
            ativo=ativo,
        )
        db.session.add(n)
        db.session.commit()
        return n.id


# ---------------------------------------------------------------------------
# Migration — helpers exercitados no SQLite do harness (padrão h5b/AJ16-B)
# ---------------------------------------------------------------------------

def test_migration_heads_e_schema_pos_create_all(app):
    """O modelo reflete a migration: colunas novas + índice funcional."""
    with app.app_context():
        cols_curso = {
            c["name"] for c in inspect(db.engine).get_columns("curso")
        }
        cols_nivel = {c["name"] for c in inspect(db.engine).get_columns("nivel")}
        cols_opcao = {
            c["name"] for c in inspect(db.engine).get_columns("opcao_proxima_turma")
        }
        cols_conselho = {
            c["name"] for c in inspect(db.engine).get_columns("conselho_classe")
        }
        assert "programa" in cols_curso
        assert "programa" in cols_nivel
        assert "programa" not in cols_opcao  # legado, sem coluna nova
        assert "proximo_curso_id" in cols_conselho
        assert "proximo_nivel_id" in cols_conselho
        # Unicidade funcional presente como índice (expressão não reflete
        # nome em alguns dialetos — o modelo a declara em __table_args__).
        assert any(
            "uq_nivel_nome_unidade_programa" in str(i)
            for i in Nivel.__table_args__
        )


def test_migration_upgrade_idempotente_no_sqlite(app):
    """Rodar o upgrade duas vezes não falha nem duplica (inspeção)."""
    with app.app_context():
        bind = db.session.connection()
        mig._add_coluna(bind, mig.T_CURSO, mig.COL_CURSO, "VARCHAR(50)")
        mig._add_coluna(bind, mig.T_NIVEL, mig.COL_NIVEL, "VARCHAR(50)")
        mig._add_coluna(
            bind, mig.T_CONSELHO, mig.COL_CONSELHO_CURSO, "INTEGER"
        )
        mig._add_coluna(
            bind, mig.T_CONSELHO, mig.COL_CONSELHO_NIVEL, "INTEGER"
        )
        mig._trocar_unicidade_nivel(bind, "upgrade")
        # Segunda passada: nada muda.
        mig._add_coluna(bind, mig.T_CURSO, mig.COL_CURSO, "VARCHAR(50)")
        mig._add_coluna(bind, mig.T_NIVEL, mig.COL_NIVEL, "VARCHAR(50)")
        mig._add_coluna(
            bind, mig.T_CONSELHO, mig.COL_CONSELHO_CURSO, "INTEGER"
        )
        mig._add_coluna(
            bind, mig.T_CONSELHO, mig.COL_CONSELHO_NIVEL, "INTEGER"
        )
        mig._trocar_unicidade_nivel(bind, "upgrade")
        db.session.commit()

        constraints = {
            c["name"]
            for c in inspect(db.engine).get_unique_constraints("nivel")
        }
        assert mig.UNQ_ANTIGA not in constraints


def test_migration_guarda_downgrade_recusa_duplicata(app):
    """D8: (nome, unidade) duplicado entre programas → downgrade aborta."""
    with app.app_context():
        bind = db.session.connection()
        db.session.add_all([
            Nivel(nome="Infantil", unidade_id=1, programa="Esporte"),
            Nivel(nome="Infantil", unidade_id=1, programa="Meio Ambiente"),
        ])
        db.session.flush()
        with pytest.raises(RuntimeError, match="AJ22"):
            mig._guarda_downgrade(bind)
        db.session.rollback()


def test_migration_guarda_downgrade_passa_sem_duplicata(app):
    with app.app_context():
        bind = db.session.connection()
        db.session.add(Nivel(nome="Único", unidade_id=1, programa="Esporte"))
        db.session.flush()
        mig._guarda_downgrade(bind)  # não levanta
        db.session.rollback()


def test_migration_downgrade_restaura_unicidade_antiga(app):
    """Após downgrade, (nome, unidade) volta a ser único — duplicata
    entre programas é recusada pelo banco."""
    with app.app_context():
        bind = db.session.connection()
        mig._trocar_unicidade_nivel(bind, "downgrade")
        db.session.commit()
        db.session.add(Nivel(nome="Dup", unidade_id=9, programa="Esporte"))
        db.session.flush()
        db.session.add(Nivel(nome="Dup", unidade_id=9, programa="Outros"))
        with pytest.raises(Exception):
            db.session.flush()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Regra — salvar_fechamento_data
# ---------------------------------------------------------------------------

def test_regra_nivel_exige_proximo_curso(client, app):
    ids = _setup(app)
    _login(client, ids)
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=None, nivel=nid),
    ])
    assert r.status_code == 200
    assert r.get_json()["success"] is False
    assert "próximo curso" in r.get_json()["message"].lower()
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_regra_curso_sem_programa_recusa_nivel(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Egresso", ids["unidade"], programa=None)
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False
    assert "programa" in r.get_json()["message"].lower()


def test_regra_programa_sem_niveis_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Meio Ambiente")
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False
    assert "nível ativo" in r.get_json()["message"].lower()


def test_regra_nivel_outro_programa_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Outros", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False


def test_regra_nivel_outra_unidade_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    with app.app_context():
        outra = Unidade(nome="Unidade B", ativo=True)
        db.session.add(outra)
        db.session.flush()
        nid = Nivel(nome="Sub-12", programa="Esporte", unidade_id=outra.id)
        db.session.add(nid)
        db.session.commit()
        nid = nid.id

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False


def test_regra_nivel_inativo_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Esporte",
                 unidade_id=ids["unidade"], ativo=False)

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False


def test_regra_nivel_legado_sem_programa_nunca_aceito(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Legado", programa=None, unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert r.get_json()["success"] is False


def test_regra_curso_inativo_novo_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Antigo", ids["unidade"], programa="Esporte", ativo=False)

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid),
    ])
    assert r.get_json()["success"] is False
    assert "ativo" in r.get_json()["message"].lower()


def test_regra_curso_outra_unidade_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    with app.app_context():
        outra = Unidade(nome="Unidade B", ativo=True)
        db.session.add(outra)
        db.session.flush()
        cid = _curso(app, "Externo", outra.id, programa="Esporte")

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid),
    ])
    assert r.get_json()["success"] is False


def test_regra_valido_grava_proximo_curso(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
        _item(ids["alunos"][1], curso=cid, nivel=None),
    ])
    assert r.get_json()["success"] is True
    with app.app_context():
        c1 = ConselhoClasse.query.filter_by(aluno_id=ids["alunos"][0]).one()
        c2 = ConselhoClasse.query.filter_by(aluno_id=ids["alunos"][1]).one()
        assert c1.proximo_curso_id == cid
        assert c1.proximo_nivel_id == nid
        # Legado nunca é escrito pelo fechamento.
        assert c1.proxima_turma_id is None
        assert c2.proximo_nivel_id is None  # "Não se aplica"


def test_regra_curso_inativo_ja_gravado_inalterado_aceito(client, app):
    """E1: curso inativado depois da escolha continua aceito inalterado."""
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")

    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid),
    ])
    assert ok.get_json()["success"] is True

    with app.app_context():
        db.session.get(Curso, cid).ativo = False
        db.session.commit()

    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid),
    ])
    assert ok.get_json()["success"] is True
    with app.app_context():
        c = ConselhoClasse.query.filter_by(aluno_id=ids["alunos"][0]).one()
        assert c.proximo_curso_id == cid


def test_regra_recusa_atomica_nao_grava_nada(client, app):
    """Um item inválido no lote → rollback de TODOS os alunos."""
    ids = _setup(app, alunos=2)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid_outro = _nivel(app, "X", programa="Outros", unidade_id=ids["unidade"])

    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid_outro),  # inválido
        _item(ids["alunos"][1], curso=cid, nivel=None),       # válido
    ])
    assert r.get_json()["success"] is False
    with app.app_context():
        assert ConselhoClasse.query.count() == 0


def test_regra_limpar_curso_zera_nivel(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert ok.get_json()["success"] is True

    # Regrava sem curso: o nível precisa zerar junto.
    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=None, nivel=None),
    ])
    assert ok.get_json()["success"] is True
    with app.app_context():
        c = ConselhoClasse.query.filter_by(aluno_id=ids["alunos"][0]).one()
        assert c.proximo_curso_id is None
        assert c.proximo_nivel_id is None


def test_regra_nivel_inativo_ja_gravado_inalterado_aceito(client, app):
    """Exceção AJ22: nível inativado depois da escolha continua valendo se
    reenviado inalterado."""
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert ok.get_json()["success"] is True

    # Inativa o nível e regrava o MESMO valor.
    with app.app_context():
        n = db.session.get(Nivel, nid)
        n.ativo = False
        db.session.commit()

    ok = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid),
    ])
    assert ok.get_json()["success"] is True
    with app.app_context():
        c = ConselhoClasse.query.filter_by(aluno_id=ids["alunos"][0]).one()
        assert c.proximo_nivel_id == nid


def test_regra_nivel_inativo_trocado_recusa(client, app):
    """A exceção só vale para o valor JÁ gravado — outro nível inativo
    continua recusado."""
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid_ok = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])
    nid_inativo = _nivel(app, "Sub-14", programa="Esporte",
                         unidade_id=ids["unidade"], ativo=False)

    _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid_ok),
    ])
    r = _salvar(client, ids["turma"], ids["oferta"], [
        _item(ids["alunos"][0], curso=cid, nivel=nid_inativo),
    ])
    assert r.get_json()["success"] is False


# ---------------------------------------------------------------------------
# Unicidade do nível (D8)
# ---------------------------------------------------------------------------

def test_unicidade_mesmo_nome_programas_diferentes_ok(app):
    with app.app_context():
        db.session.add_all([
            Nivel(nome="Infantil", unidade_id=5, programa="Esporte"),
            Nivel(nome="Infantil", unidade_id=5, programa="Outros"),
            Nivel(nome="Infantil", unidade_id=5, programa=None),
        ])
        db.session.commit()  # não levanta


def test_unicidade_duplicata_mesmo_programa_recusa(app):
    with app.app_context():
        db.session.add(Nivel(nome="Infantil", unidade_id=5, programa="Esporte"))
        db.session.flush()
        db.session.add(Nivel(nome="Infantil", unidade_id=5, programa="Esporte"))
        with pytest.raises(Exception):
            db.session.flush()
        db.session.rollback()


def test_unicidade_duplicata_legado_recusa(app):
    """Dois níveis sem programa com mesmo nome+unidade → recusa (mantém a
    unicidade anterior para legados)."""
    with app.app_context():
        db.session.add(Nivel(nome="Infantil", unidade_id=5, programa=None))
        db.session.flush()
        db.session.add(Nivel(nome="Infantil", unidade_id=5, programa=None))
        with pytest.raises(Exception):
            db.session.flush()
        db.session.rollback()


# ---------------------------------------------------------------------------
# Tela de fechamento
# ---------------------------------------------------------------------------

def test_tela_rotulos_e_defaults(client, app):
    ids = _setup(app)
    _login(client, ids)
    _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}")
    body = r.data.decode("utf-8")
    assert r.status_code == 200
    assert "Próximo Curso" in body
    assert "<th>Nível</th>" in body
    assert "Não se aplica" in body
    # Select de nível nasce desabilitado ("Não se aplica" default).
    assert 'class="form-select form-select-sm border-info d-print-none nivel-select"' in body
    assert "disabled" in body
    # Dados embutidos via tojson (sem requisição extra).
    assert "NIVEL_DATA" in body and "CURSO_PROGRAMA" in body
    # O curso da unidade aparece no select de próximo curso.
    assert "Curso AJ22" in body

    # Nível legado (programa NULL) NUNCA entra no mapa do fechamento (D2).
    _nivel(app, "Legado Sem Programa", programa=None, unidade_id=ids["unidade"])
    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}")
    body = r.data.decode("utf-8")
    m = re.search(r"const NIVEL_DATA = (\{.*?\});", body, re.S)
    assert m, "NIVEL_DATA não embutido"
    assert "Legado Sem Programa" not in m.group(1)


def test_tela_pre_seleciona_conselho_gravado(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])
    with app.app_context():
        db.session.add(ConselhoClasse(
            aluno_id=ids["alunos"][0], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
            unidade_id=ids["unidade"], situacao_final="Aprovado",
            proximo_curso_id=cid, proximo_nivel_id=nid,
            concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
        ))
        db.session.commit()

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}")
    body = r.data.decode("utf-8")
    assert f'data-nivel-atual="{nid}"' in body
    assert re.search(rf'<option value="{cid}" selected>', body)


def test_tela_fallback_legado_sem_nivel(client, app):
    """Sem `proximo_curso_id`, a opção antiga aparece só para leitura."""
    ids = _setup(app)
    _login(client, ids)
    oid = _opcao_legado(app, "Avançado legado")
    with app.app_context():
        db.session.add(ConselhoClasse(
            aluno_id=ids["alunos"][0], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
            unidade_id=ids["unidade"], situacao_final="Aprovado",
            proxima_turma_id=oid,
            concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
        ))
        db.session.commit()

    r = client.get(f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}")
    body = r.data.decode("utf-8")
    assert 'data-legado="Avançado legado"' in body
    assert "Legado: Avançado legado (sem nível)" in body


# ---------------------------------------------------------------------------
# Cadastro — cursos (programa) e níveis
# ---------------------------------------------------------------------------

def test_rotas_e_aba_legadas_removidas(client, app):
    ids = _setup(app)
    _login(client, ids)

    assert client.post(
        "/planejamento/proxima-opcao/1/programa",
        data={"csrf_token": "", "programa_opcao": "Esporte"},
    ).status_code == 404
    assert client.post(
        "/planejamento/proxima-opcao/1/inativar",
        data={"csrf_token": ""},
    ).status_code == 404

    body = client.get("/planejamento").data.decode("utf-8")
    assert "Próximos Cursos" not in body
    assert "tabProximos" not in body
    assert "proxima_opcao" not in body


def test_cadastro_curso_com_programa(client, app):
    ids = _setup(app)
    _login(client, ids)
    r = client.post("/cursos/novo", json={
        "nome": "Curso novo", "descricao": "", "programa": "Outros",
    })
    assert r.status_code == 200
    assert r.get_json()["success"] is True
    assert r.get_json()["programa"] == "Outros"
    with app.app_context():
        c = Curso.query.filter_by(nome="Curso novo").one()
        assert c.programa == "Outros"


def test_cadastro_curso_programa_invalido(client, app):
    ids = _setup(app)
    _login(client, ids)
    r = client.post("/cursos/novo", json={
        "nome": "Curso novo", "programa": "Inexistente",
    })
    assert r.status_code == 400
    with app.app_context():
        assert Curso.query.filter_by(nome="Curso novo").count() == 0


def test_editar_curso_programa_e_preservar_quando_omitido(client, app):
    ids = _setup(app)
    _login(client, ids)
    cid = _curso(app, "Avançado", ids["unidade"], programa="Esporte")

    r = client.post(f"/cursos/{cid}/editar", json={
        "nome": "Avançado", "descricao": "", "programa": "Outros",
    })
    assert r.status_code == 200
    assert r.get_json()["programa"] == "Outros"

    # Payload sem `programa` (cliente antigo) preserva o valor atual.
    r = client.post(f"/cursos/{cid}/editar", json={
        "nome": "Avançado 2", "descricao": "",
    })
    assert r.status_code == 200
    with app.app_context():
        c = db.session.get(Curso, cid)
        assert c.nome == "Avançado 2"
        assert c.programa == "Outros"


def test_cadastro_nivel_com_programa(client, app):
    ids = _setup(app)
    _login(client, ids)
    client.post("/planejamento", data={
        "csrf_token": "", "tipo_post": "nivel", "aba": "niveis",
        "nome_nivel": "Sub-12", "programa_nivel": "Esporte",
    })
    with app.app_context():
        n = Nivel.query.filter_by(nome="Sub-12").one()
        assert n.programa == "Esporte"
        assert n.unidade_id == ids["unidade"]


def test_cadastro_nivel_mesmo_nome_outro_programa_ok(client, app):
    ids = _setup(app)
    _login(client, ids)
    for prog in ("Esporte", "Outros"):
        client.post("/planejamento", data={
            "csrf_token": "", "tipo_post": "nivel", "aba": "niveis",
            "nome_nivel": "Infantil", "programa_nivel": prog,
        })
    with app.app_context():
        assert Nivel.query.filter_by(nome="Infantil").count() == 2


def test_cadastro_nivel_duplicata_mesmo_programa_recusa(client, app):
    ids = _setup(app)
    _login(client, ids)
    for _ in range(2):
        client.post("/planejamento", data={
            "csrf_token": "", "tipo_post": "nivel", "aba": "niveis",
            "nome_nivel": "Infantil", "programa_nivel": "Esporte",
        })
    with app.app_context():
        assert Nivel.query.filter_by(nome="Infantil").count() == 1


def test_tela_planejamento_cursos_programa_e_avisos(client, app):
    ids = _setup(app)
    _login(client, ids)
    # Curso sem programa (aviso) e nenhum nível ativo na unidade.
    _curso(app, "Sem programa", ids["unidade"], programa=None)
    r = client.get("/planejamento")
    body = r.data.decode("utf-8")
    assert r.status_code == 200
    assert 'id="cursoProgramaInput"' in body
    assert 'id="editCursoPrograma"' in body
    assert "Cursos sem programa" in body
    assert "Sem programa" in body
    assert "Programas sem nível ativo" in body

    _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])
    body = client.get("/planejamento?aba=niveis").data.decode("utf-8")
    assert "programa_nivel" in body
    assert "Níveis sem programa" not in body  # nível criado já tem programa


# ---------------------------------------------------------------------------
# Leitores — resultado do conselho, ficha e resumo
# ---------------------------------------------------------------------------

def _fechar_com_dados(app, ids, nivel_id=None):
    """Grava conselhos FINAL com próximo curso (+nível) direto no banco."""
    with app.app_context():
        cid = Curso.query.filter_by(ativo=True).first().id
        for aluno_id in ids["alunos"]:
            db.session.add(ConselhoClasse(
                aluno_id=aluno_id, turma_id=ids["turma"],
                turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
                unidade_id=ids["unidade"], situacao_final="Aprovado",
                proximo_curso_id=cid, proximo_nivel_id=nivel_id,
                concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
            ))
        db.session.commit()
        return cid


def test_leitor_resultado_mostra_curso_e_nivel(client, app):
    ids = _setup(app)
    _login(client, ids)
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])
    _fechar_com_dados(app, ids, nivel_id=nid)

    r = client.get(
        f"/relatorios/conselho?periodo_letivo_id={_periodo(app, ids)}"
        f"&turmas={ids['turma']}&turmas_all=0"
    )
    body = r.data.decode("utf-8")
    assert r.status_code == 200
    assert "Curso AJ22" in body
    assert "Sub-12" in body
    assert "Próximo curso / Nível" in body


def test_leitor_resultado_fallback_legado(client, app):
    ids = _setup(app)
    _login(client, ids)
    oid = _opcao_legado(app, "Avançado legado")
    with app.app_context():
        for aluno_id in ids["alunos"]:
            db.session.add(ConselhoClasse(
                aluno_id=aluno_id, turma_id=ids["turma"],
                turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
                unidade_id=ids["unidade"], situacao_final="Aprovado",
                proxima_turma_id=oid,
                concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
            ))
        db.session.commit()

    body = client.get(
        f"/relatorios/conselho?periodo_letivo_id={_periodo(app, ids)}"
        f"&turmas={ids['turma']}"
    ).data.decode("utf-8")
    assert "Avançado legado" in body


def test_ficha_e_resumo_mostram_destino(client, app):
    ids = _setup(app)
    _login(client, ids)
    nid = _nivel(app, "Sub-12", programa="Esporte", unidade_id=ids["unidade"])
    _fechar_com_dados(app, ids, nivel_id=nid)

    resumo = client.get(
        f"/conselho/resumo/{ids['turma']}?turma_curso_id={ids['oferta']}"
        "&etapa=FINAL"
    )
    assert resumo.status_code == 200
    body = resumo.data.decode("utf-8")
    assert "Curso AJ22" in body and "Sub-12" in body


def _periodo(app, ids):
    with app.app_context():
        return Turma.query.get(ids["turma"]).periodo_letivo_id


def _contar_selects(engine, fn):
    contagem = {"n": 0}

    def counter(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            contagem["n"] += 1

    event.listen(engine, "before_cursor_execute", counter)
    try:
        fn()
    finally:
        event.remove(engine, "before_cursor_execute", counter)
    return contagem["n"]


def test_leitor_resultado_queries_constantes_com_2x_alunos(client, app):
    """N+1: o relatório não cresce em queries com o dobro de alunos."""
    ids7 = _setup(app, alunos=7)
    _login(client, ids7)
    nid = _nivel(app, "Sub-12", programa="Esporte",
                 unidade_id=ids7["unidade"])
    _fechar_com_dados(app, ids7, nivel_id=nid)
    pid = _periodo(app, ids7)

    n7 = _contar_selects(db.engine, lambda: client.get(
        f"/relatorios/conselho?periodo_letivo_id={pid}"
        f"&turmas={ids7['turma']}"
    ))

    # Duplica os alunos na mesma oferta (segundo setup usa outra turma —
    # aqui adicionamos 7 alunos extras na mesma turma/oferta).
    with app.app_context():
        for i in range(7):
            aluno = Aluno(
                nome=f"Extra {i}", unidade_id=ids7["unidade"], ativo=True,
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, ids7["turma"], ids7["oferta"])
            db.session.add(ConselhoClasse(
                aluno_id=aluno.id, turma_id=ids7["turma"],
                turma_curso_id=ids7["oferta"], etapa=EtapaConselho.FINAL,
                unidade_id=ids7["unidade"], situacao_final="Aprovado",
                concluido=True, data_inicio=DATA_INI, data_fim=DATA_FIM,
            ))
        db.session.commit()

    n14 = _contar_selects(db.engine, lambda: client.get(
        f"/relatorios/conselho?periodo_letivo_id={pid}"
        f"&turmas={ids7['turma']}"
    ))
    # Margem pequena para queries de apoio; o importante é não crescer
    # linearmente com alunos.
    assert n14 <= n7 + 5

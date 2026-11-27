"""Guia de Indicadores: aliases, ocultação, conteúdo, acesso e impressão."""

import inspect
import io
import re
from datetime import date, timedelta
from pathlib import Path

import pytest
from openpyxl import load_workbook

from app import db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PerfilDiversidade,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.relatorios.bi import INDICADORES_ALUNOS, executar_indicador
from app.relatorios.catalogo import (
    ALIASES,
    CODIGOS_OCULTOS_DA_CENTRAL,
    INDICADORES,
    ULTIMA_REVISAO_CATALOGO,
    VERSAO_CATALOGO,
    indicadores_para_guia,
    listar_indicadores,
    resolver_codigo,
    validar_catalogo_guia,
)
from _helpers import login_as, professor_semente

RAIZ = Path(__file__).resolve().parents[1]

CODIGOS_ORIGINAIS = frozenset(
    """
    ALU-001 ALU-002 ALU-003 ALU-004 ALU-005 ALU-006 ALU-007 ALU-008
    ALU-009 ALU-010 ALU-011 ALU-012 ALU-013 ALU-014 ALU-015 ALU-016
    ALU-017 ALU-018 INS-001 INS-002 INS-003 INS-004 INS-005 INS-006
    INS-007 INS-008 INS-009 FRE-001 FRE-002 FRE-003 FRE-004 FRE-005 FRE-006
    FRE-007 FRE-008 FRE-009 FRE-010 TUR-001 TUR-002 TUR-003 TUR-004
    TUR-005 TUR-006 TUR-007 TUR-008 AUL-001 AUL-002 AUL-003 AUL-004
    AUL-005 AUL-006 AUL-007 AUL-008 SOC-001 SOC-002 DIV-001 ATD-001
    CRU-001 CRU-002 CRU-003 CRU-004 CRU-005
    """.split()
)

PAIRES_ALIAS = (
    ("INS-001", "INS-004"),
    ("INS-003", "INS-005"),
    ("TUR-002", "TUR-001"),
    ("ALU-010", "TUR-003"),
)


def _criar_usuario(unidade, role, email):
    usuario = User(
        name=f"Usuário {role}",
        email=email,
        role=role,
        unidade_id=unidade.id,
        is_active=True,
        first_login=False,
    )
    db.session.add(usuario)
    db.session.commit()
    return usuario


def _semear():
    """Base pequena, mas com unidades/períodos/ofertas/status Variados."""
    hoje = date.today()
    unidades = [Unidade(nome=f"Unidade {i}", ativo=True) for i in (1, 2)]
    db.session.add_all(unidades)
    db.session.flush()

    periodos = []
    turmas = []
    for unidade in unidades:
        for rotulo, inicio, fim in (
            ("anterior", hoje - timedelta(days=400), hoje - timedelta(days=31)),
            ("atual", hoje - timedelta(days=7), hoje + timedelta(days=90)),
        ):
            periodo = PeriodoLetivo(
                nome=f"{unidade.nome}-{rotulo}",
                data_inicio=inicio,
                data_fim=fim,
                unidade_id=unidade.id,
                ativo=True,
            )
            db.session.add(periodo)
            db.session.flush()
            turma = Turma(
                nome=f"Turma {periodo.nome}",
                unidade_id=unidade.id,
                periodo_letivo_id=periodo.id,
                ativo=True,
                turno="Manhã",
            )
            db.session.add(turma)
            db.session.flush()
            periodos.append(periodo)
            turmas.append(turma)

    cursos = [
        Curso(nome=f"Curso {i}", unidade_id=unidades[0].id, ativo=True)
        for i in (1, 2)
    ]
    db.session.add_all(cursos)
    db.session.flush()

    professor = professor_semente(unidades[0].id)
    ofertas = []
    for indice, turma in enumerate(turmas):
        oferta = TurmaCurso(
            turma_id=turma.id,
            curso_id=cursos[indice % 2].id,
            professor_id=professor.id,
            unidade_id=turma.unidade_id,
            turno="Manhã",
            ativo=True,
            principal=True,
            programa="Teste",
        )
        db.session.add(oferta)
        db.session.flush()
        ofertas.append(oferta)

    alunos = []
    for i in range(1, 6):
        aluno = Aluno(
            nome=f"Aluno {i}",
            unidade_id=unidades[i % 2].id,
            ativo=(i != 5),
            created_at=hoje - timedelta(days=i),
            data_nascimento=date(2010 + i, 1, 1),
        )
        db.session.add(aluno)
        db.session.flush()
        alunos.append(aluno)
        if i < 4:
            db.session.add(
                PerfilDiversidade(
                    aluno_id=aluno.id,
                    unidade_id=aluno.unidade_id,
                    saude_laudo=True,
                )
            )

    for aluno, turma, oferta, ativo in (
        (alunos[0], turmas[1], ofertas[1], True),
        (alunos[1], turmas[0], ofertas[0], False),
        (alunos[1], turmas[1], ofertas[1], True),
        (alunos[2], turmas[3], ofertas[3], True),
        (alunos[3], turmas[1], ofertas[1], False),
        (alunos[4], turmas[1], ofertas[1], True),
    ):
        db.session.add(
            Inscricao(
                aluno_id=aluno.id,
                turma_id=turma.id,
                turma_curso_id=oferta.id,
                data_inicio=hoje - timedelta(days=20),
                ativo=ativo,
            )
        )
    db.session.commit()
    return {
        "unidade": unidades[0].id,
        "periodo_anterior": periodos[0].id,
        "periodo_atual": periodos[1].id,
        "turma": turmas[1].id,
        "curso": cursos[0].id,
        "professor": professor.id,
        "hoje": hoje,
    }


def _filtros(cenario):
    return [
        {},
        {"unidade_id": cenario["unidade"]},
        {"periodo_letivo_id": cenario["periodo_atual"]},
        {"turno": "Manhã"},
        {"curso_id": cenario["curso"]},
        {"turma_id": cenario["turma"]},
        {"professor_id": cenario["professor"]},
        {
            "unidade_id": cenario["unidade"],
            "periodo_letivo_id": cenario["periodo_atual"],
        },
        {"data_inicio": cenario["hoje"] - timedelta(days=30)},
    ]


def _permitidos(codigo, filtros):
    funcao = INDICADORES_ALUNOS[resolver_codigo(codigo)]
    aceitos = inspect.signature(funcao).parameters
    return {k: v for k, v in filtros.items() if k in aceitos}


def _query(filtros):
    return "&".join(f"{chave}={valor}" for chave, valor in filtros.items())


def _linhas_xlsx(resposta):
    workbook = load_workbook(io.BytesIO(resposta.data), data_only=True)
    return [
        [celula.value for celula in linha]
        for linha in workbook["Resultado"].iter_rows(min_row=5)
    ]


def test_nenhum_codigo_removido_e_aliases_explicitos(app):
    with app.app_context():
        assert set(INDICADORES) == CODIGOS_ORIGINAIS
        assert len(INDICADORES) == 62
        for alias, canonico in ALIASES.items():
            assert alias in INDICADORES
            assert canonico in INDICADORES
            assert resolver_codigo(alias) == canonico
            assert resolver_codigo(canonico) == canonico
        assert CODIGOS_OCULTOS_DA_CENTRAL == frozenset(ALIASES) | {
            "INS-006",
            "INS-007",
        }


def test_catalogo_do_guia_e_completo_e_sem_codigo_de_tarefa(app):
    with app.app_context():
        assert validar_catalogo_guia() is True
        itens = indicadores_para_guia()
        assert len(itens) == len(CODIGOS_ORIGINAIS)
        padrao = re.compile(r"\bAJ\s*\d+[A-Za-z]?\b", re.IGNORECASE)
        for item in itens:
            assert item["mede"] and item["regra"] and item["unidade"]
            assert item["filtros"] is not None
            assert item["nao_aplicaveis"] is not None
            texto = " ".join(
                [
                    item["nome"],
                    item["mede"],
                    item["regra"],
                    *item["observacoes"],
                ]
            )
            assert not padrao.search(texto)


def test_pares_alias_provados_com_mesmos_dados_e_varios_filtros(app):
    with app.app_context():
        cenario = _semear()

        assert executar_indicador("INS-003", unidade_id=cenario["unidade"]) == 2
        assert executar_indicador("TUR-002", unidade_id=cenario["unidade"]) == 2
        assert executar_indicador("ALU-010", unidade_id=cenario["unidade"])

        for canonico, alias in PAIRES_ALIAS:
            valores = []
            for filtro in _filtros(cenario):
                permitidos = _permitidos(canonico, filtro)
                esperado = executar_indicador(canonico, **permitidos)
                obtido = executar_indicador(alias, **permitidos)
                assert obtido == esperado, (canonico, alias, permitidos)
                valores.append(esperado)
            assert any(valor not in (0, 0.0, [], None) for valor in valores)


def test_alias_resolvem_na_api_e_no_xlsx(app, client):
    with app.app_context():
        cenario = _semear()
        admin_id = _criar_usuario(
            db.session.get(Unidade, cenario["unidade"]),
            "admin",
            "guia.admin@example.test",
        ).id
    login_as(client, admin_id, cenario["unidade"])

    filtros_api = [
        {"unidade_id": cenario["unidade"]},
        {"periodo_letivo_id": cenario["periodo_atual"]},
        {"turno": "Manhã"},
        {"curso_id": cenario["curso"]},
    ]
    for canonico, alias in PAIRES_ALIAS:
        for filtro in filtros_api:
            permitidos = _permitidos(canonico, filtro)
            query = _query(permitidos)
            resposta_canonical = client.get(
                f"/relatorios/bi/indicador/{canonico}?{query}"
            )
            resposta_alias = client.get(f"/relatorios/bi/indicador/{alias}?{query}")
            assert resposta_canonical.status_code == 200
            assert resposta_alias.status_code == 200
            assert resposta_alias.json["indicador"] == alias
            assert resposta_alias.json["resultado"] == resposta_canonical.json[
                "resultado"
            ]

            xlsx_canonical = client.get(f"/relatorios/bi/exportar/xlsx?codigo={canonico}&{query}")
            xlsx_alias = client.get(f"/relatorios/bi/exportar/xlsx?codigo={alias}&{query}")
            assert xlsx_canonical.status_code == 200
            assert xlsx_alias.status_code == 200
            assert _linhas_xlsx(xlsx_alias) == _linhas_xlsx(xlsx_canonical)


def test_central_nao_oferece_aliases_mas_catalogo_os_mantem(app, client):
    with app.app_context():
        unidade = Unidade(nome="Unidade Central", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin_id = _criar_usuario(
            unidade, "admin", "central.admin@example.test"
        ).id
        unidade_id = unidade.id
    login_as(client, admin_id, unidade_id)

    html = client.get("/relatorios/bi").get_data(as_text=True)
    catalogo = listar_indicadores()
    for codigo in CODIGOS_OCULTOS_DA_CENTRAL:
        assert codigo not in html
        assert codigo in catalogo
    for codigo in set(CODIGOS_ORIGINAIS) - CODIGOS_OCULTOS_DA_CENTRAL:
        assert f'value="{codigo}"' in html
    assert "/relatorios/bi/indicadores" in html
    assert "Guia de indicadores" in html
    assert "Como é calculado" in html
    assert "encodeURIComponent(codigoAtual)" in html


@pytest.mark.parametrize("perfil,esperado", (("admin", 200), ("pedagogico", 200), ("professor", 403)))
def test_guia_tem_o_mesmo_controle_de_acesso_da_central(app, client, perfil, esperado):
    with app.app_context():
        unidade = Unidade(nome=f"Unidade Guia {perfil}", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        usuario_id = _criar_usuario(
            unidade, perfil, f"guia.{perfil}@example.test"
        ).id
        unidade_id = unidade.id
    login_as(client, usuario_id, unidade_id)
    resposta = client.get("/relatorios/bi/indicadores")
    assert resposta.status_code == esperado


def test_guia_e_gerado_do_catalogo_com_busca_ancoras_e_impressao(app, client):
    anonimo = app.test_client()
    assert anonimo.get("/relatorios/bi/indicadores").status_code in (302, 401)

    with app.app_context():
        unidade = Unidade(nome="Unidade Guia Conteúdo", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        admin_id = _criar_usuario(
            unidade, "admin", "guia.conteudo@example.test"
        ).id
        unidade_id = unidade.id
    login_as(client, admin_id, unidade_id)
    resposta = client.get("/relatorios/bi/indicadores")
    assert resposta.status_code == 200
    html = resposta.get_data(as_text=True)

    assert "Guia de Indicadores" in html
    assert "Glossário" in html
    assert "Cadastro novo × aluno novo" in html
    assert "Índice por categoria" in html
    assert "O que mede" in html
    assert "Como é calculado" in html
    assert "Filtros aplicáveis" in html
    assert "Filtros que não se aplicam" in html
    assert "Expandir tudo" in html
    assert "Recolher tudo" in html
    assert VERSAO_CATALOGO in html
    assert ULTIMA_REVISAO_CATALOGO in html
    assert 'data-pdf-nome="Guia de Indicadores - pautaON - {data}"' in html
    assert "css/relatorios/guia_indicadores.css" in html
    assert "js/relatorios/guia_indicadores.js" in html

    catalogo = listar_indicadores()
    for codigo in catalogo:
        assert f'id="{codigo}"' in html
    assert 'href="#ALU-010"' in html
    assert 'id="ALU-010"' in html
    assert "Substituído por INS-003" in html
    assert "Indisponível" in html

    visivel = re.sub(r"<[^>]+>", " ", html)
    visivel = visivel.replace("&middot;", " ").replace("&nbsp;", " ")
    assert not re.search(r"\bAJ\s*\d+[A-Za-z]?\b", visivel, re.IGNORECASE)

    css = (RAIZ / "app/static/css/relatorios/guia_indicadores.css").read_text(
        encoding="utf-8"
    )
    assert "@page" in css
    assert "#conteudo-impressao" in css
    assert ".print-only" in css
    assert "d-print-none" in css
    assert "break-inside: avoid" in css

    js = (RAIZ / "app/static/js/relatorios/guia_indicadores.js").read_text(
        encoding="utf-8"
    )
    assert "buscaIndicador" in js
    assert "normalizar" in js
    assert "data-guia-toggle" in js
    assert "hashchange" in js
    assert "expandir" in js and "recolher" in js

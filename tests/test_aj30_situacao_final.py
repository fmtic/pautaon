"""AJ30 — fechamento do conselho: vocabulário único, NULL e autosave por linha.

Cobre o contrato novo ponta a ponta no SQLite:
    1. enum/lista ordenada como fonte única (sem valores antigos);
    2. AJ30-B: select e impressão mostram o mesmo "—" (value="" = NULL);
    3. POST de UMA linha para cada situação canônica;
    4. vazio/"—" grava NULL e NÃO cria ConselhoClasse (regra AJ20);
    5. payload inválido não altera situação/curso/nível gravados (rollback);
    6. badges do resultado: "—" em vez de "Sem Registro";
    7. aviso "N aluno(s) sem situação final definida" antes de encerrar;
    8. sumário de leitores com os 6 valores + NULL.
"""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pytest
from _helpers import login_as, nova_inscricao, nova_oferta

from app.database import db
from app.models import (
    Aluno,
    ConselhoClasse,
    Curso,
    PeriodoConselho,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import (
    SITUACAO_FINAL_BADGES,
    SITUACAO_FINAL_INDEFINIDA,
    SITUACAO_FINAL_LEGADO,
    SITUACAO_FINAL_OPCOES,
    EtapaConselho,
    SituacaoFinal,
)

DATA_INI, DATA_FIM = date(2026, 2, 2), date(2026, 6, 30)


def _setup(app, *, dois_alunos=False):
    with app.app_context():
        unidade = Unidade(nome="Unidade AJ30", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        usuario = User(
            name="User AJ30", email="aj30@teste.local", role="admin",
            first_login=False, unidade_id=unidade.id,
        )
        usuario.set_password("SenhaLocal!123")
        periodo = PeriodoLetivo(
            nome="Período AJ30", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        curso = Curso(nome="Curso AJ30", unidade_id=unidade.id, ativo=True)
        outro = Curso(nome="Curso Destino AJ30", unidade_id=unidade.id, ativo=True)
        db.session.add_all([usuario, periodo, curso, outro])
        db.session.flush()

        turma = Turma(
            nome="Turma AJ30", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, unidade.id, programa="Esporte", principal=True
        )
        db.session.add(PeriodoConselho(
            nome="Conselho Final AJ30", data_inicio=date(2026, 6, 1),
            data_fim=date(2026, 6, 20), conselho_final=True,
            periodo_letivo_id=periodo.id, unidade_id=unidade.id,
        ))

        alunos = []
        for indice in range(2 if dois_alunos else 1):
            aluno = Aluno(
                nome=f"Aluno AJ30 {indice + 1}", unidade_id=unidade.id, ativo=True
            )
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, turma.id, oferta.id)
            alunos.append(aluno.id)

        db.session.commit()
        return {
            "user_id": usuario.id, "unidade": unidade.id,
            "turma": turma.id, "oferta": oferta.id,
            "periodo": periodo.id, "curso": curso.id, "outro_curso": outro.id,
            "alunos": alunos,
        }


def _post(client, ids, aluno_id, situacao, curso_id="", nivel_id=""):
    return client.post(
        f"/conselho/fechamento/{ids['turma']}/salvar",
        json={
            "oferta_id": ids["oferta"],
            "aluno_id": aluno_id,
            "situacao": situacao,
            "proximo_curso_id": curso_id,
            "proximo_nivel_id": nivel_id,
        },
    )


def _conselho(ids, aluno_id):
    return ConselhoClasse.query.filter_by(
        turma_curso_id=ids["oferta"], aluno_id=aluno_id,
        etapa=EtapaConselho.FINAL,
    ).first()


# ---------------------------------------------------------------------------
# (1) fonte única
# ---------------------------------------------------------------------------

def test_vocabulario_final_e_mapa_de_renomeacao():
    assert list(SITUACAO_FINAL_OPCOES) == [
        "Aprovado", "Participante", "Reprovado por faltas",
        "Desistente", "Evadido", "Empregado",
    ]
    assert [s.value for s in SituacaoFinal] == list(SITUACAO_FINAL_OPCOES)
    assert SITUACAO_FINAL_LEGADO == {
        "Concluído": "Aprovado",
        "Participação": "Participante",
        "Reprovado por Falta": "Reprovado por faltas",
    }
    # Apelidos de NOME continuam resolvendo para o valor canônico.
    assert SituacaoFinal.PARTICIPACAO.value == "Participante"
    assert SituacaoFinal.REPROVADO_POR_FALTA.value == "Reprovado por faltas"
    # O mapa de badges aceita apelidos históricos só para leitura de dados
    # pré-migração; o domínio gravado continua sendo o enum de 6 valores.
    assert SITUACAO_FINAL_BADGES["Concluído"] == SITUACAO_FINAL_BADGES["Aprovado"]
    assert SITUACAO_FINAL_BADGES["Participante"][1] == "Participante"
    assert SITUACAO_FINAL_BADGES[""][1] == SITUACAO_FINAL_INDEFINIDA == "—"


# ---------------------------------------------------------------------------
# (2) tela
# ---------------------------------------------------------------------------

def test_select_e_impressao_usam_o_mesmo_traco(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    html = client.get(
        f"/conselho/fechamento/{ids['turma']}?oferta_sel={ids['oferta']}"
    ).get_data(as_text=True)

    trecho = html[html.index("situacao-select"):html.index("</select>", html.index("situacao-select"))]
    opcoes = re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', trecho)
    assert SITUACAO_FINAL_INDEFINIDA == "—"
    assert opcoes[0] == ("", SITUACAO_FINAL_INDEFINIDA)
    assert [valor for valor, _ in opcoes[1:]] == list(SITUACAO_FINAL_OPCOES)
    assert "selected" not in opcoes[0][0]
    assert "Concluído" not in trecho and "Participação" not in trecho
    assert "Reprovado por Falta<" not in trecho
    assert "Não definido" not in html
    assert 'aria-label="Situação final"' in trecho
    assert 'title="Situação final não definida"' in trecho
    assert 'aria-label="Situação final não definida"' in trecho
    assert f'data-rotulo-ausente="{SITUACAO_FINAL_INDEFINIDA}"' in trecho

    span = re.search(
        r'<span class="d-none d-print-inline situacao-texto[^"]*"([^>]*)>([^<]*)</span>',
        html,
    )
    assert span is not None
    assert span.group(2).strip() == SITUACAO_FINAL_INDEFINIDA
    assert 'title="Situação final não definida"' in span.group(1)
    assert 'aria-label="Situação final não definida"' in span.group(1)
    assert "As alterações são salvas automaticamente." in html
    assert "Salvar Fechamento" not in html
    assert "autosave-indicador" in html and 'aria-live="polite"' in html
    assert "autosave.js" in html


# ---------------------------------------------------------------------------
# (3)/(4)/(5) POST de uma linha
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("situacao", list(SITUACAO_FINAL_OPCOES))
def test_post_de_uma_linha_para_cada_situacao(app, client, situacao):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    aluno_id = ids["alunos"][0]

    resposta = _post(client, ids, aluno_id, situacao)
    assert resposta.get_json() == {"success": True}
    with app.app_context():
        conselho = _conselho(ids, aluno_id)
        assert conselho is not None
        assert conselho.situacao_final == situacao
        assert conselho.concluido is True
        assert conselho.data_fim == date.today()


def test_vazio_grava_null_e_nao_cria_linha(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    aluno_id = ids["alunos"][0]

    assert _post(client, ids, aluno_id, "").get_json() == {"success": True}
    with app.app_context():
        assert _conselho(ids, aluno_id) is None

    # Com linha já existente, o "—" limpa o valor mas NÃO apaga a
    # linha (histórico/respostas do conselho ficam preservados).
    assert _post(client, ids, aluno_id, "Aprovado").get_json()["success"] is True
    assert _post(client, ids, aluno_id, "").get_json() == {"success": True}
    with app.app_context():
        conselho = _conselho(ids, aluno_id)
        assert conselho is not None
        assert conselho.situacao_final is None


def test_invalido_recusa_tudo_e_preserva_curso_e_nivel(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    aluno_id = ids["alunos"][0]

    assert _post(
        client, ids, aluno_id, "Aprovado", ids["curso"], ""
    ).get_json()["success"] is True
    recusa = _post(
        client, ids, aluno_id, "SITUACAO_INEXISTENTE", ids["outro_curso"], 999999
    )
    assert recusa.get_json()["success"] is False
    assert "Situação final inválida" in recusa.get_json()["message"]

    with app.app_context():
        conselho = _conselho(ids, aluno_id)
        assert conselho.situacao_final == "Aprovado"
        assert conselho.proximo_curso_id == ids["curso"]
        assert conselho.proximo_nivel_id is None


def test_valores_antigos_sao_normalizados_na_fronteira(app, client):
    ids = _setup(app)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    aluno_id = ids["alunos"][0]
    for antigo, novo in SITUACAO_FINAL_LEGADO.items():
        assert _post(client, ids, aluno_id, antigo).get_json()["success"] is True
        with app.app_context():
            assert _conselho(ids, aluno_id).situacao_final == novo


# ---------------------------------------------------------------------------
# (6) leitores
# ---------------------------------------------------------------------------

def test_resultado_conselho_mostra_traco_e_novos_badges(app, client):
    ids = _setup(app, dois_alunos=True)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    with app.app_context():
        for aluno_id, situacao in zip(ids["alunos"], ("Participante", None), strict=False):
            db.session.add(ConselhoClasse(
                aluno_id=aluno_id, turma_id=ids["turma"],
                turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
                unidade_id=ids["unidade"], situacao_final=situacao,
                concluido=True, observacao="conteúdo",
            ))
        db.session.commit()

    html = client.get("/relatorios/conselho", query_string={
        "periodo_letivo_id": ids["periodo"], "turmas": ids["turma"],
    }).get_data(as_text=True)
    assert "Sem Registro" not in html
    assert "Não definido" not in html
    assert "badge-situacao-participante" in html
    badge = re.search(
        r'<span class="badge badge-situacao-nao-definido"([^>]*)>([^<]*)</span>',
        html,
    )
    assert badge is not None
    assert badge.group(2).strip() == SITUACAO_FINAL_INDEFINIDA
    assert 'title="Situação final não definida"' in badge.group(1)
    assert 'aria-label="Situação final não definida"' in badge.group(1)


def test_rotulo_antigo_so_existe_nos_casos_b():
    raiz = Path(__file__).resolve().parents[1] / "app"
    # (b) Programa/centro de custo e a regra de ocultá-los — não é situação
    # final e deve continuar exatamente como está.
    casos_b = {
        raiz / "registros" / "turmas.py",
        raiz / "templates" / "turmas" / "detalhe.html",
        raiz / "templates" / "turmas" / "editar.html",
        raiz / "templates" / "turmas" / "listar.html",
    }
    for arquivo in casos_b:
        assert "Não definido" in arquivo.read_text(encoding="utf-8")

    encontrados = []
    for arquivo in sorted(raiz.rglob("*")):
        if arquivo.suffix not in {".py", ".html", ".js"} or arquivo in casos_b:
            continue
        if "Não definido" in arquivo.read_text(encoding="utf-8", errors="ignore"):
            encontrados.append(str(arquivo.relative_to(raiz)))
    assert encontrados == []


def test_aviso_de_encerramento_calcula_pendencias_em_lote(app, client):
    ids = _setup(app, dois_alunos=True)
    login_as(client, str(ids["user_id"]), ids["unidade"])
    with app.app_context():
        db.session.add(ConselhoClasse(
            aluno_id=ids["alunos"][0], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], etapa=EtapaConselho.FINAL,
            unidade_id=ids["unidade"], situacao_final="Aprovado",
            concluido=True,
        ))
        db.session.commit()

    html = client.get("/conselho").get_data(as_text=True)
    assert 'confirmarEncerramento(event, 1)' in html
    assert 'onsubmit="return confirmarEncerramento(event, 1);"' in html
    assert "/static/js/conselho/conselho.js" in html

    # Depois de definir o segundo aluno, não há pendência.
    assert _post(client, ids, ids["alunos"][1], "Evadido").get_json()["success"] is True
    html = client.get("/conselho").get_data(as_text=True)
    assert 'confirmarEncerramento(event, 0)' in html

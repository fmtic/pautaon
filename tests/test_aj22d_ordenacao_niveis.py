"""AJ22-D — Níveis agrupados por curso e ordenados A-Z (só apresentação).

Sem migration, sem mudança de schema e sem alterar regras de gravação:
a ordenação é feita em memória com chave normalizada (casefold + sem
acentos), desempate por `id`, e reutilizada pela aba Níveis do
planejamento e pelos selects de nível de `turmas/detalhe.html`.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import event

from app.database import db
from app.models import Aluno, Curso, Nivel, PeriodoLetivo, Turma, Unidade, User
from app.utils.ordenacao import chave_ordenacao
from _helpers import login_as, nova_inscricao, nova_oferta

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)
LINHA_NIVEL = (
    r'<i class="bi bi-bar-chart-fill me-2 small opacity-50"></i>([^<\n]+)'
)


def _seed(app):
    """Unidade + admin + turma/oferta + um aluno (para os selects da turma)."""
    with app.app_context():
        un = Unidade(nome="Unidade D", ativo=True)
        db.session.add(un)
        db.session.flush()
        usuario = User(
            name="Admin D", email="aj22d@example.com", role="admin",
            first_login=False,
        )
        periodo = PeriodoLetivo(
            nome="Periodo D", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso_base = Curso(nome="Curso Base", unidade_id=un.id, ativo=True)
        db.session.add_all([usuario, periodo, curso_base])
        db.session.flush()
        turma = Turma(
            nome="Turma D", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta = nova_oferta(turma.id, curso_base.id, un.id, principal=True)
        aluno = Aluno(nome="Aluno D", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, oferta.id)
        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": un.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "curso_base": curso_base.id,
            "aluno": aluno.id,
        }


def _login(client, ids):
    login_as(client, str(ids["user_id"]), ids["unidade"])


def _curso(app, nome, unidade_id, ativo=True):
    with app.app_context():
        curso = Curso(nome=nome, unidade_id=unidade_id, ativo=ativo)
        db.session.add(curso)
        db.session.commit()
        return curso.id


def _nivel(app, nome, curso_id, unidade_id, ativo=True):
    with app.app_context():
        nivel = Nivel(
            nome=nome, curso_id=curso_id, unidade_id=unidade_id, ativo=ativo,
        )
        db.session.add(nivel)
        db.session.commit()
        return nivel.id


def _blocos(body):
    """Posições dos cabeçalhos de bloco no HTML (`sem-curso` ou id do curso)."""
    return {
        chave: match.start()
        for match in re.finditer(r'data-grupo-nivel="([^"]+)"', body)
        for chave in [match.group(1)]
    }


def _nomes_linhas(body):
    return re.findall(LINHA_NIVEL, body)


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


# ---------------------------------------------------------------------------
# Chave normalizada
# ---------------------------------------------------------------------------

def test_chave_ordenacao_acentos_e_caixa():
    assert chave_ordenacao("Álgebra") == "algebra"
    assert chave_ordenacao("Básico") == "basico"
    assert chave_ordenacao("avançado") == chave_ordenacao("Avançado")
    assert chave_ordenacao(None) == ""
    assert chave_ordenacao("Álgebra") < chave_ordenacao("Básico")


def test_ordem_acentos_e_caixa_mista_no_cadastro(client, app):
    ids = _seed(app)
    _login(client, ids)
    # Inserção de propósito fora de ordem: a página tem que ordenar.
    for nome in ("Básico", "avançado", "Álgebra", "Avançado"):
        _nivel(app, nome, None, ids["unidade"])

    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)
    nomes = _nomes_linhas(body)
    # Álgebra < avançado/Avançado (juntos, desempate por id) < Básico.
    assert [chave_ordenacao(n) for n in nomes] == sorted(
        chave_ordenacao(n) for n in nomes
    )
    assert nomes[0] == "Álgebra"
    assert nomes[-1] == "Básico"
    assert nomes[1:3] in (["avançado", "Avançado"], ["Avançado", "avançado"])


# ---------------------------------------------------------------------------
# Agrupamento na aba Níveis
# ---------------------------------------------------------------------------

def test_agrupamento_por_curso_contagem_e_ordem_a_z(client, app):
    ids = _seed(app)
    _login(client, ids)
    # Cursos criados em ordem inversa para provar que a ordem vem do helper.
    zeta = _curso(app, "Zeta", ids["unidade"])
    alfa = _curso(app, "Alfa", ids["unidade"])
    _nivel(app, "Básico", zeta, ids["unidade"])
    _nivel(app, "Álgebra", zeta, ids["unidade"])
    _nivel(app, "Intermediário", alfa, ids["unidade"])
    _nivel(app, "Avulso", None, ids["unidade"])

    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)
    pos = _blocos(body)
    assert pos["sem-curso"] < pos[str(alfa)] < pos[str(zeta)]
    # Curso da oferta não tem nível: não gera bloco.
    assert str(ids["curso_base"]) not in pos
    # "Sem curso" no topo, Alfa (1) e Zeta (2) com contagem no cabeçalho.
    assert "1 nível" in body
    assert "2 níveis" in body
    assert _nomes_linhas(body) == [
        "Avulso", "Intermediário", "Álgebra", "Básico",
    ]


def test_curso_sem_nivel_nao_gera_bloco(client, app):
    ids = _seed(app)
    _login(client, ids)
    vazio = _curso(app, "Curso Vazio", ids["unidade"])
    preenchido = _curso(app, "Curso Preenchido", ids["unidade"])
    _nivel(app, "Único", preenchido, ids["unidade"])

    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)
    pos = _blocos(body)
    assert str(vazio) not in pos
    assert str(preenchido) in pos
    assert "Curso Vazio" in body  # continua no select de cadastro


def test_inativos_no_fim_do_bloco_com_etiqueta(client, app):
    ids = _seed(app)
    _login(client, ids)
    curso = _curso(app, "Curso Misto", ids["unidade"])
    _nivel(app, "Zumbi", curso, ids["unidade"])                  # ativo
    _nivel(app, "Álgebra", curso, ids["unidade"], ativo=False)   # inativo
    _nivel(app, "Beta", curso, ids["unidade"])                   # ativo

    body = client.get("/planejamento?aba=niveis").get_data(as_text=True)
    assert _nomes_linhas(body) == ["Beta", "Zumbi", "Álgebra"]
    assert "INATIVO" in body
    assert "opacity-50 bg-light" in body


# ---------------------------------------------------------------------------
# Selects de turmas/detalhe.html
# ---------------------------------------------------------------------------

def test_selects_da_turma_ordenados_por_curso_e_nivel(client, app):
    ids = _seed(app)
    _login(client, ids)
    zeta = _curso(app, "Zeta", ids["unidade"])
    alfa = _curso(app, "Alfa", ids["unidade"])
    # AJ22-E: a ficha mostra somente os níveis do curso DA OFERTA do aluno;
    # a ordem A-Z continua valendo dentro desse conjunto (AJ22-D).
    _nivel(app, "Básico", ids["curso_base"], ids["unidade"])
    _nivel(app, "Álgebra", ids["curso_base"], ids["unidade"])
    _nivel(app, "Intermediário", alfa, ids["unidade"])
    _nivel(app, "Zeta Nível", zeta, ids["unidade"])
    _nivel(app, "Avulso", None, ids["unidade"])

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    selects = re.findall(
        r'<select name="nivel"[^>]*>(.*?)</select>', body, re.S
    )
    assert selects, "select de nível do aluno não encontrado"
    opcoes = re.findall(
        r'<option value="([^"]*)"[^>]*>([^<]*)</option>', selects[0]
    )
    # Valores e rótulos continuam sendo apenas o nome do nível (AJ22-E).
    assert [valor for valor, _ in opcoes] == [
        "Não se aplica", "Álgebra", "Básico",
    ]
    assert [texto for _, texto in opcoes] == [
        "Não se aplica", "Álgebra", "Básico",
    ]
    # Níveis de outros cursos e o legado sem curso ficam de fora.
    for nome in ("Intermediário", "Zeta Nível", "Avulso"):
        assert nome not in [valor for valor, _ in opcoes]


# ---------------------------------------------------------------------------
# Sem N+1
# ---------------------------------------------------------------------------

def test_queries_constantes_com_2x7_niveis(client, app):
    ids = _seed(app)
    _login(client, ids)
    curso = _curso(app, "Curso N+1", ids["unidade"])
    for indice in range(7):
        _nivel(app, f"Nível {indice:02d}", curso, ids["unidade"])

    def carregar():
        return client.get("/planejamento?aba=niveis").get_data(as_text=True)

    n7 = _contar_selects(db.engine, carregar)
    for indice in range(7, 14):
        _nivel(app, f"Nível {indice:02d}", curso, ids["unidade"])
    n14 = _contar_selects(db.engine, carregar)

    # Margem para consultas de apoio; o que importa é não crescer por nível.
    assert n14 <= n7 + 5

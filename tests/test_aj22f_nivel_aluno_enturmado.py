"""AJ22-F — Select de nível do aluno JÁ enturmado: valor atual preservado.

Mesma regra do AJ22-E (somente níveis ativos do curso da oferta da inscrição,
da unidade da turma ou globais), mas a ficha do aluno enturmado agora mostra
o valor já gravado como primeira opção ``(atual)`` mesmo quando ele não existe
no catálogo ou pertence a outro curso. O POST ``atualizar_nivel_aluno``
sanitiza valores novos fora do conjunto do curso, mas aceita o valor atual.

``Inscricao.nivel`` continua sendo texto livre; sem migration e sem schema.
"""

from __future__ import annotations

import re
from datetime import date

from sqlalchemy import event

from app.database import db
from app.models import Aluno, Curso, Inscricao, Nivel, PeriodoLetivo, Turma, Unidade, User
from _helpers import login_as, nova_inscricao, nova_oferta

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _seed(app):
    with app.app_context():
        un = Unidade(nome="Unidade F Aluno", ativo=True)
        db.session.add(un)
        db.session.flush()
        usuario = User(
            name="Admin F Aluno", email="aj22f-aluno@example.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        periodo = PeriodoLetivo(
            nome="Periodo F Aluno", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso_a = Curso(nome="Curso A", unidade_id=un.id, ativo=True)
        curso_b = Curso(nome="Curso B", unidade_id=un.id, ativo=True)
        curso_vazio = Curso(nome="Curso Vazio", unidade_id=un.id, ativo=True)
        db.session.add_all([usuario, periodo, curso_a, curso_b, curso_vazio])
        db.session.flush()
        turma = Turma(
            nome="Turma F Aluno", data_inicio=DATA_INI, data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()
        oferta_a = nova_oferta(turma.id, curso_a.id, un.id, principal=True)
        oferta_b = nova_oferta(turma.id, curso_b.id, un.id, principal=False)
        oferta_vazia = nova_oferta(turma.id, curso_vazio.id, un.id, principal=False)

        db.session.add_all([
            Nivel(nome="Iniciante A", curso_id=curso_a.id, unidade_id=un.id, ativo=True),
            Nivel(nome="Avançado A", curso_id=curso_a.id, unidade_id=un.id, ativo=True),
            Nivel(nome="Módulo B", curso_id=curso_b.id, unidade_id=un.id, ativo=True),
        ])
        db.session.flush()
        aluno = Aluno(nome="Aluno F", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.commit()
        return {
            "user_id": usuario.id,
            "unidade": un.id,
            "turma": turma.id,
            "curso_a": curso_a.id,
            "curso_b": curso_b.id,
            "oferta_a": oferta_a.id,
            "oferta_b": oferta_b.id,
            "oferta_vazia": oferta_vazia.id,
            "aluno": aluno.id,
        }


def _login(client, ids):
    login_as(client, str(ids["user_id"]), ids["unidade"])


def _opcoes_ficha(body, oferta_id, aluno_id):
    padrao = (
        rf'id="detalhes-oferta-{oferta_id}".*?/aluno/{aluno_id}/atualizar-nivel'
        r'.*?<select name="nivel"[^>]*>(.*?)</select>'
    )
    match = re.search(padrao, body, re.S)
    assert match, f"select do aluno {aluno_id} na oferta {oferta_id} não encontrado"
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', match.group(1))


def _post_nivel(client, ids, oferta_id, nivel, aluno_id=None):
    return client.post(
        f"/aluno/{aluno_id or ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": oferta_id,
            "nivel": nivel,
        },
        follow_redirects=True,
    )


def _niveis_grabados(app, ids, oferta_id):
    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            turma_curso_id=oferta_id, aluno_id=ids["aluno"], ativo=True
        ).first()
        aluno = db.session.get(Aluno, ids["aluno"])
        return inscricao.nivel if inscricao else None, aluno.nivel


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
# Valor atual "(atual)" na ficha do aluno enturmado
# ---------------------------------------------------------------------------


def test_valor_atual_fora_do_catalogo_e_primeira_opcao_e_preservado(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Legado Livre")
        db.session.commit()
    _login(client, ids)

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    opcoes = _opcoes_ficha(body, ids["oferta_a"], ids["aluno"])
    assert opcoes[0] == ("Legado Livre", "Legado Livre (atual)")
    assert '<option value="Legado Livre" selected>Legado Livre (atual)</option>' in body
    assert [valor for valor, _ in opcoes[1:]] == [
        "Não se aplica", "Avançado A", "Iniciante A",
    ]

    # Salvar sem mudar não apaga o texto livre.
    resposta = _post_nivel(client, ids, ids["oferta_a"], "Legado Livre")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == ("Legado Livre", "Legado Livre")


def test_valor_atual_de_outro_curso_aparece_e_nao_entra_no_catalogo(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Módulo B")
        db.session.commit()
    _login(client, ids)

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    opcoes = _opcoes_ficha(body, ids["oferta_a"], ids["aluno"])
    assert opcoes[0] == ("Módulo B", "Módulo B (atual)")
    assert "Módulo B" not in [valor for valor, _ in opcoes[1:]]
    assert "Não se aplica" in [valor for valor, _ in opcoes]

    resposta = _post_nivel(client, ids, ids["oferta_a"], "Módulo B")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == ("Módulo B", "Módulo B")


def test_valor_atual_em_catalogo_nao_duplica_opcao(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Iniciante A")
        db.session.commit()
    _login(client, ids)

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    opcoes = _opcoes_ficha(body, ids["oferta_a"], ids["aluno"])
    assert opcoes[0] == ("Iniciante A", "Iniciante A (atual)")
    assert [valor for valor, _ in opcoes].count("Iniciante A") == 1
    assert [valor for valor, _ in opcoes[1:]] == ["Não se aplica", "Avançado A"]


def test_curso_sem_niveis_mostra_atual_e_nao_se_aplica(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(
            ids["aluno"], ids["turma"], ids["oferta_vazia"], nivel="Texto Antigo"
        )
        db.session.commit()
    _login(client, ids)

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    opcoes = _opcoes_ficha(body, ids["oferta_vazia"], ids["aluno"])
    assert opcoes == [
        ("Texto Antigo", "Texto Antigo (atual)"),
        ("Não se aplica", "Não se aplica"),
    ]

    resposta = _post_nivel(client, ids, ids["oferta_vazia"], "Texto Antigo")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_vazia"]) == ("Texto Antigo", "Texto Antigo")


def test_valor_atual_apenas_na_ficha_do_aluno_tambem_e_aceito(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"])
        aluno = db.session.get(Aluno, ids["aluno"])
        aluno.nivel = "Somente Ficha"
        db.session.commit()
    _login(client, ids)

    body = client.get(f"/turma/{ids['turma']}").get_data(as_text=True)
    opcoes = _opcoes_ficha(body, ids["oferta_a"], ids["aluno"])
    assert opcoes[0] == ("Somente Ficha", "Somente Ficha (atual)")

    resposta = _post_nivel(client, ids, ids["oferta_a"], "Somente Ficha")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == ("Somente Ficha", "Somente Ficha")


# ---------------------------------------------------------------------------
# Defesa no POST
# ---------------------------------------------------------------------------


def test_post_com_nivel_novo_de_outro_curso_rejeita_sem_gravar(client, app):
    """AJ32-B: nível fora do catálogo/sanitizado não pode responder ok:true nem gravar."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Iniciante A")
        aluno = db.session.get(Aluno, ids["aluno"])
        aluno.nivel = "Iniciante A"
        db.session.commit()
    _login(client, ids)

    resposta = client.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta_a"],
            "nivel": "Módulo B",
        },
        follow_redirects=False,
    )
    # fallback form: redirect com flash warning, sem gravar
    assert resposta.status_code in (302, 303)
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == ("Iniciante A", "Iniciante A")


def test_post_com_nivel_valido_do_curso_grava(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"])
        db.session.commit()
    _login(client, ids)

    resposta = _post_nivel(client, ids, ids["oferta_a"], "Avançado A")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == ("Avançado A", "Avançado A")


def test_post_nao_se_aplica_limpa_nivel_atual(client, app):
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Legado Livre")
        aluno = db.session.get(Aluno, ids["aluno"])
        aluno.nivel = "Legado Livre"
        db.session.commit()
    _login(client, ids)

    resposta = _post_nivel(client, ids, ids["oferta_a"], "Não se aplica")
    assert resposta.status_code == 200
    assert _niveis_grabados(app, ids, ids["oferta_a"]) == (None, None)


# ---------------------------------------------------------------------------
# Sem N+1
# ---------------------------------------------------------------------------


def test_queries_constantes_com_2x7_alunos(client, app):
    ids = _seed(app)
    _login(client, ids)

    def carregar():
        return client.get(f"/turma/{ids['turma']}").get_data(as_text=True)

    def adicionar_alunos(primeiro, ultimo):
        with app.app_context():
            for indice in range(primeiro, ultimo):
                aluno = Aluno(
                    nome=f"Aluno N+1 {indice:02d}", unidade_id=ids["unidade"], ativo=True,
                )
                db.session.add(aluno)
                db.session.flush()
                nova_inscricao(aluno.id, ids["turma"], ids["oferta_a"], nivel="Iniciante A")
            db.session.commit()

    adicionar_alunos(0, 7)
    n7 = _contar_selects(db.engine, carregar)
    adicionar_alunos(7, 14)
    n14 = _contar_selects(db.engine, carregar)

    assert n14 <= n7 + 5

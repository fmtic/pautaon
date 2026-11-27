"""AJ22-E — Select de nível no modal de enturmação restrito ao curso da oferta.

Sem migration, sem alteração de schema:
- O modal de enturmação (turmas/detalhe.html) exibe no select `nivel_<aluno_id>`
  apenas os níveis pertencentes ao curso da oferta selecionada (`oferta_sel.curso_id`).
- Níveis de outros cursos e níveis sem curso (legados) são omitidos.
- Se o curso não tem níveis cadastrados, exibe apenas "Não se aplica".
- No POST de enturmação, sanitização defensiva garante que níveis de outros cursos
  não sejam gravados.
"""

from __future__ import annotations

import re
from datetime import date

from _helpers import login_as, nova_inscricao, nova_oferta
from app.database import db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    Nivel,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _seed(app):
    """Cria unidade, admin, período e turma base."""
    with app.app_context():
        un = Unidade(nome="Unidade E", ativo=True)
        db.session.add(un)
        db.session.flush()
        usuario = User(
            name="Admin E", email="aj22e@example.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        periodo = PeriodoLetivo(
            nome="Periodo E", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=un.id, ativo=True,
        )
        curso_a = Curso(nome="Curso A", unidade_id=un.id, ativo=True)
        curso_b = Curso(nome="Curso B", unidade_id=un.id, ativo=True)
        curso_vazio = Curso(nome="Curso Vazio", unidade_id=un.id, ativo=True)
        db.session.add_all([usuario, periodo, curso_a, curso_b, curso_vazio])
        db.session.flush()

        turma = Turma(
            nome="Turma E", turno="Manhã", data_inicio=DATA_INI,
            data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
            unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        oferta_a = nova_oferta(turma.id, curso_a.id, un.id, principal=True)
        oferta_b = nova_oferta(turma.id, curso_b.id, un.id, principal=False)
        oferta_vazia = nova_oferta(turma.id, curso_vazio.id, un.id, principal=False)

        # Níveis associados aos cursos
        nivel_a1 = Nivel(nome="Iniciante A", curso_id=curso_a.id, unidade_id=un.id, ativo=True)
        nivel_a2 = Nivel(nome="Avançado A", curso_id=curso_a.id, unidade_id=un.id, ativo=True)
        nivel_b1 = Nivel(nome="Módulo B", curso_id=curso_b.id, unidade_id=un.id, ativo=True)
        nivel_avulso = Nivel(nome="Sem Curso", curso_id=None, unidade_id=un.id, ativo=True)
        db.session.add_all([nivel_a1, nivel_a2, nivel_b1, nivel_avulso])
        db.session.flush()

        aluno = Aluno(nome="Aluno E", unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.commit()

        return {
            "user_id": usuario.id,
            "unidade": un.id,
            "turma": turma.id,
            "curso_a": curso_a.id,
            "curso_b": curso_b.id,
            "curso_vazio": curso_vazio.id,
            "oferta_a": oferta_a.id,
            "oferta_b": oferta_b.id,
            "oferta_vazia": oferta_vazia.id,
            "nivel_a1": nivel_a1.id,
            "nivel_a2": nivel_a2.id,
            "nivel_b1": nivel_b1.id,
            "aluno": aluno.id,
        }


def _login(client, ids):
    login_as(client, str(ids["user_id"]), ids["unidade"])


def _opcoes_nivel_modal(body, aluno_id):
    """Extrai os textos das opções do select `nivel_<aluno_id>` no modal."""
    padrao = rf'<select name="nivel_{aluno_id}"[^>]*>(.*?)</select>'
    match = re.search(padrao, body, re.S)
    assert match, f"select nivel_{aluno_id} não encontrado no HTML"
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', match.group(1))


def _opcoes_nivel_ficha(body, oferta_id, aluno_id):
    """Extrai as opções do select `nivel` na ficha do aluno da oferta."""
    padrao = rf'id="detalhes-oferta-{oferta_id}".*?/aluno/{aluno_id}/atualizar-nivel.*?<select name="nivel"[^>]*>(.*?)</select>'
    match = re.search(padrao, body, re.S)
    assert match, f"select nivel para aluno {aluno_id} na oferta {oferta_id} não encontrado"
    return re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)</option>', match.group(1))


# ---------------------------------------------------------------------------
# Testes de Renderização no Modal de Enturmação
# ---------------------------------------------------------------------------

def test_modal_enturmar_exibe_apenas_niveis_do_curso_selecionado(client, app):
    ids = _seed(app)
    _login(client, ids)

    # 1. Abre o modal selecionando a Oferta A (Curso A)
    r_a = client.get(f"/turma/{ids['turma']}?oferta_sel={ids['oferta_a']}&modal=enturmar")
    assert r_a.status_code == 200
    opcoes_a = _opcoes_nivel_modal(r_a.get_data(as_text=True), ids["aluno"])
    valores_a = [v for v, _ in opcoes_a]
    textos_a = [t.strip() for _, t in opcoes_a]

    # Deve conter "Não se aplica" e os níveis do Curso A em ordem A-Z
    assert valores_a == ["Não se aplica", "Avançado A", "Iniciante A"]
    assert textos_a == ["Não se aplica", "Avançado A", "Iniciante A"]
    # Não pode conter níveis do Curso B nem sem curso
    assert "Módulo B" not in valores_a
    assert "Sem Curso" not in valores_a

    # 2. Abre o modal selecionando a Oferta B (Curso B)
    r_b = client.get(f"/turma/{ids['turma']}?oferta_sel={ids['oferta_b']}&modal=enturmar")
    assert r_b.status_code == 200
    opcoes_b = _opcoes_nivel_modal(r_b.get_data(as_text=True), ids["aluno"])
    valores_b = [v for v, _ in opcoes_b]

    assert valores_b == ["Não se aplica", "Módulo B"]
    assert "Iniciante A" not in valores_b
    assert "Avançado A" not in valores_b
    assert "Sem Curso" not in valores_b


def test_modal_enturmar_curso_sem_niveis_exibe_apenas_nao_se_aplica(client, app):
    ids = _seed(app)
    _login(client, ids)

    # Abre com Oferta Vazia (Curso Vazio, sem níveis)
    r = client.get(f"/turma/{ids['turma']}?oferta_sel={ids['oferta_vazia']}&modal=enturmar")
    assert r.status_code == 200
    opcoes = _opcoes_nivel_modal(r.get_data(as_text=True), ids["aluno"])
    valores = [v for v, _ in opcoes]

    assert valores == ["Não se aplica"]


def test_modal_enturmar_turma_oferta_unica(client, app):
    """Em turma com apenas 1 oferta, oferta_sel é automática."""
    with app.app_context():
        un = Unidade(nome="Unidade Unica", ativo=True)
        db.session.add(un)
        db.session.flush()
        user = User(name="Admin U", email="u@example.com", role="admin", first_login=False, unidade_id=un.id)
        cur = Curso(nome="Curso Unico", unidade_id=un.id, ativo=True)
        db.session.add_all([user, cur])
        db.session.flush()
        t = Turma(nome="Turma Unica", data_inicio=DATA_INI, data_fim=DATA_FIM, unidade_id=un.id, ativo=True)
        db.session.add(t)
        db.session.flush()
        nova_oferta(t.id, cur.id, un.id, principal=True)
        nv1 = Nivel(nome="Nível 1", curso_id=cur.id, unidade_id=un.id, ativo=True)
        nv_outro = Nivel(nome="Nível Outro", curso_id=None, unidade_id=un.id, ativo=True)
        al = Aluno(nome="Aluno U", unidade_id=un.id, ativo=True)
        db.session.add_all([nv1, nv_outro, al])
        db.session.commit()
        uid, tid, aid = user.id, t.id, al.id
        un_id = un.id

    login_as(client, str(uid), un_id)
    r = client.get(f"/turma/{tid}")
    assert r.status_code == 200
    opcoes = _opcoes_nivel_modal(r.get_data(as_text=True), aid)
    valores = [v for v, _ in opcoes]

    assert valores == ["Não se aplica", "Nível 1"]
    assert "Nível Outro" not in valores


# ---------------------------------------------------------------------------
# Testes de Gravação e Sanitização no POST
# ---------------------------------------------------------------------------

def test_enturmar_post_com_nivel_valido_grava_com_sucesso(client, app):
    ids = _seed(app)
    _login(client, ids)

    r = client.post(
        f"/turma/enturmar/{ids['turma']}",
        data={
            "turma_curso_id": ids["oferta_a"],
            "aluno_ids[]": [str(ids["aluno"])],
            f"nivel_{ids['aluno']}": "Iniciante A",
            f"entrada_{ids['aluno']}": "inicio",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            turma_id=ids["turma"],
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert inscricao is not None
        assert inscricao.nivel == "Iniciante A"
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel == "Iniciante A"


def test_enturmar_post_com_nivel_de_outro_curso_sanitiza_para_none(client, app):
    """Se tentar enviar um nível de outro curso, não grava (sanitizado)."""
    ids = _seed(app)
    _login(client, ids)

    r = client.post(
        f"/turma/enturmar/{ids['turma']}",
        data={
            "turma_curso_id": ids["oferta_a"],
            "aluno_ids[]": [str(ids["aluno"])],
            f"nivel_{ids['aluno']}": "Módulo B",  # pertence ao Curso B, não A!
            f"entrada_{ids['aluno']}": "inicio",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            turma_id=ids["turma"],
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert inscricao is not None
        # Sanitizado: nível não foi gravado
        assert inscricao.nivel is None
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel is None


def test_enturmar_post_com_nao_se_aplica_grava_none(client, app):
    ids = _seed(app)
    _login(client, ids)

    r = client.post(
        f"/turma/enturmar/{ids['turma']}",
        data={
            "turma_curso_id": ids["oferta_a"],
            "aluno_ids[]": [str(ids["aluno"])],
            f"nivel_{ids['aluno']}": "Não se aplica",
            f"entrada_{ids['aluno']}": "inicio",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        inscricao = Inscricao.query.filter_by(
            turma_id=ids["turma"],
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert inscricao is not None
        assert inscricao.nivel is None


# ---------------------------------------------------------------------------
# Testes de Renderização na Ficha do Aluno Enturmado (Card da Oferta)
# ---------------------------------------------------------------------------

def test_ficha_aluno_exibe_apenas_niveis_do_curso_da_oferta(client, app):
    """Na listagem de alunos enturmados no card da oferta, o select inline
    exibe apenas os níveis do curso daquela oferta (em ordem alfabética)."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"])
        db.session.commit()
    _login(client, ids)

    r = client.get(f"/turma/{ids['turma']}")
    assert r.status_code == 200
    opcoes = _opcoes_nivel_ficha(r.get_data(as_text=True), ids["oferta_a"], ids["aluno"])
    valores = [v for v, _ in opcoes]
    textos = [t.strip() for _, t in opcoes]

    assert valores == ["Não se aplica", "Avançado A", "Iniciante A"]
    assert textos == ["Não se aplica", "Avançado A", "Iniciante A"]
    # Não pode conter níveis do Curso B nem sem curso
    assert "Módulo B" not in valores
    assert "Sem Curso" not in valores


def test_ficha_aluno_curso_sem_niveis_exibe_apenas_nao_se_aplica(client, app):
    """Se o curso da oferta não possui níveis cadastrados, exibe apenas 'Não se aplica'."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_vazia"])
        db.session.commit()
    _login(client, ids)

    r = client.get(f"/turma/{ids['turma']}")
    assert r.status_code == 200
    opcoes = _opcoes_nivel_ficha(r.get_data(as_text=True), ids["oferta_vazia"], ids["aluno"])
    valores = [v for v, _ in opcoes]

    assert valores == ["Não se aplica"]


# ---------------------------------------------------------------------------
# Testes de Atualização Inline (/aluno/<id>/atualizar-nivel)
# ---------------------------------------------------------------------------

def test_atualizar_nivel_post_com_nivel_valido_grava_sucesso(client, app):
    """POST em atualizar_nivel_aluno com nível válido do curso grava com sucesso."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"])
        db.session.commit()
    _login(client, ids)

    r = client.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta_a"],
            "nivel": "Iniciante A",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel == "Iniciante A"
        insc = Inscricao.query.filter_by(
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert insc is not None
        assert insc.nivel == "Iniciante A"


def test_atualizar_nivel_post_com_nivel_de_outro_curso_rejeita_sem_gravar(client, app):
    """AJ32-B: nível fora do catálogo do curso da oferta é rejeitado, sem gravar."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Iniciante A")
        aluno = db.session.get(Aluno, ids["aluno"])
        aluno.nivel = "Iniciante A"
        db.session.commit()
    _login(client, ids)

    r = client.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta_a"],
            "nivel": "Módulo B",  # Pertence ao Curso B, não ao Curso A
        },
        follow_redirects=True,
    )
    assert r.status_code == 200
    assert "inválido" in r.get_data(as_text=True).lower()

    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel == "Iniciante A"
        insc = Inscricao.query.filter_by(
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert insc is not None
        assert insc.nivel == "Iniciante A"


def test_atualizar_nivel_post_nao_se_aplica_limpa_nivel(client, app):
    """POST em atualizar_nivel_aluno com 'Não se aplica' limpa o nível."""
    ids = _seed(app)
    with app.app_context():
        nova_inscricao(ids["aluno"], ids["turma"], ids["oferta_a"], nivel="Iniciante A")
        aluno = db.session.get(Aluno, ids["aluno"])
        aluno.nivel = "Iniciante A"
        db.session.commit()
    _login(client, ids)

    r = client.post(
        f"/aluno/{ids['aluno']}/atualizar-nivel",
        data={
            "turma_id": ids["turma"],
            "turma_curso_id": ids["oferta_a"],
            "nivel": "Não se aplica",
        },
        follow_redirects=True,
    )
    assert r.status_code == 200

    with app.app_context():
        aluno = db.session.get(Aluno, ids["aluno"])
        assert aluno.nivel is None
        insc = Inscricao.query.filter_by(
            turma_curso_id=ids["oferta_a"],
            aluno_id=ids["aluno"],
            ativo=True,
        ).first()
        assert insc is not None
        assert insc.nivel is None

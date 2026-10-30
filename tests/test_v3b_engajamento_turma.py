# ruff: noqa: F811
"""V3b — "Engajamento da turma" no Painel Pedagógico do professor.

Cobrir o serviço `valores_mais_atribuidos` (ordenação, empate, percentual,
legado D2, valor inativo, escopo por oferta, SELECTs constantes) e o bloco no
HTML (posição, estado vazio, rodapé, escape, sem dado por aluno, troca com o
filtro, isolamento de professor/unidade).

Rota: `/professor/painel-pedagogico` (`main.painel_pedagogico_professor`).
"""

from datetime import date, time, timedelta

from sqlalchemy import event

from _helpers import login_as, nova_inscricao, nova_oferta

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
    ValorEsportista,
)
from app.models.enums import ConceitoFrequencia
from app.services.engajamento_turma import valores_mais_atribuidos
from config import Config

HOJE = date.today()
GRADE = dict(
    dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
    hora_inicio=time(8),
    hora_fim=time(10),
)


class SQLiteTestConfig(Config):
    SECRET_KEY = "chave-de-teste-s1-sem-valor-real-1234567890"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _usuario(nome, email, role, unidade_id):
    user = User(name=nome, email=email, role=role, first_login=False,
                unidade_id=unidade_id)
    user.set_password("SenhaLocal!123")
    return user


def _seed(app):
    """Prof (dono de O1 e O2) e prof2 (O3 na mesma turma; O4 em outra unidade)."""
    with app.app_context():
        un = Unidade(nome="Unidade V3b", ativo=True)
        un2 = Unidade(nome="Unidade V3b 2", ativo=True)
        db.session.add_all([un, un2])
        db.session.flush()

        prof = _usuario("Prof V3b", "prof.v3b@x.com", "professor", un.id)
        prof2 = _usuario("Prof V3b 2", "prof2.v3b@x.com", "professor", un.id)
        prof_outra = _usuario("Prof Outra", "profo.v3b@x.com", "professor", un2.id)
        db.session.add_all([prof, prof2, prof_outra])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="P V3b", data_inicio=HOJE - timedelta(days=60),
            data_fim=HOJE + timedelta(days=60), unidade_id=un.id, ativo=True,
        )
        periodo2 = PeriodoLetivo(
            nome="P V3b 2", data_inicio=HOJE - timedelta(days=60),
            data_fim=HOJE + timedelta(days=60), unidade_id=un2.id, ativo=True,
        )
        db.session.add_all([periodo, periodo2])
        db.session.flush()

        turma = Turma(
            nome="Turma V3b", unidade_id=un.id, periodo_letivo_id=periodo.id,
            professor_id=prof.id, ativo=True,
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
        )
        turma_outra = Turma(
            nome="Turma V3b outra", unidade_id=un2.id,
            periodo_letivo_id=periodo2.id, professor_id=prof_outra.id,
            ativo=True, data_inicio=periodo2.data_inicio,
            data_fim=periodo2.data_fim,
        )
        db.session.add_all([turma, turma_outra])
        db.session.flush()

        cursos = [
            Curso(nome=f"Curso V3b {i}", unidade_id=un.id, ativo=True)
            for i in range(3)
        ]
        curso_outra = Curso(nome="Curso V3b outra", unidade_id=un2.id, ativo=True)
        db.session.add_all([*cursos, curso_outra])
        db.session.flush()

        o1 = nova_oferta(turma.id, cursos[0].id, un.id, principal=True,
                         professor_id=prof.id, **GRADE)
        o2 = nova_oferta(turma.id, cursos[1].id, un.id, principal=False,
                         professor_id=prof.id, **GRADE)
        o3 = nova_oferta(turma.id, cursos[2].id, un.id, principal=False,
                         professor_id=prof2.id, **GRADE)
        o4 = nova_oferta(turma_outra.id, curso_outra.id, un2.id, principal=True,
                         professor_id=prof_outra.id, **GRADE)

        alunos = [
            Aluno(nome=nome, unidade_id=un.id, ativo=True)
            for nome in ("Ana Souza", "Bruno Dias", "Carla Reis")
        ]
        db.session.add_all(alunos)
        db.session.flush()
        for aluno in alunos:
            nova_inscricao(aluno.id, turma.id, o1.id)
            nova_inscricao(aluno.id, turma.id, o2.id)

        db.session.commit()
        return {
            "un": un.id,
            "un2": un2.id,
            "prof": prof.id,
            "prof2": prof2.id,
            "prof_outra": prof_outra.id,
            "turma": turma.id,
            "turma_outra": turma_outra.id,
            "o1": o1.id,
            "o2": o2.id,
            "o3": o3.id,
            "o4": o4.id,
            "a1": alunos[0].id,
            "a2": alunos[1].id,
            "a3": alunos[2].id,
            "alunos": [a.id for a in alunos],
            "_k": 0,
        }


def _valor(app, ids, nome, *, ativo=True):
    with app.app_context():
        valor = ValorEsportista(nome=nome, ativo=ativo, unidade_id=ids["un"])
        db.session.add(valor)
        db.session.commit()
        return valor.id


def _atribuir(app, ids, valor_id, quantidade, *, oferta_id=None, legado=False):
    """Cria `quantidade` linhas de Frequencia com o valor (aluno/data únicos)."""
    oferta = ids["o1"] if oferta_id is None else oferta_id
    with app.app_context():
        for _ in range(quantidade):
            k = ids["_k"]
            ids["_k"] += 1
            db.session.add(
                Frequencia(
                    aluno_id=ids["alunos"][k % len(ids["alunos"])],
                    turma_id=ids["turma"],
                    turma_curso_id=None if legado else oferta,
                    data=HOJE - timedelta(days=1 + k),
                    conceito=ConceitoFrequencia.A,
                    valor_esportista_id=valor_id,
                    unidade_id=ids["un"],
                )
            )
        db.session.commit()


def _top3(app, ids, oferta_id=None):
    with app.app_context():
        return valores_mais_atribuidos(ids["turma"], oferta_id or ids["o1"])


def _nomes(resultado):
    return [item["nome"] for item in resultado["itens"]]


# ---------------------------------------------------------------------------
# Serviço
# ---------------------------------------------------------------------------

def test_ordenacao_decrescente(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 3)
    _atribuir(app, ids, _valor(app, ids, "Respeito"), 2)
    _atribuir(app, ids, _valor(app, ids, "Disciplina"), 1)

    resultado = _top3(app, ids)

    assert _nomes(resultado) == ["Colaboração", "Respeito", "Disciplina"]
    assert [i["quantidade"] for i in resultado["itens"]] == [3, 2, 1]
    assert resultado["total"] == 6


def test_empate_desempata_pelo_nome(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Superação"), 2)
    _atribuir(app, ids, _valor(app, ids, "Respeito"), 2)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 1)

    assert _nomes(_top3(app, ids)) == ["Respeito", "Superação", "Colaboração"]


def test_menos_de_tres_valores(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2)
    _atribuir(app, ids, _valor(app, ids, "Respeito"), 1)

    resultado = _top3(app, ids)

    assert _nomes(resultado) == ["Colaboração", "Respeito"]
    assert resultado["total"] == 3


def test_sem_valores(app):
    ids = _seed(app)  # nenhuma Frequencia com valor

    resultado = _top3(app, ids)

    assert resultado == {"itens": [], "total": 0}


def test_percentual_e_sobre_o_total_da_oferta(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 4)
    _atribuir(app, ids, _valor(app, ids, "Respeito"), 3)
    _atribuir(app, ids, _valor(app, ids, "Disciplina"), 2)
    _atribuir(app, ids, _valor(app, ids, "Empatia"), 1)
    _atribuir(app, ids, _valor(app, ids, "Superação"), 1)

    resultado = _top3(app, ids)

    assert resultado["total"] == 11  # todos, não só o top 3 (9)
    assert [i["percentual"] for i in resultado["itens"]] == [36.4, 27.3, 18.2]


def test_oferta_a_nao_ve_dados_da_oferta_b(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2, oferta_id=ids["o1"])
    _atribuir(app, ids, _valor(app, ids, "Empatia"), 3, oferta_id=ids["o2"])

    assert _nomes(_top3(app, ids, ids["o1"])) == ["Colaboração"]
    assert _top3(app, ids, ids["o2"])["total"] == 3
    assert _nomes(_top3(app, ids, ids["o2"])) == ["Empatia"]


def test_legado_d2_entra_na_oferta_unica(app):
    ids = _seed(app)
    with app.app_context():
        # Só a O1 fica ativa na turma: as linhas legado (NULL) são dela.
        for oferta_id in (ids["o2"], ids["o3"]):
            db.session.get(TurmaCurso, oferta_id).ativo = False
        db.session.commit()

    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2, legado=True)

    resultado = _top3(app, ids, ids["o1"])

    assert resultado["total"] == 2
    assert _nomes(resultado) == ["Colaboração"]


def test_legado_d2_nao_entra_com_duas_ofertas(app):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 1, oferta_id=ids["o1"])
    _atribuir(app, ids, _valor(app, ids, "Empatia"), 3, legado=True)

    resultado = _top3(app, ids, ids["o1"])

    assert resultado["total"] == 1
    assert _nomes(resultado) == ["Colaboração"]


def test_valor_inativo_ja_usado_aparece(app):
    ids = _seed(app)
    valor_id = _valor(app, ids, "Fair Play", ativo=False)
    _atribuir(app, ids, valor_id, 2)

    resultado = _top3(app, ids)

    assert _nomes(resultado) == ["Fair Play"]
    assert resultado["total"] == 2


def test_selects_constantes_com_2_e_8_valores(app):
    ids = _seed(app)
    for nome in ("V1", "V2"):
        _atribuir(app, ids, _valor(app, ids, nome), 1)

    def _conta_selects():
        consultas = []

        def _conta(_conn, _cursor, statement, _params, _context, _many):
            consultas.append(statement)

        event.listen(db.engine, "before_cursor_execute", _conta)
        try:
            with app.app_context():
                valores_mais_atribuidos(ids["turma"], ids["o1"])
        finally:
            event.remove(db.engine, "before_cursor_execute", _conta)
        return len(consultas)

    with app.app_context():  # aquece caches de sessão
        valores_mais_atribuidos(ids["turma"], ids["o1"])
    com_2 = _conta_selects()

    for nome in ("V3", "V4", "V5", "V6", "V7", "V8"):
        _atribuir(app, ids, _valor(app, ids, nome), 1)
    com_8 = _conta_selects()

    assert com_2 == com_8


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------

def _html(app, client, ids, *, oferta_id=None):
    login_as(client, ids["prof"], ids["un"])
    url = f"/professor/painel-pedagogico?turma_id={ids['turma']}"
    if oferta_id is not None:
        url += f"&turma_curso={oferta_id}"
    resposta = client.get(url)
    assert resposta.status_code == 200
    return resposta.get_data(as_text=True)


def test_bloco_abaixo_do_grafico_e_blocos_preservados(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2)

    html = _html(app, client, ids)

    assert "Engajamento da turma" in html
    assert "Valores/Posturas do Esportista mais atribuídos" in html
    assert html.index("chartEvolucao") < html.index("Engajamento da turma")
    # Blocos existentes intactos.
    assert "Evolução de Assiduidade Aula a Aula" in html
    assert "Qualitativo da Frequência" in html
    assert "Rendimento e Assiduidade por Aluno" in html


def test_estado_vazio(app, client):
    ids = _seed(app)

    html = _html(app, client, ids)

    assert "Engajamento da turma" in html
    assert "Ainda não há valores registrados nesta oferta." in html


def test_rodape_com_total(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 3)
    _atribuir(app, ids, _valor(app, ids, "Respeito"), 2)

    html = _html(app, client, ids)

    assert "Baseado em 5 registros de presença com valor." in html
    assert "60.0%" in html


def test_nome_do_valor_e_escapado(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "<b>Liderança</b>"), 2)

    html = _html(app, client, ids)

    assert "&lt;b&gt;Liderança&lt;/b&gt;" in html
    assert "<b>Liderança</b>" not in html


def test_bloco_nao_mostra_nome_de_aluno(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2)

    html = _html(app, client, ids)
    bloco = html[
        html.index("Engajamento da turma"):
        html.index("Rendimento e Assiduidade por Aluno")
    ]

    for nome in ("Ana Souza", "Bruno Dias", "Carla Reis"):
        assert nome not in bloco


def test_bloco_muda_com_o_filtro(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2, oferta_id=ids["o1"])
    _atribuir(app, ids, _valor(app, ids, "Empatia"), 3, oferta_id=ids["o2"])

    html_o1 = _html(app, client, ids, oferta_id=ids["o1"])
    html_o2 = _html(app, client, ids, oferta_id=ids["o2"])

    assert "Colaboração" in html_o1 and "Empatia" not in html_o1
    assert "Empatia" in html_o2 and "Colaboração" not in html_o2
    assert "Baseado em 2 registros" in html_o1
    assert "Baseado em 3 registros" in html_o2


def test_nao_ve_oferta_de_outro_professor(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 1, oferta_id=ids["o1"])
    _atribuir(app, ids, _valor(app, ids, "Empatia"), 4, oferta_id=ids["o3"])

    html = _html(app, client, ids, oferta_id=ids["o3"])

    # A oferta do outro professor não entra: cai na primeira entrada dele.
    assert "Empatia" not in html
    assert "Colaboração" in html
    assert "Baseado em 1 registros de presença com valor." in html


def test_professor_de_outra_unidade_nao_ve_o_bloco(app, client):
    ids = _seed(app)
    _atribuir(app, ids, _valor(app, ids, "Colaboração"), 2, oferta_id=ids["o1"])

    login_as(client, ids["prof_outra"], ids["un2"])
    resposta = client.get(
        f"/professor/painel-pedagogico?turma_id={ids['turma']}"
        f"&turma_curso={ids['o1']}"
    )
    html = resposta.get_data(as_text=True)

    # O filtro aponta para a turma/unidade de outro professor: cai na entrada
    # dele (sem valores), nunca nos dados da unidade 1.
    assert resposta.status_code == 200
    assert "Colaboração" not in html
    assert "Ainda não há valores registrados nesta oferta." in html

# ruff: noqa: F811
"""F1 — autor do lançamento em `frequencia` e `conselho_resposta`.

Regras cobertas:
    - `POST /frequencia` grava `autor_id`/`autor_nome` de quem salvou (criação);
    - reedição por outro usuário autorizado troca o autor para o último que salvou;
    - regravar o MESMO conceito (ou só mexer no Valor do Esportista) NÃO troca;
    - mesmos casos em `conselho_resposta` via `salvar_conselho`;
    - linha anterior à F1 continua NULL e as telas seguem 200;
    - a FK declara ON DELETE SET NULL e a linha sobrevive à exclusão do usuário;
    - contexto sem usuário (serviço/seed) grava NULL;
    - o POST não faz SELECT por linha na tabela `user` (sem N+1).
"""

from datetime import time, timedelta

import pytest

from _helpers import (
    dia_de_aula_ate,
    hoje_ref,
    login_as,
    nova_inscricao,
    nova_oferta,
)
from sqlalchemy import event

from app import db
from app.models import (
    Aluno,
    ConselhoClasse,
    ConselhoResposta,
    Curso,
    Frequencia,
    PerguntaConselho,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from app.utils.autor import autor_do_lancamento
from app.utils.datetime_parse import parse_date
from app.utils.logica import carregar_contexto_turma, get_local_now

# AJ4-B: semente e relógio do app ancorados no mesmo dia de referência
# (``hoje_fixo`` congela ``get_local_now``/``gerar_datas``; a semente usa
# ``dia_de_aula_ate`` para nunca cair num dia sem aula — domingo).
pytestmark = pytest.mark.usefixtures("hoje_fixo")


def _cenario(app, *, n_alunos=1):
    """Unidade + admin + pedagogico + professor + turma com 1 oferta + alunos.

    A turma tem grade de segunda a sexta (8h–10h) e período vigente, então
    `carregar_contexto_turma` devolve datas de aula válidas para o POST.
    """
    hoje = dia_de_aula_ate(hoje_ref())
    with app.app_context():
        un = Unidade(nome="Unidade F1", ativo=True)
        db.session.add(un)
        db.session.flush()

        admin = User(
            name="Admin F1", email="admin.f1@x.com", role="admin",
            first_login=False, unidade_id=un.id,
        )
        pedagogico = User(
            name="Pedagogico F1", email="pedagogico.f1@x.com",
            role="pedagogico", first_login=False, unidade_id=un.id,
        )
        prof = User(
            name="Prof F1", email="prof.f1@x.com", role="professor",
            first_login=False, unidade_id=un.id,
        )
        admin.set_password("SenhaLocal!123")
        pedagogico.set_password("SenhaLocal!123")
        prof.set_password("SenhaLocal!123")
        db.session.add_all([admin, pedagogico, prof])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="Periodo F1",
            data_inicio=hoje.replace(day=1),
            data_fim=hoje + timedelta(days=60),
            unidade_id=un.id, ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome="Turma F1", turno="Manhã",
            data_inicio=periodo.data_inicio, data_fim=periodo.data_fim,
            periodo_letivo_id=periodo.id, unidade_id=un.id, ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        curso = Curso(nome="Curso F1", unidade_id=un.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = nova_oferta(
            turma.id, curso.id, un.id, programa="Programa F1",
            professor_id=prof.id, principal=True,
            dias_semana="Segunda, Terça, Quarta, Quinta, Sexta",
            hora_inicio=time(8),
            hora_fim=time(10),
        )

        alunos = []
        for i in range(n_alunos):
            aluno = Aluno(nome=f"Aluno F1 {i}", unidade_id=un.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            nova_inscricao(aluno.id, turma.id, oferta.id)
            alunos.append(aluno.id)

        db.session.commit()

        return {
            "un": un.id,
            "admin": admin.id,
            "pedagogico": pedagogico.id,
            "prof": prof.id,
            "turma": turma.id,
            "oferta": oferta.id,
            "alunos": alunos,
            "data": carregar_contexto_turma(turma.id)["datas"][0],
        }


def _post_pauta(client, ids, conceito="A", aluno_idx=0):
    return client.post(
        "/frequencia",
        data={
            "turma": str(ids["turma"]),
            "data": ids["data"],
            f"aluno_{ids['alunos'][aluno_idx]}": conceito,
        },
        follow_redirects=False,
    )


def _linha(app, ids, aluno_idx=0):
    with app.app_context():
        return Frequencia.query.filter_by(
            aluno_id=ids["alunos"][aluno_idx],
            turma_curso_id=ids["oferta"],
            data=ids["data"],
        ).first()


# ---------------------------------------------------------------------------
# frequencia — criação, troca e não-troca
# ---------------------------------------------------------------------------

def test_post_frequencia_grava_autor_do_professor(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof"], ids["un"])

    assert _post_pauta(client, ids, "A").status_code == 302

    linha = _linha(app, ids)
    assert linha is not None
    assert linha.autor_id == ids["prof"]
    assert linha.autor_nome == "Prof F1"


def test_reedicao_por_outro_usuario_troca_o_autor(app, client):
    ids = _cenario(app)
    login_as(client, ids["prof"], ids["un"])
    _post_pauta(client, ids, "A")
    assert _linha(app, ids).autor_id == ids["prof"]

    login_as(client, ids["admin"], ids["un"])
    assert _post_pauta(client, ids, "F").status_code == 302

    linha = _linha(app, ids)
    assert linha.conceito == "F"
    assert linha.autor_id == ids["admin"]
    assert linha.autor_nome == "Admin F1"


def test_regravacao_identica_nao_troca_o_autor(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    _post_pauta(client, ids, "A")

    # Mesmo conceito, outro usuário: o autor continua o primeiro que gravou.
    login_as(client, ids["pedagogico"], ids["un"])
    assert _post_pauta(client, ids, "A").status_code == 302

    linha = _linha(app, ids)
    assert linha.conceito == "A"
    assert linha.autor_id == ids["admin"]
    assert linha.autor_nome == "Admin F1"

    # Mudou o conceito: agora sim o autor passa a ser o último que salvou.
    login_as(client, ids["prof"], ids["un"])
    _post_pauta(client, ids, "B")
    linha = _linha(app, ids)
    assert linha.conceito == "B"
    assert linha.autor_id == ids["prof"]


# ---------------------------------------------------------------------------
# frequencia — histórico, esquema e contexto sem usuário
# ---------------------------------------------------------------------------

def test_linha_antiga_continua_null_e_tela_segue_200(app, client):
    ids = _cenario(app)
    with app.app_context():
        legado = Frequencia(
            aluno_id=ids["alunos"][0], turma_id=ids["turma"],
            turma_curso_id=ids["oferta"], data=parse_date(ids["data"]),
            conceito="A",
            unidade_id=ids["un"],
        )
        db.session.add(legado)
        db.session.commit()
        legado_id = legado.id

    login_as(client, ids["admin"], ids["un"])
    resposta = client.get(
        f"/frequencia?turma_id={ids['turma']}&data={ids['data']}"
    )
    assert resposta.status_code == 200

    with app.app_context():
        linha = db.session.get(Frequencia, legado_id)
        assert linha is not None
        assert linha.autor_id is None
        assert linha.autor_nome is None


def test_fk_autor_declara_on_delete_set_null(app):
    with app.app_context():
        for modelo in (Frequencia, ConselhoResposta):
            coluna = modelo.__table__.c.autor_id
            fk = next(iter(coluna.foreign_keys))
            assert fk.column.table.name == "user"
            assert fk.ondelete == "SET NULL"
            assert coluna.nullable is True


def test_excluir_usuario_nao_apaga_a_linha(app, client):
    ids = _cenario(app)
    login_as(client, ids["admin"], ids["un"])
    _post_pauta(client, ids, "A")

    with app.app_context():
        linha_id = _linha(app, ids).id
        db.session.delete(db.session.get(User, ids["admin"]))
        db.session.commit()

        linha = db.session.get(Frequencia, linha_id)
        assert linha is not None
        assert linha.aluno_id == ids["alunos"][0]
        # O snapshot do nome fica; o id é anulado pela FK (NULL) no PostgreSQL.
        assert linha.autor_nome == "Admin F1"


def test_contexto_sem_usuario_grava_null(app):
    with app.app_context():
        assert autor_do_lancamento() == (None, None)

        un = Unidade(nome="Unidade Seed F1", ativo=True)
        db.session.add(un)
        db.session.flush()
        turma = Turma(
            nome="Turma Seed F1", turno="Manhã",
            data_inicio=get_local_now().date(),
            data_fim=get_local_now().date(), unidade_id=un.id, ativo=True,
        )
        aluno = Aluno(nome="Aluno Seed F1", unidade_id=un.id, ativo=True)
        db.session.add_all([turma, aluno])
        db.session.flush()

        linha = Frequencia(
            aluno_id=aluno.id, turma_id=turma.id, data=get_local_now().date(),
            conceito="A", unidade_id=un.id,
        )
        db.session.add(linha)
        db.session.commit()
        assert linha.autor_id is None
        assert linha.autor_nome is None


def test_post_sem_select_por_linha_em_user(app, client):
    """O autor vem do `current_user` já carregado: 1 SELECT no máximo."""
    ids = _cenario(app, n_alunos=3)
    login_as(client, ids["prof"], ids["un"])

    engine = db.engine
    consultas = []

    def _before_cursor_execute(
        conn, cursor, statement, parameters, context, executemany
    ):
        texto = statement.lower()
        if texto.lstrip().startswith("select") and "from user" in texto:
            consultas.append(statement)

    event.listen(engine, "before_cursor_execute", _before_cursor_execute)
    try:
        resposta = client.post(
            "/frequencia",
            data={
                "turma": str(ids["turma"]),
                "data": ids["data"],
                **{
                    f"aluno_{aluno_id}": "A"
                    for aluno_id in ids["alunos"]
                },
            },
            follow_redirects=False,
        )
    finally:
        event.remove(engine, "before_cursor_execute", _before_cursor_execute)

    assert resposta.status_code == 302
    assert len(consultas) <= 1, (
        f"{len(consultas)} SELECT(s) em user para 3 alunos: o autor deveria "
        "vir do current_user, não de uma consulta por linha."
    )
    with app.app_context():
        gravadas = Frequencia.query.filter_by(turma_curso_id=ids["oferta"]).all()
        assert len(gravadas) == 3
        assert all(linha.autor_id == ids["prof"] for linha in gravadas)


# ---------------------------------------------------------------------------
# conselho_resposta — mesmos casos via salvar_conselho
# ---------------------------------------------------------------------------

def _pergunta(app):
    with app.app_context():
        pergunta = PerguntaConselho(
            etapa=EtapaConselho.INICIAL, tipo="ALUNO",
            texto="Como o aluno participa das aulas?", ativo=True,
        )
        db.session.add(pergunta)
        db.session.commit()
        return pergunta.id


def _post_conselho(client, ids, pergunta_id, texto_resposta):
    return client.post(
        "/conselho/salvar",
        data={
            "turma_id": str(ids["turma"]),
            "etapa": "INICIAL",
            "turma_curso_id": str(ids["oferta"]),
            f"resp_{ids['alunos'][0]}_{pergunta_id}": texto_resposta,
        },
        follow_redirects=False,
    )


def _resposta(app, ids, pergunta_id):
    with app.app_context():
        conselho = ConselhoClasse.query.filter_by(
            aluno_id=ids["alunos"][0], turma_curso_id=ids["oferta"],
        ).first()
        if conselho is None:
            return None
        return ConselhoResposta.query.filter_by(
            conselho_id=conselho.id,
            aluno_id=ids["alunos"][0],
            pergunta_id=pergunta_id,
        ).first()


def test_conselho_salvar_grava_autor(app, client):
    ids = _cenario(app)
    pergunta_id = _pergunta(app)
    login_as(client, ids["admin"], ids["un"])

    assert _post_conselho(client, ids, pergunta_id, "Participa bem").status_code == 302

    resposta = _resposta(app, ids, pergunta_id)
    assert resposta is not None
    assert resposta.resposta == "Participa bem"
    assert resposta.autor_id == ids["admin"]
    assert resposta.autor_nome == "Admin F1"


def test_conselho_reedicao_troca_autor(app, client):
    ids = _cenario(app)
    pergunta_id = _pergunta(app)
    login_as(client, ids["admin"], ids["un"])
    _post_conselho(client, ids, pergunta_id, "Participa bem")
    assert _resposta(app, ids, pergunta_id).autor_id == ids["admin"]

    login_as(client, ids["pedagogico"], ids["un"])
    assert _post_conselho(client, ids, pergunta_id, "Precisa de apoio").status_code == 302

    resposta = _resposta(app, ids, pergunta_id)
    assert resposta.resposta == "Precisa de apoio"
    assert resposta.autor_id == ids["pedagogico"]
    assert resposta.autor_nome == "Pedagogico F1"


def test_conselho_mesmo_texto_nao_troca_autor(app, client):
    ids = _cenario(app)
    pergunta_id = _pergunta(app)
    login_as(client, ids["admin"], ids["un"])
    _post_conselho(client, ids, pergunta_id, "Participa bem")

    login_as(client, ids["pedagogico"], ids["un"])
    assert _post_conselho(client, ids, pergunta_id, "Participa bem").status_code == 302

    resposta = _resposta(app, ids, pergunta_id)
    assert resposta.autor_id == ids["admin"]
    assert resposta.autor_nome == "Admin F1"


def test_tela_do_conselho_segue_200(app, client):
    ids = _cenario(app)
    _pergunta(app)
    login_as(client, ids["admin"], ids["un"])

    resposta = client.get(
        f"/conselho/lancamento?turma={ids['turma']}&etapa=INICIAL"
    )
    assert resposta.status_code == 200

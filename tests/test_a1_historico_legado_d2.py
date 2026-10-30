# ruff: noqa: F811
"""A1 (item 1) — regra D2 do legado no histórico do aluno.

Caracterização do achado M1: aluno com frequência LEGADA
(``turma_curso_id IS NULL``) em turma de oferta única aparecia com 0,0% no
histórico e com 75,0% na pauta/listagem. O histórico passa a aplicar a MESMA
regra D2 de `agregar_por_oferta` (`ofertas_unicas_ativas`): as linhas legadas
entram na inscrição da oferta SOMENTE quando ela é a única ativa da turma.

Observação de schema: desde a migration ``c3d4e5f6a7b8``
(``Inscricao.turma_curso_id`` NOT NULL) não existe inscrição sem oferta; o
caminho legado do serviço (par ``(turma_id, None)``) é coberto chamando
`frequencias_aluno_por_inscricao` diretamente.
"""

from datetime import date

import pytest
from _helpers import login_as, nova_inscricao, nova_oferta
from sqlalchemy import event

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    Turma,
    Unidade,
    User,
)
from app.services.frequencia_oferta import (
    agregar_por_oferta,
    frequencias_aluno_por_inscricao,
)

DATA_INI = date(2026, 2, 2)
DATA_FIM = date(2026, 6, 30)


def _cenario(app, *, ofertas=1, ativas=True, nome="Aluno A1"):
    """Unidade + período + turma com N ofertas + aluno inscrito na 1ª oferta.

    `ativas=False` cria a oferta como INATIVA (turma sem oferta ativa).
    A frequência legada (3 A + 1 F) é sempre gravada na turma.
    """
    with app.app_context():
        un = Unidade(nome="Unidade A1", ativo=True)
        user = User(
            name=f"Admin A1 {nome}",
            email=f"admin.a1.{nome.lower()}@example.com",
            role="admin",
            first_login=False,
            unidade_id=un.id,
        )
        db.session.add_all([un, user])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome=f"P A1 {nome}",
            data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(periodo)
        db.session.flush()

        turma = Turma(
            nome=f"Turma A1 {nome}",
            turno="Manhã",
            data_inicio=DATA_INI,
            data_fim=DATA_FIM,
            periodo_letivo_id=periodo.id,
            unidade_id=un.id,
            ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        ids_ofertas = []
        for i in range(ofertas):
            curso = Curso(nome=f"Curso A1 {i}", unidade_id=un.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            ids_ofertas.append(
                nova_oferta(
                    turma.id,
                    curso.id,
                    un.id,
                    principal=(i == 0),
                    ativo=ativas,
                ).id
            )

        aluno = Aluno(nome=nome, unidade_id=un.id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        nova_inscricao(aluno.id, turma.id, ids_ofertas[0])

        # Legado: 3 presenças + 1 falta SEM oferta (75,0%).
        for dia, conceito in (
            (date(2026, 3, 2), "A"),
            (date(2026, 3, 3), "A"),
            (date(2026, 3, 4), "A"),
            (date(2026, 3, 5), "F"),
        ):
            db.session.add(
                Frequencia(
                    aluno_id=aluno.id,
                    turma_id=turma.id,
                    turma_curso_id=None,
                    data=dia,
                    conceito=conceito,
                    unidade_id=un.id,
                )
            )
        db.session.commit()

        return {
            "unidade": un.id,
            "user": user.id,
            "aluno": aluno.id,
            "turma": turma.id,
            "ofertas": ids_ofertas,
        }


def test_pauta_ja_aplica_d2_e_historico_nao(app):
    """O achado: a mesma inscrição vale 75,0% na pauta e 0,0% no histórico."""
    ids = _cenario(app, ofertas=1)
    with app.app_context():
        pauta = agregar_por_oferta([ids["ofertas"][0]])[ids["ofertas"][0]]
        historico = frequencias_aluno_por_inscricao(
            ids["aluno"], [(ids["turma"], ids["ofertas"][0])]
        )[(ids["turma"], ids["ofertas"][0])]

    assert pauta.pct == pytest.approx(75.0)
    assert pauta.presentes == 3 and pauta.faltas == 1
    # Caracterização do defeito: o histórico lia só a oferta (nenhuma linha).
    assert historico["total"] == 4, historico
    assert historico["presenca_percentual"] == pytest.approx(75.0)


def test_rota_historico_mostra_o_mesmo_percentual_da_pauta(app, client):
    ids = _cenario(app, ofertas=1)
    login_as(client, ids["user"], ids["unidade"])

    resposta = client.get(f"/aluno/{ids['aluno']}/historico")
    assert resposta.status_code == 200
    corpo = resposta.get_data(as_text=True)

    assert "75.0%" in corpo
    assert "0.0%" not in corpo


def test_multi_oferta_legado_nao_entra_em_nenhuma(app):
    """Em turma com 2+ ofertas ativas o legado fica fora das duas (D2)."""
    ids = _cenario(app, ofertas=2)
    with app.app_context():
        o1, o2 = ids["ofertas"]
        # Uma presença própria da oferta 1 (sem legado), para diferenciar.
        db.session.add(
            Frequencia(
                aluno_id=ids["aluno"],
                turma_id=ids["turma"],
                turma_curso_id=o1,
                data=date(2026, 3, 9),
                conceito="A",
                unidade_id=ids["unidade"],
            )
        )
        db.session.commit()

        stats = frequencias_aluno_por_inscricao(
            ids["aluno"], [(ids["turma"], o1), (ids["turma"], o2)]
        )

    assert stats[(ids["turma"], o1)]["total"] == 1
    assert stats[(ids["turma"], o1)]["presenca_percentual"] == pytest.approx(100.0)
    assert stats[(ids["turma"], o2)]["total"] == 0


def test_oferta_unica_inativa_nao_recebe_legado(app):
    """Turma sem oferta ATIVA única: o legado não entra na oferta inativa."""
    ids = _cenario(app, ofertas=1, ativas=False)
    with app.app_context():
        stats = frequencias_aluno_por_inscricao(
            ids["aluno"], [(ids["turma"], ids["ofertas"][0])]
        )

    assert stats[(ids["turma"], ids["ofertas"][0])]["total"] == 0


def test_par_legado_le_somente_linhas_null(app):
    """Inscrição sem oferta (par `(turma, None)`) continua lendo só o NULL."""
    ids = _cenario(app, ofertas=1)
    with app.app_context():
        stats = frequencias_aluno_por_inscricao(ids["aluno"], [(ids["turma"], None)])

    assert stats[(ids["turma"], None)]["total"] == 4
    assert stats[(ids["turma"], None)]["presenca_percentual"] == pytest.approx(75.0)


def test_consultas_constantes_por_inscricao(app):
    """O custo não cresce com o número de inscrições (sem N+1)."""
    um = _cenario(app, ofertas=1, nome="Um")
    tres = _cenario(app, ofertas=1, nome="Tres")
    with app.app_context():
        # Completa o segundo aluno com duas inscrições extras em outras turmas.
        base = Turma.query.filter_by(nome="Turma A1 Tres").first()
        for i in range(2):
            extra = Turma(
                nome=f"Turma Extra {i}",
                turno="Tarde",
                data_inicio=DATA_INI,
                data_fim=DATA_FIM,
                periodo_letivo_id=base.periodo_letivo_id,
                unidade_id=tres["unidade"],
                ativo=True,
            )
            db.session.add(extra)
            db.session.flush()
            curso = Curso(nome=f"Curso Extra {i}", unidade_id=tres["unidade"])
            db.session.add(curso)
            db.session.flush()
            oferta = nova_oferta(extra.id, curso.id, tres["unidade"])
            nova_inscricao(tres["aluno"], extra.id, oferta.id)
        db.session.commit()

        def _selects(pares):
            contagem = {"n": 0}

            def _conta(conn, cursor, statement, params, context, executemany):
                contagem["n"] += 1

            event.listen(db.engine, "before_cursor_execute", _conta)
            try:
                frequencias_aluno_por_inscricao(tres["aluno"], pares)
            finally:
                event.remove(db.engine, "before_cursor_execute", _conta)
            return contagem["n"]

        pares_um = [(um["turma"], um["ofertas"][0])]
        pares_tres = [
            (turma_id, oferta_id)
            for turma_id, oferta_id in db.session.query(
                Inscricao.turma_id, Inscricao.turma_curso_id
            )
            .filter_by(aluno_id=tres["aluno"])
            .all()
        ]
        assert len(pares_tres) == 3

        assert _selects(pares_um) == _selects(pares_tres)

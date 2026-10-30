"""H3c: carga horária por ocorrência na grade da oferta."""

from datetime import date, time

from sqlalchemy import event

from app import create_app, db
from _helpers import login_as, professor_semente
from app.models import (
    Curso,
    DiaBloqueado,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import TipoDiaBloqueado
from app.registros.turmas import pos_filtrar_turmas
from app.services.turma_curso_horario import (
    cargas_horarias_ofertas_em_lote,
    cargas_horarias_turmas_em_lote,
    definir_grade,
)
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _novo_app():
    return create_app(SQLiteTestConfig)


def _oferta(turma, curso, principal, dias, inicio, fim):
    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        unidade_id=turma.unidade_id,
        ativo=True,
        principal=principal,
        programa="Teste",
        professor_id=professor_semente(turma.unidade_id).id,
        data_inicio=inicio,
        data_fim=fim,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, dias)
    return oferta


def _seed_variavel():
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U1", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="2026",
            data_inicio=date(2026, 3, 2),
            data_fim=date(2026, 3, 13),
            unidade_id=unidade.id,
            ativo=True,
        )
        curso_a = Curso(nome="A", unidade_id=unidade.id, ativo=True)
        curso_b = Curso(nome="B", unidade_id=unidade.id, ativo=True)
        db.session.add_all([periodo, curso_a, curso_b])
        db.session.flush()
        turma = Turma(
            nome="Multi",
            unidade_id=unidade.id,
            curso_id=curso_a.id,
            periodo_letivo_id=periodo.id,
            ativo=True,
            data_inicio=periodo.data_inicio,
            data_fim=periodo.data_fim,
        )
        db.session.add(turma)
        db.session.flush()
        principal = _oferta(
            turma,
            curso_a,
            True,
            [(0, time(9), time(10)), (2, time(9), time(11))],
            date(2026, 3, 2),
            date(2026, 3, 13),
        )
        secundaria = _oferta(
            turma,
            curso_b,
            False,
            [(0, time(10), time(11)), (2, time(10), time(11))],
            date(2026, 3, 4),
            date(2026, 3, 13),
        )
        bloqueado = DiaBloqueado(
            data=date(2026, 3, 4),
            tipo=TipoDiaBloqueado.FERIADO,
            periodo_letivo_id=periodo.id,
            unidade_id=unidade.id,
        )
        db.session.add(bloqueado)
        db.session.commit()
        return app, {
            "turma": turma.id,
            "principal": principal.id,
            "secundaria": secundaria.id,
            "periodo": periodo.id,
            "unidade": unidade.id,
        }


def test_total_oferta_soma_duracao_de_cada_weekday_e_respeita_vigencia_bloqueio():
    app, ids = _seed_variavel()
    with app.app_context():
        principal, secundaria = [
            db.session.get(TurmaCurso, ids[key]) for key in ("principal", "secundaria")
        ]
        cargas = cargas_horarias_ofertas_em_lote([principal, secundaria])
        # Principal: 2 segundas × 60 + 1 quarta × 120; 4/3 está bloqueada.
        assert cargas[principal.id].carga_horaria_total == 240
        # Secundária inicia em 4/3: quarta bloqueada; resta segunda + quarta.
        assert cargas[secundaria.id].carga_horaria_total == 120
        # Grade não uniforme não pode ser representada por uma aula única.
        assert cargas[principal.id].carga_horaria_aula is None
        assert cargas[principal.id].min_ch_aula == 60


def test_total_turma_une_intervalos_sobrepostos_e_soma_disjuntos():
    app, ids = _seed_variavel()
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        carga = cargas_horarias_turmas_em_lote([turma])[turma.id]
        # 3/2: 60; 3/9: intervalos adjacentes somam 120; 3/11:
        # intervalos sobrepostos contam a união [09:00,11:00] uma vez (120).
        assert carga.carga_horaria_total == 300
        assert carga.carga_horaria_aula is None
        assert carga.min_ch_aula == 60
        assert turma.dias_aula_efetivos() == 3
        assert pos_filtrar_turmas([turma], {"min_ch_aula": "1"}) == [turma]
        assert pos_filtrar_turmas([turma], {"min_ch_aula": "1.01"}) == []
        # Histórico: o total da turma (300 min) difere do total da principal
        # (240 min). O filtro min_ch_total usa o MESMO valor exibido na lista.
        assert pos_filtrar_turmas([turma], {"min_ch_total": "4.5"}) == [turma]
        assert pos_filtrar_turmas([turma], {"min_ch_total": "5"}) == [turma]
        assert pos_filtrar_turmas([turma], {"min_ch_total": "5.01"}) == []


def test_turma_com_uma_oferta_uniforme_iguala_total_da_oferta():
    app, ids = _seed_variavel()
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        principal = db.session.get(TurmaCurso, ids["principal"])
        secundaria = db.session.get(TurmaCurso, ids["secundaria"])
        principal.ativo = False
        secundaria.principal = True
        db.session.flush()
        cargas = cargas_horarias_turmas_em_lote([turma])[turma.id]
        oferta_carga = cargas_horarias_ofertas_em_lote([secundaria])[secundaria.id]
        assert cargas.carga_horaria_total == oferta_carga.carga_horaria_total


def _loga(app, user_id):
    client = app.test_client()
    login_as(client, str(user_id))
    return client


# Fontes da C.H.: grade da oferta e bloqueios do calendário. As duas são
# lidas em LOTE — o custo não pode crescer com o nº de ofertas.
_FONTES_CH = ("turma_curso_horario", "dia_bloqueado")


def _statements_ch(statements):
    return [s for s in statements if any(fonte in s for fonte in _FONTES_CH)]


def test_listagem_e_carga_horaria_turmas_nao_fazem_n_mais_um_por_oferta():
    app, ids = _seed_variavel()
    with app.app_context():
        user = User(
            name="Coord",
            email="coord@example.com",
            role="pedagogico",
            first_login=False,
            unidade_id=ids["unidade"],
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id
        engine = db.engine

    client = _loga(app, user_id)

    def count_for(url):
        statements = []

        def before_cursor_execute(_conn, _cursor, statement, _params, _context, _executemany):
            statements.append(statement)

        event.listen(engine, "before_cursor_execute", before_cursor_execute)
        try:
            response = client.get(url)
            assert response.status_code == 200
        finally:
            event.remove(engine, "before_cursor_execute", before_cursor_execute)
        return len(statements), len(_statements_ch(statements))

    url_lista = f"/turma?periodo_letivo_id={ids['periodo']}"
    url_ch = f"/turmas/carga-horaria?periodo_id={ids['periodo']}&status_periodo=concluido"
    lista_base, ch_lista_base = count_for(url_lista)
    ch_base, _ = count_for(url_ch)

    extras = 4
    with app.app_context():
        turma = db.session.get(Turma, ids["turma"])
        for index in range(extras):
            curso = Curso(nome=f"Extra {index}", unidade_id=ids["unidade"], ativo=True)
            db.session.add(curso)
            db.session.flush()
            _oferta(
                turma,
                curso,
                False,
                [(4, time(12), time(13))],
                date(2026, 3, 2),
                date(2026, 3, 13),
            )
        db.session.commit()

    lista_n, ch_lista_n = count_for(url_lista)
    ch_n, ch_n_ch = count_for(url_ch)

    # C.H.: consultas de grade/bloqueio constantes com 2 ou 6 ofertas.
    assert ch_lista_n == ch_lista_base
    # Página de C.H. por curso: nenhuma consulta nova por oferta.
    assert ch_n <= ch_base
    assert ch_n_ch <= ch_lista_base

    # Dívida PRÉ-EXISTENTE, fora do H3c: a sub-linha da listagem exibe a
    # frequência de CADA oferta (`freq_geral_oferta`, ~4 consultas por linha).
    # O crescimento do total fica restrito a isso — nada de C.H.
    assert lista_n - lista_base <= 4 * extras

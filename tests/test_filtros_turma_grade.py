"""H3d — filtros de dia/horário e agregação de dias da listagem pela GRADE.

Cobre:
    - filtro de dia e de horário em grade uniforme;
    - filtro de dia e de horário em grade NÃO uniforme (casa só no dia certo);
    - dia + horário exigindo os dois na MESMA linha da grade;
    - `min_ch_aula` da turma multi-oferta = menor duração entre TODAS as
      ofertas ativas;
    - agregação de dias da linha da listagem (união das ofertas ativas).

H5a: a agenda vem SÓ da grade. Turma sem oferta (T-SEM) e oferta ativa sem
grade (T-LEG) são estados sem agenda — não casam nenhum filtro de dia/horário
e não contribuem dias na linha (antes casavam pelas colunas escalares).
"""

from datetime import date, time

import pytest
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload

from app import create_app
from app.database import db
from app.models import (
    Curso,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.registros.turmas import (
    _resumo_ofertas,
    aplicar_filtros_turmas,
    pos_filtrar_turmas,
)
from app.services.turma_curso_horario import (
    cargas_horarias_turmas_em_lote,
    definir_grade,
    grades_por_oferta,
)
from config import Config
from _helpers import professor_semente

DATA_INI = date(2026, 3, 2)
DATA_FIM = date(2026, 12, 15)


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _oferta(turma, curso, principal, grade, **campos):
    """Oferta com grade (linhas ``(dia, ini, fim)``) gravada pelo serviço."""
    campos.setdefault("professor_id", professor_semente(turma.unidade_id).id)
    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        unidade_id=turma.unidade_id,
        ativo=True,
        principal=principal,
        programa="Teste",
        data_inicio=DATA_INI,
        data_fim=DATA_FIM,
        **campos,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, grade)
    return oferta


def _seed(app, variavel=False):
    """5 turmas: uniforme, multi-oferta, sem oferta, oferta sem grade (+var)."""
    with app.app_context():
        unidade = Unidade(nome="U1", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        periodo = PeriodoLetivo(
            nome="2026", data_inicio=DATA_INI, data_fim=DATA_FIM,
            unidade_id=unidade.id, ativo=True,
        )
        db.session.add(periodo)
        user = User(
            name="Coord", email="coord@example.com", role="pedagogico",
            first_login=False, unidade_id=unidade.id,
        )
        db.session.add(user)
        cursos = [
            Curso(nome=f"C{i}", unidade_id=unidade.id, ativo=True) for i in range(1, 6)
        ]
        db.session.add_all(cursos)
        db.session.flush()

        def nova_turma(nome):
            turma = Turma(
                nome=nome, unidade_id=unidade.id, curso_id=cursos[0].id,
                periodo_letivo_id=periodo.id, ativo=True,
                data_inicio=DATA_INI, data_fim=DATA_FIM,
            )
            db.session.add(turma)
            db.session.flush()
            return turma

        t_uni = nova_turma("T-UNI")
        o_uni = _oferta(
            t_uni, cursos[1], True,
            [(0, time(8), time(9, 30)), (2, time(8), time(9, 30))],
        )

        t_multi = nova_turma("T-MULTI")
        o_p = _oferta(
            t_multi, cursos[0], True,
            [(0, time(8), time(11)), (2, time(8), time(11))],
        )
        o_s = _oferta(t_multi, cursos[2], False, [(1, time(8), time(9))])

        t_sem = nova_turma("T-SEM")

        # Estado inválido desde o H5a: oferta ativa SEM grade (nenhuma agenda).
        t_leg = nova_turma("T-LEG")
        o_leg = TurmaCurso(
            turma_id=t_leg.id, curso_id=cursos[3].id, unidade_id=unidade.id,
            ativo=True, principal=True, programa="Teste",
            professor_id=professor_semente(unidade.id).id,
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add(o_leg)

        ids = {
            "unidade": unidade.id, "periodo": periodo.id, "user": user.id,
            "t_uni": t_uni.id, "t_multi": t_multi.id, "t_sem": t_sem.id,
            "t_leg": t_leg.id, "o_uni": o_uni.id, "o_p": o_p.id, "o_s": o_s.id,
        }
        if variavel:
            # Grade NÃO uniforme: nenhuma coluna escalar representa a oferta.
            t_var = nova_turma("T-VAR")
            o_var = _oferta(
                t_var, cursos[4], True,
                [(1, time(8), time(10)), (3, time(14), time(16))],
            )
            ids["t_var"] = t_var.id
            ids["o_var"] = o_var.id
        db.session.commit()
        return ids


def _filtrar(args):
    """Nomes das turmas devolvidas por `aplicar_filtros_turmas` + filtro em SQL."""
    stmt = aplicar_filtros_turmas(select(Turma), args)
    return {t.nome for t in db.session.execute(stmt).scalars().all()}


# --- Filtros pela GRADE (grades uniformes e não uniformes) --------------------
class TestCaracterizacaoFiltros:
    """Grades uniformes: dia/horário casam pela grade da oferta."""

    def test_dia_segunda(self, app):
        _seed(app)
        assert _filtrar({"dia": "Segunda"}) == {"T-UNI", "T-MULTI"}

    def test_dia_quinta_sem_grade_nao_casa(self, app):
        """H5a: T-LEG (oferta sem grade) e T-SEM (sem oferta) não têm agenda."""
        _seed(app)
        assert _filtrar({"dia": "Quinta"}) == set()

    def test_dia_terca(self, app):
        _seed(app)
        assert _filtrar({"dia": "Terça"}) == {"T-MULTI"}

    def test_dia_sabado_sem_oferta_nao_casa(self, app):
        """Antes do H5a T-SEM casava Sábado pelo CSV da turma; agora não tem agenda."""
        _seed(app)
        assert _filtrar({"dia": "Sábado"}) == set()

    def test_horario_inicio(self, app):
        _seed(app)
        assert _filtrar({"horario_inicio": "08:00"}) == {"T-UNI", "T-MULTI"}

    def test_horario_inicio_de_oferta_sem_grade_nao_casa(self, app):
        _seed(app)
        assert _filtrar({"horario_inicio": "10:00"}) == set()

    def test_horario_inicio_de_turma_sem_oferta_nao_casa(self, app):
        _seed(app)
        assert _filtrar({"horario_inicio": "19:00"}) == set()

    def test_dia_e_horario_na_mesma_oferta(self, app):
        _seed(app)
        assert _filtrar({"dia": "Quarta", "horario_inicio": "08:00"}) == {
            "T-UNI", "T-MULTI",
        }

    def test_dia_e_horario_sem_cruzamento(self, app):
        _seed(app)
        assert _filtrar({"dia": "Terça", "horario_inicio": "10:00"}) == set()

    def test_dia_invalido_mantem_comparador_antigo(self, app):
        _seed(app)
        assert _filtrar({"dia": "Xyz"}) == set()

    def test_texto_vazio_nao_filtra(self, app):
        _seed(app)
        assert len(_filtrar({"dia": "", "horario_inicio": ""})) == 4

    def test_agregacao_de_dias_da_linha(self, app):
        ids = _seed(app)
        for chave, esperado in (
            ("t_uni", (["Segunda", "Quarta"], ["Seg.", "Qua."])),
            ("t_multi", (["Segunda", "Terça", "Quarta"], ["Seg.", "Ter.", "Qua."])),
            # H5a: sem agenda (turma sem oferta / oferta sem grade) → sem dias.
            ("t_sem", ([], [])),
            ("t_leg", ([], [])),
        ):
            resumo = _resumo_ofertas(db.session.get(Turma, ids[chave]))
            assert (resumo["dias"], resumo["dias_abreviados"]) == esperado


# --- Comportamento novo (grade NÃO uniforme) ---------------------------------
class TestFiltrosPelaGradeNaoUniforme:
    """T-VAR: Terça 08:00–10:00 e Quinta 14:00–16:00."""

    def test_dia_casa_somente_os_dias_da_grade(self, app):
        _seed(app, variavel=True)
        assert _filtrar({"dia": "Terça"}) == {"T-MULTI", "T-VAR"}
        # T-LEG não casa mais (oferta sem grade desde o H5a).
        assert _filtrar({"dia": "Quinta"}) == {"T-VAR"}
        assert _filtrar({"dia": "Sexta"}) == set()

    def test_horario_casa_a_hora_de_inicio_de_qualquer_dia(self, app):
        _seed(app, variavel=True)
        assert "T-VAR" in _filtrar({"horario_inicio": "08:00"})
        assert "T-VAR" in _filtrar({"horario_inicio": "14:00"})
        # 10:00/16:00 são FIM de alguma linha, nunca início: não casam.
        assert "T-VAR" not in _filtrar({"horario_inicio": "10:00"})
        assert "T-VAR" not in _filtrar({"horario_inicio": "16:00"})

    def test_dia_e_horario_precisam_casar_na_mesma_linha(self, app):
        _seed(app, variavel=True)
        # Antes do H3d a projeção escalar (14:00) fazia Terça + 14:00 casar.
        assert "T-VAR" not in _filtrar({"dia": "Terça", "horario_inicio": "14:00"})
        assert "T-VAR" not in _filtrar({"dia": "Quinta", "horario_inicio": "08:00"})
        assert "T-VAR" in _filtrar({"dia": "Terça", "horario_inicio": "08:00"})
        assert "T-VAR" in _filtrar({"dia": "Quinta", "horario_inicio": "14:00"})

    def test_sem_grade_nao_casa_filtro_algum(self, app):
        """H5a: T-LEG (oferta ativa sem grade) e T-SEM (sem oferta) ficam fora
        de TODOS os filtros de agenda — o fallback escalar foi removido."""
        _seed(app, variavel=True)
        assert "T-LEG" not in _filtrar({"horario_inicio": "10:00"})
        assert "T-SEM" not in _filtrar({"horario_inicio": "19:00"})
        assert "T-SEM" not in _filtrar({"dia": "Sábado"})
        assert _filtrar({"dia": "Sábado"}) == set()

    def test_agregacao_de_dias_le_a_grade(self, app):
        ids = _seed(app, variavel=True)
        resumo = _resumo_ofertas(db.session.get(Turma, ids["t_var"]))
        assert resumo["dias"] == ["Terça", "Quinta"]
        assert resumo["dias_abreviados"] == ["Ter.", "Qui."]


class TestMinChAulaGlobal:
    """Decisão H3d: menor duração semanal entre TODAS as ofertas ativas."""

    def test_turma_multi_usa_o_menor_entre_todas_as_ofertas(self, app):
        ids = _seed(app)
        turma = db.session.get(Turma, ids["t_multi"])
        carga = cargas_horarias_turmas_em_lote([turma])[turma.id]
        # Principal = aulas de 3h; secundária = aula de 1h. Antes do H3d o
        # filtro usava só a principal (180).
        assert carga.carga_horaria_aula == 180
        assert carga.min_ch_aula == 60

    def test_filtro_min_ch_aula_usa_o_minimo_global(self, app):
        ids = _seed(app)
        turma = db.session.get(Turma, ids["t_multi"])
        assert pos_filtrar_turmas([turma], {"min_ch_aula": "1"}) == [turma]
        assert pos_filtrar_turmas([turma], {"min_ch_aula": "1.5"}) == []

    def test_turma_de_uma_oferta_nao_muda(self, app):
        ids = _seed(app)
        turma = db.session.get(Turma, ids["t_uni"])
        carga = cargas_horarias_turmas_em_lote([turma])[turma.id]
        assert carga.min_ch_aula == 90  # aula de 1h30


# --- Sem N+1 nos filtros/agregação -------------------------------------------
def _consultas_de_grade(args):
    """Nº de statements que tocam a grade/ofertas ao rodar filtros + agregação.

    Reproduz o eager loading da rota `turma()`: sem ele qualquer lazy load
    contaria como N+1 e o teste mediria outra coisa.
    """
    from sqlalchemy import event

    engine = db.engine
    vistas = []

    def _antes(conn, cursor, statement, parameters, context, executemany):
        if "turma_curso" in statement.lower():
            vistas.append(statement)

    stmt = aplicar_filtros_turmas(
        select(Turma).options(
            joinedload(Turma.professor),
            selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.curso),
            selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.professor),
            selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.horarios),
        ),
        args,
    )
    event.listen(engine, "before_cursor_execute", _antes)
    try:
        turmas = db.session.execute(stmt).unique().scalars().all()
        _resumo_ofertas_e_carga(turmas)
    finally:
        event.remove(engine, "before_cursor_execute", _antes)
    return len(vistas)


def _resumo_ofertas_e_carga(turmas):
    """O mesmo trabalho da rota: resumo por turma + C.H. em lote."""
    grades = grades_por_oferta([o for t in turmas for o in t.ofertas_curso if o.ativo])
    for turma in turmas:
        _resumo_ofertas(turma, grades)
    cargas_horarias_turmas_em_lote(turmas)


class TestSemN1:
    def test_numero_de_consultas_de_grade_nao_cresce_com_turmas(self, app):
        _seed(app, variavel=True)
        base = _consultas_de_grade({"dia": "Terça"})
        with app.app_context():
            unidade = db.session.execute(select(Unidade)).scalars().first()
            periodo = db.session.execute(select(PeriodoLetivo)).scalars().first()
            curso = db.session.execute(select(Curso)).scalars().first()
            for i in range(3):
                turma = Turma(
                    nome=f"T-X{i}", unidade_id=unidade.id, curso_id=curso.id,
                    periodo_letivo_id=periodo.id, ativo=True,
                    data_inicio=DATA_INI, data_fim=DATA_FIM,
                )
                db.session.add(turma)
                db.session.flush()
                _oferta(turma, curso, True, [(1, time(7), time(8))])
            db.session.commit()
        assert _consultas_de_grade({"dia": "Terça"}) == base

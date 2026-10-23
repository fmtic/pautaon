"""
Onda 4 — Fase 4 (Etapa K2): lista de turmas por oferta.

Cobre:
    - GET da lista com turma de 0, 1 e 2 ofertas (200; selo/sub-linha só com 2+);
    - agregação de professores/turnos/dias na linha de turma multi-oferta;
    - filtros por oferta (COALESCE oferta→turma) — inclusive "não casa quando o
      professor só existe na coluna congelada de uma turma com ofertas ativas";
    - min_ch_total avaliado sobre a oferta principal;
    - carga_horaria_aula / carga_horaria_total da oferta (agenda conhecida,
      com um dia bloqueado);
    - datas_esperadas_oferta inalterada após a extração de datas_aula_oferta.
"""

from datetime import date, time, timedelta

from app import create_app, db
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
from config import Config

DATA_INI = date(2026, 3, 2)    # segunda-feira
DATA_FIM = date(2026, 12, 15)  # terça-feira


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


def _novo_app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    return test_app


def _loga(app, user_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    return client


def _iter_datas(inicio: date, fim: date):
    dias = []
    atual = inicio
    while atual <= fim:
        dias.append(atual)
        atual += timedelta(days=1)
    return dias


def _esperado(inicio: date, fim: date, weekday_set: set[int], blocked=()):
    bloqueadas = {
        d if isinstance(d, str) else d.strftime("%Y-%m-%d") for d in blocked
    }
    return [
        d
        for d in _iter_datas(inicio, fim)
        if d.weekday() in weekday_set and d.strftime("%Y-%m-%d") not in bloqueadas
    ]


def _seed():
    """U1: resp + professores A/B/C, 2 cursos, um período letivo e 3 turmas.

    - T1: 0 ofertas (professor congelado = A).
    - T2: 1 oferta principal (professor da oferta = A; coluna congelada = C).
    - T3: 2 ofertas — principal A "Segunda,Quarta" 09:00-10:00, secundária B
      "Terça" 14:00-15:30 (coluna congelada da turma = C).
    DiaBloqueado: a primeira quarta-feira (DATA_INI+2) do período.
    """
    app = _novo_app()
    with app.app_context():
        db.create_all()

        u1 = Unidade(nome="U1", ativo=True)
        db.session.add(u1)
        db.session.flush()

        resp = User(name="Coord", email="coord@example.com", role="pedagogico",
                    first_login=False, unidade_id=u1.id)
        pA = User(name="Prof A", email="pa@example.com", role="professor",
                  first_login=False, unidade_id=u1.id)
        pB = User(name="Prof B", email="pb@example.com", role="professor",
                  first_login=False, unidade_id=u1.id)
        pC = User(name="Prof C", email="pc@example.com", role="professor",
                  first_login=False, unidade_id=u1.id)
        db.session.add_all([resp, pA, pB, pC])

        cA = Curso(nome="Curso A", unidade_id=u1.id, ativo=True)
        cB = Curso(nome="Curso B", unidade_id=u1.id, ativo=True)
        db.session.add_all([cA, cB])
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="2026", data_inicio=DATA_INI, data_fim=DATA_FIM, unidade_id=u1.id,
        )
        db.session.add(periodo)
        db.session.flush()

        comuns = dict(
            unidade_id=u1.id, ativo=True, turno="Manhã", dias_semana="Segunda",
            hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM, periodo_letivo_id=periodo.id,
        )
        t1 = Turma(nome="T1", professor_id=pA.id, **comuns)
        t2 = Turma(nome="T2", professor_id=pC.id, **comuns)
        t3 = Turma(nome="T3", professor_id=pC.id, **comuns)
        db.session.add_all([t1, t2, t3])
        db.session.flush()

        o2 = TurmaCurso(
            turma_id=t2.id, curso_id=cA.id, unidade_id=u1.id, ativo=True,
            principal=True, professor_id=pA.id, turno="Manhã",
            dias_semana="Segunda", hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        o3p = TurmaCurso(
            turma_id=t3.id, curso_id=cA.id, unidade_id=u1.id, ativo=True,
            principal=True, professor_id=pA.id, turno="Manhã",
            dias_semana="Segunda,Quarta", hora_inicio=time(9, 0), hora_fim=time(10, 0),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        o3b = TurmaCurso(
            turma_id=t3.id, curso_id=cB.id, unidade_id=u1.id, ativo=True,
            principal=False, professor_id=pB.id, turno="Tarde",
            dias_semana="Terça", hora_inicio=time(14, 0), hora_fim=time(15, 30),
            data_inicio=DATA_INI, data_fim=DATA_FIM,
        )
        db.session.add_all([o2, o3p, o3b])

        bloqueado = DATA_INI + timedelta(days=2)  # primeira quarta-feira
        db.session.add(DiaBloqueado(
            data=bloqueado, tipo=TipoDiaBloqueado.FERIADO,
            periodo_letivo_id=periodo.id, unidade_id=u1.id,
        ))

        db.session.commit()

        ids = {
            "resp": resp.id, "u1": u1.id, "periodo": periodo.id,
            "t1": t1.id, "t2": t2.id, "t3": t3.id,
            "o2": o2.id, "o3p": o3p.id, "o3b": o3b.id,
            "bloqueado": bloqueado,
        }
    return app, ids


def _lista(app, user_id, query=""):
    client = _loga(app, user_id)
    return client.get(f"/turma{query}")


def _corpo(r):
    return r.get_data(as_text=True)


# --- GET com 0, 1 e 2 ofertas -------------------------------------------------
def test_lista_retorna_200_e_mostra_selo_e_sublinha_so_para_2_ofertas():
    app, ids = _seed()
    r = _lista(app, ids["resp"])
    assert r.status_code == 200
    body = _corpo(r)
    assert "T1" in body and "T2" in body and "T3" in body
    # Selos e sub-linha só da turma de 2+ ofertas.
    assert "2 cursos" in body
    assert 'id="ofertas-%d"' % ids["t3"] in body
    # A de 1 oferta não gera sub-linha.
    assert 'id="ofertas-%d"' % ids["t2"] not in body
    assert 'id="ofertas-%d"' % ids["t1"] not in body


# --- Agregação de professores/turnos/dias na linha multi-oferta ---------------
def test_linha_multi_mostra_dois_professores_e_uniao_de_dias():
    app, ids = _seed()
    body = _corpo(_lista(app, ids["resp"]))
    # Dentro da linha ( célula do nome ) os dois professores das ofertas.
    assert "Prof A" in body and "Prof B" in body
    # Dias: união Segunda/Terça/Quarta aparece (Sábado etc. não entra).
    for dia in ("Segunda", "Terça", "Quarta"):
        assert dia in body


# --- Filtro por coluna de uma oferta que não é a principal --------------------
def test_filtro_professor_segunda_oferta_encontra_turma():
    app, ids = _seed()
    body = _corpo(_lista(app, ids["resp"], "?professor=Prof%20B"))
    assert "T3" in body
    assert "T1" not in body and "T2" not in body


def test_filtro_turno_e_dia_da_segunda_oferta_encontram_turma():
    app, ids = _seed()
    # turno "Tarde" só existe na oferta secundária de T3.
    corpo_turno = _corpo(_lista(app, ids["resp"], "?turno=Tarde"))
    assert "T3" in corpo_turno and "T1" not in corpo_turno
    # dia "Terça" só existe na oferta secundária de T3.
    corpo_dia = _corpo(_lista(app, ids["resp"], "?dia=Ter%C3%A7a"))
    assert "T3" in corpo_dia and "T1" not in corpo_dia


# --- Coluna congelada da turma NÃO casa quando há ofertas ativas --------------
def test_professor_so_na_coluna_congelada_nao_encontra_turma_multi():
    app, ids = _seed()
    # "Prof C" é apenas a coluna congelada de T2/T3; nenhuma oferta ativa o usa.
    body = _corpo(_lista(app, ids["resp"], "?professor=Prof%20C"))
    assert "T2" not in body
    assert "T3" not in body


def test_professor_da_oferta_encontra_turma_de_uma_oferta():
    app, ids = _seed()
    body = _corpo(_lista(app, ids["resp"], "?professor=Prof%20A"))
    assert "T2" in body and "T3" in body


# --- min_ch_total sobre a oferta principal ------------------------------------
def test_min_ch_total_usa_oferta_principal():
    app, ids = _seed()
    with app.app_context():
        o3p = db.session.get(TurmaCurso, ids["o3p"])
        o3b = db.session.get(TurmaCurso, ids["o3b"])
        p_total_min = o3p.carga_horaria_total
        b_total_min = o3b.carga_horaria_total
        assert p_total_min is not None and b_total_min is not None
        assert p_total_min > b_total_min

    # Limiar entre as duas: se usasse a secundária, T3 sumiria; usando a
    # principal, T3 permanece.
    thr = b_total_min // 60 + 1
    body = _corpo(_lista(app, ids["resp"], f"?min_ch_total={thr}"))
    assert "T3" in body

    # Acima da principal, T3 sai.
    thr_hi = p_total_min // 60 + 1
    body_hi = _corpo(_lista(app, ids["resp"], f"?min_ch_total={thr_hi}"))
    assert "T3" not in body_hi


# --- C.H. da oferta conferem com cálculo manual (com dia bloqueado) -----------
def test_carga_horaria_oferta_calculo_manual_com_bloqueio():
    app, ids = _seed()
    # Segunda(0)/Quarta(2), até data_fim, menos a quarta bloqueada.
    esperado = _esperado(
        DATA_INI, DATA_FIM, {0, 2}, blocked=[ids["bloqueado"]]
    )
    assert DATA_INI.weekday() == 0
    assert ids["bloqueado"] not in esperado
    assert len(esperado) >= 2

    # terça(1), sem bloqueio.
    esperado_b = _esperado(DATA_INI, DATA_FIM, {1})

    with app.app_context():
        o3p = db.session.get(TurmaCurso, ids["o3p"])
        o3b = db.session.get(TurmaCurso, ids["o3b"])
        assert o3p.carga_horaria_aula == 60          # 09:00-10:00
        assert o3p.carga_horaria_total == 60 * len(esperado)
        assert o3b.carga_horaria_aula == 90          # 14:00-15:30
        assert o3b.carga_horaria_total == 90 * len(esperado_b)


# --- datas_esperadas_oferta inalterada (corta em hoje) ------------------------
def test_datas_esperadas_oferta_continua_cortando_em_hoje():
    app, ids = _seed()
    from app.services.turma_curso import datas_aula_oferta, datas_esperadas_oferta

    hoje = DATA_INI + timedelta(days=13)  # duas semanas de Segunda/Quarta
    esperado_ate_hoje = _esperado(DATA_INI, hoje, {0, 2})

    with app.app_context():
        o3p = db.session.get(TurmaCurso, ids["o3p"])
        ate_hoje = datas_esperadas_oferta(o3p, hoje)
        assert ate_hoje == esperado_ate_hoje
        # Sem limite vai até data_fim → mais datas do que "até hoje".
        todas = datas_aula_oferta(o3p)
        assert len(todas) > len(ate_hoje)

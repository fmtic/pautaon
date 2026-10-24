"""
Testes da Onda 4 — Fase 4 (D2 + D3a).

D2 (pauta da oferta e contagem de inscrições NULL):
    - Aluno com DUAS inscrições ativas na turma (uma NULL e outra da oferta
      única ativa) aparece UMA única vez na pauta (EXISTS, não JOIN).
    - Modo estrito (2+ ofertas, sem fallback NULL) também não duplica.
    - Contagem do aviso "N aluno(s) sem curso definido na turma" conta
      aluno_id distinto.

D3a (leitores de pauta impressa / frequência lançada):
    - Pauta impressa com oferta única continua igual (sem exigir turma_curso).
    - Com 2+ ofertas, sem turma_curso, redireciona pedindo a escolha.
    - Com 2+ ofertas e turma_curso, só alunos/frequências daquela oferta.
    - turma_curso pertencente a outra turma é recusado.
    - frequencias_lancadas por oferta não enxerga lançamento de outra oferta.
"""

from datetime import date

import pytest

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia
from app.registros.core import _alunos_da_oferta, _contagem_inscricoes_sem_curso
from app.utils.frequencia import frequencias_lancadas
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
        WTF_CSRF_ENABLED=False,
    )
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def base(app):
    """Turma com oferta única ativa e aluno com 2 inscrições ativas (NULL + oferta)."""
    unidade = Unidade(nome="Unidade F4 D2", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    curso = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
    turma = Turma(
        nome="Turma F4 D2", unidade_id=unidade.id, ativo=True, curso_id=None,
    )
    db.session.add_all([curso, turma])
    db.session.flush()

    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        unidade_id=unidade.id,
        ativo=True,
        principal=True,
    )
    db.session.add(oferta)

    aluno = Aluno(nome="Aluno Dupla Inscrição", unidade_id=unidade.id, ativo=True)
    db.session.add(aluno)
    db.session.flush()

    db.session.add_all([
        # Inscrição legada sem curso (turma_curso_id NULL)
        Inscricao(aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=None, ativo=True),
        # Inscrição vinculada à oferta única ativa
        Inscricao(aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id, ativo=True),
    ])
    db.session.commit()

    return {"unidade": unidade, "curso": curso, "turma": turma,
            "oferta": oferta, "aluno": aluno}


def test_aluno_com_duas_inscricoes_aparece_uma_vez_na_pauta(base):
    """Fallback NULL ativo (oferta única): EXISTS não duplica o aluno."""
    pauta = _alunos_da_oferta(
        base["turma"].id, base["oferta"].id, incluir_inscricoes_null=True,
    )
    assert [a.id for a in pauta] == [base["aluno"].id]


def test_aluno_com_duas_inscricoes_aparece_uma_vez_no_modo_estrito(base):
    """Sem fallback (regra 2+ ofertas): só a inscrição da oferta, 1 linha."""
    pauta = _alunos_da_oferta(
        base["turma"].id, base["oferta"].id, incluir_inscricoes_null=False,
    )
    assert [a.id for a in pauta] == [base["aluno"].id]


def test_contagem_sem_curso_conta_aluno_uma_vez(base):
    """Aluno com 1 inscrição NULL entre as 2 ativas → aviso conta 1."""
    assert _contagem_inscricoes_sem_curso(base["turma"].id) == 1


# =============================================================================
# D3a — leitores de pauta impressa e frequência lançada
# =============================================================================

DATA_AULA = date(2026, 3, 2)  # segunda-feira


def _novo_app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    return test_app


def _sem_cenario(pares, cria_outra_turma=False):
    """Monta app + turma com 1 oferta por par (curso, aluno), cada aluno com
    inscrição e frequência lançadas na mesma DATA_AULA. Retorna (app, info).
    """
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="Unidade D3a", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        resp = User(
            name="Coordenador", email="coord.d3a@example.com",
            role="pedagogico", first_login=False, unidade_id=unidade.id,
        )
        db.session.add(resp)

        turma = Turma(
            nome="Turma D3a", unidade_id=unidade.id, ativo=True, curso_id=None,
            data_inicio=DATA_AULA, data_fim=DATA_AULA, dias_semana="Segunda",
        )
        db.session.add(turma)
        db.session.flush()

        oferta_ids, aluno_ids = [], []
        for nome_curso, nome_aluno in pares:
            curso = Curso(nome=nome_curso, unidade_id=unidade.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            oferta = TurmaCurso(
                turma_id=turma.id, curso_id=curso.id,
                unidade_id=unidade.id, ativo=True,
            )
            db.session.add(oferta)
            aluno = Aluno(nome=nome_aluno, unidade_id=unidade.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            db.session.add_all([
                Inscricao(
                    aluno_id=aluno.id, turma_id=turma.id,
                    turma_curso_id=oferta.id, ativo=True,
                ),
                Frequencia(
                    aluno_id=aluno.id, turma_id=turma.id,
                    turma_curso_id=oferta.id, data=DATA_AULA,
                    conceito=ConceitoFrequencia.A, unidade_id=unidade.id,
                ),
            ])
            oferta_ids.append(oferta.id)
            aluno_ids.append(aluno.id)

        info = {
            "resp_id": resp.id,
            "turma_id": turma.id,
            "oferta_ids": oferta_ids,
            "aluno_ids": aluno_ids,
        }

        if cria_outra_turma:
            outra = Turma(
                nome="Outra Turma", unidade_id=unidade.id, ativo=True, curso_id=None,
            )
            db.session.add(outra)
            db.session.flush()
            oc = Curso(nome="Xadrez", unidade_id=unidade.id, ativo=True)
            db.session.add(oc)
            db.session.flush()
            oo = TurmaCurso(
                turma_id=outra.id, curso_id=oc.id,
                unidade_id=unidade.id, ativo=True,
            )
            db.session.add(oo)
            info["outra_oferta_id"] = oo.id

        db.session.commit()
    return app, info


def _loga(app, resp_id):
    client = app.test_client()
    with client.session_transaction() as session:
        session["_user_id"] = str(resp_id)
        session["_fresh"] = True
    return client


def test_pauta_impressa_oferta_unica_igual_hoje():
    """1 oferta ativa: imprime sem exigir turma_curso (200, sem redirect)."""
    app, info = _sem_cenario([("Natação", "Aluno Natação Zeta")])
    client = _loga(app, info["resp_id"])
    r = client.get(f"/turma/{info['turma_id']}/imprimir-pauta")
    assert r.status_code == 200
    assert "Aluno Natação Zeta" in r.get_data(as_text=True)


def test_pauta_impressa_duas_ofertas_sem_turma_curso_redireciona():
    """2+ ofertas sem turma_curso: redireciona para a tela de frequência."""
    app, info = _sem_cenario([
        ("Natação", "Aluno Natação Zeta"),
        ("Judô", "Aluno Judô Ypsilon"),
    ])
    client = _loga(app, info["resp_id"])
    r = client.get(f"/turma/{info['turma_id']}/imprimir-pauta")
    assert r.status_code == 302
    assert "/frequencia" in r.headers["Location"]


def test_pauta_impressa_duas_ofertas_filtrada_por_oferta():
    """2+ ofertas com turma_curso: só alunos/frequências daquela oferta."""
    app, info = _sem_cenario([
        ("Natação", "Aluno Natação Zeta"),
        ("Judô", "Aluno Judô Ypsilon"),
    ])
    client = _loga(app, info["resp_id"])
    r = client.get(
        f"/turma/{info['turma_id']}/imprimir-pauta"
        f"?turma_curso={info['oferta_ids'][0]}"
    )
    body = r.get_data(as_text=True)
    assert r.status_code == 200
    assert "Aluno Natação Zeta" in body
    assert "Aluno Judô Ypsilon" not in body
    assert "Natação" in body  # curso no cabeçalho da impressão


def test_pauta_impressa_recusa_oferta_de_outra_turma():
    """turma_curso de outra turma não pertence às ofertas: recusa e retorna."""
    app, info = _sem_cenario(
        [("Natação", "Aluno Natação Zeta"), ("Judô", "Aluno Judô Ypsilon")],
        cria_outra_turma=True,
    )
    client = _loga(app, info["resp_id"])
    r = client.get(
        f"/turma/{info['turma_id']}/imprimir-pauta"
        f"?turma_curso={info['outra_oferta_id']}"
    )
    assert r.status_code == 302
    assert "/frequencia" in r.headers["Location"]


def test_frequencias_lancadas_por_oferta_nao_ve_outra_oferta():
    """Contagem por oferta ignora lançamentos de outra oferta no mesmo dia."""
    app, info = _sem_cenario([
        ("Natação", "Aluno Natação Zeta"),
        ("Judô", "Aluno Judô Ypsilon"),
    ])
    with app.app_context():
        aluno_ids = info["aluno_ids"]
        oferta_a = info["oferta_ids"][0]
        # Por oferta A: só o lançamento da oferta A (1), não vê o da B.
        assert frequencias_lancadas(
            info["turma_id"], DATA_AULA, aluno_ids, turma_curso_id=oferta_a,
        ) == 1
        # Sem oferta (legado por turma): conta os dois lançamentos.
        assert frequencias_lancadas(
            info["turma_id"], DATA_AULA, aluno_ids,
        ) == 2


# =============================================================================
# D3b-1 — regra "turma em andamento" no adicionar_oferta
# =============================================================================

def test_adicionar_oferta_turma_encerrada_mantem_heranca_e_nao_recebe_hoje(app):
    """Turma já encerrada (data_fim < hoje): nova oferta sem data_inicio NÃO
    recebe 'hoje'; mantém a herança da turma e não falha (D3b-1)."""
    from app.services.turma_curso import adicionar_oferta

    inicio_passado = date(2020, 1, 1)
    fim_passado = date(2020, 6, 1)  # encerrada: data_fim bem antes de hoje

    unidade = Unidade(nome="Unidade Encerrada F4", ativo=True)
    db.session.add(unidade)
    db.session.flush()

    curso_a = Curso(nome="Natação Enc", unidade_id=unidade.id, ativo=True)
    curso_b = Curso(nome="Judô Enc", unidade_id=unidade.id, ativo=True)
    turma = Turma(
        nome="Turma Encerrada F4", unidade_id=unidade.id, ativo=True,
        curso_id=None, data_inicio=inicio_passado, data_fim=fim_passado,
    )
    db.session.add_all([curso_a, curso_b, turma])
    db.session.flush()

    # Oferta A já existente (principal), sem dias/hora para não conflitar.
    db.session.add(TurmaCurso(
        turma_id=turma.id, curso_id=curso_a.id, unidade_id=unidade.id,
        ativo=True, principal=True,
    ))
    db.session.commit()

    # Adiciona a 2ª oferta (B) sem data_inicio: turma encerrada → não usa hoje.
    oferta = adicionar_oferta(turma, curso_id=curso_b.id, principal=False)

    assert getattr(oferta, "inicio_ajustado_para_hoje", False) is False
    # Mantém a herança da turma (data_inicio da turma), não 'hoje'.
    assert oferta.data_inicio == inicio_passado


# =============================================================================
# ETAPA E — cobertura dos cenários a) a h) (i já coberto acima)
# =============================================================================

from datetime import timedelta

_DIAS_SEMANA = (
    "Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo",
)
DATA_ROTA = date(2026, 3, 2)  # data fixa no passado (<= hoje) para o POST
DIA_ROTA = _DIAS_SEMANA[DATA_ROTA.weekday()]


def _data_weekday(alvo: int, base: date = DATA_ROTA) -> date:
    """Primeira data >= `base` cujo weekday é `alvo` (0=Segunda)."""
    return base + timedelta(days=(alvo - base.weekday()) % 7)


def _seed_servico(*, ofertas):
    """Cria unidade + turma (sem curso legado) + uma oferta por cfg.
    cfg: dict(curso, dias, ini, fim, alunos=[nome]). Ofertas[0] é principal.
    Retorna dict com 'unidade', 'turma', 'ofertas' (instâncias), 'cursos',
    'alunos' (nome->id).
    """
    unidade = Unidade(nome="U svc", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    turma = Turma(nome="T svc", unidade_id=unidade.id, ativo=True, curso_id=None)
    db.session.add(turma)
    db.session.flush()

    ofertas_out, cursos, alunos = [], {}, {}
    for i, cfg in enumerate(ofertas):
        curso = Curso(nome=cfg["curso"], unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        oferta = TurmaCurso(
            turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
            ativo=True, principal=(i == 0), dias_semana=cfg.get("dias"),
            data_inicio=cfg.get("ini"), data_fim=cfg.get("fim"),
        )
        db.session.add(oferta)
        db.session.flush()
        ofertas_out.append(oferta)
        cursos[cfg["curso"]] = curso.id
        for nome in cfg.get("alunos", []):
            aluno = Aluno(nome=nome, unidade_id=unidade.id, ativo=True)
            db.session.add(aluno)
            db.session.flush()
            db.session.add(Inscricao(
                aluno_id=aluno.id, turma_id=turma.id,
                turma_curso_id=oferta.id, ativo=True,
            ))
            alunos[nome] = aluno.id
    db.session.commit()
    return {
        "unidade": unidade, "turma": turma, "ofertas": ofertas_out,
        "cursos": cursos, "alunos": alunos,
    }


def _mk_rota(ofertas_cfg, *, data=DATA_ROTA):
    """App + usuário pedagógico + turma (calendário legado cobre `data`) e uma
    oferta por cfg (curso, alunos=[nome], tema=str|None). Retorna (app, ids)."""
    from app.models import TemaAula

    dia = _DIAS_SEMANA[data.weekday()]
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U rota", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        resp = User(
            name="Coord Rota", email="coord.rota@example.com",
            role="pedagogico", first_login=False, unidade_id=unidade.id,
        )
        db.session.add(resp)
        turma = Turma(
            nome="T rota", unidade_id=unidade.id, ativo=True, curso_id=None,
            dias_semana=dia, data_inicio=data, data_fim=data,
        )
        db.session.add(turma)
        db.session.flush()

        ids = {
            "resp": resp.id, "turma": turma.id, "ofertas": [],
            "alunos": {}, "temas": {}, "unidade": unidade.id,
        }
        for i, cfg in enumerate(ofertas_cfg):
            curso = Curso(nome=cfg["curso"], unidade_id=unidade.id, ativo=True)
            db.session.add(curso)
            db.session.flush()
            oferta = TurmaCurso(
                turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
                ativo=True, principal=(i == 0), dias_semana=dia,
                data_inicio=data, data_fim=data,
            )
            db.session.add(oferta)
            db.session.flush()
            ids["ofertas"].append(oferta.id)
            if cfg.get("tema"):
                tema = TemaAula(
                    curso_id=curso.id, titulo=cfg["tema"], ordem=1,
                    unidade_id=unidade.id, ativo=True,
                )
                db.session.add(tema)
                db.session.flush()
                ids["temas"][cfg["curso"]] = tema.id
            for nome in cfg.get("alunos", []):
                aluno = Aluno(nome=nome, unidade_id=unidade.id, ativo=True)
                db.session.add(aluno)
                db.session.flush()
                db.session.add(Inscricao(
                    aluno_id=aluno.id, turma_id=turma.id,
                    turma_curso_id=oferta.id, ativo=True,
                ))
                ids["alunos"][nome] = aluno.id
        db.session.commit()
    return app, ids


# --- a) oferta única: resolver NÃO valida vigência/dia ---------------------
def test_oferta_unica_sem_validacao_de_vigencia_e_dia(app):
    from app.services.turma_curso import resolver_oferta_lancamento

    d = _seed_servico(ofertas=[{
        "curso": "Natação", "dias": "Segunda",
        "ini": date(2026, 3, 2), "fim": date(2026, 3, 2), "alunos": ["A1"],
    }])
    o = d["ofertas"][0]
    # Data fora da vigência E do dia, SEM turma_curso_id → oferta única é
    # escolhida automaticamente, sem validação extra (comportamento anterior).
    out = resolver_oferta_lancamento(d["turma"].id, date(2025, 12, 25), turma_curso_id=None)
    assert out is not None and out.id == o.id


# --- b) 2+ ofertas no mesmo dia: não sobrescreve Frequencia/RegistroAula ----
def test_segunda_oferta_mesmo_dia_nao_sobrescreve_a_primeira():
    from app.models import RegistroAula

    app, ids = _mk_rota([
        {"curso": "Natação", "alunos": ["Aluno A"], "tema": "Tema A"},
        {"curso": "Judô", "alunos": ["Aluno B"], "tema": "Tema B"},
    ])
    client = _loga(app, ids["resp"])
    ds = DATA_ROTA.isoformat()
    oa, ob = ids["ofertas"]
    a = ids["alunos"]["Aluno A"]
    b = ids["alunos"]["Aluno B"]
    ta = ids["temas"]["Natação"]
    tb = ids["temas"]["Judô"]
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, "turma_curso": oa,
        f"aluno_{a}": ConceitoFrequencia.A.value, "tema_id": ta,
        "observacoes": "obs A",
    })
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, "turma_curso": ob,
        f"aluno_{b}": ConceitoFrequencia.F.value, "tema_id": tb,
        "observacoes": "obs B",
    })
    with app.app_context():
        fa = Frequencia.query.filter_by(turma_curso_id=oa).one()
        fb = Frequencia.query.filter_by(turma_curso_id=ob).one()
        assert fa.conceito == ConceitoFrequencia.A
        assert fb.conceito == ConceitoFrequencia.F
        regs = {
            r.turma_curso_id: r
            for r in RegistroAula.query.filter_by(data=DATA_ROTA).all()
        }
        assert regs[oa].tema_id == ta and regs[oa].observacoes == "obs A"
        assert regs[ob].tema_id == tb and regs[ob].observacoes == "obs B"


# --- c1) legado (0 ofertas): lançar 2x no mesmo dia atualiza, não duplica --
def test_legado_lancar_duas_vezes_atualiza_nao_duplica():
    app, ids = _mk_rota([{"curso": "Natação", "alunos": ["Aluno A"]}])
    # Desativa a única oferta → 0 ativas → caminho legado.
    with app.app_context():
        db.session.get(TurmaCurso, ids["ofertas"][0]).ativo = False
        db.session.commit()
    client = _loga(app, ids["resp"])
    ds = DATA_ROTA.isoformat()
    a = ids["alunos"]["Aluno A"]
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, f"aluno_{a}": ConceitoFrequencia.A.value,
    })
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, f"aluno_{a}": ConceitoFrequencia.F.value,
    })
    with app.app_context():
        rows = Frequencia.query.filter_by(aluno_id=a, turma_id=ids["turma"]).all()
        assert len(rows) == 1
        assert rows[0].conceito == ConceitoFrequencia.F
        assert rows[0].turma_curso_id is None


# --- c2) busca legada deve filtrar turma_curso_id IS NULL ------------------
def test_frequencia_legada_nao_confundida_com_oferta():
    app, ids = _mk_rota([{"curso": "Natação", "alunos": ["Aluno A"]}])
    oa = ids["ofertas"][0]
    a = ids["alunos"]["Aluno A"]
    client = _loga(app, ids["resp"])
    ds = DATA_ROTA.isoformat()
    # 1) lança pela OFERTA → linha com turma_curso_id=oa.
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, "turma_curso": oa,
        f"aluno_{a}": ConceitoFrequencia.A.value,
    })
    # 2) desativa a oferta → turma passa a ter 0 ofertas ativas (legado).
    with app.app_context():
        db.session.get(TurmaCurso, oa).ativo = False
        db.session.commit()
    # 3) lança no caminho LEGADO (sem turma_curso) no MESMO aluno/dia.
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, f"aluno_{a}": ConceitoFrequencia.F.value,
    })
    with app.app_context():
        legada = Frequencia.query.filter_by(
            aluno_id=a, turma_id=ids["turma"], turma_curso_id=None,
        ).all()
        # Esperado: nasce uma linha legada própria (IS NULL); a busca legada
        # NÃO deve reaproveitar/reescrever a linha da oferta.
        assert len(legada) == 1, "busca legada deveria filtrar turma_curso_id IS NULL"
        assert legada[0].conceito == ConceitoFrequencia.F


# --- d) dias_semana com acento/espaço e variante -feira --------------------
def test_data_bate_dias_semana_acento_espace_variante():
    from app.services.turma_curso import _data_bate_dias_semana

    ter = _data_weekday(1)
    qui = _data_weekday(3)
    seg = _data_weekday(0)
    assert _data_bate_dias_semana("Terça, Quinta", ter) is True
    assert _data_bate_dias_semana("Terça, Quinta", qui) is True
    assert _data_bate_dias_semana("Terça, Quinta", seg) is False
    assert _data_bate_dias_semana("Terça-feira", ter) is True
    assert _data_bate_dias_semana("Terça-feira", seg) is False


# --- e1) oferta informada: data fora da vigência é recusada ----------------
def test_resolver_recusa_data_fora_da_vigencia(app):
    from app.services.turma_curso import resolver_oferta_lancamento

    d = _seed_servico(ofertas=[
        {"curso": "Natação", "dias": DIA_ROTA, "ini": DATA_ROTA, "fim": DATA_ROTA, "alunos": ["A1"]},
        {"curso": "Judô", "dias": DIA_ROTA, "ini": DATA_ROTA, "fim": DATA_ROTA, "alunos": ["B1"]},
    ])
    oa = d["ofertas"][0]
    with pytest.raises(ValueError):
        resolver_oferta_lancamento(d["turma"].id, DATA_ROTA + timedelta(days=7), turma_curso_id=oa.id)


# --- e2) oferta informada: dia fora da grade é recusado --------------------
def test_resolver_recusa_dia_fora_da_grade(app):
    from app.services.turma_curso import resolver_oferta_lancamento

    d = _seed_servico(ofertas=[{
        "curso": "Natação", "dias": DIA_ROTA,
        "ini": DATA_ROTA - timedelta(days=30), "fim": DATA_ROTA + timedelta(days=30),
        "alunos": ["A1"],
    }])
    oa = d["ofertas"][0]
    outro_dia = _data_weekday((DATA_ROTA.weekday() + 2) % 7)  # outro dia, dentro da vigência
    with pytest.raises(ValueError):
        resolver_oferta_lancamento(d["turma"].id, outro_dia, turma_curso_id=oa.id)


# --- f) tema de outro curso recusado; tema curso_id NULL aceito -----------
def test_resolver_tema_de_outro_curso_recusado_e_null_aceito(app):
    from app.models import TemaAula
    from app.services.turma_curso import resolver_oferta_lancamento

    d = _seed_servico(ofertas=[
        {"curso": "Natação", "dias": DIA_ROTA, "ini": DATA_ROTA, "fim": DATA_ROTA, "alunos": ["A1"]},
        {"curso": "Judô", "dias": DIA_ROTA, "ini": DATA_ROTA, "fim": DATA_ROTA, "alunos": ["B1"]},
    ])
    oa = d["ofertas"][0]
    un = d["unidade"]
    tema_b = TemaAula(
        curso_id=d["cursos"]["Judô"], titulo="Tema Judô", ordem=1,
        unidade_id=un.id, ativo=True,
    )
    tema_null = TemaAula(
        curso_id=None, titulo="Tema Genérico", ordem=1, unidade_id=un.id, ativo=True,
    )
    db.session.add_all([tema_b, tema_null])
    db.session.commit()
    # Tema de outro curso → recusado.
    with pytest.raises(ValueError):
        resolver_oferta_lancamento(d["turma"].id, DATA_ROTA, turma_curso_id=oa.id, tema_id=tema_b.id)
    # Tema sem curso (curso_id NULL) → aceito.
    out = resolver_oferta_lancamento(d["turma"].id, DATA_ROTA, turma_curso_id=oa.id, tema_id=tema_null.id)
    assert out is not None and out.id == oa.id


# --- g) POST ignora alunos fora da pauta da oferta -------------------------
def test_post_ignora_aluno_fora_da_pauta_da_oferta():
    app, ids = _mk_rota([
        {"curso": "Natação", "alunos": ["Aluno A"]},
        {"curso": "Judô", "alunos": ["Aluno B"]},
    ])
    client = _loga(app, ids["resp"])
    ds = DATA_ROTA.isoformat()
    oa, ob = ids["ofertas"]
    a = ids["alunos"]["Aluno A"]
    b = ids["alunos"]["Aluno B"]
    # POST na oferta A tentando lançar também o aluno B (que é da oferta).
    client.post("/frequencia", data={
        "turma": ids["turma"], "data": ds, "turma_curso": oa,
        f"aluno_{a}": ConceitoFrequencia.A.value,
        f"aluno_{b}": ConceitoFrequencia.A.value,
    })
    with app.app_context():
        assert Frequencia.query.filter_by(turma_curso_id=oa, aluno_id=a).count() == 1
        # Aluno B não pertence à pauta de A → lançamento ignorado.
        assert Frequencia.query.filter_by(turma_curso_id=oa, aluno_id=b).count() == 0


# --- h) inscrição NULL: entra com 1 oferta, fica fora com 2+ ---------------
def test_inscricao_null_entra_com_1_oferta_e_fica_fora_com_2(app):
    unidade = Unidade(nome="U null", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    turma = Turma(nome="T null", unidade_id=unidade.id, ativo=True, curso_id=None)
    db.session.add(turma)
    db.session.flush()
    curso_a = Curso(nome="Natação", unidade_id=unidade.id, ativo=True)
    db.session.add(curso_a)
    db.session.flush()
    oa = TurmaCurso(
        turma_id=turma.id, curso_id=curso_a.id, unidade_id=unidade.id,
        ativo=True, principal=True,
    )
    db.session.add(oa)
    db.session.flush()

    aluno_curso = Aluno(nome="Com Curso", unidade_id=unidade.id, ativo=True)
    aluno_null = Aluno(nome="Sem Curso", unidade_id=unidade.id, ativo=True)
    db.session.add_all([aluno_curso, aluno_null])
    db.session.flush()
    db.session.add_all([
        Inscricao(aluno_id=aluno_curso.id, turma_id=turma.id, turma_curso_id=oa.id, ativo=True),
        Inscricao(aluno_id=aluno_null.id, turma_id=turma.id, turma_curso_id=None, ativo=True),
    ])
    db.session.commit()

    # Com 1 oferta ativa (fallback NULL ligado): o aluno sem curso entra.
    pauta_1 = _alunos_da_oferta(turma.id, oa.id, incluir_inscricoes_null=True)
    assert {a.id for a in pauta_1} == {aluno_curso.id, aluno_null.id}

    # Surge a 2ª oferta → modo estrito (NULL fora de toda pauta).
    curso_b = Curso(nome="Judô", unidade_id=unidade.id, ativo=True)
    db.session.add(curso_b)
    db.session.flush()
    db.session.add(TurmaCurso(
        turma_id=turma.id, curso_id=curso_b.id, unidade_id=unidade.id, ativo=True,
    ))
    db.session.commit()

    pauta_2 = _alunos_da_oferta(turma.id, oa.id, incluir_inscricoes_null=False)
    assert {a.id for a in pauta_2} == {aluno_curso.id}


# =============================================================================
# ETAPA F — oferta automática ao criar turma (criar_oferta_inicial_da_turma)
# =============================================================================

from datetime import time


def _mk_app_criacao():
    """App + unidade + usuário pedagógico + curso ativo da mesma unidade.
    Retorna (app, ids) com 'resp', 'unidade' e 'curso'."""
    app = _novo_app()
    with app.app_context():
        db.create_all()
        unidade = Unidade(nome="U F", ativo=True)
        db.session.add(unidade)
        db.session.flush()
        resp = User(
            name="Coord F", email="coord.f@example.com",
            role="pedagogico", first_login=False, unidade_id=unidade.id,
        )
        db.session.add(resp)
        curso = Curso(nome="Natação F", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.commit()
        ids = {"resp": resp.id, "unidade": unidade.id, "curso": curso.id}
    return app, ids


def _post_nova_turma(app, ids, *, nome, curso_id=None, dias="Segunda", data=DATA_ROTA):
    """POST /turma/nova com datas personalizadas cobrindo `data` (Segunda).
    Retorna (resp, client)."""
    client = _loga(app, ids["resp"])
    form = {
        "turma": nome,
        "dias_semana": dias,
        "datas_personalizadas": "1",
        "data_inicio": data.isoformat(),
        "data_fim": data.isoformat(),
    }
    if curso_id is not None:
        form["curso_id"] = curso_id
    return client.post("/turma/nova", data=form), client


# --- função: copia atributos, principal=False, oferta única ----------------
def test_criar_oferta_inicial_copia_atributos_e_principal_false(app):
    from app.services.turma_curso import criar_oferta_inicial_da_turma

    unidade = Unidade(nome="U F func", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Natação F func", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="T F func", unidade_id=unidade.id, ativo=True, curso_id=curso.id,
        turno="Manhã", dias_semana="Segunda, Quarta",
        hora_inicio=time(9, 0), hora_fim=time(10, 30),
        data_inicio=date(2026, 3, 2), data_fim=date(2026, 12, 15),
        centro_custo="CC-42",
    )
    db.session.add(turma)
    db.session.flush()

    oferta = criar_oferta_inicial_da_turma(turma)
    db.session.commit()

    assert oferta is not None
    assert oferta.principal is False
    assert oferta.ativo is True
    assert oferta.curso_id == curso.id
    assert oferta.turma_id == turma.id
    assert oferta.unidade_id == unidade.id
    assert oferta.turno == "Manhã"
    assert oferta.dias_semana == "Segunda, Quarta"
    assert oferta.hora_inicio == time(9, 0)
    assert oferta.hora_fim == time(10, 30)
    assert oferta.data_inicio == date(2026, 3, 2)
    assert oferta.data_fim == date(2026, 12, 15)
    assert oferta.centro_custo == "CC-42"
    assert TurmaCurso.query.filter_by(turma_id=turma.id).count() == 1


# --- função: turma sem curso não gera oferta --------------------------------
def test_criar_oferta_inicial_turma_sem_curso_devolve_none(app):
    from app.services.turma_curso import criar_oferta_inicial_da_turma

    unidade = Unidade(nome="U F none", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    turma = Turma(
        nome="T F none", unidade_id=unidade.id, ativo=True, curso_id=None,
    )
    db.session.add(turma)
    db.session.flush()

    assert criar_oferta_inicial_da_turma(turma) is None
    db.session.commit()
    assert TurmaCurso.query.count() == 0


# --- função: idempotente (chamar duas vezes não duplica) -------------------
def test_criar_oferta_inicial_idempotente_nao_duplica(app):
    from app.services.turma_curso import criar_oferta_inicial_da_turma

    unidade = Unidade(nome="U F idem", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    curso = Curso(nome="Natação F idem", unidade_id=unidade.id, ativo=True)
    db.session.add(curso)
    db.session.flush()
    turma = Turma(
        nome="T F idem", unidade_id=unidade.id, ativo=True, curso_id=curso.id,
    )
    db.session.add(turma)
    db.session.flush()

    o1 = criar_oferta_inicial_da_turma(turma)
    o2 = criar_oferta_inicial_da_turma(turma)
    db.session.commit()

    assert o1 is not None
    assert o2.id == o1.id
    assert TurmaCurso.query.filter_by(turma_id=turma.id).count() == 1


# --- rota: turma com curso gera exatamente 1 oferta ------------------------
def test_nova_turma_com_curso_gera_uma_oferta_principal_false():
    app, ids = _mk_app_criacao()
    nome = "Turma F Rota"
    r, _ = _post_nova_turma(app, ids, nome=nome, curso_id=ids["curso"])
    assert r.status_code == 302
    with app.app_context():
        turma = Turma.query.filter_by(nome=nome).first()
        assert turma is not None
        assert turma.curso_id == ids["curso"]
        ofertas = TurmaCurso.query.filter_by(turma_id=turma.id).all()
        assert len(ofertas) == 1
        assert ofertas[0].principal is False
        assert ofertas[0].ativo is True
        assert ofertas[0].curso_id == ids["curso"]


# --- rota: turma sem curso não gera oferta ---------------------------------
def test_nova_turma_sem_curso_nao_gera_oferta():
    app, ids = _mk_app_criacao()
    nome = "Turma F Rota Sem Curso"
    r, _ = _post_nova_turma(app, ids, nome=nome, curso_id=None)
    assert r.status_code == 302
    with app.app_context():
        turma = Turma.query.filter_by(nome=nome).first()
        assert turma is not None
        assert turma.curso_id is None
        assert TurmaCurso.query.filter_by(turma_id=turma.id).count() == 0


# --- rota: frequência lançada em turma nova grava turma_curso_id -----------
def test_frequencia_lancada_em_turma_nova_grava_turma_curso_id():
    app, ids = _mk_app_criacao()
    nome = "Turma F Lanca"
    _post_nova_turma(app, ids, nome=nome, curso_id=ids["curso"])
    with app.app_context():
        turma = Turma.query.filter_by(nome=nome).first()
        oferta = TurmaCurso.query.filter_by(turma_id=turma.id).first()
        assert oferta is not None
        aluno = Aluno(nome="Aluno Lanca", unidade_id=turma.unidade_id, ativo=True)
        db.session.add(aluno)
        db.session.flush()
        db.session.add(Inscricao(
            aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
            ativo=True,
        ))
        db.session.commit()
        turma_id, oferta_id, aluno_id = turma.id, oferta.id, aluno.id

    client = _loga(app, ids["resp"])
    # Sem turma_curso no form: com oferta única, o resolver a escolhe sozinho.
    client.post("/frequencia", data={
        "turma": turma_id,
        "data": DATA_ROTA.isoformat(),
        f"aluno_{aluno_id}": ConceitoFrequencia.A.value,
    })
    with app.app_context():
        freq = Frequencia.query.filter_by(aluno_id=aluno_id, turma_id=turma_id).first()
        assert freq is not None, "lançamento deveria criar registro de frequência"
        assert freq.turma_curso_id == oferta_id


# --- rota: falha na oferta não deixa turma gravada (transação única) -------
def test_falha_ao_criar_oferta_nao_deixa_turma_gravada(monkeypatch):
    app, ids = _mk_app_criacao()
    import app.registros.turmas as turmas_mod

    def _boom(_turma):
        raise RuntimeError("oferta falhou")

    monkeypatch.setattr(turmas_mod, "criar_oferta_inicial_da_turma", _boom)

    nome = "Turma F Rollback"
    r, _ = _post_nova_turma(app, ids, nome=nome, curso_id=ids["curso"])
    assert r.status_code == 302
    with app.app_context():
        assert Turma.query.filter_by(nome=nome).first() is None
        assert TurmaCurso.query.count() == 0

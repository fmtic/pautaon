"""Etapa M4 — Política de desativar_oferta + histórico de oferta inativa
em período encerrado.

Regra do responsável: desativar_oferta só pode inativar se NÃO houver aluno
associado à oferta em período ainda em andamento (guarda só no caminho da
rota ``registros.turma_oferta_desativar``; o serviço protege-se via
``verificar_alunos_em_andamento=True``). Leitores de histórico
(``bi_filtros.cond_inscricao_enturmada`` e ``aluno_status``) aceitam oferta
INATIVA quando o período da turma já encerrou — desativar oferta de período
encerrado não altera BI/status retroativamente.

Cobertura (roteiro do Passo 4): bloqueia com aluno ativo em período em
andamento/futuro e em turma sem período (flash traz contagem e nome do
período); permite com período encerrado (BI e status estáveis), com
inscrição inativa e sem alunos; BI de período em andamento não conta oferta
inativa; guarda antigo (principal com 2+ restantes) preservado; serviço sem
o flag mantém comportamento antigo (flusso de excluir_turma intocado);
usuário de outra unidade → 403; admin sem unidade na sessão → 403.

Um usuário por teste (regra do responsável).
"""

from datetime import date, time, timedelta

import pytest
from sqlalchemy import func, select

from app import create_app
from app.database import db
from _helpers import professor_semente
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PeriodoLetivo,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import StatusAluno
from app.relatorios.bi_filtros import cond_inscricao_enturmada
from app.services.aluno_status import status_alunos
from app.services.turma_curso import desativar_oferta
from app.utils.timezone import get_local_now
from config import Config

HOJE = get_local_now().date()


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
        SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
    )
    with test_app.app_context():
        assert db.engine.dialect.name == "sqlite"
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def _loga(client, user_id, unidade_id=None):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
        if unidade_id is not None:
            session["unidade_id"] = unidade_id
    return client


def _datas(periodo_kind):
    """(data_inicio, data_fim, nome) do período; None = turma sem período."""
    if periodo_kind == "andamento":
        return HOJE - timedelta(days=30), HOJE + timedelta(days=60), "Letivo 2026"
    if periodo_kind == "futuro":
        return HOJE + timedelta(days=100), HOJE + timedelta(days=200), "Letivo 2027"
    if periodo_kind == "encerrado":
        return HOJE - timedelta(days=200), HOJE - timedelta(days=100), "Letivo 2025"
    return None


def _seed(periodo="andamento", *, alunos_ativos=1, alunos_inativos=0,
          role="pedagogico", ofertas=1):
    """Unidade + 1 usuário (``role``) + turma do período dado + ``ofertas``
    ofertas ativas (principal na primeira) + ``alunos_ativos`` inscrições
    ativas e ``alunos_inativos`` inativas na PRIMEIRA oferta.

    Retorna dict de ids. Aluno de outra unidade não é semeado aqui: os
    testes de isolamento criam o intruso à parte (um usuário por teste)."""
    unidade = Unidade(nome="U M4", ativo=True)
    db.session.add(unidade)
    db.session.flush()
    user = User(
        name=f"Usuário {role}", email=f"{role}.m4@example.com",
        role=role, first_login=False, unidade_id=unidade.id,
    )
    db.session.add(user)

    datas = _datas(periodo)
    periodo_obj = None
    if datas:
        ini, fim, nome = datas
        periodo_obj = PeriodoLetivo(
            nome=nome, data_inicio=ini, data_fim=fim, unidade_id=unidade.id,
        )
        db.session.add(periodo_obj)
        db.session.flush()

    turma = Turma(
        nome="Turma M4", unidade_id=unidade.id, ativo=True, turno="Manhã",
        data_inicio=(periodo_obj.data_inicio if periodo_obj
                     else HOJE - timedelta(days=30)),
        data_fim=(periodo_obj.data_fim if periodo_obj
                  else HOJE + timedelta(days=60)),
        periodo_letivo_id=periodo_obj.id if periodo_obj else None,
    )
    db.session.add(turma)
    db.session.flush()

    ofert = []
    for k in range(ofertas):
        curso = Curso(nome=f"Curso {k + 1}", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()
        o = TurmaCurso(
            turma_id=turma.id, curso_id=curso.id, unidade_id=unidade.id,
            ativo=True, principal=(k == 0), turno="Manhã",
            data_inicio=turma.data_inicio, data_fim=turma.data_fim,
            programa="Teste", professor_id=professor_semente(unidade.id).id,
        )
        db.session.add(o)
        db.session.flush()
        ofert.append(o)

    def _matricular(n, *, ativo):
        ids = []
        for j in range(n):
            aluno = Aluno(
                nome=f"Aluno {'A' if ativo else 'I'}{j + 1}",
                ativo=True, unidade_id=unidade.id,
            )
            db.session.add(aluno)
            db.session.flush()
            insc = Inscricao(
                aluno_id=aluno.id, turma_id=turma.id,
                turma_curso_id=ofert[0].id, ativo=ativo,
                data_inicio=periodo_obj.data_inicio if periodo_obj else turma.data_inicio,
            )
            if not ativo:
                insc.motivo_desativacao = "DESENTURMADO"
                insc.data_desativacao = get_local_now()
            db.session.add(insc)
            db.session.flush()
            ids.append((aluno.id, insc.id))
        return ids

    ativos = _matricular(alunos_ativos, ativo=True)
    inativos = _matricular(alunos_inativos, ativo=False)
    db.session.commit()
    return {
        "unidade": unidade.id, "user": user.id,
        "periodo": periodo_obj.id if periodo_obj else None,
        "turma": turma.id,
        "ofertas": [o.id for o in ofert],
        "alunos_ativos": [a for a, _ in ativos],
        "inscricoes_ativas": [i for _, i in ativos],
        "inscricoes_inativas": [i for _, i in inativos],
    }


def _desativar(client, oferta_id):
    return client.post(f"/turma/oferta/{oferta_id}/desativar",
                       follow_redirects=False)


def _count_enturmadas(oferta_id):
    """Inscrições ativas da oferta que o BI conta como enturmadas."""
    return db.session.execute(
        select(func.count(Inscricao.id))
        .where(Inscricao.turma_curso_id == oferta_id, cond_inscricao_enturmada())
    ).scalar_one()


# =============================================================================
# Guarda da rota — bloqueios
# =============================================================================


def test_bloqueia_com_aluno_ativo_em_periodo_em_andamento(client, app):
    c = _seed("andamento", alunos_ativos=2)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    assert "/ofertas" in resp.headers["Location"]
    with app.app_context():
        oferta = db.session.get(TurmaCurso, c["ofertas"][0])
        assert oferta.ativo is True
        for iid in c["inscricoes_ativas"]:
            assert db.session.get(Inscricao, iid).ativo is True


def test_flash_menciona_contagem_e_nome_do_periodo(client, app):
    """A rota mostra a mensagem do serviço em flash; a fonte (ValueError)
    é verificada aqui — inclui a contagem de alunos e o nome do período.
    Com follow_redirects=False o flash só apareceria na página seguinte,
    então a asserção é feita sobre a exceção que gera o flash."""
    c = _seed("andamento", alunos_ativos=1)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        oferta = db.session.get(TurmaCurso, c["ofertas"][0])
        assert oferta.ativo is True  # rota não gravou nada
        with pytest.raises(ValueError) as exc:
            desativar_oferta(oferta, verificar_alunos_em_andamento=True)
        msg = str(exc.value)
    assert "1 aluno(s) ativo(s)" in msg
    assert "Letivo 2026" in msg


def test_bloqueia_em_periodo_futuro(client, app):
    c = _seed("futuro", alunos_ativos=1)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is True


def test_bloqueia_turma_sem_periodo(client, app):
    """Turma sem periodo_letivo_id conta como em andamento (regra do M4)."""
    c = _seed(None, alunos_ativos=1)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is True


# =============================================================================
# Guarda da rota — permitidos
# =============================================================================


def test_permite_periodo_encerrado_bi_e_status_estaveis(client, app):
    """Desativar oferta de período encerrado não altera retroativamente o
    BI (inscrição segue contada) nem o status do aluno."""
    c = _seed("encerrado", alunos_ativos=1)
    aluno_id = c["alunos_ativos"][0]
    oferta_id = c["ofertas"][0]
    _loga(client, c["user"])

    with app.app_context():
        bi_antes = _count_enturmadas(oferta_id)
        status_antes = status_alunos(c["periodo"], aluno_ids=[aluno_id])
        assert bi_antes == 1
        assert status_antes[aluno_id] is not None

    resp = _desativar(client, oferta_id)

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, oferta_id).ativo is False
        assert _count_enturmadas(oferta_id) == bi_antes
        assert status_alunos(c["periodo"], aluno_ids=[aluno_id]) == status_antes


def test_permite_com_inscricao_inativa(client, app):
    c = _seed("andamento", alunos_ativos=0, alunos_inativos=1)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is False


def test_permite_oferta_sem_alunos(client, app):
    c = _seed("andamento", alunos_ativos=0)
    _loga(client, c["user"])

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 302
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is False


# =============================================================================
# Leitura — BI e status com oferta inativa
# =============================================================================


def test_bi_periodo_andamento_nao_conta_oferta_inativa(app):
    """Oferta inativa em período em andamento: inscrição ativa deixa de ser
    contada como enturmada (regra J2/B6 preservada para não-encerrado)."""
    c = _seed("andamento", alunos_ativos=1)
    with app.app_context():
        assert _count_enturmadas(c["ofertas"][0]) == 1
        # Caminho interno (sem a guarda da rota): excluir_turma et al.
        desativar_oferta(db.session.get(TurmaCurso, c["ofertas"][0]))
        assert _count_enturmadas(c["ofertas"][0]) == 0


def test_servico_sem_flag_mantem_comportamento_antigo(app):
    """Fluxos internos (excluir_turma) não podem ser afetados pela guarda:
    desativar_oferta(oferta) sem flag desativa mesmo com aluno ativo em
    período em andamento."""
    c = _seed("andamento", alunos_ativos=1)
    with app.app_context():
        oferta = desativar_oferta(db.session.get(TurmaCurso, c["ofertas"][0]))
        assert oferta.ativo is False


def test_status_periodo_encerrado_estavel_com_oferta_inativa(app):
    """Mesmo cenário do teste de rota, agora direto no serviço de status."""
    c = _seed("encerrado", alunos_ativos=1)
    aluno_id = c["alunos_ativos"][0]
    with app.app_context():
        antes = status_alunos(c["periodo"], aluno_ids=[aluno_id])
        assert antes[aluno_id] == StatusAluno.NOVO
        desativar_oferta(db.session.get(TurmaCurso, c["ofertas"][0]))
        depois = status_alunos(c["periodo"], aluno_ids=[aluno_id])
        assert depois == antes


# =============================================================================
# Guardas antigos preservados + isolamento
# =============================================================================


def test_guarda_principal_com_2_restantes_preservada(client, app):
    """Desativar a única principal deixando 2+ ativas sem principal continua
    bloqueado (regra da Fase 2), mesmo com período encerrado (guarda M4
    inofensiva aqui)."""
    c = _seed("encerrado", alunos_ativos=0, ofertas=3)
    with app.app_context():
        segunda = db.session.get(TurmaCurso, c["ofertas"][1])
        segunda.principal = False
        db.session.commit()
    principal_id = c["ofertas"][0]
    _loga(client, c["user"])

    resp = _desativar(client, principal_id)

    assert resp.status_code == 302
    with app.app_context():
        oferta = db.session.get(TurmaCurso, principal_id)
        assert oferta.ativo is True
        # O flash da rota é a mensagem antiga de principal, reproducible via
        # serviço (rota converte ValueError em flash).
        with pytest.raises(ValueError, match="sem principal"):
            desativar_oferta(oferta, verificar_alunos_em_andamento=True)


def test_usuario_de_outra_unidade_recebe_403(client, app):
    c = _seed("andamento", alunos_ativos=1)
    with app.app_context():
        outra = Unidade(nome="U M4 Outra", ativo=True)
        db.session.add(outra)
        db.session.flush()
        intruso = User(
            name="Intruso", email="intruso.m4@example.com",
            role="pedagogico", first_login=False, unidade_id=outra.id,
        )
        db.session.add(intruso)
        db.session.commit()
        intruso_id, outra_id = intruso.id, outra.id
    _loga(client, intruso_id, unidade_id=outra_id)

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 403
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is True


def test_admin_sem_unidade_na_sessao_recebe_403(client, app):
    """Visão Global não escreve: assert_unidade_context bloqueia unidade
    None até para ADMIN (regra do responsável)."""
    c = _seed("andamento", alunos_ativos=1, role="admin")
    _loga(client, c["user"])  # sem unidade_id na sessão

    resp = _desativar(client, c["ofertas"][0])

    assert resp.status_code == 403
    with app.app_context():
        assert db.session.get(TurmaCurso, c["ofertas"][0]).ativo is True

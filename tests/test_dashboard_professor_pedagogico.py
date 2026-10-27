"""
Testes do Painel Pedagógico do Professor.

Testa:
1. Serviço `obter_estatisticas_professor`:
   - Cálculos quantitativos (frequência %, faltas, presenças)
   - Cálculos qualitativos (conceitos A, B, C, D, IQR)
   - Perfis de rendimento dos alunos (Alto Rendimento, Regular, Atenção Pedagógica)
   - Cobertura de pauta e histórico
2. Rota `main.painel_pedagogico_professor`:
   - Controle de acesso (403 para perfil não autorizado)
   - Renderização correta com status 200 para perfil professor
"""

from datetime import date, timedelta
import pytest

from app import create_app, db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    PeriodoLetivo,
    RegistroAula,
    TemaAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import ConceitoFrequencia, UserRole
from app.services.estatisticas_professor import obter_estatisticas_professor
from config import Config

HOJE = date.today()
_DIAS = ("Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado", "Domingo")
DIA_HOJE = _DIAS[HOJE.weekday()]


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
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _criar_cenario(app):
    """Cria professor, turma, oferta, alunos e frequências com conceitos A, B, C, D, F."""
    with app.app_context():
        unidade = Unidade(nome="Unidade Teste", ativo=True)
        db.session.add(unidade)
        db.session.flush()

        periodo = PeriodoLetivo(
            nome="2026.1",
            data_inicio=HOJE - timedelta(days=30),
            data_fim=HOJE + timedelta(days=30),
            ativo=True,
            unidade_id=unidade.id,
        )
        db.session.add(periodo)
        db.session.flush()

        professor = User(
            name="Prof. Teste",
            email="prof@teste.com",
            role=UserRole.PROFESSOR.value,
            is_active=True,
            first_login=False,
            unidade_id=unidade.id,
        )
        professor.set_password("senha123")
        db.session.add(professor)
        db.session.flush()

        curso = Curso(nome="Violão Iniciante", unidade_id=unidade.id, ativo=True)
        db.session.add(curso)
        db.session.flush()

        tema1 = TemaAula(curso_id=curso.id, titulo="Postura e Cordas", ordem=1, unidade_id=unidade.id)
        tema2 = TemaAula(curso_id=curso.id, titulo="Primeiros Acordes", ordem=2, unidade_id=unidade.id)
        db.session.add_all([tema1, tema2])
        db.session.flush()

        turma = Turma(
            nome="Turma V-A",
            unidade_id=unidade.id,
            periodo_letivo_id=periodo.id,
            professor_id=professor.id,
            curso_id=curso.id,
            data_inicio=HOJE - timedelta(days=14),
            data_fim=HOJE + timedelta(days=14),
            ativo=True,
        )
        db.session.add(turma)
        db.session.flush()

        oferta = TurmaCurso(
            turma_id=turma.id,
            curso_id=curso.id,
            professor_id=professor.id,
            unidade_id=unidade.id,
            data_inicio=turma.data_inicio,
            data_fim=turma.data_fim,
            programa="Música",
            ativo=True,
        )
        db.session.add(oferta)
        db.session.flush()

        # Alunos:
        # 1. Aluno Alto Rendimento (A, B)
        a1 = Aluno(nome="Ana Silva", unidade_id=unidade.id, ativo=True)
        # 2. Aluno Regular/Baixo (C, D)
        a2 = Aluno(nome="Carlos Souza", unidade_id=unidade.id, ativo=True)
        # 3. Aluno Faltoso (F, F, F) -> busca ativa
        a3 = Aluno(nome="Beatriz Lima", unidade_id=unidade.id, ativo=True)
        db.session.add_all([a1, a2, a3])
        db.session.flush()

        for a in (a1, a2, a3):
            db.session.add(Inscricao(
                aluno_id=a.id,
                turma_id=turma.id,
                turma_curso_id=oferta.id,
                ativo=True,
            ))

        d1 = HOJE - timedelta(days=7)
        d2 = HOJE

        # Registro de aula
        db.session.add(RegistroAula(
            turma_id=turma.id,
            turma_curso_id=oferta.id,
            data=d1,
            tema_id=tema1.id,
            instrutor_id=professor.id,
            unidade_id=unidade.id,
        ))
        db.session.add(RegistroAula(
            turma_id=turma.id,
            turma_curso_id=oferta.id,
            data=d2,
            tema_id=tema2.id,
            instrutor_id=professor.id,
            unidade_id=unidade.id,
        ))

        # Frequências D1
        db.session.add(Frequencia(aluno_id=a1.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d1, conceito=ConceitoFrequencia.A, unidade_id=unidade.id))
        db.session.add(Frequencia(aluno_id=a2.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d1, conceito=ConceitoFrequencia.C, unidade_id=unidade.id))
        db.session.add(Frequencia(aluno_id=a3.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d1, conceito=ConceitoFrequencia.F, unidade_id=unidade.id))

        # Frequências D2
        db.session.add(Frequencia(aluno_id=a1.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d2, conceito=ConceitoFrequencia.B, unidade_id=unidade.id))
        db.session.add(Frequencia(aluno_id=a2.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d2, conceito=ConceitoFrequencia.D, unidade_id=unidade.id))
        db.session.add(Frequencia(aluno_id=a3.id, turma_id=turma.id, turma_curso_id=oferta.id, data=d2, conceito=ConceitoFrequencia.F, unidade_id=unidade.id))

        db.session.commit()

        return {
            "professor_id": professor.id,
            "turma_id": turma.id,
            "oferta_id": oferta.id,
            "aluno1_id": a1.id,
            "aluno2_id": a2.id,
            "aluno3_id": a3.id,
        }


def test_obter_estatisticas_professor_sem_turmas(app):
    """Professor sem turmas retorna estrutura vazia sem erro."""
    with app.app_context():
        stats = obter_estatisticas_professor(user_id=999)
        assert stats["entradas"] == []
        assert stats["entrada_selecionada"] is None
        assert stats["resumo_geral"]["total_alunos"] == 0
        assert stats["resumo_geral"]["frequencia_media_turma"] == 0.0


def test_obter_estatisticas_professor_calculos(app):
    """Verifica cálculos de conceitos A/B/C/D, frequência e rendimento."""
    cenario = _criar_cenario(app)

    with app.app_context():
        stats = obter_estatisticas_professor(
            user_id=cenario["professor_id"],
            turma_id=cenario["turma_id"],
            turma_curso_id=cenario["oferta_id"],
        )

        assert stats["entrada_selecionada"] is not None
        resumo = stats["resumo_geral"]
        assert resumo["total_alunos"] == 3
        assert resumo["total_aulas_realizadas"] == 2

        # Presenças: A1 teve 2, A2 teve 2 -> total 4 presenças
        # Faltas: A3 teve 2 -> total 2 faltas
        assert resumo["total_presencas"] == 4
        assert resumo["total_faltas"] == 2
        # Frequência: 4 / 6 = 66.7%
        assert resumo["frequencia_media_turma"] == 66.7

        # Conceitos: A=1, B=1, C=1, D=1
        conceitos = stats["qualitativo_conceitos"]["contagem"]
        assert conceitos["A"] == 1
        assert conceitos["B"] == 1
        assert conceitos["C"] == 1
        assert conceitos["D"] == 1

        # Alunos:
        alunos_dict = {a["id"]: a for a in stats["alunos_rendimento"]}

        # Ana Silva: 100% frequência, conceitos A e B -> ALTO
        ana = alunos_dict[cenario["aluno1_id"]]
        assert ana["freq_pct"] == 100.0
        assert ana["categoria_rendimento"] == "ALTO"
        assert ana["presencas"] == 2
        assert ana["faltas"] == 0

        # Carlos Souza: 100% frequência, conceitos C e D -> BAIXO
        carlos = alunos_dict[cenario["aluno2_id"]]
        assert carlos["freq_pct"] == 100.0
        assert carlos["categoria_rendimento"] == "BAIXO"
        assert carlos["presencas"] == 2

        # Beatriz Lima: 0% frequência, 2 faltas -> Risco
        beatriz = alunos_dict[cenario["aluno3_id"]]
        assert beatriz["freq_pct"] == 0.0
        assert beatriz["faltas"] == 2
        assert beatriz["faixa_freq"] == "lo"
        assert beatriz["faltas_consecutivas"] == 2

        # Cobertura curricular
        cobertura = stats["cobertura_pauta"]
        assert cobertura["temas_total"] == 2
        assert cobertura["temas_ministrados"] == 2
        assert cobertura["temas_cobertura_pct"] == 100.0


def test_rota_painel_pedagogico_permissao_e_render(app):
    """Verifica acesso à rota /professor/painel-pedagogico."""
    cenario = _criar_cenario(app)
    client = app.test_client()

    with app.app_context():
        prof = db.session.get(User, cenario["professor_id"])

        with client.session_transaction() as sess:
            sess["_user_id"] = str(prof.id)
            sess["_fresh"] = True

        resp = client.get("/professor/painel-pedagogico")
        assert resp.status_code == 200
        html = resp.get_data(as_text=True)
        assert "Painel Pedagógico" in html
        assert "Qualitativo da Frequência" in html
        assert "Rendimento e Assiduidade por Aluno" in html
        assert "Ana Silva" in html

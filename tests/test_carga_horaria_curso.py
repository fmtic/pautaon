"""
Testes automatizados para a rota de Carga Horária e Catálogo de Cursos
(/turmas/carga-horaria) e edição de cursos via modal (/cursos/<id>/editar).
Valida a alternância exclusiva entre turmas vigentes e concluídas,
além do cascateamento de todos os dropdowns de filtros pelo filtro-mestre de vigência.
"""

from datetime import date, timedelta
import pytest
from app import create_app, db
from app.models import Curso, PeriodoLetivo, Turma, Unidade, User
from config import Config


class SQLiteTestConfig(Config):
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    TESTING = True
    WTF_CSRF_ENABLED = False


@pytest.fixture
def app():
    test_app = create_app(SQLiteTestConfig)
    test_app.config.update({
        "TESTING": True,
        "WTF_CSRF_ENABLED": False,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    })
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def test_carga_horaria_turmas_alternancia_exclusiva_e_filtros_cascateados(client, app):
    """
    Testa se a rota /turmas/carga-horaria:
    1. Opera em modalidade estritamente alternada (Vigentes vs Concluídos).
    2. Cascateia as opções dos seletores (Período, Professor, Curso) com base no filtro-mestre de vigência.
    3. Exibe o botão visível 'Limpar Filtros'.
    4. Permite editar o curso via modal e salva as alterações.
    """
    hoje = date.today()
    with app.app_context():
        unidade = Unidade(nome="Unidade Central", ativo=True)
        db.session.add(unidade)
        db.session.commit()

        # Admin
        admin = User(
            name="Coordenador Admin",
            email="admin@test.com",
            role="admin",
            first_login=False,
            unidade_id=unidade.id,
        )
        admin.set_password("Senha123!")

        # Professores
        prof_vigente = User(
            name="Professora Ativa Vigente",
            email="prof.ativa@test.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )
        prof_passado = User(
            name="Professor Anterior Concluido",
            email="prof.anterior@test.com",
            role="professor",
            first_login=False,
            unidade_id=unidade.id,
        )

        db.session.add_all([admin, prof_vigente, prof_passado])
        db.session.commit()

        # Período vigente (termina no futuro)
        periodo_vig = PeriodoLetivo(
            nome="Semestre Atual",
            data_inicio=hoje - timedelta(days=30),
            data_fim=hoje + timedelta(days=60),
            unidade_id=unidade.id,
            ativo=True,
        )
        # Período concluído (terminou no passado)
        periodo_conc = PeriodoLetivo(
            nome="Semestre Passado",
            data_inicio=hoje - timedelta(days=180),
            data_fim=hoje - timedelta(days=90),
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add_all([periodo_vig, periodo_conc])
        db.session.commit()

        # Curso 1 (com turma vigente)
        curso1 = Curso(
            nome="Python para Dados",
            descricao="Curso preparatório de análise de dados",
            ativo=True,
            unidade_id=unidade.id,
        )
        # Curso 2 (com turma concluída)
        curso2 = Curso(
            nome="Design Grafico",
            descricao="Design e ilustração",
            ativo=True,
            unidade_id=unidade.id,
        )
        db.session.add_all([curso1, curso2])
        db.session.commit()

        # Turma no período vigente
        turma_vig = Turma(
            nome="Turma Python 2026A",
            curso_id=curso1.id,
            periodo_letivo_id=periodo_vig.id,
            professor_id=prof_vigente.id,
            unidade_id=unidade.id,
            ativo=True,
        )
        # Turma no período concluído
        turma_conc = Turma(
            nome="Turma Design 2025B",
            curso_id=curso2.id,
            periodo_letivo_id=periodo_conc.id,
            professor_id=prof_passado.id,
            unidade_id=unidade.id,
            ativo=True,
        )
        db.session.add_all([turma_vig, turma_conc])
        db.session.commit()

        # Login com admin
        with client.session_transaction() as sess:
            sess["_user_id"] = str(admin.id)
            sess["unidade_id"] = unidade.id

        # ── 1. ACESSO PADRÃO: MODO VIGENTE ──
        resp_padrao = client.get("/turmas/carga-horaria")
        assert resp_padrao.status_code == 200
        html_padrao = resp_padrao.get_data(as_text=True)

        # Botão Limpar Filtros
        assert "Limpar Filtros" in html_padrao

        # Cabeçalhos do modo Vigente
        assert "Atualmente lecionado por" in html_padrao
        assert "(turmas em períodos letivos ainda vigentes)" in html_padrao
        assert "(%) Atualmente presente em" in html_padrao
        assert "Foram lecionadas por" not in html_padrao

        # Tabela (tbody) do modo Vigente
        tbody_padrao = html_padrao.split("<tbody>")[1].split("</tbody>")[0]
        assert "Python para Dados" in tbody_padrao
        assert "Professora Ativa Vigente" in tbody_padrao
        assert "Professor Anterior Concluido" not in tbody_padrao

        # Dropdowns cascateados no modo Vigente
        select_p_vig = html_padrao.split('id="filtroPeriodo"')[1].split("</select>")[0]
        assert "Semestre Atual" in select_p_vig
        assert "Semestre Passado" not in select_p_vig

        select_prof_vig = html_padrao.split('id="filtroProfessor"')[1].split("</select>")[0]
        assert "Professora Ativa Vigente" in select_prof_vig
        assert "Professor Anterior Concluido" not in select_prof_vig

        select_c_vig = html_padrao.split('id="filtroCurso"')[1].split("</select>")[0]
        assert "Python para Dados" in select_c_vig
        assert "Design Grafico" not in select_c_vig

        # ── 2. MODO CONCLUÍDO (status_periodo=concluido) ──
        resp_conc = client.get("/turmas/carga-horaria?status_periodo=concluido")
        assert resp_conc.status_code == 200
        html_conc = resp_conc.get_data(as_text=True)

        # Cabeçalhos do modo Concluído
        assert "Foram lecionadas por" in html_conc
        assert "(turmas em períodos letivos já concluídos)" in html_conc
        assert "(%) Foi presente em" in html_conc
        assert "Atualmente lecionado por" not in html_conc

        # Tabela (tbody) do modo Concluído
        tbody_conc = html_conc.split("<tbody>")[1].split("</tbody>")[0]
        assert "Design Grafico" in tbody_conc
        assert "Professor Anterior Concluido" in tbody_conc
        assert "Professora Ativa Vigente" not in tbody_conc

        # Dropdowns cascateados no modo Concluído
        select_p_conc = html_conc.split('id="filtroPeriodo"')[1].split("</select>")[0]
        assert "Semestre Passado" in select_p_conc
        assert "Semestre Atual" not in select_p_conc

        select_prof_conc = html_conc.split('id="filtroProfessor"')[1].split("</select>")[0]
        assert "Professor Anterior Concluido" in select_prof_conc
        assert "Professora Ativa Vigente" not in select_prof_conc

        select_c_conc = html_conc.split('id="filtroCurso"')[1].split("</select>")[0]
        assert "Design Grafico" in select_c_conc
        assert "Python para Dados" not in select_c_conc

        # ── 3. EDIÇÃO DO CURSO VIA MODAL ──
        resp_edit = client.post(
            f"/cursos/{curso1.id}/editar",
            json={
                "nome": "Python Pro",
                "descricao": "Ementa renovada",
            },
        )
        assert resp_edit.status_code == 200
        data_edit = resp_edit.get_json()
        assert data_edit["success"] is True
        assert data_edit["nome"] == "Python Pro"
        assert data_edit["descricao"] == "Ementa renovada"

        curso1_db = db.session.get(Curso, curso1.id)
        assert curso1_db.nome == "Python Pro"

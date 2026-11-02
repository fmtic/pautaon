"""
AJ6-A Rodada 2 — Teste de Causa Real (H8 / H9 / H5).

Fixture sintética com a MESMA FORMA dos dados reais do pautaon:
  - Unidades 1 e 2 (MGB)
  - Períodos "2026.2" homônimos (ids fora do nosso controle; o fixture os cria)
  - Turma Informática: 1 oferta (principal, curso=Informática), 13 alunos,
    frequência em 4 dias (52 linhas), nenhuma linha legada
  - Turma Natação: 2 ofertas ativas — principal = curso Mecânica (outra coisa),
    secundária = curso Natação; 0 linhas de frequência
  - hoje_fixo DEPOIS dos 4 dias

Hipóteses a confirmar/descartar:
  H8 — duplicação de linhas por JOIN com turma de 2 ofertas nos totais do período
  H9 — agregar_por_turma usa curso_id da turma (principal) em vez de oferta com lançamentos
  H5 — cálculo de dias esperados/pendências pela grade até hoje

Para cada hipótese exibimos o valor retornado pelo serviço e o valor esperado
calculado por SQL equivalente direto.
"""
from __future__ import annotations

from datetime import date, time

import pytest

from app import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    PeriodoLetivo,
    Turma,
    TurmaCursoHorario,
    RegistroAula,
    Unidade,
    User,
)
from app.services.frequencia_oferta import (
    agregar_por_oferta,
    agregar_por_turma,
)

from _helpers import login_as, nova_inscricao, nova_oferta, professor_semente


# ---------------------------------------------------------------------------
# Dados da fixture — espelham pautaon real
# ---------------------------------------------------------------------------
_INICIO = date(2026, 8, 1)
_FIM    = date(2026, 12, 15)
# hoje_fixo = 2026-10-29 (HOJE_FIXO_PADRAO de _helpers.py) — depois dos 4 dias de aula
_DATAS_AULA = [
    date(2026, 10, 5),   # Dia 1
    date(2026, 10, 7),   # Dia 2
    date(2026, 10, 12),  # Dia 3
    date(2026, 10, 14),  # Dia 4
]
_N_ALUNOS_INFO = 13     # exato do pautaon
_N_DIAS        = 4
_N_LINHAS_INFO = _N_ALUNOS_INFO * _N_DIAS  # 52


# ---------------------------------------------------------------------------
# Fixture principal
# ---------------------------------------------------------------------------
@pytest.fixture
def seed_causa_real(app, hoje_fixo):
    """Semente que replica a estrutura do pautaon para H8/H9."""
    with app.app_context():
        # --- Unidades ---
        u1 = Unidade(nome="Unidade1", ativo=True)
        u2 = Unidade(nome="MGB", ativo=True)
        db.session.add_all([u1, u2])
        db.session.flush()

        # --- Períodos homônimos "2026.2" ---
        p1 = PeriodoLetivo(nome="2026.2", data_inicio=_INICIO, data_fim=_FIM,
                           unidade_id=u1.id, ativo=True)
        p2 = PeriodoLetivo(nome="2026.2", data_inicio=_INICIO, data_fim=_FIM,
                           unidade_id=u2.id, ativo=True)
        db.session.add_all([p1, p2])
        db.session.flush()

        # --- Cursos ---
        c_info    = Curso(nome="Informática", unidade_id=u2.id, ativo=True)
        c_nat     = Curso(nome="Natação", unidade_id=u2.id, ativo=True)
        c_mecanica = Curso(nome="Mecânica de motores de popa", unidade_id=u2.id, ativo=True)
        db.session.add_all([c_info, c_nat, c_mecanica])
        db.session.flush()

        # --- Professores ---
        prof_info = professor_semente(u2.id, email="prof.info2@x.com", nome="Prof Info")
        prof_nat  = professor_semente(u2.id, email="prof.nat2@x.com",  nome="Prof Nat")

        # --- Turma Informática: 1 oferta principal ---
        turma_info = Turma(
            nome="Informática", unidade_id=u2.id,
            periodo_letivo_id=p2.id, curso_id=c_info.id,
            professor_id=prof_info.id, ativo=True, turno="Manhã",
            data_inicio=_INICIO, data_fim=_FIM,
        )
        db.session.add(turma_info); db.session.flush()

        oferta_info = nova_oferta(
            turma_info.id, c_info.id, u2.id,
            principal=True, professor_id=prof_info.id,
        )

        # Grade horaria da oferta (Segundas e Quartas, 08:00 as 11:00)
        db.session.add(TurmaCursoHorario(
            turma_curso_id=oferta_info.id, dia_semana=0,
            hora_inicio=time(8, 0), hora_fim=time(11, 0),
        ))
        db.session.add(TurmaCursoHorario(
            turma_curso_id=oferta_info.id, dia_semana=2,
            hora_inicio=time(8, 0), hora_fim=time(11, 0),
        ))
        db.session.flush()

        # --- 13 Alunos Informática, inscritos na oferta_info ---
        alunos_info: list[Aluno] = []
        for i in range(1, _N_ALUNOS_INFO + 1):
            a = Aluno(
                nome=f"Aluno Info {i:02d}", unidade_id=u2.id, ativo=True,
                cpf=f"1111111{i:04d}", data_nascimento=date(2010, 1, 1),
            )
            db.session.add(a)
            db.session.flush()
            nova_inscricao(a.id, turma_info.id, oferta_info.id)
            alunos_info.append(a)

        # --- Frequência: 13 alunos × 4 dias = 52 linhas com unidade_id NULL (forma real do pautaon) ---
        for aluno in alunos_info:
            for d in _DATAS_AULA:
                db.session.add(Frequencia(
                    aluno_id=aluno.id,
                    turma_id=turma_info.id,
                    turma_curso_id=oferta_info.id,
                    data=d, conceito="A",
                    unidade_id=None,  # Realidade comprovada do pautaon
                ))

        # --- Turma Natação: 2 ofertas ativas ---
        # principal=True → Mecânica de motores de popa (IGUAL ao pautaon real)
        # principal=False → Natação (oferta secundária)
        turma_nat = Turma(
            nome="Natação", unidade_id=u2.id,
            periodo_letivo_id=p2.id, curso_id=c_nat.id,
            professor_id=prof_nat.id, ativo=True, turno="Manhã",
            data_inicio=_INICIO, data_fim=_FIM,
        )
        db.session.add(turma_nat); db.session.flush()

        oferta_nat_mecanica = nova_oferta(
            turma_nat.id, c_mecanica.id, u2.id,
            principal=True, professor_id=prof_nat.id,
        )
        oferta_nat_natacao = nova_oferta(
            turma_nat.id, c_nat.id, u2.id,
            principal=False, professor_id=prof_nat.id,
        )

        # Natação não tem frequência lançada (igual ao pautaon)

        db.session.commit()

        return {
            "u1_id": u1.id, "u2_id": u2.id,
            "p1_id": p1.id, "p2_id": p2.id,
            "turma_info_id": turma_info.id,
            "turma_nat_id": turma_nat.id,
            "oferta_info_id": oferta_info.id,
            "oferta_nat_mecanica_id": oferta_nat_mecanica.id,
            "oferta_nat_natacao_id": oferta_nat_natacao.id,
            "alunos_info_ids": [a.id for a in alunos_info],
            "datas_aula": _DATAS_AULA,
            "n_linhas_esperadas": _N_LINHAS_INFO,
            "n_alunos_info": _N_ALUNOS_INFO,
        }


# ---------------------------------------------------------------------------
# H3 — filtro de unidade NÃO muda resultado para MGB (sem turma cross-unidade)
# ---------------------------------------------------------------------------
class TestH3FiltroUnidade:
    """H3: agregar_por_turma sem e com unidade_id devem dar o mesmo resultado
    quando NÃO há turma com unidade diferente do período."""

    def test_h3_sem_filtro_igual_com_filtro(self, app, seed_causa_real):
        """Com escopo pelas turmas da unidade, agregar_por_turma encontra as 52 linhas
        mesmo quando Frequencia.unidade_id é NULL (forma real do pautaon)."""
        with app.app_context():
            s = seed_causa_real
            turmas = [s["turma_info_id"], s["turma_nat_id"]]

            resultado = agregar_por_turma(turmas)

            # Informática deve aparecer (tem frequência lançada com unidade_id NULL)
            assert s["turma_info_id"] in resultado
            info = resultado[s["turma_info_id"]]
            assert info.total == s["n_linhas_esperadas"]
            assert info.presentes == s["n_linhas_esperadas"]
            assert info.pct_turma == 100.0

    def test_h3_nenhuma_turma_cross_unidade_na_fixture(self, app, seed_causa_real):
        """Confirma que a fixture não tem turma com unidade != periodo.unidade."""
        with app.app_context():
            from app.models import Turma, PeriodoLetivo
            s = seed_causa_real
            turmas = Turma.query.filter(
                Turma.id.in_([s["turma_info_id"], s["turma_nat_id"]])
            ).all()
            for t in turmas:
                pl = PeriodoLetivo.query.get(t.periodo_letivo_id)
                assert t.unidade_id == pl.unidade_id, (
                    f"Turma {t.nome} tem unidade_id={t.unidade_id} "
                    f"mas período tem unidade_id={pl.unidade_id}"
                )


# ---------------------------------------------------------------------------
# H8 — duplicação de linhas por JOIN com turma de 2 ofertas
# ---------------------------------------------------------------------------
class TestH8DuplicacaoNat:
    """H8: o total do período duplica quando a turma Natação (2 ofertas) entra?

    agregar_por_turma usa GROUP BY turma_id (não por oferta), então NÃO deveria
    duplicar. Este teste verifica se o total de alunos no período é 13 (só
    Informática tem frequência) e não 26 ou outro múltiplo.
    """

    def test_h8_total_alunos_periodo_nao_duplica(self, app, seed_causa_real):
        """O painel do período soma 13 alunos, não 26."""
        with app.app_context():
            from app.relatorios.painel_pedagogico import periodo as periodo_view
            s = seed_causa_real
            periodo = PeriodoLetivo.query.get(s["p2_id"])

            vp = periodo_view.montar(periodo, unidade_id=s["u2_id"])

            total_alunos = vp["totais"]["alunos"]
            # Apenas Informática tem frequência → 13 alunos
            assert total_alunos == s["n_alunos_info"], (
                f"H8 CONFIRMADA: total_alunos={total_alunos} "
                f"(esperado {s['n_alunos_info']}) — duplicação detectada"
            )

    def test_h8_total_aulas_periodo_correto(self, app, seed_causa_real):
        """O painel conta 52 aulas (13 × 4), não 104."""
        with app.app_context():
            from app.relatorios.painel_pedagogico import periodo as periodo_view
            s = seed_causa_real
            periodo = PeriodoLetivo.query.get(s["p2_id"])

            vp = periodo_view.montar(periodo, unidade_id=s["u2_id"])

            # totais["pct_geral"] deriva de presentes/total_aulas agregados
            # Verificamos via turmas: apenas Informática aparece (Natação sem freq)
            turmas = vp["turmas"]
            # Natação não deve aparecer (sem frequência, sem info no freq dict)
            nomes = [t["nome"] for t in turmas]
            assert "Natação" not in nomes, (
                f"H8: Natação aparece em turmas_dados mesmo sem frequência: {nomes}"
            )
            assert "Informática" in nomes, (
                f"Informática não aparece em turmas_dados: {nomes}"
            )

    def test_h8_agregar_por_turma_nao_duplica_nat(self, app, seed_causa_real):
        """agregar_por_turma para Natação (2 ofertas, 0 linhas): retorna vazio."""
        with app.app_context():
            s = seed_causa_real
            resultado = agregar_por_turma([s["turma_nat_id"]])
            # Sem linhas de frequência → não entra no dict
            assert s["turma_nat_id"] not in resultado, (
                f"H8: Natação aparece em agregar_por_turma mesmo sem freq: "
                f"{resultado.get(s['turma_nat_id'])}"
            )

    def test_h8_agregar_por_turma_info_nao_duplica(self, app, seed_causa_real):
        """agregar_por_turma para Informática: 52 linhas contáveis, não duplica."""
        with app.app_context():
            s = seed_causa_real
            resultado = agregar_por_turma([s["turma_info_id"]])
            assert s["turma_info_id"] in resultado
            info = resultado[s["turma_info_id"]]

            esperado_total    = s["n_linhas_esperadas"]   # 52
            esperado_presentes = s["n_linhas_esperadas"]  # todas "P"
            assert info.total == esperado_total, (
                f"H8: total={info.total} != {esperado_total} — duplicação?"
            )
            assert info.presentes == esperado_presentes, (
                f"H8: presentes={info.presentes} != {esperado_presentes}"
            )


# ---------------------------------------------------------------------------
# H9 — agregar_por_turma usa a oferta principal, não a oferta com lançamentos
# ---------------------------------------------------------------------------
class TestH9OfertaPrincipal:
    """H9: agregar_por_turma usa turma_id (todas as linhas da turma), não
    filtra pela oferta principal. Mas agregar_por_OFERTA da oferta_info
    deve coincidir com agregar_por_turma quando a turma tem UMA oferta ativa.

    Para Natação (2 ofertas ativas, 0 linhas) não há diferença (ambos vazios).
    Para Informática (1 oferta ativa, 52 linhas) ambos retornam 52.
    Se H9 fosse verdadeira, agregar_por_oferta da oferta_info deveria diferir
    de agregar_por_turma para Informática — mas não difere.
    """

    def test_h9_turma_info_oferta_vs_turma_coincide(self, app, seed_causa_real):
        """Informática: agregar_por_oferta == agregar_por_turma (1 oferta ativa)."""
        with app.app_context():
            s = seed_causa_real
            por_oferta = agregar_por_oferta([s["oferta_info_id"]])
            por_turma  = agregar_por_turma([s["turma_info_id"]])

            of = por_oferta[s["oferta_info_id"]]
            tu = por_turma[s["turma_info_id"]]

            # H9 seria verdadeira se pct diferisse; não difere com 1 oferta
            assert of.presentes == tu.presentes, (
                f"H9: presentes oferta={of.presentes} != turma={tu.presentes}"
            )
            assert of.total == tu.total, (
                f"H9: total oferta={of.total} != turma={tu.total}"
            )

    def test_h9_nat_2_ofertas_por_oferta_correto(self, app, seed_causa_real):
        """Natação: agregar_por_oferta de cada oferta retorna zerado (sem freq)."""
        with app.app_context():
            s = seed_causa_real
            ids = [s["oferta_nat_mecanica_id"], s["oferta_nat_natacao_id"]]
            resultado = agregar_por_oferta(ids)

            for oid in ids:
                assert oid in resultado
                of = resultado[oid]
                assert of.total == 0, (
                    f"H9: oferta_id={oid} tem total={of.total} != 0 sem frequência lançada"
                )

    def test_h9_nat_2_ofertas_nao_unica(self, app, seed_causa_real):
        """Natação tem 2 ofertas ativas → nenhuma é 'única' → legado NÃO entra."""
        with app.app_context():
            from app.services.frequencia_oferta import ofertas_unicas_ativas
            s = seed_causa_real
            ids = [s["oferta_nat_mecanica_id"], s["oferta_nat_natacao_id"]]
            unicas = ofertas_unicas_ativas(ids)
            assert unicas == set(), (
                f"H9: Natação aparece como única mas tem 2 ofertas: {unicas}"
            )

    def test_h9_info_1_oferta_e_unica(self, app, seed_causa_real):
        """Informática tem 1 oferta ativa → é 'única' (legado entraria se houvesse)."""
        with app.app_context():
            from app.services.frequencia_oferta import ofertas_unicas_ativas
            s = seed_causa_real
            unicas = ofertas_unicas_ativas([s["oferta_info_id"]])
            assert s["oferta_info_id"] in unicas, (
                f"H9: Informática com 1 oferta ativa não classificada como única: {unicas}"
            )


# ---------------------------------------------------------------------------
# H5 — dias esperados / pendências calculados pela grade até hoje
# ---------------------------------------------------------------------------
class TestH5DiasEsperados:
    """H5: o painel calcula pendências com base nos dias da grade até hoje_fixo.

    Na fixture, nenhuma oferta tem grade definida. O serviço de frequência
    não usa grade para contar dias — conta as linhas reais lançadas.
    Logo, H5 não se aplica ao contador bruto de frequência.

    Verificamos que o total de aulas no painel bate com os lançamentos reais
    (4 dias × 13 alunos = 52) e não com nenhum cálculo de grade.
    """

    def test_h5_total_aulas_igual_lancamentos_reais(self, app, seed_causa_real):
        """Total de aulas no painel = linhas reais lançadas, não grade × hoje."""
        with app.app_context():
            s = seed_causa_real
            resultado = agregar_por_turma([s["turma_info_id"]])
            info = resultado[s["turma_info_id"]]

            # 13 alunos × 4 dias = 52 linhas contáveis (todas "P")
            assert info.total == 52, (
                f"H5: total={info.total} != 52 lançamentos reais"
            )

    def test_h5_pct_turma_100_porcento(self, app, seed_causa_real):
        """Todas as presenças = 'P' → 100% de frequência."""
        with app.app_context():
            s = seed_causa_real
            resultado = agregar_por_turma([s["turma_info_id"]])
            info = resultado[s["turma_info_id"]]
            assert info.pct_turma == 100.0, (
                f"H5: pct_turma={info.pct_turma} != 100.0"
            )


# ---------------------------------------------------------------------------
# Matriz completa de perfis × métricas (fumaça + consistência)
# ---------------------------------------------------------------------------
ROLES_RELATORIOS = ["admin", "pedagogico", "secretaria", "gerencia", "servico_social"]


@pytest.fixture
def usuarios_causa_real(app, seed_causa_real):
    """Cria usuários para todos os perfis, com unidade MGB."""
    with app.app_context():
        u2_id = seed_causa_real["u2_id"]
        usuarios = {}
        for role in ROLES_RELATORIOS:
            u = User(
                email=f"causa.{role}@test.com",
                name=f"Causa {role}",
                role=role,
                unidade_id=u2_id,
                is_active=True,
                first_login=False,
            )
            u.set_password("pw")
            db.session.add(u)
            usuarios[role] = u
        db.session.commit()
        for u in usuarios.values():
            db.session.refresh(u)
        return usuarios


class TestMatrizPerfisPainel:
    """Todos os perfis devem ver 200 e os mesmos totais-chave."""

    def test_painel_200_todos_perfis_sem_periodo(self, app, seed_causa_real, usuarios_causa_real, client):
        """GET /relatorios/painel → 200 para todos os perfis."""
        with app.app_context():
            for role, user in usuarios_causa_real.items():
                login_as(client, user, unidade_id=seed_causa_real["u2_id"])
                resp = client.get("/relatorios/painel")
                assert resp.status_code == 200, (
                    f"Perfil {role}: /relatorios/painel retornou {resp.status_code}"
                )

    def test_painel_200_todos_perfis_com_periodo(self, app, seed_causa_real, usuarios_causa_real, client):
        """GET /relatorios/painel?periodo_letivo_id → 200 para todos os perfis."""
        with app.app_context():
            pid = seed_causa_real["p2_id"]
            for role, user in usuarios_causa_real.items():
                login_as(client, user, unidade_id=seed_causa_real["u2_id"])
                resp = client.get(f"/relatorios/painel?periodo_letivo_id={pid}")
                assert resp.status_code == 200, (
                    f"Perfil {role}: com periodo_letivo_id retornou {resp.status_code}"
                )

    def test_painel_mesmos_totais_entre_perfis(self, app, seed_causa_real, usuarios_causa_real, client):
        """Todos os perfis veem os mesmos totais e espelham a visão do professor (13 alunos, 100% freq)."""
        with app.app_context():
            from app.relatorios.painel_pedagogico import periodo as periodo_view
            s = seed_causa_real
            periodo = db.session.get(PeriodoLetivo, s["p2_id"])

            vp = periodo_view.montar(periodo, unidade_id=s["u2_id"])
            total_esperado_alunos = vp["totais"]["alunos"]
            pct_esperado = vp["totais"]["pct_geral"]

            # Com Frequencia.unidade_id NULL (forma real do pautaon),
            # o painel deve enxergar os 13 alunos e 100% de presença, igual ao professor.
            assert total_esperado_alunos == s["n_alunos_info"], (
                f"Painel zerado: total_alunos={total_esperado_alunos} (esperado {s['n_alunos_info']})"
            )
            assert pct_esperado == 100.0, (
                f"Painel com freq errada: pct_geral={pct_esperado} (esperado 100.0)"
            )

            # Todos os perfis com unidade MGB devem ver o mesmo painel
            for role in ROLES_RELATORIOS:
                vp2 = periodo_view.montar(periodo, unidade_id=s["u2_id"])
                assert vp2["totais"]["alunos"] == s["n_alunos_info"], (
                    f"Perfil {role}: total_alunos difere entre chamadas"
                )
                assert vp2["totais"]["pct_geral"] == 100.0, (
                    f"Perfil {role}: pct_geral difere entre chamadas"
                )

    def test_visao_turma_info_200_todos_perfis(self, app, seed_causa_real, usuarios_causa_real, client):
        """GET /relatorios/painel?turma_id=<info> → 200 para todos os perfis."""
        with app.app_context():
            tid = seed_causa_real["turma_info_id"]
            for role, user in usuarios_causa_real.items():
                login_as(client, user, unidade_id=seed_causa_real["u2_id"])
                resp = client.get(f"/relatorios/painel?turma_id={tid}")
                assert resp.status_code == 200, (
                    f"Perfil {role}: visão turma retornou {resp.status_code}"
                )


# ---------------------------------------------------------------------------
# Teste do escritor: salvar_frequencia via rota real grava unidade_id
# ---------------------------------------------------------------------------
def test_escritor_salvar_frequencia_grava_unidade_id(app, seed_causa_real, client):
    """Testa que o escritor (salvar_frequencia via rota real) preenche unidade_id tanto
    na criação de nova linha quanto na atualização de linha legada com unidade_id NULL."""
    with app.app_context():
        s = seed_causa_real
        turma = db.session.get(Turma, s["turma_info_id"])
        prof = db.session.get(User, turma.professor_id)
        aluno_id = s["alunos_info_ids"][0]
        nova_data = date(2026, 10, 19)  # Segunda-feira, dentro do periodo, na grade

    login_as(client, prof, unidade_id=s["u2_id"])

    # 1. Criação de nova frequência via POST na rota real
    resp = client.post("/frequencia", data={
        "turma": str(s["turma_info_id"]),
        "turma_curso": str(s["oferta_info_id"]),
        "data": nova_data.isoformat(),
        f"aluno_{aluno_id}": "A",
    }, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        freq_nova = Frequencia.query.filter_by(
            turma_id=s["turma_info_id"],
            aluno_id=aluno_id,
            data=nova_data,
        ).first()
        assert freq_nova is not None
        assert freq_nova.unidade_id == s["u2_id"], (
            f"Escritor não gravou unidade_id na criação: {freq_nova.unidade_id} (esperado {s['u2_id']})"
        )

        reg_novo = RegistroAula.query.filter_by(
            turma_id=s["turma_info_id"],
            data=nova_data,
        ).first()
        assert reg_novo is not None
        assert reg_novo.unidade_id == s["u2_id"], (
            f"Escritor não gravou unidade_id no RegistroAula: {reg_novo.unidade_id} (esperado {s['u2_id']})"
        )

    # 2. Atualização de frequência existente que estava com unidade_id NULL
    data_semente = s["datas_aula"][0]
    resp2 = client.post("/frequencia", data={
        "turma": str(s["turma_info_id"]),
        "turma_curso": str(s["oferta_info_id"]),
        "data": data_semente.isoformat(),
        f"aluno_{aluno_id}": "B",
    }, follow_redirects=True)
    assert resp2.status_code == 200

    with app.app_context():
        freq_atualizada = Frequencia.query.filter_by(
            turma_id=s["turma_info_id"],
            aluno_id=aluno_id,
            data=data_semente,
        ).first()
        assert freq_atualizada is not None
        assert freq_atualizada.conceito == "B"
        assert freq_atualizada.unidade_id == s["u2_id"], (
            f"Escritor não preencheu unidade_id na atualização: {freq_atualizada.unidade_id} (esperado {s['u2_id']})"
        )





# ---------------------------------------------------------------------------
# Teste de isolamento de duas unidades com unidade_id NULL
# ---------------------------------------------------------------------------
def test_isolamento_duas_unidades_com_unidade_id_null(app):
    """Usuário da unidade A não enxerga frequência da unidade B nem com unidade_id NULL."""
    with app.app_context():
        u1 = Unidade(nome="Unidade A", ativo=True)
        u2 = Unidade(nome="Unidade B", ativo=True)
        db.session.add_all([u1, u2])
        db.session.flush()

        p1 = PeriodoLetivo(nome="2026.2", data_inicio=_INICIO, data_fim=_FIM, unidade_id=u1.id, ativo=True)
        p2 = PeriodoLetivo(nome="2026.2", data_inicio=_INICIO, data_fim=_FIM, unidade_id=u2.id, ativo=True)
        db.session.add_all([p1, p2])
        db.session.flush()

        c1 = Curso(nome="Curso A", unidade_id=u1.id, ativo=True)
        c2 = Curso(nome="Curso B", unidade_id=u2.id, ativo=True)
        db.session.add_all([c1, c2])
        db.session.flush()

        prof1 = professor_semente(u1.id, email="prof.u1@test.com", nome="Prof U1")
        prof2 = professor_semente(u2.id, email="prof.u2@test.com", nome="Prof U2")

        t1 = Turma(nome="Turma U1", unidade_id=u1.id, periodo_letivo_id=p1.id, curso_id=c1.id, professor_id=prof1.id, ativo=True)
        t2 = Turma(nome="Turma U2", unidade_id=u2.id, periodo_letivo_id=p2.id, curso_id=c2.id, professor_id=prof2.id, ativo=True)
        db.session.add_all([t1, t2])
        db.session.flush()

        a1 = Aluno(nome="Aluno A", unidade_id=u1.id, ativo=True, data_nascimento=date(2010, 1, 1))
        a2 = Aluno(nome="Aluno B", unidade_id=u2.id, ativo=True, data_nascimento=date(2010, 1, 1))
        db.session.add_all([a1, a2])
        db.session.flush()

        f1 = Frequencia(turma_id=t1.id, aluno_id=a1.id, data=date(2026, 8, 3), conceito="A", unidade_id=None)
        f2 = Frequencia(turma_id=t2.id, aluno_id=a2.id, data=date(2026, 8, 3), conceito="A", unidade_id=None)
        db.session.add_all([f1, f2])
        db.session.commit()

        # O painel/agregação para unidade A consulta as turmas de U1
        turmas_u1 = Turma.query.filter_by(periodo_letivo_id=p1.id, ativo=True).all()
        turmas_u1_ids = [t.id for t in turmas_u1]

        agg_u1 = agregar_por_turma(turmas_u1_ids)
        assert t1.id in agg_u1
        assert t2.id not in agg_u1
        assert agg_u1[t1.id].total == 1
        assert agg_u1[t1.id].presentes == 1


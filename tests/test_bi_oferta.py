"""ETAPA D3b.4a — BI e relatório geral POR OFERTA.

Passo 2 (CARACTERIZAÇÃO) fixou aqui os números do código ANTES da
refatoração (tabela antes/depois em docs/D3b_4a_relatorio.md). Após a
migração do Passo 3, `_ESPERADO` passou a fixar os números NOVOS —
curso/professor pela oferta, faixas pelo serviço único, legado pela regra
D2. Os testes finais (PASSO 5) cobrem as decisões: faixas somando o total
contável, aluno em 2 ofertas, rotas sem 500, isolamento e ausência de N+1.

Cenário (`_seed`):
    - Unidade A: período P1 EM ANDAMENTO com turmas
        * Alfa — 2 ofertas de CURSOS e PROFESSORES diferentes
          (o1=Natação/Prof Um, o2=Xadrez/Prof Dois); colunas legadas da turma
          apontam Natação/Prof Um. Ana inscrita nas DUAS ofertas.
        * Delta — oferta única od (Natação/Prof Dois), colunas legadas da
          turma NULL e frequência LEGADA (turma_curso_id NULL) da Fefa.
        * Zeta — sem nenhuma frequência (Huga).
      e P2 ENCERRADO com Gema (Xadrez/Prof Um, Gui com J… sem J; 6 linhas).
    - Unidade B: P3 em andamento, Bela/Futsal B/Prof Beta com Ivon
      (isolamento entre unidades).
    - Fronteiras de faixa: Beto 90,0 exato; Caia 188A+21F = 89,9521
      (arredonda para 90,0 e, pelo serviço único, entra em hi); Davi 134A+
      45F = 74,9; Ana 75,0; Elza sem frequência contável.
    - AUL-001 QUEBRAVA com unidade+curso/prof/periodo (JOIN duplo de Turma
      em `total_aulas_registradas` = 500 na rota); defect caracterizado no
      Passo 2 e CORRIGIDO na migração — os números estão em `_ESPERADO`.
"""
# ruff: noqa: F811 — fixtures `app`/`client` reaproveitados do harness D5.2.

from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event

from _helpers import nova_inscricao, nova_oferta  # noqa: F401 (padrão do harness)
from test_conselho_oferta import app, client  # noqa: F401 (fixtures)

from app import db
from app.models import (
    Aluno,
    Atendimento,
    ConselhoClasse,
    Curso,
    EnderecoAluno,
    Frequencia,
    Inscricao,
    PerfilDiversidade,
    PerfilSocioeconomico,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    TurmaCurso,
    Unidade,
    User,
)
from app.models.enums import EtapaConselho
from app.services.frequencia_oferta import faixa, percentual
from app.utils.logica import calcular_frequencias_relatorio

from app.relatorios.bi_alunos import (
    alunos_ativos,
    alunos_beneficiarios_programas_sociais,
    alunos_frequencia_75_89,
    alunos_frequencia_90,
    alunos_frequencia_inferior_75,
    alunos_inativos,
    alunos_por_curso,
    alunos_por_faixa_etaria,
    alunos_por_faixa_renda,
    alunos_por_tipo_deficiencia,
    alunos_por_turma,
    alunos_por_unidade,
    alunos_pcd,
    alunos_raca_conselho,
    alunos_sexo,
    aulas_por_curso,
    aulas_por_professor,
    aulas_por_turma,
    desempenho_conselho_por_renda,
    frequencia_critica_por_vulnerabilidade,
    frequencia_media,
    frequencia_por_curso,
    frequencia_por_turma,
    inscricoes_ativas,
    inscricoes_por_curso,
    sem_internet_por_bairro_zona,
    total_aulas_registradas,
    total_atendimentos,
    total_faltas,
    total_faltas_justificadas,
    total_inscricoes,
    total_lancamentos_frequencia,
    total_presencas,
)


# ---------------------------------------------------------------------------
# Semente do cenário (idêntica ao diagnóstico do Passo 2)
# ---------------------------------------------------------------------------

def _seed():
    """Cria o cenário completo e retorna um dict de nomes → objetos/ids."""
    hoje = date.today()
    ua = Unidade(nome="Unidade A", ativo=True)
    ub = Unidade(nome="Unidade B", ativo=True)
    db.session.add_all([ua, ub])
    db.session.flush()

    p1 = PeriodoLetivo(nome="P1 A", data_inicio=hoje - timedelta(days=30),
                       data_fim=hoje + timedelta(days=60),
                       unidade_id=ua.id, ativo=True)
    p2 = PeriodoLetivo(nome="P2 A encerrado", data_inicio=hoje - timedelta(days=400),
                       data_fim=hoje - timedelta(days=100),
                       unidade_id=ua.id, ativo=True)
    p3 = PeriodoLetivo(nome="P3 B", data_inicio=hoje - timedelta(days=30),
                       data_fim=hoje + timedelta(days=60),
                       unidade_id=ub.id, ativo=True)
    db.session.add_all([p1, p2, p3])
    db.session.flush()

    cn = Curso(nome="Natação", unidade_id=ua.id, ativo=True)
    cx = Curso(nome="Xadrez", unidade_id=ua.id, ativo=True)
    cb = Curso(nome="Futsal B", unidade_id=ub.id, ativo=True)
    db.session.add_all([cn, cx, cb])
    db.session.flush()

    prof1 = User(name="Prof Um", email="p1@x.com", role="professor",
                 first_login=False, unidade_id=ua.id)
    prof2 = User(name="Prof Dois", email="p2@x.com", role="professor",
                 first_login=False, unidade_id=ua.id)
    profb = User(name="Prof Beta", email="pb@x.com", role="professor",
                 first_login=False, unidade_id=ub.id)
    db.session.add_all([prof1, prof2, profb])
    db.session.flush()

    def _turma(nome, un, per, curso=None, prof=None, turno="Manhã",
               programa="Padrão"):
        t = Turma(nome=nome, ativo=True, unidade_id=un.id,
                  periodo_letivo_id=per.id,
                  curso_id=curso.id if curso else None,
                  professor_id=prof.id if prof else None,
                  turno=turno, programa=programa,
                  data_inicio=per.data_inicio, data_fim=per.data_fim)
        db.session.add(t)
        db.session.flush()
        return t

    def _oferta(t, curso, prof, principal=True):
        return nova_oferta(
            t.id, curso.id, t.unidade_id,
            principal=principal, professor_id=prof.id,
            turno=t.turno, programa=t.programa,
        )

    alfa = _turma("Alfa", ua, p1, cn, prof1)
    o1 = _oferta(alfa, cn, prof1)
    o2 = _oferta(alfa, cx, prof2, principal=False)
    delta = _turma("Delta", ua, p1, None, None, turno="Tarde", programa="Avulso")
    od = _oferta(delta, cn, prof2)
    gema = _turma("Gema", ua, p2, cx, prof1)
    og = _oferta(gema, cx, prof1)
    zeta = _turma("Zeta", ua, p1, cn, prof2)
    oz = _oferta(zeta, cn, prof1)
    bela = _turma("Bela", ub, p3, cb, profb)
    ob = _oferta(bela, cb, profb)

    def _aluno(nome, un=ua):
        a = Aluno(nome=nome, unidade_id=un.id, ativo=True)
        db.session.add(a)
        db.session.flush()
        return a

    Ana = _aluno("Ana")
    Beto = _aluno("Beto")
    Caia = _aluno("Caia")
    Davi = _aluno("Davi")
    Elza = _aluno("Elza")
    Fefa = _aluno("Fefa")
    Gui = _aluno("Gui")
    Huga = _aluno("Huga")
    Ivon = _aluno("Ivon", ub)

    def _ins(aluno, t, o, inicio=None):
        nova_inscricao(aluno.id, t.id, o.id,
                       data_inicio=inicio or date.today())

    _ins(Ana, alfa, o1)
    _ins(Ana, alfa, o2)
    _ins(Beto, alfa, o1)
    _ins(Caia, alfa, o1)
    _ins(Davi, alfa, o1)
    _ins(Elza, alfa, o1)
    _ins(Fefa, delta, od)
    _ins(Gui, gema, og, inicio=p2.data_inicio)
    _ins(Huga, zeta, oz)
    _ins(Ivon, bela, ob)

    freq_rows = []

    def _freq(aluno, t, o_id, d, c):
        freq_rows.append(Frequencia(aluno_id=aluno.id, turma_id=t.id,
                                    turma_curso_id=o_id, data=d, conceito=c,
                                    unidade_id=t.unidade_id))

    base = hoje - timedelta(days=25)
    # Ana: 75,0 em CADA oferta (3 presenças + 1 falta) e um J no meio (o1).
    for i, (o_id, c) in enumerate([
        (o1.id, "A"), (o1.id, "A"), (o1.id, "J"), (o1.id, "A"), (o1.id, "F"),
        (o2.id, "A"), (o2.id, "A"), (o2.id, "A"), (o2.id, "F"),
    ]):
        _freq(Ana, alfa, o_id, base + timedelta(days=i), c)
    # Beto: 9,0/1,0 → 90,0 exato (hi nas duas regras).
    _freq(Beto, alfa, o1.id, base, "F")
    for i in range(9):
        _freq(Beto, alfa, o1.id, base + timedelta(days=1 + i), "A")
    # Caia: 188A + 21F → 89,9521 → arred. 90,0 (FORA de todas as faixas hoje).
    for i in range(188):
        _freq(Caia, alfa, o1.id, base + timedelta(days=i), "A")
    for i in range(21):
        _freq(Caia, alfa, o1.id, base + timedelta(days=190 + i), "F")
    # Davi: 134A + 45F → 74,8603 → arred. 74,9 (lo nas duas regras).
    for i in range(134):
        _freq(Davi, alfa, o1.id, base + timedelta(days=i), "A")
    for i in range(45):
        _freq(Davi, alfa, o1.id, base + timedelta(days=140 + i), "F")
    # Fefa: linhas LEGADAS (turma_curso_id NULL) em turma de oferta única.
    _freq(Fefa, delta, None, base, "A")
    _freq(Fefa, delta, None, base + timedelta(days=1), "F")
    # Gui: 4A + 2F em período ENCERRADO → 66,7.
    for i in range(4):
        _freq(Gui, gema, og.id, base + timedelta(days=i), "A")
    for i in range(2):
        _freq(Gui, gema, og.id, base + timedelta(days=10 + i), "F")
    # Ivon (unidade B): 2A + 2F → 50,0.
    for i in range(2):
        _freq(Ivon, bela, ob.id, base + timedelta(days=i), "A")
    for i in range(2):
        _freq(Ivon, bela, ob.id, base + timedelta(days=5 + i), "F")
    db.session.add_all(freq_rows)

    reg_rows = []

    def _reg(t, o_id, d, instrutor):
        reg_rows.append(RegistroAula(turma_id=t.id, turma_curso_id=o_id,
                                     data=d, instrutor_id=instrutor.id,
                                     unidade_id=t.unidade_id))

    for i in range(3):
        _reg(alfa, o1.id, base + timedelta(days=i), prof1)
    for i in range(2):
        _reg(alfa, o2.id, base + timedelta(days=i), prof2)
    _reg(alfa, None, base + timedelta(days=10), prof1)   # legado, turma com 2 ofertas
    _reg(delta, None, base, prof2)                       # legado, oferta única
    _reg(delta, None, base + timedelta(days=1), prof2)
    _reg(delta, od.id, base + timedelta(days=2), prof2)
    _reg(gema, og.id, base, prof1)
    _reg(bela, ob.id, base, profb)
    db.session.add_all(reg_rows)

    db.session.add_all([
        PerfilSocioeconomico(aluno_id=Ana.id, unidade_id=ua.id,
                             renda_familiar=Decimal("2000.00"),
                             vulnerabilidade_social=False,
                             beneficio_social_status="Sim"),
        PerfilSocioeconomico(aluno_id=Davi.id, unidade_id=ua.id,
                             renda_familiar=Decimal("1000.00"),
                             vulnerabilidade_social=True,
                             beneficio_social_status="Não"),
        PerfilSocioeconomico(aluno_id=Fefa.id, unidade_id=ua.id,
                             renda_familiar=Decimal("800.00"),
                             vulnerabilidade_social=True,
                             beneficio_social_status="Sim"),
        PerfilSocioeconomico(aluno_id=Gui.id, unidade_id=ua.id,
                             renda_familiar=Decimal("5000.00"),
                             vulnerabilidade_social=False,
                             beneficio_social_status="Não"),
        PerfilDiversidade(aluno_id=Ana.id, unidade_id=ua.id,
                          genero="Feminino", raca_cor="Branca"),
        PerfilDiversidade(aluno_id=Davi.id, unidade_id=ua.id,
                          genero="Masculino", raca_cor="Parda",
                          saude_laudo=True, tipo_deficiencia="Física"),
        PerfilDiversidade(aluno_id=Fefa.id, unidade_id=ua.id, raca_cor="Preta"),
        PerfilDiversidade(aluno_id=Caia.id, unidade_id=ua.id, genero="Feminino"),
        PerfilDiversidade(aluno_id=Beto.id, unidade_id=ua.id, genero="Masculino"),
        EnderecoAluno(aluno_id=Davi.id, unidade_id=ua.id, zona="Rural",
                      bairro="Centro", possui_acesso_internet=False),
        EnderecoAluno(aluno_id=Fefa.id, unidade_id=ua.id, zona="Urbana",
                      bairro="Oeste", possui_acesso_internet=False),
    ])

    db.session.add_all([
        ConselhoClasse(turma_id=alfa.id, aluno_id=Ana.id, turma_curso_id=o1.id,
                       etapa=EtapaConselho.FINAL, situacao_final="Aprovado",
                       unidade_id=ua.id, concluido=True),
        ConselhoClasse(turma_id=alfa.id, aluno_id=Ana.id, turma_curso_id=o2.id,
                       etapa=EtapaConselho.FINAL, situacao_final="Aprovado",
                       unidade_id=ua.id, concluido=True),
        ConselhoClasse(turma_id=alfa.id, aluno_id=Davi.id, turma_curso_id=o1.id,
                       etapa=EtapaConselho.FINAL,
                       situacao_final="Reprovado por Falta",
                       unidade_id=ua.id, concluido=True),
        ConselhoClasse(turma_id=delta.id, aluno_id=Fefa.id, turma_curso_id=od.id,
                       etapa=EtapaConselho.FINAL, situacao_final="Aprovado",
                       unidade_id=ua.id, concluido=True),
    ])

    db.session.add_all([
        Atendimento(aluno_id=Davi.id, data_atendimento=base, resumo="a",
                    dados={}, unidade_id=ua.id),
        Atendimento(aluno_id=Fefa.id, data_atendimento=base, resumo="b",
                    dados={}, unidade_id=ua.id),
    ])
    db.session.commit()

    return dict(
        ua=ua.id, ub=ub.id, p1=p1.id, p2=p2.id, p3=p3.id,
        cn=cn.id, cx=cx.id, cb=cb.id,
        prof1=prof1.id, prof2=prof2.id, profb=profb.id,
        alfa=alfa.id, delta=delta.id, gema=gema.id, zeta=zeta.id, bela=bela.id,
        o1=o1.id, o2=o2.id, od=od.id, og=og.id, oz=oz.id, ob=ob.id,
    )


@pytest.fixture
def cenario(app):
    with app.app_context():
        yield _seed()


# ---------------------------------------------------------------------------
# Coleta dos números do cenário
# ---------------------------------------------------------------------------

def _map(lst):
    return {r["nome"]: r["valor"] for r in lst}


def _u(s, **extra):
    f = {"unidade_id": s["ua"]}
    f.update(extra)
    return f


# ---------------------------------------------------------------------------
# PASSO 2/5 — NÚMEROS ESPERADOS PÓS-MIGRAÇÃO (oferta como fonte de
# curso/professor; faixas pelo serviço; legado pela regra D2). Coletados com
# `tmp_caracteriza_bi.py` após o Passo 3 em 26/10/2026. A tabela
# antes→depois com a causa de cada diferença está em docs/D3b_4a_relatorio.md.
# ---------------------------------------------------------------------------

_ESPERADO = {
    # FRE-001..005 — curso/professor resolvem pela OFERTA (decisão 1); o
    # legado de Delta (turma de oferta única) entra no curso Natação pela
    # regra D2 (decisão 3); a linha legada de Alfa não existe em frequência.
    "FRE001": 415, "FRE001cn": 405, "FRE001cx": 10,
    "FRE001p1": 409, "FRE001p2": 6, "FRE001alfa": 407, "FRE001delta": 2,
    "FRE002": 342, "FRE002cn": 335, "FRE002cx": 7,
    "FRE002p1": 338, "FRE002p2": 4,
    "FRE003": 72, "FRE003cn": 69, "FRE003cx": 3,
    "FRE003p1": 70, "FRE003p2": 2,
    "FRE004": 1, "FRE004cn": 1, "FRE004cx": 0, "FRE004p1": 1, "FRE004p2": 0,
    "FRE005": 82.6, "FRE005cn": 82.9, "FRE005cx": 70.0,
    "FRE005p1": 82.8, "FRE005p2": 66.7,
    # Faixas via serviço (decisão 4): 2+1+3 = 6 = exatamente os alunos com
    # frequência contável na A (Caia 89,9521 → 90,0 arredondado entra em hi).
    "FRE006": 2, "FRE007": 1, "FRE008": 3,
    "FRE006cn": 2, "FRE007cn": 1, "FRE008cn": 2,
    "FRE006cx": 0, "FRE007cx": 1, "FRE008cx": 1,
    # FRE-009: turmas selecionadas pela OFERTA (decisão 1) — Delta entra no
    # curso Natação via oferta única; percentual continua POR TURMA.
    "FREQ009": {"Alfa": 83.0, "Delta": 50.0, "Gema": 66.7, "Zeta": 0.0},
    "FREQ009cn": {"Alfa": 83.0, "Delta": 50.0, "Zeta": 0.0},
    "FREQ009p2": {"Alfa": 83.0, "Delta": 50.0},
    # FRE-010: agregação em lote por curso usando só linhas de oferta +
    # legado D2 (o Xadrez de Ana-o2 entra; 82,9 = 339/410 no total).
    "FREQ010": {"Natação": 82.9, "Xadrez": 70.0},
    "FREQ010p1": {"Natação": 83.1, "Xadrez": 66.7},
    # ALU-002..007 — filtros de vínculo passam pelo `Inscricao.turma_curso_id`
    # (decisão 1): Ana conta em Natação E em Xadrez; Fefa entra em Natação.
    "ALU002": 8, "ALU002cn": 7, "ALU002cx": 2,
    "ALU003": 0, "ALU003cn": 0, "ALU003cx": 0,
    "ALU005": {"Não Informado": 3, "Feminino": 2, "Masculino": 2},
    "ALU005cn": {"Não Informado": 3, "Feminino": 2, "Masculino": 2},
    "ALU005cx": {"Feminino": 1},
    "ALU006cn": {"Não Informado": 7}, "ALU006cx": {"Não Informado": 1},
    "ALU007": 1, "ALU007cn": 1, "ALU007cx": 0,
    # ALU-008 é CADASTRAL (decisão 6 — base mantida; catálogo diz
    # 'Alunos cadastrados por unidade'); só os FILTROS migraram pela oferta.
    "ALU008": {"Unidade A": 8, "Unidade B": 1},
    "ALU008p": {"Unidade A": 7},
    "ALU008cn": {"Unidade A": 7}, "ALU008cx": {"Unidade A": 2},
    "ALU008p1": {"Unidade A": 7},
    # ALU-009 (decisão 2): aluno DISTINTO dentro de cada curso — Ana conta
    # 1 em Natação e 1 em Xadrez (a soma por curso pode exceder os
    # distintos da unidade). ALU-010: 1 vez por turma (Alfa = 5 distintos).
    "ALU009": {"Futsal B": 1, "Natação": 7, "Xadrez": 1},
    "ALU009p": {"Natação": 7, "Xadrez": 1},
    "ALU009p1": {"Natação": 6}, "ALU009p2": {"Natação": 1, "Xadrez": 1},
    "ALU010": {"Alfa": 5, "Bela": 1, "Delta": 1, "Zeta": 1},
    "ALU010cn": {"Alfa": 5, "Delta": 1, "Zeta": 1},
    "ALU010cx": {"Alfa": 1},
    "ALU010p1": {"Alfa": 5, "Zeta": 1},
    # INS — join do curso pela oferta da inscrição (NOT NULL, sem fallback).
    "INS001": 9, "INS001cn": 7, "INS001cx": 2,
    "INS001p1": 7, "INS001p2": 2, "INS001alfa": 6, "INS001delta": 1,
    "INS002cn": 7,
    "INS008": {"Natação": 7, "Xadrez": 2},
    "INS008p1": {"Natação": 6, "Xadrez": 1},
    # AUL-001 — defect do JOIN duplo CORRIGIDO: unidade + curso/prof/periodo
    # não quebra mais; a linha legada de Alfa (2 ofertas) não entra em curso
    # nenhum (6+3 = 10 − 1), e o legado de Delta (oferta única) entra.
    "AUL001": 10, "AUL001cn": 6, "AUL001cx": 3,
    "AUL001p1": 4, "AUL001p2": 5, "AUL001per1": 9,
    "AUL002": {"Alfa": 6, "Delta": 3, "Gema": 1},
    "AUL002cn": {"Alfa": 3, "Delta": 3},
    # AUL-004: professor da OFERTA do registro (instrutor mantido quando o
    # indicador é por instrutor); legados seguem a regra D2.
    "AUL004": {"Prof Dois": 5, "Prof Um": 4},
    "AUL004cn": {"Prof Dois": 3, "Prof Um": 3},
    "AUL005": {"Natação": 6, "Xadrez": 3},
    "AUL005p1": {"Natação": 3, "Xadrez": 1}, "AUL005p2": {"Natação": 3, "Xadrez": 2},
    # SOC/DIV/ATD/CRU — transitivos dos filtros migrados (aplicar_filtros_*).
    "SOC001": {"Não informado": 4, "Até R$ 1.500,00": 2,
               "De R$ 1.500,01 a R$ 3.000,00": 1,
               "De R$ 3.000,01 a R$ 6.000,00": 1, "Acima de R$ 6.000,00": 0},
    "SOC001cx": {"Não informado": 0, "Até R$ 1.500,00": 0,
                 "De R$ 1.500,01 a R$ 3.000,00": 1,
                 "De R$ 3.000,01 a R$ 6.000,00": 1, "Acima de R$ 6.000,00": 0},
    "SOC002": 2, "SOC002cx": 1,
    "DIV001": {"Física": 1},
    "ATD001": 2, "ATD001cx": 0, "ATD001p2": 1,
    "CRU001": {"Vulnerável (Sim)": 2, "Não Vulnerável (Não)": 1},
    "CRU001cn": {"Vulnerável (Sim)": 2, "Não Vulnerável (Não)": 0},
    "CRU001cx": {"Vulnerável (Sim)": 0, "Não Vulnerável (Não)": 1},
    "CRU002": {"Branca": 1, "Parda": 1, "Preta": 1},
    "CRU002cx": {"Branca": 1}, "CRU002p2": {"Branca": 1, "Preta": 1},
    "CRU003": {"Rural - Centro": 1, "Urbana - Oeste": 1},
    "CRU003cx": {},
    "CRU005": {"Até R$ 1.500,00 (Aprovados: 1, Outros: 1)": 2,
               "De R$ 1.500,01 a R$ 3.000,00 (Aprovados: 2, Outros: 0)": 2,
               "Acima de R$ 3.000,00 (Aprovados: 0, Outros: 0)": 0,
               "Não informado (Aprovados: 0, Outros: 0)": 0},
    "CRU005cx": {"Até R$ 1.500,00 (Aprovados: 0, Outros: 0)": 0,
                 "De R$ 1.500,01 a R$ 3.000,00 (Aprovados: 1, Outros: 0)": 1,
                 "Acima de R$ 3.000,00 (Aprovados: 0, Outros: 0)": 0,
                 "Não informado (Aprovados: 0, Outros: 0)": 0},
    # Relatório geral (logica.calcular_frequencias_relatorio) — professor
    # agora vem da OFERTA (decisão 1): Prof Dois passa a ter frequência;
    # Turma.programa continua MANTER (fora do escopo, D3b.7 não pega isso).
    "GERAL_geral": 82.6,
    "GERAL_prog": {"Padrão": 82.8, "Avulso": 50.0},
    "GERAL_turma": {"Alfa": 83.0, "Delta": 50.0, "Gema": 66.7, "Zeta": 0.0},
    "GERAL_prof": {"Prof Um": 82.8, "Prof Dois": 66.7},
}


def test_caracterizacao_frequencia(cenario):
    """FRE-001..008 pós-migração (filtros curso/prof resolvem pela oferta)."""
    s = cenario
    assert total_lancamentos_frequencia(**_u(s)) == _ESPERADO["FRE001"]
    assert total_lancamentos_frequencia(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE001cn"]
    assert total_lancamentos_frequencia(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE001cx"]
    assert total_lancamentos_frequencia(**_u(s, professor_id=s["prof1"])) == _ESPERADO["FRE001p1"]
    assert total_lancamentos_frequencia(**_u(s, professor_id=s["prof2"])) == _ESPERADO["FRE001p2"]
    assert total_lancamentos_frequencia(**_u(s, turma_id=s["alfa"])) == _ESPERADO["FRE001alfa"]
    assert total_lancamentos_frequencia(**_u(s, turma_id=s["delta"])) == _ESPERADO["FRE001delta"]

    assert total_presencas(**_u(s)) == _ESPERADO["FRE002"]
    assert total_presencas(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE002cn"]
    assert total_presencas(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE002cx"]
    assert total_presencas(**_u(s, professor_id=s["prof1"])) == _ESPERADO["FRE002p1"]
    assert total_presencas(**_u(s, professor_id=s["prof2"])) == _ESPERADO["FRE002p2"]

    assert total_faltas(**_u(s)) == _ESPERADO["FRE003"]
    assert total_faltas(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE003cn"]
    assert total_faltas(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE003cx"]
    assert total_faltas(**_u(s, professor_id=s["prof1"])) == _ESPERADO["FRE003p1"]
    assert total_faltas(**_u(s, professor_id=s["prof2"])) == _ESPERADO["FRE003p2"]

    assert total_faltas_justificadas(**_u(s)) == _ESPERADO["FRE004"]
    assert total_faltas_justificadas(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE004cn"]
    assert total_faltas_justificadas(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE004cx"]
    assert total_faltas_justificadas(**_u(s, professor_id=s["prof1"])) == _ESPERADO["FRE004p1"]
    assert total_faltas_justificadas(**_u(s, professor_id=s["prof2"])) == _ESPERADO["FRE004p2"]

    assert frequencia_media(**_u(s)) == _ESPERADO["FRE005"]
    assert frequencia_media(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE005cn"]
    assert frequencia_media(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE005cx"]
    assert frequencia_media(**_u(s, professor_id=s["prof1"])) == _ESPERADO["FRE005p1"]
    assert frequencia_media(**_u(s, professor_id=s["prof2"])) == _ESPERADO["FRE005p2"]

    # Faixas via serviço único (decisão 4): 2+1+3 = 6 = TODOS os alunos com
    # frequência contável na unidade A — Caia (89,9521 → 90,0 arredondado)
    # passou a entrar em hi, fechando a brecha caracterizada no Passo 2.
    assert alunos_frequencia_90(**_u(s)) == _ESPERADO["FRE006"]
    assert alunos_frequencia_75_89(**_u(s)) == _ESPERADO["FRE007"]
    assert alunos_frequencia_inferior_75(**_u(s)) == _ESPERADO["FRE008"]
    assert (
        _ESPERADO["FRE006"] + _ESPERADO["FRE007"] + _ESPERADO["FRE008"]
        == 6
    ), "as três faixas devem somar exatamente os alunos com frequência contável"
    assert alunos_frequencia_90(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE006cn"]
    assert alunos_frequencia_75_89(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE007cn"]
    assert alunos_frequencia_inferior_75(**_u(s, curso_id=s["cn"])) == _ESPERADO["FRE008cn"]
    assert alunos_frequencia_90(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE006cx"]
    assert alunos_frequencia_75_89(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE007cx"]
    assert alunos_frequencia_inferior_75(**_u(s, curso_id=s["cx"])) == _ESPERADO["FRE008cx"]


def test_caracterizacao_frequencia_agregada(cenario):
    """FRE-009/010 pós-migração (agregação em lote; turmas/curso pela oferta)."""
    s = cenario
    assert _map(frequencia_por_turma(**_u(s))) == _ESPERADO["FREQ009"]
    assert _map(
        frequencia_por_turma(**_u(s, curso_id=s["cn"]))
    ) == _ESPERADO["FREQ009cn"]
    assert _map(
        frequencia_por_turma(**_u(s, professor_id=s["prof2"]))
    ) == _ESPERADO["FREQ009p2"]
    assert _map(frequencia_por_curso(**_u(s))) == _ESPERADO["FREQ010"]
    assert _map(
        frequencia_por_curso(**_u(s, professor_id=s["prof1"]))
    ) == _ESPERADO["FREQ010p1"]


def test_caracterizacao_alunos(cenario):
    """ALU-002..010 pós-migração (vínculo do aluno pela oferta da inscrição)."""
    s = cenario
    assert alunos_ativos(**_u(s)) == _ESPERADO["ALU002"]
    assert alunos_ativos(**_u(s, curso_id=s["cn"])) == _ESPERADO["ALU002cn"]
    assert alunos_ativos(**_u(s, curso_id=s["cx"])) == _ESPERADO["ALU002cx"]
    assert alunos_inativos(**_u(s)) == _ESPERADO["ALU003"]
    assert alunos_inativos(**_u(s, curso_id=s["cn"])) == _ESPERADO["ALU003cn"]
    assert alunos_inativos(**_u(s, curso_id=s["cx"])) == _ESPERADO["ALU003cx"]

    assert _map(alunos_sexo(**_u(s))) == _ESPERADO["ALU005"]
    assert _map(alunos_sexo(**_u(s, curso_id=s["cn"]))) == _ESPERADO["ALU005cn"]
    assert _map(alunos_sexo(**_u(s, curso_id=s["cx"]))) == _ESPERADO["ALU005cx"]
    assert _map(
        alunos_por_faixa_etaria(**_u(s, curso_id=s["cn"]))
    ) == _ESPERADO["ALU006cn"]
    assert _map(
        alunos_por_faixa_etaria(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["ALU006cx"]
    assert alunos_pcd(**_u(s)) == _ESPERADO["ALU007"]
    assert alunos_pcd(**_u(s, curso_id=s["cn"])) == _ESPERADO["ALU007cn"]
    assert alunos_pcd(**_u(s, curso_id=s["cx"])) == _ESPERADO["ALU007cx"]

    # ALU-008 é CADASTRAL (decisão 6 — base mantida; catálogo: 'Alunos
    # cadastrados por unidade'); com filtro, o vínculo resolve pela OFERTA.
    assert _map(alunos_por_unidade()) == _ESPERADO["ALU008"]
    assert _map(alunos_por_unidade(periodo_letivo_id=s["p1"])) == _ESPERADO["ALU008p"]
    assert _map(alunos_por_unidade(curso_id=s["cn"])) == _ESPERADO["ALU008cn"]
    assert _map(alunos_por_unidade(curso_id=s["cx"])) == _ESPERADO["ALU008cx"]
    assert _map(
        alunos_por_unidade(professor_id=s["prof1"])
    ) == _ESPERADO["ALU008p1"]

    # ALU-009/010 pós-migração: curso pela OFERTA da inscrição (Ana conta 1
    # em Natação e 1 em Xadrez; Fefa entra em Natação via od).
    assert _map(alunos_por_curso()) == _ESPERADO["ALU009"]
    assert _map(alunos_por_curso(periodo_letivo_id=s["p1"])) == _ESPERADO["ALU009p"]
    assert _map(
        alunos_por_curso(professor_id=s["prof1"])
    ) == _ESPERADO["ALU009p1"]
    assert _map(alunos_por_curso(professor_id=s["prof2"])) == _ESPERADO["ALU009p2"]
    assert _map(alunos_por_turma()) == _ESPERADO["ALU010"]
    assert _map(alunos_por_turma(curso_id=s["cn"])) == _ESPERADO["ALU010cn"]
    assert _map(alunos_por_turma(curso_id=s["cx"])) == _ESPERADO["ALU010cx"]
    assert _map(
        alunos_por_turma(professor_id=s["prof1"])
    ) == _ESPERADO["ALU010p1"]


def test_caracterizacao_inscricoes(cenario):
    """INS-001/002/008 pós-migração (filtro de curso pela oferta da inscrição)."""
    s = cenario
    assert total_inscricoes(**_u(s)) == _ESPERADO["INS001"]
    assert total_inscricoes(**_u(s, curso_id=s["cn"])) == _ESPERADO["INS001cn"]
    assert total_inscricoes(**_u(s, curso_id=s["cx"])) == _ESPERADO["INS001cx"]
    assert total_inscricoes(**_u(s, professor_id=s["prof1"])) == _ESPERADO["INS001p1"]
    assert total_inscricoes(**_u(s, professor_id=s["prof2"])) == _ESPERADO["INS001p2"]
    assert total_inscricoes(**_u(s, turma_id=s["alfa"])) == _ESPERADO["INS001alfa"]
    assert total_inscricoes(**_u(s, turma_id=s["delta"])) == _ESPERADO["INS001delta"]
    assert inscricoes_ativas(**_u(s, curso_id=s["cn"])) == _ESPERADO["INS002cn"]
    assert _map(inscricoes_por_curso(**_u(s))) == _ESPERADO["INS008"]
    assert _map(
        inscricoes_por_curso(**_u(s, professor_id=s["prof1"]))
    ) == _ESPERADO["INS008p1"]


def test_caracterizacao_aulas(cenario):
    """AUL-001..005 pós-migração — defect do JOIN duplo corrigido.

    O código ANTERIOR quebrava com unidade + curso/professor/período
    (`OperationalError` = 500 na rota do BI); a correção usa UM join de
    `Turma` e curso/professor pela oferta do registro (decisões 1/3).
    """
    s = cenario
    assert total_aulas_registradas(**_u(s)) == _ESPERADO["AUL001"]
    assert total_aulas_registradas(**_u(s, turma_id=s["alfa"])) == 6
    assert total_aulas_registradas(**_u(s, turma_id=s["delta"])) == 3
    # Antes OperationalError (= 500); agora retornam números normalmente:
    assert total_aulas_registradas(
        **_u(s, curso_id=s["cn"])
    ) == _ESPERADO["AUL001cn"]
    assert total_aulas_registradas(
        **_u(s, curso_id=s["cx"])
    ) == _ESPERADO["AUL001cx"]
    assert total_aulas_registradas(
        **_u(s, professor_id=s["prof1"])
    ) == _ESPERADO["AUL001p1"]
    assert total_aulas_registradas(
        **_u(s, professor_id=s["prof2"])
    ) == _ESPERADO["AUL001p2"]
    assert total_aulas_registradas(
        **_u(s, periodo_letivo_id=s["p1"])
    ) == _ESPERADO["AUL001per1"]

    assert _map(aulas_por_turma(**_u(s))) == _ESPERADO["AUL002"]
    assert _map(aulas_por_turma(**_u(s, curso_id=s["cn"]))) == _ESPERADO["AUL002cn"]
    assert _map(aulas_por_professor(**_u(s))) == _ESPERADO["AUL004"]
    assert _map(
        aulas_por_professor(**_u(s, curso_id=s["cn"]))
    ) == _ESPERADO["AUL004cn"]
    assert _map(aulas_por_curso(**_u(s))) == _ESPERADO["AUL005"]
    assert _map(
        aulas_por_curso(**_u(s, professor_id=s["prof1"]))
    ) == _ESPERADO["AUL005p1"]
    assert _map(
        aulas_por_curso(**_u(s, professor_id=s["prof2"]))
    ) == _ESPERADO["AUL005p2"]


def test_caracterizacao_sociais_cruzados(cenario):
    """SOC/DIV/ATD/CRU pós-migração (transitivos dos filtros por oferta)."""
    s = cenario
    assert _map(alunos_por_faixa_renda(**_u(s))) == _ESPERADO["SOC001"]
    assert _map(
        alunos_por_faixa_renda(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["SOC001cx"]
    assert alunos_beneficiarios_programas_sociais(**_u(s)) == _ESPERADO["SOC002"]
    assert alunos_beneficiarios_programas_sociais(
        **_u(s, curso_id=s["cx"])
    ) == _ESPERADO["SOC002cx"]
    assert _map(alunos_por_tipo_deficiencia(**_u(s))) == _ESPERADO["DIV001"]
    assert total_atendimentos(**_u(s)) == _ESPERADO["ATD001"]
    assert total_atendimentos(**_u(s, curso_id=s["cx"])) == _ESPERADO["ATD001cx"]
    assert total_atendimentos(**_u(s, professor_id=s["prof2"])) == _ESPERADO["ATD001p2"]
    assert _map(
        frequencia_critica_por_vulnerabilidade(**_u(s))
    ) == _ESPERADO["CRU001"]
    assert _map(
        frequencia_critica_por_vulnerabilidade(**_u(s, curso_id=s["cn"]))
    ) == _ESPERADO["CRU001cn"]
    assert _map(
        frequencia_critica_por_vulnerabilidade(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["CRU001cx"]
    assert _map(alunos_raca_conselho(**_u(s))) == _ESPERADO["CRU002"]
    assert _map(
        alunos_raca_conselho(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["CRU002cx"]
    assert _map(
        alunos_raca_conselho(**_u(s, professor_id=s["prof2"]))
    ) == _ESPERADO["CRU002p2"]
    assert _map(sem_internet_por_bairro_zona(**_u(s))) == _ESPERADO["CRU003"]
    assert _map(
        sem_internet_por_bairro_zona(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["CRU003cx"]
    assert _map(desempenho_conselho_por_renda(**_u(s))) == _ESPERADO["CRU005"]
    assert _map(
        desempenho_conselho_por_renda(**_u(s, curso_id=s["cx"]))
    ) == _ESPERADO["CRU005cx"]


def test_caracterizacao_relatorio_geral(cenario):
    """calcular_frequencias_relatorio pós-migração (professor pela oferta)."""
    s = cenario
    turmas_a = Turma.query.filter_by(unidade_id=s["ua"], ativo=True).all()
    p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(turmas_a, s["ua"])
    assert p_geral == _ESPERADO["GERAL_geral"]
    assert f_prog == _ESPERADO["GERAL_prog"]
    assert f_turma == _ESPERADO["GERAL_turma"]
    assert f_prof == _ESPERADO["GERAL_prof"]


# ---------------------------------------------------------------------------
# PASSO 5 — garantias das decisões 1–4 além dos números caracterizados
# ---------------------------------------------------------------------------

def test_limites_de_faixa_do_servico():
    """Decisão (4): percentual arredondado e faixa sobre o valor arredondado.

    Fronteiras do protocolo: 89,96 (→90,0 e entra em hi), 90,0, 75,0, 74,9.
    """
    assert percentual(188, 21) == 90.0     # Caia: 89,9521 → 90,0
    assert percentual(9, 1) == 90.0        # Beto: hi exato
    assert percentual(3, 1) == 75.0        # Ana: mid (>= 75)
    assert percentual(134, 45) == 74.9     # Davi: lo (< 75)
    assert faixa(90.0) == "hi"
    assert faixa(89.96) == "hi"           # 89,96 → 90,0 (o serviço fecha a
                                          # brecha arredondando antes)
    assert faixa(75.0) == "mid"
    assert faixa(74.9) == "lo"


def test_faixas_somam_contaveis_por_escopo(cenario):
    """Decisão (4): hi+mid+lo = alunos com frequência contável (6 na A;
    5 em Natação — Ana/Beto/Caia/Davi/Fefa; 2 em Xadrez — Ana/Gui)."""
    s = cenario
    assert (
        alunos_frequencia_90(**_u(s))
        + alunos_frequencia_75_89(**_u(s))
        + alunos_frequencia_inferior_75(**_u(s))
        == 6
    )
    assert (
        alunos_frequencia_90(**_u(s, curso_id=s["cn"]))
        + alunos_frequencia_75_89(**_u(s, curso_id=s["cn"]))
        + alunos_frequencia_inferior_75(**_u(s, curso_id=s["cn"]))
        == 5
    )
    assert (
        alunos_frequencia_90(**_u(s, curso_id=s["cx"]))
        + alunos_frequencia_75_89(**_u(s, curso_id=s["cx"]))
        + alunos_frequencia_inferior_75(**_u(s, curso_id=s["cx"]))
        == 2
    )


def test_aluno_em_duas_ofertas(cenario):
    """Decisões (1)/(2): Ana (2 ofertas) conta 1× por curso no ALU-009 e
    1× pela turma no ALU-010; o filtro de curso devolve só a oferta pedida."""
    s = cenario
    por_curso = _map(alunos_por_curso())
    assert por_curso["Natação"] == 7 and por_curso["Xadrez"] == 1
    assert _map(alunos_por_turma())["Alfa"] == 5  # Ana não conta duas vezes
    assert _map(inscricoes_por_curso(**_u(s))) == {"Natação": 7, "Xadrez": 2}
    # aluno inscrito nas 2 ofertas aparece só no curso filtrado
    assert total_inscricoes(**_u(s, curso_id=s["cx"])) == 2  # Ana + Gui
    assert total_inscricoes(**_u(s, curso_id=s["cn"])) == 7


def test_legado_regra_d2(cenario):
    """Decisão (3): legado entra no curso da ÚNICA oferta ativa da turma."""
    s = cenario
    # Frequência: as 2 linhas legadas de Fefa (Delta, oferta única od) entra
    # no curso Natação — toda linha tem oferta própria ou é atribuível:
    assert (
        total_lancamentos_frequencia(**_u(s, curso_id=s["cn"]))
        + total_lancamentos_frequencia(**_u(s, curso_id=s["cx"]))
        == _ESPERADO["FRE001"]
    )
    assert "Delta" in _map(frequencia_por_turma(**_u(s, curso_id=s["cn"])))
    assert _map(alunos_por_curso())["Natação"] == 7  # Fefa não some do curso
    # Aulas: a linha legada de Alfa (turma com 2 ofertas) NÃO entra em curso
    # nenhum — cn + cx = total − 1.
    assert (
        total_aulas_registradas(**_u(s, curso_id=s["cn"]))
        + total_aulas_registradas(**_u(s, curso_id=s["cx"]))
        == _ESPERADO["AUL001"] - 1
    )


def _login(client, user_id):
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user_id)
        sess["_fresh"] = True


def test_rotas_bi_aceitam_oferta_sem_500(cenario, client):
    """Passo 3d/5: as três rotas aceitam curso_id/turma_id/professor_id e
    jamais devolvem 500 — valor inválido vira None (`type=int`) ou 400."""
    s = cenario
    admin = User(name="BI Admin", email="bi@x.com", role="admin",
                 first_login=False)
    db.session.add(admin)
    db.session.commit()
    _login(client, admin.id)

    urls = [
        f"/relatorios/bi/dados?dimensao=curso&curso_id={s['cn']}",
        f"/relatorios/bi/dados?dimensao=turma&turma_id={s['alfa']}",
        "/relatorios/bi/dados?dimensao=curso&curso_id=abc",
        "/relatorios/bi/dados?dimensao=curso&curso_id=-1",
        f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}&curso_id={s['cn']}",
        f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}&professor_id={s['prof1']}",
        f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}&turma_id=abc",
        f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}&curso_id=999999",
        "/relatorios/bi/indicador/NAO-EXISTE?curso_id=abc",
        f"/relatorios/bi/exportar/xlsx?codigo=FRE-005&unidade_id={s['ua']}&curso_id={s['cx']}",
        f"/relatorios/bi/exportar/xlsx?codigo=FRE-005&unidade_id={s['ua']}&turma_id=abc",
        f"/relatorios/bi/exportar/xlsx?codigo=FRE-005&unidade_id={s['ua']}&professor_id=999999",
    ]
    for url in urls:
        resp = client.get(url)
        assert resp.status_code in (200, 400, 404), (url, resp.status_code)

    # sanidade: o filtro da rota chega ao indicador resolvido pela OFERTA
    r = client.get(
        f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}&curso_id={s['cn']}"
    )
    assert r.status_code == 200
    assert r.get_json()["resultado"] == _ESPERADO["FRE001cn"]


def test_isolamento_unidade_b(cenario, client):
    """Passo 5: papel operacional da unidade B não vê dados da unidade A."""
    s = cenario
    ped_b = User(name="Pedagogo B", email="pedb@x.com", role="pedagogico",
                 first_login=False, unidade_id=s["ub"])
    db.session.add(ped_b)
    db.session.commit()
    _login(client, ped_b.id)

    # Sem pedir unidade, o escopo é forçado para a B: só as 4 linhas do Ivon.
    r = client.get("/relatorios/bi/indicador/FRE-001")
    assert r.status_code == 200
    assert r.get_json()["resultado"] == 4

    # Pedir a unidade A explicitamente → 403 (nunca 500, nunca dados da A).
    r2 = client.get(f"/relatorios/bi/indicador/FRE-001?unidade_id={s['ua']}")
    assert r2.status_code == 403

    # API de gráfico: dimensão turma só conhece a turma Bela.
    r3 = client.get("/relatorios/bi/dados?dimensao=turma")
    assert r3.status_code == 200
    assert r3.get_json()["labels"] == ["Bela"]


def test_sem_n_plus_1_frequencia_agregada(cenario):
    """Passo 5: FRE-009/010 agregam em lote — o nº de consultas NÃO cresce
    com o número de turmas (medido via `before_cursor_execute`)."""
    s = cenario
    chamadas = []

    def _cont(conn, cursor, statement, parameters, context, executemany):
        chamadas.append(statement)

    engine = db.engine
    event.listen(engine, "before_cursor_execute", _cont)
    try:
        del chamadas[:]
        frequencia_por_turma(**_u(s))
        n_turma_1 = len(chamadas)
        del chamadas[:]
        frequencia_por_curso(**_u(s))
        n_curso_1 = len(chamadas)

        # Acréscimo de uma turma+oferta com frequência: em lote o custo é
        # FIXO; o código ANTERIOR (≥1 consulta por turma) cresceria aqui.
        hoje = date.today()
        eta = Turma(nome="Eta", ativo=True, unidade_id=s["ua"],
                    periodo_letivo_id=s["p1"], turno="Noite",
                    programa="Padrão", data_inicio=hoje - timedelta(days=30),
                    data_fim=hoje + timedelta(days=60))
        db.session.add(eta)
        db.session.flush()
        oe = nova_oferta(eta.id, s["cn"], s["ua"], principal=True,
                         professor_id=s["prof1"], turno="Noite",
                         programa="Padrão")
        huga_id = Aluno.query.filter_by(nome="Huga").one().id
        db.session.add_all([
            Frequencia(aluno_id=huga_id, turma_id=eta.id, turma_curso_id=oe.id,
                       data=hoje - timedelta(days=d), conceito="A",
                       unidade_id=s["ua"])
            for d in (1, 2)
        ])
        db.session.commit()

        del chamadas[:]
        frequencia_por_turma(**_u(s))
        n_turma_2 = len(chamadas)
        del chamadas[:]
        frequencia_por_curso(**_u(s))
        n_curso_2 = len(chamadas)
    finally:
        event.remove(engine, "before_cursor_execute", _cont)

    turmas = Turma.query.filter(Turma.unidade_id == s["ua"],
                                Turma.ativo.is_(True)).count()
    assert turmas >= 5, "cenário precisa de várias turmas para a medição"
    # Custo fixo (seleção + agregação em lote do serviço), independente do
    # número de turmas — sem N+1.
    assert n_turma_2 == n_turma_1, (
        f"frequencia_por_turma cresceu {n_turma_1}→{n_turma_2} ao adicionar "
        "turma (N+1)"
    )
    assert n_curso_2 == n_curso_1, (
        f"frequencia_por_curso cresceu {n_curso_1}→{n_curso_2} ao adicionar "
        "turma (N+1)"
    )
    assert n_turma_1 <= 6 and n_curso_1 <= 6, (
        f"contagem absoluta alta: {n_turma_1}/{n_curso_1}"
    )


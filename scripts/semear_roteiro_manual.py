"""Semente do Roteiro de Teste Manual (M1) — cenário rotulado em banco de ENSAIO.

Cria (ou atualiza) um cenário mínimo, **idempotente** e marcado com o rótulo
``[ROTEIRO]`` para o roteiro ``docs/Roteiro_Teste_Manual.md``:

  - 1 unidade principal (+ 1 unidade vizinha, para os casos de isolamento);
  - 5 perfis com senha conhecida (impressa ao final): admin, gerência,
    pedagógico, secretaria e professor;
  - 1 período vigente e 1 encerrado;
  - cursos/programas, centro de custo, temas e perguntas de conselho;
  - **Turma A** — 1 oferta (programa Esporte) + frequência LEGADA
    (``turma_curso_id IS NULL``);
  - **Turma B** — 2 ofertas de programas diferentes, com conceitos diferentes
    por oferta (estatísticas mudam ao trocar de oferta);
  - **Turma C** — grade por dia NÃO uniforme (Seg 08:00–10:00,
    Qua 08:00–11:00, Sex 14:00–15:30);
  - **Turma D** — já excluída logicamente, com uma oferta desativada ANTES
    (marcador L4.1 só com a oferta que estava ativa);
  - aluno transferido e aluno desenturmado;
  - diário de aula e conselho (uma oferta com conselho pendente, outra
    concluída).

Uso (o banco alvo precisa ter "ensaio" no nome — proteção do banco principal):

    python scripts/semear_roteiro_manual.py                 # pautaon_ensaio
    python scripts/semear_roteiro_manual.py --db pautaon_ensaio
    python scripts/semear_roteiro_manual.py --limpar        # remove só o rótulo

A conexão é a do ``.env``/ambiente com o nome do banco trocado
(``make_url(...).set(database=...)``), o mesmo padrão dos demais scripts.

Nada em ``app/`` é alterado por esta semente; ela usa os modelos e dois
serviços de escrita já existentes (``definir_grade`` e o marcador de exclusão
lógica) para que o estado semeado seja idêntico ao produzido pelas telas.
"""
from __future__ import annotations

import argparse
import os
import sys
from calendar import monthrange
from datetime import date, time, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import dotenv_values  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from config import Config  # noqa: E402

ROTULO = "[ROTEIRO]"
DOMINIO = "roteiro.local"
DB_PADRAO = "pautaon_ensaio"

def resolver_senha(args) -> tuple[str, str]:
    """Resolve a senha na ordem: --senha > ROTEIRO_SENHA > gerada.

    Retorna (senha, origem) onde origem in {'argumento','ambiente','gerada'}.
    """
    import os as _os
    if getattr(args, "senha", None):
        return args.senha, "argumento"
    env = _os.getenv("ROTEIRO_SENHA")
    if env:
        return env, "ambiente"
    from app.services.auth_service import generate_secure_random_password
    return generate_secure_random_password(16), "gerada"

#: códigos de cor/turno usados pelas telas
TURNO_MANHA = "Manhã"
TURNO_TARDE = "Tarde"


# ---------------------------------------------------------------------------
# Conexão / app
# ---------------------------------------------------------------------------

def _dsn(nome_banco: str) -> str:
    """DSN do banco alvo, derivado da conexão do .env (credenciais mantidas)."""
    raw = os.getenv("DATABASE_URL") or dotenv_values(".env").get("DATABASE_URL")
    if not raw:
        raise SystemExit("DATABASE_URL ausente no ambiente e no .env.")
    dsn = make_url(raw).set(database=nome_banco).render_as_string(hide_password=False)
    if "ensaio" not in (make_url(dsn).database or "").lower():
        raise SystemExit(
            f"Semente recusada: o banco '{make_url(dsn).database}' não contém "
            "'ensaio'. Esta semente só roda em banco de ensaio (scratch)."
        )
    return dsn


def _criar_app(dsn: str):
    """App apontando para o banco alvo, sem CSRF (não há formulário aqui)."""
    from app import create_app

    class _Cfg(Config):
        SQLALCHEMY_DATABASE_URI = dsn
        WTF_CSRF_ENABLED = False

    return create_app(_Cfg)


# ---------------------------------------------------------------------------
# Utilidades de data e de upsert
# ---------------------------------------------------------------------------

def _mes_deslocado(hoje: date, desloc: int) -> tuple[int, int]:
    ano, mes = hoje.year, hoje.month + desloc
    while mes < 1:
        mes += 12
        ano -= 1
    while mes > 12:
        mes -= 12
        ano += 1
    return ano, mes


def _periodo_vigente(hoje: date) -> tuple[date, date]:
    """Janela de 4 meses (±2) em torno de hoje — sempre vigente e no ano civil."""
    ano_ini, mes_ini = _mes_deslocado(hoje, -2)
    ano_fim, mes_fim = _mes_deslocado(hoje, 2)
    return date(ano_ini, mes_ini, 1), date(ano_fim, mes_fim, monthrange(ano_fim, mes_fim)[1])


def _periodo_encerrado(hoje: date) -> tuple[date, date]:
    """Janela de 6 meses que termina no dia anterior ao início da vigente."""
    inicio_vigente, _ = _periodo_vigente(hoje)
    fim = inicio_vigente - timedelta(days=1)
    ano_ini, mes_ini = _mes_deslocado(fim, -6)
    return date(ano_ini, mes_ini, 1), fim


def _dias_da_semana(inicio: date, fim: date, weekday: int, quantos: int) -> list[date]:
    """Primeiras `quantos` ocorrências do weekday (0=segunda) no intervalo."""
    dias: list[date] = []
    atual = inicio + timedelta(days=(weekday - inicio.weekday()) % 7)
    while atual <= fim and len(dias) < quantos:
        dias.append(atual)
        atual += timedelta(days=7)
    return dias


def _ocorrencias(inicio: date, fim: date) -> dict[int, int]:
    """Nº de ocorrências de cada weekday (0–5) entre início e fim, inclusive."""
    contagem = {dia: 0 for dia in range(6)}
    atual = inicio
    while atual <= fim:
        if atual.weekday() <= 5:
            contagem[atual.weekday()] += 1
        atual += timedelta(days=1)
    return contagem


def _um(model, **filtro):
    from app.database import db

    return db.session.execute(db.select(model).filter_by(**filtro)).scalars().first()


def _upsert(model, *, criar_com: dict, atualizar: dict | None = None, **filtro):
    """Busca por `filtro`; cria com `criar_com` ou atualiza os campos dados.

    Na criação valem `atualizar` + `criar_com` (o segundo tem precedência), de
    modo que a semente possa descrever o estado desejado uma única vez.
    """
    from app.database import db

    obj = _um(model, **filtro)
    if obj is None:
        campos = {**(atualizar or {}), **criar_com}
        obj = model(**filtro, **campos)
        db.session.add(obj)
        db.session.flush()
        return obj, True
    for campo, valor in (atualizar or {}).items():
        setattr(obj, campo, valor)
    db.session.flush()
    return obj, False


# ---------------------------------------------------------------------------
# Semente
# ---------------------------------------------------------------------------

def _semear(hoje: date) -> dict:
    from app.database import db
    from app.models import (
        Aluno,
        CentroCusto,
        ConselhoClasse,
        ConselhoResposta,
        Curso,
        Frequencia,
        Inscricao,
        OpcaoProximaTurma,
        PerguntaConselho,
        PeriodoLetivo,
        RegistroAula,
        TemaAula,
        Transferencia,
        Turma,
        TurmaCurso,
        Unidade,
        User,
    )
    from app.models.enums import EtapaConselho, TipoPergunta
    from app.services.turma_curso import (
        MOTIVO_TURMA_DESATIVADA,
        desativar_oferta,
        gravar_marcador_exclusao,
        marcador_exclusao_turma,
        sincronizar_programa_turma,
    )
    from app.services.turma_curso_horario import definir_grade

    # ---- unidades -------------------------------------------------------
    unidade, _ = _upsert(
        Unidade,
        criar_com={"ativo": True},
        atualizar={"ativo": True},
        nome=f"{ROTULO} Unidade Central",
    )
    vizinha, _ = _upsert(
        Unidade,
        criar_com={"ativo": True},
        atualizar={"ativo": True},
        nome=f"{ROTULO} Unidade Vizinha",
    )

    # ---- usuários (5 perfis) --------------------------------------------
    def _usuario(perfil: str, papel: str, unidade_id):
        usuario, _ = _upsert(
            User,
            criar_com={
                "name": f"{ROTULO} {perfil}",
                "role": papel,
                "is_active": True,
                "first_login": False,
                "unidade_id": unidade_id,
            },
            atualizar={
                "name": f"{ROTULO} {perfil}",
                "role": papel,
                "is_active": True,
                "first_login": False,
                "unidade_id": unidade_id,
            },
            email=f"{perfil.lower()}.m1@{DOMINIO}",
        )
        usuario.set_password(senha)
        db.session.flush()
        return usuario

    admin = _usuario("Admin", "admin", None)
    gerencia = _usuario("Gerencia", "gerencia", None)
    pedagogico = _usuario("Pedagogico", "pedagogico", unidade.id)
    secretaria = _usuario("Secretaria", "secretaria", unidade.id)
    professor = _usuario("Professor", "professor", unidade.id)
    db.session.commit()

    # ---- períodos -------------------------------------------------------
    ini_vig, fim_vig = _periodo_vigente(hoje)
    ini_enc, fim_enc = _periodo_encerrado(hoje)
    periodo_vig, _ = _upsert(
        PeriodoLetivo,
        criar_com={},
        atualizar={
            "data_inicio": ini_vig, "data_fim": fim_vig,
            "unidade_id": unidade.id, "ativo": True,
        },
        nome=f"{ROTULO} Periodo Vigente",
    )
    periodo_enc, _ = _upsert(
        PeriodoLetivo,
        criar_com={},
        atualizar={
            "data_inicio": ini_enc, "data_fim": fim_enc,
            "unidade_id": unidade.id, "ativo": True,
        },
        nome=f"{ROTULO} Periodo Encerrado",
    )
    periodo_viz, _ = _upsert(
        PeriodoLetivo,
        criar_com={},
        atualizar={
            "data_inicio": ini_vig, "data_fim": fim_vig,
            "unidade_id": vizinha.id, "ativo": True,
        },
        nome=f"{ROTULO} Periodo Vizinha",
    )

    # ---- catálogos ------------------------------------------------------
    centro, _ = _upsert(
        CentroCusto,
        criar_com={"ativo": True},
        atualizar={"ativo": True},
        nome=f"{ROTULO} Centro Padrao", unidade_id=unidade.id,
    )

    def _curso(nome: str, unidade_id=unidade.id):
        return _upsert(
            Curso,
            criar_com={"ativo": True, "descricao": f"{ROTULO} curso de teste"},
            atualizar={"ativo": True},
            nome=f"{ROTULO} {nome}", unidade_id=unidade_id,
        )[0]

    curso_natacao = _curso("Curso Natacao")
    curso_info = _curso("Curso Informatica")
    curso_horta = _curso("Curso Horta")
    curso_vizinho = _curso("Curso Vizinha", unidade_id=vizinha.id)

    tema_natacao, _ = _upsert(
        TemaAula,
        criar_com={"ativo": True, "unidade_id": unidade.id, "ordem": 1},
        atualizar={"ativo": True, "ordem": 1},
        titulo=f"{ROTULO} Tema Respiracao", curso_id=curso_natacao.id,
    )
    tema_info, _ = _upsert(
        TemaAula,
        criar_com={"ativo": True, "unidade_id": unidade.id, "ordem": 1},
        atualizar={"ativo": True, "ordem": 1},
        titulo=f"{ROTULO} Tema Planilhas", curso_id=curso_info.id,
    )
    tema_horta, _ = _upsert(
        TemaAula,
        criar_com={"ativo": True, "unidade_id": unidade.id, "ordem": 1},
        atualizar={"ativo": True, "ordem": 1},
        titulo=f"{ROTULO} Tema Compostagem", curso_id=curso_horta.id,
    )

    for nome in ("Aprovado para a proxima etapa", "Egresso"):
        _upsert(
            OpcaoProximaTurma,
            criar_com={"ativo": True},
            atualizar={"ativo": True},
            nome=f"{ROTULO} {nome}",
        )

    perguntas = {}
    for chave, etapa, tipo, texto, opcoes in (
        ("grupo", EtapaConselho.INICIAL, TipoPergunta.TURMA,
         "Como esta o grupo neste inicio?", "Bom | Regular | Ruim"),
        ("participacao", EtapaConselho.INICIAL, TipoPergunta.TURMA,
         "Participacao coletiva nas atividades", "Alta | Media | Baixa"),
        ("frequencia", EtapaConselho.INICIAL, TipoPergunta.ALUNO,
         "Frequencia do aluno no inicio", "Suficiente | Insuficiente"),
        ("socializacao", EtapaConselho.INICIAL, TipoPergunta.ALUNO,
         "Socializacao com o grupo", "Boa | Regular | Dificuldade"),
        ("parecer", EtapaConselho.FINAL, TipoPergunta.ALUNO,
         "Parecer final do aluno", "Aprovado | Reprovado | Desistente"),
    ):
        perguntas[chave], _ = _upsert(
            PerguntaConselho,
            criar_com={},
            atualizar={"etapa": etapa, "tipo": tipo, "opcoes": opcoes, "ativo": True},
            texto=f"{ROTULO} {texto}",
        )

    # ---- turmas ---------------------------------------------------------
    def _turma(nome, *, periodo, ativo=True, programa=None, curso_id=None,
               professor_id=None, turno=TURNO_MANHA, unidade_id=unidade.id,
               datas=None):
        inicio, fim = datas or (periodo.data_inicio, periodo.data_fim)
        campos = {
            "ativo": ativo, "programa": programa, "curso_id": curso_id,
            "professor_id": professor_id, "turno": turno, "unidade_id": unidade_id,
            "data_inicio": inicio, "data_fim": fim,
            "periodo_letivo_id": periodo.id, "centro_custo": centro.nome,
        }
        return _upsert(Turma, criar_com=campos, atualizar=campos, nome=f"{ROTULO} {nome}")[0]

    def _oferta(turma, curso, *, programa, principal=False, ativo=True,
                grade=None, turno=TURNO_MANHA, professor_id=None):
        campos = {
            "programa": programa, "principal": principal, "ativo": ativo,
            "turno": turno, "professor_id": professor_id, "unidade_id": turma.unidade_id,
            "data_inicio": turma.data_inicio, "data_fim": turma.data_fim,
            "centro_custo": turma.centro_custo,
        }
        oferta, _ = _upsert(
            TurmaCurso, criar_com=campos, atualizar=campos,
            turma_id=turma.id, curso_id=curso.id,
        )
        if grade:
            definir_grade(oferta, grade)
        return oferta

    # Turma A — oferta única (programa Esporte) + legado NULL
    turma_a = _turma(
        "Turma A - Oferta Unica", periodo=periodo_vig, programa="Esporte",
        curso_id=curso_natacao.id, professor_id=professor.id,
    )
    oferta_a = _oferta(
        turma_a, curso_natacao, programa="Esporte", professor_id=professor.id,
        grade=[(dia, time(8, 0), time(10, 0)) for dia in (0, 2)],
    )
    sincronizar_programa_turma(turma_a)

    # Turma B — DOIS cursos (programas diferentes) e grade em dias distintos
    turma_b = _turma(
        "Turma B - Dois Cursos", periodo=periodo_vig, programa=None,
        curso_id=None, professor_id=professor.id, turno=TURNO_TARDE,
    )
    oferta_b1 = _oferta(
        turma_b, curso_info, programa="Profissionalizante", principal=True,
        grade=[(0, time(14, 0), time(16, 0)), (2, time(14, 0), time(16, 0))],
        turno=TURNO_TARDE, professor_id=professor.id,
    )
    oferta_b2 = _oferta(
        turma_b, curso_horta, programa="Meio Ambiente", principal=False,
        grade=[(1, time(14, 0), time(16, 0)), (3, time(14, 0), time(16, 0))],
        turno=TURNO_TARDE, professor_id=professor.id,
    )
    sincronizar_programa_turma(turma_b)

    # Turma C — grade por dia NÃO uniforme
    turma_c = _turma(
        "Turma C - Grade Variavel", periodo=periodo_vig, programa="Profissionalizante",
        curso_id=curso_info.id, professor_id=professor.id,
    )
    grade_c = [
        (0, time(8, 0), time(10, 0)),   # segunda: 120 min
        (2, time(8, 0), time(11, 0)),   # quarta:  180 min
        (4, time(14, 0), time(15, 30)), # sexta:    90 min
    ]
    oferta_c = _oferta(
        turma_c, curso_info, programa="Profissionalizante",
        professor_id=professor.id, grade=grade_c,
    )
    sincronizar_programa_turma(turma_c)

    # Turma D — excluída logicamente, com oferta desativada ANTES
    turma_d = _turma(
        "Turma D - Excluida (lixeira)", periodo=periodo_enc, programa="Profissionalizante",
        curso_id=None, professor_id=professor.id, ativo=True,
    )
    oferta_d1 = _oferta(
        turma_d, curso_info, programa="Profissionalizante", principal=True,
        professor_id=professor.id,
        grade=[(0, time(8, 0), time(10, 0))],
    )
    oferta_d2 = _oferta(
        turma_d, curso_horta, programa="Meio Ambiente", principal=False,
        professor_id=professor.id,
        grade=[(1, time(8, 0), time(10, 0))],
    )

    # Turma da unidade vizinha (isolamento)
    turma_viz = _turma(
        "Turma Vizinha - Oferta Unica", periodo=periodo_viz, programa="Outros",
        curso_id=curso_vizinho.id, unidade_id=vizinha.id,
        datas=(ini_vig, fim_vig),
    )
    oferta_viz = _oferta(
        turma_viz, curso_vizinho, programa="Outros",
        grade=[(0, time(8, 0), time(10, 0))],
    )
    sincronizar_programa_turma(turma_viz)

    # ---- alunos ---------------------------------------------------------
    def _aluno(nome, *, ativo=True, unidade_id=unidade.id, nascimento=None):
        campos = {"ativo": ativo, "unidade_id": unidade_id}
        if nascimento:
            campos["data_nascimento"] = nascimento
        return _upsert(Aluno, criar_com=campos, atualizar=campos, nome=f"{ROTULO} {nome}")[0]

    alunos = {}
    for nome, nascimento in (
        ("Ana A1", date(2012, 3, 4)),
        ("Bruno A2", date(2011, 7, 19)),
        ("Carla B1", date(2010, 1, 8)),
        ("Diego B2", date(2012, 11, 2)),
        ("Elisa C1", date(2011, 5, 23)),
        ("Fabio C2", date(2010, 9, 14)),
        ("Gabriela Transf", date(2011, 2, 27)),
        ("Heitor Desent", date(2012, 8, 6)),
        ("Inacia D-ativa", date(2010, 12, 1)),
    ):
        alunos[nome] = _aluno(nome, nascimento=nascimento)
    # aluno INATIVO: é o conflito da reativação na lixeira (L4)
    alunos["Joao D-inativo"] = _aluno("Joao D-inativo", ativo=False)
    aluno_viz = _aluno("Aluno Vizinha", unidade_id=vizinha.id)

    # ---- inscrições -----------------------------------------------------
    def _inscricao(aluno, turma, oferta, *, ativo=True, motivo=None,
                   data_desativacao=None, inicio=None):
        filtro = {"aluno_id": aluno.id, "turma_curso_id": oferta.id}
        existentes = db.session.execute(
            db.select(Inscricao).filter_by(**filtro).order_by(Inscricao.id)
        ).scalars().all()
        registro = next((i for i in existentes if i.ativo == ativo), None)
        if registro is None and existentes:
            # Reaproveita a linha do mesmo par (histórico preservado): evita
            # criar uma inscrição nova a cada execução da semente.
            registro = existentes[-1]
        if registro is None:
            registro = Inscricao(
                aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id,
                ativo=ativo, data_inicio=inicio or turma.data_inicio,
                motivo_desativacao=motivo, data_desativacao=data_desativacao,
            )
            db.session.add(registro)
        else:
            registro.turma_id = turma.id
            registro.ativo = ativo
            registro.motivo_desativacao = motivo
            registro.data_desativacao = data_desativacao
            registro.data_inicio = inicio or registro.data_inicio
        db.session.flush()
        return registro

    _inscricao(alunos["Ana A1"], turma_a, oferta_a)
    _inscricao(alunos["Bruno A2"], turma_a, oferta_a)
    # aluno desenturmado (saiu da turma sem transferência)
    _inscricao(
        alunos["Heitor Desent"], turma_a, oferta_a, ativo=False,
        motivo="DESENTURMADO", data_desativacao=db.func.now(),
    )
    # aluno transferido: origem A (inativa) -> destino C (ativa) + registro
    _inscricao(
        alunos["Gabriela Transf"], turma_a, oferta_a, ativo=False,
        motivo="TRANSFERENCIA", data_desativacao=db.func.now(),
    )
    _inscricao(alunos["Gabriela Transf"], turma_c, oferta_c)

    transferencia = db.session.execute(
        db.select(Transferencia).filter_by(aluno_id=alunos["Gabriela Transf"].id)
    ).scalars().first()
    if transferencia is None:
        db.session.add(Transferencia(
            aluno_id=alunos["Gabriela Transf"].id,
            turma_origem_id=turma_a.id, turma_destino_id=turma_c.id,
            observacoes=f"{ROTULO} transferencia semeada", unidade_id=unidade.id,
        ))
        db.session.flush()

    _inscricao(alunos["Carla B1"], turma_b, oferta_b1)
    _inscricao(alunos["Diego B2"], turma_b, oferta_b1)
    _inscricao(alunos["Diego B2"], turma_b, oferta_b2)  # dupla oferta na mesma turma
    _inscricao(alunos["Carla B1"], turma_b, oferta_b2)  # idem, para diferenciar ofertas
    _inscricao(alunos["Elisa C1"], turma_c, oferta_c)
    _inscricao(alunos["Fabio C2"], turma_c, oferta_c)
    _inscricao(alunos["Inacia D-ativa"], turma_d, oferta_d1)
    _inscricao(alunos["Joao D-inativo"], turma_d, oferta_d1, ativo=False, motivo="DESENTURMADO")
    _inscricao(aluno_viz, turma_viz, oferta_viz)

    # ---- frequência / diário -------------------------------------------
    def _frequencia(aluno, turma, oferta_id, dia, conceito):
        filtro = {"aluno_id": aluno.id, "turma_id": turma.id,
                  "turma_curso_id": oferta_id, "data": dia}
        registro = _um(Frequencia, **filtro)
        if registro is None:
            db.session.add(Frequencia(
                aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta_id,
                data=dia, conceito=conceito, unidade_id=turma.unidade_id,
            ))
        else:
            registro.conceito = conceito
        db.session.flush()

    dias_legado = _dias_da_semana(ini_vig, fim_vig, 0, 2)
    # Turma A: só LEGADO (turma_curso_id NULL) — pauta legada intacta
    for dia in dias_legado:
        _frequencia(alunos["Ana A1"], turma_a, None, dia, "A")
        _frequencia(alunos["Bruno A2"], turma_a, None, dia, "F" if dia == dias_legado[0] else "A")

    # B1 tem grade seg/qua e B2 tem grade ter/qui: as aulas são semeadas em
    # datas da própria oferta, para o seletor "Data da Aula" da tela listá-las.
    dias_b1 = _dias_da_semana(ini_vig, fim_vig, 0, 3)  # segundas
    dias_b2 = _dias_da_semana(ini_vig, fim_vig, 1, 2)  # terças
    # Oferta B1: Carla (A, A, F) e Diego (A, F) -> 3 presenças em 5 = 60,0%
    _frequencia(alunos["Carla B1"], turma_b, oferta_b1.id, dias_b1[0], "A")
    _frequencia(alunos["Diego B2"], turma_b, oferta_b1.id, dias_b1[0], "A")
    _frequencia(alunos["Carla B1"], turma_b, oferta_b1.id, dias_b1[1], "A")
    _frequencia(alunos["Diego B2"], turma_b, oferta_b1.id, dias_b1[1], "F")
    _frequencia(alunos["Carla B1"], turma_b, oferta_b1.id, dias_b1[2], "F")
    # Oferta B2: Diego (A) e Carla (F, F) -> 1 presença em 3 = 33,3%
    _frequencia(alunos["Diego B2"], turma_b, oferta_b2.id, dias_b2[0], "A")
    _frequencia(alunos["Carla B1"], turma_b, oferta_b2.id, dias_b2[0], "F")
    _frequencia(alunos["Carla B1"], turma_b, oferta_b2.id, dias_b2[1], "F")

    dias_c = _dias_da_semana(ini_vig, fim_vig, 2, 2)
    _frequencia(alunos["Elisa C1"], turma_c, oferta_c.id, dias_c[0], "A")
    _frequencia(alunos["Fabio C2"], turma_c, oferta_c.id, dias_c[0], "J")
    _frequencia(alunos["Elisa C1"], turma_c, oferta_c.id, dias_c[1], "B")
    _frequencia(alunos["Fabio C2"], turma_c, oferta_c.id, dias_c[1], "F")

    dias_d = _dias_da_semana(ini_enc, fim_enc, 0, 2)
    _frequencia(alunos["Inacia D-ativa"], turma_d, oferta_d1.id, dias_d[0], "A")
    _frequencia(alunos["Inacia D-ativa"], turma_d, oferta_d1.id, dias_d[1], "C")

    def _diario(turma, oferta_id, dia, tema, observacoes):
        registro = _um(RegistroAula, turma_id=turma.id, turma_curso_id=oferta_id, data=dia)
        if registro is None:
            registro = RegistroAula(
                turma_id=turma.id, turma_curso_id=oferta_id, data=dia,
                tema_id=tema.id, observacoes=observacoes,
                instrutor_id=professor.id, unidade_id=turma.unidade_id,
            )
            registro.temas = [tema]
            db.session.add(registro)
        else:
            registro.observacoes = observacoes
            registro.tema_id = tema.id
            registro.temas = [tema]
        db.session.flush()

    _diario(turma_a, None, dias_legado[0], tema_natacao, f"{ROTULO} diario legado A")
    _diario(turma_b, oferta_b1.id, dias_b1[0], tema_info, f"{ROTULO} diario oferta B1")
    _diario(turma_b, oferta_b2.id, dias_b2[0], tema_horta, f"{ROTULO} diario oferta B2")
    _diario(turma_c, oferta_c.id, dias_c[0], tema_info, f"{ROTULO} diario oferta C")

    # ---- conselho -------------------------------------------------------
    def _conselho(turma, oferta, aluno, etapa, *, concluido, respostas=(),
                  parecer=None):
        filtro = {"turma_curso_id": oferta.id, "aluno_id": aluno.id, "etapa": etapa}
        conselho = _um(ConselhoClasse, **filtro)
        if conselho is None:
            conselho = ConselhoClasse(
                **filtro, turma_id=turma.id, concluido=concluido,
                unidade_id=turma.unidade_id, data_inicio=turma.data_inicio,
                data_fim=turma.data_fim, observacao=parecer,
            )
            db.session.add(conselho)
            db.session.flush()
        else:
            conselho.concluido = concluido
            conselho.observacao = parecer
        for chave, resposta in respostas:
            pergunta = perguntas[chave]
            existente = _um(ConselhoResposta, conselho_id=conselho.id,
                            aluno_id=aluno.id, pergunta_id=pergunta.id)
            if existente is None:
                db.session.add(ConselhoResposta(
                    conselho_id=conselho.id, aluno_id=aluno.id,
                    pergunta_id=pergunta.id, resposta=resposta,
                    unidade_id=turma.unidade_id,
                ))
            else:
                existente.resposta = resposta
        db.session.flush()
        return conselho

    # Turma B/oferta B1: conselho INICIAL CONCLUÍDO (painel mostra "concluído")
    for aluno, resposta in ((alunos["Carla B1"], "Suficiente"),
                            (alunos["Diego B2"], "Insuficiente")):
        _conselho(
            turma_b, oferta_b1, aluno, EtapaConselho.INICIAL, concluido=True,
            respostas=(("frequencia", resposta), ("socializacao", "Boa")),
        )
    oferta_b1.conselho_concluido = True
    oferta_b1.avaliacao_inicial = f"{ROTULO} grupo engajado, atencao a frequencia."
    oferta_b1.avaliacao_percurso = None

    # Turma A/oferta A: conselho INICIAL PENDENTE (para lançar/fechar no roteiro)
    _conselho(
        turma_a, oferta_a, alunos["Ana A1"], EtapaConselho.INICIAL, concluido=False,
        respostas=(("frequencia", "Suficiente"),),
    )
    _conselho(
        turma_a, oferta_a, alunos["Bruno A2"], EtapaConselho.INICIAL, concluido=False,
    )
    oferta_a.conselho_concluido = False

    # ---- turma D: exclusão lógica com oferta desativada ANTES -----------
    if oferta_d2.ativo:
        desativar_oferta(oferta_d2, verificar_alunos_em_andamento=False)
    inscricoes_ativas = [
        i.id for i in db.session.execute(
            db.select(Inscricao).filter_by(turma_id=turma_d.id, ativo=True)
        ).scalars()
    ]
    if turma_d.ativo:
        turma_d.ativo = False
        for oferta in (oferta_d1, oferta_d2):
            oferta.ativo = False
        for inscricao in db.session.execute(
            db.select(Inscricao).filter_by(turma_id=turma_d.id, ativo=True)
        ).scalars():
            inscricao.ativo = False
            inscricao.data_desativacao = db.func.now()
            inscricao.motivo_desativacao = MOTIVO_TURMA_DESATIVADA
        db.session.flush()
        if marcador_exclusao_turma(turma_d.id) is None:
            gravar_marcador_exclusao(
                turma_d.id, [oferta_d1.id], inscricoes_ativas,
                usuario_nome=f"{ROTULO} semente", ip="127.0.0.1",
                unidade_id=unidade.id,
            )
        db.session.flush()

    db.session.commit()

    return {
        "unidade": unidade, "vizinha": vizinha,
        "periodo_vig": periodo_vig, "periodo_enc": periodo_enc,
        "turma_a": turma_a, "oferta_a": oferta_a,
        "turma_b": turma_b, "oferta_b1": oferta_b1, "oferta_b2": oferta_b2,
        "turma_c": turma_c, "oferta_c": oferta_c, "grade_c": grade_c,
        "turma_d": turma_d, "oferta_d1": oferta_d1, "oferta_d2": oferta_d2,
        "turma_viz": turma_viz, "oferta_viz": oferta_viz,
        "alunos": alunos, "dias_legado": dias_legado,
        "dias_b1": dias_b1, "dias_b2": dias_b2,
        "dias_c": dias_c, "dias_d": dias_d,
        "usuarios": {
            "admin": admin, "gerencia": gerencia, "pedagogico": pedagogico,
            "secretaria": secretaria, "professor": professor,
        },
        "marcador_turma_d": marcador_exclusao_turma(turma_d.id),
    }


# ---------------------------------------------------------------------------
# Contagens, valores esperados e limpeza
# ---------------------------------------------------------------------------

def _contagens() -> dict:
    from app.database import db
    from app.models import (
        Aluno,
        ConselhoClasse,
        Curso,
        Frequencia,
        Inscricao,
        PerguntaConselho,
        PeriodoLetivo,
        RegistroAula,
        TemaAula,
        Turma,
        TurmaCurso,
        TurmaCursoHorario,
        Unidade,
        User,
    )

    def _n(model, **filtro):
        return db.session.execute(
            db.select(db.func.count(model.id)).filter_by(**filtro)
        ).scalar()

    return {
        "unidades": _n(Unidade),
        "usuarios": _n(User),
        "periodos": _n(PeriodoLetivo),
        "cursos": _n(Curso),
        "temas": _n(TemaAula),
        "turmas": _n(Turma),
        "ofertas": _n(TurmaCurso),
        "grade": _n(TurmaCursoHorario),
        "alunos": _n(Aluno),
        "inscricoes": _n(Inscricao),
        "inscricoes_ativas": _n(Inscricao, ativo=True),
        "frequencias": _n(Frequencia),
        "frequencias_legado": db.session.execute(
            db.select(db.func.count(Frequencia.id)).filter(
                Frequencia.turma_curso_id.is_(None)
            )
        ).scalar(),
        "diarios": _n(RegistroAula),
        "conselhos": _n(ConselhoClasse),
        "perguntas": _n(PerguntaConselho),
    }


def _esperados(dados: dict) -> dict:
    """Valores esperados calculados AQUI (aritmética independente do app)."""
    from app.database import db
    from app.models import Frequencia, Turma
    from app.services.frequencia_oferta import agregar_por_oferta, agregar_por_turma
    from app.services.turma_curso_horario import (
        carga_horaria_total_turma,
        cargas_horarias_ofertas_em_lote,
    )

    def _pct_manual(linhas: list[str]) -> float:
        presenca = {"A", "B", "C", "D"}
        contaveis = [c for c in linhas if c in presenca or c == "F"]
        if not contaveis:
            return 0.0
        return round(100.0 * sum(1 for c in contaveis if c in presenca) / len(contaveis), 1)

    def _conceitos(turma_id, oferta_id="legado") -> list[str]:
        stmt = db.select(Frequencia.conceito).filter(Frequencia.turma_id == turma_id)
        if oferta_id == "legado":
            stmt = stmt.filter(Frequencia.turma_curso_id.is_(None))
        elif oferta_id is not None:
            stmt = stmt.filter(Frequencia.turma_curso_id == oferta_id)
        return [str(c.value if hasattr(c, "value") else c) for c in db.session.execute(stmt).scalars()]

    turma_a, turma_b, turma_c = dados["turma_a"], dados["turma_b"], dados["turma_c"]
    manual = {
        "freq_turma_a_manual": _pct_manual(_conceitos(turma_a.id)),
        "freq_b1_manual": _pct_manual(_conceitos(turma_b.id, dados["oferta_b1"].id)),
        "freq_b2_manual": _pct_manual(_conceitos(turma_b.id, dados["oferta_b2"].id)),
        "freq_turma_b_manual": _pct_manual(_conceitos(turma_b.id, None)),
    }
    app_valores = {
        "freq_turma_a_app": agregar_por_turma([turma_a.id])[turma_a.id].pct_turma,
        "freq_b1_app": agregar_por_oferta([dados["oferta_b1"].id], por_turma=turma_b.id)[dados["oferta_b1"].id].pct,
        "freq_b2_app": agregar_por_oferta([dados["oferta_b2"].id], por_turma=turma_b.id)[dados["oferta_b2"].id].pct,
        "freq_turma_b_app": agregar_por_turma([turma_b.id])[turma_b.id].pct_turma,
    }

    # C.H. da turma C: conta independente (ocorrências × duração do dia)
    ocorrencias = _ocorrencias(turma_c.data_inicio, turma_c.data_fim)
    minutos_por_dia = {
        dia: int((fim.hour * 60 + fim.minute) - (ini.hour * 60 + ini.minute))
        for dia, ini, fim in dados["grade_c"]
    }
    total_manual = sum(ocorrencias[dia] * minutos_por_dia[dia] for dia in minutos_por_dia)
    carga_c = cargas_horarias_ofertas_em_lote([dados["oferta_c"]])[dados["oferta_c"].id]
    app_valores["ch_total_turma_c_app"] = carga_horaria_total_turma(turma_c)
    manual["ch_total_turma_c_manual"] = total_manual
    manual["ch_aula_turma_c_app"] = carga_c.carga_horaria_aula

    # Alunos enturmados (visão por período)
    from app.services.enturmado import contar_alunos_enturmados

    manual["enturmados_periodo_vigente"] = contar_alunos_enturmados(
        periodo_letivo_id=dados["periodo_vig"].id
    )
    manual["turmas_ativas_unidade"] = db.session.execute(
        db.select(db.func.count(Turma.id)).filter_by(
            unidade_id=dados["unidade"].id, ativo=True
        )
    ).scalar()
    return {**manual, **app_valores}


def _contagens_rotulo() -> dict:
    """Contagens SÓ do rótulo — é o que prova a idempotência entre execuções."""
    from app.database import db

    rotulo_like = f"{ROTULO}%"

    def _scalar(sql: str) -> int:
        return db.session.execute(text(sql), {"r": rotulo_like}).scalar()

    return {
        "unidades": _scalar("SELECT count(*) FROM unidade WHERE nome LIKE :r"),
        "usuarios": db.session.execute(
            text('SELECT count(*) FROM "user" WHERE email LIKE :e'),
            {"e": f"%@{DOMINIO}"},
        ).scalar(),
        "periodos": _scalar("SELECT count(*) FROM periodo_letivo WHERE nome LIKE :r"),
        "turmas": _scalar("SELECT count(*) FROM turma WHERE nome LIKE :r"),
        "ofertas": _scalar(
            "SELECT count(*) FROM turma_curso WHERE turma_id IN "
            "(SELECT id FROM turma WHERE nome LIKE :r)"
        ),
        "grade": _scalar(
            "SELECT count(*) FROM turma_curso_horario WHERE turma_curso_id IN "
            "(SELECT tc.id FROM turma_curso tc JOIN turma t ON t.id = tc.turma_id "
            "WHERE t.nome LIKE :r)"
        ),
        "alunos": _scalar("SELECT count(*) FROM aluno WHERE nome LIKE :r"),
        "inscricoes": _scalar(
            "SELECT count(*) FROM inscricoes WHERE turma_id IN "
            "(SELECT id FROM turma WHERE nome LIKE :r)"
        ),
        "frequencias": _scalar(
            "SELECT count(*) FROM frequencia WHERE turma_id IN "
            "(SELECT id FROM turma WHERE nome LIKE :r)"
        ),
        "diarios": _scalar(
            "SELECT count(*) FROM registro_aula WHERE turma_id IN "
            "(SELECT id FROM turma WHERE nome LIKE :r)"
        ),
        "conselhos": _scalar(
            "SELECT count(*) FROM conselho_classe WHERE turma_id IN "
            "(SELECT id FROM turma WHERE nome LIKE :r)"
        ),
        "perguntas": _scalar("SELECT count(*) FROM conselho_pergunta WHERE texto LIKE :r"),
    }


def _limpar() -> int:
    """Remove APENAS os registros com o rótulo (ordem das dependências de FK)."""
    from app.database import db

    rotulo_like = f"{ROTULO}%"
    email_like = f"%@{DOMINIO}"
    turmas = db.session.execute(
        text("SELECT id FROM turma WHERE nome LIKE :r"), {"r": rotulo_like}
    ).scalars().all()
    alunos = db.session.execute(
        text("SELECT id FROM aluno WHERE nome LIKE :r"), {"r": rotulo_like}
    ).scalars().all()
    unidades = db.session.execute(
        text("SELECT id FROM unidade WHERE nome LIKE :r"), {"r": rotulo_like}
    ).scalars().all()
    usuarios = db.session.execute(
        text('SELECT id FROM "user" WHERE email LIKE :e'), {"e": email_like}
    ).scalars().all()

    if turmas:
        ids = ",".join(str(t) for t in turmas)
        conselhos = db.session.execute(
            text(f"SELECT id FROM conselho_classe WHERE turma_id IN ({ids})")
        ).scalars().all()
        if conselhos:
            lista = ",".join(str(c) for c in conselhos)
            db.session.execute(text(f"DELETE FROM conselho_resposta WHERE conselho_id IN ({lista})"))
        for tabela, coluna in (
            ("frequencia", "turma_id"),
            ("registro_aula", "turma_id"),
            ("conselho_classe", "turma_id"),
            ("dia_bloqueado_turma", "turma_id"),
            ("inscricoes", "turma_id"),
        ):
            db.session.execute(text(f"DELETE FROM {tabela} WHERE {coluna} IN ({ids})"))
        db.session.execute(
            text(f"DELETE FROM transferencia WHERE turma_origem_id IN ({ids}) "
                 f"OR turma_destino_id IN ({ids})")
        )
        db.session.execute(
            text("DELETE FROM turma_curso_horario WHERE turma_curso_id IN "
                 f"(SELECT id FROM turma_curso WHERE turma_id IN ({ids}))")
        )
        db.session.execute(text(f"DELETE FROM turma_curso WHERE turma_id IN ({ids})"))
        db.session.execute(text(f"DELETE FROM turma WHERE id IN ({ids})"))
    if alunos:
        lista = ",".join(str(a) for a in alunos)
        db.session.execute(text(f"DELETE FROM inscricoes WHERE aluno_id IN ({lista})"))
        db.session.execute(text(f"DELETE FROM frequencia WHERE aluno_id IN ({lista})"))
        db.session.execute(text(f"DELETE FROM conselho_resposta WHERE aluno_id IN ({lista})"))
        db.session.execute(text(f"DELETE FROM conselho_classe WHERE aluno_id IN ({lista})"))
        db.session.execute(text(f"DELETE FROM transferencia WHERE aluno_id IN ({lista})"))
        db.session.execute(text(f"DELETE FROM aluno WHERE id IN ({lista})"))
    if usuarios:
        lista = ",".join(str(u) for u in usuarios)
        cond_unidade = f"unidade_id IN ({','.join(str(u) for u in unidades)})" if unidades else "FALSE"
        db.session.execute(
            text(f"DELETE FROM log_acao WHERE usuario_id IN ({lista}) OR {cond_unidade}")
        )
    db.session.execute(text("DELETE FROM conselho_pergunta WHERE texto LIKE :r"), {"r": rotulo_like})
    db.session.execute(text("DELETE FROM tema_aula WHERE titulo LIKE :r"), {"r": rotulo_like})
    db.session.execute(text("DELETE FROM curso WHERE nome LIKE :r"), {"r": rotulo_like})
    db.session.execute(text("DELETE FROM centro_custo WHERE nome LIKE :r"), {"r": rotulo_like})
    db.session.execute(text("DELETE FROM opcao_proxima_turma WHERE nome LIKE :r"), {"r": rotulo_like})
    db.session.execute(text("DELETE FROM periodo_letivo WHERE nome LIKE :r"), {"r": rotulo_like})
    if usuarios:
        lista = ",".join(str(u) for u in usuarios)
        db.session.execute(text(f'DELETE FROM "user" WHERE id IN ({lista})'))
    db.session.execute(text("DELETE FROM unidade WHERE nome LIKE :r"), {"r": rotulo_like})
    db.session.commit()
    return len(turmas) + len(alunos) + len(unidades) + len(usuarios)


def _relatorio(dados: dict, contagens: dict, rotulo: dict, esperados: dict) -> None:
    ids = dados
    print("\n=== SEMENTE DO ROTEIRO (M1) ===")
    print(f"Unidade principal : {ids['unidade'].id} {ids['unidade'].nome}")
    print(f"Unidade vizinha   : {ids['vizinha'].id} {ids['vizinha'].nome}")
    print(f"Periodo vigente   : {ids['periodo_vig'].id} "
          f"{ids['periodo_vig'].data_inicio} a {ids['periodo_vig'].data_fim}")
    print(f"Turma A (1 oferta): {ids['turma_a'].id} / oferta {ids['oferta_a'].id} (legado NULL)")
    print(f"Turma B (2 ofertas): {ids['turma_b'].id} / ofertas "
          f"{ids['oferta_b1'].id} (Profissionalizante) e {ids['oferta_b2'].id} (Meio Ambiente)")
    print(f"Turma C (grade variavel): {ids['turma_c'].id} / oferta {ids['oferta_c'].id}")
    print(f"Turma D (lixeira) : {ids['turma_d'].id} / ofertas {ids['oferta_d1'].id} "
          f"(no marcador) e {ids['oferta_d2'].id} (desativada antes)")
    print(f"Turma vizinha     : {ids['turma_viz'].id} / oferta {ids['oferta_viz'].id}")
    print(f"Datas de aula    : A legado {ids['dias_legado'][0]} ; B1 {ids['dias_b1'][0]} ; "
          f"B2 {ids['dias_b2'][0]} ; C {ids['dias_c'][0]} ; D {ids['dias_d'][0]}")
    print("\nUsuarios (senha unica):")
    for perfil, usuario in ids["usuarios"].items():
        print(f"  {perfil:11s} {usuario.email:32s} {'(senha definida por argumento/ambiente)' if origem != 'gerada' else '(gerada)'}")
    print("\nURLs prontas (troque a porta se o app nao estiver em 5000):")
    base = "http://127.0.0.1:5000"
    ana = ids["alunos"]["Ana A1"].id
    elisa = ids["alunos"]["Elisa C1"].id
    for nome_url, url in (
        ("login", f"{base}/login"),
        ("unidade central", f"{base}/trocar-unidade/{ids['unidade'].id}"),
        ("visao global", f"{base}/trocar-unidade/0"),
        ("listagem de turmas", f"{base}/turma"),
        ("lixeira", f"{base}/turmas/lixeira"),
        ("turma A", f"{base}/turma/{ids['turma_a'].id}"),
        ("ofertas da turma B", f"{base}/turma/{ids['turma_b'].id}/ofertas"),
        ("editar turma C (grade)", f"{base}/turma/editar/{ids['turma_c'].id}"),
        ("frequencia turma A (legado)",
         f"{base}/frequencia?turma_id={ids['turma_a'].id}&data={ids['dias_legado'][0]}"),
        ("frequencia B1",
         f"{base}/frequencia?turma_id={ids['turma_b'].id}&turma_curso={ids['oferta_b1'].id}"
         f"&data={ids['dias_b1'][0]}"),
        ("frequencia B2",
         f"{base}/frequencia?turma_id={ids['turma_b'].id}&turma_curso={ids['oferta_b2'].id}"
         f"&data={ids['dias_b2'][0]}"),
        ("pauta completa turma A", f"{base}/turma/{ids['turma_a'].id}/imprimir-pauta"),
        ("conselho painel", f"{base}/conselho"),
        ("conselho lancamento turma B/B1",
         f"{base}/conselho/lancamento?turma={ids['turma_b'].id}&etapa=INICIAL"
         f"&oferta_sel={ids['oferta_b1'].id}"),
        ("conselho perguntas", f"{base}/conselho/perguntas"),
        ("historico Ana", f"{base}/aluno/{ana}/historico"),
        ("ficha 360 Elisa", f"{base}/relatorios/alunos/{elisa}/ficha"),
        ("certificados do periodo vigente",
         f"{base}/periodo-letivo/relatorio/{ids['periodo_vig'].id}"),
        ("relatorio geral", f"{base}/relatorios/"),
        ("BI", f"{base}/relatorios/bi"),
        ("painel pedagogico", f"{base}/relatorios/painel"),
    ):
        print(f"  {nome_url:31s} {url}")
    print("\nContagens (banco inteiro — pode incluir dados preexistentes):")
    for chave, valor in contagens.items():
        print(f"  {chave:22s} {valor}")
    print("\nContagens do rotulo (base da idempotencia):")
    for chave, valor in rotulo.items():
        print(f"  {chave:22s} {valor}")
    print("\nValores esperados (aritmetica independente vs. app):")
    for chave in sorted(esperados):
        print(f"  {chave:32s} {esperados[chave]}")
    divergentes = [
        chave for chave in ("freq_turma_a", "freq_b1", "freq_b2", "freq_turma_b")
        if esperados.get(f"{chave}_manual") != esperados.get(f"{chave}_app")
    ]
    if esperados.get("ch_total_turma_c_manual") != esperados.get("ch_total_turma_c_app"):
        divergentes.append("ch_total_turma_c")
    print("\nDivergencias manual x app:", divergentes or "nenhuma")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--db", default=os.getenv("PAUTAON_ENSAIO_DB", DB_PADRAO),
        help=f"nome do banco de ensaio (padrao: {DB_PADRAO})",
    )
    parser.add_argument(
        "--limpar", action="store_true",
        help="remove apenas os registros com o rotulo [ROTEIRO] e sai",
    )
    parser.add_argument(
        "--senha", default=None,
        help="senha para os usuarios [ROTEIRO] (opcional; senao ROTEIRO_SENHA ou gerada)",
    )
    args = parser.parse_args()

    senha, origem = resolver_senha(args)
    # validar
    from app.services.auth_service import validate_password_strength
    erros = validate_password_strength(senha)
    if erros:
        for e in erros:
            print("Senha fraca:", e)
        return 2

    dsn = _dsn(args.db)
    from flask_login import login_user

    from app.database import db
    from app.models import User
    from app.utils.timezone import get_local_now

    app = _criar_app(dsn)
    with app.app_context():
        banco = db.engine.url.database
        print(f"Banco alvo: {banco}")

        if args.limpar:
            removidos = _limpar()
            print(f"Removidos {removidos} registros-raiz com o rotulo {ROTULO}.")
            print("Contagens restantes:", _contagens())
            return 0

        with app.test_request_context("/"):
            admin = db.session.execute(
                db.select(User).filter_by(email=f"admin.m1@{DOMINIO}")
            ).scalars().first()
            if admin is not None:
                login_user(admin, force=True)
            dados = _semear(get_local_now().date())
            login_user(
                db.session.execute(
                    db.select(User).filter_by(email=f"admin.m1@{DOMINIO}")
                ).scalars().first(),
                force=True,
            )
            contagens = _contagens()
            rotulo = _contagens_rotulo()
            esperados = _esperados(dados)
        _relatorio(dados, contagens, rotulo, esperados)
        if origem == "gerada":
            print(f"\nSenha dos usuarios [ROTEIRO] (gerada agora): {senha}")
        else:
            print("\nSenha definida por argumento/ambiente.")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())

from datetime import date, datetime

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload, selectinload

from app.database import db
from app.models import (
    Aluno,
    CentroCusto,
    Curso,
    Frequencia,
    Inscricao,
    Nivel,
    PerfilDiversidade,
    PeriodoLetivo,
    RegistroAula,
    TemaAula,
    Turma,
    TurmaCurso,
    User,
)
from app.models.enums import UserRole
from app.services.enturmacao import MSG_JA_ENTURMADO, enturmar_aluno
from app.services.entrada_oferta import inicio_efetivo, parse_escolha_entrada
from app.services.turma_curso import (
    adicionar_oferta,
    criar_oferta_inicial_da_turma,
    definir_principal,
    desativar_oferta,
    datas_aula_oferta,
    editar_oferta,
    gravar_marcador_exclusao,
    gravar_troca_professor_da_oferta,
    oferta_tem_lancamentos,
    ofertas_com_lancamentos,
    ofertas_ativas,
    sincronizar_programa_turma,
    turma_tem_historico,
    _AGENDA_INCOMPLETA,
    _alunos_da_oferta,
    _conflitos_horario_concomitante,
)
from app.services.turma_curso_horario import (
    definir_grade,
    filtro_por_dia_horario,
    grade_da_oferta,
    grade_uniforme,
    grades_para_exibicao,
    grades_por_oferta,
)
from app.utils.datetime_parse import parse_date, parse_time
from app.utils.dias_semana import (
    token_para_weekday,
    weekday_para_abrev,
    weekday_para_nome,
)
from app.utils.formatters import formatar_ch
from app.utils.logica import (
    _blocked_dates_str,
    calcular_idades,
    carregar_contexto_turma,
    get_unidade_id,
    meses_de_datas,
)
from app.utils.timezone import get_local_now
from app.services.auth_service import register_security_log

from . import bp
from .shared import assert_unidade_context, obter_proximo_ordenacao

# Motivo gravado em `inscricoes.motivo_desativacao` quando a turma é desativada
# por exclusão lógica (Onda 4, Etapa I). Mesma família de tokens de `TRANSFERENCIA`
# (CAIXA-ALTA, sem acento) usada em app/registros/alunos.py.
MOTIVO_INSCRICAO_TURMA_DESATIVADA = "TURMA_DESATIVADA"


# E2/G1: porta de confirmação da troca de professor numa oferta que já tem
# lançamento gravado (mesmo padrão do bloco de limpeza de lançamentos).
MSG_TROCA_PROFESSOR_COM_LANCAMENTO = (
    "Trocar o professor de uma oferta com lançamentos exige confirmação: os "
    "registros já feitos continuam atribuídos a quem os lançou. Salve "
    "novamente confirmando a troca."
)


# ---------------------------------------------------------------------------
# H4 — parsing único da agenda do formulário
# ---------------------------------------------------------------------------

# Dias aceitos na agenda: segunda (0) a sábado (5). Domingo (6) é recusado.
_DIAS_AGENDA = (0, 1, 2, 3, 4, 5)


def _token_weekday(token) -> int | None:
    """Resolve um token de dia do formulário em índice ``date.weekday()``.

    Aceita o índice numérico usado pelos checkboxes do H4 (``"3"``) e o nome
    legado (``"Quarta"``, ``"qua."``, ``"quarta-feira"``) — assim o contrato
    novo convive com payloads antigos. Token desconhecido → ``None``.
    """
    texto = str(token or "").strip()
    if not texto:
        return None
    if len(texto) <= 2 and texto.isdigit():
        dia = int(texto)
        return dia if 0 <= dia <= 6 else None
    return token_para_weekday(texto)


def _resultado_grade(
    *,
    por_dia: bool = False,
    dias: list[int] | None = None,
    hora_inicio=None,
    hora_fim=None,
    itens: list | None = None,
    erro: str | None = None,
) -> dict:
    """Monta o dicionário de retorno de ``grade_do_formulario``."""
    return {
        "por_dia": por_dia,
        "dias": list(dias or []),
        "hora_inicio": hora_inicio,
        "hora_fim": hora_fim,
        "itens": itens,
        "erro": erro,
    }


def grade_do_formulario(form) -> dict:
    """Lê a agenda do formulário e devolve a grade pronta para o serviço (H4).

    Contrato único dos três formulários de agenda (turma nova, turma editada e
    curso da turma): ``dias_semana`` (checkboxes repetidos, valor = weekday
    0–5 ou nome legado), ``hora_inicio``/``hora_fim`` (o **par padrão**) e, no
    modo personalizado, o interruptor ``horario_por_dia`` somado aos pares por
    dia ``hora_inicio_<w>``/``hora_fim_<w>``.

    - **modo padrão**: o par único é replicado em todos os dias marcados —
      exatamente o comportamento anterior ao H4;
    - **modo personalizado**: cada dia marcado traz o próprio par; campos de
      dias **não** marcados são ignorados;
    - domingo é recusado, dia marcado sem par completo ou com ``fim <= início``
      vira mensagem que identifica o dia.

    Devolve ``{"por_dia", "dias", "hora_inicio", "hora_fim", "itens", "erro"}``,
    onde ``itens`` é a lista ``[(weekday, início, fim)]`` pronta para o
    ``agenda=`` dos serviços (``None`` quando ``erro`` vem preenchido). Esta
    função só traduz o formulário: a validação **autoritativa** continua no
    servidor, em ``definir_grade``.
    """
    dias: list[int] = []
    for bruto in form.getlist("dias_semana"):
        if not str(bruto).strip():
            continue
        dia = _token_weekday(bruto)
        if dia is None:
            return _resultado_grade(
                erro=f"Dia de aula inválido: “{bruto}”. Use segunda a sábado."
            )
        if dia == 6:
            return _resultado_grade(
                erro="Domingo não é dia de aula — use segunda a sábado."
            )
        if dia not in dias:
            dias.append(dia)
    dias.sort()

    por_dia = str(form.get("horario_por_dia") or "").strip().lower() in (
        "1", "on", "true", "sim", "yes",
    )
    hora_inicio = parse_time(form.get("hora_inicio"))
    hora_fim = parse_time(form.get("hora_fim"))

    if not dias:
        return _resultado_grade(
            por_dia=por_dia,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            erro=_AGENDA_INCOMPLETA,
        )

    if not por_dia:
        # Modo padrão: um par único replicado nos dias marcados.
        if hora_inicio is None or hora_fim is None:
            return _resultado_grade(
                por_dia=False,
                dias=dias,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                erro=_AGENDA_INCOMPLETA,
            )
        if hora_fim <= hora_inicio:
            return _resultado_grade(
                por_dia=False,
                dias=dias,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                erro="O fim do horário deve ser maior que o início.",
            )
        return _resultado_grade(
            por_dia=False,
            dias=dias,
            hora_inicio=hora_inicio,
            hora_fim=hora_fim,
            itens=[(d, hora_inicio, hora_fim) for d in dias],
        )

    # Modo personalizado: um par por dia marcado; dias fora ficam de fora.
    itens: list = []
    for dia in dias:
        nome = weekday_para_nome(dia)
        ini = parse_time(form.get(f"hora_inicio_{dia}"))
        fim = parse_time(form.get(f"hora_fim_{dia}"))
        if ini is None or fim is None:
            return _resultado_grade(
                por_dia=True,
                dias=dias,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                erro=f"Informe o horário de início e de fim da {nome}.",
            )
        if fim <= ini:
            return _resultado_grade(
                por_dia=True,
                dias=dias,
                hora_inicio=hora_inicio,
                hora_fim=hora_fim,
                erro=f"O horário da {nome} deve terminar depois de começar.",
            )
        itens.append((dia, ini, fim))

    return _resultado_grade(
        por_dia=True,
        dias=dias,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        itens=itens,
    )


def _erro_agenda_formulario(grade: dict) -> bool:
    """True quando o erro de agenda merece devolver o formulário preenchido.

    ``_AGENDA_INCOMPLETA`` **sem** dia marcado e **sem** interruptor ligado é o
    estado "tela sem agenda" de antes do H4 — a herança/fallback do serviço
    decide o que fazer (turma legada, 1ª oferta por herança). Qualquer outro
    erro foi digitado pelo usuário e volta para correção.
    """
    if not grade["erro"]:
        return False
    if grade["por_dia"] or grade["dias"]:
        return True
    return grade["erro"] != _AGENDA_INCOMPLETA


def _fmt_hora_agenda(value):
    """`time`/`"HH:MM"` → texto para `<input type="time">`; `None` → `""`."""
    if value is None:
        return ""
    if hasattr(value, "strftime"):
        return value.strftime("%H:%M")
    return str(value)


def _estado_agenda(
    *, dias=(), por_dia=False, hora_inicio="", hora_fim="", por_dia_map=None, erro=None
):
    """Estado do componente de agenda que o template consumes (H4, Passo 3).

    ``dias`` = weekdays marcados; ``hora_inicio``/``hora_fim`` = par padrão;
    ``por_dia_map`` = ``{weekday: (início, fim)}`` do modo personalizado; é essa
    a fonte que abre o formulário já em modo personalizado quando a grade da
    oferta não é uniforme.
    """
    return {
        "dias": set(dias),
        "por_dia": por_dia,
        "hora_inicio": _fmt_hora_agenda(hora_inicio),
        "hora_fim": _fmt_hora_agenda(hora_fim),
        "por_dia_map": {
            w: (_fmt_hora_agenda(ini), _fmt_hora_agenda(fim))
            for w, (ini, fim) in (por_dia_map or {}).items()
        },
        "erro": erro,
    }


def _estado_agenda_da_grade(linhas):
    """Estado a partir das linhas da grade (H5a: só a grade é fonte).

    Sem linhas devolve estado vazio — o formulário não pré-preenche nada a
    partir das colunas escalares (elas deixaram de ser lidas).
    """
    if not linhas:
        return _estado_agenda()
    pares = {(l.hora_inicio, l.hora_fim) for l in linhas}
    por_dia = len(pares) > 1
    if len(pares) == 1:
        ini, fim = next(iter(pares))
    else:
        ini = fim = None
    return _estado_agenda(
        dias={l.dia_semana for l in linhas},
        por_dia=por_dia,
        hora_inicio=ini,
        hora_fim=fim,
        por_dia_map={l.dia_semana: (l.hora_inicio, l.hora_fim) for l in linhas},
    )


def _estado_agenda_do_form(form):
    """Estado a partir do POST rejeitado — o formulário volta como o usuário digitou."""
    grade = grade_do_formulario(form)
    mapa = {
        w: (form.get(f"hora_inicio_{w}") or "", form.get(f"hora_fim_{w}") or "")
        for w in grade["dias"]
    }
    return _estado_agenda(
        dias=grade["dias"],
        por_dia=grade["por_dia"],
        hora_inicio=grade["hora_inicio"],
        hora_fim=grade["hora_fim"],
        por_dia_map=mapa,
        erro=grade["erro"],
    )


def _serializar_estado_agenda(estado):
    """Estado → ``"dia:HH:MM-HH:MM|..."`` (mesmo formato do JS, mudança de agenda)."""
    mapa = estado["por_dia_map"] or {}
    partes = []
    for w in sorted(estado["dias"]):
        ini, fim = mapa.get(w, (estado["hora_inicio"], estado["hora_fim"]))
        partes.append(f"{w}:{ini or ''}-{fim or ''}")
    return "|".join(partes)


def _parse_int_arg(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _parse_float_arg(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def _parse_float_arg(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# Ordem canônica dos dias para união/exibição: `date.weekday()` (0 = segunda).
# A abreviação da listagem mantém o ponto final usado desde a Etapa K.


def _ofertas_ativas_da_turma(turma):
    """Ofertas ativas da turma em ordem estável (menor id primeiro).

    Usa o relacionamento `ofertas_curso` já carregado por eager loading na
    rota; filtra `ativo` em Python (sem query extra, sem N+1). Tolerante a
    objetos sem a relação (ex.: doubles de teste) — tratam-se como 0 ofertas.
    """
    return sorted(
        (o for o in getattr(turma, "ofertas_curso", ()) if o.ativo),
        key=lambda o: o.id,
    )


def _oferta_principal(turma):
    """Oferta principal da turma: a marcada `principal`; se nenhuma, a de menor
    id entre as ativas; None se não houver oferta ativa."""
    ativas = _ofertas_ativas_da_turma(turma)
    for o in ativas:
        if o.principal:
            return o
    return ativas[0] if ativas else None


def _ofertas_ativas_existe():
    """EXISTS correlacionado: a turma possui ao menos uma oferta ativa."""
    return (
        select(TurmaCurso.id)
        .where(TurmaCurso.turma_id == Turma.id, TurmaCurso.ativo.is_(True))
        .exists()
    )


def _existe_oferta_que(cond_oferta):
    """EXISTS correlacionado sobre ofertas ativas cuja `cond_oferta` (já com
    COALESCE oferta→turma) casa. Turma sem oferta ativa nunca casa aqui."""
    return (
        select(TurmaCurso.id)
        .where(TurmaCurso.turma_id == Turma.id, TurmaCurso.ativo.is_(True), cond_oferta)
        .exists()
    )


def _csv_token_match(coluna, valor):
    """Compara um nome com um token de campo CSV sem casar nomes parciais."""
    normalizada = func.replace(func.coalesce(coluna, ""), " ", "")
    token = func.replace(func.coalesce(valor, ""), " ", "")
    token = func.replace(func.replace(func.replace(token, "\\", "\\\\"), "%", "\\%"), "_", "\\_")
    return or_(
        normalizada == token,
        normalizada.like(token + ",%", escape="\\"),
        normalizada.like("%," + token + ",%", escape="\\"),
        normalizada.like("%," + token, escape="\\"),
    )


def _tokens_centro_custo(valor: str | None) -> set[str]:
    return {token.strip() for token in (valor or "").split(",") if token.strip()}


_PALETA_BADGES_ANO = (
    ("#0d6efd", "#ffffff"), ("#198754", "#ffffff"),
    ("#dc3545", "#ffffff"), ("#6f42c1", "#ffffff"),
    ("#0dcaf0", "#102a43"), ("#fd7e14", "#212529"),
    ("#d63384", "#ffffff"), ("#20c997", "#102a43"),
    ("#6c757d", "#ffffff"), ("#ffc107", "#212529"),
)

# Programas aceitos na oferta (mesma lista da tela "Cursos da Turma"). A
# coluna Turma.programa é projeção da oferta principal ativa (MER §8.10).
_PROGRAMAS_OFERTA = ("Profissionalizante", "Esporte", "Meio Ambiente", "Outros")


def _filtro_por_oferta(cond_oferta, cond_turma):
    """Casa se QUALQUER oferta ativa casa (via COALESCE) OU, só quando a turma
    não tem oferta ativa, se a coluna congelada da turma casa."""
    return or_(
        _existe_oferta_que(cond_oferta),
        and_(~_ofertas_ativas_existe(), cond_turma),
    )


def _resumo_ofertas(turma, grades=None):
    """Professores/turnos distintos e união ordenada dos dias das ofertas
    ativas, para a linha-agregado da lista.

    Desde o H3d os **dias** saem da GRADE das ofertas ativas (a decisão é que
    a Turma DERIVE os dias da união das ofertas). H5a: sem fallback escalar —
    oferta ativa sem grade não contribui com dias (estado inválido) e turma
    sem oferta ativa não tem agenda.

    `grades` é o mapa `oferta_id -> linhas` já carregado pela rota (sem N+1).
    Quando omitido, a grade de cada oferta ativa é lida sob demanda — caminho
    usado por chamadas isoladas (testes, telas pontuais), sempre pela grade.
    """
    ativas = _ofertas_ativas_da_turma(turma)
    professores, turnos, dias_set = [], [], set()
    for o in ativas:
        nome_p = (
            o.professor.name if o.professor is not None
            else (turma.professor.name if turma.professor is not None else None)
        )
        if nome_p and nome_p not in professores:
            professores.append(nome_p)
        turno = o.turno or turma.turno
        if turno and turno not in turnos:
            turnos.append(turno)
        if grades is None:
            linhas = grade_da_oferta(o)
        else:
            linhas = grades.get(o.id) or []
        if not linhas:
            current_app.logger.error(
                "Oferta %s sem grade: dias da listagem ignoram a oferta "
                "(estado inválido desde o H5a).",
                o.id,
            )
            continue
        dias_set.update(linha.dia_semana for linha in linhas)
    dias = [weekday_para_nome(d) for d in sorted(dias_set)]
    dias_abreviados = [f"{weekday_para_abrev(d)}." for d in sorted(dias_set)]
    return {
        "professores": professores,
        "turnos": turnos,
        "dias": dias,
        "dias_abreviados": dias_abreviados,
    }


def aplicar_filtros_turmas(stmt, args, incluir_turmas_sem_periodo=False):
    """Aplica filtros persistidos (SQL) sobre o select de Turma.

    periodo_letivo_id e ano_periodo restringem o período da turma; centro_custo
    usa o catálogo ativo da unidade e os centros associados às ofertas. Para
    professor/turno/dia/horario_inicio, a turma casa se QUALQUER oferta ativa
    casar usando COALESCE(coluna da oferta, coluna da turma); sem oferta ativa,
    valem as colunas da turma. nome e programa seguem na turma.

    incluir_turmas_sem_periodo: na vista padrão (sem período/ano escolhidos,
    quando a rota injeta o ano vigente) turmas com periodo_letivo_id NULL
    continuam visíveis — exibidas com o selo "Sem período". Quando o usuário
    escolhe período/ano explicitamente o filtro permanece estrito (flag False).
    """
    nome = (args.get("nome") or "").strip()
    if nome:
        stmt = stmt.where(Turma.nome.ilike(f"%{nome}%"))

    periodo_letivo_id = _parse_int_arg(args.get("periodo_letivo_id"))
    if periodo_letivo_id:
        stmt = stmt.where(
            Turma.periodo_letivo_id.in_(
                select(PeriodoLetivo.id).where(
                    PeriodoLetivo.id == periodo_letivo_id,
                    PeriodoLetivo.unidade_id == Turma.unidade_id,
                )
            )
        )
    ano_periodo = _parse_int_arg(args.get("ano_periodo"))
    if ano_periodo:
        por_ano = Turma.periodo_letivo_id.in_(
            select(PeriodoLetivo.id).where(
                PeriodoLetivo.unidade_id == Turma.unidade_id,
                func.extract("year", PeriodoLetivo.data_inicio) == ano_periodo
            )
        )
        if incluir_turmas_sem_periodo:
            # Vista padrão: turma sem período letivo não é ocultada pelo ano
            # vigente injetado automaticamente (D3).
            por_ano = or_(por_ano, Turma.periodo_letivo_id.is_(None))
        stmt = stmt.where(por_ano)

    centro_custo_id = _parse_int_arg(args.get("centro_custo"))
    if centro_custo_id:
        oferta_no_centro = (
            select(TurmaCurso.id)
            .join(
                CentroCusto,
                and_(
                    CentroCusto.id == centro_custo_id,
                    CentroCusto.unidade_id == Turma.unidade_id,
                    CentroCusto.ativo.is_(True),
                ),
            )
            .where(
                TurmaCurso.turma_id == Turma.id,
                TurmaCurso.ativo.is_(True),
                _csv_token_match(
                    func.coalesce(
                        func.nullif(TurmaCurso.centro_custo, ""),
                        Turma.centro_custo,
                    ),
                    CentroCusto.nome,
                ),
            )
            .exists()
        )
        stmt = stmt.where(oferta_no_centro)

    professor = (args.get("professor") or "").strip()
    if professor:
        prof_like = f"%{professor}%"
        # COALESCE(oferta.professor_id, turma.professor_id) -> nome do User.
        cond_oferta = (
            select(User.id)
            .where(
                User.id == func.coalesce(TurmaCurso.professor_id, Turma.professor_id),
                User.name.ilike(prof_like),
            )
            .exists()
        )
        cond_turma = (
            select(User.id)
            .where(User.id == Turma.professor_id, User.name.ilike(prof_like))
            .exists()
        )
        stmt = stmt.where(_filtro_por_oferta(cond_oferta, cond_turma))

    turno = (args.get("turno") or "").strip()
    if turno:
        stmt = stmt.where(
            _filtro_por_oferta(
                func.coalesce(TurmaCurso.turno, Turma.turno) == turno,
                Turma.turno == turno,
            )
        )

    # Programa da turma é projeção da oferta principal.
    programa = (args.get("programa") or "").strip()
    if programa:
        stmt = stmt.where(Turma.programa == programa)

    # Dia e horário leem SOMENTE a GRADE (H3d/H5a): a turma casa quando uma
    # oferta ATIVA tem linha de grade com o weekday e/ou a hora de início — os
    # dois critérios na MESMA linha, então “dia A + hora do dia B” não casa.
    # Não existe comparador escalar de reserva: turma sem oferta ativa com
    # grade não casa (a agenda nasce com a oferta).
    dia = (args.get("dia") or "").strip()
    horario = parse_time(args.get("horario_inicio"))
    if dia or horario:
        dia_semana = token_para_weekday(dia) if dia else None
        if dia and dia_semana is None:
            # Token fora do domínio 0–6: não casa nenhuma turma (sem CSV
            # escalar de reserva desde o H5a).
            current_app.logger.warning(
                "Filtro de dia com token desconhecido: %r — nenhuma turma casa.",
                dia,
            )
            stmt = stmt.where(false())
        else:
            stmt = stmt.where(filtro_por_dia_horario(dia_semana, horario))

    return stmt


def pos_filtrar_turmas(turmas, args):
    """Filtra em memória critérios calculados (alunos, frequência, C.H.).

    Com 2+ ofertas ativas, `min_freq` é avaliado sobre a oferta principal.
    A C.H. usa SEMPRE o valor calculado da turma — o mesmo exibido na lista:
    `min_ch_aula` compara a MENOR duração semanal entre todas as ofertas ativas
    (H3d) e `min_ch_total` compara o tempo físico da turma (união dos
    intervalos das ofertas ativas), nunca o total de uma oferta isolada. Com 0
    ou 1 oferta o resultado é o mesmo de antes. `min_alunos` inalterado.
    """
    min_alunos = _parse_int_arg(args.get("min_alunos"))
    min_freq = _parse_float_arg(args.get("min_freq"))
    min_ch_aula = _parse_float_arg(args.get("min_ch_aula"))
    min_ch_total = _parse_float_arg(args.get("min_ch_total"))

    cargas = {}
    if min_ch_aula is not None or min_ch_total is not None:
        from app.services.turma_curso_horario import cargas_horarias_turmas_em_lote

        persistidas = [t for t in turmas if getattr(t, "id", None) is not None]
        cargas = cargas_horarias_turmas_em_lote(persistidas)

    # Frequência em LOTE (D3b-2.5): mapa pré-calculado (turma = soma) para
    # `min_freq` — compara o MESMO valor exibido na coluna (D7). UMA consulta.
    _agg_turma_freq = {}
    if min_freq is not None:
        from app.services.frequencia_oferta import agregar_por_turma

        persistidas = [t for t in turmas if getattr(t, "id", None) is not None]
        _agg_turma_freq = agregar_por_turma([t.id for t in persistidas])

    resultado = []
    for turma_item in turmas:
        if min_alunos is not None and turma_item.alunos_ativos_count < min_alunos:
            continue

        carga_turma = cargas.get(getattr(turma_item, "id", None))
        multi = (
            carga_turma.ofertas_ativas >= 2
            if carga_turma is not None
            else len(_ofertas_ativas_da_turma(turma_item)) >= 2
        )
        principal = _oferta_principal(turma_item) if multi else None

        if min_freq is not None:
            tid = getattr(turma_item, "id", None)
            if tid is None:
                # Objeto sem id (compatibilidade/testes): fallback à
                # property `freq_geral` (turma = soma), como antes da D3b-2.5
                # para 0/1 oferta; para 2+ ofertas o antigo comparava a oferta
                # principal, mas o fallback não tem oferta — mantém soma.
                freq = turma_item.freq_geral
            else:
                info = _agg_turma_freq.get(tid)
                freq = info.pct_turma if info is not None else 0.0
            if freq < min_freq:
                continue

        if min_ch_aula is not None:
            ch_aula = (
                carga_turma.min_ch_aula
                if carga_turma is not None
                else (
                    principal.carga_horaria_aula
                    if multi
                    else turma_item.carga_horaria_aula
                )
            )
            if ch_aula is None or ch_aula < min_ch_aula * 60:
                continue

        if min_ch_total is not None:
            ch_total = (
                carga_turma.carga_horaria_total
                if carga_turma is not None
                else (principal.carga_horaria_total if multi else turma_item.carga_horaria_total)
            )
            if ch_total is None or ch_total < min_ch_total * 60:
                continue

        resultado.append(turma_item)
    return resultado


@bp.route("/turma")
@login_required
def turma():
    # AJ6-B5 (REGRA DO RESPONSÁVEL): a LISTA de turmas é exclusiva dos perfis
    # gestores. O professor NUNCA acessa a lista — ele entra nas ofertas dele pelo
    # painel/ficha, via REGRA ÚNICA de autorização por oferta (AJ6-B3/B4), sem
    # predicação nova. `servico_social` já não estava aqui (inalterado); só o
    # professor perde acesso em relação ao estado anterior. Ver docs/Relatórios.
    if current_user.role not in [
        "admin", "pedagogico", "secretaria", "gerencia",
    ]:
        abort(403)

    unidade_id = get_unidade_id()
    stmt_base = select(Turma).where(Turma.ativo == True)
    if unidade_id:
        stmt_base = stmt_base.where(Turma.unidade_id == unidade_id)

    # Eager loading (sem N+1): professor da turma + ofertas com curso,
    # professor e GRADE (H3d). O filtro `ativo` das ofertas é feito no helper
    # (Python), sobre a relação já carregada — sem query por linha.
    stmt_base = stmt_base.options(
        joinedload(Turma.professor),
        selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.curso),
        selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.professor),
        selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.horarios),
    )

    filtros = request.args.to_dict(flat=True)
    periodo_selecionado = _parse_int_arg(filtros.get("periodo_letivo_id"))
    ano_atual = get_local_now().year
    # Sem período exato ou ano informado, a listagem abre no ano vigente.
    vista_padrao = not periodo_selecionado and not _parse_int_arg(filtros.get("ano_periodo"))
    if vista_padrao:
        filtros["ano_periodo"] = str(ano_atual)
    filtros_rapidos = {"centro_custo", "ano_periodo", "periodo_letivo_id"}
    filtros_painel_aberto = any(chave not in filtros_rapidos for chave in filtros)
    stmt = aplicar_filtros_turmas(
        stmt_base, filtros, incluir_turmas_sem_periodo=vista_padrao
    )
    turmas = (
        db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome))
        .unique()
        .scalars()
        .all()
    )
    turmas = pos_filtrar_turmas(turmas, request.args)
    from app.services.turma_curso_horario import (
        cargas_horarias_ofertas_em_lote,
        cargas_horarias_turmas_em_lote,
    )

    carga_turma_map = cargas_horarias_turmas_em_lote(turmas)
    ofertas_carga = [o for t in turmas for o in _ofertas_ativas_da_turma(t)]
    carga_oferta_map = cargas_horarias_ofertas_em_lote(ofertas_carga)
    grades_ofertas = grades_por_oferta(ofertas_carga)
    grade_oferta_map = grades_para_exibicao(
        ofertas_carga, carga_oferta_map, grades_ofertas
    )

    # Frequência em LOTE (D3b-2.2): mapas pré-calculados, UMA consulta por
    # mapa — evita N+1 de `Turma.freq_geral`/`freq_geral_oferta` na listagem.
    from app.services.frequencia_oferta import (
        freq_geral_ofertas_em_lote,
        freq_geral_turmas_em_lote,
    )

    freq_turma_map = freq_geral_turmas_em_lote(
        [t.id for t in turmas]
    )
    freq_oferta_map = freq_geral_ofertas_em_lote(
        [o.id for o in ofertas_carga]
    )

    # Centros disponíveis para o filtro do formulário.
    stmt_centros_catalogo = select(CentroCusto).where(CentroCusto.ativo.is_(True))
    if unidade_id:
        stmt_centros_catalogo = stmt_centros_catalogo.where(
            CentroCusto.unidade_id == unidade_id
        )
    centros_catalogo = db.session.execute(
        stmt_centros_catalogo.order_by(CentroCusto.nome, CentroCusto.unidade_id)
    ).scalars().all()
    centro_custo_selecionado = _parse_int_arg(filtros.get("centro_custo"))
    periodo_selecionado = _parse_int_arg(filtros.get("periodo_letivo_id"))
    ano_selecionado = _parse_int_arg(filtros.get("ano_periodo"))

    # O seletor inclui períodos históricos e futuros. As badges rápidas ficam
    # limitadas ao ano atual e ao anterior, agrupadas pelo ano de início.
    stmt_periodos = select(PeriodoLetivo)
    if unidade_id:
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.unidade_id == unidade_id)
    periodos_filtro = db.session.execute(
        stmt_periodos.order_by(PeriodoLetivo.data_inicio.desc(), PeriodoLetivo.nome)
    ).scalars().all()
    periodos_por_ano = {}
    for periodo in periodos_filtro:
        if periodo.data_inicio:
            periodos_por_ano.setdefault(periodo.data_inicio.year, []).append(periodo)
    anos_periodos = [ano_atual]
    if ano_atual - 1 in periodos_por_ano:
        anos_periodos.append(ano_atual - 1)
    if periodo_selecionado and ano_selecionado is None:
        periodo_escolhido = next(
            (p for p in periodos_filtro if p.id == periodo_selecionado), None
        )
        if periodo_escolhido and periodo_escolhido.data_inicio:
            ano_periodo_escolhido = periodo_escolhido.data_inicio.year
            if ano_periodo_escolhido in anos_periodos:
                ano_selecionado = ano_periodo_escolhido
    cores_por_ano = {
        ano: _PALETA_BADGES_ANO[idx % len(_PALETA_BADGES_ANO)]
        for idx, ano in enumerate(anos_periodos)
    }
    filtros_sem_periodo = dict(filtros)
    filtros_sem_periodo.pop("periodo_letivo_id", None)
    filtros_sem_periodo.pop("ano_periodo", None)
    periodos_badges = []
    anos_badges = []
    for idx, ano in enumerate(anos_periodos):
        cor, cor_texto = cores_por_ano[ano]
        params_ano = dict(filtros_sem_periodo)
        params_ano["ano_periodo"] = ano
        anos_badges.append({
            "ano": ano,
            "cor": cor,
            "cor_texto": cor_texto,
            "url": url_for("registros.turma", **params_ano),
            "selecionado": ano == ano_selecionado,
            "periodos": [],
        })
        # O ano corrente é sempre oferecido como etiqueta visual; quando a
        # unidade ainda não cadastrou período nele, `periodos_por_ano` não tem
        # a chave — daí o .get() (defeito P2: KeyError → 500 na virada de ano).
        for periodo in periodos_por_ano.get(ano, []):
            params_periodo = dict(filtros_sem_periodo)
            params_periodo["periodo_letivo_id"] = periodo.id
            item = {
                "periodo": periodo,
                "ano": ano,
                "cor": cor,
                "cor_texto": cor_texto,
                "url": url_for("registros.turma", **params_periodo),
                "selecionado": periodo.id == periodo_selecionado,
            }
            periodos_badges.append(item)
            anos_badges[-1]["periodos"].append(item)

    # Vistas por turma para o template (evita recomputar e chama de método na Jinja).
    ofertas_map = {t.id: _ofertas_ativas_da_turma(t) for t in turmas}
    principal_map = {t.id: _oferta_principal(t) for t in turmas}
    resumo_map = {t.id: _resumo_ofertas(t, grades_ofertas) for t in turmas}
    carga_horaria_total_map = {
        turma.id: carga_turma_map[turma.id].carga_horaria_total
        for turma in turmas
    }

    # Nome da turma e professor vêm de todas as turmas ativas da unidade, sem
    # depender do ano/período ou dos demais filtros atualmente selecionados.
    stmt_turmas_opcoes = select(Turma).where(Turma.ativo.is_(True))
    if unidade_id:
        stmt_turmas_opcoes = stmt_turmas_opcoes.where(Turma.unidade_id == unidade_id)
    stmt_turmas_opcoes = stmt_turmas_opcoes.options(
        joinedload(Turma.professor),
        selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.professor),
    )
    turmas_opcoes = (
        db.session.execute(stmt_turmas_opcoes.order_by(Turma.nome))
        .unique()
        .scalars()
        .all()
    )
    nomes_turmas = sorted({t.nome for t in turmas_opcoes if t.nome})
    professores_por_nome = {}
    for t in turmas_opcoes:
        ofertas_opcoes = _ofertas_ativas_da_turma(t)
        professores_efetivos = (
            [oferta.professor or t.professor for oferta in ofertas_opcoes]
            if ofertas_opcoes else [t.professor]
        )
        for professor_opcao in professores_efetivos:
            if professor_opcao is not None:
                professores_por_nome.setdefault(
                    professor_opcao.name, professor_opcao
                )
    professores_filtro = [
        professores_por_nome[nome] for nome in sorted(professores_por_nome)
    ]
    return render_template(
        "turmas/listar.html",
        turmas=turmas,
        ofertas_map=ofertas_map,
        principal_map=principal_map,
        resumo_map=resumo_map,
        carga_horaria_total_map=carga_horaria_total_map,
        carga_turma_map=carga_turma_map,
        carga_oferta_map=carga_oferta_map,
        grade_oferta_map=grade_oferta_map,
        freq_turma_map=freq_turma_map,
        freq_oferta_map=freq_oferta_map,
        formatar_ch=formatar_ch,
        nomes_turmas=nomes_turmas,
        professores=professores_filtro,
        centros_filtro=centros_catalogo,
        centro_custo_selecionado=centro_custo_selecionado,
        periodo_selecionado=periodo_selecionado,
        periodos_filtro=periodos_filtro,
        ano_selecionado=ano_selecionado,
        anos_badges=anos_badges,
        periodos_badges=periodos_badges,
        filtros_painel_aberto=filtros_painel_aberto,
        url_imprimir_centros=url_for(
            "registros.imprimir_centros_custo_turmas", **filtros
        ),
    )


@bp.route("/turmas/centros-custo/imprimir")
@login_required
def imprimir_centros_custo_turmas():
    """Imprime centros, turmas e ofertas ativas, respeitando os filtros recebidos."""
    if current_user.role not in [
        "admin", "pedagogico", "secretaria", "gerencia",
    ]:
        abort(403)

    from app.models import Unidade

    unidade_id = get_unidade_id()
    filtros = request.args.to_dict(flat=True)
    periodo_id_filtro = _parse_int_arg(filtros.get("periodo_letivo_id"))
    ano_filtro = _parse_int_arg(filtros.get("ano_periodo"))
    periodo_relatorio = "Todos"
    if periodo_id_filtro:
        stmt_periodo_relatorio = select(PeriodoLetivo).where(
            PeriodoLetivo.id == periodo_id_filtro
        )
        if unidade_id:
            stmt_periodo_relatorio = stmt_periodo_relatorio.where(
                PeriodoLetivo.unidade_id == unidade_id
            )
        periodo_obj_relatorio = db.session.execute(
            stmt_periodo_relatorio
        ).scalar_one_or_none()
        if periodo_obj_relatorio:
            ano_inicio = (
                f" ({periodo_obj_relatorio.data_inicio.year})"
                if periodo_obj_relatorio.data_inicio else ""
            )
            periodo_relatorio = f"{periodo_obj_relatorio.nome}{ano_inicio}"
        else:
            periodo_relatorio = f"Período selecionado (ID {periodo_id_filtro})"
    elif ano_filtro:
        periodo_relatorio = f"Todos os períodos de {ano_filtro}"

    centros = CentroCusto.query.filter(CentroCusto.ativo.is_(True))
    turmas_query = select(Turma).where(Turma.ativo.is_(True))
    if unidade_id:
        centros = centros.filter_by(unidade_id=unidade_id)
        turmas_query = turmas_query.where(Turma.unidade_id == unidade_id)
    centro_custo_id = _parse_int_arg(filtros.get("centro_custo"))
    if centro_custo_id:
        centros = centros.filter(CentroCusto.id == centro_custo_id)
    centros = centros.order_by(CentroCusto.nome, CentroCusto.unidade_id).all()
    turmas_query = aplicar_filtros_turmas(turmas_query, filtros)
    turmas = (
        db.session.execute(
            turmas_query.options(
                joinedload(Turma.professor),
                selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.curso),
                selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.professor),
                selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.horarios),
            ).order_by(Turma.ordenacao, Turma.nome)
        )
        .unique()
        .scalars()
        .all()
    )
    turmas = pos_filtrar_turmas(turmas, filtros)

    from app.services.turma_curso_horario import (
        cargas_horarias_ofertas_em_lote,
        cargas_horarias_turmas_em_lote,
    )

    carga_turma_map = cargas_horarias_turmas_em_lote(turmas)
    ofertas_todas = [o for item in turmas for o in _ofertas_ativas_da_turma(item)]
    carga_oferta_map = cargas_horarias_ofertas_em_lote(ofertas_todas)
    # Grade de exibição (H3d): dias/horários vêm da grade, não da projeção.
    grade_oferta_map = grades_para_exibicao(ofertas_todas, carga_oferta_map)

    centros_por_chave = {
        (centro.unidade_id, centro.nome): centro for centro in centros
    }
    turmas_por_centro = {centro.id: [] for centro in centros}
    for turma_item in turmas:
        ofertas_turma = _ofertas_ativas_da_turma(turma_item)
        ch_total_turma = carga_turma_map[turma_item.id].carga_horaria_total
        principal = next(
            (oferta for oferta in ofertas_turma if oferta.principal),
            ofertas_turma[0] if len(ofertas_turma) == 1 else None,
        )

        ofertas_por_centro = {}
        if ofertas_turma:
            for oferta in ofertas_turma:
                nomes_centros = _tokens_centro_custo(
                    oferta.centro_custo or turma_item.centro_custo
                )
                for nome_centro in nomes_centros:
                    centro = centros_por_chave.get((turma_item.unidade_id, nome_centro))
                    if centro:
                        ofertas_por_centro.setdefault(centro.id, []).append(oferta)
        else:
            for nome_centro in _tokens_centro_custo(turma_item.centro_custo):
                centro = centros_por_chave.get((turma_item.unidade_id, nome_centro))
                if centro:
                    ofertas_por_centro.setdefault(centro.id, [])

        for centro_id, ofertas_centro in ofertas_por_centro.items():
            ofertas_centro.sort(key=lambda oferta: (oferta.id != getattr(principal, "id", None), oferta.id))
            turmas_por_centro[centro_id].append({
                "turma": turma_item,
                "ofertas": ofertas_centro,
                "principal_id": getattr(principal, "id", None),
                "carga_horaria_total": ch_total_turma,
            })

    if any(filtros.values()) and not centro_custo_id:
        centros = [centro for centro in centros if turmas_por_centro[centro.id]]

    unidade = db.session.get(Unidade, unidade_id) if unidade_id else None
    return render_template(
        "turmas/imprimir_listar_turma.html",
        centros=centros,
        turmas_por_centro=turmas_por_centro,
        unidade_id=unidade_id,
        unidade_nome=unidade.nome if unidade else None,
        periodo_relatorio=periodo_relatorio,
        url_retorno=url_for("registros.turma", **filtros),
        carga_oferta_map=carga_oferta_map,
        grade_oferta_map=grade_oferta_map,
        filtros_aplicados=any(filtros.values()),
        agora=get_local_now(),
        formatar_ch=formatar_ch,
    )


@bp.route("/turmas/lista")
@login_required
def turma_listar():
    return turma()


@bp.route("/turmas/lixeira")
@login_required
def turma_lixeira():
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    unidade_id = get_unidade_id()
    # Visão Global: somente leitura, sem botão.
    visao_global = unidade_id is None

    stmt = select(Turma).where(Turma.ativo.is_(False)).options(
        joinedload(Turma.periodo_letivo)
    )
    if unidade_id:
        stmt = stmt.where(Turma.unidade_id == unidade_id)
    turmas = db.session.execute(stmt.order_by(Turma.nome)).scalars().unique().all()

    # Pré-visualização com a MESMA regra de `reativar_turma`, em carga única
    # (ofertas, inscrições, alunos, marcadores) — sem N+1 por turma (L4.1).
    from app.services.turma_curso import previews_reativacao_em_lote

    previews = previews_reativacao_em_lote(turmas)

    return render_template(
        "turmas/turma_lixeira.html",
        turmas=turmas,
        visao_global=visao_global,
        previews=previews,
    )


@bp.route("/turmas/reativar/<int:id>", methods=["POST"])
@login_required
def reativar_turma_route(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    if not turma_obj or turma_obj.ativo:
        flash("Turma não encontrada na lixeira.", "warning")
        return redirect(url_for("registros.turma_lixeira"))

    assert_unidade_context(turma_obj.unidade_id, get_unidade_id())

    confirmar = request.form.get("confirmar_periodo") == "1"
    # A lixeira sempre envia a seleção explícita (`selecao_explicita`), inclusive
    # quando nenhuma oferta vem marcada — assim "desmarcar tudo" é recusa do
    # serviço, e não pré-seleção silenciosa do marcador.
    oferta_ids = None
    if request.form.get("selecao_explicita") == "1":
        try:
            oferta_ids = [int(v) for v in request.form.getlist("oferta_ids") if v]
        except ValueError:
            db.session.rollback()
            flash("Seleção de cursos inválida.", "danger")
            return redirect(url_for("registros.turma_lixeira"))

    from app.services.turma_curso import reativar_turma as _reativar

    try:
        resultado = _reativar(
            turma_obj,
            confirmar_periodo_encerrado=confirmar,
            oferta_ids=oferta_ids,
        )
        db.session.commit()
    except ValueError as exc:
        db.session.rollback()
        flash(str(exc), "danger")
        return redirect(url_for("registros.turma_lixeira"))
    except Exception as exc:
        db.session.rollback()
        from app.utils.errors import flash_and_log
        flash_and_log(exc, location="registros.reativar_turma_route")
        return redirect(url_for("registros.turma_lixeira"))

    # LogAcao
    try:
        register_security_log(
            "Reativação de Turma",
            f"Turma id={id} nome='{turma_obj.nome}' reativada: "
            f"{resultado['ofertas_reativadas']} oferta(s), "
            f"{resultado['inscricoes_reativadas']} inscrição(ões), "
            f"{len(resultado['conflitos'])} conflito(s).",
        )
        db.session.commit()
    except Exception:
        db.session.rollback()

    msg = (
        f"Turma reativada: {resultado['ofertas_reativadas']} oferta(s) e "
        f"{resultado['inscricoes_reativadas']} inscrição(ões) reativadas."
    )
    if resultado["cursos_reativados"]:
        msg += f" Cursos que voltaram: {'; '.join(resultado['cursos_reativados'])}."
    if resultado["ofertas_inativas_restantes"]:
        nomes = "; ".join(o["curso"] for o in resultado["ofertas_inativas_restantes"])
        msg += (
            f" Permanecem inativos (desativados antes da exclusão da turma ou "
            f"fora da seleção): {nomes}."
        )
    if resultado["conflitos"]:
        msg += (
            f" {len(resultado['conflitos'])} inscrição(ões) permaneceram "
            "inativas (aluno inativo ou já matriculado na oferta)."
        )
    flash(msg, "success")
    return redirect(url_for("registros.turma_lixeira"))


@bp.route("/turma/nova", methods=["GET", "POST"])
@login_required
def nova_turma():
    if current_user.role not in ["admin", "pedagogico", "gerencia", "secretaria"]:
        abort(403)

    unidade_id = get_unidade_id()
    if request.method == "POST" and unidade_id is None:
        # ETAPA B4: Visão Global é somente leitura — sem unidade efetiva a
        # rota recusa (403) em vez de criar Turma com unidade_id NULL (item 11).
        abort(403)
    if request.method == "POST":
        nome_turma = request.form.get("turma")
        if not nome_turma or not nome_turma.strip():
            flash("O nome da turma é obrigatório pela regra de negócios.", "warning")
            return redirect(url_for("registros.nova_turma"))

        # H4: a agenda vem do parsing único dos formulários. A tela de turma
        # nova não expõe o interruptor "Horário diferente por dia" (decisão
        # H4 — o por dia é editado em Cursos da Turma), mas o contrato é o
        # mesmo, e a grade segue para a oferta inicial via ``agenda=``.
        grade = grade_do_formulario(request.form)
        if _erro_agenda_formulario(grade):
            flash(grade["erro"], "warning")
            return redirect(url_for("registros.nova_turma"))

        professor_id = request.form.get("professor_id")
        professor_id = (
            int(professor_id) if professor_id and professor_id.isdigit() else None
        )
        periodo_letivo_id = request.form.get("periodo_letivo_id")
        periodo_letivo_id = (
            int(periodo_letivo_id)
            if periodo_letivo_id and periodo_letivo_id.isdigit()
            else None
        )
        if periodo_letivo_id is None:
            flash("Vincule a turma a um período letivo.", "warning")
            return redirect(url_for("registros.nova_turma"))
        turno = request.form.get("turno")
        centro_custo = request.form.get("centro_custo") or None
        periodo_obj = None

        if periodo_letivo_id:
            periodo_obj = db.session.get(PeriodoLetivo, periodo_letivo_id)
            # ETAPA B4: guard incondicional por unidade (o `unidade_id and`
            # anterior era pulado na Visão Global).
            if not periodo_obj or periodo_obj.unidade_id != unidade_id:
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.nova_turma"))

        if professor_id:
            professor = db.session.get(User, professor_id)
            if (
                not professor
                or professor.role != "professor"
                or (
                    periodo_letivo_id and professor.unidade_id != periodo_obj.unidade_id
                )
                or professor.unidade_id != unidade_id
            ):
                flash(
                    "Professor inválido para esta unidade ou período letivo.", "warning"
                )
                return redirect(url_for("registros.nova_turma"))

        if centro_custo and periodo_letivo_id:
            periodo_obj = db.session.get(PeriodoLetivo, periodo_letivo_id)
            centros_disponiveis = (
                [c.strip() for c in periodo_obj.centro_custo.split(",")]
                if periodo_obj and periodo_obj.centro_custo
                else []
            )
            if centros_disponiveis and centro_custo not in centros_disponiveis:
                flash("Centro de custo inválido para o período selecionado.", "warning")
                return redirect(url_for("registros.nova_turma"))

        # Datas do curso: quando não há datas específicas, o intervalo é
        # herdado do período letivo. Se houver, validamos para que nenhuma
        # data ultrapasse os limites do período ao qual a turma é vinculada.
        datas_personalizadas = request.form.get("datas_personalizadas") == "1"
        if datas_personalizadas:
            data_inicio = parse_date(request.form.get("data_inicio"))
            data_fim = parse_date(request.form.get("data_fim"))
            if data_inicio and periodo_obj and data_inicio < periodo_obj.data_inicio:
                flash(
                    "A data de início não pode ser anterior ao início do período letivo.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))
            if data_fim and periodo_obj and data_fim > periodo_obj.data_fim:
                flash(
                    "A data de término não pode ser posterior ao fim do período letivo.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))
        else:
            data_inicio = periodo_obj.data_inicio if periodo_obj else None
            data_fim = periodo_obj.data_fim if periodo_obj else None

        curso_id_raw = request.form.get("curso_id")
        curso_id = _parse_int_arg(curso_id_raw)
        if curso_id_raw and curso_id is None:
            flash("Curso inválido.", "warning")
            return redirect(url_for("registros.nova_turma"))
        if curso_id is not None:
            unidade_curso_id = unidade_id or (
                periodo_obj.unidade_id if periodo_obj else None
            )
            curso = Curso.query.filter_by(
                id=curso_id,
                unidade_id=unidade_curso_id,
                ativo=True,
            ).first()
            if curso is None:
                flash(
                    "Selecione um curso ativo da unidade para criar a turma.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))

        # Toda oferta exige programa (MER §8.10). A oferta inicial é criada a
        # partir da turma, então o programa precisa chegar antes dela.
        programa = (request.form.get("programa") or "").strip() or None
        if curso_id is not None and not programa:
            flash("Selecione o programa da oferta.", "warning")
            return redirect(url_for("registros.nova_turma"))

        nova = Turma(
            nome=nome_turma,
            # Turma sem curso não tem oferta: a projeção continua NULL.
            programa=programa if curso_id is not None else None,
            turno=turno,
            centro_custo=centro_custo,
            professor_id=professor_id,
            # Onda 2A: colunas são DATE/TIME. Parse explícito.
            data_inicio=data_inicio,
            data_fim=data_fim,
            # H4: dias_semana/hora_inicio/hora_fim da Turma NÃO são mais
            # escritos pela rota — são projeção da oferta única, sincronizada
            # logo abaixo depois de ``definir_grade``.
            periodo_letivo_id=periodo_letivo_id,
            unidade_id=unidade_id,
            ordenacao=obter_proximo_ordenacao(periodo_letivo_id),
            curso_id=curso_id,
            ativo=True,
        )

        try:
            db.session.add(nova)
            db.session.flush()  # garante turma.id para vincular a oferta inicial
            criar_oferta_inicial_da_turma(nova, agenda=grade["itens"])
            db.session.commit()
            flash(
                f"A turma '{nome_turma}' foi cadastrada. Agora inclua os cursos que serão ofertados.",
                "success",
            )
            return redirect(url_for("registros.turma_ofertas", id=nova.id))
        except ValueError as erro:
            # H2: oferta inicial exige agenda completa na turma.
            db.session.rollback()
            flash(str(erro), "warning")
            return redirect(url_for("registros.nova_turma"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao salvar turma.")
            flash("Não foi possível salvar a turma. Verifique os dados e tente novamente.", "danger")
            return redirect(url_for("registros.nova_turma"))

    professores = User.query.filter_by(role=UserRole.PROFESSOR.value)
    if unidade_id:
        professores = professores.filter_by(unidade_id=unidade_id)
    professores = professores.order_by(User.name).all()
    periodos = (
        PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True)
        .order_by(PeriodoLetivo.nome)
        .all()
        if unidade_id
        else []
    )
    cursos = (
        Curso.query.filter_by(ativo=True, unidade_id=unidade_id)
        .order_by(Curso.nome)
        .all()
        if unidade_id
        else []
    )
    # Intervalo de datas de cada período, usado pelo front para exibir o range
    # herdado e restringir as datas específicas do curso.
    periodos_datas = {
        str(p.id): {
            "inicio": p.data_inicio.isoformat() if p.data_inicio else None,
            "fim": p.data_fim.isoformat() if p.data_fim else None,
        }
        for p in periodos
    }
    # ETAPA B6 (R2): o programa é projeção da oferta principal e não é mais
    # solicitado no cadastro da turma; nova_turma.html não consome `programas`,
    # então o contexto órfão foi removido daqui. `_PROGRAMAS_OFERTA` segue em
    # uso por editar_turma.
    return render_template(
        "turmas/nova_turma.html",
        professores=professores,
        periodos=periodos,
        periodo_ativo=None,
        cursos=cursos,
        periodos_datas=periodos_datas,
    )


@bp.route("/turma/<int:id>")
@login_required
def ver_turma(id):
    from app.services.aluno_info_professor import (
        professor_da_oferta,
        professor_de_alguma_oferta_ativa,
        professor_pode_acessar_oferta,
    )

    unidade_id = get_unidade_id()
    turma_obj = Turma.query.get_or_404(id)
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    # E3 (I1): acesso do professor por OFERTA, sem herdar `turma.professor_id` —
    # vale para quem leciona alguma oferta ativa da turma; quem só é o professor
    # cadastrado da turma (sem oferta própria) perde a entrada.
    if (
        current_user.role == UserRole.PROFESSOR
        and not professor_de_alguma_oferta_ativa(id, current_user)
    ):
        abort(403)

    # Etapa M1: turma vem das ofertas ATIVAS (salvar antes do ctx, que agita
    # a sessão via carregar_contexto_turma). Modal: 0 ofertas = aviso e envio
    # bloqueado; 1 = tela como hoje; 2+ = seletor de curso e lista filtrada
    # pela oferta escolhida (?oferta_sel=).
    ofertas_lista = ofertas_ativas(id)
    ofertas_lista.sort(key=lambda oferta: (not oferta.principal, oferta.id))
    ofertas_todas = (
        TurmaCurso.query.options(
            joinedload(TurmaCurso.curso),
            joinedload(TurmaCurso.professor),
            selectinload(TurmaCurso.horarios),
        )
        .filter_by(turma_id=id)
        .order_by(TurmaCurso.principal.desc(), TurmaCurso.ativo.desc(), TurmaCurso.id)
        .all()
    )
    # Grade de exibição em lote (H3d): um único selectinload acima, sem N+1.
    grade_oferta_map = grades_para_exibicao(ofertas_todas)
    oferta_principal = next(
        (oferta for oferta in ofertas_lista if oferta.principal),
        ofertas_lista[0] if len(ofertas_lista) == 1 else None,
    )
    # AJ6-B4: "centro de custo compartilhado" do topo da ficha vem da oferta
    # PRINCIPAL. Para o professor, se essa oferta não é dele (é de outro), o
    # campo não pode ser mostrado nem como "Não definido" — revela que há uma
    # oferta com centro de custo que ele não leciona. REGRA ÚNICA
    # `professor_pode_acessar_oferta` (demais perfis sempre True: inalterado).
    oferta_principal_do_professor = professor_pode_acessar_oferta(
        current_user, oferta_principal
    )
    ofertas_todas.sort(
        key=lambda oferta: (
            oferta.id != (oferta_principal.id if oferta_principal else None),
            not oferta.ativo,
            oferta.id,
        )
    )

    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash(
            "O contexto da turma contém erros e não pode ser gerado. Reporte ao Suporte.",
            "danger",
        )
        # AJ6-B5: o professor não acessa a lista /turma (403); na falha de contexto
        # devolva-o ao painel. Demais perfis seguem para a lista.
        if current_user.role == UserRole.PROFESSOR:
            return redirect(url_for("main.painel"))
        return redirect(url_for("registros.turma"))

    # O join da pauta pode repetir o aluno quando ele está em mais de uma
    # oferta. A ficha da turma lista a pessoa uma vez e mostra cada vínculo.
    ctx["alunos"] = list({aluno.id: aluno for aluno in ctx.get("alunos", [])}.values())

    if len(ofertas_lista) == 1:
        oferta_sel = ofertas_lista[0]
    elif len(ofertas_lista) >= 2:
        sel_id = request.args.get("oferta_sel", type=int)
        oferta_sel = next(
            (o for o in ofertas_lista if o.id == sel_id), None
        )
    else:
        oferta_sel = None

    if oferta_sel is not None:
        # Disponível para a oferta = sem inscrição ATIVA naquela oferta
        # (pode ter inscrição ativa em outra oferta da mesma turma).
        alunos_disponiveis = Aluno.query.filter(
            Aluno.ativo.is_(True),
            ~Aluno.inscricoes.any(
                (Inscricao.turma_id == id)
                & (Inscricao.turma_curso_id == oferta_sel.id)
                & (Inscricao.ativo.is_(True))
            ),
        )
        if turma_obj.unidade_id:
            alunos_disponiveis = alunos_disponiveis.filter(
                Aluno.unidade_id == turma_obj.unidade_id
            )
        alunos_disponiveis = alunos_disponiveis.order_by(Aluno.nome).all()
    else:
        alunos_disponiveis = []
    alunos_ativos_count = (
        Aluno.query.join(Inscricao)
        .filter(Inscricao.turma_id == id, Inscricao.ativo == True, Aluno.ativo == True)
        .distinct()
        .count()
    )
    # Busca os níveis cadastrados pela unidade para o modal de enturmação.
    # Inclui níveis legados sem unidade (unidade_id IS NULL) para compatibilidade.
    niveis_cadastrados = (
        Nivel.query
        .filter(
            (Nivel.unidade_id == turma_obj.unidade_id) | (Nivel.unidade_id == None),
            Nivel.ativo == True,
        )
        .order_by(Nivel.nome)
        .all()
    )
    # Lista de alunos agrupada pela oferta; a ficha mantém cada vínculo como
    # linha própria dentro do painel recolhível do curso correspondente.
    alunos_por_oferta = {oferta.id: [] for oferta in ofertas_todas}
    for inscricao in (
        Inscricao.query.options(joinedload(Inscricao.aluno))
        .join(TurmaCurso, TurmaCurso.id == Inscricao.turma_curso_id)
        .filter(Inscricao.turma_id == id, Inscricao.ativo.is_(True))
        .order_by(TurmaCurso.id, Inscricao.id)
        .all()
    ):
        alunos_por_oferta.setdefault(inscricao.turma_curso_id, []).append(inscricao)

    # AJ6-B3 (decisão 1): para o professor a ficha é a da SUA oferta. A régua de
    # entrada acima (adesão: leciona alguma oferta ativa da turma) fica
    # inalterada; o que sai do payload/HTML passa a ser restrito às ofertas que
    # ele pode acessar — pela REGRA ÚNICA `ofertas_do_professor` (que envolve
    # `professor_pode_acessar_oferta`), sem duplicar a checagem aqui. Demais
    # perfis seguem vendo a turma inteira (guarda de papel + unidade).
    if current_user.role == UserRole.PROFESSOR:
        from app.services.aluno_info_professor import ofertas_do_professor

        ids_do_professor = [o.id for o in ofertas_do_professor(current_user, ofertas_todas)]
        ativos_do_professor = {o.id for o in ofertas_do_professor(current_user, ofertas_lista)}
        grade_oferta_map = {
            chave: valor for chave, valor in grade_oferta_map.items()
            if chave in ids_do_professor
        }
        alunos_disponiveis = []
        alunos_ativos_count = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == id,
                Inscricao.ativo.is_(True),
                Aluno.ativo.is_(True),
                Inscricao.turma_curso_id.in_(ids_do_professor or [-1]),
            )
            .distinct()
            .count()
        )
        ctx["alunos"] = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == id,
                Inscricao.ativo.is_(True),
                Aluno.ativo.is_(True),
                Inscricao.turma_curso_id.in_(ids_do_professor or [-1]),
            )
            .order_by(Aluno.nome)
            .all()
        )
        calcular_idades(ctx["alunos"])
        # Agenda e seletor de mês só das ofertas dele (vigência e dias próprios).
        datas_professor = sorted({
            data_aula.strftime("%Y-%m-%d")
            for oferta in ofertas_lista
            if oferta.id in ativos_do_professor
            for data_aula in datas_aula_oferta(
                oferta, blocked=_blocked_dates_str(turma_obj),
            )
        })
        ctx["datas"] = datas_professor
        ctx["meses"] = meses_de_datas(datas_professor)
        cursos_do_professor = {
            o.curso_id for o in ofertas_todas if o.id in ids_do_professor
        }
        ctx["temas"] = (
            TemaAula.query.filter(
                TemaAula.curso_id.in_(cursos_do_professor or [-1]),
                TemaAula.ativo.is_(True),
            ).all()
        )
        ofertas_todas = [o for o in ofertas_todas if o.id in ids_do_professor]
        ofertas_lista = [o for o in ofertas_lista if o.id in ativos_do_professor]
        if oferta_sel is not None and oferta_sel.id not in ativos_do_professor:
            oferta_sel = None
        alunos_por_oferta = {
            chave: valor for chave, valor in alunos_por_oferta.items()
            if chave in ids_do_professor
        }

    # AJ18-B: pergunta de data de entrada quando a oferta selecionada já começou.
    entrada_hoje = get_local_now().date()
    oferta_entrada = oferta_sel
    entrada_obrigatoria = False
    entrada_ini_iso = None
    entrada_fim_iso = None
    if oferta_entrada is not None:
        ini_eff = inicio_efetivo(oferta_entrada)
        fim_eff = oferta_entrada.data_fim or (oferta_entrada.turma.data_fim if oferta_entrada.turma else None)
        entrada_ini_iso = ini_eff.isoformat() if ini_eff else None
        entrada_fim_iso = fim_eff.isoformat() if fim_eff else None
        if ini_eff and entrada_hoje > ini_eff:
            entrada_obrigatoria = True

    return render_template(
        "turmas/detalhe.html",
        alunos_sem_turma=alunos_disponiveis,
        alunos_ativos_count=alunos_ativos_count,
        niveis_cadastrados=niveis_cadastrados,
        ofertas=ofertas_lista,
        ofertas_todas=ofertas_todas,
        oferta_principal=oferta_principal,
        oferta_principal_do_professor=oferta_principal_do_professor,
        oferta_sel=oferta_sel,
        alunos_por_oferta=alunos_por_oferta,
        grade_oferta_map=grade_oferta_map,
        # E3: ofertas ativas do professor logado (vazio p/ os demais perfis) —
        # o detalhe usa para mostrar só os links de pauta/Diário que ele abre.
        ofertas_do_professor=(
            [o for o in ofertas_lista if professor_da_oferta(o, current_user)]
            if current_user.role == UserRole.PROFESSOR
            else []
        ),
        abrir_modal_enturmar=request.args.get("modal") == "enturmar",
        entrada_obrigatoria=entrada_obrigatoria,
        entrada_hoje_iso=entrada_hoje.isoformat(),
        entrada_ini_iso=entrada_ini_iso,
        entrada_fim_iso=entrada_fim_iso,
        **ctx,
    )


@bp.route("/turma/enturmar/<int:turma_id>", methods=["POST"])
@login_required
def enturmar_alunos(turma_id):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
    ):
        abort(403)

    unidade_id = get_unidade_id()
    turma_obj = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma_obj.unidade_id, unidade_id)

    # Etapa M1: aluno só é enturmado em curso (oferta). A oferta destino é
    # resolvida pela contagem de ofertas ativas da turma.
    ofertas = ofertas_ativas(turma_obj.id)
    if not ofertas:
        flash(
            "Esta turma ainda não tem curso. Cadastre um curso em "
            "Cursos da Turma antes de enturmar alunos.",
            "warning",
        )
        return redirect(url_for("registros.ver_turma", id=turma_id))

    if len(ofertas) == 1:
        # Oferta única: grava nela, sem exigir escolha na tela.
        oferta_sel = ofertas[0]
        oferta_id = oferta_sel.id
    else:
        # 2+ ofertas: turma_curso_id é obrigatório no POST e precisa apontar
        # para oferta ativa da própria turma (a unidade já foi validada na
        # turma; ofertas_ativas só devolve ofertas ativas dela).
        oferta_id = request.form.get("turma_curso_id", type=int)
        oferta_sel = next((o for o in ofertas if o.id == oferta_id), None)
        if oferta_sel is None:
            flash(
                "Selecione o curso (oferta) em que os alunos serão enturmados.",
                "warning",
            )
            return redirect(url_for("registros.ver_turma", id=turma_id))

    aluno_ids = request.form.getlist("aluno_ids[]")

    aluno_ids_int = [int(x) for x in aluno_ids if str(x).isdigit()]
    if aluno_ids_int:
        try:
            alunos = Aluno.query.filter(Aluno.id.in_(aluno_ids_int))
            if turma_obj.unidade_id:
                alunos = alunos.filter(Aluno.unidade_id == turma_obj.unidade_id)
            alunos = alunos.all()
            # AJ18-B: quando a oferta já começou, a escolha de entrada é obrigatória
            # para CADA aluno selecionado do lote (recusa atômica se faltar),
            # mesmo que nenhum campo entrada_* seja enviado no POST. Oferta não
            # iniciada -> NULL sem perguntar.
            hoje_ent = get_local_now().date()
            ini_eff = inicio_efetivo(oferta_sel)
            entrada_obrigatoria = bool(ini_eff and hoje_ent > ini_eff)
            enturmados = 0
            acoes = []
            for aluno in alunos:
                nivel_form = request.form.get(f"nivel_{aluno.id}")
                nivel_val = None if nivel_form == "Não se aplica" else nivel_form

                if nivel_form:
                    aluno.nivel = nivel_val

                # AJ18-B: data de entrada do aluno na oferta.
                if entrada_obrigatoria:
                    entrada_raw = request.form.get(f"entrada_{aluno.id}")
                    if not entrada_raw:
                        flash(
                            "Informe a data de entrada na oferta para todos os alunos selecionados.",
                            "warning",
                        )
                        db.session.rollback()
                        return redirect(
                            url_for(
                                "registros.ver_turma",
                                id=turma_id,
                                oferta_sel=oferta_sel.id,
                                modal="enturmar",
                            )
                        )
                    try:
                        data_entrada, rotulo_entrada = parse_escolha_entrada(
                            entrada_raw, oferta_sel, hoje_ent
                        )
                    except ValueError as e:
                        flash(str(e), "warning")
                        db.session.rollback()
                        return redirect(
                            url_for(
                                "registros.ver_turma",
                                id=turma_id,
                                oferta_sel=oferta_sel.id,
                                modal="enturmar",
                            )
                        )
                else:
                    data_entrada, rotulo_entrada = None, "desde o início"

                # ETAPA M2: duplicidade e criação concentradas no serviço
                # único de enturmação. Duplicata ativa na mesma oferta segue
                # como salto silencioso (sem flash), como antes; em outra
                # oferta da turma, o aluno pode ter nova inscrição ativa.
                try:
                    insc = enturmar_aluno(
                        aluno,
                        turma_obj,
                        oferta_id,
                        nivel=nivel_val,
                        data_inicio=hoje_ent,
                        data_entrada=data_entrada,
                    )
                except ValueError as e:
                    if str(e) != MSG_JA_ENTURMADO:
                        flash(str(e), "warning")
                        db.session.rollback()
                        return redirect(
                            url_for(
                                "registros.ver_turma",
                                id=turma_id,
                                oferta_sel=oferta_sel.id,
                                modal="enturmar",
                            )
                        )
                    continue
                enturmados += 1
                acoes.append((aluno, insc, rotulo_entrada))

            # LogAcao por aluno enturmado com a data escolhida.
            if acoes:
                try:
                    from app.models import LogAcao
                except Exception:
                    LogAcao = None
                if LogAcao is not None:
                    for aluno_log, _, rotulo_entrada in acoes:
                        db.session.add(
                            LogAcao(
                                usuario_id=current_user.id,
                                usuario_nome=getattr(current_user, "name", None),
                                acao="Enturmação de aluno na oferta",
                                detalhes=(
                                    f"aluno_id={aluno_log.id} nome=\"{aluno_log.nome}\" "
                                    f"turma_id={turma_obj.id} oferta_id={oferta_sel.id} "
                                    f"entrada={rotulo_entrada}"
                                ),
                                ip=request.remote_addr,
                                unidade_id=turma_obj.unidade_id,
                            )
                        )

            db.session.commit()
            flash(
                f"{enturmados} aluno(s) inscrito(s) em {oferta_sel.curso.nome} "
                f"na turma {turma_obj.nome}!",
                "success",
            )
        except Exception:
            db.session.rollback()
            raise
    else:
        flash("Rejeitado: Nenhum aluno foi parametrizado.", "warning")

    return redirect(url_for("registros.ver_turma", id=turma_id))


def _editar_turma_contexto(turma_obj, rascunho=None):
    """Contexto do formulário de edição de turma (GET e re-render do POST — H4).

    Além do contexto histórico, expõe a agenda em termos do H4:
    ``dias_agenda`` (Segunda–Sábado, weekday 0–5), ``grade_atual`` (linhas da
    oferta única — pré-preenchem o modo personalizado) e
    ``agenda_nao_uniforme``. O critério de bloqueio passa a ser apenas "2+
    ofertas": turma com 1 oferta e grade não uniforme é EDITÁVEL pelo mesmo
    componente (decisão H4).
    """
    unidade_id = get_unidade_id()
    stmt_prof = select(User).where(User.role == "professor")
    if unidade_id:
        stmt_prof = stmt_prof.where(User.unidade_id == unidade_id)
    elif turma_obj.unidade_id:
        stmt_prof = stmt_prof.where(User.unidade_id == turma_obj.unidade_id)
    professores = db.session.execute(stmt_prof.order_by(User.name)).scalars().all()
    periodos = (
        PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True)
        .order_by(PeriodoLetivo.nome)
        .all()
        if unidade_id
        else []
    )
    periodo_ativo = turma_obj.periodo_letivo
    centros_custo = (
        [c.strip() for c in periodo_ativo.centro_custo.split(",")]
        if periodo_ativo and periodo_ativo.centro_custo
        else []
    )
    cursos = (
        Curso.query.filter_by(
            ativo=True, unidade_id=unidade_id or turma_obj.unidade_id
        )
        .order_by(Curso.nome)
        .all()
    )
    if turma_obj.curso and not turma_obj.curso.ativo:
        cursos.append(turma_obj.curso)
        cursos.sort(key=lambda curso: curso.nome.casefold())
    periodos_centros_edit = {
        str(p.id): (
            [c.strip() for c in p.centro_custo.split(",")] if p.centro_custo else []
        )
        for p in periodos
    }
    tem_lancamentos = bool(
        Frequencia.query.filter_by(turma_id=turma_obj.id).first()
        or RegistroAula.query.filter_by(turma_id=turma_obj.id).first()
    )
    # Onda 4 (Fase 4, G3): ofertas ativas para o bloco "Cursos desta turma".
    ofertas = ofertas_ativas(turma_obj.id)
    n_ofertas = len(ofertas)
    # H4: o bloqueio de agenda é apenas "2+ ofertas".
    agenda_bloqueada = n_ofertas >= 2
    grade_atual = grade_da_oferta(ofertas[0]) if n_ofertas == 1 else []
    if rascunho is not None and n_ofertas == 1:
        estado_agenda = _estado_agenda_do_form(rascunho)
    else:
        # H5a: turma com 0 ofertas não tem agenda (ela nasce com a oferta) e
        # com 1 oferta o estado vem só da grade dela.
        estado_agenda = _estado_agenda_da_grade(grade_atual)
    return dict(
        turma=turma_obj,
        professores=professores,
        programas=list(_PROGRAMAS_OFERTA),
        periodos=periodos,
        periodo_ativo=periodo_ativo,
        periodos_centros_edit=periodos_centros_edit,
        centros_custo=centros_custo,
        cursos=cursos,
        tem_lancamentos=tem_lancamentos,
        ofertas=ofertas,
        n_ofertas=n_ofertas,
        agenda_bloqueada=agenda_bloqueada,
        dias_agenda=list(_DIAS_AGENDA),
        grade_atual=grade_atual,
        estado_agenda=estado_agenda,
        grade_original=_serializar_estado_agenda(estado_agenda),
        agenda_nao_uniforme=bool(grade_atual) and not grade_uniforme(ofertas[0]),
    )


@bp.route("/turma/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_turma(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    unidade_id = get_unidade_id()
    assert_unidade_context(turma_obj.unidade_id, unidade_id)

    if request.method == "POST":
        avisos_horario = []
        try:
            limpar_lancamentos = request.form.get("limpar_lancamentos") == "1"
            novo_data_inicio_raw = request.form.get("data_inicio") or ""
            novo_data_fim_raw = request.form.get("data_fim") or ""

            # H4: a agenda vem do parsing único dos formulários (mesmo
            # contrato das rotas de oferta — a turma com 1 oferta usa o
            # mesmo componente, inclusive o modo personalizado).
            # H5a: com 0 ofertas o formulário não tem campos de agenda e o
            # POST os ignora; nenhuma coluna escalar é lida ou escrita.
            grade = grade_do_formulario(request.form)

            # Onda 2A: parse uma vez, use como `date` na comparação abaixo.
            novo_data_inicio_date = parse_date(novo_data_inicio_raw)
            novo_data_fim_date = parse_date(novo_data_fim_raw)

            # --- Onda 4 (Fase 4, G2): classificação das ofertas da turma ---
            ativas = ofertas_ativas(id)
            n_ativas = len(ativas)
            oferta_única = ativas[0] if n_ativas == 1 else None

            # H4: com oferta ÚNICA a agenda é sempre editável por este
            # formulário — grade não uniforme é aceita (modo personalizado).
            # O bloqueio de agenda é apenas "2+ ofertas" (REGRA 4 abaixo);
            # a decisão é tomada ANTES de qualquer escrita.
            if oferta_única is not None and _erro_agenda_formulario(grade):
                flash(grade["erro"], "warning")
                return render_template(
                    "turmas/editar.html",
                    **_editar_turma_contexto(turma_obj, rascunho=request.form),
                    rascunho=request.form,
                )
            itens_grade_única: list | None = grade["itens"]
            if oferta_única is not None:
                atuais = sorted(
                    (l.dia_semana, l.hora_inicio, l.hora_fim)
                    for l in grade_da_oferta(oferta_única)
                )
                mudou_agenda = (
                    itens_grade_única is not None
                    and sorted(itens_grade_única) != atuais
                )
            else:
                # H5a: sem oferta não há agenda na turma — a agenda nasce com
                # a oferta e o POST não escreve nada de dias/horários.
                mudou_agenda = False

            # Campos "de oferta" vindos do POST (professor/turno/centro/curso).
            novo_professor_raw = request.form.get("professor_id") or None
            novo_turno = request.form.get("turno")
            novo_centro_custo = request.form.get("centro_custo") or None
            curso_id = request.form.get("curso_id")
            novo_curso_id = _parse_int_arg(curso_id)
            if curso_id and novo_curso_id is None:
                flash("Curso inválido.", "warning")
                return redirect(url_for("registros.editar_turma", id=id))

            # REGRA 3 (1 oferta ativa): trocar o curso exige mexer nas ofertas.
            # Verificado ANTES de qualquer gravação — nada é alterado aqui.
            if (
                oferta_única is not None
                and novo_curso_id != oferta_única.curso_id
            ):
                flash(
                    "Para trocar o curso, desative a oferta e cadastre outra em "
                    "Cursos da Turma.",
                    "warning",
                )
                return redirect(url_for("registros.editar_turma", id=id))

            # REGRA 4 (2+ ofertas ativas): ignora os campos de oferta no
            # servidor; avisa se algum divergiu e grava só o resto da turma.
            if n_ativas >= 2:
                def _diff_professor():
                    if not novo_professor_raw:
                        return turma_obj.professor_id is not None
                    try:
                        return int(novo_professor_raw) != turma_obj.professor_id
                    except (TypeError, ValueError):
                        return True

                divergiu_oferta = (
                    novo_curso_id != turma_obj.curso_id
                    or _diff_professor()
                    or novo_turno != turma_obj.turno
                    or novo_data_inicio_date != turma_obj.data_inicio
                    or novo_data_fim_date != turma_obj.data_fim
                    or novo_centro_custo != turma_obj.centro_custo
                )
                if divergiu_oferta:
                    flash(
                        "Os dados de curso, professor, turno, horários e datas são "
                        "editados em Cursos da Turma.",
                        "info",
                    )
                dados_de_lancamento_alterados = False

                turma_obj.nome = request.form.get("turma")

                original_periodo_id = turma_obj.periodo_letivo_id
                novo_periodo_id = request.form.get("periodo_letivo_id")
                novo_periodo_id = (
                    int(novo_periodo_id)
                    if novo_periodo_id and novo_periodo_id.isdigit()
                    else None
                )
                turma_obj.periodo_letivo_id = novo_periodo_id
                periodo_obj = (
                    db.session.get(PeriodoLetivo, novo_periodo_id)
                    if novo_periodo_id
                    else turma_obj.periodo_letivo
                )
                if novo_periodo_id and (
                    not periodo_obj or periodo_obj.unidade_id != unidade_id
                ):
                    flash(
                        "Período letivo inválido para a unidade selecionada.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))
                if original_periodo_id != novo_periodo_id or not turma_obj.ordenacao:
                    turma_obj.ordenacao = obter_proximo_ordenacao(novo_periodo_id)

                # Turma.programa é projeção da oferta principal ativa (MER
                # §8.10) e não é editável de forma independente: reprojeta em
                # vez de ler o campo do formulário (defeito P4).
                sincronizar_programa_turma(turma_obj)

                db.session.commit()
                flash(
                    f"Alterações da turma '{turma_obj.nome}' foram salvas!",
                    "success",
                )
                return redirect(url_for("registros.turma"))

            # --- REGRAS 2 (sem oferta) e 3 (1 oferta): fluxo atual ---
            dados_de_lancamento_alterados = (
                mudou_agenda
                or novo_data_inicio_date != turma_obj.data_inicio
                or novo_data_fim_date != turma_obj.data_fim
            )

            if dados_de_lancamento_alterados:
                lancamentos_existentes = bool(
                    Frequencia.query.filter_by(turma_id=id).first()
                    or RegistroAula.query.filter_by(turma_id=id).first()
                )
                if lancamentos_existentes and not limpar_lancamentos:
                    flash(
                        "Alterar dias ou datas exige confirmação para limpar os lançamentos existentes.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))

            # E2/G1: com oferta única o professor da turma é espelhado na oferta,
            # então a troca obedece a mesma regra da tela de cursos: com
            # lançamento gravado exige confirmação explícita (conferida antes de
            # qualquer escrita).
            if oferta_única is not None:
                _prof_candidato = _parse_int_arg(novo_professor_raw)
                if (
                    _prof_candidato
                    and _prof_candidato != oferta_única.professor_id
                    and oferta_tem_lancamentos(oferta_única.id)
                    and request.form.get("confirmar_troca_professor") != "1"
                ):
                    flash(MSG_TROCA_PROFESSOR_COM_LANCAMENTO, "warning")
                    return redirect(url_for("registros.editar_turma", id=id))

            turma_obj.nome = request.form.get("turma")
            turma_obj.turno = novo_turno
            turma_obj.data_inicio = novo_data_inicio_date
            turma_obj.data_fim = novo_data_fim_date
            # H5a: a agenda da turma NUNCA é escrita direto — nem com oferta
            # única (a grade da oferta é a única fonte) nem sem oferta (a
            # agenda nasce com a oferta, em Cursos da Turma).
            # E2: inteiro normalizado — o espelho para a oferta compara ids.
            turma_obj.professor_id = _parse_int_arg(novo_professor_raw)

            original_periodo_id = turma_obj.periodo_letivo_id
            novo_periodo_id = request.form.get("periodo_letivo_id")
            novo_periodo_id = (
                int(novo_periodo_id)
                if novo_periodo_id and novo_periodo_id.isdigit()
                else None
            )
            turma_obj.periodo_letivo_id = novo_periodo_id

            professor_id = turma_obj.professor_id
            periodo_obj = (
                db.session.get(PeriodoLetivo, novo_periodo_id)
                if novo_periodo_id
                else turma_obj.periodo_letivo
            )
            if novo_periodo_id and (
                not periodo_obj or periodo_obj.unidade_id != unidade_id
            ):
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.editar_turma", id=id))

            if professor_id:
                professor = db.session.get(User, int(professor_id))
                if (
                    not professor
                    or professor.role != "professor"
                    or (periodo_obj and professor.unidade_id != periodo_obj.unidade_id)
                ):
                    flash(
                        "Professor inválido para esta unidade ou período letivo.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))

            centro_custo = novo_centro_custo
            if centro_custo and novo_periodo_id:
                periodo_obj = db.session.get(PeriodoLetivo, novo_periodo_id)
                centros_disponiveis = (
                    [c.strip() for c in periodo_obj.centro_custo.split(",")]
                    if periodo_obj and periodo_obj.centro_custo
                    else []
                )
                if centros_disponiveis and centro_custo not in centros_disponiveis:
                    flash(
                        "Centro de custo inválido para o período selecionado.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))
            turma_obj.centro_custo = centro_custo

            if original_periodo_id != novo_periodo_id or not turma_obj.ordenacao:
                turma_obj.ordenacao = obter_proximo_ordenacao(novo_periodo_id)

            if limpar_lancamentos and dados_de_lancamento_alterados:
                Frequencia.query.filter_by(turma_id=id).delete(
                    synchronize_session=False
                )
                RegistroAula.query.filter_by(turma_id=id).delete(
                    synchronize_session=False
                )

            # Curso: 1 oferta já foi validada acima (só mantém o mesmo curso);
            # sem oferta, aplica-se a validação e a gravação atuais.
            if oferta_única is not None:
                turma_obj.curso_id = novo_curso_id
            elif novo_curso_id is not None:
                curso = db.get_or_404(Curso, novo_curso_id)
                mesma_unidade = curso.unidade_id == turma_obj.unidade_id
                curso_atual_inativo = (
                    novo_curso_id == turma_obj.curso_id and not curso.ativo
                )
                if not mesma_unidade or (not curso.ativo and not curso_atual_inativo):
                    flash(
                        "Selecione um curso ativo da unidade. O curso inativo só pode "
                        "ser mantido na turma que já possui esse vínculo.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))
                turma_obj.curso_id = novo_curso_id
            else:
                turma_obj.curso_id = novo_curso_id

            # REGRA 3 (1 oferta ativa): espelha na oferta exatamente o que foi
            # gravado na turma. Conflitos de horário geram apenas aviso; não
            # impedem a gravação transacional de turma e oferta. Desde o H2 os
            # dias/horários vão para a oferta via definir_grade (única fonte);
            # no H4 a grade pode ser NÃO uniforme (modo personalizado) e no H5a
            # a rota não toca em coluna escalar de agenda.
            if oferta_única is not None:
                if mudou_agenda and itens_grade_única is not None:
                    # Concomitância só faz sentido com a grade candidata em
                    # mãos; com oferta única não há concorrente ativo.
                    avisos_horario = _conflitos_horario_concomitante(
                        id,
                        agenda=itens_grade_única,
                        data_inicio=turma_obj.data_inicio,
                        data_fim=turma_obj.data_fim,
                        exclude_oferta_id=oferta_única.id,
                    )
                # E2/G1: a OFERTA é a fonte do professor (regra "sem herança"):
                # esvaziar o campo da turma não zera a oferta — o que volta para
                # a turma é o professor da oferta. A troca fica auditável no
                # log (anterior e novo, com id e nome).
                professor_anterior = oferta_única.professor_id
                if turma_obj.professor_id:
                    if turma_obj.professor_id != professor_anterior:
                        gravar_troca_professor_da_oferta(
                            oferta_única.id, professor_anterior,
                            turma_obj.professor_id,
                            usuario_id=current_user.id,
                            usuario_nome=current_user.name,
                            ip=request.remote_addr,
                            unidade_id=turma_obj.unidade_id,
                        )
                    oferta_única.professor_id = turma_obj.professor_id
                elif professor_anterior:
                    turma_obj.professor_id = professor_anterior
                oferta_única.turno = turma_obj.turno
                if mudou_agenda and itens_grade_única is not None:
                    definir_grade(oferta_única, itens_grade_única)
                oferta_única.data_inicio = turma_obj.data_inicio
                oferta_única.data_fim = turma_obj.data_fim
                oferta_única.centro_custo = turma_obj.centro_custo

                sincronizar_programa_turma(turma_obj)
            else:
                sincronizar_programa_turma(turma_obj)
            db.session.commit()

            for aviso in avisos_horario:
                flash(aviso, "warning")

            # Verificar inconsistências após salvar (H5a: o critério é haver
            # oferta com agenda — não mais a coluna `dias_semana` da turma).
            tem_ofertas = bool(ofertas_ativas(id))
            ch_total = turma_obj.carga_horaria_total
            dias_efetivos = turma_obj.dias_aula_efetivos()

            if tem_ofertas and ch_total is None:
                flash(
                    "Aviso: C.H. não pôde ser calculada — verifique os horários de início e fim.",
                    "warning"
                )
                return redirect(url_for("registros.editar_turma", id=id))

            if tem_ofertas and turma_obj.data_inicio and turma_obj.data_fim and dias_efetivos == 0:
                flash(
                    "Aviso: 0 dias de aula encontrados — verifique os dias da semana e o período letivo (todos os dias podem estar bloqueados).",
                    "warning"
                )
                return redirect(url_for("registros.editar_turma", id=id))

            flash(f"Alterações da turma '{turma_obj.nome}' foram salvas!", "success")
            return redirect(url_for("registros.turma"))
        except Exception:
            db.session.rollback()
            flash("Erro durante commit do formulário no banco.", "danger")

    return render_template(
        "turmas/editar.html", **_editar_turma_contexto(turma_obj)
    )


# ---------------------------------------------------------------------------
# Onda 4 — Fase 2: ofertas de curso na turma (TurmaCurso), cadastro incremental
# e regra do curso principal. As colunas legadas de Turma seguem intocadas
# aqui; o espelhamento controlado vive em app/services/turma_curso.py.
# ---------------------------------------------------------------------------


def _turma_para_ofertas(id):
    """Carrega a turma validando papel e unidade (padrão das rotas de turmas)."""
    if current_user.role not in ["admin", "pedagogico", "secretaria", "gerencia"]:
        abort(403)
    turma_obj = db.session.get(Turma, id)
    if turma_obj is None:
        abort(404)
    assert_unidade_context(turma_obj.unidade_id, get_unidade_id())
    return turma_obj


def _dados_oferta_form(form, turma_obj, grade: dict | None = None):
    """Extrai os campos de oferta do POST usando os mesmos parseadores do
    cadastro de turma (datas nativas — Onda 2A).

    H4: a agenda sai de ``grade_do_formulario``. Quando o formulário traz uma
    grade completa (modo padrão) ou está em modo personalizado, vai
    ``agenda=[(weekday, início, fim)]`` — única fonte do serviço. Sem agenda ou
    com agenda parcial, mantém-se o envio do trio escalar (herança/aviso do
    serviço), exatamente como antes do H4.
    """
    grade = grade_do_formulario(form) if grade is None else grade
    periodo_obj = turma_obj.periodo_letivo
    data_inicio = parse_date(form.get("data_inicio"))
    data_fim = parse_date(form.get("data_fim"))
    if periodo_obj:
        if data_inicio and data_inicio < periodo_obj.data_inicio:
            raise ValueError(
                "A data de início não pode ser anterior ao início do período letivo."
            )
        if data_fim and data_fim > periodo_obj.data_fim:
            raise ValueError(
                "A data de término não pode ser posterior ao fim do período letivo."
            )
    centro_custo = form.get("centro_custo") or None
    programa = (form.get("programa") or "").strip()
    if not programa:
        raise ValueError("Selecione o programa da oferta.")
    if centro_custo and periodo_obj and periodo_obj.centro_custo:
        centros_disponiveis = [
            c.strip() for c in periodo_obj.centro_custo.split(",")
        ]
        if centros_disponiveis and centro_custo not in centros_disponiveis:
            raise ValueError("Centro de custo inválido para o período selecionado.")
    dados = {
        "curso_id": _parse_int_arg(form.get("curso_id")),
        "principal": form.get("principal") == "on",
        "professor_id": _parse_int_arg(form.get("professor_id")),
        "turno": form.get("turno") or None,
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "centro_custo": centro_custo,
        "programa": programa,
    }
    if grade["por_dia"]:
        # Modo personalizado: ou a grade por dia está completa, ou erro claro.
        if grade["erro"]:
            raise ValueError(grade["erro"])
        dados["agenda"] = grade["itens"]
    elif grade["itens"] is not None:
        dados["agenda"] = grade["itens"]
    # Sem agenda no formulário: o serviço decide (herança da grade de outra
    # oferta ou erro de agenda incompleta). H5a: nenhum campo escalar de
    # agenda é enviado.
    return dados


def _ofertas_de_agenda_da_turma(turma_obj):
    """Contexto de agenda da tela de cursos: ofertas, grade por dia e exibição.

    ``linhas`` (``grades_por_oferta``) pré-preenche o formulário por dia; com
    grade NÃO uniforme o modo personalizado já abre preenchido (decisão H4).
    ``grade_map`` é a ``GradeExibicao`` da tabela (não a projeção).
    """
    ofertas = (
        TurmaCurso.query.filter_by(turma_id=turma_obj.id)
        .order_by(TurmaCurso.ativo.desc(), TurmaCurso.id)
        .all()
    )
    linhas = grades_por_oferta(ofertas)
    grade_map = grades_para_exibicao(ofertas, grades=linhas)
    return ofertas, linhas, grade_map


def _render_ofertas(turma_obj, *, rascunho=None, oferta_aberta=None, status=200):
    """ReRenderiza a tela de cursos com o formulário voltado preenchido (H4).

    Usado quando a validação da agenda recusa o POST: o usuário mantém o que
    digitou (inclusive o modo personalizado aberto) e o flash já gravado
    aparece normalmente.
    """
    unidade_id = turma_obj.unidade_id
    professores = (
        User.query.filter_by(role=UserRole.PROFESSOR.value, unidade_id=unidade_id)
        .order_by(User.name)
        .all()
    )
    ids_ofertados = {o.curso_id for o in ofertas_ativas(turma_obj.id)}
    cursosDisponiveis = [
        c for c in Curso.query.filter_by(ativo=True, unidade_id=unidade_id)
        .order_by(Curso.nome).all()
        if c.id not in ids_ofertados
    ]
    centros = (
        [c.strip() for c in turma_obj.periodo_letivo.centro_custo.split(",")]
        if turma_obj.periodo_letivo and turma_obj.periodo_letivo.centro_custo
        else []
    )
    ofertas, linhas, grade_map = _ofertas_de_agenda_da_turma(turma_obj)
    # E2: quais ofertas têm lançamento gravado — são as que pedem confirmação
    # para trocar o professor (o servidor repete a checagem).
    ofertas_lancadas = ofertas_com_lancamentos([o.id for o in ofertas])
    # Estado do componente de agenda por formulário (H4): o POST rejeitado
    # volta como o usuário digitou; os demais formulários partem da grade.
    estados_oferta = {}
    for oferta_item in ofertas:
        if not oferta_item.ativo:
            continue
        if rascunho is not None and oferta_aberta == oferta_item.id:
            estados_oferta[oferta_item.id] = _estado_agenda_do_form(rascunho)
        else:
            estados_oferta[oferta_item.id] = _estado_agenda_da_grade(
                linhas.get(oferta_item.id) or []
            )
    estado_nova = (
        _estado_agenda_do_form(rascunho)
        if rascunho is not None and oferta_aberta == "nova"
        else _estado_agenda()
    )
    return render_template(
        "turmas/ofertas.html",
        turma=turma_obj,
        ofertas=ofertas,
        professores=professores,
        cursosDisponiveis=cursosDisponiveis,
        centros=centros,
        dias_semana=[weekday_para_nome(d) for d in _DIAS_AGENDA],
        dias_agenda=list(_DIAS_AGENDA),
        grade_linhas=linhas,
        grade_map=grade_map,
        estados_oferta=estados_oferta,
        estado_nova=estado_nova,
        ofertas_lancadas=ofertas_lancadas,
        rascunho=rascunho,
        oferta_aberta=oferta_aberta,
    ), status


@bp.route("/turma/<int:id>/ofertas")
@login_required
def turma_ofertas(id):
    """Tela de cursos da turma: lista de ofertas + formulário incremental."""
    turma_obj = _turma_para_ofertas(id)
    return _render_ofertas(turma_obj)


@bp.route("/turma/<int:id>/ofertas/nova", methods=["POST"])
@login_required
def turma_oferta_nova(id):
    """Adiciona uma oferta de curso à turma (cadastro incremental, sem limite)."""
    turma_obj = _turma_para_ofertas(id)
    grade = grade_do_formulario(request.form)
    if _erro_agenda_formulario(grade):
        # H4: erro de agenda digitado pelo usuário — flash e o formulário
        # volta preenchido (inclusive modo personalizado aberto).
        flash(grade["erro"], "warning")
        return _render_ofertas(
            turma_obj, rascunho=request.form, oferta_aberta="nova"
        )
    try:
        dados = _dados_oferta_form(request.form, turma_obj, grade=grade)
        if dados["curso_id"] is None:
            raise ValueError("Selecione um curso para adicionar à turma.")
        nome_curso = db.session.get(Curso, dados["curso_id"]).nome
        oferta = adicionar_oferta(turma_obj, **dados)
    except ValueError as erro:
        db.session.rollback()
        flash(str(erro), "warning")
        return _render_ofertas(
            turma_obj, rascunho=request.form, oferta_aberta="nova"
        )
    except IntegrityError:
        db.session.rollback()
        flash(
            "A oferta conflitou com outra alteração da turma. Recarregue a "
            "página e tente novamente.",
            "warning",
        )
        return redirect(url_for("registros.turma_ofertas", id=id))

    for aviso in getattr(oferta, "avisos_horario", []):
        flash(aviso, "warning")
    flash(
        f"Curso '{nome_curso}' adicionado à turma.",
        "success",
    )
    return redirect(url_for("registros.turma_ofertas", id=id))


@bp.route("/turma/oferta/<int:oferta_id>/editar", methods=["POST"])
@login_required
def turma_oferta_editar(oferta_id):
    """Edita os atributos próprios da oferta (professor, horários, vigência)."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    grade = grade_do_formulario(request.form)
    if _erro_agenda_formulario(grade):
        flash(grade["erro"], "warning")
        return _render_ofertas(
            turma_obj, rascunho=request.form, oferta_aberta=oferta_id
        )
    try:
        dados = _dados_oferta_form(request.form, turma_obj, grade=grade)
        dados.pop("principal", None)
        if dados["curso_id"] is None:
            raise ValueError("A oferta precisa estar vinculada a um curso.")
        professor_anterior = oferta.professor_id
        novo_professor = dados.get("professor_id")
        # E2: trocar o professor é permitido, mas numa oferta com lançamento
        # gravado exige confirmação explícita (mesmo padrão da limpeza de
        # lançamentos da turma) e fica registrado em log_acao.
        if novo_professor and novo_professor != professor_anterior:
            if (
                oferta_tem_lancamentos(oferta.id)
                and request.form.get("confirmar_troca_professor") != "1"
            ):
                db.session.rollback()
                flash(MSG_TROCA_PROFESSOR_COM_LANCAMENTO, "warning")
                return _render_ofertas(
                    turma_obj, rascunho=request.form, oferta_aberta=oferta_id
                )
            gravar_troca_professor_da_oferta(
                oferta.id, professor_anterior, novo_professor,
                usuario_id=current_user.id,
                usuario_nome=current_user.name,
                ip=request.remote_addr,
                unidade_id=turma_obj.unidade_id,
            )
        editar_oferta(oferta, **dados)
        for aviso in getattr(oferta, "avisos_horario", []):
            flash(aviso, "warning")
    except ValueError as erro:
        # H2/validação autoritativa do definir_grade: nada foi commitado —
        # desfaz mutações parciais e devolve o formulário preenchido.
        db.session.rollback()
        flash(str(erro), "warning")
        return _render_ofertas(
            turma_obj, rascunho=request.form, oferta_aberta=oferta_id
        )
    flash(f"Oferta '{oferta.curso.nome}' atualizada na turma.", "success")
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/oferta/<int:oferta_id>/principal", methods=["POST"])
@login_required
def turma_oferta_principal(oferta_id):
    """Define o curso principal da turma em troca atômica."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    try:
        definir_principal(oferta)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))
    flash(
        f"'{oferta.curso.nome}' agora é o curso principal da turma.", "success"
    )
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/oferta/<int:oferta_id>/desativar", methods=["POST"])
@login_required
def turma_oferta_desativar(oferta_id):
    """Remove o curso da turma (soft delete); histórico de inscrições preservado."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    try:
        # ETAPA M4: a guarda de alunos ativos em período em andamento vale
        # apenas para este caminho de rota; excluir_turma e demais fluxos
        # internos não passam por aqui (ou usam o padrão False).
        desativar_oferta(oferta, verificar_alunos_em_andamento=True)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))
    flash(f"O curso '{oferta.curso.nome}' foi removido da turma.", "success")
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_turma(id):
    # Verificações de perfil e isolamento por unidade ANTES de qualquer alteração.
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    if not turma_obj:
        return redirect(url_for("registros.turma"))

    from app.models import DiaBloqueadoTurma, TemaAula

    assert_unidade_context(turma_obj.unidade_id, get_unidade_id())
    nome = turma_obj.nome

    try:
        if turma_tem_historico(id):
            # COM histórico: exclusão LÓGICA. Preserva Frequencia, RegistroAula,
            # ConselhoClasse, Transferencia e as inscrições (mantém o vínculo
            # histórico); só desativa turma, ofertas e inscrições ativas.
            turma_obj.ativo = False
            # L4.1: o marcador guarda SÓ as ofertas que estavam ativas — oferta
            # já removida do curso antes da exclusão não pode voltar.
            ofertas_reativaveis = []
            for oferta in TurmaCurso.query.filter_by(turma_id=id).all():
                if oferta.ativo:
                    ofertas_reativaveis.append(oferta.id)
                oferta.ativo = False
            agora = get_local_now()
            inscricoes_desativadas = []
            for inscricao in Inscricao.query.filter_by(turma_id=id, ativo=True).all():
                inscricao.ativo = False
                inscricao.data_desativacao = agora
                # Mesmo mecanismo da desenturmação/transferência: motivo em
                # CAIXA-ALTA, sem acento (ver alunos.py: "TRANSFERENCIA").
                inscricao.motivo_desativacao = MOTIVO_INSCRICAO_TURMA_DESATIVADA
                inscricoes_desativadas.append(inscricao.id)
            # Marcador L4.1 na MESMA transação (sem commit próprio): é o único
            # sinal de quem saiu da turma junto com ela — o `updated_at` não
            # serve, porque o listener de auditoria o reescreve também nas
            # ofertas que já estavam inativas.
            gravar_marcador_exclusao(
                id, ofertas_reativaveis, inscricoes_desativadas,
                usuario_id=current_user.id,
                usuario_nome=current_user.name,
                ip=request.remote_addr,
                unidade_id=turma_obj.unidade_id,
            )
            db.session.commit()
            flash(
                "Turma desativada: possui lançamentos, o histórico foi preservado.",
                "success",
            )
        else:
            # SEM histórico: exclusão FÍSICA, na ordem das dependências de FK.
            # tema_aula.turma_id é anulável (legado): solta o vínculo, o tema
            # permanece pelo curso.
            TemaAula.query.filter_by(turma_id=id).update(
                {"turma_id": None}, synchronize_session=False
            )
            # Filhos NOT NULL que apontam para a turma/ofertas:
            Inscricao.query.filter_by(turma_id=id).delete(synchronize_session=False)
            DiaBloqueadoTurma.query.filter_by(turma_id=id).delete(
                synchronize_session=False
            )
            # Ofertas (TurmaCurso) — já sem inscrições que as referenciem.
            TurmaCurso.query.filter_by(turma_id=id).delete(synchronize_session=False)
            # Por último a própria turma (delete em massa: sem cascata ORM).
            db.session.query(Turma).filter_by(id=id).delete(synchronize_session=False)
            # Registra a ação com o mecanismo padrão de exclusões do projeto
            # (LogAcao via register_security_log), antes do commit final.
            register_security_log(
                "Exclusão de Turma",
                f"Turma id={id} nome='{nome}' excluída.",
            )
            db.session.commit()
            flash("Turma excluída.", "success")
    except Exception:
        current_app.logger.exception("Falha ao excluir turma %s", id)
        db.session.rollback()
        flash("Falha ao excluir a turma.", "danger")

    return redirect(url_for("registros.turma"))


@bp.route("/turmas/carga-horaria")
@login_required
def carga_horaria_turmas():
    """
    Exibe a listagem de cursos com descrição, temas associados,
    professores que já foram associados ao curso (que seguiram associados
    até o fim do período letivo da turma) e percentual de presença
    do curso nas turmas de qualquer período até seu encerramento.
    Mantém filtros de Unidade, Período Letivo, Professor e Curso.
    """
    if current_user.role not in ["admin", "pedagogico", "gerencia", "secretaria"]:
        abort(403)

    from app.models import TemaAula

    hoje = date.today()
    unidade_id = get_unidade_id()
    unidade_id_filtro = request.args.get("unidade_id", type=int)
    periodo_id = request.args.get("periodo_id", type=int)
    professor_id = request.args.get("professor_id", type=int)
    curso_id = request.args.get("curso_id", type=int)
    status_periodo = request.args.get("status_periodo", type=str)

    # Para usuários globais, usa o filtro de unidade; para locais, usa fixo
    unidade_efetiva = unidade_id_filtro if current_user.role in ["admin", "gerencia"] else unidade_id

    # Determina o status da visualização de forma estrita e alternada: 'vigente' ou 'concluido'
    periodo_selecionado = db.session.get(PeriodoLetivo, periodo_id) if periodo_id else None
    if periodo_selecionado:
        status_view = "vigente" if periodo_selecionado.data_fim >= hoje else "concluido"
    elif status_periodo == "concluido":
        status_view = "concluido"
    else:
        # Padrão: períodos vigentes (em andamento)
        status_view = "vigente"

    # Condições de vigência de turmas baseadas no período letivo ou datas próprias
    cond_vigente = db.or_(
        Turma.periodo_letivo_id.in_(
            select(PeriodoLetivo.id).where(PeriodoLetivo.data_fim >= hoje)
        ),
        db.and_(Turma.periodo_letivo_id.is_(None), db.or_(Turma.data_fim >= hoje, Turma.data_fim.is_(None))),
    )
    cond_concluido = db.or_(
        Turma.periodo_letivo_id.in_(
            select(PeriodoLetivo.id).where(PeriodoLetivo.data_fim < hoje)
        ),
        db.and_(Turma.periodo_letivo_id.is_(None), Turma.data_fim < hoje),
    )

    # Condição da modalidade ativa
    cond_status = cond_vigente if status_view == "vigente" else cond_concluido

    # Total geral de turmas da modalidade ativa no escopo (denominador do percentual)
    stmt_geral = select(db.func.count(Turma.id)).where(
        Turma.ativo == True,
        cond_status,
    )
    if unidade_efetiva:
        stmt_geral = stmt_geral.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_geral = stmt_geral.where(Turma.periodo_letivo_id == periodo_id)
    total_geral_turmas = db.session.execute(stmt_geral).scalar() or 0

    # Consulta dos Cursos disponíveis
    stmt_cursos = select(Curso).where(Curso.ativo == True)
    if unidade_efetiva:
        stmt_cursos = stmt_cursos.where(Curso.unidade_id == unidade_efetiva)
    if curso_id:
        stmt_cursos = stmt_cursos.where(Curso.id == curso_id)

    # Restringe aos cursos ofertados no período ou na modalidade ativa
    if periodo_id:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    Turma.periodo_letivo_id == periodo_id,
                )
            )
        )
    else:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    cond_status,
                )
            )
        )

    if professor_id:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    Turma.professor_id == professor_id,
                )
            )
        )

    cursos_base = db.session.execute(stmt_cursos.order_by(Curso.nome)).scalars().all()

    cursos_dados = []
    for c in cursos_base:
        # 1. Temas associados ao curso
        temas = (
            TemaAula.query.filter_by(curso_id=c.id, ativo=True)
            .order_by(TemaAula.ordem, TemaAula.id)
            .all()
        )

        # 2. Professores da modalidade ativa (vigente ou concluído)
        stmt_prof = (
            select(User)
            .join(Turma, Turma.professor_id == User.id)
            .where(
                Turma.curso_id == c.id,
                Turma.ativo == True,
                cond_status,
            )
        )
        if unidade_efetiva:
            stmt_prof = stmt_prof.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_prof = stmt_prof.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_prof = stmt_prof.where(Turma.professor_id == professor_id)

        profs_ativos = (
            db.session.execute(stmt_prof.distinct().order_by(User.name))
            .scalars()
            .all()
        )

        # 3. Turmas deste curso na modalidade ativa
        stmt_turmas_c = select(db.func.count(Turma.id)).where(
            Turma.curso_id == c.id,
            Turma.ativo == True,
            cond_status,
        )
        if unidade_efetiva:
            stmt_turmas_c = stmt_turmas_c.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_turmas_c = stmt_turmas_c.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_turmas_c = stmt_turmas_c.where(Turma.professor_id == professor_id)

        total_turmas_c = db.session.execute(stmt_turmas_c).scalar() or 0
        percentual = (
            round((total_turmas_c / total_geral_turmas) * 100, 1)
            if total_geral_turmas > 0
            else 0.0
        )

        # 4. C.H. total: soma da carga calculada em lote para as turmas do curso.
        stmt_turmas_ch = select(Turma).where(
            Turma.curso_id == c.id,
            Turma.ativo == True,
            cond_status,
        )
        if unidade_efetiva:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.professor_id == professor_id)

        turmas_ch = db.session.execute(
            stmt_turmas_ch.options(
                selectinload(Turma.ofertas_curso).selectinload(TurmaCurso.horarios)
            )
        ).scalars().all()
        from app.services.turma_curso_horario import cargas_horarias_turmas_em_lote

        cargas_turmas = cargas_horarias_turmas_em_lote(turmas_ch)
        ch_total_minutos = sum(
            (cargas_turmas[t.id].carga_horaria_total or 0) for t in turmas_ch
        ) or None  # None → "—" no template via formatar_ch

        cursos_dados.append({
            "curso": c,
            "temas": temas,
            "professores": profs_ativos,
            "total_turmas": total_turmas_c,
            "percentual_presenca": percentual,
            "ch_total_minutos": ch_total_minutos,
        })

    # ── DROPDOWNS DE FILTROS CASCATEADOS PELO FILTRO-MESTRE DE VIGÊNCIA ──
    # 1. Unidades (apenas para papéis globais)
    if current_user.role in ["admin", "gerencia"]:
        from app.models import Unidade
        unidades = Unidade.query.order_by(Unidade.nome).all()
    else:
        unidades = []

    # 2. Períodos Letivos: filtrados estritamente pela modalidade ativa (vigente ou concluído)
    stmt_periodos = select(PeriodoLetivo).where(PeriodoLetivo.ativo == True)
    if unidade_efetiva:
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.unidade_id == unidade_efetiva)

    if status_view == "vigente":
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.data_fim >= hoje).order_by(
            PeriodoLetivo.data_inicio.asc(), PeriodoLetivo.nome.asc()
        )
    else:
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.data_fim < hoje).order_by(
            PeriodoLetivo.data_fim.desc(), PeriodoLetivo.nome.asc()
        )

    periodos = db.session.execute(stmt_periodos).scalars().all()

    # 3. Professores: apenas professores da unidade escolhida (ou todas se global "Todas")
    # que possuam turmas na modalidade ativa (e no período selecionado, se houver)
    stmt_turmas_prof_filtro = select(Turma.professor_id).where(
        Turma.ativo == True,
        cond_status,
        Turma.professor_id.isnot(None),
    )
    if unidade_efetiva:
        stmt_turmas_prof_filtro = stmt_turmas_prof_filtro.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_turmas_prof_filtro = stmt_turmas_prof_filtro.where(Turma.periodo_letivo_id == periodo_id)

    stmt_profs = select(User).where(
        User.role == "professor",
        User.id.in_(stmt_turmas_prof_filtro),
    )
    if unidade_efetiva:
        stmt_profs = stmt_profs.where(User.unidade_id == unidade_efetiva)

    professores = db.session.execute(stmt_profs.order_by(User.name)).scalars().all()

    # 4. Cursos: apenas cursos da unidade escolhida (ou todas se global "Todas")
    # que possuam turmas na modalidade ativa + período + professor selecionados
    stmt_turmas_curso_filtro = select(Turma.curso_id).where(
        Turma.ativo == True,
        cond_status,
        Turma.curso_id.isnot(None),
    )
    if unidade_efetiva:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.periodo_letivo_id == periodo_id)
    if professor_id:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.professor_id == professor_id)

    stmt_cursos_dropdown = select(Curso).where(
        Curso.ativo == True,
        Curso.id.in_(stmt_turmas_curso_filtro),
    )
    if unidade_efetiva:
        stmt_cursos_dropdown = stmt_cursos_dropdown.where(Curso.unidade_id == unidade_efetiva)

    cursos = db.session.execute(stmt_cursos_dropdown.order_by(Curso.nome)).scalars().all()

    return render_template(
        "turmas/carga_horaria_curso.html",
        cursos_dados=cursos_dados,
        status_view=status_view,
        status_periodo=status_periodo,
        total_geral_turmas=total_geral_turmas,
        unidades=unidades,
        periodos=periodos,
        professores=professores,
        cursos=cursos,
        unidade_id_filtro=unidade_id_filtro,
        periodo_id=periodo_id,
        professor_id=professor_id,
        curso_id=curso_id,
        formatar_ch=formatar_ch,
        hoje=hoje,
    )


@bp.route("/turma/<int:turma_id>/observacoes")
@login_required
def ver_observacoes(turma_id):
    if current_user.role not in ["admin", "pedagogico", "secretaria", "professor"]:
        abort(403)

    # Mesma guarda de `ver_turma`/`imprimir_pauta`: isolamento por unidade e,
    # para professor, apenas as turmas em que ele leciona alguma oferta ativa
    # (E3/I1: regra por OFERTA, sem herdar `turma.professor_id`).
    from app.services.aluno_info_professor import (
        ofertas_do_professor,
        professor_de_alguma_oferta_ativa,
    )

    turma_obj = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma_obj.unidade_id, get_unidade_id())
    if (
        current_user.role == UserRole.PROFESSOR
        and not professor_de_alguma_oferta_ativa(turma_id, current_user)
    ):
        abort(403)

    # Onda 4 (Fase 4, D3a): filtro opcional por oferta (querystring
    # `turma_curso`). Com 2+ ofertas ativas cada observação ganha o rótulo
    # do curso; registros com turma_curso_id NULL aparecem sem rótulo.
    # Com 0/1 oferta a tela é exatamente como hoje.
    #
    # AJ6-B: não existe "professor da turma" — o professor vê só o diário das
    # OFERTAS em que é o professor. O seletor e a consulta usam apenas as
    # ofertas dele; pedir oferta alheia explicitamente é negado (403). O
    # registro legado (turma_curso_id NULL) só entra quando a turma tem
    # exatamente 1 oferta ativa e ela é dele (mesma atribuição D2 da pauta).
    ofertas_todas = ofertas_ativas(turma_id)
    ofertas = ofertas_do_professor(current_user, ofertas_todas)
    mostrar_curso = len(ofertas) >= 2
    turma_curso_id = _parse_int_arg(request.args.get("turma_curso"))

    # A1: a aula entra no diário quando tem atividades OU observações;
    # registros com os dois vazios continuam fora (comportamento anterior).
    filtros = [
        RegistroAula.turma_id == turma_id,
        or_(
            and_(RegistroAula.observacoes != None, RegistroAula.observacoes != ""),
            and_(RegistroAula.atividades != None, RegistroAula.atividades != ""),
        ),
    ]
    if turma_curso_id is not None:
        if any(o.id == turma_curso_id for o in ofertas):
            filtros.append(RegistroAula.turma_curso_id == turma_curso_id)
        elif current_user.role == UserRole.PROFESSOR:
            # Oferta que não é dele → nega (403) sem revelar se existe.
            abort(403)
        else:
            flash("Curso selecionado inválido para esta turma.", "warning")
    elif current_user.role == UserRole.PROFESSOR:
        # Sem escolha: o diário é restrito às ofertas dele (nunca as de outro
        # professor na mesma turma). NULL só no caso de oferta única.
        ids_dele = [o.id for o in ofertas]
        if len(ofertas_todas) == 1 and len(ofertas) == 1:
            filtros.append(
                or_(
                    RegistroAula.turma_curso_id.in_(ids_dele),
                    RegistroAula.turma_curso_id.is_(None),
                )
            )
        else:
            filtros.append(RegistroAula.turma_curso_id.in_(ids_dele))

    observacoes = (
        RegistroAula.query.filter(*filtros)
        .order_by(RegistroAula.data.desc())
        .all()
    )
    return render_template(
        "turmas/observacoes.html",
        obs=observacoes,
        turma=turma_obj,
        historico=observacoes,
        mostrar_curso=mostrar_curso,
    )


@bp.route("/turma/<int:id>/imprimir-pauta")
@login_required
def imprimir_pauta(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        if current_user.role != "professor":
            abort(403)

    turma = Turma.query.get_or_404(id)
    assert_unidade_context(turma.unidade_id, get_unidade_id())

    from app.services.aluno_info_professor import (
        alunos_com_info_professor,
        professor_da_oferta,
    )

    # Onda 4 (Fase 4, D3a): `turma_curso` opcional na querystring.
    #   - 0 ofertas ativas: igual a hoje (pauta e frequências por turma).
    #   - 1 oferta ativa: uso automático sem seletor; as frequências da
    #     oferta incluem as legado NULL (regra de pauta da D2 — a inscrição
    #     sem curso só pode ser dela) e a lista de alunos segue por turma.
    #   - 2+ ofertas: exige escolha — sem turma_curso não imprime misturado
    #     (flash pedindo o curso e retorno à tela de frequência, que tem o
    #     seletor); com turma_curso, alunos e frequências só da oferta, com
    #     o nome do curso no cabeçalho da impressão.
    #
    # G1 (28/10/2026) — professor da OFERTA, sem herança da turma:
    #   - a oferta vem de `turma_curso`; sem parâmetro, 1 oferta ativa → ela,
    #     2+ → a de menor id (ordem de `ofertas_ativas`); a oferta `principal`
    #     NÃO decide acesso (R2 do G1);
    #   - oferta de outro professor, oferta sem professor ou turma sem oferta
    #     ativa dele => 403 (nenhum perfil professor herda `turma.professor_id`);
    #   - a lista de alunos é SEMPRE a da oferta dele (`_alunos_da_oferta`) e a
    #     indicação de "outras ofertas" não é exibida (ele não as leciona).
    #   Demais perfis (admin/pedagógico/secretaria) mantêm o comportamento.
    ofertas = ofertas_ativas(id)
    oferta = None
    turma_curso_id = _parse_int_arg(request.args.get("turma_curso"))
    if current_user.role == UserRole.PROFESSOR:
        if turma_curso_id is not None:
            oferta = next((o for o in ofertas if o.id == turma_curso_id), None)
        else:
            oferta = ofertas[0] if ofertas else None
        if not professor_da_oferta(oferta, current_user):
            abort(403)
    elif len(ofertas) >= 2:
        if turma_curso_id is None:
            flash(
                "Esta turma tem mais de um curso ativo. Selecione o curso "
                "antes de imprimir a pauta.",
                "warning",
            )
            return redirect(url_for("registros.frequencia", turma_id=id))
        oferta = next((o for o in ofertas if o.id == turma_curso_id), None)
        if oferta is None:
            flash("Curso selecionado inválido para esta turma.", "warning")
            return redirect(url_for("registros.frequencia", turma_id=id))
    elif len(ofertas) == 1:
        oferta = ofertas[0]

    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash(
            "Não há informações completas para montar arquitetura de pauta.", "warning"
        )
        return redirect(url_for("registros.ver_turma", id=id))

    if oferta is not None and (
        len(ofertas) >= 2 or current_user.role == UserRole.PROFESSOR
    ):
        # Pauta da oferta: inscrição sempre apontada para a oferta —
        # Inscricao.turma_curso_id é NOT NULL desde a Onda 4. Para o professor
        # vale também com 1 oferta ativa: só entram alunos inscritos na
        # oferta dele (PARTE B, item 3).
        ctx["alunos"] = _alunos_da_oferta(
            id, oferta.id,
        )

    if oferta is not None:
        # A agenda da impressão segue a vigência e os dias próprios da oferta,
        # incluindo datas futuras e respeitando os dias bloqueados do período.
        ctx["datas"] = [
            data_aula.strftime("%Y-%m-%d")
            for data_aula in datas_aula_oferta(
                oferta, blocked=_blocked_dates_str(ctx["turma"])
            )
        ]

    alunos_ids = [aluno.id for aluno in ctx["alunos"]]
    outras_ofertas_por_aluno = {aluno_id: [] for aluno_id in alunos_ids}
    # PARTE B: o professor não vê a indicação de ofertas que não leciona.
    if alunos_ids and current_user.role != UserRole.PROFESSOR:
        stmt_ofertas_alunos = (
            select(Inscricao.aluno_id, TurmaCurso.id, Curso.nome)
            .join(TurmaCurso, Inscricao.turma_curso_id == TurmaCurso.id)
            .join(Curso, TurmaCurso.curso_id == Curso.id)
            .where(
                Inscricao.turma_id == id,
                Inscricao.ativo.is_(True),
                TurmaCurso.ativo.is_(True),
                Inscricao.aluno_id.in_(alunos_ids),
            )
            .order_by(Curso.nome)
        )
        for aluno_id, oferta_id, nome_curso in db.session.execute(
            stmt_ofertas_alunos
        ):
            if oferta is not None and oferta_id == oferta.id:
                continue
            if nome_curso and nome_curso not in outras_ofertas_por_aluno[aluno_id]:
                outras_ofertas_por_aluno[aluno_id].append(nome_curso)

    perfis_diversidade = {}
    if alunos_ids:
        perfis_diversidade = {
            perfil.aluno_id: perfil
            for perfil in db.session.execute(
                select(PerfilDiversidade).where(
                    PerfilDiversidade.aluno_id.in_(alunos_ids)
                )
            ).scalars()
        }
    dados_alunos_impressao = {}
    for aluno in ctx["alunos"]:
        perfil = perfis_diversidade.get(aluno.id)
        dados_alunos_impressao[aluno.id] = {
            "idade": aluno.idade if aluno.data_nascimento else None,
            "acompanhante": (
                aluno.acompanhante_aulas
                if aluno.vai_acompanhado_aulas else None
            ),
            "medicacao": (
                perfil.saude_medicamento_nome or "Sim"
                if perfil and perfil.saude_medicacao == "Sim"
                else None
            ),
            "informacoes_professor": (
                perfil.informacoes_para_professor.strip()
                if perfil and perfil.informacoes_para_professor
                else None
            ),
            "outras_ofertas": outras_ofertas_por_aluno.get(aluno.id, []),
        }

    # I1: para o professor, as linhas de acompanhante e de instruções só saem
    # dos alunos que ele leciona hoje — MESMA regra de /aluno/<id>/info-professor
    # (professor efetivo da oferta, inscrição/turma/oferta ativas, unidade e
    # período não encerrado). Outros perfis: `None` = sem restrição (inalterado).
    # Medicação não passa por aqui.
    alunos_com_info = None
    if current_user.role == UserRole.PROFESSOR:
        alunos_com_info = alunos_com_info_professor(alunos_ids, current_user)

    nomes_meses = {
        "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
        "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
        "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
    }
    mes_selecionado = request.args.get("mes")
    if mes_selecionado:
        ctx["datas"] = [data for data in ctx["datas"] if f"-{mes_selecionado}-" in data]
        ctx["mes_nome"] = nomes_meses.get(mes_selecionado, mes_selecionado)

    # A pauta completa é dividida por mês para evitar que as colunas de todo o
    # ano sejam cortadas pela área rolável do navegador ao imprimir.
    datas_por_mes_map = {}
    for data_aula in sorted(ctx["datas"]):
        numero_mes = data_aula[5:7]
        chave_mes = data_aula[:7]
        grupo_mes = datas_por_mes_map.setdefault(
            chave_mes,
            {"ano": data_aula[:4], "numero": numero_mes, "datas": []},
        )
        grupo_mes["datas"].append(data_aula)
    datas_por_mes = [
        {
            **grupo_mes,
            "nome": nomes_meses.get(grupo_mes["numero"], grupo_mes["numero"]),
        }
        for grupo_mes in datas_por_mes_map.values()
    ]

    # Onda 2A: Frequencia.data é `date`, mas ctx["datas"] é list[str].
    # Converter para date antes do IN, senão nunca casa.
    datas_ctx = ctx["datas"]
    datas_date = [parse_date(d) for d in datas_ctx]
    datas_date = [d for d in datas_date if d is not None]

    freq_filtros = [
        Frequencia.turma_id == id,
        Frequencia.data.in_(datas_date),
    ] if datas_date else None
    if freq_filtros is not None and oferta is not None:
        if len(ofertas) == 1:
            # Oferta única: frequências legado NULL pertencem a ela (regra
            # da pauta D2); na prática equivale ao filtro por turma de hoje.
            freq_filtros.append(
                or_(
                    Frequencia.turma_curso_id == oferta.id,
                    Frequencia.turma_curso_id.is_(None),
                )
            )
        else:
            freq_filtros.append(Frequencia.turma_curso_id == oferta.id)

    registros = (
        Frequencia.query.filter(*freq_filtros).all()
        if freq_filtros
        else []
    )

    # O template indexa por string. Mantemos as chaves no formato 'YYYY-MM-DD'.
    frequencias = {}
    for registro in registros:
        chave = registro.data.strftime('%Y-%m-%d')
        frequencias.setdefault(chave, {})[registro.aluno_id] = registro.conceito

    return render_template(
        "frequencia/imprimir_pauta.html",
        **ctx,
        frequencias=frequencias,
        datas_por_mes=datas_por_mes,
        oferta_atual=oferta,
        dados_alunos_impressao=dados_alunos_impressao,
        alunos_com_info=alunos_com_info,
        now=datetime.now(),
    )

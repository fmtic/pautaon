"""
================================================================================
LOGICA.PY - Helpers de negócio (frequência, turmas, relatórios)
================================================================================

NOTA SOBRE TIPOS (Onda 2A):
    `Turma.data_inicio`, `Turma.data_fim`, `Turma.hora_inicio`, `Turma.hora_fim`,
    `Frequencia.data`, `RegistroAula.data`, `TemaAula.data` e
    `DiaBloqueadoTurma.data` agora são `date`/`time` nativos.

NOTA SOBRE ENUMS (Onda 2B):
    Comparações com conceitos de frequência e perfis usam `ConceitoFrequencia`
    e `UserRole` de `app.models.enums`. Os conjuntos derivados
    (`CONCEITOS_PRESENCA`, `CONCEITOS_CONTABEIS`) também são importados de lá
    — a fonte única é `enums.py`.

DÍVIDA TÉCNICA CONHECIDA:
    `gerar_datas` ainda retorna `List[str]` ('YYYY-MM-DD') por compatibilidade
    com templates legados. Idealmente retornaria `List[date]`.
================================================================================
"""

from datetime import datetime, date, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import current_app, session
from flask_login import current_user

from app.database import db
from app.models import (
    Aluno,
    ConfiguracaoSistema,
    DiaBloqueado,
    DiaBloqueadoTurma,
    Frequencia,
    Inscricao,
    RegistroAula,
    TemaAula,
    Turma,
    User,
)
from app.models.enums import (
    ConceitoFrequencia,
    CONCEITOS_PRESENCA,
    CONCEITOS_CONTABEIS,
    UserRole,
)
from app.utils.datetime_parse import parse_date
from app.utils.timezone import get_local_now


NAME_LOWER_EXCEPTIONS = {
    'da', 'de', 'do', 'dos', 'das', 'e', 'van', 'von', 'del',
    'da', 'di', 'du', 'la', 'le', 'y', 'al',
}


# =============================================================================
# HELPERS DE DATA (interno)
# =============================================================================

def _normalizar_data(valor) -> Optional[date]:
    """
    Aceita `date`, `datetime` ou string 'YYYY-MM-DD' e devolve `date`.

    Usado em pontos onde o valor pode chegar como string de formulário/URL
    ou como `date` já vindo de uma coluna do banco.
    """
    return parse_date(valor)


def _blocked_dates_str(turma: Turma) -> set[str]:
    """
    Datas bloqueadas do período letivo da turma, EXCLUINDO as exceções por
    turma. Retorna strings 'YYYY-MM-DD'.

    IMPORTANTE: o resultado é subtraído como string para bater com o que
    `gerar_datas` espera em `blocked_dates`.
    """
    if not turma or not turma.periodo_letivo_id:
        return set()

    dias = DiaBloqueado.query.filter_by(
        periodo_letivo_id=turma.periodo_letivo_id
    ).all()
    excecoes = DiaBloqueadoTurma.query.filter_by(turma_id=turma.id).all()

    bloqueadas = {d.data.strftime('%Y-%m-%d') for d in dias}
    excecoes_str = {e.data.strftime('%Y-%m-%d') for e in excecoes}
    return bloqueadas - excecoes_str


# =============================================================================
# FREQUÊNCIA - estatísticas
# =============================================================================

def calcular_estatisticas_frequencia(conceitos) -> Dict[str, Any]:
    """
    Calcula frequência por conceito.

    Regra:
        - Presença: A, B, C, D
        - Falta: F
        - Justificada: J (não entra no denominador)
        - Frequência = presenças / (presenças + faltas)
    """
    # Inicializa contadores a partir do enum — garante que não esquecemos
    # nenhum conceito se o enum evoluir.
    counts = {c.value: 0 for c in ConceitoFrequencia}
    for conceito in conceitos:
        # Aceita tanto `ConceitoFrequencia.X` quanto `'X'` (str) porque os
        # enums herdam de `str`. `.value` normaliza para a string pura.
        valor = conceito.value if isinstance(conceito, ConceitoFrequencia) else conceito
        if valor in counts:
            counts[valor] += 1

    # `CONCEITOS_PRESENCA` é frozenset de membros do enum (não strings).
    # Por isso extraímos `.value` para acessar os contadores.
    presencas = sum(counts[c.value] for c in CONCEITOS_PRESENCA)
    faltas = counts[ConceitoFrequencia.F.value]
    justificadas = counts[ConceitoFrequencia.J.value]
    total_validas = presencas + faltas

    def percentual(valor: int, total: int = total_validas) -> float:
        return round(valor / total * 100, 1) if total else 0.0

    return {
        'counts': counts,
        'total': total_validas,
        'total_registros': sum(counts.values()),
        'presencas': presencas,
        'faltas': faltas,
        'justificadas': justificadas,
        'presenca_percentual': percentual(presencas),
        'falta_percentual': percentual(faltas),
        'justificada_percentual': percentual(justificadas, sum(counts.values())),
    }


# =============================================================================
# HELPERS DE APRESENTAÇÃO
# =============================================================================

def formatar_nome_proprio(nome: str | None) -> str | None:
    """
    Normaliza um nome próprio para apresentação padrão.

    Mantém preposições e conectores em minúsculas, mas capitaliza os nomes.
    Exemplo: "adriely da conceição nunes" -> "Adriely da Conceição Nunes".
    """
    if not nome:
        return None

    def format_word(word: str, is_first: bool) -> str:
        lower = word.lower()
        if not is_first and lower in NAME_LOWER_EXCEPTIONS:
            return lower
        return '-'.join(part.capitalize() if part else '' for part in lower.split('-'))

    parts = [p for p in nome.strip().split() if p]
    if not parts:
        return None

    formatted_parts = [format_word(parts[0], True)]
    formatted_parts += [format_word(word, False) for word in parts[1:]]

    return ' '.join(formatted_parts)


def get_unidade_id() -> Optional[int]:
    """
    Retorna o ID da unidade efetiva para o usuário logado.

    Perfis operacionais vinculados a uma unidade não podem cair em visão global
    por sessão vazia ou stale. Admin e gerência continuam usando o contexto
    selecionado na sessão.
    """
    global_roles = (UserRole.ADMIN, UserRole.GERENCIA)
    if current_user.is_authenticated and current_user.role not in global_roles:
        if current_user.unidade_id:
            session["unidade_id"] = current_user.unidade_id
            return current_user.unidade_id
        session.pop("unidade_id", None)
        return None

    if 'unidade_id' in session:
        try:
            return int(session.get('unidade_id'))
        except (ValueError, TypeError):
            session.pop("unidade_id", None)
    return None


# =============================================================================
# GERAÇÃO DE DATAS DE AULA
# =============================================================================

def gerar_datas(
    turma: Turma,
    incluir_futuro: bool = False,
    blocked_dates: set = None,
) -> List[str]:
    """
    Gera lista cronológica de datas de aula conforme os dias da semana da turma.

    IMPORTANTE (Onda 2A):
        `turma.data_inicio` e `turma.data_fim` agora são `date`. O parâmetro
        `blocked_dates` continua sendo um conjunto de STRINGS 'YYYY-MM-DD'
        (compatibilidade com templates legados).

    DÍVIDA TÉCNICA:
        Esta função retorna `List[str]`. Idealmente retornaria `List[date]`.

    :param turma: Instância de Turma.
    :param incluir_futuro: Se True, projeta até `data_fim`. Se False, corta em hoje.
    :param blocked_dates: Datas bloqueadas (strings 'YYYY-MM-DD').
    :return: Lista de strings 'YYYY-MM-DD', do mais antigo ao mais recente
             (ou invertida, se `incluir_futuro=False`).
    """
    blocked_dates = blocked_dates or set()
    datas: List[str] = []

    if not turma or not turma.data_inicio or not turma.data_fim:
        return datas

    mapa_dias = {
        'Segunda': 0, 'Terça': 1, 'Quarta': 2, 'Quinta': 3,
        'Sexta': 4, 'Sábado': 5, 'Domingo': 6,
        'Segunda-feira': 0, 'Terça-feira': 1, 'Quarta-feira': 2,
        'Quinta-feira': 3, 'Sexta-feira': 4, 'Sábado-feira': 5,
    }

    inicio = datetime.combine(turma.data_inicio, time.min)
    fim = datetime.combine(turma.data_fim, time.min)

    if incluir_futuro:
        data_limite = fim
    else:
        hoje = datetime.now()
        data_limite = min(fim, hoje)

    dias_permitidos = [
        mapa_dias[d.strip()]
        for d in (turma.dias_semana or "").split(',')
        if d.strip() in mapa_dias
    ]

    atual = inicio
    while atual <= data_limite:
        if atual.weekday() in dias_permitidos:
            ds = atual.strftime("%Y-%m-%d")
            if ds not in blocked_dates:
                datas.append(ds)
        atual += timedelta(days=1)

    if incluir_futuro:
        return datas
    return datas[::-1]  # Mais atual -> mais antigo


# =============================================================================
# CONTEXTO DE TURMA PARA TEMPLATES
# =============================================================================

def calcular_idades(alunos: List[Aluno]) -> None:
    """
    Acopla a propriedade computada `.idade_calculada` a cada aluno.

    Tolerante a `data_nascimento` como `date` ou string (legado).
    """
    hoje = date.today()
    for aluno in alunos:
        if not aluno.data_nascimento:
            aluno.idade_calculada = "?"
            continue

        nasc = aluno.data_nascimento
        if not isinstance(nasc, date):
            try:
                nasc = datetime.strptime(str(nasc), "%Y-%m-%d").date()
            except (ValueError, TypeError):
                aluno.idade_calculada = "?"
                continue

        aluno.idade_calculada = (
            hoje.year - nasc.year
            - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
        )


def carregar_contexto_turma(turma_id: int, pauta_impressa: bool = False) -> Dict[str, Any]:
    """
    Retorna um dicionário de contexto para renderização da pauta de uma turma.

    Injeta automaticamente os dias bloqueados do período letivo, já
    descontando as exceções (`DiaBloqueadoTurma`).
    """
    turma = Turma.query.get_or_404(turma_id)

    blocked_dates = _blocked_dates_str(turma)

    alunos = (
        Aluno.query.join(Inscricao)
        .filter(
            Inscricao.turma_id == turma_id,
            Inscricao.ativo == True,
            Aluno.ativo == True,
        )
        .order_by(Aluno.nome)
        .all()
    )
    calcular_idades(alunos)

    datas = gerar_datas(
        turma, incluir_futuro=pauta_impressa, blocked_dates=blocked_dates
    )

    meses_disponiveis = []
    vistos = set()
    nomes_meses = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro',
    }
    for d in datas:
        mes_num = d[5:7]
        if mes_num not in vistos:
            meses_disponiveis.append({
                'numero': mes_num,
                'nome': nomes_meses.get(mes_num, 'Mês Desconhecido'),
            })
            vistos.add(mes_num)

    if turma.curso_id:
        temas = TemaAula.query.filter_by(curso_id=turma.curso_id, ativo=True).all()
    else:
        temas = TemaAula.query.filter_by(turma_id=turma_id, ativo=True).all()

    return dict(
        turma=turma,
        alunos=alunos,
        datas=datas,
        temas=temas,
        meses=meses_disponiveis,
    )


# =============================================================================
# FREQUÊNCIA - leitura e escrita
# =============================================================================

def carregar_frequencias(
    turma_id: int,
    data: str | date,
) -> Tuple[Dict[int, str], Optional[int], str]:
    """
    Carrega os conceitos lançados para uma turma em uma data.

    Onda 2A: `Frequencia.data` e `RegistroAula.data` agora são `date`.
    A função aceita string ou date e normaliza via `parse_date`.

    :return: (dict{aluno_id: conceito}, tema_selecionado_id | None, observacoes)
    """
    frequencias: Dict[int, str] = {}
    tema_selecionado: Optional[int] = None
    obs_salva: str = ""

    data_alvo = parse_date(data)
    if not turma_id or not data_alvo:
        return frequencias, tema_selecionado, obs_salva

    registros = Frequencia.query.filter_by(
        turma_id=turma_id, data=data_alvo
    ).all()
    frequencias = {f.aluno_id: f.conceito for f in registros}

    diario = RegistroAula.query.filter_by(
        turma_id=turma_id, data=data_alvo
    ).first()
    if diario:
        tema_selecionado = diario.tema_id
        obs_salva = diario.observacoes or ""

    return frequencias, tema_selecionado, obs_salva


def salvar_frequencia(form: Dict[str, str]) -> Tuple[int, Optional[str]]:
    """
    Consolida os lançamentos de frequência e o diário da aula em um único commit.

    Onda 2A: `data` do formulário chega como string; convertida via `parse_date`
    antes de qualquer consulta/gravação.

    :return: (turma_id, data_str) em caso de sucesso; (0, None) em caso de erro.
    """
    try:
        turma_raw = form.get('turma', '0').strip()
        turma_id = int(turma_raw) if turma_raw and turma_raw.isdigit() else 0

        data_raw = (form.get('data', '') or form.get('data_hidden', '')).strip()
        data_alvo = parse_date(data_raw)

        tema_id_raw = form.get('tema_id', '').strip()
        tema_id = int(tema_id_raw) if tema_id_raw and tema_id_raw.isdigit() else None
        texto_observacoes = form.get('observacoes', '').strip() or None

        if not data_alvo or turma_id == 0:
            return turma_id, None

        # --- Registro de aula (diário do educador) ---
        registro = RegistroAula.query.filter_by(
            turma_id=turma_id, data=data_alvo
        ).first()
        if registro:
            registro.observacoes = texto_observacoes
            registro.tema_id = tema_id
            registro.instrutor_id = current_user.id
        else:
            db.session.add(RegistroAula(
                turma_id=turma_id,
                data=data_alvo,
                tema_id=tema_id,
                observacoes=texto_observacoes,
                instrutor_id=current_user.id,
            ))

        # --- Frequência por aluno ---
        alunos_post = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == turma_id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .all()
        )

        for aluno in alunos_post:
            conceito = form.get(f'aluno_{aluno.id}', '').strip()
            if not conceito:
                continue

            freq = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_id=turma_id, data=data_alvo
            ).first()

            if freq:
                freq.conceito = conceito
            else:
                db.session.add(Frequencia(
                    aluno_id=aluno.id,
                    turma_id=turma_id,
                    data=data_alvo,
                    conceito=conceito,
                ))

        db.session.commit()
        return turma_id, data_alvo.strftime('%Y-%m-%d')

    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Erro ao salvar frequência (turma_id=%s)",
            form.get('turma'),
        )
        return 0, None


# =============================================================================
# RELATÓRIOS
# =============================================================================

def calcular_estatisticas_idade(unidade_id: Optional[int] = None) -> Dict[str, Any]:
    """Média de idade geral, por programa e por turma."""
    alunos_query = Aluno.query.filter(Aluno.ativo == True)
    if unidade_id:
        alunos_query = alunos_query.filter_by(unidade_id=unidade_id)
    alunos = alunos_query.all()
    if not alunos:
        return {'media_geral': 0, 'media_programa': {}, 'media_turma': {}}

    idades_geral = [a.idade for a in alunos]
    media_geral = sum(idades_geral) / len(idades_geral) if idades_geral else 0

    media_por_programa = {}
    prog_query = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        prog_query = prog_query.filter(Turma.unidade_id == unidade_id)
    for prog, in prog_query.all():
        q = Aluno.query.join(Aluno.turmas).filter(
            Turma.programa == prog,
            Aluno.ativo == True,
            Turma.ativo == True,
        )
        if unidade_id:
            q = q.filter(Aluno.unidade_id == unidade_id, Turma.unidade_id == unidade_id)
        alunos_prog = q.all()
        if alunos_prog:
            idades = [a.idade for a in alunos_prog]
            media_por_programa[prog] = sum(idades) / len(idades)

    media_por_turma = {}
    turma_query = Turma.query.filter_by(ativo=True)
    if unidade_id:
        turma_query = turma_query.filter_by(unidade_id=unidade_id)
    for t in turma_query.all():
        idades = [
            a.idade for a in t.alunos
            if a.ativo and (not unidade_id or a.unidade_id == unidade_id)
        ]
        if idades:
            media_por_turma[t.nome] = sum(idades) / len(idades)

    return {
        'media_geral': round(media_geral, 1),
        'media_programa': media_por_programa,
        'media_turma': media_por_turma,
    }


def calcular_frequencias_relatorio(
    todas_as_turmas: List[Turma],
    unidade_id: Optional[int] = None,
) -> Tuple[float, Dict[str, float], Dict[str, float], Dict[str, float]]:
    """Retorna (geral, por_programa, por_turma, por_professor), em %."""

    def calc_pc(query) -> float:
        estatisticas = calcular_estatisticas_frequencia(
            registro.conceito for registro in query.all()
        )
        return estatisticas['presenca_percentual']

    q_geral = Frequencia.query.join(
        Turma, Frequencia.turma_id == Turma.id
    ).filter(Turma.ativo == True)
    if unidade_id:
        q_geral = q_geral.filter(Turma.unidade_id == unidade_id)
    p_geral = calc_pc(q_geral)

    f_prog: Dict[str, float] = {}
    prog_query = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        prog_query = prog_query.filter(Turma.unidade_id == unidade_id)
    for prog, in prog_query.all():
        q = Frequencia.query.join(
            Turma, Frequencia.turma_id == Turma.id
        ).filter(Turma.programa == prog, Turma.ativo == True)
        if unidade_id:
            q = q.filter(Turma.unidade_id == unidade_id)
        f_prog[prog] = calc_pc(q)

    f_turma: Dict[str, float] = {}
    for t in todas_as_turmas:
        q = Frequencia.query.filter(Frequencia.turma_id == t.id)
        f_turma[t.nome] = calc_pc(q)

    f_prof: Dict[str, float] = {}
    # Onda 2B (limpeza): usa o enum em vez da string 'professor'.
    prof_query = User.query.filter_by(role=UserRole.PROFESSOR.value)
    if unidade_id:
        prof_query = prof_query.filter_by(unidade_id=unidade_id)
    for prof in prof_query.all():
        q = Frequencia.query.join(
            Turma, Frequencia.turma_id == Turma.id
        ).filter(Turma.professor_id == prof.id, Turma.ativo == True)
        if unidade_id:
            q = q.filter(Turma.unidade_id == unidade_id)
        if q.count() > 0:
            f_prof[prof.name] = calc_pc(q)

    return p_geral, f_prog, f_turma, f_prof


def calcular_metricas_conselho(unidade_id: Optional[int] = None) -> Dict[str, float]:
    """
    Progresso do conselho (aulas planejadas vs. registradas e reuniões concluídas).

    As datas de corte vêm de ConfiguracaoSistema (chaves 'inicio_conselho' e
    'fim_conselho', no formato 'YYYY-MM-DD'). São convertidas para `date` antes
    de comparar com `TemaAula.data` / `RegistroAula.data`, que são `date`.
    """
    def _conf(chave: str):
        if unidade_id:
            c = ConfiguracaoSistema.query.filter_by(
                chave=chave, unidade_id=unidade_id
            ).first()
            if c:
                return c
        return ConfiguracaoSistema.query.filter_by(
            chave=chave, unidade_id=None
        ).first()

    conf_inicio = _conf('inicio_conselho')
    conf_fim = _conf('fim_conselho')

    prog_aulas = 0.0
    if conf_inicio and conf_fim:
        try:
            inicio = datetime.strptime(conf_inicio.valor, "%Y-%m-%d").date()
            fim = datetime.strptime(conf_fim.valor, "%Y-%m-%d").date()
            tema_query = TemaAula.query.filter(TemaAula.data.between(inicio, fim))
            registro_query = RegistroAula.query.filter(
                RegistroAula.data.between(inicio, fim)
            )
            if unidade_id:
                tema_query = tema_query.filter_by(unidade_id=unidade_id)
                registro_query = registro_query.filter_by(unidade_id=unidade_id)
            total = tema_query.count()
            real = registro_query.count()
            prog_aulas = round((real / total * 100), 1) if total > 0 else 0.0
        except (ValueError, TypeError):
            current_app.logger.exception(
                "Erro ao calcular progresso de aulas do conselho"
            )

    total_t_q = Turma.query.filter_by(ativo=True)
    concluidas_q = Turma.query.filter_by(ativo=True, conselho_concluido=True)
    if unidade_id:
        total_t_q = total_t_q.filter_by(unidade_id=unidade_id)
        concluidas_q = concluidas_q.filter_by(unidade_id=unidade_id)
    total_t = total_t_q.count()
    concluidas = concluidas_q.count()
    prog_reunioes = float(
        round((concluidas / total_t * 100), 1) if total_t > 0 else 0.0
    )

    return {
        'progresso_aulas': prog_aulas,
        'progresso_reunioes': prog_reunioes,
        'turmas_concluidas': concluidas,
        'total_turmas': total_t,
    }
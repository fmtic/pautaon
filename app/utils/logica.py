"""
================================================================================
LOGICA.PY - Helpers de negócio (frequência, turmas, relatórios)
================================================================================

NOTA SOBRE TIPOS (Onda 2A):
    `Turma.data_inicio`, `Turma.data_fim`,
    `Frequencia.data`, `RegistroAula.data`, `TemaAula.data` e
    `DiaBloqueadoTurma.data` agora são `date`/`time` nativos.

NOTA SOBRE AGENDA (H5a):
    dias e horários de aula vivem SÓ em `turma_curso_horario` (grade da
    oferta). As colunas escalares `dias_semana`/`hora_inicio`/`hora_fim` de
    `Turma`/`TurmaCurso` não são lidas por este módulo.

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
    TurmaCurso,
    User,
    ValorEsportista,
)
from app.models.enums import (
    ConceitoFrequencia,
    CONCEITOS_PRESENCA,
    UserRole,
)
from app.utils.autor import autor_do_lancamento
from app.utils.datetime_parse import parse_date
from app.utils.timezone import get_local_now  # noqa: F401
from app.services.turma_curso import resolver_oferta_lancamento


NAME_LOWER_EXCEPTIONS = {
    'da', 'de', 'do', 'dos', 'das', 'e', 'van', 'von', 'del',
    'da', 'di', 'du', 'la', 'le', 'y', 'al',
}

# A1: conceitos que habilitam o lançamento de um Valor do Esportista.
# Comparação por TEXTO porque o formulário de frequência envia strings
# (`form.get`), não o Enum `ConceitoFrequencia`.
_CONCEITOS_PRESENCA_TEXTO = frozenset({'A', 'B', 'C', 'D'})


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

    # H3a/H5a: os dias da turma são DERIVADOS da grade das ofertas ativas
    # (uma consulta). Sem grade não há agenda: a lista sai vazia — não existe
    # mais leitura do CSV escalar de `dias_semana`.
    from app.services.turma_curso_horario import dias_da_turma

    dias_permitidos = dias_da_turma(turma.id)
    if not dias_permitidos:
        return datas

    inicio = datetime.combine(turma.data_inicio, time.min)
    fim = datetime.combine(turma.data_fim, time.min)

    if incluir_futuro:
        data_limite = fim
    else:
        hoje = datetime.now()
        data_limite = min(fim, hoje)

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
# CARGA HORÁRIA
# =============================================================================

def calcular_dias_aula_turma(turma: Turma) -> int:
    """
    Quantidade de dias de aula de uma turma no período letivo.

    Usa o mesmo calendário da pauta (dias da semana da turma entre
    data_inicio e data_fim), EXCLUINDO os dias sem aula do período
    (`DiaBloqueado`), com as exceções por turma (`DiaBloqueadoTurma`)
    já descontadas.
    """
    if not turma or not turma.data_inicio or not turma.data_fim:
        return 0
    blocked = _blocked_dates_str(turma)
    return len(gerar_datas(turma, incluir_futuro=True, blocked_dates=blocked))

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


#: Nome extenso de cada mês, por chave 'MM' (seletor de pauta mensal).
_NOMES_MESES = {
    '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
    '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
    '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro',
}


def meses_de_datas(datas_iso) -> list:
    """Meses (numero, nome) presentes em datas 'YYYY-MM-DD', em ordem.

    Único caminho de cálculo dos meses de calendário; usado por
    `carregar_contexto_turma` e por quem precisa recompor o seletor depois de
    filtrar as datas por oferta (ficha da turma no escopo do professor).
    """
    meses, vistos = [], set()
    for d in datas_iso:
        mes_num = d[5:7]
        if mes_num not in vistos:
            meses.append({
                'numero': mes_num,
                'nome': _NOMES_MESES.get(mes_num, 'Mês Desconhecido'),
            })
            vistos.add(mes_num)
    return meses


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

    meses_disponiveis = meses_de_datas(datas)

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

def _ler_registros_aula(
    turma_id: int,
    data_alvo: date,
    turma_curso_id: Optional[int] = None,
) -> Tuple[List[Frequencia], Optional[RegistroAula]]:
    """Linhas de frequência + diário da aula (com temas e valores em selectin)."""
    if turma_curso_id is not None:
        registros = (
            Frequencia.query
            .filter_by(turma_curso_id=turma_curso_id, data=data_alvo)
            .all()
        )
        diario = RegistroAula.query.filter_by(
            turma_curso_id=turma_curso_id, data=data_alvo
        ).first()
    else:
        # Legado (sem oferta): filtra turma_curso_id IS NULL para não
        # reaproveitar/reescrever registros de ofertas (mesma turma_id/data).
        registros = (
            Frequencia.query
            .filter_by(turma_id=turma_id, data=data_alvo, turma_curso_id=None)
            .all()
        )
        diario = RegistroAula.query.filter_by(
            turma_id=turma_id, data=data_alvo, turma_curso_id=None
        ).first()
    return registros, diario


def _resumo_diario(
    diario: Optional[RegistroAula],
) -> Tuple[List[int], str, str]:
    """Temas marcados no dia (nunca `None`), observações e atividades."""
    if diario is None:
        return [], "", ""
    temas = [tema.id for tema in diario.temas]
    if not temas and diario.tema_id is not None:
        temas = [diario.tema_id]
    return temas, diario.observacoes or "", diario.atividades or ""


def carregar_frequencias(
    turma_id: int,
    data: str | date,
    turma_curso_id: Optional[int] = None,
) -> Tuple[Dict[int, str], List[int], str]:
    """
    Carrega os conceitos lançados para uma turma (ou oferta) em uma data.

    Onda 2A: `Frequencia.data` e `RegistroAula.data` agora são `date`.
    A função aceita string ou date e normaliza via `parse_date`.

    Onda 4 (Fase 4, D1): com `turma_curso_id` informado, Frequência e Diário
    são lidos por oferta (`turma_curso_id`, `data`); com None, mantém o
    comportamento legado (filtro somente por `turma_id`, `data`).

    Temas múltiplos: o segundo elemento é sempre a **lista** de IDs de tema
    marcados no dia — vazia quando não há diário ainda (dia não lançado) ou
    quando `turma_id`/`data` são inválidos. Nunca `None`: o template testa
    `tema.id in tema_selecionado` e `None` derrubava a pauta com TypeError.

    :return: (dict{aluno_id: conceito}, tema_ids_selecionados | [], observacoes)
    """
    data_alvo = parse_date(data)
    if not turma_id or not data_alvo:
        return {}, [], ""

    registros, diario = _ler_registros_aula(turma_id, data_alvo, turma_curso_id)
    frequencias = {f.aluno_id: f.conceito for f in registros}
    tema_selecionado, obs_salva, _atividades = _resumo_diario(diario)

    return frequencias, tema_selecionado, obs_salva


def carregar_frequencias_e_valores(
    turma_id: int,
    data: str | date,
    turma_curso_id: Optional[int] = None,
) -> Tuple[Dict[int, str], List[ValorEsportista], List[int], str, str]:
    """Como `carregar_frequencias`, acrescido dos valores da AULA (AJ16-B).

    Devolve `(conceitos, valores_da_aula, temas, observacoes, atividades)`.
    Os valores vêm de `RegistroAula.valores` (relação N:N, `lazy='selectin'`),
    não mais de cada linha de frequência; o conjunto é preservado mesmo em
    aula sem presença. Valores **inativos** já vinculados continuam sendo
    devolvidos de propósito, para o template exibi-los e não perder histórico.
    """
    data_alvo = parse_date(data)
    if not turma_id or not data_alvo:
        return {}, [], [], "", ""

    registros, diario = _ler_registros_aula(turma_id, data_alvo, turma_curso_id)
    frequencias = {f.aluno_id: f.conceito for f in registros}
    valores_aula = list(diario.valores) if diario is not None else []
    tema_selecionado, obs_salva, atividades_salvas = _resumo_diario(diario)

    return frequencias, valores_aula, tema_selecionado, obs_salva, atividades_salvas


#: Mensagem única da pendência por aula (AJ16-B).
MENSAGEM_VALOR_AULA_OBRIGATORIO = (
    "Selecione ao menos um valor trabalhado na aula. Nada foi salvo."
)


class PendenciaValorAula(ValueError):
    """Lançamento recusado: aula com presença (A–D) e nenhum valor marcado.

    É levantada **antes** de qualquer escrita — nem conceito, nem linha de
    frequência, nem diário (temas/observações/atividades/valores).
    """

    def __init__(self):
        super().__init__(MENSAGEM_VALOR_AULA_OBRIGATORIO)


class ValorAulaInvalido(ValueError):
    """Seleção de valores inválida: nada pode ser gravado."""


def _ids_valor_do_form(form: Dict[str, str]) -> List[int]:
    """Ids únicos de `valor_ids`, recusando qualquer valor não numérico."""
    if hasattr(form, 'getlist'):
        brutos = form.getlist('valor_ids')
    else:
        brutos = form.get('valor_ids', [])
        if isinstance(brutos, (str, int)):
            brutos = [brutos]

    ids: List[int] = []
    for bruto in brutos:
        texto = str(bruto or '').strip()
        if not texto:
            continue
        if not texto.isdigit() or int(texto) <= 0:
            raise ValorAulaInvalido("Seleção de valores inválida. Nada foi salvo.")
        ids.append(int(texto))
    return list(dict.fromkeys(ids))


def _resolver_valores_da_aula(
    ids: List[int],
    unidade_id: Optional[int],
    valores_antigos: List[ValorEsportista],
) -> List[ValorEsportista]:
    """Resolve o conjunto da aula, recusando valor inexistente/inativo/estranho.

    Regra (AJ16-B):
        - id inexistente ou de outra unidade é recusado;
        - valor inativo **já vinculado** à aula é preservado;
        - valor inativo novo é recusado (mesmo espírito da A1/V2).

    A ordem final é alfabética (a mesma de `RegistroAula.valores`), sem
    duplicatas.
    """
    if not ids:
        return []

    antigos = {valor.id for valor in valores_antigos}
    encontrados = {
        valor.id: valor
        for valor in ValorEsportista.query.filter(
            ValorEsportista.id.in_(ids)
        ).all()
    }
    resolvidos: List[ValorEsportista] = []
    for valor_id in ids:
        valor = encontrados.get(valor_id)
        if valor is None:
            raise ValorAulaInvalido(
                f"Valor do Esportista {valor_id} não existe. Nada foi salvo."
            )
        if unidade_id is not None and valor.unidade_id != unidade_id:
            raise ValorAulaInvalido(
                "Um dos valores selecionados pertence a outra unidade. "
                "Nada foi salvo."
            )
        if not valor.ativo and valor_id not in antigos:
            raise ValorAulaInvalido(
                "Um dos valores selecionados está inativo. Nada foi salvo."
            )
        resolvidos.append(valor)

    return sorted(
        resolvidos,
        key=lambda valor: ((valor.nome or '').casefold(), valor.nome or '', valor.id),
    )


def unidade_tem_valores_ativos(unidade_id: Optional[int]) -> bool:
    """A obrigatoriedade só vale se a unidade tem catálogo ativo (V2).

    Unidade sem nenhum valor ativo não pode travar a pauta: a tela não teria
    opção para o professor escolher. `unidade_id=None` (turma sem unidade)
    olha o catálogo global — o mesmo escopo do seletor da pauta.
    """
    from app.models import ValorEsportista

    consulta = ValorEsportista.query.filter(ValorEsportista.ativo.is_(True))
    if unidade_id is not None:
        consulta = consulta.filter(ValorEsportista.unidade_id == unidade_id)
    return bool(db.session.query(consulta.exists()).scalar())


def _conceitos_enviados(
    form: Dict[str, str],
    alunos: List[Aluno],
) -> Dict[int, str]:
    """Conceitos não vazios enviados para os alunos da pauta."""
    conceitos: Dict[int, str] = {}
    for aluno in alunos:
        conceito = (form.get(f'aluno_{aluno.id}', '') or '').strip()
        if conceito:
            conceitos[aluno.id] = conceito
    return conceitos


def _aula_exige_valor(
    conceitos: Dict[int, str],
    unidade_id: Optional[int],
) -> bool:
    """A–D na pauta + catálogo ativo na unidade ⇒ a aula exige ≥1 valor."""
    if not unidade_tem_valores_ativos(unidade_id):
        return False
    return any(
        conceito in _CONCEITOS_PRESENCA_TEXTO
        for conceito in conceitos.values()
    )


def _planejar_frequencia(
    conceitos: Dict[int, str],
    alunos: List[Aluno],
    *,
    oferta_id: Optional[int],
    turma_id: int,
    data_alvo: date,
) -> List[Tuple[Aluno, str, Optional[Frequencia]]]:
    """Fase de LEITURA: resolve a linha existente de cada aluno com conceito.

    Aluno sem conceito não entra no plano: a linha existente fica intocada.
    """
    plano: List[Tuple[Aluno, str, Optional[Frequencia]]] = []
    for aluno in alunos:
        conceito = conceitos.get(aluno.id)
        if not conceito:
            continue

        if oferta_id is not None:
            freq = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_curso_id=oferta_id, data=data_alvo
            ).first()
        else:
            freq = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_id=turma_id, data=data_alvo,
                turma_curso_id=None,
            ).first()

        plano.append((aluno, conceito, freq))
    return plano


def salvar_frequencia(form: Dict[str, str]) -> Tuple[int, Optional[str]]:
    """
    Consolida os lançamentos de frequência e o diário da aula em um único commit.

    Onda 2A: `data` do formulário chega como string; convertida via `parse_date`
    antes de qualquer consulta/gravação.

    Onda 4 (Fase 4, D1): resolve a oferta de lançamento via
    `resolver_oferta_lancamento` (campo opcional `turma_curso` no formulário).
    Haverendo oferta, a busca do RegistroAula e da Frequencia existentes é
    feita por (turma_curso_id, data) — nunca por (turma_id, data), sob pena
    de o diário de uma segunda oferta sobrescrever o da primeira. Sem oferta
    (turma sem oferta ativa), cai no caminho legado por turma_id. `turma_id`
    continua sendo gravado em ambas as tabelas.

    :return: (turma_id, data_str) em caso de sucesso; (0, None) em caso de erro.

    F1 (autor do lançamento): cada linha criada recebe `autor_id`/`autor_nome`
    do usuário logado. Em linha existente o autor só é trocado quando o
    CONCEITO muda — regravar o mesmo conceito (ou só mexer nos valores da
    aula) mantém o autor anterior.

    AJ16-B: os valores/posturas do esportista são da AULA. O formulário envia
    `valor_ids` (repetido); o conjunto é validado e substituído por inteiro em
    `RegistroAula.valores`, com deduplicação. Havendo A–D na pauta e catálogo
    ativo na unidade, exigir ao menos um valor — sempre antes de qualquer
    escrita.
    """
    try:
        turma_raw = form.get('turma', '0').strip()
        turma_id = int(turma_raw) if turma_raw and turma_raw.isdigit() else 0

        data_raw = (form.get('data', '') or form.get('data_hidden', '')).strip()
        data_alvo = parse_date(data_raw)

        if hasattr(form, 'getlist'):
            temas_raw = form.getlist('tema_ids')
        else:
            temas_raw = form.get('tema_ids', [])
            if isinstance(temas_raw, str):
                temas_raw = [temas_raw]
        if not temas_raw:
            legado_tema = form.get('tema_id', '').strip()
            temas_raw = [legado_tema] if legado_tema else []
        if any(not str(valor).strip().isdigit() or int(valor) <= 0 for valor in temas_raw):
            raise ValueError("Seleção de temas inválida.")
        tema_ids = list(dict.fromkeys(int(valor) for valor in temas_raw))
        tema_id = tema_ids[0] if tema_ids else None
        texto_observacoes = form.get('observacoes', '').strip() or None
        # A1: atividades da aula — campo independente das observações.
        texto_atividades = form.get('atividades', '').strip() or None

        turma_curso_raw = form.get('turma_curso', '').strip()
        turma_curso_id = (
            int(turma_curso_raw) if turma_curso_raw and turma_curso_raw.isdigit() else None
        )

        if not data_alvo or turma_id == 0:
            return turma_id, None

        # --- Oferta de lançamento (Onda 4) ---
        # ValueError (2+ cursos sem escolha, oferta inválida etc.) é capturado
        # pelo except genérico abaixo → (0, None); na D2 a rota passará a
        # exibir a mensagem específica via flash.
        oferta = resolver_oferta_lancamento(
            turma_id, data_alvo, turma_curso_id=turma_curso_id,
            tema_ids=tema_ids,
        )
        oferta_id = oferta.id if oferta else None

        # --- Alunos da pauta + conceitos enviados ---
        alunos_post = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == turma_id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .all()
        )
        conceitos = _conceitos_enviados(form, alunos_post)

        # AJ18-C (item 1): defesa em profundidade — ignora conceitos enviados
        # para alunos cuja entrada na oferta é posterior à data-alvo. Linhas
        # já registradas antes da entrada não são alteradas (alunos sem conceito
        # enviado não entram no plano e permanecem intocados).
        if oferta_id is not None and data_alvo is not None:
            from app.services.entrada_oferta import aula_conta_para_aluno
            inscricoes_por_aluno = {}
            for insc in Inscricao.query.filter(
                Inscricao.turma_curso_id == oferta_id,
                Inscricao.ativo.is_(True),
            ).all():
                inscricoes_por_aluno.setdefault(insc.aluno_id, insc)
            for aluno_id_conceito in list(conceitos.keys()):
                insc = inscricoes_por_aluno.get(aluno_id_conceito)
                if insc is not None and not aula_conta_para_aluno(insc, data_alvo):
                    conceitos.pop(aluno_id_conceito, None)

        # AJ16-B: o valor/postura do esportista pertence à unidade da TURMA —
        # o mesmo escopo do GET (a sessão pode estar em Visão Global).
        turma_obj = db.session.get(Turma, turma_id)
        valor_unidade_id = (
            turma_obj.unidade_id if turma_obj is not None else get_unidade_id()
        )

        # --- Registro de aula existente (leitura para a validação) ---
        if oferta_id is not None:
            registro = RegistroAula.query.filter_by(
                turma_curso_id=oferta_id, data=data_alvo
            ).first()
        else:
            registro = RegistroAula.query.filter_by(
                turma_id=turma_id, data=data_alvo, turma_curso_id=None
            ).first()
        valores_antigos = list(registro.valores) if registro is not None else []

        # AJ16-B: valida o conjunto da aula ANTES de qualquer escrita. Ids
        # inexistentes, de outra unidade ou inativos novos são recusados; um
        # inativo já vinculado continua válido. O conjunto substitui o antigo
        # por inteiro (com deduplicação).
        ids_valores = _ids_valor_do_form(form)
        valores_aula = _resolver_valores_da_aula(
            ids_valores, valor_unidade_id, valores_antigos,
        )
        if _aula_exige_valor(conceitos, valor_unidade_id) and not valores_aula:
            raise PendenciaValorAula()

        plano = _planejar_frequencia(
            conceitos,
            alunos_post,
            oferta_id=oferta_id,
            turma_id=turma_id,
            data_alvo=data_alvo,
        )

        # --- Registro de aula (diário do educador) ---
        if registro:
            if registro.unidade_id is None and valor_unidade_id is not None:
                registro.unidade_id = valor_unidade_id
            registro.observacoes = texto_observacoes
            registro.atividades = texto_atividades
            registro.tema_id = tema_id  # compatibilidade com leitores legados
            registro.temas = TemaAula.query.filter(TemaAula.id.in_(tema_ids)).all() if tema_ids else []
            registro.instrutor_id = current_user.id
        else:
            registro = RegistroAula(
                turma_id=turma_id,
                turma_curso_id=oferta_id,
                data=data_alvo,
                tema_id=tema_id,  # espelho temporário durante a transição
                observacoes=texto_observacoes,
                atividades=texto_atividades,
                instrutor_id=current_user.id,
                unidade_id=valor_unidade_id,
            )
            registro.temas = TemaAula.query.filter(TemaAula.id.in_(tema_ids)).all() if tema_ids else []
            db.session.add(registro)
        registro.valores = valores_aula

        # --- Frequência por aluno (plano já validado) ---
        autor_id, autor_nome = autor_do_lancamento()
        for aluno, conceito, freq in plano:
            if freq is None:
                freq = Frequencia(
                    aluno_id=aluno.id,
                    turma_id=turma_id,
                    turma_curso_id=oferta_id,
                    data=data_alvo,
                    autor_id=autor_id,
                    autor_nome=autor_nome,
                    unidade_id=valor_unidade_id,
                )
                db.session.add(freq)
            else:
                if freq.unidade_id is None and valor_unidade_id is not None:
                    freq.unidade_id = valor_unidade_id
                if freq.conceito != conceito:
                    # F1: o autor é o último que MUDOU o conceito; regravar o
                    # mesmo valor não troca o autor.
                    freq.autor_id = autor_id
                    freq.autor_nome = autor_nome
            freq.conceito = conceito

        db.session.commit()
        return turma_id, data_alvo.strftime('%Y-%m-%d')

    except (PendenciaValorAula, ValorAulaInvalido):
        db.session.rollback()
        raise
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
    """Retorna (geral, por_programa, por_turma, por_professor), em %.

    ETAPA D3b.4a (decisões 1, 3 e 4): o percentual vem da regra única do
    serviço `frequencia_oferta`; `por_turma` agregada em lote
    (`agregar_por_turma` — todas as linhas da turma, ofertas + legado, como
    a tela já exibe) e `por_professor` passa a ser o professor DA OFERTA
    (`TurmaCurso.professor_id`, sem fallback para a turma; as linhas
    legadas entram pela oferta única ativa da turma — regra D2 — dentro de
    `agregar_por_oferta`). `por_programa` continua por `Turma.programa`
    (turno/coorte é D3b.7).
    """
    # Import local: mesma lição de `contar_ofertas_conselho` (evita
    # dependência de `app.services` no carregamento de `logica`).
    from app.services.frequencia_oferta import (
        agregar_por_oferta,
        agregar_por_turma,
        percentual,
    )

    def calc_pc(query) -> float:
        # D3b.4a (decisão 4): percentual pela regra única do serviço —
        # presentes/(presentes+faltas), J fora, 1 casa (mesmo resultado do
        # antigo `calcular_estatisticas_frequencia`, agora fonte única).
        contagens = (
            query.filter(Frequencia.conceito.in_(["A", "B", "C", "D", "F"]))
            .with_entities(Frequencia.conceito, db.func.count(Frequencia.id))
            .group_by(Frequencia.conceito)
            .all()
        )
        presentes = sum(
            n for conceito, n in contagens if conceito in ("A", "B", "C", "D")
        )
        faltas = sum(n for conceito, n in contagens if conceito == "F")
        return percentual(presentes, faltas)

    q_geral = Frequencia.query.join(
        Turma, Frequencia.turma_id == Turma.id
    ).filter(Turma.ativo == True)
    if unidade_id:
        q_geral = q_geral.filter(Turma.unidade_id == unidade_id)
    p_geral = calc_pc(q_geral)

    f_prog: Dict[str, float] = {}
    # ETAPA D3b-2.6: agrupamento por programa da OFERTA (TurmaCurso.programa),
    # reusando a regra D2 do legado (oferta única ativa recebe as linhas
    # legadas NULL; em turma sem oferta única ativa, o legado cai em
    # Turma.programa, projeção). Fórmula §8.1 inalterada.
    from collections import defaultdict

    from app.services.frequencia_oferta import ofertas_unicas_ativas

    # Ofertas ativas das turmas ativas no escopo.
    ofertas_q = (
        db.session.query(TurmaCurso.id, TurmaCurso.turma_id, TurmaCurso.programa)
        .join(Turma, Turma.id == TurmaCurso.turma_id)
        .filter(Turma.ativo == True)
    )
    if unidade_id:
        ofertas_q = ofertas_q.filter(Turma.unidade_id == unidade_id)
    ofertas_rows = ofertas_q.all()
    ofertas_map: Dict[int, tuple[int, str]] = {
        oid: (tid, prog) for oid, tid, prog in ofertas_rows
    }
    unicas = ofertas_unicas_ativas(list(ofertas_map.keys()))
    turma_unica_oferta: Dict[int, int] = {
        ofertas_map[oid][0]: oid for oid in unicas
    }

    # Programas distintos (ofertas + projeção das turmas sem oferta única).
    programas_distintos: set[str] = {prog for _, _, prog in ofertas_rows}
    turmas_scope = Turma.query.filter_by(ativo=True)
    if unidade_id:
        turmas_scope = turmas_scope.filter_by(unidade_id=unidade_id)
    for t in turmas_scope.all():
        if t.id not in turma_unica_oferta:
            if t.programa:
                programas_distintos.add(t.programa)

    # Acumular presentes/faltas por programa (UMA consulta em Frequencia).
    totais_por_prog: Dict[str, list[int]] = defaultdict(lambda: [0, 0])
    fq = (
        db.session.query(
            Frequencia.turma_id,
            Frequencia.turma_curso_id,
            Frequencia.conceito,
            Turma.programa,
        )
        .join(Turma, Frequencia.turma_id == Turma.id)
        .filter(Turma.ativo == True)
    )
    if unidade_id:
        fq = fq.filter(Turma.unidade_id == unidade_id)
    for tid, tcid, conceito, prog_turma in fq.all():
        if conceito not in ("A", "B", "C", "D", "F"):
            continue
        # Programa da linha:
        if tcid is not None and tcid in ofertas_map:
            prog = ofertas_map[tcid][1]
        else:
            oid = turma_unica_oferta.get(tid)
            if oid is not None:
                prog = ofertas_map[oid][1]
            else:
                prog = prog_turma
        if prog is None:
            continue
        if conceito in ("A", "B", "C", "D"):
            totais_por_prog[prog][0] += 1
        elif conceito == "F":
            totais_por_prog[prog][1] += 1

    for prog in sorted(programas_distintos):
        pres, fal = totais_por_prog.get(prog, [0, 0])
        f_prog[prog] = percentual(pres, fal)

    f_turma: Dict[str, float] = {}
    if todas_as_turmas:
        # D3b.4a: UMA consulta agregada para todas as turmas (sem N+1);
        # turmas sem frequência ficam com 0.0 (como antes).
        agregado_turmas = agregar_por_turma(
            [t.id for t in todas_as_turmas]
        )
        for t in todas_as_turmas:
            info = agregado_turmas.get(t.id)
            f_turma[t.nome] = info.pct_turma if info is not None else 0.0

    f_prof: Dict[str, float] = {}
    # Onda 2B (limpeza): usa o enum em vez da string 'professor'.
    prof_query = User.query.filter_by(role=UserRole.PROFESSOR.value)
    if unidade_id:
        prof_query = prof_query.filter_by(unidade_id=unidade_id)
    nomes_prof = {prof.id: prof.name for prof in prof_query.all()}

    # D3b.4a (decisão 1): professor DA OFERTA (TurmaCurso.professor_id) em
    # turmas ativas no escopo; o serviço aplica a regra D2 ao legado.
    q_ofertas = db.session.query(TurmaCurso.id, TurmaCurso.professor_id).join(
        Turma, Turma.id == TurmaCurso.turma_id
    ).filter(Turma.ativo == True)
    if unidade_id:
        q_ofertas = q_ofertas.filter(Turma.unidade_id == unidade_id)

    ofertas_por_prof: Dict[int, List[int]] = {}
    for oferta_id, prof_rel in q_ofertas.all():
        if prof_rel is None or prof_rel not in nomes_prof:
            continue
        ofertas_por_prof.setdefault(prof_rel, []).append(oferta_id)

    for prof_rel, ids in ofertas_por_prof.items():
        agregado = agregar_por_oferta(ids)
        presentes = sum(info.presentes for info in agregado.values())
        faltas = sum(info.faltas for info in agregado.values())
        if presentes + faltas > 0:
            f_prof[nomes_prof[prof_rel]] = percentual(presentes, faltas)

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
            registro_query = (
                RegistroAula.query
                .join(Turma, Turma.id == RegistroAula.turma_id)
                .filter(RegistroAula.data.between(inicio, fim))
            )
            if unidade_id:
                tema_query = tema_query.filter_by(unidade_id=unidade_id)
                registro_query = registro_query.filter(
                    Turma.unidade_id == unidade_id
                )
            total = tema_query.count()
            real = registro_query.count()
            prog_aulas = round((real / total * 100), 1) if total > 0 else 0.0
        except (ValueError, TypeError):
            current_app.logger.exception(
                "Erro ao calcular progresso de aulas do conselho"
            )

    # D5.3: as reuniões do conselho são contadas por OFERTA — ofertas ativas
    # de turmas ativas (concluídas × total), respeitando a unidade. Turma sem
    # oferta ativa não abre conselho e não entra na conta. Import local para
    # não criar dependência de `app.services` no carregamento de `logica`
    # (lição do ciclo app.services → app.relatorios).
    from app.services.turma_curso import contar_ofertas_conselho

    concluidas, total_t = contar_ofertas_conselho(unidade_id)
    prog_reunioes = float(
        round((concluidas / total_t * 100), 1) if total_t > 0 else 0.0
    )

    return {
        'progresso_aulas': prog_aulas,
        'progresso_reunioes': prog_reunioes,
        'turmas_concluidas': concluidas,
        'total_turmas': total_t,
    }

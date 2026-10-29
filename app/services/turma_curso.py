"""
Regras de ofertas de curso na turma (Onda 4 — Fases 2 e 3).

A entidade `TurmaCurso` (oferta concreta de um curso em uma turma) nasce na
Fase 1; aqui ficam as regras de aplicação que garantem o contrato da
especificação §4/§5/§14:

    - Cadastro incremental: cada oferta é adicionada uma a uma, sem limite.
    - `UNIQUE(turma_id, curso_id)`: o mesmo curso não entra duas vezes na
      mesma turma (a constraint também protege no banco).
    - Principal: com uma única oferta ativa a marca é opcional; com duas ou
      mais ofertas ativas deve existir exatamente um curso principal. O
      máximo já é garantido pelo índice único parcial `uix_turma_curso_principal`;
      a obrigatoriedade é validada aqui.
    - Professor (G1/P2): toda oferta tem professor — vazio é recusado no
      cadastro (`adicionar_oferta`, `criar_oferta_inicial_da_turma`) e na
      edição (`editar_oferta`); trocar é permitido e, havendo lançamento na
      oferta, exige confirmação e fica registrado em `log_acao`.
    - Concomitância: horários sobrepostos entre ofertas ativas da mesma turma
      são permitidos; o usuário recebe um aviso informativo.
    - Compatibilidade legada (§14): o espelhamento para as colunas de `Turma`
      só ocorre em turma com oferta única ativa e que nunca teve curso legado
      (situação criada por esta feature). Turmas do backfill e turmas com
      2+ ofertas mantêm as colunas legadas congeladas — sem dual-write.
      H5a: o espelho NÃO inclui mais agenda — `dias_semana`/`hora_inicio`/
      `hora_fim` de `Turma` e `TurmaCurso` não são lidos nem escritos aqui; a
      grade (`turma_curso_horario`) é a única fonte.

Todas as funções fazem `db.session.commit()` internamente e levantam
`ValueError` com mensagem de usuário amigável em caso de violação de regra;
quem chama (rotas) converter em `flash`.
"""
from __future__ import annotations

import logging
import re
from datetime import date, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload, selectinload

from app.database import db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PeriodoLetivo,
    TemaAula,
    Turma,
    TurmaCurso,
    User,
)
from app.models.base import get_local_now
from app.services.aluno_info_professor import condicao_professor_da_oferta
from app.services.turma_curso_horario import (
    Linha,
    definir_grade,
    grade_da_oferta,
)
from app.utils.dias_semana import (
    weekday_para_nome,
    weekdays_para_csv,
)

logger = logging.getLogger(__name__)

# Mensagem única usada quando a oferta fica sem professor (G1/P2: toda oferta
# precisa de um professor responsável — trocar é permitido, esvaziar, não).
_PROFESSOR_OBRIGATORIO = (
    "Selecione o professor responsável: toda oferta precisa de um professor."
)


# Mensagem única usada quando a agenda enviada está incompleta (H2: toda
# oferta precisa de ao menos um dia e horário completo início+fim).
_AGENDA_INCOMPLETA = (
    "Selecione ao menos um dia de aula (segunda a sábado) e preencha as horas "
    "de início e fim, com o fim maior que o início."
)


def ofertas_ativas(turma_id: int):
    """Ofertas ativas da turma em ordem estável (legado primeiro)."""
    return (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )


def contar_ofertas_conselho(unidade_id=None) -> tuple[int, int]:
    """(concluídas, total) de ofertas ativas de turmas ativas (D5.3).

    Turma sem oferta ativa não entra em nenhum dos dois lados; a unidade é
    aplicada quando informada (mesma regra dos demais contadores).
    """
    query = (
        db.session.query(TurmaCurso.conselho_concluido)
        .join(Turma, Turma.id == TurmaCurso.turma_id)
        .filter(TurmaCurso.ativo.is_(True), Turma.ativo.is_(True))
    )
    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)
    flags = [bool(flag) for (flag,) in query.all()]
    return sum(flags), len(flags)


def alunos_ativos_por_oferta(oferta_ids) -> dict[int, int]:
    """Contagem de alunos ativos por oferta em uma única consulta."""
    ids = [oferta_id for oferta_id in oferta_ids if oferta_id is not None]
    if not ids:
        return {}
    linhas = (
        db.session.query(
            Inscricao.turma_curso_id,
            func.count(func.distinct(Inscricao.aluno_id)),
        )
        .filter(
            Inscricao.turma_curso_id.in_(ids),
            Inscricao.ativo.is_(True),
        )
        .group_by(Inscricao.turma_curso_id)
        .all()
    )
    return {oferta_id: total for oferta_id, total in linhas}


def ofertas_do_painel_conselho(
    unidade_id=None,
    *,
    programa=None,
    turno=None,
    professor_id=None,
) -> list[dict]:
    """Uma entrada por OFERTA ativa de turma ativa para o painel do conselho.

    Cada item traz `oferta`, `turma`, `curso`, `professor`, `programa`,
    `turno`, `concluida` (flag da OFERTA) e `alunos_ativos`. Turma sem oferta
    ativa simplesmente não aparece. Turma, curso e professor vêm por
    `joinedload` e a contagem de alunos em uma única agregação — sem N+1 na
    listagem.
    """
    query = (
        TurmaCurso.query
        .join(Turma, Turma.id == TurmaCurso.turma_id)
        .join(Curso, Curso.id == TurmaCurso.curso_id)
        .options(
            joinedload(TurmaCurso.turma),
            joinedload(TurmaCurso.curso),
            joinedload(TurmaCurso.professor),
            # H3e: dias/horários exibidos no painel saem da grade (lote).
            selectinload(TurmaCurso.horarios),
        )
        .filter(TurmaCurso.ativo.is_(True), Turma.ativo.is_(True))
    )
    if unidade_id:
        query = query.filter(Turma.unidade_id == unidade_id)
    if programa and programa != "Todos":
        query = query.filter(Turma.programa == programa)
    if turno and turno != "Todos":
        query = query.filter(Turma.turno == turno)
    if professor_id:
        # Consenso de 29/10/2026 (conselho do professor): "professor da
        # oferta" SEM herança do professor da turma — a MESMA expressão da
        # pauta/I1 (PARTE B/G1). O professor da turma que não está na oferta
        # não enxerga esse conselho; o da oferta enxerga.
        query = query.filter(condicao_professor_da_oferta(professor_id))

    ofertas = query.order_by(Turma.ordenacao, Turma.nome, TurmaCurso.id).all()
    contagens = alunos_ativos_por_oferta([oferta.id for oferta in ofertas])
    return [
        {
            "oferta": oferta,
            "turma": oferta.turma,
            "curso": oferta.curso,
            "professor": oferta.professor or oferta.turma.professor,
            "programa": oferta.programa or oferta.turma.programa,
            "turno": oferta.turno or oferta.turma.turno,
            "concluida": bool(oferta.conselho_concluido),
            "alunos_ativos": contagens.get(oferta.id, 0),
        }
        for oferta in ofertas
    ]


def turma_tem_historico(turma_id: int) -> bool:
    """True se a turma tem histórico que impede a exclusão física
    (Onda 4, Etapa I).

    "Tem histórico" = existe qualquer linha em `Frequencia`, `RegistroAula`,
    `ConselhoClasse` ou `Transferencia` ligada à turma — por `turma_id` ou,
    em `Frequencia`/`RegistroAula`, por `turma_curso_id` de uma de suas ofertas;
    em `Transferencia`, por `turma_origem_id` ou `turma_destino_id`.
    `DiaBloqueadoTurma` e `TemaAula` NÃO contam como histórico (são vínculos
    de agenda/planejamento, tratados na exclusão).
    """
    from app.models import ConselhoClasse, Frequencia, RegistroAula, Transferencia

    oferta_ids = [o.id for o in TurmaCurso.query.filter_by(turma_id=turma_id).all()]

    if Frequencia.query.filter(
        or_(
            Frequencia.turma_id == turma_id,
            Frequencia.turma_curso_id.in_(oferta_ids),
        )
    ).first():
        return True
    if RegistroAula.query.filter(
        or_(
            RegistroAula.turma_id == turma_id,
            RegistroAula.turma_curso_id.in_(oferta_ids),
        )
    ).first():
        return True
    if ConselhoClasse.query.filter_by(turma_id=turma_id).first():
        return True
    if Transferencia.query.filter(
        or_(
            Transferencia.turma_origem_id == turma_id,
            Transferencia.turma_destino_id == turma_id,
        )
    ).first():
        return True
    return False


def _normalizar_agenda(agenda: list) -> list[tuple[int, time | None, time | None]]:
    """Normaliza a grade CANDIDATA para tuplas ordenadas por dia.

    Aceita itens no formato do serviço — ``(dia, hora_inicio, hora_fim)`` — e
    ``Linha`` da grade lida da oferta (``grade_da_oferta``).
    """
    itens: list[tuple[int, time | None, time | None]] = []
    for item in agenda:
        if isinstance(item, Linha):
            itens.append((item.dia_semana, item.hora_inicio, item.hora_fim))
        else:
            dia, ini, fim = item
            itens.append((int(dia), ini, fim))
    return sorted(itens, key=lambda t: t[0])


def _sobreposicao_horario(a_ini: time, a_fim: time, b_ini: time, b_fim: time) -> bool:
    """True se os intervalos [a_ini, a_fim) e [b_ini, b_fim) se sobrepõem
    estritamente (adjacência fimA==iniB NÃO é sobreposição)."""
    return a_ini < b_fim and b_ini < a_fim


def _sobreposicao_vigencia(
    a_ini: date | None, a_fim: date | None,
    b_ini: date | None, b_fim: date | None,
) -> bool:
    """True se os intervalos de vigência se interceptam.
    NULL em qualquer extremo = aberto (não limita).
    """
    if a_fim is not None and b_ini is not None and a_fim < b_ini:
        return False
    if b_fim is not None and a_ini is not None and b_fim < a_ini:
        return False
    return True


def _mensagem_conflito(
    outra: TurmaCurso,
    grade_outra: list[tuple[int, time | None, time | None]],
    dias_conflito: list[int],
) -> str:
    """Aviso de concomitância citando o(s) dia(s) em conflito (H3b).

    Grade uniforme da outra oferta → mantém o formato anterior
    (``<dias CSV>, HH:MM–HH:MM``), que é o texto caracterizado nos testes.
    Grade não uniforme → um segmento por dia em conflito
    (``Terça 08:00–10:00; Quinta 14:00–16:00``).
    """
    curso_nome = outra.curso.nome if outra.curso else f"curso #{outra.curso_id}"
    pares = {(ini, fim) for _, ini, fim in grade_outra}
    if len(pares) == 1:
        ini, fim = next(iter(pares))
        # H3f: os dias citados no aviso saem da grade recebida (fonte da
        # verdade), não da projeção escalar; para uniforme o CSV é o mesmo.
        dias_txt = weekdays_para_csv([dia for dia, _, _ in grade_outra])
        detalhe = f"{dias_txt}, {ini:%H:%M}–{fim:%H:%M}"
    else:
        por_dia = {dia: (ini, fim) for dia, ini, fim in grade_outra}
        detalhe = "; ".join(
            f"{weekday_para_nome(dia)} "
            f"{por_dia[dia][0]:%H:%M}–{por_dia[dia][1]:%H:%M}"
            for dia in dias_conflito
        )
    return (
        f"Horário concomitante com '{curso_nome}' ({detalhe}). "
        "A oferta foi salva."
    )


def _agenda_da_oferta(
    oferta: TurmaCurso,
) -> list[tuple[int, time | None, time | None]] | None:
    """Itens ``(dia, início, fim)`` da **grade atual** da oferta (H3f/H5a).

    Única fonte dos defaults de `editar_oferta` e da checagem de conflito.
    Oferta **sem grade** é estado inválido desde o H5a: registra ``logger.error``
    e devolve ``None`` — as colunas escalares nunca são lidas.
    """
    linhas = grade_da_oferta(oferta)
    if linhas:
        return [(l.dia_semana, l.hora_inicio, l.hora_fim) for l in linhas]
    logger.error(
        "Oferta %s sem grade: agenda indefinida (estado inválido desde o H5a).",
        oferta.id,
    )
    return None


def _conflitos_horario_concomitante(
    turma_id: int,
    *,
    data_inicio: date | None = None,
    data_fim: date | None = None,
    exclude_oferta_id: int | None = None,
    agenda: list | None = None,
) -> list[str]:
    """Lista conflitos POR DIA com outras ofertas ativas da mesma turma (H3b).

    Para cada weekday em comum, compara o intervalo DESSE dia; há conflito
    quando os intervalos se sobrepõem (início_a < fim_b e início_b < fim_a).
    Horários adjacentes (fim = início) NÃO conflitam. A vigência continua
    limitando a comparação (sem interseção → sem conflito). Concomitância é
    permitida; as mensagens servem apenas como ALERTA — nunca bloqueiam.

    A grade candidata vem SEMPRE de `agenda` (itens ``(dia, ini, fim)`` ou
    ``Linha``), necessária quando a oferta ainda não tem linhas no banco
    (criação) ou tem grade diferente da atual. Sem `agenda` não há checagem
    (H5a: não existe mais a conversão do trio escalar). As grades das demais
    ofertas saem em UMA consulta: a relação ``horarios`` é ``selectin`` e vem
    carregada junto com as ofertas (``grade_da_oferta`` não consulta de novo)
    — sem N+1. Oferta ativa **sem grade** não é comparada (estado inválido,
    ``logger.error``).
    """
    grade_nova = _normalizar_agenda(agenda) if agenda is not None else []
    if not grade_nova:
        return []

    outras = (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )
    outras = [
        o for o in outras
        if not (exclude_oferta_id and o.id == exclude_oferta_id)
    ]

    por_dia_nova = {dia: (ini, fim) for dia, ini, fim in grade_nova}
    conflitos = []
    for outra in outras:
        # A relação `horarios` é selectin: a grade já veio no lote acima.
        grade_outra = [
            (l.dia_semana, l.hora_inicio, l.hora_fim)
            for l in grade_da_oferta(outra)
        ]
        if not grade_outra:
            logger.error(
                "Oferta %s sem grade: concomitância não comparada (estado "
                "inválido desde o H5a).", outra.id,
            )
            continue
        if not _sobreposicao_vigencia(
            data_inicio, data_fim, outra.data_inicio, outra.data_fim
        ):
            continue

        por_dia_outra = {dia: (ini, fim) for dia, ini, fim in grade_outra}
        dias_conflito = []
        for dia in sorted(set(por_dia_nova) & set(por_dia_outra)):
            ini_a, fim_a = por_dia_nova[dia]
            ini_b, fim_b = por_dia_outra[dia]
            if None in (ini_a, fim_a, ini_b, fim_b):
                continue  # dia sem horário (legado) não permite comparar
            if _sobreposicao_horario(ini_a, fim_a, ini_b, fim_b):
                dias_conflito.append(dia)
        if dias_conflito:
            conflitos.append(_mensagem_conflito(outra, grade_outra, dias_conflito))
    return conflitos


def _validar_curso(turma: Turma, curso_id: int) -> Curso:
    curso = db.session.get(Curso, curso_id)
    if curso is None or not curso.ativo:
        raise ValueError("Selecione um curso ativo para ofertar na turma.")
    if turma.unidade_id is None or curso.unidade_id != turma.unidade_id:
        raise ValueError("O curso selecionado não pertence à unidade da turma.")
    # O UNIQUE(turma_id, curso_id) é pleno — vale também para ofertas já
    # desativadas (histórico). Reofertar o mesmo curso exigiria reativar o
    # registro anterior, não criar um novo.
    existente = TurmaCurso.query.filter_by(turma_id=turma.id, curso_id=curso_id).first()
    if existente is not None:
        if existente.ativo:
            raise ValueError(
                f"O curso '{curso.nome}' já é ofertado nesta turma. "
                "Cada curso pode entrar apenas uma vez na mesma turma."
            )
        raise ValueError(
            f"O curso '{curso.nome}' já possui histórico nesta turma "
            "(oferta desativada). Entre em contato com a administração para "
            "reativar o registro anterior."
        )
    return curso


def _validar_professor(professor_id, unidade_id):
    """Professor da oferta: obrigatório (G1/P2) e da unidade da turma.

    Esvaziar não é aceito — a oferta sem professor não libera acesso a nada
    (regra "sem herança" do I1, `professor_da_oferta`) e deixa a turma órfã na
    tela do professor. Trocar (outro id) é permitido: quem decide a propagação
    do acesso é a rota (`oferta_tem_lancamentos`).
    """
    if not professor_id:
        raise ValueError(_PROFESSOR_OBRIGATORIO)
    professor = db.session.get(User, int(professor_id))
    if (
        professor is None
        or professor.role != "professor"
        or (unidade_id and professor.unidade_id != unidade_id)
    ):
        raise ValueError(
            "Professor inválido para a unidade da turma."
        )
    return professor.id


# -----------------------------------------------------------------------------
# Troca de professor da oferta (E2): confirmação quando há lançamento e registro
# do anterior e do novo em `log_acao`.
# -----------------------------------------------------------------------------

#: `acao` da entrada de `log_acao` gravada na troca de professor da oferta.
ACAO_TROCA_PROFESSOR_OFERTA = "Trocar Professor da Oferta"

_PADRAO_TROCA_PROFESSOR = re.compile(
    r"\Aoferta_id=(?P<oferta>\d+)"
    r" anterior_id=(?P<anterior>\d+|none)"
    r' anterior_nome="(?P<anterior_nome>[^"]*)"'
    r" novo_id=(?P<novo>\d+|none)"
    r' novo_nome="(?P<novo_nome>[^"]*)"\Z'
)


def _ref_professor(professor_id) -> tuple[str, str]:
    """`(token_id, nome)` do professor para o texto do log (`none`/vazio)."""
    if not professor_id:
        return "none", ""
    professor = db.session.get(User, int(professor_id))
    return str(int(professor_id)), (professor.name if professor else "")


def formatar_detalhe_troca_professor(oferta_id, anterior_id=None, novo_id=None) -> str:
    """Texto (parseável) do `detalhes` da troca: id e nome de cada professor."""
    a_token, a_nome = _ref_professor(anterior_id)
    n_token, n_nome = _ref_professor(novo_id)
    return (
        f"oferta_id={int(oferta_id)} "
        f'anterior_id={a_token} anterior_nome="{a_nome}" '
        f'novo_id={n_token} novo_nome="{n_nome}"'
    )


def parsear_detalhe_troca_professor(detalhes) -> dict | None:
    """`{oferta_id, anterior_id, anterior_nome, novo_id, novo_nome}` ou `None`."""
    if not detalhes:
        return None
    achado = _PADRAO_TROCA_PROFESSOR.match(str(detalhes).strip())
    if not achado:
        return None

    def _id(valor):
        return None if valor == "none" else int(valor)

    return {
        "oferta_id": int(achado.group("oferta")),
        "anterior_id": _id(achado.group("anterior")),
        "anterior_nome": achado.group("anterior_nome"),
        "novo_id": _id(achado.group("novo")),
        "novo_nome": achado.group("novo_nome"),
    }


def oferta_tem_lancamentos(oferta_id: int) -> bool:
    """Há lançamento (frequência, registro de aula ou conselho) na oferta?

    Usado como guarda da troca de professor: com lançamento gravado, a troca
    precisa de confirmação explícita (mesmo padrão da limpeza de lançamentos
    na edição da turma).
    """
    from app.models import ConselhoClasse, Frequencia, RegistroAula

    return bool(
        db.session.query(Frequencia.id)
        .filter(Frequencia.turma_curso_id == oferta_id)
        .first()
        or db.session.query(RegistroAula.id)
        .filter(RegistroAula.turma_curso_id == oferta_id)
        .first()
        or db.session.query(ConselhoClasse.id)
        .filter(ConselhoClasse.turma_curso_id == oferta_id)
        .first()
    )


def ofertas_com_lancamentos(oferta_ids) -> set[int]:
    """Versão em lote de `oferta_tem_lancamentos` (telas que listam ofertas).

    Três consultas `DISTINCT` no total — uma por tipo de lançamento — em vez de
    uma por linha da listagem.
    """
    from app.models import ConselhoClasse, Frequencia, RegistroAula

    ids = [int(id_oferta) for id_oferta in oferta_ids if id_oferta]
    if not ids:
        return set()
    com_lancamento: set[int] = set()
    for modelo in (Frequencia, RegistroAula, ConselhoClasse):
        com_lancamento.update(
            id_oferta
            for (id_oferta,) in (
                db.session.query(modelo.turma_curso_id)
                .filter(modelo.turma_curso_id.in_(ids))
                .distinct()
                .all()
            )
        )
    return com_lancamento


def gravar_troca_professor_da_oferta(
    oferta_id, anterior_id, novo_id, *,
    usuario_id=None, usuario_nome=None, ip=None, unidade_id=None,
) -> None:
    """Acrescenta o LogAcao da troca de professor (sem commit).

    Grava só os ids e nomes do professor anterior e do novo — o formato das
    demais entradas do log (repr do objeto, gravado pelo listener de
    auditoria) permanece intocado.
    """
    from app.models import LogAcao

    db.session.add(LogAcao(
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
        acao=ACAO_TROCA_PROFESSOR_OFERTA,
        detalhes=formatar_detalhe_troca_professor(
            oferta_id, anterior_id=anterior_id, novo_id=novo_id
        ),
        ip=ip,
        unidade_id=unidade_id,
    ))


def _validar_principal_obrigatorio(turma: Turma, principal_oferta: bool):
    """Ao passar a ter 2+ ofertas ativas, deve existir exatamente um principal.

    Como a nova oferta ainda não está no banco, a conta considera as ofertas
    ativas existentes: se alguma já é principal, a nova pode entrar sem marca;
    caso contrário, a nova oferta precisa ser marcada como principal.
    """
    ativas = ofertas_ativas(turma.id)
    if len(ativas) >= 1 and not principal_oferta and not any(o.principal for o in ativas):
        raise ValueError(
            "A turma passa a ter mais de um curso: marque exatamente um "
            "como curso principal desta oferta."
        )


def _sincronizar_legado(turma: Turma, oferta: TurmaCurso) -> None:
    """Espelhamento controlado (§14): apenas turma com oferta única ativa
    e sem curso legado algum nunca teve vínculo — situação criada na Fase 2.
    """
    ativas = ofertas_ativas(turma.id)
    if len(ativas) != 1 or turma.curso_id is not None:
        return
    # Espelha a oferta única nas colunas legadas de Turma, para que a turma
    # criada no fluxo novo (sem curso) passe a exibir os dados do curso no
    # card da listagem e nos leitores que ainda usam as colunas de Turma.
    # H5a: a agenda NÃO entra no espelho — dias/horários vivem só na grade.
    turma.curso_id = oferta.curso_id
    turma.professor_id = oferta.professor_id
    turma.turno = oferta.turno
    turma.data_inicio = oferta.data_inicio
    turma.data_fim = oferta.data_fim
    turma.centro_custo = oferta.centro_custo
    turma.programa = oferta.programa


def sincronizar_programa_turma(turma: Turma) -> None:
    """Projeta na turma o programa da oferta principal ativa.

    Quando há uma única oferta ativa, ela é a referência mesmo sem a marca
    explícita de principal. Sem ofertas ativas, limpa a projeção.
    """
    ativas = ofertas_ativas(turma.id)
    principal = next((o for o in ativas if o.principal), None)
    referencia = principal or (ativas[0] if ativas else None)
    turma.programa = referencia.programa if referencia else None


def criar_oferta_inicial_da_turma(
    turma: Turma, agenda: list | None = None
) -> TurmaCurso | None:
    """Cria a oferta inicial de uma turma recém-cadastrada que tem curso legado.

    Espelha o backfill da migration `311d554dfd6e`: se a turma tem `curso_id`
    e ainda não tem **nenhuma** oferta (ativa ou desativada), gera uma única
    `TurmaCurso` copiando os atributos da própria turma (professor, turno,
    dias da semana, horários, datas, centro de custo e unidade), com
    `principal=False` (oferta única não exige marcação).

    Idempotente: havendo qualquer oferta na turma, devolve a existente sem
    criar nada. Turma sem `curso_id` não gera oferta (devolve `None`).

    Diferente das demais funções deste módulo: **não** faz commit — apenas
    `add`/`flush` — para que a rota grave turma e oferta na mesma transação
    (falha na oferta desfaz a turma). Não valida concomitância: a oferta
    replica exatamente a grade já aceita da turma.

    Desde o H2 a agenda da oferta é a GRADE (`definir_grade`): toda oferta
    nasce com ao menos um dia e o par completo de horários, e as colunas
    escalares não são fonte nem destino. H5a: sem `agenda`, ou com agenda
    vazia, a criação é recusada com ValueError — não existe mais herança a
    partir das colunas da turma (nunca se cria oferta com grade parcial).
    G1/P2: turma sem professor também não gera oferta (ValueError) — o
    professor espelhado é o da própria turma.

    H4: `agenda` (itens ``(dia_semana, hora_inicio, hora_fim)``) é a grade por
    dia enviada pelo formulário — é ela que é gravada (pode ser NÃO uniforme).
    """
    existente = (
        TurmaCurso.query
        .filter_by(turma_id=turma.id)
        .order_by(TurmaCurso.id)
        .first()
    )
    if existente is not None:
        return existente

    if turma.curso_id is None:
        return None

    if not turma.programa or not turma.programa.strip():
        raise ValueError("Toda oferta precisa ter um programa.")

    # H5a: a agenda da oferta inicial vem SEMPRE do formulário (grade por
    # dia). Os escalares da turma não são lidos em nenhuma hipótese.
    itens = agenda or None
    if itens is None:
        raise ValueError(
            f"A turma não tem agenda completa — {_AGENDA_INCOMPLETA.lower()}"
        )

    # G1/P2: a oferta espelha o professor da turma; sem professor não há como
    # criar a oferta (a definição fica em Cursos da Turma, junto do curso).
    if not turma.professor_id:
        raise ValueError(_PROFESSOR_OBRIGATORIO)

    periodo = turma.periodo_letivo

    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=turma.curso_id,
        principal=False,
        professor_id=turma.professor_id,
        turno=turma.turno,
        # dias_semana/hora_inicio/hora_fim: projeção gravada pelo definir_grade.
        data_inicio=periodo.data_inicio if periodo else turma.data_inicio,
        data_fim=periodo.data_fim if periodo else turma.data_fim,
        centro_custo=turma.centro_custo,
        programa=turma.programa,
        unidade_id=turma.unidade_id,
        ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, itens)
    sincronizar_programa_turma(turma)
    return oferta


def adicionar_oferta(
    turma: Turma,
    *,
    curso_id: int,
    principal: bool = False,
    professor_id=None,
    turno: str | None = None,
    data_inicio=None,
    data_fim=None,
    centro_custo: str | None = None,
    programa: str | None = None,
    agenda: list | None = None,
) -> TurmaCurso:
    """Cria uma oferta incremental na turma, aplicando as regras da Onda 4.

    H4: `agenda` (itens ``(dia_semana, hora_inicio, hora_fim)``) é a grade por
    dia vinda do formulário e é a fonte da agenda (admite grade NÃO uniforme):
    vai para `definir_grade` e para a checagem de concomitância.

    H5a: sem `agenda`, a herança de agenda vem da **grade** de uma oferta ativa
    da turma (se houver); as colunas escalares de `Turma`/`TurmaCurso` não são
    mais parâmetro nem fonte. Sem agenda resultante → `ValueError`.
    """
    curso = _validar_curso(turma, curso_id)
    programa = (programa or "").strip()
    if not programa:
        raise ValueError("Toda oferta precisa ter um programa.")
    # G1/P2: o professor pode vir da herança da turma (primeira oferta de uma
    # turma sem vínculo legado), mas a ausência é recusada pela validação.
    if turma.curso_id is None and not professor_id:
        professor_id = turma.professor_id
    professor_id = _validar_professor(professor_id, turma.unidade_id)
    _validar_principal_obrigatorio(turma, principal)

    # A oferta usa os limites do período letivo por padrão. Datas enviadas
    # explicitamente pelo usuário prevalecem, desde que dentro do período.
    periodo = turma.periodo_letivo
    if periodo:
        data_inicio = data_inicio or periodo.data_inicio
        data_fim = data_fim or periodo.data_fim
        if data_inicio and not periodo.data_inicio <= data_inicio <= periodo.data_fim:
            raise ValueError("A data de início deve estar dentro do período letivo da turma.")
        if data_fim and not periodo.data_inicio <= data_fim <= periodo.data_fim:
            raise ValueError("A data de término deve estar dentro do período letivo da turma.")
    if data_inicio and data_fim and data_inicio > data_fim:
        raise ValueError("A data de início da oferta não pode ser posterior à data de término.")

    avisos_horario = _conflitos_horario_concomitante(
        turma.id,
        data_inicio=data_inicio,
        data_fim=data_fim,
        agenda=agenda,
    )

    # Herança de atributos não-agenda: primeira oferta de uma turma sem vínculo
    # legado parte dos valores da própria turma (compatibilidade com a UI
    # antiga). A agenda só é herdada da GRADE de uma oferta ativa da turma
    # (H3f/H5a) — nunca das colunas escalares.
    agenda_herdada: list[tuple[int, time, time]] | None = None
    if turma.curso_id is None:
        # Professor: resolvido e validado no topo da função (G1/P2).
        turno = turno or turma.turno
        if agenda is None:
            com_grade = [
                (o, grade_da_oferta(o)) for o in ofertas_ativas(turma.id)
            ]
            com_grade = [(o, g) for o, g in com_grade if g]
            if com_grade:
                _ref, g_ref = next(
                    ((o, g) for o, g in com_grade if o.principal), com_grade[0]
                )
                agenda_herdada = [
                    (l.dia_semana, l.hora_inicio, l.hora_fim) for l in g_ref
                ]
        data_inicio = data_inicio or turma.data_inicio
        data_fim = data_fim or turma.data_fim
        centro_custo = centro_custo or turma.centro_custo

    # H2: a grade da oferta é a fonte dos dias/horários e nasce completa —
    # valida ANTES de qualquer escrita (nada é alterado em caso de erro).
    itens = agenda if agenda is not None else agenda_herdada
    if itens is None:
        raise ValueError(_AGENDA_INCOMPLETA)

    # A troca é feita antes do INSERT e dentro da mesma transação. O flush
    # libera o índice único parcial antes de gravar a nova oferta principal.
    if principal:
        for oferta_existente in ofertas_ativas(turma.id):
            if oferta_existente.principal:
                oferta_existente.principal = False
        db.session.flush()

    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        principal=bool(principal),
        professor_id=professor_id,
        turno=turno,
        # H5a: dias/horários vivem só na grade (definir_grade abaixo).
        data_inicio=data_inicio,
        data_fim=data_fim,
        centro_custo=centro_custo,
        programa=programa,
        unidade_id=turma.unidade_id,
        ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()
    definir_grade(oferta, itens)
    _sincronizar_legado(turma, oferta)
    sincronizar_programa_turma(turma)

    db.session.commit()
    oferta.avisos_horario = avisos_horario
    return oferta


def editar_oferta(oferta: TurmaCurso, **dados) -> TurmaCurso:
    """Atualiza os atributos da oferta. O campo `principal` não é editável
    aqui (use `definir_principal`).

    H2/H4: a agenda NÃO é gravada por setattr — `dados["agenda"]` (itens
    ``(dia_semana, hora_inicio, hora_fim)``) substitui a grade inteira via
    ``definir_grade`` (admite grade NÃO uniforme). Sem `agenda` no `dados`, a
    grade não é tocada.

    H5a: as colunas escalares de agenda deixaram de ser aceitas como fonte ou
    default — enviá-las levanta ``ValueError`` (use ``agenda=``); os defaults
    da checagem de conflito saem da **grade atual** (``_agenda_da_oferta``).

    G1/P2: ``professor_id`` presente e vazio é recusado (trocar é permitido;
    esvaziar, não). Quem segura a troca com lançamento gravado é a rota.
    """
    if "professor_id" in dados:
        dados["professor_id"] = _validar_professor(
            dados["professor_id"], oferta.turma.unidade_id
        )
    if "curso_id" in dados and dados["curso_id"] != oferta.curso_id:
        _validar_curso(oferta.turma, dados["curso_id"])
    if "programa" in dados:
        dados["programa"] = (dados["programa"] or "").strip()
        if not dados["programa"]:
            raise ValueError("Toda oferta precisa ter um programa.")

    escalares = {"dias_semana", "hora_inicio", "hora_fim"} & set(dados)
    if escalares:
        raise ValueError(
            "Os dias e horários da oferta são definidos pela grade: envie "
            "`agenda` com os itens (dia, início, fim)."
        )
    # H4: a grade por dia pode chegar pronta (itens ``(dia, ini, fim)``).
    itens = dados.pop("agenda", None)

    # Concomitância: checar ao mexer na vigência ou na agenda. A agenda usada
    # é a nova (se veio) ou a grade **real** da oferta (relação já carregada —
    # sem consulta extra); oferta sem grade não é comparada (H5a).
    if {"data_inicio", "data_fim"} & set(dados) or itens is not None:
        avisos_horario = _conflitos_horario_concomitante(
            oferta.turma_id,
            data_inicio=dados.get("data_inicio", oferta.data_inicio),
            data_fim=dados.get("data_fim", oferta.data_fim),
            exclude_oferta_id=oferta.id,
            agenda=(
                itens
                if itens is not None
                else _agenda_da_oferta(oferta)
            ),
        )
    else:
        avisos_horario = []

    for campo in (
        "curso_id", "professor_id", "turno",
        "data_inicio", "data_fim", "centro_custo", "programa",
    ):
        if campo in dados:
            setattr(oferta, campo, dados[campo])

    if itens is not None:
        # Única escrita dos dias/horários da oferta: substitui a grade.
        definir_grade(oferta, itens)

    sincronizar_programa_turma(oferta.turma)

    # Espelhamento somente na situação-herança criada pela Fase 2
    # (oferta única ativa e turma sem curso legado — nunca ocorre com legado).
    ativas = ofertas_ativas(oferta.turma_id)
    if len(ativas) == 1 and oferta.turma.curso_id is None:
        _sincronizar_legado(oferta.turma, oferta)

    db.session.commit()
    oferta.avisos_horario = avisos_horario
    return oferta


def definir_principal(oferta: TurmaCurso) -> TurmaCurso:
    """Torna a oferta o curso principal da turma em swap atômico.

    Marca a nova e desmarca as demais; como resultado sempre existe exatamente
    um principal entre as ofertas ativas, cumprindo a regra de 2+ ofertas.
    """
    if not oferta.ativo:
        raise ValueError("Só é possível definir principal entre ofertas ativas.")
    for outra in ofertas_ativas(oferta.turma_id):
        if outra.id != oferta.id and outra.principal:
            outra.principal = False
    db.session.flush()
    oferta.principal = True
    sincronizar_programa_turma(oferta.turma)
    db.session.commit()
    return oferta


def _alunos_ativos_em_andamento(oferta: TurmaCurso) -> int:
    """ETAPA M4: quantos alunos têm inscrição ATIVA nesta oferta, em turma
    ativa, cujo período letivo ainda não encerrou.

    Regra do responsável: período com `data_fim >= hoje` está em andamento
    (futuro conta como andamento); turma **sem** `periodo_letivo_id` conta
    como em andamento por prudência. Período encerrado (`data_fim < hoje`)
    e inscrição inativa não bloqueiam.
    """
    hoje = get_local_now().date()
    return (
        db.session.query(func.count(func.distinct(Inscricao.aluno_id)))
        .join(Turma, Turma.id == Inscricao.turma_id)
        .outerjoin(PeriodoLetivo, PeriodoLetivo.id == Turma.periodo_letivo_id)
        .filter(
            Inscricao.turma_curso_id == oferta.id,
            Inscricao.ativo.is_(True),
            Turma.ativo.is_(True),
            or_(
                Turma.periodo_letivo_id.is_(None),
                PeriodoLetivo.data_fim.is_(None),
                PeriodoLetivo.data_fim >= hoje,
            ),
        )
        .scalar()
        or 0
    )


def desativar_oferta(
    oferta: TurmaCurso, *, verificar_alunos_em_andamento: bool = False,
) -> TurmaCurso:
    """Soft delete da oferta (`ativo=False`). O histórico de inscrições é
    preservado — `inscricoes_oferta` não tem cascade.

    `verificar_alunos_em_andamento` (ETAPA M4): guarda usada **apenas** pela
    rota `registros.turma_oferta_desativar` — recusa enquanto houver aluno
    ativo em período não encerrado. Fluxos internos (excluir_turma desativa
    as ofertas por atributo próprio, sem passar aqui) mantêm o comportamento
    antigo ligando o valor padrão False.
    """
    restantes = [o for o in ofertas_ativas(oferta.turma_id) if o.id != oferta.id]
    if len(restantes) >= 2 and not any(o.principal for o in restantes):
        raise ValueError(
            "A turma ficará com mais de um curso ativo sem principal. "
            "Defina o curso principal antes de desativar esta oferta."
        )
    if verificar_alunos_em_andamento:
        bloqueantes = _alunos_ativos_em_andamento(oferta)
        if bloqueantes:
            # A oferta ainda não foi desativada, então 'restantes' ainda a
            # inclui ao procurar o período da turma para a mensagem.
            periodo = oferta.turma.periodo_letivo if oferta.turma else None
            nome_periodo = periodo.nome if periodo else "sem período letivo"
            raise ValueError(
                f"Não é possível remover o curso '{_nome_curso(oferta)}': "
                f"há {bloqueantes} aluno(s) ativo(s) na oferta em período "
                f"letivo ainda em andamento ('{nome_periodo}'). A desativação "
                "só é permitida após o encerramento do período ou quando não "
                "houver alunos ativos."
            )
    oferta.ativo = False
    sincronizar_programa_turma(oferta.turma)
    db.session.commit()
    return oferta


# =============================================================================
# RESOLUÇÃO DA OFERTA DE LANÇAMENTO (Onda 4 — Fase 4, §7)
# =============================================================================

def _dias_set_da_oferta(oferta: TurmaCurso) -> set[int]:
    """Dias (weekday 0-5) em que a oferta tem aula (H3a).

    Fonte única: a grade ``turma_curso_horario`` (lida da relação já carregada
    — sem consulta por data/oferta). Oferta sem grade devolve conjunto vazio e
    registra ``logger.error`` (estado inválido desde o H5a: não há leitura das
    colunas escalares).
    """
    dias = {linha.dia_semana for linha in grade_da_oferta(oferta)}
    if not dias:
        logger.error(
            "Oferta %s sem grade: dias da semana indefinidos (estado inválido "
            "desde o H5a).",
            oferta.id,
        )
    return dias


def _data_bate_dias_semana(oferta: TurmaCurso, data: date) -> bool:
    """True se `data` cai em um dos dias da grade da oferta. Oferta sem dias
    em que a grade não define nada não impõe restrição (True).
    """
    dias = _dias_set_da_oferta(oferta)
    if not dias:
        return True
    return data.weekday() in dias


def _formatar_vigencia(oferta: TurmaCurso) -> str:
    """Texto legível da vigência da oferta ('de ... até ...', aberto em NULL)."""
    ini = f"{oferta.data_inicio:%d/%m/%Y}" if oferta.data_inicio else "início aberto"
    fim = f"{oferta.data_fim:%d/%m/%Y}" if oferta.data_fim else "sem término definido"
    return f"{ini} até {fim}"


def _nome_curso(oferta: TurmaCurso) -> str:
    return oferta.curso.nome if oferta.curso else f"curso #{oferta.curso_id}"


def resolver_oferta_lancamento(
    turma_id: int,
    data: date,
    turma_curso_id: int | None = None,
    tema_id: int | None = None,
    tema_ids: list[int] | tuple[int, ...] | None = None,
) -> TurmaCurso | None:
    """Decide qual oferta (TurmaCurso) deve receber o lançamento de frequência/
    diário de `turma_id` na `data`, validando a escolha informada.

    Regras (§7 — Fase 4):
        - Oferta não informada:
            * turma sem oferta ativa  → None (comportamento legado);
            * exatamente 1 oferta ativa → usa essa oferta;
            * 2+ ofertas ativas → ValueError pedindo a escolha do curso.
        - Oferta informada (turma_curso_id): rejeita (ValueError) quando a
          oferta não existe, está inativa, pertence a outra turma, a data está
          fora da vigência (NULL = aberto), o dia da semana não está nos dias
          da oferta (quando definidos) ou algum tema selecionado pertence a
          outro curso que não o da oferta.

    Não grava nada — apenas resolve e valida. Levanta ValueError com mensagem
    de usuário (convenção deste módulo; a rota converte em flash).
    """
    ids_temas = list(dict.fromkeys(
        tema_ids or ([] if tema_id is None else [tema_id])
    ))
    temas_selecionados = (
        TemaAula.query.filter(TemaAula.id.in_(ids_temas)).all()
        if ids_temas else []
    )
    if len(temas_selecionados) != len(ids_temas):
        raise ValueError("Um ou mais temas selecionados não existem.")

    def validar_temas_curso(oferta: TurmaCurso) -> None:
        if any(t.curso_id not in (None, oferta.curso_id) for t in temas_selecionados):
            raise ValueError(
                f"Um dos temas selecionados pertence a outro curso, não a "
                f"'{_nome_curso(oferta)}'. Escolha temas do curso da oferta."
            )

    if turma_curso_id is not None:
        oferta = db.session.get(TurmaCurso, turma_curso_id)
        if oferta is None:
            raise ValueError("Curso da oferta inválido para esta turma.")
        if oferta.turma_id != turma_id:
            raise ValueError("A oferta selecionada não pertence a esta turma.")
        if not oferta.ativo:
            raise ValueError(
                f"A oferta '{_nome_curso(oferta)}' está desativada e não "
                "aceita novos lançamentos."
            )
        if oferta.data_inicio is not None and data < oferta.data_inicio:
            raise ValueError(
                f"A data {data:%d/%m/%Y} está antes da vigência da oferta "
                f"'{_nome_curso(oferta)}' ({_formatar_vigencia(oferta)})."
            )
        if oferta.data_fim is not None and data > oferta.data_fim:
            raise ValueError(
                f"A data {data:%d/%m/%Y} está depois da vigência da oferta "
                f"'{_nome_curso(oferta)}' ({_formatar_vigencia(oferta)})."
            )
        if not _data_bate_dias_semana(oferta, data):
            # H3f: os dias citados na mensagem saem da grade (via leitura com
            # fallback legado), não da projeção escalar.
            raise ValueError(
                f"A data {data:%d/%m/%Y} não cai em um dia de aula da oferta "
                f"'{_nome_curso(oferta)}' "
                f"({weekdays_para_csv(sorted(_dias_set_da_oferta(oferta)))})."
            )
        validar_temas_curso(oferta)
        return oferta

    ativas = ofertas_ativas(turma_id)
    if not ativas:
        turma = db.session.get(Turma, turma_id)
        if turma and any(
            tema.curso_id not in (None, turma.curso_id)
            for tema in temas_selecionados
        ):
            raise ValueError(
                "Um dos temas selecionados não pertence ao curso desta turma."
            )
        return None  # sem oferta ativa → caminho legado (só turma_id)
    if len(ativas) == 1:
        validar_temas_curso(ativas[0])
        return ativas[0]
    nomes = ", ".join(_nome_curso(o) for o in ativas)
    raise ValueError(
        f"Esta turma tem {len(ativas)} cursos ativos ({nomes}). "
        "Selecione o curso ao qual o lançamento se refere."
    )


# =============================================================================
# PAUTA E AGENDA DA OFERTA (Onda 4 — Fase 4, D2/D3b-1)
# =============================================================================


def _alunos_da_oferta(
    turma_id: int,
    oferta_id: int,
) -> list:
    """Pauta de lançamento de uma oferta (Onda 4 — Fase 4, D2).

    Regra (endurecida na ETAPA B6):
        - Entram os alunos com inscrição ativa na turma cujo
          `Inscricao.turma_curso_id` é a oferta.

    O antigo fallback (`turma_curso_id` NULL quando a turma tem exatamente
    1 oferta ativa, via `incluir_inscricoes_null`) tornou-se código morto:
    desde a migration da Onda 4 (c3d4e5f6a7b8) Inscricao.turma_curso_id é
    NOT NULL, então nenhuma inscrição pode ficar sem oferta — o parâmetro e
    o ramo foram removidos.

    - Sem oferta ativa a rota mantém a pauta por turma (legado), que não
      passa por aqui.

    Move-se para este módulo na D3b-1 para ser reutilizada pelos leitores de
    pendência (dashboards) sem importar `app.registros.core` (blueprint) de
    `app.utils` — o que causaria dependência circular.
    """
    filtros_inscricao = [
        Inscricao.turma_id == turma_id,
        Inscricao.ativo == True,
        Inscricao.turma_curso_id == oferta_id,
    ]
    # EXISTS em vez de JOIN: o aluno aparece uma única vez mesmo quando tem
    # 2+ inscrições ativas elegíveis na oferta.
    return (
        Aluno.query.filter(
            Aluno.ativo == True,
            db.session.query(Inscricao.id)
            .filter(
                Inscricao.aluno_id == Aluno.id,
                *filtros_inscricao,
            )
            .exists(),
        )
        .order_by(Aluno.nome)
        .all()
    )


def datas_aula_oferta(
    oferta: TurmaCurso,
    limite: date | None = None,
    blocked: set | None = None,
) -> list[date]:
    """Datas de aula da OFERTA, respeitando a vigência e os dias da GRADE.

    - Vigência: janela [data_inicio, data_fim]; NULL nos extremos herda da
      turma; sem início OU fim definíveis → sem datas.
    - `limite`: teto **inclusivo** de projeção. `None` vai até a `data_fim`
      efetiva; quando informado, corta em `min(limite, data_fim)` e a data
      igual ao teto ainda é incluída.
    - Dias da semana: `_data_bate_dias_semana`/`_dias_set_da_oferta`, lendo
      apenas a grade. Sem dias na grade → sem datas.
    - `blocked`: conjunto de strings 'YYYY-MM-DD' (feriados / dias sem aula).
    """
    blocked = blocked or set()
    inicio = oferta.data_inicio
    fim = oferta.data_fim
    if inicio is None and oferta.turma is not None:
        inicio = oferta.turma.data_inicio
    if fim is None and oferta.turma is not None:
        fim = oferta.turma.data_fim
    if not inicio or not fim:
        return []

    limite_efetivo = fim if limite is None else min(limite, fim)
    if inicio > limite_efetivo:
        return []

    dias = _dias_set_da_oferta(oferta)
    if not dias:
        return []

    datas: list[date] = []
    atual = inicio
    while atual <= limite_efetivo:
        if atual.weekday() in dias and atual.strftime('%Y-%m-%d') not in blocked:
            datas.append(atual)
        atual += timedelta(days=1)
    return datas


def datas_esperadas_oferta(
    oferta: TurmaCurso,
    hoje: date | None,
    blocked: set | None = None,
) -> list[date]:
    """Datas esperadas da oferta até `hoje`, ou por toda a vigência se ``None``.

    A listagem de pendências passa uma data explícita (D3b-1); a C.H. da oferta
    passa ``None`` para somar ocorrências de toda a vigência.
    """
    return datas_aula_oferta(oferta, limite=hoje, blocked=blocked)

# =============================================================================
# REATIVAÇÃO DE TURMA (L4 / L4.1)
# =============================================================================

# Motivo gravado em `Inscricao.motivo_desativacao` pela exclusão lógica da
# turma (`excluir_turma`); espelha `MOTIVO_INSCRICAO_TURMA_DESATIVADA` da rota.
MOTIVO_TURMA_DESATIVADA = "TURMA_DESATIVADA"

#: `acao` do `LogAcao`-marcador gravado por `excluir_turma` no caminho lógico.
#: É o ÚNICO sinal confiável de quais ofertas foram desativadas JUNTO com a
#: turma (L4.1): o `updated_at` não serve — o listener de auditoria grava
#: `updated_at = now()` em toda oferta tocada pela exclusão, inclusive as que
#: já estavam inativas (medido em PostgreSQL e SQLite).
ACAO_EXCLUSAO_LOGICA_TURMA = "Excluir turma (lógica)"

_PADRAO_MARCADOR = re.compile(
    r"\Aturma_id=(?P<turma>\d+)"
    r" ofertas=\[(?P<ofertas>[\d,\s]*)\]"
    r" inscricoes=\[(?P<inscricoes>[\d,\s]*)\]\Z"
)


def _csv_ids(ids) -> str:
    return ",".join(str(int(i)) for i in (ids or []))


def _parse_ids(texto: str) -> list[int]:
    return [int(p) for p in texto.replace(" ", "").split(",") if p]


def formatar_marcador_exclusao(turma_id, oferta_ids, inscricao_ids) -> str:
    """Texto do `detalhes` do LogAcao-marcador (parseável por linha)."""
    return (
        f"turma_id={int(turma_id)} ofertas=[{_csv_ids(oferta_ids)}] "
        f"inscricoes=[{_csv_ids(inscricao_ids)}]"
    )


def parsear_marcador_exclusao(detalhes) -> dict | None:
    """`{turma_id, ofertas, inscricoes}` ou `None` se o texto não é o marcador."""
    if not detalhes:
        return None
    achado = _PADRAO_MARCADOR.match(str(detalhes).strip())
    if not achado:
        return None
    return {
        "turma_id": int(achado.group("turma")),
        "ofertas": _parse_ids(achado.group("ofertas")),
        "inscricoes": _parse_ids(achado.group("inscricoes")),
    }


def gravar_marcador_exclusao(
    turma_id, oferta_ids, inscricao_ids, *,
    usuario_id=None, usuario_nome=None, ip=None, unidade_id=None,
) -> None:
    """Acrescenta o LogAcao-marcador da exclusão lógica (sem commit).

    Chamado por `excluir_turma` na MESMA transação que desativa turma, ofertas
    e inscrições — é isso que permite à reativação saber quais ofertas estavam
    ativas. `oferta_ids` é a lista das que estavam **ativas** (as demais já
    estavam fora da turma antes da exclusão e não podem voltar).
    """
    from app.models import LogAcao

    db.session.add(LogAcao(
        usuario_id=usuario_id,
        usuario_nome=usuario_nome,
        acao=ACAO_EXCLUSAO_LOGICA_TURMA,
        detalhes=formatar_marcador_exclusao(turma_id, oferta_ids, inscricao_ids),
        ip=ip,
        unidade_id=unidade_id,
    ))


def _consulta_marcadores():
    """Linhas de LogAcao-marcador (id, detalhes) da mais antiga para a mais nova."""
    from app.models import LogAcao

    return (
        db.session.query(LogAcao.id, LogAcao.detalhes)
        .filter(LogAcao.acao == ACAO_EXCLUSAO_LOGICA_TURMA)
        .order_by(LogAcao.id)
        .all()
    )


def marcador_exclusao_turma(turma_id: int) -> dict | None:
    """Último marcador de exclusão lógica da turma (ou `None` se não há).

    `None` é o caso da turma excluída ANTES desta versão: sem marcador não há
    pré-seleção possível e a reativação exige escolha explícita.
    """
    prefixo = f"turma_id={int(turma_id)} ofertas="
    from app.models import LogAcao

    linhas = (
        db.session.query(LogAcao.id, LogAcao.detalhes)
        .filter(
            LogAcao.acao == ACAO_EXCLUSAO_LOGICA_TURMA,
            LogAcao.detalhes.startswith(prefixo, autoescape=True),
        )
        .order_by(LogAcao.id.desc())
        .all()
    )
    for _id, detalhes in linhas:
        marcador = parsear_marcador_exclusao(detalhes)
        if marcador and marcador["turma_id"] == int(turma_id):
            return marcador
    return None


def marcadores_exclusao_em_lote() -> dict[int, dict]:
    """`{turma_id: marcador}` de UMA vez (última ocorrência por turma)."""
    marcadores: dict[int, dict] = {}
    for _id, detalhes in _consulta_marcadores():
        marcador = parsear_marcador_exclusao(detalhes)
        if marcador:
            marcadores[marcador["turma_id"]] = marcador
    return marcadores


def _periodo_encerrado(turma: Turma, hoje: date) -> bool:
    periodo = turma.periodo_letivo
    return bool(periodo and periodo.data_fim and periodo.data_fim < hoje)


def _hoje_local() -> date:
    try:
        return get_local_now().date()
    except Exception:  # relógio/fuso indisponível: cai no do sistema
        return date.today()


def _selecionar_ofertas_reativacao(
    inativas: list[TurmaCurso], marcador: dict | None, oferta_ids,
) -> tuple[list[TurmaCurso], str | None]:
    """`(selecionadas, motivo_recusa)` — regra única da pré-visualização e da
    reativação (L4.1).

    - `oferta_ids` informado (escolha explícita do operador na lixeira): só
      podem ser ofertas inativas desta turma; qualquer outra coisa é recusada.
    - `oferta_ids` ausente: usa a pré-seleção do marcador da exclusão lógica.
      Sem marcador (turma excluída antes desta versão) nada é pré-marcado.
    """
    if oferta_ids is not None:
        pedidos = [int(i) for i in oferta_ids]
        por_id = {o.id: o for o in inativas}
        invalidos = [i for i in pedidos if i not in por_id]
        if invalidos:
            return [], (
                "A seleção contém curso(s) que não são ofertas inativas desta "
                f"turma (ids {', '.join(str(i) for i in invalidos)})."
            )
        return [por_id[i] for i in dict.fromkeys(pedidos)], None

    if marcador is None:
        return [], None
    do_marcador = set(marcador["ofertas"])
    return [o for o in inativas if o.id in do_marcador], None


def _classificar_inscricoes(
    candidatas, ids_reativar, alunos_ativos, pares_ativos,
) -> tuple[list, list]:
    """`(reativaveis, conflitos)` das inscrições marcadas TURMA_DESATIVADA.

    Só voltam as inscrições das ofertas que serão reativadas; aluno inativo ou
    inscrição ativa do mesmo aluno na mesma oferta (outra linha) é conflito e
    permanece inativa. `pares_ativos` é `{(aluno_id, turma_curso_id)}` das
    inscrições ativas da turma.
    """
    reativaveis, conflitos = [], []
    for insc in candidatas:
        if insc.turma_curso_id not in ids_reativar:
            continue
        if insc.aluno_id not in alunos_ativos:
            conflitos.append(insc.id)
            continue
        if (insc.aluno_id, insc.turma_curso_id) in pares_ativos:
            conflitos.append(insc.id)
            continue
        reativaveis.append(insc)
    return reativaveis, conflitos


def _contexto_reativacao_em_lote(turmas) -> dict[int, dict]:
    """Carga em lote das ofertas/inscrições/marcadores de N turmas.

    Número de SELECTs CONSTANTE (ofertas, inscrições candidatas, alunos,
    inscrições ativas, marcadores), independentemente de quantas turmas a
    listagem mostra — sem N+1 na lixeira.
    """
    turma_ids = [t.id for t in turmas]
    if not turma_ids:
        return {}

    ofertas_por_turma: dict[int, list[TurmaCurso]] = {tid: [] for tid in turma_ids}
    for oferta in (
        TurmaCurso.query
        .options(joinedload(TurmaCurso.curso))
        .filter(TurmaCurso.turma_id.in_(turma_ids))
        .order_by(TurmaCurso.id)
        .all()
    ):
        ofertas_por_turma.setdefault(oferta.turma_id, []).append(oferta)

    candidatas_por_turma: dict[int, list[Inscricao]] = {tid: [] for tid in turma_ids}
    for insc in (
        Inscricao.query
        .filter(
            Inscricao.turma_id.in_(turma_ids),
            Inscricao.motivo_desativacao == MOTIVO_TURMA_DESATIVADA,
        )
        .all()
    ):
        candidatas_por_turma.setdefault(insc.turma_id, []).append(insc)

    aluno_ids = {i.aluno_id for lista in candidatas_por_turma.values() for i in lista}
    alunos_ativos = {
        aid for (aid,) in
        db.session.query(Aluno.id).filter(Aluno.id.in_(aluno_ids), Aluno.ativo.is_(True))
    } if aluno_ids else set()

    pares_ativos = {
        (aid, oid) for aid, oid in
        db.session.query(Inscricao.aluno_id, Inscricao.turma_curso_id).filter(
            Inscricao.turma_id.in_(turma_ids), Inscricao.ativo.is_(True)
        )
    }

    marcadores = marcadores_exclusao_em_lote()
    contexto = {}
    por_turma = {t.id: t for t in turmas}
    for tid in turma_ids:
        contexto[tid] = {
            "turma": por_turma[tid],
            "ofertas": ofertas_por_turma.get(tid, []),
            "candidatas": candidatas_por_turma.get(tid, []),
            "alunos_ativos": alunos_ativos,
            "pares_ativos": pares_ativos,
            "marcador": marcadores.get(tid),
        }
    return contexto


def _avaliar_reativacao(dados: dict, *, hoje: date, oferta_ids=None) -> dict:
    """Núcleo comum: o que a lixeira mostra e o que `reativar_turma` faz."""
    turma = dados["turma"]
    ofertas = dados["ofertas"]
    inativas = [o for o in ofertas if not o.ativo]
    ativas = [o for o in ofertas if o.ativo]
    marcador = dados["marcador"]

    selecionadas, recusa = _selecionar_ofertas_reativacao(inativas, marcador, oferta_ids)
    ids_reativar = {o.id for o in selecionadas}
    reativaveis, conflitos = _classificar_inscricoes(
        dados["candidatas"], ids_reativar,
        dados["alunos_ativos"], dados["pares_ativos"],
    )

    lista_final = ativas + list(selecionadas)
    principals = [o for o in lista_final if o.principal]
    viola_principal = len(lista_final) >= 2 and len(principals) != 1

    periodo_encerrado = _periodo_encerrado(turma, hoje)
    return {
        "turma": turma,
        "marcador": marcador,
        "inativas": inativas,
        "selecionadas": selecionadas,
        "ids_reativar": ids_reativar,
        "mantidas_inativas": [o for o in inativas if o.id not in ids_reativar],
        "reativaveis": reativaveis,
        "conflitos": conflitos,
        "viola_principal": viola_principal,
        "recusa_selecao": recusa,
        "tem_marcador": marcador is not None,
        "periodo_encerrado": periodo_encerrado,
    }


def _montar_preview(avaliacao: dict) -> dict:
    """View da lixeira: uma linha por oferta inativa, com a origem dela."""
    do_marcador = set(avaliacao["marcador"]["ofertas"]) if avaliacao["tem_marcador"] else set()
    return {
        "ofertas": [
            {
                "id": o.id,
                "curso": _nome_curso(o),
                "reativar": o.id in avaliacao["ids_reativar"],
                "na_exclusao": o.id in do_marcador,
                "vigencia": _formatar_vigencia(o),
            }
            for o in avaliacao["inativas"]
        ],
        "ofertas_reativar": len(avaliacao["selecionadas"]),
        "ofertas_inativas": len(avaliacao["inativas"]),
        "inscricoes_reativar": len(avaliacao["reativaveis"]),
        "conflitos": len(avaliacao["conflitos"]),
        "periodo_encerrado": avaliacao["periodo_encerrado"],
        "tem_marcador": avaliacao["tem_marcador"],
        "viola_principal": avaliacao["viola_principal"],
    }


def preview_reativacao(turma: Turma) -> dict:
    """Resumo da reativação de UMA turma (MESMA regra de `reativar_turma`).

    A listagem da lixeira usa `previews_reativacao_em_lote` (carga única); esta
    entrada avulsa serve a chamadas isoladas.
    """
    dados = _contexto_reativacao_em_lote([turma])[turma.id]
    return _montar_preview(_avaliar_reativacao(dados, hoje=_hoje_local()))


def previews_reativacao_em_lote(turmas) -> dict[int, dict]:
    """Pré-visualização de várias turmas com carga única (sem N+1 na lixeira)."""
    contexto = _contexto_reativacao_em_lote(turmas)
    hoje = _hoje_local()
    previews = {}
    for turma in turmas:
        dados = contexto.get(turma.id)
        if dados is None:
            continue
        previews[turma.id] = _montar_preview(_avaliar_reativacao(dados, hoje=hoje))
    return previews


def reativar_turma(
    turma: Turma, *,
    confirmar_periodo_encerrado: bool = False,
    oferta_ids: list[int] | tuple[int, ...] | None = None,
) -> dict:
    """Reativa uma turma logicamente excluída (sem commit) — L4/L4.1.

    Só voltam as ofertas **desativadas junto com a turma**: a pré-seleção vem do
    LogAcao-marcador gravado por `excluir_turma` e o operador pode ajustar a
    lista (`oferta_ids` da lixeira). Oferta desativada ANTES (removida do curso
    pela rota `turma_oferta_desativar`) permanece inativa — ressuscitá-la
    violaria a intenção do responsável e a regra de curso principal.

    Toda validação roda antes de qualquer mutação: violação recusa a operação
    inteira, sem alteração parcial (quem chama faz `rollback` no `ValueError`).

    L4.2: ao voltar ao menos uma oferta, `Turma.programa` é reprojetado pelo
    programa da oferta principal ativa (`sincronizar_programa_turma`) na mesma
    transação — a reativação pode mudar a referência (volta só uma oferta que
    não era a principal). Turma sem ofertas reativadas não tem projeção a
    recalcular e mantém o programa atual.
    """
    contexto = _contexto_reativacao_em_lote([turma])
    hoje = _hoje_local()
    avaliacao = _avaliar_reativacao(contexto[turma.id], hoje=hoje, oferta_ids=oferta_ids)

    if avaliacao["periodo_encerrado"] and not confirmar_periodo_encerrado:
        raise ValueError(
            "O período letivo da turma já encerrou. Confirme a reativação."
        )
    if avaliacao["recusa_selecao"]:
        raise ValueError(avaliacao["recusa_selecao"])
    if not avaliacao["tem_marcador"] and oferta_ids is None and avaliacao["inativas"]:
        raise ValueError(
            "Não há registro de quais cursos foram desativados junto com a turma "
            "(exclusão anterior a esta versão). Escolha explicitamente os cursos "
            "a reativar."
        )
    if avaliacao["inativas"] and not avaliacao["selecionadas"]:
        raise ValueError(
            "Selecione ao menos um curso para reativar junto com a turma."
        )
    if avaliacao["viola_principal"]:
        raise ValueError(
            "Reativação violaria a regra de curso principal (2+ ofertas ativas "
            "exigem exatamente 1 principal). Ajuste antes de reativar."
        )

    turma.ativo = True
    for oferta in avaliacao["selecionadas"]:
        oferta.ativo = True
    for insc in avaliacao["reativaveis"]:
        insc.ativo = True
        insc.data_desativacao = None
        insc.motivo_desativacao = None

    # L4.2: `Turma.programa` é projeção da oferta principal ativa (§8.10) e a
    # volta muda a referência (ex.: volta só uma oferta não principal). Só
    # reprojeta quando alguma oferta volta: turma sem ofertas (estado legado)
    # não tem referência e não pode perder o programa que ainda alimenta
    # listagem e filtros. Sem commit — a transação é a do chamador.
    if avaliacao["selecionadas"]:
        sincronizar_programa_turma(turma)

    return {
        "ofertas_reativadas": len(avaliacao["selecionadas"]),
        "ofertas_reativadas_ids": [o.id for o in avaliacao["selecionadas"]],
        "cursos_reativados": [_nome_curso(o) for o in avaliacao["selecionadas"]],
        "ofertas_inativas_restantes": [
            {"id": o.id, "curso": _nome_curso(o)} for o in avaliacao["mantidas_inativas"]
        ],
        "inscricoes_reativadas": len(avaliacao["reativaveis"]),
        "conflitos": list(avaliacao["conflitos"]),
        "periodo_encerrado": avaliacao["periodo_encerrado"],
    }

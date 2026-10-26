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
    - Concomitância: horários sobrepostos entre ofertas ativas da mesma turma
      são permitidos; o usuário recebe um aviso informativo.
    - Compatibilidade legada (§14): o espelhamento para as colunas de `Turma`
      só ocorre em turma com oferta única ativa e que nunca teve curso legado
      (situação criada por esta feature). Turmas do backfill e turmas com
      2+ ofertas mantêm as colunas legadas congeladas — sem dual-write.

Todas as funções fazem `db.session.commit()` internamente e levantam
`ValueError` com mensagem de usuário amigável em caso de violação de regra;
quem chama (rotas) converter em `flash`.
"""
from __future__ import annotations

import logging
from datetime import date, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import joinedload

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
from app.services.turma_curso_horario import (
    definir_grade,
    grade_a_partir_do_legado,
    grade_da_oferta,
)
from app.utils.dias_semana import csv_para_weekdays, csv_tokens_desconhecidos

logger = logging.getLogger(__name__)

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
        query = query.filter(
            or_(
                TurmaCurso.professor_id == professor_id,
                Turma.professor_id == professor_id,
            )
        )

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


def _parse_dias(dias_semana: str | None) -> set[str]:
    """Converte CSV de dias ('Segunda, Quarta') em set normalizado (lowerstrip).

    PONTE (H3a): desde a migração dos leitores de agenda, só é usado por
    ``_conflitos_horario_concomitante`` (leitor de concomitância, ainda por
    dia — grupo concomitância do H3). Será removido quando a concomitância
    passar a comparar a grade por dia.
    """
    if not dias_semana:
        return set()
    return {d.strip().lower() for d in dias_semana.split(",") if d.strip()}


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


def _conflitos_horario_concomitante(
    turma_id: int,
    *,
    dias_semana: str | None,
    hora_inicio: time | None,
    hora_fim: time | None,
    data_inicio: date | None,
    data_fim: date | None,
    exclude_oferta_id: int | None = None,
) -> list[str]:
    """Lista conflitos com outras ofertas ativas da mesma turma.

    A checagem é pulada quando faltam dados mínimos (sem dias OU sem horários).
    Concomitância é permitida; as mensagens servem apenas como alerta.
    """
    # Dados insuficientes — não há como determinar conflito
    dias_novos = _parse_dias(dias_semana)
    if not dias_novos or hora_inicio is None or hora_fim is None:
        return []

    outras = (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )
    conflitos = []
    for outra in outras:
        if exclude_oferta_id and outra.id == exclude_oferta_id:
            continue
        # Precisa ter dados de horário para comparar
        dias_outra = _parse_dias(outra.dias_semana)
        if not dias_outra or outra.hora_inicio is None or outra.hora_fim is None:
            continue
        # Condição 1: dias em comum
        if not dias_novos & dias_outra:
            continue
        # Condição 2: sobreposição estrita de horário
        if not _sobreposicao_horario(hora_inicio, hora_fim, outra.hora_inicio, outra.hora_fim):
            continue
        # Condição 3: vigências se interceptam
        if not _sobreposicao_vigencia(data_inicio, data_fim, outra.data_inicio, outra.data_fim):
            continue
        # Conflito detectado: alerta sem bloquear a operação.
        curso_nome = outra.curso.nome if outra.curso else f"curso #{outra.curso_id}"
        conflitos.append(
            f"Horário concomitante com '{curso_nome}' "
            f"({outra.dias_semana}, {outra.hora_inicio:%H:%M}–{outra.hora_fim:%H:%M}). "
            "A oferta foi salva."
        )
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
    if not professor_id:
        return None
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
    turma.curso_id = oferta.curso_id
    turma.professor_id = oferta.professor_id
    turma.turno = oferta.turno
    turma.dias_semana = oferta.dias_semana
    turma.hora_inicio = oferta.hora_inicio
    turma.hora_fim = oferta.hora_fim
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


def criar_oferta_inicial_da_turma(turma: Turma) -> TurmaCurso | None:
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

    Desde o H2 a agenda vem da TURMA só quando está COMPLETA (dias + início +
    fim): a grade da oferta é criada pelo serviço (`definir_grade`) e as
    colunas escalares da oferta passam a ser projeção. Herança incompleta é
    recusada com ValueError (nunca se cria oferta com grade parcial).
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

    itens = grade_a_partir_do_legado(
        turma.dias_semana, turma.hora_inicio, turma.hora_fim
    )
    if itens is None:
        raise ValueError(
            f"A turma não tem agenda completa — {_AGENDA_INCOMPLETA.lower()}"
        )

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
    dias_semana: str | None = None,
    hora_inicio=None,
    hora_fim=None,
    data_inicio=None,
    data_fim=None,
    centro_custo: str | None = None,
    programa: str | None = None,
) -> TurmaCurso:
    """Cria uma oferta incremental na turma, aplicando as regras da Onda 4."""
    curso = _validar_curso(turma, curso_id)
    programa = (programa or "").strip()
    if not programa:
        raise ValueError("Toda oferta precisa ter um programa.")
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
        dias_semana=dias_semana,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    # Herança de atributos: primeira oferta de uma turma sem vínculo legado
    # parte dos valores da própria turma (compatibilidade com a UI antiga).
    # Usa `or` para herdar os demais atributos de turma quando aplicável.
    if turma.curso_id is None:
        professor_id = professor_id or turma.professor_id
        turno = turno or turma.turno
        dias_semana = dias_semana or turma.dias_semana
        hora_inicio = hora_inicio or turma.hora_inicio
        hora_fim = hora_fim or turma.hora_fim
        data_inicio = data_inicio or turma.data_inicio
        data_fim = data_fim or turma.data_fim
        centro_custo = centro_custo or turma.centro_custo

    # H2: a grade da oferta é a fonte dos dias/horários e nasce completa —
    # valida ANTES de qualquer escrita (nada é alterado em caso de erro).
    itens = grade_a_partir_do_legado(dias_semana, hora_inicio, hora_fim)
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
        # dias_semana/hora_inicio/hora_fim: projeção gravada pelo definir_grade.
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

    H2: `dias_semana`/`hora_inicio`/`hora_fim` NÃO são mais gravados por
    setattr direto — quando algum deles chega, a grade inteira da oferta é
    substituida por ``definir_grade`` (grade uniforme a partir do CSV + par
    do formulário; UI de grade variável é H4) e as colunas escalares passam a
    ser projeção. Herança/legado incompleto é recusado (nunca grade parcial).
    Sem campos de agenda no `dados`, a grade não é tocada.
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

    agenda = {"dias_semana", "hora_inicio", "hora_fim"} & set(dados)
    itens: list | None = None
    if agenda:
        efetivo = {
            "dias": dados.get("dias_semana", oferta.dias_semana),
            "ini": dados.get("hora_inicio", oferta.hora_inicio),
            "fim": dados.get("hora_fim", oferta.hora_fim),
        }
        itens = grade_a_partir_do_legado(
            efetivo["dias"], efetivo["ini"], efetivo["fim"]
        )
        if itens is None:
            raise ValueError(_AGENDA_INCOMPLETA)

    # Concomitância: checar apenas se pelo menos um dos campos de horário/dias mudou
    campos_horario = {"dias_semana", "hora_inicio", "hora_fim", "data_inicio", "data_fim"}
    if campos_horario & set(dados):
        avisos_horario = _conflitos_horario_concomitante(
            oferta.turma_id,
            dias_semana=dados.get("dias_semana", oferta.dias_semana),
            hora_inicio=dados.get("hora_inicio", oferta.hora_inicio),
            hora_fim=dados.get("hora_fim", oferta.hora_fim),
            data_inicio=dados.get("data_inicio", oferta.data_inicio),
            data_fim=dados.get("data_fim", oferta.data_fim),
            exclude_oferta_id=oferta.id,
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
        # Única escrita dos dias/horários da oferta: substitui a grade e
        # reprojeta as colunas escalares (sincronizar_projecao_horario).
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

    Fonte canônica: a grade ``turma_curso_horario`` (lida da relação já
    carregada — sem consulta por data/oferta). Sem grade (linha 100% legado,
    anterior ao backfill), cai no CSV projetado via conversor único — a
    projeção segue correta até o H5, então o fallback preserva o resultado.
    """
    dias = {linha.dia_semana for linha in grade_da_oferta(oferta)}
    if dias:
        return dias
    csv = _dias_efetivos_da_oferta(oferta)
    desconhecidos = csv_tokens_desconhecidos(csv)
    if desconhecidos:
        logger.warning(
            "Oferta %s sem grade: CSV de dias legado tem tokens desconhecidos %s "
            "(descartados na leitura de agenda).", oferta.id, desconhecidos,
        )
    return set(csv_para_weekdays(csv))


def _data_bate_dias_semana(oferta: TurmaCurso, data: date) -> bool:
    """True se `data` cai em um dos dias da grade da oferta. Oferta sem dias
    definidos não impõe restrição (True). H3a: lê a grade (weekday 0-5), não
    mais o CSV via ``_parse_dias``.
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
            raise ValueError(
                f"A data {data:%d/%m/%Y} não cai em um dia de aula da oferta "
                f"'{_nome_curso(oferta)}' ({oferta.dias_semana})."
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


def _dias_efetivos_da_oferta(oferta: TurmaCurso) -> str | None:
    """Dias da semana que regem a agenda da oferta; herda os da turma quando a
    oferta não define os próprios (compatibilidade com o backfill legado)."""
    if oferta.dias_semana:
        return oferta.dias_semana
    if oferta.turma is not None:
        return oferta.turma.dias_semana
    return None


def datas_aula_oferta(
    oferta: TurmaCurso,
    limite: date | None = None,
    blocked: set | None = None,
) -> list[date]:
    """Datas de aula da OFERTA, respeitando a vigência e os dias da semana
    próprios da oferta (herdados da turma quando ausentes).

    - Vigência: janela [data_inicio, data_fim]; NULL nos extremos herda da
      turma; sem início OU fim definíveis → sem datas.
    - `limite`: teto exclusivo de projeção. `None` vai até a `data_fim`
      efetiva; quando informado, corta em `min(limite, data_fim)`.
    - Dias da semana: `_data_bate_dias_semana` com os dias efetivos da
      oferta. Sem dias em nenhum dos dois → sem datas.
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
    hoje: date,
    blocked: set | None = None,
) -> list[date]:
    """Datas de aula da OFERTA até `hoje` (inclusive), cortadas na `data_fim`
    efetiva — base da contagem de pendência por oferta (D3b-1).

    Delega para `datas_aula_oferta` com `limite=hoje` (a helper corta em
    `min(hoje, data_fim)`, preservando exatamente o comportamento anterior).
    """
    return datas_aula_oferta(oferta, limite=hoje, blocked=blocked)

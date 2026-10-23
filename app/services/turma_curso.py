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
    - Concomitância (§5): é proibido horário sobreposto entre cursos da
      mesma turma em dias comuns, dentro de vigências que se interceptam.
      Adjacência (fim de um = início do outro) é permitida.
    - Compatibilidade legada (§14): o espelhamento para as colunas de `Turma`
      só ocorre em turma com oferta única ativa e que nunca teve curso legado
      (situação criada por esta feature). Turmas do backfill e turmas com
      2+ ofertas mantêm as colunas legadas congeladas — sem dual-write.

Todas as funções fazem `db.session.commit()` internamente e levantam
`ValueError` com mensagem de usuário amigável em caso de violação de regra;
quem chama (rotas) converter em `flash`.
"""
from __future__ import annotations

from datetime import date, time

from app.database import db
from app.models import Curso, TemaAula, Turma, TurmaCurso, User


def ofertas_ativas(turma_id: int):
    """Ofertas ativas da turma em ordem estável (legado primeiro)."""
    return (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )


def _parse_dias(dias_semana: str | None) -> set[str]:
    """Converte CSV de dias ('Segunda, Quarta') em set normalizado (lowerstrip)."""
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


def _validar_horario_concomitante(
    turma_id: int,
    *,
    dias_semana: str | None,
    hora_inicio: time | None,
    hora_fim: time | None,
    data_inicio: date | None,
    data_fim: date | None,
    exclude_oferta_id: int | None = None,
) -> None:
    """Levanta ValueError se a nova/edição da oferta conflitar com outra oferta
    ativa da mesma turma (§5 — concomitância proibida; adjacência permitida).

    A checagem é pulada quando faltam dados mínimos (sem dias OU sem horários).
    """
    # Dados insuficientes — não há como determinar conflito
    dias_novos = _parse_dias(dias_semana)
    if not dias_novos or hora_inicio is None or hora_fim is None:
        return

    outras = (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )
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
        # Conflito detectado
        curso_nome = outra.curso.nome if outra.curso else f"curso #{outra.curso_id}"
        raise ValueError(
            f"Horário concomitante com '{curso_nome}' "
            f"({outra.dias_semana}, {outra.hora_inicio:%H:%M}–{outra.hora_fim:%H:%M}). "
            "Cursos da mesma turma não podem ter aulas no mesmo dia e horário "
            "(adjacência é permitida)."
        )


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
    caso contrário (legado sem principal do backfill), a marca é obrigatória.
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
    turma.curso_id = oferta.curso_id


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
) -> TurmaCurso:
    """Cria uma oferta incremental na turma, aplicando as regras da Onda 4."""
    curso = _validar_curso(turma, curso_id)
    professor_id = _validar_professor(professor_id, turma.unidade_id)
    _validar_principal_obrigatorio(turma, principal)
    _validar_horario_concomitante(
        turma.id,
        dias_semana=dias_semana,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )

    # Herança de atributos: primeira oferta de uma turma sem vínculo legado
    # parte dos valores da própria turma (compatibilidade com a UI antiga).
    if turma.curso_id is None:
        professor_id = professor_id or turma.professor_id
        turno = turno or turma.turno
        dias_semana = dias_semana or turma.dias_semana
        hora_inicio = hora_inicio or turma.hora_inicio
        hora_fim = hora_fim or turma.hora_fim
        data_inicio = data_inicio or turma.data_inicio
        data_fim = data_fim or turma.data_fim
        centro_custo = centro_custo or turma.centro_custo

    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=curso.id,
        principal=bool(principal),
        professor_id=professor_id,
        turno=turno,
        dias_semana=dias_semana,
        hora_inicio=hora_inicio,
        hora_fim=hora_fim,
        data_inicio=data_inicio,
        data_fim=data_fim,
        centro_custo=centro_custo,
        unidade_id=turma.unidade_id,
        ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()
    _sincronizar_legado(turma, oferta)
    db.session.commit()
    return oferta


def editar_oferta(oferta: TurmaCurso, **dados) -> TurmaCurso:
    """Atualiza os atributos da oferta. O campo `principal` não é editável
    aqui (use `definir_principal`); alterações não retroativas: inscrições e
    lançamentos existentes continuam como estão.
    """
    if "professor_id" in dados:
        dados["professor_id"] = _validar_professor(
            dados["professor_id"], oferta.turma.unidade_id
        )
    if "curso_id" in dados and dados["curso_id"] != oferta.curso_id:
        _validar_curso(oferta.turma, dados["curso_id"])

    # Concomitância: checar apenas se pelo menos um dos campos de horário/dias mudou
    campos_horario = {"dias_semana", "hora_inicio", "hora_fim", "data_inicio", "data_fim"}
    if campos_horario & set(dados):
        _validar_horario_concomitante(
            oferta.turma_id,
            dias_semana=dados.get("dias_semana", oferta.dias_semana),
            hora_inicio=dados.get("hora_inicio", oferta.hora_inicio),
            hora_fim=dados.get("hora_fim", oferta.hora_fim),
            data_inicio=dados.get("data_inicio", oferta.data_inicio),
            data_fim=dados.get("data_fim", oferta.data_fim),
            exclude_oferta_id=oferta.id,
        )

    for campo in (
        "curso_id", "professor_id", "turno", "dias_semana",
        "hora_inicio", "hora_fim", "data_inicio", "data_fim", "centro_custo",
    ):
        if campo in dados:
            setattr(oferta, campo, dados[campo])

    # Espelhamento somente na situação-herança criada pela Fase 2
    # (oferta única ativa e turma sem curso legado — nunca ocorre com legado).
    ativas = ofertas_ativas(oferta.turma_id)
    if len(ativas) == 1 and oferta.turma.curso_id is None:
        _sincronizar_legado(oferta.turma, oferta)

    db.session.commit()
    return oferta


def definir_principal(oferta: TurmaCurso) -> TurmaCurso:
    """Torna a oferta o curso principal da turma em swap atômico.

    Marca a nova e desmarca as demais; como resultado sempre existe exatamente
    um principal entre as ofertas ativas, cumprindo a regra de 2+ ofertas.
    """
    if not oferta.ativo:
        raise ValueError("Só é possível definir principal entre ofertas ativas.")
    for outra in ofertas_ativas(oferta.turma_id):
        outra.principal = outra.id == oferta.id
    if not oferta.principal:
        oferta.principal = True
    db.session.commit()
    return oferta


def desativar_oferta(oferta: TurmaCurso) -> TurmaCurso:
    """Soft delete da oferta (`ativo=False`). O histórico de inscrições é
    preservado — `inscricoes_oferta` não tem cascade.
    """
    restantes = [o for o in ofertas_ativas(oferta.turma_id) if o.id != oferta.id]
    if len(restantes) >= 2 and not any(o.principal for o in restantes):
        raise ValueError(
            "A turma ficará com mais de um curso ativo sem principal. "
            "Defina o curso principal antes de desativar esta oferta."
        )
    oferta.ativo = False
    db.session.commit()
    return oferta


# =============================================================================
# RESOLUÇÃO DA OFERTA DE LANÇAMENTO (Onda 4 — Fase 4, §7)
# =============================================================================

_NOMES_DIA_SEMANA = (
    'segunda', 'terça', 'quarta', 'quinta', 'sexta', 'sábado', 'domingo',
)


def _data_bate_dias_semana(dias_semana: str | None, data: date) -> bool:
    """True se `data` cai em um dos dias definidos para a oferta. Oferta sem
    `dias_semana` definido não impõe restrição (True). Aceita a variante
    'Segunda-feira' além de 'Segunda'.
    """
    dias = _parse_dias(dias_semana)
    if not dias:
        return True
    nome = _NOMES_DIA_SEMANA[data.weekday()]
    return nome in dias or f"{nome}-feira" in dias


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
          da oferta (quando definidos) ou o `tema_id` informado pertence a
          outro curso que não o da oferta.

    Não grava nada — apenas resolve e valida. Levanta ValueError com mensagem
    de usuário (convenção deste módulo; a rota converte em flash).
    """
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
        if not _data_bate_dias_semana(oferta.dias_semana, data):
            raise ValueError(
                f"A data {data:%d/%m/%Y} não cai em um dia de aula da oferta "
                f"'{_nome_curso(oferta)}' ({oferta.dias_semana})."
            )
        if tema_id is not None:
            tema = db.session.get(TemaAula, tema_id)
            if tema is not None and tema.curso_id not in (None, oferta.curso_id):
                raise ValueError(
                    f"O tema selecionado pertence a outro curso, não a "
                    f"'{_nome_curso(oferta)}'. Escolha um tema do curso da oferta."
                )
        return oferta

    ativas = ofertas_ativas(turma_id)
    if not ativas:
        return None  # sem oferta ativa → caminho legado (só turma_id)
    if len(ativas) == 1:
        return ativas[0]
    nomes = ", ".join(_nome_curso(o) for o in ativas)
    raise ValueError(
        f"Esta turma tem {len(ativas)} cursos ativos ({nomes}). "
        "Selecione o curso ao qual o lançamento se refere."
    )

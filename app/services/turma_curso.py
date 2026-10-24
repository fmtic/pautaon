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

from datetime import date, time, timedelta

from sqlalchemy import or_

from app.database import db
from app.models import Aluno, Curso, Inscricao, TemaAula, Turma, TurmaCurso, User
from app.utils.timezone import get_local_now


def ofertas_ativas(turma_id: int):
    """Ofertas ativas da turma em ordem estável (legado primeiro)."""
    return (
        TurmaCurso.query
        .filter_by(turma_id=turma_id, ativo=True)
        .order_by(TurmaCurso.id)
        .all()
    )


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

    oferta = TurmaCurso(
        turma_id=turma.id,
        curso_id=turma.curso_id,
        principal=False,
        professor_id=turma.professor_id,
        turno=turma.turno,
        dias_semana=turma.dias_semana,
        hora_inicio=turma.hora_inicio,
        hora_fim=turma.hora_fim,
        data_inicio=turma.data_inicio,
        data_fim=turma.data_fim,
        centro_custo=turma.centro_custo,
        programa=turma.programa,
        unidade_id=turma.unidade_id,
        ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()
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
    # Guarda se o início veio preenchido do formulário antes de qualquer
    # herança/ajuste — se veio vazio pode entrar na regra "turma em andamento".
    data_inicio_informada = data_inicio is not None

    curso = _validar_curso(turma, curso_id)
    professor_id = _validar_professor(professor_id, turma.unidade_id)
    _validar_principal_obrigatorio(turma, principal)

    # Regra "turma em andamento" (Onda 4 — Fase 4, D3b-1): roda ANTES da
    # validação de concomitância e da instanciação, para que o início efetivo
    # já seja usado em ambas. Se o início veio vazio, a turma já tem outra
    # oferta (ativa OU desativada) e está em andamento (já começou e ainda não
    # terminou), define o início da nova oferta como hoje local — para não
    # inventar aulas retroativas jamais lançadas. Tem PRECEDÊNCIA sobre a
    # herança abaixo (que usa `or`). Na primeira oferta da turma, ou com turma
    # encerrada, mantém a herança; com data_inicio preenchida respeita o valor.
    # Sinaliza via marcador `inicio_ajustado_para_hoje` para a rota exibir flash.
    inicio_ajustado_para_hoje = False
    if not data_inicio_informada:
        hoje_local = get_local_now().date()
        tem_outra_oferta = (
            TurmaCurso.query.filter_by(turma_id=turma.id).first() is not None
        )
        turma_em_andamento = (
            turma.data_inicio is not None
            and turma.data_inicio <= hoje_local
            and (turma.data_fim is None or turma.data_fim >= hoje_local)
        )
        if tem_outra_oferta and turma_em_andamento:
            data_inicio = hoje_local
            inicio_ajustado_para_hoje = True

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
    # Usa `or`, então preserva o `data_inicio` já definido pela regra acima.
    if turma.curso_id is None:
        professor_id = professor_id or turma.professor_id
        turno = turno or turma.turno
        dias_semana = dias_semana or turma.dias_semana
        hora_inicio = hora_inicio or turma.hora_inicio
        hora_fim = hora_fim or turma.hora_fim
        data_inicio = data_inicio or turma.data_inicio
        data_fim = data_fim or turma.data_fim
        centro_custo = centro_custo or turma.centro_custo
        programa = programa or turma.programa

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
        programa=programa,
        unidade_id=turma.unidade_id,
        ativo=True,
    )
    db.session.add(oferta)
    db.session.flush()
    _sincronizar_legado(turma, oferta)
    db.session.commit()
    # Marcador transitório (não é coluna): a rota usa para avisar o usuário.
    oferta.inicio_ajustado_para_hoje = inicio_ajustado_para_hoje
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
        "hora_inicio", "hora_fim", "data_inicio", "data_fim", "centro_custo", "programa",
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


# =============================================================================
# PAUTA E AGENDA DA OFERTA (Onda 4 — Fase 4, D2/D3b-1)
# =============================================================================


def _alunos_da_oferta(
    turma_id: int,
    oferta_id: int,
    *,
    incluir_inscricoes_null: bool,
) -> list:
    """Pauta de lançamento de uma oferta (Onda 4 — Fase 4, D2).

    Regra:
        - Entram os alunos com inscrição ativa na turma cujo
          `Inscricao.turma_curso_id` é a oferta.
        - Fallback: inscrições ativas da mesma turma com `turma_curso_id`
          NULL entram SOMENTE quando a turma tem exatamente 1 oferta ativa
          (`incluir_inscricoes_null=True`) — nesse caso a inscrição só pode
          ser dela. Com 2+ ofertas ativas as NULL são ambíguas e não
          aparecem em nenhuma pauta; a tela avisa a secretaria para definir
          o curso da inscrição.
        - Sem oferta ativa a rota mantém a pauta por turma (legado), que não
          passa por aqui.

    Move-se para este módulo na D3b-1 para ser reutilizada pelos leitores de
    pendência (dashboards) sem importar `app.registros.core` (blueprint) de
    `app.utils` — o que causaria dependência circular.
    """
    filtros_inscricao = [
        Inscricao.turma_id == turma_id,
        Inscricao.ativo == True,
    ]
    if incluir_inscricoes_null:
        filtros_inscricao.append(
            or_(
                Inscricao.turma_curso_id == oferta_id,
                Inscricao.turma_curso_id.is_(None),
            )
        )
    else:
        filtros_inscricao.append(Inscricao.turma_curso_id == oferta_id)
    # EXISTS em vez de JOIN: o aluno aparece uma única vez mesmo quando tem
    # 2+ inscrições ativas elegíveis (ex.: uma NULL e uma da oferta).
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

    dias = _dias_efetivos_da_oferta(oferta)
    if not _parse_dias(dias):
        return []

    datas: list[date] = []
    atual = inicio
    while atual <= limite_efetivo:
        if _data_bate_dias_semana(dias, atual) and atual.strftime('%Y-%m-%d') not in blocked:
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

"""
================================================================================
FREQUENCIA.PY - Helpers compartilhados de contagem de frequência
================================================================================

Criado na Onda 2A. Centraliza consultas usadas em mais de um lugar
(dashboard do professor, dashboard da secretaria, etc.) para evitar duplicação
e inconsistência.

IMPORTANTE (Onda 2A):
    `Frequencia.data` agora é `date`. Todas as comparações devem usar `date`,
    nunca string. Use `parse_date()` se a origem for string.

NOTA DE TRANSIÇÃO:
    `datas_bloqueadas_str` ainda retorna strings porque `gerar_datas` (em
    `app/utils/logica.py`) opera com strings no parâmetro `blocked_dates`.
    Quando `gerar_datas` for refatorado para `date`, esta função também deve
    ser ajustada para retornar `set[date]`.
================================================================================
"""

from datetime import date
from typing import Iterable

from app.models import Aluno, DiaBloqueado, Frequencia, Inscricao
from app.utils.timezone import get_local_now


def alunos_ativos_da_turma(turma_id: int) -> list[int]:
    """
    Retorna os IDs dos alunos ativos matriculados na turma.

    Filtra por:
        - Inscricao.ativo = True
        - Aluno.ativo = True
    """
    return [
        a.id for a in (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == turma_id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .all()
        )
    ]


def frequencias_lancadas(
    turma_id: int,
    data_alvo: date,
    aluno_ids: Iterable[int],
    turma_curso_id: int | None = None,
) -> int:
    """
    Conta quantos alunos da turma têm conceito lançado em `data_alvo`.

    `data_alvo` DEVE ser `date`. Após a Onda 2A, `Frequencia.data` é `date`;
    comparar com `date` permite que o índice `ix_frequencia_turma_data` seja
    aproveitado pela query.

    Considera "lançado" quando o conceito não é NULL (campo é ENUM nativo do PG).

    Onda 4 (Fase 4, D3a): com `turma_curso_id` informado a contagem é por
    oferta — usa o índice `ix_frequencia_turma_curso_data` e não enxerga
    lançamentos de outras ofertas no mesmo dia. Sem o parâmetro, mantém o
    comportamento legado (filtro por `turma_id`). Com 2+ ofertas ativas, o
    chamador que precisa saber "a turma já lançou hoje?" deve consultar por
    oferta, pois o total de alunos da turma inclui os das demais ofertas.
    """
    aluno_ids = list(aluno_ids)
    if not aluno_ids:
        return 0

    filtros = [
        Frequencia.data == data_alvo,
        Frequencia.aluno_id.in_(aluno_ids),
        Frequencia.conceito.isnot(None),
    ]
    if turma_curso_id is not None:
        filtros.append(Frequencia.turma_curso_id == turma_curso_id)
    else:
        filtros.append(Frequencia.turma_id == turma_id)
    return Frequencia.query.filter(*filtros).count()


def datas_bloqueadas_str(periodo_letivo_id: int | None) -> set[str]:
    """
    Datas sem aula do período, no formato 'YYYY-MM-DD' (string).

    Mantido como string porque `gerar_datas` ainda opera com strings no
    parâmetro `blocked_dates`. Quando `gerar_datas` for refatorado para
    `date`, esta função pode retornar `set[date]`.
    """
    if not periodo_letivo_id:
        return set()
    return {
        d.data.strftime('%Y-%m-%d')
        for d in DiaBloqueado.query.filter_by(
            periodo_letivo_id=periodo_letivo_id
        ).all()
    }


def contar_pendencias_frequencia(turmas) -> int:
    """
    Conta o total de aulas com frequência incompleta em uma lista de turmas.

    Uma aula é "pendente" quando pelo menos um aluno ativo da turma não tem
    conceito lançado naquele dia.

    Usa `parse_date` para aceitar tanto `date` quanto string vinda de
    `gerar_datas` (transição).

    Onda 4 (Fase 4, D3b-1): com 2+ ofertas ativas a pendência é avaliada por
    OFERTA — cada oferta usa sua própria agenda (vigência + dias da semana) e
    sua própria pauta (`_alunos_da_oferta`, regra da D2), comparando o lançado
    da oferta (`frequencias_lancadas(..., turma_curso_id=oferta)`) com o tamanho
    da pauta dela. Assim uma aula de uma segunda oferta em dia que o calendário
    legado da turma não cobre deixa de "sumir" da contagem. Com 0 ou 1 oferta
    ativa o cálculo é exatamente o de hoje (por turma).
    """
    from app.services.turma_curso import ofertas_ativas
    from app.utils.datetime_parse import parse_date
    from app.utils.logica import gerar_datas

    total = 0
    for turma in turmas:
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)

        ativas = ofertas_ativas(turma.id)
        if len(ativas) >= 2:
            total += _pendencias_por_ofertas(turma, ativas, blocked)
            continue

        # 0 ou 1 oferta ativa: comportamento legado inalterado (por turma).
        datas_aula = gerar_datas(
            turma, incluir_futuro=False, blocked_dates=blocked
        )

        aluno_ids = alunos_ativos_da_turma(turma.id)
        if not aluno_ids:
            continue

        for data_item in datas_aula:
            data_alvo = parse_date(data_item)
            if data_alvo is None:
                continue
            if frequencias_lancadas(turma.id, data_alvo, aluno_ids) < len(aluno_ids):
                total += 1
    return total


def _pendencias_por_ofertas(turma, ativas, blocked) -> int:
    """Pendência somada por oferta (2+ ativas) — D3b-1.

    Para cada oferta: itera as datas esperadas da própria oferta até hoje e
    conta a aula como pendente quando o lançado da oferta é menor que o
    tamanho da pauta dela. Pauta estrita (sem fallback NULL), pois com 2+
    ofertas as inscrições NULL são ambíguas.
    """
    from app.services.turma_curso import _alunos_da_oferta, datas_esperadas_oferta

    hoje = get_local_now().date()
    pendencias = 0
    for oferta in ativas:
        pauta = _alunos_da_oferta(
            turma.id, oferta.id,
        )
        if not pauta:
            continue
        aluno_ids = [a.id for a in pauta]
        for data_alvo in datas_esperadas_oferta(oferta, hoje, blocked):
            lancados = frequencias_lancadas(
                turma.id, data_alvo, aluno_ids, turma_curso_id=oferta.id,
            )
            if lancados < len(aluno_ids):
                pendencias += 1
    return pendencias


def situacao_datas_oferta(turma, oferta) -> dict:
    """Status das aulas da OFERTA para o seletor "Data da Aula" (V3a).

    Usa a definição de "lançada" já existente nas pendências do dashboard
    (``frequencias_lancadas`` / ``_pendencias_por_ofertas``): a aula está
    lançada quando **todos** os alunos da pauta da oferta têm conceito
    registrado naquela data. Nada novo é criado aqui — só em lote.

    Devolve::

        {
          "status": {ISO: "lancada" | "pendente"},  # datas da oferta
          "lancadas": X,        # datas <= hoje totalmente lançadas
          "total_ate_hoje": Y,  # datas da oferta <= hoje
          "pendentes": Z,       # Y - X
          "proxima_pendente": ISO | None,  # a mais antiga
        }

    Datas futuras já lançadas entram em ``status`` como "lancada" (e não
    contam em X/Y/Z). Datas do seletor que não pertencem ao calendário da
    oferta simplesmente não aparecem em ``status`` (sem marca no template).

    Legado D2: quando a oferta é a ÚNICA ativa da turma, as linhas com
    ``turma_curso_id`` NULL contam como dela (mesma regra das demais leituras).
    Uma única consulta agregada por data — sem N+1.
    """
    from sqlalchemy import and_, func, or_

    from app.database import db
    from app.services.frequencia_oferta import ofertas_unicas_ativas
    from app.services.turma_curso import _alunos_da_oferta, datas_aula_oferta

    vazio = {
        "status": {},
        "lancadas": 0,
        "total_ate_hoje": 0,
        "pendentes": 0,
        "proxima_pendente": None,
    }
    if turma is None or oferta is None:
        return vazio

    hoje = get_local_now().date()
    blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
    pauta = _alunos_da_oferta(turma.id, oferta.id)
    aluno_ids = [aluno.id for aluno in pauta]
    datas_oferta = datas_aula_oferta(oferta, blocked=blocked)
    if not aluno_ids or not datas_oferta:
        return vazio

    escopo = [Frequencia.turma_curso_id == oferta.id]
    if oferta.id in ofertas_unicas_ativas([oferta.id]):
        escopo = [
            or_(
                Frequencia.turma_curso_id == oferta.id,
                and_(
                    Frequencia.turma_curso_id.is_(None),
                    Frequencia.turma_id == turma.id,
                ),
            )
        ]

    linhas = (
        db.session.query(
            Frequencia.data,
            func.count(func.distinct(Frequencia.aluno_id)),
        )
        .filter(
            Frequencia.data.in_(datas_oferta),
            Frequencia.aluno_id.in_(aluno_ids),
            Frequencia.conceito.isnot(None),
            *escopo,
        )
        .group_by(Frequencia.data)
        .all()
    )
    lancados_por_data = {data: quantidade for data, quantidade in linhas}

    status: dict[str, str] = {}
    lancadas = 0
    pendentes: list[date] = []
    for data_oferta in datas_oferta:
        completa = lancados_por_data.get(data_oferta, 0) >= len(aluno_ids)
        chave = data_oferta.strftime("%Y-%m-%d")
        if data_oferta <= hoje:
            if completa:
                lancadas += 1
                status[chave] = "lancada"
            else:
                pendentes.append(data_oferta)
                status[chave] = "pendente"
        elif completa:
            # Futura já lançada também recebe a marca.
            status[chave] = "lancada"

    return {
        "status": status,
        "lancadas": lancadas,
        "total_ate_hoje": sum(1 for d in datas_oferta if d <= hoje),
        "pendentes": len(pendentes),
        "proxima_pendente": (
            pendentes[0].strftime("%Y-%m-%d") if pendentes else None
        ),
    }
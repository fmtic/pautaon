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
) -> int:
    """
    Conta quantos alunos da turma têm conceito lançado em `data_alvo`.

    `data_alvo` DEVE ser `date`. Após a Onda 2A, `Frequencia.data` é `date`;
    comparar com `date` permite que o índice `ix_frequencia_turma_data` seja
    aproveitado pela query.

    Considera "lançado" quando o conceito não é NULL nem string vazia.
    """
    aluno_ids = list(aluno_ids)
    if not aluno_ids:
        return 0
    return Frequencia.query.filter(
        Frequencia.turma_id == turma_id,
        Frequencia.data == data_alvo,
        Frequencia.aluno_id.in_(aluno_ids),
        Frequencia.conceito.isnot(None),
        Frequencia.conceito != '',
    ).count()


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
    """
    from app.utils.datetime_parse import parse_date
    from app.utils.logica import gerar_datas

    total = 0
    for turma in turmas:
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
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
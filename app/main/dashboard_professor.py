"""Dashboard do perfil professor: turmas, alunos e pendências de frequência."""

from datetime import date

from flask import current_app, flash, render_template
from flask_login import current_user

from app.models import Aluno, DiaBloqueado, Turma
from app.services.turma_curso import (
    _alunos_da_oferta,
    datas_esperadas_oferta,
    ofertas_ativas,
)
from app.utils.datetime_parse import parse_date
from app.utils.frequencia import (
    alunos_ativos_da_turma,
    datas_bloqueadas_str,
    frequencias_lancadas,
)
from app.utils.logica import gerar_datas
from app.utils.timezone import get_local_now


def _nome_curso_oferta(oferta) -> str:
    return oferta.curso.nome if oferta.curso else f"curso #{oferta.curso_id}"


def _aulas_pendentes(minhas_turmas):
    """
    Lista de aulas com frequência incompleta nas turmas do professor.

    Retorna lista de dicts:
        - turma     : instância de Turma
        - data      : `date` da aula (após Onda 2A)
        - faltando  : alunos sem conceito lançado
        - total     : total de alunos ativos na turma (ou na oferta)
        - oferta_label (opcional): "Turma — Curso" quando a turma tem 2+
          ofertas ativas (identifica a oferta da pendência; D3b-1)
        - turma_curso_id (opcional): id da oferta, para o link de ação
          abrir a pauta da oferta certa

    Onda 4 (D3b-1): com 2+ ofertas ativas cada oferta é avaliada
    separadamente pela sua própria agenda (vigência + dias) e a sua própria
    pauta; uma turma só aparece como completa se todas as ofertas esperadas
    na data foram lançadas. Com 0 ou 1 oferta o cálculo é o legado (por
    turma), exatamente como hoje. A lista de turmas do professor não muda.
    """
    pendentes = []
    hoje = get_local_now().date()
    for turma in minhas_turmas:
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)

        ativas = ofertas_ativas(turma.id)
        if len(ativas) >= 2:
            for oferta in ativas:
                pauta = _alunos_da_oferta(
                    turma.id, oferta.id, incluir_inscricoes_null=False,
                )
                if not pauta:
                    continue
                aluno_ids = [a.id for a in pauta]
                for data_alvo in datas_esperadas_oferta(oferta, hoje, blocked):
                    lancados = frequencias_lancadas(
                        turma.id, data_alvo, aluno_ids,
                        turma_curso_id=oferta.id,
                    )
                    if lancados < len(aluno_ids):
                        pendentes.append({
                            'turma': turma,
                            'data': data_alvo,
                            'faltando': len(aluno_ids) - lancados,
                            'total': len(aluno_ids),
                            'oferta_label': f"{turma.nome} — {_nome_curso_oferta(oferta)}",
                            'turma_curso_id': oferta.id,
                        })
            continue

        # 0 ou 1 oferta ativa: caminho legado inalterado (por turma).
        datas_aula = gerar_datas(
            turma, incluir_futuro=False, blocked_dates=blocked
        )

        aluno_ids = alunos_ativos_da_turma(turma.id)
        if not aluno_ids:
            continue

        for data_item in datas_aula:
            # `gerar_datas` ainda pode retornar strings; parse_date normaliza.
            data_alvo = parse_date(data_item)
            if data_alvo is None:
                continue

            lancados = frequencias_lancadas(turma.id, data_alvo, aluno_ids)
            if lancados < len(aluno_ids):
                pendentes.append({
                    'turma':    turma,
                    'data':     data_alvo,
                    'faltando': len(aluno_ids) - lancados,
                    'total':    len(aluno_ids),
                })

    pendentes.sort(key=lambda x: x['data'])
    return pendentes


def render_dashboard_professor():
    """Painel com as turmas do professor logado e as aulas com frequência pendente."""
    try:
        minhas_turmas = Turma.query.filter_by(
            professor_id=current_user.id, ativo=True
        ).all()
        ids_turmas = [t.id for t in minhas_turmas]

        total_meus_alunos = 0
        if ids_turmas:
            total_meus_alunos = (
                Aluno.query.join(Aluno.turmas)
                .filter(Turma.id.in_(ids_turmas), Aluno.ativo == True)
                .distinct()
                .count()
            )

        hoje = date.today()
        periodo_ids = {
            t.periodo_letivo_id for t in minhas_turmas if t.periodo_letivo_id
        }
        dias_bloqueados = []
        if periodo_ids:
            dias_bloqueados = (
                DiaBloqueado.query.filter(
                    DiaBloqueado.periodo_letivo_id.in_(periodo_ids),
                    DiaBloqueado.data >= hoje,
                )
                .order_by(DiaBloqueado.data)
                .all()
            )

        aulas_pendentes = _aulas_pendentes(minhas_turmas)

        return render_template(
            "dashboard/professor.html",
            turmas=minhas_turmas,
            total_alunos=total_meus_alunos,
            dias_bloqueados=dias_bloqueados,
            aulas_pendentes=aulas_pendentes,
        )
    except Exception:
        # Loga o traceback no servidor em vez de engolir silenciosamente.
        current_app.logger.exception(
            "Erro ao processar as turmas do professor (user_id=%s)",
            current_user.id,
        )
        flash("Erro ao processar as turmas do professor.", "warning")
        return render_template(
            "dashboard/professor.html",
            turmas=[],
            total_alunos=0,
            dias_bloqueados=[],
            aulas_pendentes=[],
        )
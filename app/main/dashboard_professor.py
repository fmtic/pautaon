"""Dashboard do perfil professor: turmas, alunos e pendências de frequência."""

from datetime import date, timedelta

from flask import current_app, flash, render_template
from flask_login import current_user

from app.models import Aluno, DiaBloqueado, Turma, TurmaCurso
from app.services.turma_curso import (
    _alunos_da_oferta,
    _dias_efetivos_da_oferta,
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


def _horario_oferta(oferta):
    """Retorna (hora_inicio, hora_fim) da oferta, herdando da turma quando ausentes."""
    hi = oferta.hora_inicio
    hf = oferta.hora_fim
    if (hi is None or hf is None) and oferta.turma is not None:
        if hi is None:
            hi = oferta.turma.hora_inicio
        if hf is None:
            hf = oferta.turma.hora_fim
    return hi, hf


def _aulas_pendentes(minhas_turmas, professor_id=None, prazo_dias=0):
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

    `professor_id`: quando informado, apenas ofertas cujo responsável é esse
    professor são consideradas (dashboard do professor). `None` preserva o
    comportamento anterior (todas as ofertas da turma).

    `prazo_dias`: aulas ocorridas há até `prazo_dias` dias NÃO são consideradas
    pendentes (prazo de lançamento). 0 = sem prazo (comportamento legado).
    """
    pendentes = []
    hoje = get_local_now().date()
    for turma in minhas_turmas:
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)

        ativas = ofertas_ativas(turma.id)
        if professor_id is not None:
            ativas = [o for o in ativas if o.professor_id == professor_id]

        if len(ativas) >= 2:
            for oferta in ativas:
                pauta = _alunos_da_oferta(
                    turma.id, oferta.id, incluir_inscricoes_null=False,
                )
                if not pauta:
                    continue
                aluno_ids = [a.id for a in pauta]
                for data_alvo in datas_esperadas_oferta(oferta, hoje, blocked):
                    if prazo_dias and (hoje - data_alvo).days <= prazo_dias:
                        continue
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
        if professor_id is not None and len(ativas) == 1 and ativas[0].professor_id != professor_id:
            continue

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
            if prazo_dias and (hoje - data_alvo).days <= prazo_dias:
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


def _entradas_professor(user_id):
    """Lista de cursos (ofertas) que o professor leciona, como dicts unificados.

    Cada entrada contém: turma, oferta (TurmaCurso ou None), turma_curso_id,
    curso_nome, label, dias, hora_inicio, hora_fim, alunos_count, pendentes_count.
    """
    entradas = []
    vistas = set()

    # 1) Ofertas onde o professor é o responsável.
    ofertas = (
        TurmaCurso.query.join(Turma)
        .filter(
            TurmaCurso.ativo == True,
            Turma.ativo == True,
            TurmaCurso.professor_id == user_id,
        )
        .order_by(Turma.nome, TurmaCurso.id)
        .all()
    )
    for oferta in ofertas:
        turma = oferta.turma
        chave = (turma.id, oferta.id)
        if chave in vistas:
            continue
        vistas.add(chave)
        ativas_turma = ofertas_ativas(turma.id)
        incluir_null = len(ativas_turma) <= 1
        pauta = _alunos_da_oferta(
            turma.id, oferta.id, incluir_inscricoes_null=incluir_null,
        )
        hi, hf = _horario_oferta(oferta)
        dias = _dias_efetivos_da_oferta(oferta)
        entradas.append({
            'turma': turma,
            'oferta': oferta,
            'turma_curso_id': oferta.id,
            'curso_nome': _nome_curso_oferta(oferta),
            'label': f"{turma.nome} — {_nome_curso_oferta(oferta)}",
            'dias': dias,
            'hora_inicio': hi,
            'hora_fim': hf,
            'alunos_count': len(pauta),
            'pendentes_count': 0,
        })

    # 2) Turmas legadas onde o professor é responsável e não tem oferta atribuída.
    turmas_legado = Turma.query.filter_by(professor_id=user_id, ativo=True).all()
    for turma in turmas_legado:
        ativas = ofertas_ativas(turma.id)
        if any(o.professor_id == user_id for o in ativas):
            continue
        if ativas:
            continue
        chave = (turma.id, None)
        if chave in vistas:
            continue
        vistas.add(chave)
        aluno_ids = alunos_ativos_da_turma(turma.id)
        curso_nome = turma.curso.nome if getattr(turma, 'curso', None) else turma.nome
        entradas.append({
            'turma': turma,
            'oferta': None,
            'turma_curso_id': None,
            'curso_nome': curso_nome,
            'label': f"{turma.nome} — {curso_nome}",
            'dias': turma.dias_semana,
            'hora_inicio': turma.hora_inicio,
            'hora_fim': turma.hora_fim,
            'alunos_count': len(aluno_ids),
            'pendentes_count': 0,
        })

    # Preenche pendentes_count por entrada (prazo de 3 dias).
    hoje = get_local_now().date()
    for e in entradas:
        turma = e['turma']
        blocked = datas_bloqueadas_str(turma.periodo_letivo_id)
        oferta = e['oferta']
        if oferta is not None:
            ativas_turma = ofertas_ativas(turma.id)
            incluir_null = len(ativas_turma) <= 1
            pauta = _alunos_da_oferta(
                turma.id, oferta.id, incluir_inscricoes_null=incluir_null,
            )
            aluno_ids = [a.id for a in pauta]
            if not aluno_ids:
                e['pendentes_count'] = 0
                continue
            count = 0
            for data_alvo in datas_esperadas_oferta(oferta, hoje, blocked):
                if (hoje - data_alvo).days <= 3:
                    continue
                lancados = frequencias_lancadas(
                    turma.id, data_alvo, aluno_ids, turma_curso_id=oferta.id,
                )
                if lancados < len(aluno_ids):
                    count += 1
            e['pendentes_count'] = count
        else:
            aluno_ids = alunos_ativos_da_turma(turma.id)
            if not aluno_ids:
                e['pendentes_count'] = 0
                continue
            datas_aula = gerar_datas(turma, incluir_futuro=False, blocked_dates=blocked)
            count = 0
            for data_item in datas_aula:
                data_alvo = parse_date(data_item)
                if data_alvo is None:
                    continue
                if (hoje - data_alvo).days <= 3:
                    continue
                lancados = frequencias_lancadas(turma.id, data_alvo, aluno_ids)
                if lancados < len(aluno_ids):
                    count += 1
            e['pendentes_count'] = count

    return entradas


def render_dashboard_professor():
    """Painel do professor logado.

    Rota/view auxiliar que monta o contexto da página dashboard/professor.html:

    - ``turmas``: lista de turmas distintas (sem repetição) do professor, usada
      para dias bloqueados e pendências.
    - ``entradas``: lista de cursos (ofertas/TurmaCurso) que o professor leciona,
      cada um com contagem de alunos (de-duplicada por oferta) e de aulas
      pendentes (mais de 3 dias).
    - ``total_alunos``: total de alunos distintos sob a gestão do professor.
    - ``dias_bloqueados``: próximos dias sem aula (feriados etc.) das turmas.
    - ``aulas_pendentes``: aulas com frequência incompleta há mais de 3 dias.

    Em caso de erro, registra o traceback e exibe a página vazia com flash.
    """
    try:
        user_id = current_user.id

        entradas = _entradas_professor(user_id)

        # Turmas distintas para dias bloqueados e pendências.
        turmas_distintas = []
        vistas_turmas = set()
        for e in entradas:
            if e['turma'].id not in vistas_turmas:
                vistas_turmas.add(e['turma'].id)
                turmas_distintas.append(e['turma'])

        # Alunos sob gestão (sem repetir).
        aluno_ids = set()
        for e in entradas:
            turma = e['turma']
            oferta = e['oferta']
            if oferta is not None:
                ativas_turma = ofertas_ativas(turma.id)
                incluir_null = len(ativas_turma) <= 1
                pauta = _alunos_da_oferta(
                    turma.id, oferta.id, incluir_inscricoes_null=incluir_null,
                )
                for a in pauta:
                    aluno_ids.add(a.id)
            else:
                for aid in alunos_ativos_da_turma(turma.id):
                    aluno_ids.add(aid)
        total_meus_alunos = len(aluno_ids)

        hoje = get_local_now().date()
        periodo_ids = {
            t.periodo_letivo_id for t in turmas_distintas if t.periodo_letivo_id
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

        aulas_pendentes = _aulas_pendentes(
            turmas_distintas, professor_id=user_id, prazo_dias=3,
        )

        return render_template(
            "dashboard/professor.html",
            turmas=turmas_distintas,
            entradas=entradas,
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
            entradas=[],
            total_alunos=0,
            dias_bloqueados=[],
            aulas_pendentes=[],
        )




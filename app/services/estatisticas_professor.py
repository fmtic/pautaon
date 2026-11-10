"""
Serviço de inteligência pedagógica e estatísticas para o painel do professor.

Mapeia indicadores quantitativos (frequência, faltas, presenças) e qualitativos
(conceitos A, B, C, D), rendimento por aluno e cumprimento da pauta.

Compatível com a arquitetura da Onda 4 (turmas multi-ofertas TurmaCurso e legadas).
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any, Dict, Optional

from app.models import Aluno, Frequencia, Inscricao, RegistroAula, TemaAula, Turma, TurmaCurso
from app.services.entrada_oferta import aula_conta_para_aluno
from app.services.turma_curso import _alunos_da_oferta, datas_aula_oferta
from app.utils.frequencia import alunos_ativos_da_turma, datas_bloqueadas_str
from app.utils.logica import formatar_nome_proprio, gerar_datas
from app.utils.timezone import get_local_now


def obter_estatisticas_professor(
    user_id: int,
    turma_id: Optional[int] = None,
    turma_curso_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Calcula estatísticas pedagógicas consolidadas para as turmas do professor.

    Se `turma_id` for informado, calcula com foco na turma/oferta especificada.
    Caso contrário, seleciona a primeira turma/oferta válida do professor ou agrega.
    """
    from app.main.dashboard_professor import _entradas_professor

    entradas = _entradas_professor(user_id)
    if not entradas:
        return {
            "entradas": [],
            "entrada_selecionada": None,
            "resumo_geral": _resumo_vazio(),
            "qualitativo_conceitos": _conceitos_vazio(),
            "evolucao_temporal": [],
            "alunos_rendimento": [],
            "cobertura_pauta": _cobertura_vazia(),
            "alertas_busca_ativa": [],
            "alunos_destaque": [],
        }

    # Seleciona a entrada alvo (ou primeira disponível)
    entrada_selecionada = None
    if turma_id is not None:
        for e in entradas:
            if e["turma"].id == turma_id:
                if turma_curso_id is not None and e["turma_curso_id"] == turma_curso_id:
                    entrada_selecionada = e
                    break
                elif turma_curso_id is None:
                    entrada_selecionada = e
                    break
    if entrada_selecionada is None:
        entrada_selecionada = entradas[0]

    turma_alvo: Turma = entrada_selecionada["turma"]
    oferta_alvo: Optional[TurmaCurso] = entrada_selecionada["oferta"]
    tc_id: Optional[int] = entrada_selecionada["turma_curso_id"]

    # 1. Alunos da pauta
    if oferta_alvo is not None:
        alunos = _alunos_da_oferta(turma_alvo.id, oferta_alvo.id)
    else:
        aluno_ids = alunos_ativos_da_turma(turma_alvo.id)
        alunos = Aluno.query.filter(Aluno.id.in_(aluno_ids), Aluno.ativo == True).order_by(Aluno.nome).all() if aluno_ids else []

    aluno_map = {a.id: a for a in alunos}
    aluno_ids_pauta = list(aluno_map.keys())

    # 2. Busca registros de frequência da turma/oferta
    freq_filtros = [Frequencia.conceito.isnot(None)]
    if tc_id is not None:
        freq_filtros.append(Frequencia.turma_curso_id == tc_id)
    else:
        freq_filtros.append(Frequencia.turma_id == turma_alvo.id)

    if aluno_ids_pauta:
        freq_filtros.append(Frequencia.aluno_id.in_(aluno_ids_pauta))

    registros_freq = (
        Frequencia.query.filter(*freq_filtros)
        .order_by(Frequencia.data.asc())
        .all() if aluno_ids_pauta else []
    )

    # 3. Busca diário de aula (RegistroAula) para temas e observações
    diario_filtros = []
    if tc_id is not None:
        diario_filtros.append(RegistroAula.turma_curso_id == tc_id)
    else:
        diario_filtros.append(RegistroAula.turma_id == turma_alvo.id)

    diarios = (
        RegistroAula.query.filter(*diario_filtros)
        .order_by(RegistroAula.data.asc())
        .all()
    )
    diario_por_data = {d.data: d for d in diarios}

    # 4. Processamento dos registros de frequência
    total_presencas = 0
    total_faltas = 0
    total_justificadas = 0
    contagem_conceitos = {"A": 0, "B": 0, "C": 0, "D": 0}

    # Por data: {data: {'presencas': int, 'faltas': int, 'conceitos': {...}}}
    datas_map = defaultdict(lambda: {"presencas": 0, "faltas": 0, "justificadas": 0, "conceitos": {"A": 0, "B": 0, "C": 0, "D": 0}})

    # Por aluno: {aluno_id: {'presencas': int, 'faltas': int, 'justificadas': int, 'conceitos': {...}, 'historico': []}}
    aluno_stats = {
        aid: {
            "aluno": aluno_map[aid],
            "presencas": 0,
            "faltas": 0,
            "justificadas": 0,
            "conceitos": {"A": 0, "B": 0, "C": 0, "D": 0},
            "historico": [],  # lista de (data, conceito, tema_nome)
        }
        for aid in aluno_ids_pauta
    }

    for reg in registros_freq:
        c_val = reg.conceito.value if hasattr(reg.conceito, "value") else str(reg.conceito)
        d_val = reg.data

        # Agrupamento da turma por data
        if c_val in ("A", "B", "C", "D"):
            datas_map[d_val]["presencas"] += 1
            datas_map[d_val]["conceitos"][c_val] += 1
            total_presencas += 1
            contagem_conceitos[c_val] += 1
        elif c_val == "F":
            datas_map[d_val]["faltas"] += 1
            total_faltas += 1
        elif c_val == "J":
            datas_map[d_val]["justificadas"] += 1
            total_justificadas += 1

        # Agrupamento individual por aluno
        if reg.aluno_id in aluno_stats:
            astat = aluno_stats[reg.aluno_id]
            t_obj = diario_por_data.get(d_val)
            tema_titulo = ", ".join(tema.titulo for tema in t_obj.temas) if t_obj and t_obj.temas else None
            astat["historico"].append({
                "data": d_val,
                "data_str": d_val.strftime("%d/%m/%Y"),
                "conceito": c_val,
                "tema": tema_titulo,
            })

            if c_val in ("A", "B", "C", "D"):
                astat["presencas"] += 1
                astat["conceitos"][c_val] += 1
            elif c_val == "F":
                astat["faltas"] += 1
            elif c_val == "J":
                astat["justificadas"] += 1

    # 5. Cálculo das métricas consolidadas da turma
    total_validas = total_presencas + total_faltas
    taxa_presenca_turma = round((total_presencas / total_validas * 100), 1) if total_validas > 0 else 0.0

    # Percentual de conceitos sobre o total de presenças
    pct_conceitos = {}
    for conc in ("A", "B", "C", "D"):
        qtd = contagem_conceitos[conc]
        pct = round((qtd / total_presencas * 100), 1) if total_presencas > 0 else 0.0
        pct_conceitos[conc] = pct

    # IQR (Índice de Qualidade de Rendimento da Turma): média ponderada (A=4, B=3, C=2, D=1) normalizada de 0 a 10
    iqr_bruto = (
        (contagem_conceitos["A"] * 4 + contagem_conceitos["B"] * 3 + contagem_conceitos["C"] * 2 + contagem_conceitos["D"] * 1)
        / total_presencas
    ) if total_presencas > 0 else 0.0
    iqr_nota = round(iqr_bruto * 2.5, 1) if total_presencas > 0 else 0.0

    # 6. Evolução temporal
    datas_ordenadas = sorted(datas_map.keys())
    evolucao_temporal = []
    for d_val in datas_ordenadas:
        info_d = datas_map[d_val]
        total_dia = info_d["presencas"] + info_d["faltas"]
        pct_dia = round((info_d["presencas"] / total_dia * 100), 1) if total_dia > 0 else 0.0
        t_obj = diario_por_data.get(d_val)
        evolucao_temporal.append({
            "data": d_val.strftime("%d/%m"),
            "data_completa": d_val.strftime("%d/%m/%Y"),
            "presencas": info_d["presencas"],
            "faltas": info_d["faltas"],
            "taxa_presenca": pct_dia,
            "conceitos": info_d["conceitos"],
            "tema": ", ".join(tema.titulo for tema in t_obj.temas) if t_obj and t_obj.temas else None,
        })

    # 7. Análise de Alunos (Rendimento e Alertas)
    alunos_processados = []
    alertas_busca_ativa = []
    alunos_destaque = []

    for aid, astat in aluno_stats.items():
        aluno_obj = astat["aluno"]
        p_val = astat["presencas"]
        f_val = astat["faltas"]
        j_val = astat["justificadas"]
        total_a = p_val + f_val
        freq_pct = round((p_val / total_a * 100), 1) if total_a > 0 else (100.0 if not registros_freq else 0.0)

        # Classificação semafórica de assiduidade
        if freq_pct >= 90.0:
            faixa_freq = "hi"
            badge_freq_classe = "success"
        elif freq_pct >= 75.0:
            faixa_freq = "mid"
            badge_freq_classe = "warning"
        else:
            faixa_freq = "lo"
            badge_freq_classe = "danger"

        # Conceito Predominante (desempate para o melhor conceito)
        c_dict = astat["conceitos"]
        conceito_pred = "A"
        max_qtd = -1
        for conc in ("A", "B", "C", "D"):
            if c_dict[conc] > max_qtd and c_dict[conc] > 0:
                max_qtd = c_dict[conc]
                conceito_pred = conc

        # Classificação do Perfil de Rendimento Pedagógico
        total_conceitos = sum(c_dict.values())
        if total_conceitos == 0:
            categoria_rendimento = "SEM_DADOS"
            badge_rend_classe = "secondary"
            rendimento_label = "Sem avaliações"
        else:
            ab_ratio = (c_dict["A"] + c_dict["B"]) / total_conceitos
            cd_ratio = (c_dict["C"] + c_dict["D"]) / total_conceitos
            if ab_ratio >= 0.70:
                categoria_rendimento = "ALTO"
                badge_rend_classe = "success"
                rendimento_label = "Alto Rendimento"
            elif cd_ratio >= 0.50 or c_dict["D"] > (c_dict["A"] + c_dict["B"]):
                categoria_rendimento = "BAIXO"
                badge_rend_classe = "danger"
                rendimento_label = "Atenção Pedagógica"
            else:
                categoria_rendimento = "MEDIO"
                badge_rend_classe = "primary"
                rendimento_label = "Rendimento Regular"

        # Alerta duplo (baixo rendimento + baixa frequência)
        alerta_duplo = (faixa_freq == "lo" and categoria_rendimento == "BAIXO")

        # Faltas consecutivas recentes (análise cronológica reversa)
        historico_ordenado = sorted(astat["historico"], key=lambda x: x["data"], reverse=True)
        faltas_seguidas_atuais = 0
        for h in historico_ordenado:
            if h["conceito"] == "F":
                faltas_seguidas_atuais += 1
            else:
                break

        aluno_dict = {
            "id": aluno_obj.id,
            "nome": formatar_nome_proprio(aluno_obj.nome) or aluno_obj.nome,
            "presencas": p_val,
            "faltas": f_val,
            "justificadas": j_val,
            "total_aulas": total_a,
            "freq_pct": freq_pct,
            "faixa_freq": faixa_freq,
            "badge_freq_classe": badge_freq_classe,
            "conceitos": c_dict,
            "conceito_predominante": conceito_pred if total_conceitos > 0 else "—",
            "categoria_rendimento": categoria_rendimento,
            "badge_rend_classe": badge_rend_classe,
            "rendimento_label": rendimento_label,
            "alerta_duplo": alerta_duplo,
            "faltas_consecutivas": faltas_seguidas_atuais,
            "historico": historico_ordenado,
        }
        alunos_processados.append(aluno_dict)

        # Gatilho de busca ativa: 3 ou mais faltas seguidas
        if faltas_seguidas_atuais >= 3:
            alertas_busca_ativa.append(aluno_dict)

        # Aluno destaque: 100% frequência e alto rendimento com mais de 2 aulas
        if freq_pct == 100.0 and categoria_rendimento == "ALTO" and total_a >= 2:
            alunos_destaque.append(aluno_dict)

    # Ordena alunos: primeiro os em risco crítico/alerta duplo, depois por ordem alfabética
    alunos_processados.sort(key=lambda x: (not x["alerta_duplo"], x["faixa_freq"] != "lo", x["nome"]))

    # 8. Relação Professor x Aluno x Pauta (Cobertura curricular e dias esperados)
    # AJ18-C (item 2): denominadores por data respeitam a entrada do aluno na
    # oferta (alunos esperados = pauta com entrada NULL ou <= data, regra única
    # em app.services.entrada_oferta). Data sem aluno esperado mantém
    # comportamento de pauta vazia (não entra como esperada/pendente).
    hoje = get_local_now().date()
    blocked = datas_bloqueadas_str(turma_alvo.periodo_letivo_id)
    if oferta_alvo is not None:
        datas_calendario = datas_aula_oferta(oferta_alvo, limite=hoje, blocked=blocked)
        curso_id = oferta_alvo.curso_id
        inscricoes_pauta = Inscricao.query.filter(
            Inscricao.turma_curso_id == oferta_alvo.id,
            Inscricao.ativo.is_(True),
            Inscricao.aluno_id.in_(aluno_ids_pauta or [-1]),
        ).all() if aluno_ids_pauta else []
    else:
        datas_geradas = gerar_datas(turma_alvo, incluir_futuro=False, blocked_dates=blocked)
        datas_calendario = [
            d for d in (date.fromisoformat(str(di)) for di in datas_geradas if di) if d <= hoje
        ]
        curso_id = turma_alvo.curso_id
        inscricoes_pauta = Inscricao.query.filter(
            Inscricao.turma_id == turma_alvo.id,
            Inscricao.ativo.is_(True),
            Inscricao.aluno_id.in_(aluno_ids_pauta or [-1]),
        ).all() if aluno_ids_pauta else []

    inscr_por_aluno = {}
    for insc in inscricoes_pauta:
        inscr_por_aluno.setdefault(insc.aluno_id, insc)

    lancados_por_data = defaultdict(set)
    for reg in registros_freq:
        if reg.data is not None and reg.aluno_id is not None:
            lancados_por_data[reg.data].add(reg.aluno_id)

    aulas_esperadas_qtd = 0
    aulas_lancadas_qtd = 0
    for d_cal in datas_calendario:
        esperados = {
            aid for aid in aluno_ids_pauta
            if (insc := inscr_por_aluno.get(aid)) is not None
            and aula_conta_para_aluno(insc, d_cal)
        }
        if not esperados:
            # Data sem aluno esperado: comportamento de pauta vazia.
            continue
        aulas_esperadas_qtd += 1
        if esperados.issubset(lancados_por_data.get(d_cal, set())):
            aulas_lancadas_qtd += 1

    pautas_em_dia_pct = round((aulas_lancadas_qtd / aulas_esperadas_qtd * 100), 1) if aulas_esperadas_qtd > 0 else 100.0

    # Temas do curso
    temas_curso = TemaAula.query.filter_by(curso_id=curso_id, ativo=True).order_by(TemaAula.ordem).all() if curso_id else []
    temas_ids_ministrados = {tema.id for diario in diarios for tema in diario.temas}
    temas_ids_ministrados.update(
        d.tema_id for d in diarios if d.tema_id is not None
    )
    temas_ministrados_count = len(temas_ids_ministrados)
    temas_total_count = len(temas_curso)

    cobertura_pauta = {
        "aulas_esperadas": aulas_esperadas_qtd,
        "aulas_lancadas": aulas_lancadas_qtd,
        "aulas_pendentes": max(0, aulas_esperadas_qtd - aulas_lancadas_qtd),
        "taxa_cumprimento_pauta": min(100.0, pautas_em_dia_pct),
        "temas_total": temas_total_count,
        "temas_ministrados": temas_ministrados_count,
        "temas_cobertura_pct": round((temas_ministrados_count / temas_total_count * 100), 1) if temas_total_count > 0 else 0.0,
    }

    # Contagem de alunos por faixa
    qtd_criticos = sum(1 for a in alunos_processados if a["faixa_freq"] == "lo")
    qtd_atencao = sum(1 for a in alunos_processados if a["faixa_freq"] == "mid")
    qtd_otimos = sum(1 for a in alunos_processados if a["faixa_freq"] == "hi")
    qtd_alto_rend = sum(1 for a in alunos_processados if a["categoria_rendimento"] == "ALTO")

    resumo_geral = {
        "total_alunos": len(alunos_processados),
        "total_aulas_realizadas": aulas_lancadas_qtd,
        "frequencia_media_turma": taxa_presenca_turma,
        "iqr_nota": iqr_nota,
        "pct_alto_rendimento": round((qtd_alto_rend / len(alunos_processados) * 100), 1) if alunos_processados else 0.0,
        "qtd_criticos": qtd_criticos,
        "qtd_atencao": qtd_atencao,
        "qtd_otimos": qtd_otimos,
        "total_presencas": total_presencas,
        "total_faltas": total_faltas,
        "total_justificadas": total_justificadas,
    }

    qualitativo_conceitos = {
        "contagem": contagem_conceitos,
        "percentuais": pct_conceitos,
        "total_presencas": total_presencas,
        "iqr_nota": iqr_nota,
    }

    return {
        "entradas": entradas,
        "entrada_selecionada": entrada_selecionada,
        "resumo_geral": resumo_geral,
        "qualitativo_conceitos": qualitativo_conceitos,
        "evolucao_temporal": evolucao_temporal,
        "alunos_rendimento": alunos_processados,
        "cobertura_pauta": cobertura_pauta,
        "alertas_busca_ativa": alertas_busca_ativa,
        "alunos_destaque": alunos_destaque,
    }


def _resumo_vazio() -> Dict[str, Any]:
    return {
        "total_alunos": 0,
        "total_aulas_realizadas": 0,
        "frequencia_media_turma": 0.0,
        "iqr_nota": 0.0,
        "pct_alto_rendimento": 0.0,
        "qtd_criticos": 0,
        "qtd_atencao": 0,
        "qtd_otimos": 0,
        "total_presencas": 0,
        "total_faltas": 0,
        "total_justificadas": 0,
    }


def _conceitos_vazio() -> Dict[str, Any]:
    return {
        "contagem": {"A": 0, "B": 0, "C": 0, "D": 0},
        "percentuais": {"A": 0.0, "B": 0.0, "C": 0.0, "D": 0.0},
        "total_presencas": 0,
        "iqr_nota": 0.0,
    }


def _cobertura_vazia() -> Dict[str, Any]:
    return {
        "aulas_esperadas": 0,
        "aulas_lancadas": 0,
        "aulas_pendentes": 0,
        "taxa_cumprimento_pauta": 0.0,
        "temas_total": 0,
        "temas_ministrados": 0,
        "temas_cobertura_pct": 0.0,
    }

"app/relatorios/bi_routes.py"

"""Rotas do módulo de Relatórios e BI."""

import inspect

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import Unidade, PeriodoLetivo

from . import bp_relatorios
from .bi import executar_indicador
from .catalogo import (
    DIMENSOES,
    FILTROS_AJUDA,
    FILTROS_CENTRAL,
    FILTROS_PARCIAIS,
    FILTROS_POSSIVEIS,
    GLOSSARIO_GUIA,
    GUIA_METADADOS,
    ROTULOS_FILTROS_GUIA,
    TEXTO_FILTRO_NAO_APLICADO,
    ULTIMA_REVISAO_CATALOGO,
    VERSAO_CATALOGO,
    CODIGOS_OCULTOS_DA_CENTRAL,
    categorias_para_guia,
    dados_ajuda_central,
    indicadores_para_guia,
    indicadores_visiveis_na_central,
    listar_indicadores,
    resolver_codigo,
    sigla_do_codigo,
    titulo_sigla,
)
from .shared import ROLES_RELATORIOS
from app.utils.logica import get_unidade_id


# Papéis com visão global (multiunidade) no BI. Os demais papéis autorizados
# (pedagógico, secretaria) ficam restritos à própria unidade.
_ROLES_GLOBAIS_BI = ("admin", "gerencia")


def _sem_codigos_ocultos(valor):
    """Remove do texto da Central aliases e indicadores indisponíveis.

    O guia mantém o texto integral; a Central continua sem oferecer nem
    mencionar códigos que não estão disponíveis nela.
    """
    if isinstance(valor, str):
        if any(codigo in valor for codigo in CODIGOS_OCULTOS_DA_CENTRAL):
            return None
        return valor
    if isinstance(valor, (list, tuple)):
        limpo = [_sem_codigos_ocultos(item) for item in valor]
        return [item for item in limpo if item is not None]
    if isinstance(valor, dict):
        return {
            chave: limpo
            for chave, item in valor.items()
            if (limpo := _sem_codigos_ocultos(item)) is not None
        }
    return valor


def _metadados_ajuda_central():
    """Metadados de ajuda da Central, lidos somente do catálogo.

    Não há SQL, número ou regra de cálculo aqui: a função apenas transforma
    os textos e a lista de filtros de `catalogo.py` no formato usado pelos
    modais e pelo aviso de filtro não aplicado.
    """
    metadados = {}
    for codigo, indicador in indicadores_visiveis_na_central().items():
        canonico = resolver_codigo(codigo)
        detalhe = GUIA_METADADOS.get(canonico, {})
        respeitados = set(detalhe.get("filtros", ()))
        parciais = FILTROS_PARCIAIS.get(canonico, {})
        ignorados = {}

        filtros = []
        for chave in FILTROS_POSSIVEIS:
            rotulo = ROTULOS_FILTROS_GUIA[chave]
            if chave in parciais:
                # Turno parcialmente aplicado (ALU-009) aparece como "parcial";
                # quando o catálogo já marca o filtro como não aplicável
                # (AUL-006/período), mantém o rótulo de não aplicável e usa o
                # texto específico do catálogo.
                situacao = (
                    "parcial" if chave in respeitados else "nao_aplicavel"
                )
                texto = parciais[chave]
                ignorados[chave] = texto
            elif chave in respeitados:
                situacao = "aplicavel"
                texto = FILTROS_AJUDA.get(chave, "")
            else:
                situacao = "nao_aplicavel"
                texto = TEXTO_FILTRO_NAO_APLICADO.format(rotulo=rotulo)
                ignorados[chave] = texto
            filtros.append(
                {
                    "chave": chave,
                    "rotulo": rotulo,
                    "situacao": situacao,
                    "texto": texto,
                }
            )

        metadados[codigo] = {
            "codigo": codigo,
            "nome": indicador["nome"],
            "sigla": sigla_do_codigo(codigo),
            "titulo_sigla": titulo_sigla(codigo, indicador.get("categoria")),
            "tipo": indicador["tipo"],
            "unidade": indicador["unidade"],
            "fonte": indicador.get("fonte", "—"),
            "mede": detalhe.get("mede", ""),
            "regra": detalhe.get("regra", ""),
            "observacoes": list(detalhe.get("observacoes", ())),
            "relacionados": [
                {"codigo": relacionado, "motivo": motivo}
                for relacionado, motivo in detalhe.get("relacionados", ())
            ],
            "filtros": filtros,
            "ignorados": ignorados,
        }
    return _sem_codigos_ocultos(metadados)


def _escopar_unidade(filtros):
    """Impõe o contexto de unidade a todos os indicadores do BI.

    `admin`/`gerencia` preservam a visão global (ou o contexto de sessão).
    Os demais papéis só enxergam a própria unidade: se pedirem outra unidade,
    a requisição é negada (403); se não pedirem nenhuma (ex.: 'Todas'), o
    escopo é forçado para a unidade efetiva do usuário. Sem unidade
    vinculada, nega-se o acesso em vez de liberar a visão global.
    """
    if current_user.role in _ROLES_GLOBAIS_BI:
        return filtros

    unidade_efetiva = get_unidade_id()
    if unidade_efetiva is None:
        abort(403)

    unidade_solicitada = filtros.get("unidade_id")
    if unidade_solicitada is not None and unidade_solicitada != unidade_efetiva:
        abort(403)

    filtros["unidade_id"] = unidade_efetiva
    return filtros


@bp_relatorios.route("/bi")
@login_required
def bi_dashboard():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    # Organiza os indicadores por categoria para exibição no template.
    # AJ33: a seleção passa a vir do catálogo (aliases e indisponíveis já
    # filtrados), mantendo a ordem/agrupamento histórico da Central.
    categorias = {}
    for codigo, indicador in indicadores_visiveis_na_central().items():
        categoria = indicador["categoria"]
        categorias.setdefault(categoria, []).append((codigo, indicador))

    unidade_query = Unidade.query.filter_by(ativo=True).order_by(Unidade.nome)
    periodo_query = PeriodoLetivo.query.order_by(PeriodoLetivo.nome.desc())
    if current_user.role not in ("admin", "gerencia"):
        unidade_efetiva = get_unidade_id()
        if unidade_efetiva is None:
            unidades = []
            periodos = []
        else:
            unidades = unidade_query.filter(Unidade.id == unidade_efetiva).all()
            periodos = periodo_query.filter(
                PeriodoLetivo.unidade_id == unidade_efetiva
            ).all()
    else:
        unidades = unidade_query.all()
        periodos = periodo_query.all()
    turnos = ["Manhã", "Tarde", "Noite", "EAD", "Outros"]

    return render_template(
        "relatorios/bi.html",
        categorias=categorias,
        unidades=unidades,
        periodos=periodos,
        turnos=turnos,
        ajuda=_sem_codigos_ocultos(dados_ajuda_central()),
        metadados_ajuda=_metadados_ajuda_central(),
        filtros_central=list(FILTROS_CENTRAL),
    )


@bp_relatorios.route("/bi/indicadores")
@login_required
def bi_guia_indicadores():
    """Guia de Indicadores — mesma porta de entrada da Central de BI."""
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    return render_template(
        "relatorios/guia_indicadores.html",
        categorias=categorias_para_guia(),
        glossario=GLOSSARIO_GUIA,
        rotulos_filtros=ROTULOS_FILTROS_GUIA,
        versao_catalogo=VERSAO_CATALOGO,
        ultima_revisao=ULTIMA_REVISAO_CATALOGO,
    )


@bp_relatorios.route("/bi/dados")
@login_required
def bi_api_dados():
    """API JSON: retorna labels/values para o gráfico dinâmico."""

    if current_user.role not in ROLES_RELATORIOS:
        return jsonify({"erro": "Acesso não autorizado."}), 403

    dimensao = request.args.get("dimensao", "faixa_etaria")

    # Mapeamento de dimensão → código de indicador disponível
    DIMENSAO_INDICADOR = {
        "unidade": "ALU-008",
        "sexo": "ALU-005",
        "faixa_etaria": "ALU-006",
        "curso": "ALU-009",
        "turma": "ALU-010",
    }

    codigo = DIMENSAO_INDICADOR.get(dimensao)
    if codigo is None:
        return jsonify({"labels": [], "values": [], "label_eixo": dimensao})

    from .bi import INDICADORES_ALUNOS

    filtros = {}
    unidade_efetiva = get_unidade_id()
    if unidade_efetiva:
        filtros["unidade_id"] = unidade_efetiva

    # ETAPA D3b.4a: curso/turma/professor tambem sao aceitos pela API.
    # `type=int` transforma valor invalido em None (o filtro simplesmente
    # nao e aplicado) — nunca 500.
    for chave in ("curso_id", "turma_id", "professor_id"):
        valor = request.args.get(chave, type=int)
        if valor is not None:
            filtros[chave] = valor

    try:
        # Códigos legados são aliases explícitos: calculam exatamente o mesmo.
        codigo_calculo = resolver_codigo(codigo)
        funcao = INDICADORES_ALUNOS.get(codigo_calculo)
        if funcao and filtros:
            parametros_aceitos = inspect.signature(funcao).parameters
            filtros = {
                k: v for k, v in filtros.items()
                if k in parametros_aceitos or "kwargs" in parametros_aceitos
            }
        resultado = executar_indicador(codigo, **filtros)
    except ValueError:
        return jsonify({"labels": [], "values": [], "label_eixo": dimensao})

    # resultado é lista de dicts {"id", "nome", "valor"} ou escalar
    if isinstance(resultado, list):
        labels = [item["nome"] for item in resultado]
        values = [item["valor"] for item in resultado]
    else:
        labels = [dimensao]
        values = [resultado]

    dim_nome = DIMENSOES.get(dimensao, {}).get("nome", dimensao)
    return jsonify({"labels": labels, "values": values, "label_eixo": dim_nome})


@bp_relatorios.route("/bi/exportar/xlsx")
@login_required
def bi_exportar_xlsx():
    """Exporta o resultado de um indicador como arquivo .xlsx."""
    import io
    import inspect
    from datetime import datetime
    import xlsxwriter

    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    codigo = request.args.get("codigo", "").strip()
    if not codigo:
        return jsonify({"erro": "Parâmetro 'codigo' é obrigatório."}), 400

    filtros = {
        "unidade_id": request.args.get("unidade_id", type=int),
        "periodo_letivo_id": request.args.get("periodo_letivo_id", type=int),
        "turno": request.args.get("turno", type=str) or None,
        # ETAPA D3b.4a: curso/turma/professor pela OFERTA; `type=int` devolve
        # None em valor invalido (filtro ignorado) — nunca 500.
        "curso_id": request.args.get("curso_id", type=int),
        "turma_id": request.args.get("turma_id", type=int),
        "professor_id": request.args.get("professor_id", type=int),
    }
    filtros = _escopar_unidade(filtros)
    filtros_limpos = {k: v for k, v in filtros.items() if v is not None}

    try:
        from .bi import INDICADORES_ALUNOS

        codigo_calculo = resolver_codigo(codigo)
        funcao = INDICADORES_ALUNOS.get(codigo_calculo)
        if funcao is None:
            return jsonify({"erro": f"Indicador '{codigo}' não implementado."}), 404

        parametros_aceitos = inspect.signature(funcao).parameters
        filtros_permitidos = {
            k: v
            for k, v in filtros_limpos.items()
            if k in parametros_aceitos or "kwargs" in parametros_aceitos
        }

        resultado = executar_indicador(codigo, **filtros_permitidos)
    except ValueError:
        return jsonify({"erro": "Os parâmetros informados para o indicador são inválidos."}), 400

    indicador = listar_indicadores().get(codigo, {})
    nome_indicador = indicador.get("nome", codigo)
    unidade_medicao = indicador.get("unidade", "")

    # ------------------------------------------------------------------ #
    # Gera o workbook em memória                                           #
    # ------------------------------------------------------------------ #
    output = io.BytesIO()
    workbook = xlsxwriter.Workbook(output, {"in_memory": True})
    worksheet = workbook.add_worksheet("Resultado")

    # Formatos
    fmt_titulo = workbook.add_format({
        "bold": True, "font_size": 14,
        "font_color": "#1a1a2e", "bottom": 1, "bottom_color": "#4361ee",
    })
    fmt_subtitulo = workbook.add_format({
        "italic": True, "font_color": "#6c757d", "font_size": 10,
    })
    fmt_header = workbook.add_format({
        "bold": True, "bg_color": "#4361ee", "font_color": "#ffffff",
        "border": 1, "border_color": "#3a0ca3",
        "align": "center", "valign": "vcenter",
    })
    # fmt_valor/fmt_item nunca foram aplicados a nenhuma célula; as chamadas
    # permanecem para registrar os formatos no workbook exatamente como antes
    # (D3b.1 — limpeza sem mudança de comportamento).
    workbook.add_format({
        "num_format": "#,##0.##", "align": "right",
    })
    workbook.add_format({"align": "left"})
    fmt_numero_grande = workbook.add_format({
        "bold": True, "font_size": 28, "font_color": "#4361ee",
        "align": "center", "valign": "vcenter",
    })
    fmt_rodape = workbook.add_format({
        "italic": True, "font_color": "#adb5bd", "font_size": 9,
    })

    # Cabeçalho do relatório
    worksheet.merge_range("A1:C1", f"Indicador: {nome_indicador}", fmt_titulo)
    worksheet.write("A2", f"Código: {codigo}  |  Unidade: {unidade_medicao}", fmt_subtitulo)
    worksheet.write("A3", f"Gerado em: {datetime.now().strftime('%d/%m/%Y %H:%M')}", fmt_subtitulo)
    worksheet.set_row(0, 22)
    worksheet.set_column("A:A", 40)
    worksheet.set_column("B:B", 20)

    # Dados
    if resultado is None:
        worksheet.write("A5", "Sem resultados para os filtros selecionados.", fmt_subtitulo)
    elif isinstance(resultado, (int, float)):
        worksheet.merge_range("A5:C6", resultado, fmt_numero_grande)
        worksheet.set_row(4, 60)
    elif isinstance(resultado, list) and resultado:
        # Cabeçalho da tabela
        worksheet.write(4, 0, "Item / Dimensão", fmt_header)
        worksheet.write(4, 1, f"Valor ({unidade_medicao})" if unidade_medicao else "Valor", fmt_header)
        worksheet.set_row(4, 20)
        # Linhas de dados
        for row_idx, item in enumerate(resultado, start=5):
            fmt_linha = workbook.add_format({
                "bg_color": "#f0f4ff" if row_idx % 2 == 0 else "#ffffff",
                "border": 1, "border_color": "#dee2e6",
            })
            fmt_valor_linha = workbook.add_format({
                "num_format": "#,##0.##", "align": "right",
                "bg_color": "#f0f4ff" if row_idx % 2 == 0 else "#ffffff",
                "border": 1, "border_color": "#dee2e6",
            })
            from app.utils.xlsx import sanitizar_valor_xlsx

            worksheet.write(row_idx, 0, sanitizar_valor_xlsx(item.get("nome") or item.get("id") or "—"), fmt_linha)
            valor = item.get("valor")
            if isinstance(valor, (int, float)):
                worksheet.write_number(row_idx, 1, valor, fmt_valor_linha)
            else:
                from app.utils.xlsx import sanitizar_valor_xlsx
                worksheet.write(row_idx, 1, sanitizar_valor_xlsx(valor if valor is not None else "—"), fmt_linha)
        # Rodapé
        rodape_row = len(resultado) + 6
        worksheet.write(rodape_row, 0, f"Total de registros: {len(resultado)}", fmt_rodape)
    else:
        worksheet.write("A5", "Sem resultados.", fmt_subtitulo)

    # Rodapé da planilha
    worksheet.set_footer(f"&L&9pautaON  &C{nome_indicador}&R&9Página &P de &N")

    workbook.close()
    output.seek(0)

    from flask import send_file

    nome_arquivo = f"pautaON_{codigo}_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=nome_arquivo,
    )


@bp_relatorios.route("/bi/indicador/<codigo>")
@login_required
def bi_indicador(codigo):
    """Executa um indicador do BI."""

    if current_user.role not in ROLES_RELATORIOS:
        return jsonify({"erro": "Acesso não autorizado."}), 403

    filtros = {
        "unidade_id": request.args.get("unidade_id", type=int),
        "periodo_letivo_id": request.args.get("periodo_letivo_id", type=int),
        "turno": request.args.get("turno", type=str),
        # ETAPA D3b.4a: curso/turma/professor pela OFERTA; `type=int` devolve
        # None em valor invalido (filtro ignorado pela limpeza abaixo) —
        # nunca 500.
        "curso_id": request.args.get("curso_id", type=int),
        "turma_id": request.args.get("turma_id", type=int),
        "professor_id": request.args.get("professor_id", type=int),
    }
    filtros = _escopar_unidade(filtros)

    filtros_limpos = {k: v for k, v in filtros.items() if v}

    try:
        from .bi import INDICADORES_ALUNOS

        codigo_calculo = resolver_codigo(codigo)
        funcao = INDICADORES_ALUNOS.get(codigo_calculo)

        if funcao:
            parametros_aceitos = inspect.signature(funcao).parameters
            # Filtra entregando só o que a função entende
            filtros_permitidos = {
                k: v
                for k, v in filtros_limpos.items()
                if k in parametros_aceitos or "kwargs" in parametros_aceitos
            }
        else:
            filtros_permitidos = filtros_limpos

        # Executa com os filtros sanitizados
        resultado = executar_indicador(codigo, **filtros_permitidos)

    except ValueError:
        return jsonify({"erro": "Os parâmetros informados para o indicador são inválidos."}), 400

    indicador = listar_indicadores().get(codigo)

    return jsonify(
        {
            "indicador": codigo,
            "nome": indicador["nome"],
            "tipo": indicador["tipo"],
            "unidade": indicador["unidade"],
            "fonte": indicador.get("fonte", "—"),
            "resultado": resultado,
        }
    )

"app/relatorios/bi_routes.py"

"""Rotas do módulo de Relatórios e BI."""

import inspect

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from app.models import Unidade, PeriodoLetivo

from . import bp_relatorios
from .bi import INDICADORES_STATUS_ALUNO, executar_indicador
from .catalogo import DIMENSOES, listar_indicadores
from .shared import ROLES_RELATORIOS
from app.utils.logica import get_unidade_id


def _escopar_unidade_status(codigo, filtros):
    if codigo not in INDICADORES_STATUS_ALUNO:
        return filtros

    if current_user.role in ("admin", "gerencia"):
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
    indicadores = listar_indicadores()

    categorias = {}
    for codigo, indicador in indicadores.items():
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

    try:
        funcao = INDICADORES_ALUNOS.get(codigo)
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
    }
    filtros = _escopar_unidade_status(codigo, filtros)
    filtros_limpos = {k: v for k, v in filtros.items() if v is not None}

    try:
        from .bi import INDICADORES_ALUNOS

        funcao = INDICADORES_ALUNOS.get(codigo)
        if funcao is None:
            return jsonify({"erro": f"Indicador '{codigo}' não implementado."}), 404

        parametros_aceitos = inspect.signature(funcao).parameters
        filtros_permitidos = {
            k: v
            for k, v in filtros_limpos.items()
            if k in parametros_aceitos or "kwargs" in parametros_aceitos
        }

        resultado = executar_indicador(codigo, **filtros_permitidos)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400

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
    fmt_valor = workbook.add_format({
        "num_format": "#,##0.##", "align": "right",
    })
    fmt_item = workbook.add_format({"align": "left"})
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
            worksheet.write(row_idx, 0, item.get("nome") or item.get("id") or "—", fmt_linha)
            valor = item.get("valor")
            if isinstance(valor, (int, float)):
                worksheet.write_number(row_idx, 1, valor, fmt_valor_linha)
            else:
                worksheet.write(row_idx, 1, valor if valor is not None else "—", fmt_linha)
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
    }
    filtros = _escopar_unidade_status(codigo, filtros)

    filtros_limpos = {k: v for k, v in filtros.items() if v}

    try:
        from .bi import INDICADORES_ALUNOS

        funcao = INDICADORES_ALUNOS.get(codigo)

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

    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400

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

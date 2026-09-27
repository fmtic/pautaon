"app/relatorios/bi_routes.py"

"""Rotas do módulo de Relatórios e BI."""

from flask import abort, jsonify, render_template, request
from flask_login import current_user, login_required

from . import bp_relatorios
from .bi import executar_indicador
from .catalogo import DIMENSOES, listar_indicadores
from .shared import ROLES_RELATORIOS


@bp_relatorios.route("/bi")
@login_required
def bi_dashboard():
    """Renderiza a Central de BI com o catálogo de dimensões."""

    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    # Converte o dicionário de dimensões em lista de tuplas (chave, nome)
    # para uso no template Jinja2.
    dimensoes = [(chave, dim["nome"]) for chave, dim in DIMENSOES.items()]

    return render_template("relatorios/bi.html", dimensoes=dimensoes)


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

    try:
        resultado = executar_indicador(codigo)
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


@bp_relatorios.route("/bi/exportar")
@login_required
def bi_exportar():
    """Exportação Excel — placeholder para implementação futura."""

    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    # TODO: gerar workbook com openpyxl e retornar arquivo .xlsx
    return jsonify({"aviso": "Exportação ainda não implementada."}), 501


@bp_relatorios.route("/bi/indicador/<codigo>")
@login_required
def bi_indicador(codigo):
    """Executa um indicador do BI."""

    if current_user.role not in ROLES_RELATORIOS:
        return jsonify({"erro": "Acesso não autorizado."}), 403

    try:
        resultado = executar_indicador(codigo)
    except ValueError as exc:
        return jsonify({"erro": str(exc)}), 400

    indicador = listar_indicadores().get(codigo)

    return jsonify(
        {
            "indicador": codigo,
            "nome": indicador["nome"],
            "tipo": indicador["tipo"],
            "unidade": indicador["unidade"],
            "resultado": resultado,
        }
    )

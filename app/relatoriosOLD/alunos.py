"""Listagem filtrável de alunos para relatórios e sua exportação em Excel.

ONDA 3B
    Leitura de PCD e acompanhante migrada para tabela/coluna novas
    (`PerfilDiversidade.saude_laudo` e `Aluno.acompanhante_aulas`),
    com fallback para os JSONs antigos.
"""

from datetime import date, datetime
from io import BytesIO

import pandas as pd
from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_login import current_user, login_required

from app.models import Aluno, PeriodoLetivo
from app.utils.logica import get_unidade_id

from . import bp_relatorios
from .shared import ROLES_RELATORIOS, aplicar_filtros_alunos, ler_filtros_alunos


COLUMN_LABELS = {
    "data_matricula": "Data da Matrícula",
    "nome": "Nome Completo",
    "nome_social": "Nome Social",
    "data_nascimento": "Data Nascimento",
    "idade": "Idade",
    "nivel": "Nível",
    "pcd": "PCD",
    "acompanhante_aulas": "Acompanhante para as aulas",
    "turmas_aluno": "Turmas",
}

COLUMN_OPTIONS = [
    {"key": "data_matricula", "label": "Data da Matrícula"},
    {"key": "nome", "label": "Nome Completo"},
    {"key": "nome_social", "label": "Nome Social"},
    {"key": "data_nascimento", "label": "Data Nascimento"},
    {"key": "idade", "label": "Idade"},
    {"key": "nivel", "label": "Nível"},
    {"key": "pcd", "label": "PCD"},
    {"key": "acompanhante_aulas", "label": "Acompanhante para as aulas"},
    {"key": "turmas_aluno", "label": "Turmas Vinculadas"},
]


# =============================================================================
# HELPERS DE LEITURA (Onda 3B — com fallback JSON)
# =============================================================================


def _calcular_idade(aluno):
    if hasattr(aluno, "idade"):
        return aluno.idade
    return (
        datetime.now().year - aluno.data_nascimento.year
        if aluno.data_nascimento
        else "-"
    )


def _is_pcd(aluno) -> bool:
    """
    True se o aluno possui laudo de saúde (PCD).

    Prefere `PerfilDiversidade.saude_laudo` (Onda 3A); cai no JSON legado
    se ainda não houver registro migrado.
    """
    if aluno.perfil_diversidade is not None:
        return bool(aluno.perfil_diversidade.saude_laudo)
    return bool((aluno.diversidade_json or {}).get("saude_laudo", False))


def _acompanhante(aluno) -> str:
    """
    Nome do acompanhante para as aulas.

    Prefere a coluna `Aluno.acompanhante_aulas` (Onda 3A); cai no JSON
    legado se a coluna estiver vazia.
    """
    valor = aluno.acompanhante_aulas
    if valor:
        return valor
    return (aluno.identificacao_json or {}).get("acompanhante_aulas") or "-"


# =============================================================================
# LISTAGEM
# =============================================================================


@bp_relatorios.route("/alunos")
@login_required
def relatorio_alunos():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    selected_cols = request.args.getlist("colunas")
    gerar = request.args.get("gerar") == "1"
    page = request.args.get("page", 1, type=int)
    per_page = 20

    filtros = ler_filtros_alunos(request.args)
    periodo_id = filtros["periodo_letivo_id"]

    if not selected_cols and not gerar:
        selected_cols = ["nome", "idade", "turmas_aluno"]
    elif not selected_cols:
        selected_cols = []

    u_id = get_unidade_id()
    periodos_query = PeriodoLetivo.query
    if u_id:
        periodos_query = periodos_query.filter_by(unidade_id=u_id)
    periodos = periodos_query.order_by(PeriodoLetivo.nome).all()

    alunos = []
    pagination = None
    total = 0

    if gerar:
        query = Aluno.query.filter_by(ativo=True)
        if u_id:
            query = query.filter_by(unidade_id=u_id)

        query = aplicar_filtros_alunos(query, filtros)
        query = query.order_by(Aluno.id.asc())
        pagination = query.paginate(page=page, per_page=per_page, error_out=False)
        alunos_lista = pagination.items
        total = pagination.total

        alunos_data = []
        for a in alunos_lista:
            d = {
                "id": a.id,
                "nome": a.nome,
                "nome_social": a.nome_social or "-",
                "data_nascimento": (
                    a.data_nascimento.strftime("%d/%m/%Y") if a.data_nascimento else "-"
                ),
                "idade": _calcular_idade(a),
                "nivel": a.nivel or "-",
                "pcd": _is_pcd(a),
                "acompanhante_aulas": _acompanhante(a),
                "turmas_aluno": True,
            }
            turmas_vinculadas = a.turmas[:3] if hasattr(a, "turmas") else []
            for i in range(1, 4):
                d[f"turma_{i}"] = (
                    turmas_vinculadas[i - 1].nome
                    if len(turmas_vinculadas) >= i
                    else "-"
                )
            alunos_data.append(d)
        alunos = alunos_data

    url_args = dict(request.args)
    url_args.pop("page", None)

    return render_template(
        "relatorios/relatorio_alunos.html",
        periodos=periodos,
        selected_periodo_id=periodo_id,
        column_options=COLUMN_OPTIONS,
        selected_cols=selected_cols,
        alunos=alunos,
        pagination=pagination,
        total=total,
        gerar=gerar,
        request=request,
    )


# =============================================================================
# EXPORTAÇÃO
# =============================================================================


@bp_relatorios.route("/relatorio_alunos/exportar")
@login_required
def exportar_relatorio_alunos():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    selected_cols = request.args.getlist("colunas")
    if not selected_cols:
        flash("Selecione ao menos um dado para exportação.", "warning")
        return redirect(url_for("relatorios.relatorio_alunos"))

    filtros = ler_filtros_alunos(request.args)

    u_id = get_unidade_id()
    query = Aluno.query.filter_by(ativo=True)
    if u_id:
        query = query.filter_by(unidade_id=u_id)
    query = aplicar_filtros_alunos(query, filtros)

    alunos_lista = query.distinct().order_by(Aluno.nome.asc()).all()

    data_to_df = []
    for a in alunos_lista:
        row = {}
        for col in selected_cols:
            if col == "turmas_aluno":
                row[COLUMN_LABELS[col]] = ", ".join([t.nome for t in a.turmas])
            elif col == "idade":
                row[COLUMN_LABELS[col]] = _calcular_idade(a)
            elif col == "data_matricula":
                row[COLUMN_LABELS[col]] = (
                    a.created_at.strftime("%d/%m/%Y %H:%M")
                    if a.created_at else "-"
                )
            elif col == "pcd":
                row[COLUMN_LABELS[col]] = "Sim" if _is_pcd(a) else "Não"
            elif col == "acompanhante_aulas":
                row[COLUMN_LABELS[col]] = _acompanhante(a)
            elif col == "data_nascimento":
                row[COLUMN_LABELS[col]] = (
                    a.data_nascimento.strftime("%d/%m/%Y") if a.data_nascimento else "-"
                )
            else:
                row[COLUMN_LABELS[col]] = getattr(a, col, "-")
        data_to_df.append(row)

    df = pd.DataFrame(data_to_df)
    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Lista de Alunos", index=False)
    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Alunos_PautaON_{date.today()}.xlsx",
    )

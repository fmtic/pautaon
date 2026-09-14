"""Relatório geral (visão consolidada) e sua exportação em Excel."""

from datetime import date
from io import BytesIO

import pandas as pd
from flask import abort, flash, redirect, render_template, send_file, url_for
from flask_login import current_user, login_required

from app.models import Aluno, Turma, User
from app.utils.logica import (
    calcular_estatisticas_idade,
    calcular_frequencias_relatorio,
    calcular_metricas_conselho,
    get_unidade_id,
)

from . import bp_relatorios
from .shared import ROLES_RELATORIOS


@bp_relatorios.route("/")
@login_required
def relatorio_geral():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    try:
        unidade_id = get_unidade_id()
        turmas_query = Turma.query.filter_by(ativo=True)
        if unidade_id:
            turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
        todas_as_turmas = turmas_query.all()

        estatisticas_idade = calcular_estatisticas_idade(unidade_id=unidade_id)
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(
            todas_as_turmas, unidade_id=unidade_id
        )
        metricas = calcular_metricas_conselho(unidade_id=unidade_id)

        total_alunos_query = Aluno.query.filter_by(ativo=True)
        total_professores_query = User.query.filter_by(role="professor")
        if unidade_id:
            total_alunos_query = total_alunos_query.filter_by(unidade_id=unidade_id)
            total_professores_query = total_professores_query.filter_by(unidade_id=unidade_id)

        total_masculino = total_feminino = total_outro = 0
        MASC = {"masculino", "homem", "masc", "m"}
        FEM = {"feminino", "mulher", "fem", "f"}
        for aluno in total_alunos_query.all():
            genero = (aluno.diversidade_json.get("genero") or "").strip().lower()
            if genero in MASC:
                total_masculino += 1
            elif genero in FEM:
                total_feminino += 1
            elif genero:
                total_outro += 1

        return render_template(
            "relatorios/geral.html",
            total_alunos=total_alunos_query.count(),
            total_professores=total_professores_query.count(),
            total_turmas=len(todas_as_turmas),
            p_presenca=p_geral,
            media_geral=estatisticas_idade.get("media_geral"),
            media_programa=estatisticas_idade.get("media_programa"),
            media_turma=estatisticas_idade.get("media_turma"),
            conselho=metricas,
            freq_programa=f_prog,
            freq_turma=f_turma,
            freq_professor=f_prof,
            todas_as_turmas=todas_as_turmas,
            total_masculino=total_masculino,
            total_feminino=total_feminino,
            total_outro=total_outro,
        )
    except Exception as e:
        from app.utils.errors import flash_and_log
        flash_and_log(e, location='relatorios.relatorio_geral')
        return redirect(url_for("main.dashboard"))


@bp_relatorios.route("/exportar")
@login_required
def exportar_relatorio():
    if current_user.role not in ROLES_RELATORIOS:
        abort(403)

    try:
        unidade_id = get_unidade_id()
        turmas_query = Turma.query.filter_by(ativo=True)
        if unidade_id:
            turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
        todas_as_turmas = turmas_query.all()
        estatisticas_idade = calcular_estatisticas_idade(unidade_id=unidade_id)
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(
            todas_as_turmas, unidade_id=unidade_id
        )
        df_idade_prog = pd.DataFrame(
            list(estatisticas_idade["media_programa"].items()),
            columns=["Programa", "Média de Idade"],
        )
        df_idade_turma = pd.DataFrame(
            list(estatisticas_idade["media_turma"].items()),
            columns=["Turma", "Média de Idade"],
        )

        df_freq_prog = pd.DataFrame(list(f_prog.items()), columns=["Programa", "% Presença"])
        df_freq_prof = pd.DataFrame(list(f_prof.items()), columns=["Professor", "% Presença"])
        df_freq_turma = pd.DataFrame(list(f_turma.items()), columns=["Turma", "% Presença"])

        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_idade_prog.to_excel(writer, sheet_name="Idade por Programa", index=False)
            df_idade_turma.to_excel(writer, sheet_name="Idade por Turma", index=False)
            df_freq_prog.to_excel(writer, sheet_name="Freq por Programa", index=False)
            df_freq_prof.to_excel(writer, sheet_name="Freq por Professor", index=False)
            df_freq_turma.to_excel(writer, sheet_name="Freq por Turma", index=False)

        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"Relatorio_PautaON_{date.today()}.xlsx",
        )
    except Exception:
        flash("Falha ao exportar o relatório Excel devido a um erro algorítmico interno.", "danger")
        return redirect(url_for("relatorios.relatorio_geral"))

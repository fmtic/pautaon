from collections import defaultdict
from datetime import date, datetime

from flask import abort, current_app, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.database import db
from app.models import Aluno, DiaBloqueado, DiaBloqueadoTurma, Inscricao, PeriodoLetivo, Turma, Unidade
from app.services.auth_service import register_security_log
from app.utils.logica import get_unidade_id
from . import bp

_ROLES_CALENDARIO = ["admin", "pedagogico", "secretaria"]


def _check_calendario_access(unidade_id):
    """Verifica se o usuário tem permissão para gerenciar o calendário."""
    if current_user.role not in _ROLES_CALENDARIO:
        abort(403)
    if current_user.role != "admin" and unidade_id:
        if current_user.unidade_id and current_user.unidade_id != unidade_id:
            abort(403)


@bp.route("/planejamento/calendario/<int:periodo_id>")
@login_required
def calendario_dias(periodo_id):
    """Retorna JSON dos dias bloqueados de um período letivo."""
    unidade_id = get_unidade_id()
    _check_calendario_access(unidade_id)

    periodo = PeriodoLetivo.query.get_or_404(periodo_id)
    if unidade_id and periodo.unidade_id != unidade_id:
        abort(403)

    dias = DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id).all()
    return jsonify(
        [
            {
                "id": item.id,
                "data": item.data.strftime("%Y-%m-%d"),
                "tipo": item.tipo,
                "descricao": item.descricao or "",
            }
            for item in dias
        ]
    )


@bp.route("/planejamento/calendario/salvar", methods=["POST"])
@login_required
def calendario_salvar():
    """Faz upsert em lote de dias bloqueados para um período letivo."""
    unidade_id = get_unidade_id()
    _check_calendario_access(unidade_id)

    payload = request.get_json(silent=True)
    if not payload:
        return jsonify({"success": False, "message": "Payload JSON inválido ou ausente"}), 400

    periodo_id = payload.get("periodo_id")
    novos_dias = payload.get("dias", [])
    if not periodo_id:
        return jsonify({"success": False, "message": "ID do período é obrigatório"}), 400

    periodo = PeriodoLetivo.query.get(periodo_id)
    if not periodo:
        return jsonify({"success": False, "message": "Período não encontrado"}), 404

    if unidade_id and periodo.unidade_id != unidade_id:
        return jsonify({"success": False, "message": "Acesso negado a esta unidade"}), 403

    excecoes_payload = payload.get("excecoes", {})

    try:
        DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id).delete()

        turma_ids = [t.id for t in Turma.query.filter_by(periodo_letivo_id=periodo_id).all()]
        if turma_ids:
            DiaBloqueadoTurma.query.filter(DiaBloqueadoTurma.turma_id.in_(turma_ids)).delete(synchronize_session=False)

        bloqueios_adicionados = 0
        for item in novos_dias:
            data_str = item.get("data")
            tipo = item.get("tipo")
            descricao = item.get("descricao", "") or ""

            if not data_str or not tipo:
                continue

            try:
                data_obj = datetime.strptime(data_str, "%Y-%m-%d").date()
            except ValueError:
                continue

            db.session.add(
                DiaBloqueado(
                    data=data_obj,
                    tipo=tipo,
                    descricao=descricao,
                    periodo_letivo_id=periodo_id,
                    unidade_id=periodo.unidade_id,
                    criado_por_id=current_user.id,
                )
            )
            bloqueios_adicionados += 1

        excecoes_adicionadas = 0
        for data_str, turma_list in excecoes_payload.items():
            if not data_str or not isinstance(turma_list, list):
                continue
            try:
                datetime.strptime(data_str, "%Y-%m-%d")
            except ValueError:
                continue

            for turma_id in turma_list:
                try:
                    turma_id_int = int(turma_id)
                except (TypeError, ValueError):
                    continue

                turma_obj = Turma.query.get(turma_id_int)
                if not turma_obj or turma_obj.periodo_letivo_id != periodo_id:
                    continue

                db.session.add(
                    DiaBloqueadoTurma(
                        turma_id=turma_obj.id,
                        data=data_str,
                        unidade_id=periodo.unidade_id,
                        criado_por_id=current_user.id,
                    )
                )
                excecoes_adicionadas += 1

        db.session.commit()
        return jsonify(
            {
                "success": True,
                "message": f"{bloqueios_adicionados} dias atualizados e {excecoes_adicionadas} exceções salvas.",
            }
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao salvar calendário de dias bloqueados.")
        return jsonify({"success": False, "message": "Erro interno ao salvar calendário."}), 500


@bp.route("/planejamento/calendario/remover/<int:dia_id>", methods=["POST"])
@login_required
def calendario_remover(dia_id):
    """Remove um único dia bloqueado."""
    unidade_id = get_unidade_id()
    _check_calendario_access(unidade_id)

    dia = DiaBloqueado.query.get_or_404(dia_id)
    if unidade_id and dia.unidade_id != unidade_id:
        abort(403)

    try:
        db.session.delete(dia)
        db.session.commit()
        return jsonify({"success": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Erro ao remover dia bloqueado.")
        return jsonify({"success": False, "message": "Erro interno ao remover dia bloqueado."}), 500


@bp.route("/planejamento/calendario/<int:periodo_id>/exportar")
@login_required
def calendario_exportar(periodo_id):
    """Renderiza a view de impressão do calendário de dias bloqueados."""
    unidade_id = get_unidade_id()
    _check_calendario_access(unidade_id)

    periodo = PeriodoLetivo.query.get_or_404(periodo_id)
    if unidade_id and periodo.unidade_id != unidade_id:
        abort(403)

    dias = (
        DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id)
        .order_by(DiaBloqueado.data)
        .all()
    )

    return render_template("planejamento/calendario_bloqueados_print.html", periodo=periodo, dias=dias)


@bp.route("/periodo-letivo")
@login_required
def periodo_letivo():
    """Lista os períodos letivos da unidade atual ou visão global."""
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    unidade_id = get_unidade_id()
    query = PeriodoLetivo.query
    if unidade_id:
        query = query.filter_by(unidade_id=unidade_id)

    todos = query.order_by(PeriodoLetivo.data_inicio.desc()).all()
    anos_disponiveis = sorted({periodo.data_inicio.year for periodo in todos}, reverse=True)

    ano_atual = date.today().year
    ano_filtro = request.args.get(
        "ano",
        type=int,
        default=(
            ano_atual
            if ano_atual in anos_disponiveis
            else (anos_disponiveis[0] if anos_disponiveis else ano_atual)
        ),
    )
    periodos = [periodo for periodo in todos if periodo.data_inicio.year == ano_filtro]

    return render_template(
        "periodos/lista.html",
        periodos=periodos,
        anos=anos_disponiveis,
        ano_filtro=ano_filtro,
    )


@bp.route("/periodo-letivo/novo", methods=["GET", "POST"])
@login_required
def periodo_letivo_novo():
    """Cria um novo período letivo associado à unidade do contexto atual."""
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    unidade_id = get_unidade_id()
    if not unidade_id:
        flash("Selecione uma unidade específica para cadastrar um novo período letivo.", "warning")
        return redirect(url_for("registros.periodo_letivo"))

    unidade = current_user.unidade if current_user.unidade_id == unidade_id else db.session.get(
        Unidade, unidade_id
    )

    if request.method == "POST":
        try:
            nome = request.form.get("nome")
            data_inicio = datetime.strptime(request.form.get("data_inicio"), "%Y-%m-%d").date()
            data_fim = datetime.strptime(request.form.get("data_fim"), "%Y-%m-%d").date()
            centro_custo = ", ".join(request.form.getlist("centro_custo"))
            estimativa = int(request.form.get("estimativa_alunos", 0))

            novo = PeriodoLetivo(
                nome=nome,
                data_inicio=data_inicio,
                data_fim=data_fim,
                unidade_id=unidade_id,
                centro_custo=centro_custo,
                estimativa_alunos=estimativa,
                ativo=True,
            )
            db.session.add(novo)
            db.session.commit()

            unidade_nome = unidade.nome if unidade else str(unidade_id)
            register_security_log(
                "Cadastro Período Letivo",
                f"Criado período {nome} para unidade {unidade_nome}",
            )
            flash(f"Período letivo '{nome}' cadastrado com sucesso!", "success")
            return redirect(url_for("registros.periodo_letivo_calendario", id=novo.id))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao cadastrar período letivo.")
            flash("Erro ao cadastrar período letivo.", "danger")

    return render_template("periodos/form.html", periodo=None, unidade=unidade)


@bp.route("/periodo-letivo/editar/<int:id>", methods=["GET", "POST"])
@login_required
def periodo_letivo_editar(id):
    """Edita os dados de um período letivo existente."""
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    periodo = db.get_or_404(PeriodoLetivo, id)
    unidade = periodo.unidade

    if request.method == "POST":
        try:
            periodo.nome = request.form.get("nome")
            periodo.data_inicio = datetime.strptime(request.form.get("data_inicio"), "%Y-%m-%d").date()
            periodo.data_fim = datetime.strptime(request.form.get("data_fim"), "%Y-%m-%d").date()
            periodo.centro_custo = ", ".join(request.form.getlist("centro_custo"))
            periodo.estimativa_alunos = int(request.form.get("estimativa_alunos", 0))
            db.session.commit()
            flash(f"Período letivo '{periodo.nome}' atualizado!", "success")
            return redirect(url_for("registros.periodo_letivo"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao editar período letivo.")
            flash("Erro ao salvar alterações no período.", "danger")

    return render_template("periodos/form.html", periodo=periodo, unidade=unidade)


@bp.route("/periodo-letivo/inativar/<int:id>")
@login_required
def periodo_letivo_inativar(id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    periodo = db.get_or_404(PeriodoLetivo, id)
    periodo.ativo = False
    db.session.commit()
    flash(f"Período '{periodo.nome}' inativado.", "info")
    return redirect(url_for("registros.periodo_letivo"))


@bp.route("/periodo-letivo/ativar/<int:id>")
@login_required
def periodo_letivo_ativar(id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    periodo = db.get_or_404(PeriodoLetivo, id)
    periodo.ativo = True
    db.session.commit()
    flash(f"Período '{periodo.nome}' reativado.", "success")
    return redirect(url_for("registros.periodo_letivo"))


@bp.route("/periodo-letivo/<int:id>/calendario", methods=["GET"])
@login_required
def periodo_letivo_calendario(id):
    """Página dedicada ao calendário de dias bloqueados de um período letivo."""
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    unidade_id = get_unidade_id()
    periodo = db.get_or_404(PeriodoLetivo, id)
    if unidade_id and periodo.unidade_id != unidade_id:
        abort(403)

    dias = DiaBloqueado.query.filter_by(periodo_letivo_id=id).order_by(DiaBloqueado.data).all()
    dias_json = [
        {"data": item.data.strftime("%Y-%m-%d"), "tipo": item.tipo, "descricao": item.descricao or ""}
        for item in dias
    ]

    turmas = (
        Turma.query.filter_by(periodo_letivo_id=id, ativo=True)
        .order_by(Turma.nome)
        .all()
    )
    turmas_json = [{"id": t.id, "nome": t.nome} for t in turmas]
    excecoes = (
        DiaBloqueadoTurma.query.join(Turma)
        .filter(Turma.periodo_letivo_id == id)
        .all()
    )
    excecoes_json = {}
    for item in excecoes:
        excecoes_json.setdefault(item.data, []).append(item.turma_id)

    return render_template(
        "periodos/calendario.html",
        periodo=periodo,
        dias_json=dias_json,
        turmas_json=turmas_json,
        excecoes_json=excecoes_json,
    )


@bp.route("/periodo-letivo/relatorio/<int:id>")
@login_required
def periodo_letivo_relatorio_certificado(id):
    """Gera lista de alunos aprovados ou participantes para certificados."""
    from app.models import ConselhoClasse

    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    periodo = db.get_or_404(PeriodoLetivo, id)
    turmas = Turma.query.filter_by(periodo_letivo_id=id, ativo=True).all()
    alunos_map = defaultdict(lambda: {"aluno": None, "cursos": []})
    situacoes_aprovadas = {"Aprovado", "Participação", "Concluído"}

    for turma in turmas:
        alunos_turma = (
            Aluno.query.join(Inscricao)
            .filter(Inscricao.turma_id == turma.id, Inscricao.ativo == True, Aluno.ativo == True)
            .order_by(Aluno.nome)
            .all()
        )

        for aluno in alunos_turma:
            conselho = ConselhoClasse.query.filter_by(
                turma_id=turma.id,
                aluno_id=aluno.id,
                etapa="FINAL",
            ).first()
            situacao = conselho.situacao_final if conselho else None
            aprovado = situacao in situacoes_aprovadas if situacao else False
            inscricao = Inscricao.query.filter_by(aluno_id=aluno.id, turma_id=turma.id).first()
            nivel_turma = inscricao.nivel if inscricao and inscricao.nivel else None

            alunos_map[aluno.id]["aluno"] = aluno
            alunos_map[aluno.id]["cursos"].append(
                {
                    "turma": turma,
                    "curso": turma.curso,
                    "nivel": nivel_turma,
                    "situacao": situacao or "—",
                    "aprovado": aprovado,
                    "concluido": turma.conselho_concluido,
                }
            )

    dados = sorted(alunos_map.values(), key=lambda item: item["aluno"].nome)
    return render_template("periodos/certificado.html", periodo=periodo, dados=dados)

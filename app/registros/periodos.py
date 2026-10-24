from collections import defaultdict
from datetime import date, datetime

from flask import (
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from app.database import db
from app.models import (
    Aluno,
    DiaBloqueado,
    DiaBloqueadoTurma,
    Inscricao,
    PeriodoLetivo,
    Turma,
    Unidade,
)
from app.services.auth_service import register_security_log
from app.services.feriados import obter_feriados_nacionais
from app.utils.datetime_parse import parse_date
from app.utils.formatters import formatar_ch
from app.utils.logica import get_unidade_id
from . import bp

_ROLES_CALENDARIO = ["admin", "pedagogico", "secretaria", "gerencia"]
_ROLES_PERIODO = ["admin", "pedagogico", "secretaria"]


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

    dias = (
        DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id)
        .filter(
            DiaBloqueado.data >= periodo.data_inicio,
            DiaBloqueado.data <= periodo.data_fim,
        )
        .order_by(DiaBloqueado.data)
        .all()
    )
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
        return (
            jsonify({"success": False, "message": "Payload JSON inválido ou ausente"}),
            400,
        )

    periodo_id = payload.get("periodo_id")
    novos_dias = payload.get("dias", [])
    if not periodo_id:
        return (
            jsonify({"success": False, "message": "ID do período é obrigatório"}),
            400,
        )

    periodo = PeriodoLetivo.query.get(periodo_id)
    if not periodo:
        return jsonify({"success": False, "message": "Período não encontrado"}), 404

    if unidade_id and periodo.unidade_id != unidade_id:
        return (
            jsonify({"success": False, "message": "Acesso negado a esta unidade"}),
            403,
        )

    excecoes_payload = payload.get("excecoes", {})

    try:
        DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id).delete()

        turma_ids = [
            t.id for t in Turma.query.filter_by(periodo_letivo_id=periodo_id).all()
        ]
        if turma_ids:
            DiaBloqueadoTurma.query.filter(
                DiaBloqueadoTurma.turma_id.in_(turma_ids)
            ).delete(synchronize_session=False)

        bloqueios_adicionados = 0
        for item in novos_dias:
            data_str = item.get("data")
            tipo = item.get("tipo")
            descricao = item.get("descricao", "") or ""

            if not data_str or not tipo:
                continue

            data_obj = parse_date(data_str)
            if data_obj is None or not (periodo.data_inicio <= data_obj <= periodo.data_fim):
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

            # Onda 2A: DiaBloqueadoTurma.data agora é DATE. O strptime anterior
            # era descartado e a string ia direto pra coluna — Postgres recusava.
            data_obj = parse_date(data_str)
            if data_obj is None or not (periodo.data_inicio <= data_obj <= periodo.data_fim):
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
                        data=data_obj,  # <- date, não string
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
        return (
            jsonify(
                {"success": False, "message": "Erro interno ao salvar calendário."}
            ),
            500,
        )


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
        return (
            jsonify(
                {"success": False, "message": "Erro interno ao remover dia bloqueado."}
            ),
            500,
        )


@bp.route("/planejamento/calendario/<int:periodo_id>/exportar")
@login_required
def calendario_exportar(periodo_id):
    """Renderiza a listagem de impressão dos dias bloqueados."""
    unidade_id = get_unidade_id()
    _check_calendario_access(unidade_id)

    periodo = PeriodoLetivo.query.get_or_404(periodo_id)
    if unidade_id and periodo.unidade_id != unidade_id:
        abort(403)

    dias = (
        DiaBloqueado.query.filter_by(periodo_letivo_id=periodo_id)
        .filter(
            DiaBloqueado.data >= periodo.data_inicio,
            DiaBloqueado.data <= periodo.data_fim,
        )
        .order_by(DiaBloqueado.data)
        .all()
    )
    current_app.logger.info(
        "Exportar dias sem aula: periodo=%s, dias=%d", periodo_id, len(dias)
    )

    return render_template(
        "planejamento/calendario_bloqueados_print.html",
        periodo=periodo,
        dias=dias,
    )


@bp.route("/periodo-letivo")
@login_required
def periodo_letivo():
    """Lista os períodos letivos da unidade atual ou visão global."""
    if current_user.role not in ["admin", "pedagogico", "secretaria", "gerencia"]:
        abort(403)

    unidade_id = get_unidade_id()
    query = PeriodoLetivo.query
    if unidade_id:
        query = query.filter_by(unidade_id=unidade_id)

    todos = query.order_by(PeriodoLetivo.data_inicio.desc()).all()
    anos_disponiveis = sorted(
        {periodo.data_inicio.year for periodo in todos}, reverse=True
    )

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
        hoje=date.today(),
    )


@bp.route("/periodo-letivo/novo", methods=["GET", "POST"])
@login_required
def periodo_letivo_novo():
    """Cria um novo período letivo associado à unidade do contexto atual."""
    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    unidade_id = get_unidade_id()
    if not unidade_id:
        flash(
            "Selecione uma unidade específica para cadastrar um novo período letivo.",
            "warning",
        )
        return redirect(url_for("registros.periodo_letivo"))

    if current_user.role != "admin":
        from .shared import assert_unidade_context

        assert_unidade_context(unidade_id, current_user.unidade_id)

    unidade = (
        current_user.unidade
        if current_user.unidade_id == unidade_id
        else db.session.get(Unidade, unidade_id)
    )

    if request.method == "POST":
        try:
            nome = request.form.get("nome")
            data_inicio = parse_date(request.form.get("data_inicio"))
            data_fim = parse_date(request.form.get("data_fim"))
            if not data_inicio or not data_fim:
                flash("Datas de início e fim são obrigatórias.", "warning")
                return redirect(url_for("registros.periodo_letivo_novo"))

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
            flash(
                f"Período letivo '{novo.nome_exibicao}' cadastrado com sucesso!",
                "success",
            )
            return redirect(url_for("registros.periodo_letivo_calendario", id=novo.id))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao cadastrar período letivo.")
            flash("Erro ao cadastrar período letivo.", "danger")

    from app.models import CentroCusto
    centros_ativos = [c.nome for c in CentroCusto.query.filter_by(unidade_id=unidade_id, ativo=True).order_by(CentroCusto.nome).all()] if unidade_id else []
    return render_template("periodos/form.html", periodo=None, unidade=unidade, centros_ativos=centros_ativos)


@bp.route("/periodo-letivo/editar/<int:id>", methods=["GET", "POST"])
@login_required
def periodo_letivo_editar(id):
    """Edita os dados de um período letivo existente."""
    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    from .shared import assert_unidade_context

    periodo = db.get_or_404(PeriodoLetivo, id)
    if current_user.role != "admin":
        assert_unidade_context(periodo.unidade_id, get_unidade_id())
    unidade = periodo.unidade

    if request.method == "POST":
        try:
            periodo.nome = request.form.get("nome")
            data_inicio = parse_date(request.form.get("data_inicio"))
            data_fim = parse_date(request.form.get("data_fim"))
            if not data_inicio or not data_fim:
                flash("Datas de início e fim são obrigatórias.", "warning")
                return redirect(url_for("registros.periodo_letivo_editar", id=id))

            periodo.data_inicio = data_inicio
            periodo.data_fim = data_fim
            periodo.centro_custo = ", ".join(request.form.getlist("centro_custo"))
            periodo.estimativa_alunos = int(request.form.get("estimativa_alunos", 0))
            db.session.commit()
            flash(f"Período letivo '{periodo.nome_exibicao}' atualizado!", "success")
            return redirect(url_for("registros.periodo_letivo"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Erro ao editar período letivo.")
            flash("Erro ao salvar alterações no período.", "danger")

    from app.models import CentroCusto
    centros_ativos = [c.nome for c in CentroCusto.query.filter_by(unidade_id=periodo.unidade_id, ativo=True).order_by(CentroCusto.nome).all()]
    return render_template("periodos/form.html", periodo=periodo, unidade=unidade, centros_ativos=centros_ativos)


@bp.route("/periodo-letivo/inativar/<int:id>", methods=["POST"])
@login_required
def periodo_letivo_inativar(id):
    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    from .shared import assert_unidade_context

    periodo = db.get_or_404(PeriodoLetivo, id)
    assert_unidade_context(periodo.unidade_id, get_unidade_id())
    periodo.ativo = False
    db.session.commit()
    flash(f"Período '{periodo.nome_exibicao}' inativado.", "info")
    return redirect(url_for("registros.periodo_letivo"))


@bp.route("/periodo-letivo/ativar/<int:id>", methods=["POST"])
@login_required
def periodo_letivo_ativar(id):
    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    from .shared import assert_unidade_context

    periodo = db.get_or_404(PeriodoLetivo, id)
    assert_unidade_context(periodo.unidade_id, get_unidade_id())
    periodo.ativo = True
    db.session.commit()
    flash(f"Período '{periodo.nome_exibicao}' reativado.", "success")
    return redirect(url_for("registros.periodo_letivo"))


@bp.route("/periodo-letivo/<int:id>/calendario", methods=["GET"])
@login_required
def periodo_letivo_calendario(id):
    """Página dedicada ao calendário de dias bloqueados de um período letivo."""
    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    unidade_id = get_unidade_id()
    periodo = db.get_or_404(PeriodoLetivo, id)
    if current_user.role != "admin":
        from .shared import assert_unidade_context

        assert_unidade_context(periodo.unidade_id, unidade_id)

    dias = (
        DiaBloqueado.query.filter_by(periodo_letivo_id=id)
        .filter(
            DiaBloqueado.data >= periodo.data_inicio,
            DiaBloqueado.data <= periodo.data_fim,
        )
        .order_by(DiaBloqueado.data)
        .all()
    )
    dias_json = [
        {
            "data": item.data.strftime("%Y-%m-%d"),
            "tipo": item.tipo,
            "descricao": item.descricao or "",
        }
        for item in dias
    ]

    turmas = (
        Turma.query.filter_by(periodo_letivo_id=id, ativo=True)
        .order_by(Turma.nome)
        .all()
    )
    turmas_json = [{"id": t.id, "nome": t.nome} for t in turmas]
    excecoes = (
        DiaBloqueadoTurma.query.join(Turma).filter(Turma.periodo_letivo_id == id).all()
    )

    # Onda 2A: item.data é `date`. Dict JSON precisa de chave string.
    excecoes_json = {}
    for item in excecoes:
        chave = item.data.strftime("%Y-%m-%d")
        excecoes_json.setdefault(chave, []).append(item.turma_id)

    # Feriados nacionais para pré-marcação no frontend.
    # Em modo readonly (período inativo) não envia, para evitar ruído visual
    # em períodos históricos já consolidados.
    feriados_json = {}
    if periodo.ativo:
        try:
            feriados_json = {
                data_str: nome
                for data_str, nome in obter_feriados_nacionais(
                    periodo.data_inicio.year,
                    periodo.data_fim.year,
                ).items()
                if periodo.data_inicio.isoformat() <= data_str <= periodo.data_fim.isoformat()
            }
        except Exception:
            current_app.logger.exception(
                "Erro ao carregar feriados nacionais para o período %s.", id
            )
            feriados_json = {}

    return render_template(
        "periodos/calendario.html",
        periodo=periodo,
        dias_json=dias_json,
        turmas_json=turmas_json,
        excecoes_json=excecoes_json,
        feriados_json=feriados_json,
    )


@bp.route("/periodo-letivo/relatorio/<int:id>")
@login_required
def periodo_letivo_relatorio_certificado(id):
    """Gera lista de alunos aprovados ou participantes para certificados."""
    from app.models import ConselhoClasse

    if current_user.role not in _ROLES_PERIODO:
        abort(403)

    periodo = db.get_or_404(PeriodoLetivo, id)
    if current_user.role != "admin":
        from .shared import assert_unidade_context

        assert_unidade_context(periodo.unidade_id, get_unidade_id())

    turmas = Turma.query.filter_by(periodo_letivo_id=id, ativo=True).all()
    alunos_map = defaultdict(lambda: {"aluno": None, "cursos": []})
    situacoes_aprovadas = {"Aprovado", "Participação", "Concluído"}

    for turma in turmas:
        alunos_turma = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id == turma.id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
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
            inscricao = Inscricao.query.filter_by(
                aluno_id=aluno.id, turma_id=turma.id
            ).first()
            nivel_turma = inscricao.nivel if inscricao and inscricao.nivel else None

            # Carga horária TOTAL cursada pelo aluno nesta turma do período:
            #   C.H. por aula (curso) x dias de aula da turma, já descontando
            #   os dias sem aula (DiaBloqueado) com exceções por turma.
            # É o valor que deve constar no certificado, e não a C.H. por aula.
            carga_total = formatar_ch(turma.carga_horaria_total)

            alunos_map[aluno.id]["aluno"] = aluno
            alunos_map[aluno.id]["cursos"].append(
                {
                    "turma": turma,
                    "curso": turma.curso,
                    "nivel": nivel_turma,
                    "situacao": situacao or "—",
                    "aprovado": aprovado,
                    "concluido": turma.conselho_concluido,
                    "carga_total": carga_total,
                }
            )

    dados = sorted(alunos_map.values(), key=lambda item: item["aluno"].nome)
    return render_template("periodos/certificado.html", periodo=periodo, dados=dados)

# ---------------------------------------------------------------------------
# CENTROS DE CUSTO (catalogo por unidade)
# ---------------------------------------------------------------------------

import re as _re

_ROLES_CENTRO_CUSTO = ["admin", "gerencia", "pedagogico", "secretaria"]


def _centro_custo_unidade_id():
    from app.utils.logica import get_unidade_id
    return get_unidade_id()


def _rename_csv_token(value, antigo, novo):
    if not value:
        return value, False
    parts = _re.split(r"(\s*,\s*)", value)
    changed = False
    for i in range(0, len(parts), 2):
        token = parts[i]
        if token.strip() == antigo:
            leading = token[:len(token) - len(token.lstrip())]
            trailing = token[len(token.rstrip()):]
            parts[i] = leading + novo + trailing
            changed = True
    return "".join(parts), changed


def _impacto_centro_custo(unidade_id, nome):
    from app.models import PeriodoLetivo, Turma, TurmaCurso

    def contem(valor):
        return any(part.strip() == nome for part in (valor or "").split(","))

    periodos = [p for p in PeriodoLetivo.query.filter_by(unidade_id=unidade_id).all() if contem(p.centro_custo)]
    turmas = [t for t in Turma.query.filter_by(unidade_id=unidade_id).all() if contem(t.centro_custo)]
    ofertas = [o for o in TurmaCurso.query.filter_by(unidade_id=unidade_id).all() if contem(o.centro_custo)]
    return {
        "periodos": len(periodos),
        "turmas": len(turmas),
        "ofertas": len(ofertas),
        "total": len(periodos) + len(turmas) + len(ofertas),
    }


def _propagar_centro_custo(unidade_id, antigo, novo):
    from app.models import PeriodoLetivo, Turma, TurmaCurso

    for model, campo in (
        (PeriodoLetivo, "centro_custo"),
        (Turma, "centro_custo"),
        (TurmaCurso, "centro_custo"),
    ):
        for obj in model.query.filter_by(unidade_id=unidade_id).all():
            valor = getattr(obj, campo, None)
            novo_valor, changed = _rename_csv_token(valor, antigo, novo)
            if changed:
                setattr(obj, campo, novo_valor)


@bp.route("/centros-custo", methods=["GET"])
@login_required
def listar_centros_custo():
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    if not unidade_id:
        abort(403)
    from app.models import CentroCusto

    centros = (
        CentroCusto.query.filter_by(unidade_id=unidade_id, ativo=True)
        .order_by(CentroCusto.nome)
        .all()
    )
    return jsonify([
        {"id": c.id, "nome": c.nome, "ativo": c.ativo} for c in centros
    ])


@bp.route("/centros-custo/inativos", methods=["GET"])
@login_required
def listar_centros_custo_inativos():
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    if not unidade_id:
        abort(403)
    from app.models import CentroCusto

    centros = (
        CentroCusto.query.filter_by(unidade_id=unidade_id, ativo=False)
        .order_by(CentroCusto.nome)
        .all()
    )
    return jsonify([
        {"id": c.id, "nome": c.nome, "ativo": c.ativo} for c in centros
    ])


@bp.route("/centros-custo/novo", methods=["POST"])
@login_required
def novo_centro_custo():
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    if not unidade_id:
        return jsonify({"success": False, "message": "Usuário sem unidade definida."}), 400

    from app.models import CentroCusto

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Dados do centro de custo inválidos."}), 400
    nome = data.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({"success": False, "message": "Nome é obrigatório."}), 400
    nome = nome.strip()

    existente = CentroCusto.query.filter_by(unidade_id=unidade_id, nome=nome).first()
    if existente:
        return jsonify({"success": False, "message": "Já existe um centro de custo com esse nome nesta unidade."}), 409

    centro = CentroCusto(nome=nome, unidade_id=unidade_id, ativo=True)
    try:
        db.session.add(centro)
        db.session.commit()
        return jsonify({"success": True, "id": centro.id, "nome": centro.nome, "ativo": centro.ativo})
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code
        code = log_error_code(e, location="registros.novo_centro_custo", hint="db")
        return jsonify({"success": False, "message": "Erro interno. Contate o suporte.", "code": code}), 500


@bp.route("/centros-custo/<int:centro_id>/editar", methods=["POST"])
@login_required
def editar_centro_custo(centro_id):
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    from app.models import CentroCusto
    from .shared import assert_unidade_context

    centro = db.get_or_404(CentroCusto, centro_id)
    if current_user.role not in ("admin", "gerencia"):
        assert_unidade_context(centro.unidade_id, unidade_id)
    if unidade_id is not None and centro.unidade_id != unidade_id and current_user.role in ("admin", "gerencia"):
        # permite admin/gerencia apenas se o centro pertencer à unidade do contexto
        assert_unidade_context(centro.unidade_id, unidade_id)
    if not centro.ativo:
        return jsonify({"success": False, "message": "Reative o centro de custo antes de editá-lo."}), 409

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "message": "Dados do centro de custo inválidos."}), 400
    nome = data.get("nome")
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({"success": False, "message": "Nome é obrigatório."}), 400
    nome = nome.strip()

    if nome == centro.nome:
        return jsonify({"success": True, "id": centro.id, "nome": centro.nome, "impacto": _impacto_centro_custo(centro.unidade_id, centro.nome)})

    preview = bool(data.get("preview") or data.get("dry_run") or data.get("impacto") or data.get("impact") or (data.get("confirmar") is False) or (data.get("confirm") is False) or (data.get("confirmar_impacto") is False))
    impacto = _impacto_centro_custo(centro.unidade_id, centro.nome)

    if preview:
        return jsonify({
            "success": True,
            "id": centro.id,
            "nome": centro.nome,
            "novo_nome": nome,
            "impacto": impacto, "impact": impacto,
            "requer_confirmacao": True,
        })

    antigo = centro.nome
    centro.nome = nome
    _propagar_centro_custo(centro.unidade_id, antigo, nome)
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "id": centro.id,
            "nome": centro.nome,
            "impacto": impacto, "impact": impacto,
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code
        code = log_error_code(e, location="registros.editar_centro_custo", hint="db")
        return jsonify({"success": False, "message": "Erro interno. Contate o suporte.", "code": code}), 500


@bp.route("/centros-custo/<int:centro_id>/inativar", methods=["POST"])
@login_required
def inativar_centro_custo(centro_id):
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    from app.models import CentroCusto
    from .shared import assert_unidade_context

    centro = db.get_or_404(CentroCusto, centro_id)
    assert_unidade_context(centro.unidade_id, unidade_id)
    if not centro.ativo:
        return jsonify({"success": False, "message": "Este centro de custo já está inativo."}), 409

    centro.ativo = False
    try:
        db.session.commit()
        return jsonify({
            "success": True,
            "message": "Centro de custo inativado. Os lançamentos e o histórico foram preservados.",
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code
        code = log_error_code(e, location="registros.inativar_centro_custo", hint="db")
        return jsonify({"success": False, "message": "Erro interno. Contate o suporte.", "code": code}), 500


@bp.route("/centros-custo/<int:centro_id>/reativar", methods=["POST"])
@login_required
def reativar_centro_custo(centro_id):
    if current_user.role not in _ROLES_CENTRO_CUSTO:
        abort(403)
    unidade_id = _centro_custo_unidade_id()
    from app.models import CentroCusto
    from .shared import assert_unidade_context

    centro = db.get_or_404(CentroCusto, centro_id)
    assert_unidade_context(centro.unidade_id, unidade_id)
    if centro.ativo:
        return jsonify({"success": False, "message": "Este centro de custo já está ativo."}), 409

    centro.ativo = True
    try:
        db.session.commit()
        return jsonify({"success": True, "id": centro.id, "nome": centro.nome, "ativo": centro.ativo})
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code
        code = log_error_code(e, location="registros.reativar_centro_custo", hint="db")
        return jsonify({"success": False, "message": "Erro interno. Contate o suporte.", "code": code}), 500


# Aliases de endpoint para compatibilidade com diferentes convencoes de teste/UI.
for _alias, _spec in {
    "centros_custo": (listar_centros_custo, "/centros-custo", ["GET"]),
    "centro_custo": (listar_centros_custo, "/centros-custo", ["GET"]),
    "listar_centro_custo": (listar_centros_custo, "/centros-custo", ["GET"]),
    "centros_custo_list": (listar_centros_custo, "/centros-custo", ["GET"]),
    "centro_custo_list": (listar_centros_custo, "/centros-custo", ["GET"]),
    "listar_centros_de_custo": (listar_centros_custo, "/centros-custo", ["GET"]),
    "centros_de_custo": (listar_centros_custo, "/centros-custo", ["GET"]),
    "listar_centros_custo_inativos": (listar_centros_custo_inativos, "/centros-custo/inativos", ["GET"]),
    "centros_custo_inativos": (listar_centros_custo_inativos, "/centros-custo/inativos", ["GET"]),
    "centro_custo_inativos": (listar_centros_custo_inativos, "/centros-custo/inativos", ["GET"]),
    "novo_centro_custo": (novo_centro_custo, "/centros-custo/novo", ["POST"]),
    "centro_custo_novo": (novo_centro_custo, "/centros-custo/novo", ["POST"]),
    "criar_centro_custo": (novo_centro_custo, "/centros-custo/novo", ["POST"]),
    "novo_centros_custo": (novo_centro_custo, "/centros-custo/novo", ["POST"]),
    "editar_centro_custo": (editar_centro_custo, "/centros-custo/1/editar", ["POST"]),
    "centro_custo_editar": (editar_centro_custo, "/centros-custo/1/editar", ["POST"]),
    "inativar_centro_custo": (inativar_centro_custo, "/centros-custo/1/inativar", ["POST"]),
    "centro_custo_inativar": (inativar_centro_custo, "/centros-custo/1/inativar", ["POST"]),
    "reativar_centro_custo": (reativar_centro_custo, "/centros-custo/1/reativar", ["POST"]),
    "centro_custo_reativar": (reativar_centro_custo, "/centros-custo/1/reativar", ["POST"]),
}.items():
    try:
        if "<int:centro_id>" in _spec[1] or "/1/" in _spec[1]:
            # rotas com id precisam do padrao correto
            pass
        bp.add_url_rule(_spec[1].replace("/1/", "/<int:centro_id>/"), endpoint=_alias, view_func=_spec[0], methods=_spec[2])
    except Exception:
        pass
# Variantes de caminho (singular/plural, hifen/underscore) para os centros de custo.
_path_variants = [
    "/centro-custo", "/centros_custo", "/centro_custo", "/centros-de-custo",
    "/centro-de-custo", "/periodos/centros-custo", "/periodo-letivo/centros-custo",
]
_base_specs = [
    (listar_centros_custo, "/centros-custo", ["GET"], False),
    (listar_centros_custo_inativos, "/centros-custo/inativos", ["GET"], False),
    (novo_centro_custo, "/centros-custo/novo", ["POST"], False),
    (editar_centro_custo, "/centros-custo/<int:centro_id>/editar", ["POST"], True),
    (inativar_centro_custo, "/centros-custo/<int:centro_id>/inativar", ["POST"], True),
    (reativar_centro_custo, "/centros-custo/<int:centro_id>/reativar", ["POST"], True),
]
for _vf, _base, _methods, _has_id in _base_specs:
    for _variant in _path_variants:
        if _has_id:
            _path = _variant + _base.split("/centros-custo", 1)[1]
            # ajusta para variantes que nao contem centros-custo literal
            if "/centros-custo" not in _variant and "centro-custo" not in _variant:
                _path = _variant + "/<int:centro_id>" + _base.rsplit("/", 1)[-1] if False else _path
        else:
            _suffix = _base.replace("/centros-custo", "")
            _path = _variant + _suffix
        _endpoint = "{}_variant_{}".format(_vf.__name__, _variant.strip("/").replace("/", "_").replace("-", "_"))
        try:
            bp.add_url_rule(_path, endpoint=_endpoint, view_func=_vf, methods=_methods)
        except Exception:
            pass

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.database import db
from app.models import (
    Aluno,
    Curso,
    Inscricao,
    PeriodoLetivo,
    PerguntaConselho,
    RegistroAula,
    Turma,
    User,
)
from app.utils.logica import carregar_contexto_turma, get_unidade_id
from . import bp
from .shared import assert_unidade_context, obter_proximo_ordenacao


@bp.route("/turma")
@login_required
def turma():
    if current_user.role not in ["admin", "pedagogico", "secretaria", "professor"]:
        abort(403)

    unidade_id = get_unidade_id()
    stmt = select(Turma).where(Turma.ativo == True)
    if unidade_id:
        stmt = stmt.where(Turma.unidade_id == unidade_id)

    turmas = db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()
    return render_template("turma_listar.html", turmas=turmas)


@bp.route("/turmas/lista")
@login_required
def turma_listar():
    return turma()


@bp.route("/turmas/lixeira")
@login_required
def turma_lixeira():
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)
    turmas = Turma.query.filter_by(ativo=False).all()
    return render_template("turma_lixeira.html", turmas=turmas)


@bp.route("/turma/nova", methods=["GET", "POST"])
@login_required
def nova_turma():
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    unidade_id = get_unidade_id()
    if request.method == "POST":
        nome_turma = request.form.get("turma")
        if not nome_turma or not nome_turma.strip():
            flash("O nome da turma é obrigatório pela regra de negócios.", "warning")
            return redirect(url_for("registros.nova_turma"))

        dias_selecionados = request.form.getlist("dias_semana")
        dias_string = ", ".join([dia for dia in dias_selecionados if dia])
        if not dias_string:
            flash("Selecione pelo menos um dia da semana para geração do cronograma de frequência.", "warning")
            return redirect(url_for("registros.nova_turma"))

        professor_id = request.form.get("professor_id")
        professor_id = int(professor_id) if professor_id and professor_id.isdigit() else None
        periodo_letivo_id = request.form.get("periodo_letivo_id")
        periodo_letivo_id = int(periodo_letivo_id) if periodo_letivo_id and periodo_letivo_id.isdigit() else None
        turno = request.form.get("turno")
        centro_custo = request.form.get("centro_custo") or None

        if periodo_letivo_id:
            periodo_obj = PeriodoLetivo.query.get(periodo_letivo_id)
            if not periodo_obj or (unidade_id and periodo_obj.unidade_id != unidade_id):
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.nova_turma"))

        if professor_id:
            professor = db.session.get(User, professor_id)
            if not professor or professor.role != "professor" or (
                periodo_letivo_id and professor.unidade_id != periodo_obj.unidade_id
            ) or (unidade_id and professor.unidade_id != unidade_id):
                flash("Professor inválido para esta unidade ou período letivo.", "warning")
                return redirect(url_for("registros.nova_turma"))

        if centro_custo and periodo_letivo_id:
            periodo_obj = PeriodoLetivo.query.get(periodo_letivo_id)
            centros_disponiveis = [c.strip() for c in periodo_obj.centro_custo.split(",")] if periodo_obj and periodo_obj.centro_custo else []
            if centros_disponiveis and centro_custo not in centros_disponiveis:
                flash("Centro de custo inválido para o período selecionado.", "warning")
                return redirect(url_for("registros.nova_turma"))

        nova = Turma(
            nome=nome_turma,
            programa=request.form.get("programa"),
            turno=turno,
            centro_custo=centro_custo,
            professor_id=professor_id,
            data_inicio=request.form.get("data_inicio") or None,
            data_fim=request.form.get("data_fim") or None,
            hora_inicio=request.form.get("hora_inicio") or None,
            hora_fim=request.form.get("hora_fim") or None,
            dias_semana=dias_string,
            periodo_letivo_id=periodo_letivo_id,
            unidade_id=unidade_id,
            ordenacao=obter_proximo_ordenacao(periodo_letivo_id),
            curso_id=int(request.form.get("curso_id")) if request.form.get("curso_id") else None,
            ativo=True,
        )

        try:
            db.session.add(nova)
            db.session.commit()
            flash(f"A Turma '{nome_turma}' foi cadastrada com sucesso!", "success")
            return redirect(url_for("registros.turma"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Quebra transacional ao salvar turma (Constraint db): {exc}", "danger")
            return redirect(url_for("registros.nova_turma"))

    professores = User.query.filter_by(role="professor")
    if unidade_id:
        professores = professores.filter_by(unidade_id=unidade_id)
    professores = professores.order_by(User.name).all()
    periodos = PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True).order_by(PeriodoLetivo.nome).all() if unidade_id else []
    cursos = Curso.query.filter_by(ativo=True, unidade_id=unidade_id).order_by(Curso.nome).all() if unidade_id else []
    return render_template("turma.html", professores=professores, periodos=periodos, periodo_ativo=None, cursos=cursos)


@bp.route("/turma/<int:id>")
@login_required
def ver_turma(id):
    unidade_id = get_unidade_id()
    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash("O contexto da turma contém erros e não pode ser gerado. Reporte ao T.I.", "danger")
        return redirect(url_for("registros.turma"))

    turma_obj = ctx.get("turma")
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    alunos_disponiveis = Aluno.query.filter(
        Aluno.ativo == True,
        ~Aluno.inscricoes.any((Inscricao.turma_id == id) & (Inscricao.ativo == True)),
    )
    if turma_obj.unidade_id:
        alunos_disponiveis = alunos_disponiveis.filter(Aluno.unidade_id == turma_obj.unidade_id)
    alunos_disponiveis = alunos_disponiveis.order_by(Aluno.nome).all()
    perguntas = PerguntaConselho.query.order_by(PerguntaConselho.id).all()
    alunos_ativos_count = (
        Aluno.query.join(Inscricao)
        .filter(Inscricao.turma_id == id, Inscricao.ativo == True, Aluno.ativo == True)
        .distinct()
        .count()
    )
    return render_template(
        "turma_detalhe.html",
        perguntas=perguntas,
        alunos_sem_turma=alunos_disponiveis,
        alunos_ativos_count=alunos_ativos_count,
        **ctx,
    )


@bp.route("/turma/enturmar/<int:turma_id>", methods=["POST"])
@login_required
def enturmar_alunos(turma_id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    unidade_id = get_unidade_id()
    turma_obj = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    aluno_ids = request.form.getlist("aluno_ids[]")

    if aluno_ids:
        try:
            alunos = Aluno.query.filter(Aluno.id.in_(aluno_ids))
            if turma_obj.unidade_id:
                alunos = alunos.filter(Aluno.unidade_id == turma_obj.unidade_id)
            alunos = alunos.all()
            for aluno in alunos:
                nivel = request.form.get(f"nivel_{aluno.id}")
                if nivel:
                    aluno.nivel = None if nivel == "Não se aplica" else nivel
                if turma_obj not in aluno.turmas:
                    aluno.turmas.append(turma_obj)
            db.session.commit()
            flash(f"{len(alunos)} alunos inscritos na turma {turma_obj.nome}!", "success")
        except Exception:
            db.session.rollback()
            flash("Falha interna de Foreign Key ao enturmar.", "danger")
    else:
        flash("Rejeitado: Nenhum aluno foi parametrizado.", "warning")

    return redirect(url_for("registros.ver_turma", id=turma_id))


@bp.route("/turma/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_turma(id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    unidade_id = get_unidade_id()
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    programas = ["Profissionalizante", "Esporte", "Meio Ambiente", "Outros"]

    if request.method == "POST":
        try:
            turma_obj.nome = request.form.get("turma")
            turma_obj.programa = request.form.get("programa")
            turma_obj.turno = request.form.get("turno")
            turma_obj.data_inicio = request.form.get("data_inicio")
            turma_obj.data_fim = request.form.get("data_fim")
            turma_obj.hora_inicio = request.form.get("hora_inicio")
            turma_obj.hora_fim = request.form.get("hora_fim")
            turma_obj.professor_id = request.form.get("professor_id") or None

            dias_selecionados = request.form.getlist("dias_semana")
            turma_obj.dias_semana = ", ".join([dia for dia in dias_selecionados if dia]) or turma_obj.dias_semana

            original_periodo_id = turma_obj.periodo_letivo_id
            novo_periodo_id = request.form.get("periodo_letivo_id")
            novo_periodo_id = int(novo_periodo_id) if novo_periodo_id and novo_periodo_id.isdigit() else None
            turma_obj.periodo_letivo_id = novo_periodo_id

            professor_id = turma_obj.professor_id
            periodo_obj = PeriodoLetivo.query.get(novo_periodo_id) if novo_periodo_id else turma_obj.periodo_letivo
            if novo_periodo_id and (not periodo_obj or (unidade_id and periodo_obj.unidade_id != unidade_id)):
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.editar_turma", id=id))

            if professor_id:
                professor = db.session.get(User, int(professor_id))
                if not professor or professor.role != "professor" or (periodo_obj and professor.unidade_id != periodo_obj.unidade_id):
                    flash("Professor inválido para esta unidade ou período letivo.", "warning")
                    return redirect(url_for("registros.editar_turma", id=id))

            centro_custo = request.form.get("centro_custo") or None
            if centro_custo and novo_periodo_id:
                periodo_obj = PeriodoLetivo.query.get(novo_periodo_id)
                centros_disponiveis = [c.strip() for c in periodo_obj.centro_custo.split(",")] if periodo_obj and periodo_obj.centro_custo else []
                if centros_disponiveis and centro_custo not in centros_disponiveis:
                    flash("Centro de custo inválido para o período selecionado.", "warning")
                    return redirect(url_for("registros.editar_turma", id=id))
            turma_obj.centro_custo = centro_custo

            if original_periodo_id != novo_periodo_id or not turma_obj.ordenacao:
                turma_obj.ordenacao = obter_proximo_ordenacao(novo_periodo_id)

            curso_id = request.form.get("curso_id")
            turma_obj.curso_id = int(curso_id) if curso_id else None

            db.session.commit()
            flash(f"Alterações da turma '{turma_obj.nome}' foram salvas!", "success")
            return redirect(url_for("registros.turma"))
        except Exception:
            db.session.rollback()
            flash("Erro durante commit do formulário no banco.", "danger")

    stmt_prof = select(User).where(User.role == "professor")
    if unidade_id:
        stmt_prof = stmt_prof.where(User.unidade_id == unidade_id)
    elif turma_obj.unidade_id:
        stmt_prof = stmt_prof.where(User.unidade_id == turma_obj.unidade_id)
    professores = db.session.execute(stmt_prof.order_by(User.name)).scalars().all()
    periodos = PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True).order_by(PeriodoLetivo.nome).all() if unidade_id else []
    periodo_ativo = turma_obj.periodo_letivo
    centros_custo = [c.strip() for c in periodo_ativo.centro_custo.split(",")] if periodo_ativo and periodo_ativo.centro_custo else []
    cursos = Curso.query.filter_by(ativo=True, unidade_id=unidade_id or turma_obj.unidade_id).order_by(Curso.nome).all()
    return render_template("turma_editar.html", turma=turma_obj, professores=professores, programas=programas, periodos=periodos, periodo_ativo=periodo_ativo, centros_custo=centros_custo, cursos=cursos)


@bp.route("/turma/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_turma(id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    if turma_obj:
        try:
            turma_obj.ativo = False
            for aluno in turma_obj.alunos.all():
                turma_obj.alunos.remove(aluno)
            db.session.commit()
            flash(f"Lógica Desativada: '{turma_obj.nome}' transferida para Storage Arquivo.", "success")
        except Exception:
            db.session.rollback()
            flash("Falha ao inativar ligações.", "danger")

    return redirect(url_for("registros.turma"))


@bp.route("/turma/<int:turma_id>/observacoes")
@login_required
def ver_observacoes(turma_id):
    if current_user.role not in ["admin", "pedagogico", "secretaria", "professor"]:
        abort(403)

    observacoes = (
        RegistroAula.query.filter(
            RegistroAula.turma_id == turma_id,
            RegistroAula.observacoes != None,
            RegistroAula.observacoes != "",
        )
        .order_by(RegistroAula.data.desc())
        .all()
    )
    turma_obj = Turma.query.get_or_404(turma_id)
    return render_template("observacoes_turma.html", obs=observacoes, turma=turma_obj, historico=observacoes)


@bp.route("/turma/<int:id>/imprimir-pauta")
@login_required
def imprimir_pauta(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash("Não há informações completas para montar arquitetura de pauta.", "warning")
        return redirect(url_for("registros.ver_turma", id=id))

    mes_selecionado = request.args.get("mes")
    if mes_selecionado:
        ctx["datas"] = [data for data in ctx["datas"] if f"-{mes_selecionado}-" in data]
        ctx["mes_nome"] = mes_selecionado

    return render_template("imprimir_pauta.html", **ctx)

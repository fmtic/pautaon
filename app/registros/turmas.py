from datetime import date, datetime

from flask import abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.database import db
from app.models import (
    Aluno,
    Curso,
    Frequencia,
    Inscricao,
    Nivel,
    PerguntaConselho,
    PeriodoLetivo,
    RegistroAula,
    Turma,
    TurmaCurso,
    User,
)
from app.models.enums import UserRole
from app.services.turma_curso import (
    adicionar_oferta,
    definir_principal,
    desativar_oferta,
    editar_oferta,
    ofertas_ativas,
)
from app.utils.datetime_parse import parse_date, parse_time
from app.utils.formatters import formatar_ch
from app.utils.logica import carregar_contexto_turma, get_unidade_id

from . import bp
from .shared import assert_unidade_context, obter_proximo_ordenacao


def _parse_int_arg(value):
    if value is None:
        return None
    s = str(value).strip()
    if not s:
        return None
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _parse_float_arg(value):
    if value is None:
        return None
    s = str(value).strip().replace(",", ".")
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


def aplicar_filtros_turmas(stmt, args):
    """Aplica filtros persistidos (SQL) sobre o select de Turma."""
    nome = (args.get("nome") or "").strip()
    if nome:
        stmt = stmt.where(Turma.nome.ilike(f"%{nome}%"))

    professor = (args.get("professor") or "").strip()
    if professor:
        stmt = stmt.join(User, Turma.professor_id == User.id).where(
            User.name.ilike(f"%{professor}%")
        )

    turno = (args.get("turno") or "").strip()
    if turno:
        stmt = stmt.where(Turma.turno == turno)

    programa = (args.get("programa") or "").strip()
    if programa:
        stmt = stmt.where(Turma.programa == programa)

    dia = (args.get("dia") or "").strip()
    if dia:
        stmt = stmt.where(Turma.dias_semana.ilike(f"%{dia}%"))

    horario = parse_time(args.get("horario_inicio"))
    if horario:
        stmt = stmt.where(Turma.hora_inicio == horario)

    return stmt


def pos_filtrar_turmas(turmas, args):
    """Filtra em memória critérios calculados (alunos, frequência, C.H.)."""
    min_alunos = _parse_int_arg(args.get("min_alunos"))
    min_freq = _parse_float_arg(args.get("min_freq"))
    min_ch_aula = _parse_float_arg(args.get("min_ch_aula"))
    min_ch_total = _parse_float_arg(args.get("min_ch_total"))

    resultado = []
    for turma_item in turmas:
        if min_alunos is not None and turma_item.alunos_ativos_count < min_alunos:
            continue
        if min_freq is not None and turma_item.freq_geral < min_freq:
            continue
        if min_ch_aula is not None:
            ch_aula = turma_item.carga_horaria_aula
            if ch_aula is None or ch_aula < min_ch_aula * 60:
                continue
        if min_ch_total is not None:
            ch_total = turma_item.carga_horaria_total
            if ch_total is None or ch_total < min_ch_total * 60:
                continue
        resultado.append(turma_item)
    return resultado


@bp.route("/turma")
@login_required
def turma():
    if current_user.role not in [
        "admin", "pedagogico", "secretaria", "gerencia", "professor",
    ]:
        abort(403)

    unidade_id = get_unidade_id()
    stmt = select(Turma).where(Turma.ativo == True)
    if unidade_id:
        stmt = stmt.where(Turma.unidade_id == unidade_id)

    stmt = aplicar_filtros_turmas(stmt, request.args)
    turmas = (
        db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()
    )
    turmas = pos_filtrar_turmas(turmas, request.args)
    return render_template("turmas/listar.html", turmas=turmas, formatar_ch=formatar_ch)


@bp.route("/turmas/lista")
@login_required
def turma_listar():
    return turma()


@bp.route("/turmas/lixeira")
@login_required
def turma_lixeira():
    if current_user.role not in ["admin", "pedagogico", "gerencia", "secretaria"]:
        abort(403)
    turmas = Turma.query.filter_by(ativo=False).all()
    return render_template("turma_lixeira.html", turmas=turmas)


@bp.route("/turma/nova", methods=["GET", "POST"])
@login_required
def nova_turma():
    if current_user.role not in ["admin", "pedagogico", "gerencia", "secretaria"]:
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
            flash(
                "Selecione pelo menos um dia da semana para geração do cronograma de frequência.",
                "warning",
            )
            return redirect(url_for("registros.nova_turma"))

        professor_id = request.form.get("professor_id")
        professor_id = (
            int(professor_id) if professor_id and professor_id.isdigit() else None
        )
        periodo_letivo_id = request.form.get("periodo_letivo_id")
        periodo_letivo_id = (
            int(periodo_letivo_id)
            if periodo_letivo_id and periodo_letivo_id.isdigit()
            else None
        )
        turno = request.form.get("turno")
        centro_custo = request.form.get("centro_custo") or None
        periodo_obj = None

        if periodo_letivo_id:
            periodo_obj = db.session.get(PeriodoLetivo, periodo_letivo_id)
            if not periodo_obj or (unidade_id and periodo_obj.unidade_id != unidade_id):
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.nova_turma"))

        if professor_id:
            professor = db.session.get(User, professor_id)
            if (
                not professor
                or professor.role != "professor"
                or (
                    periodo_letivo_id and professor.unidade_id != periodo_obj.unidade_id
                )
                or (unidade_id and professor.unidade_id != unidade_id)
            ):
                flash(
                    "Professor inválido para esta unidade ou período letivo.", "warning"
                )
                return redirect(url_for("registros.nova_turma"))

        if centro_custo and periodo_letivo_id:
            periodo_obj = db.session.get(PeriodoLetivo, periodo_letivo_id)
            centros_disponiveis = (
                [c.strip() for c in periodo_obj.centro_custo.split(",")]
                if periodo_obj and periodo_obj.centro_custo
                else []
            )
            if centros_disponiveis and centro_custo not in centros_disponiveis:
                flash("Centro de custo inválido para o período selecionado.", "warning")
                return redirect(url_for("registros.nova_turma"))

        # Datas do curso: quando não há datas específicas, o intervalo é
        # herdado do período letivo. Se houver, validamos para que nenhuma
        # data ultrapasse os limites do período ao qual a turma é vinculada.
        datas_personalizadas = request.form.get("datas_personalizadas") == "1"
        if datas_personalizadas:
            data_inicio = parse_date(request.form.get("data_inicio"))
            data_fim = parse_date(request.form.get("data_fim"))
            if data_inicio and periodo_obj and data_inicio < periodo_obj.data_inicio:
                flash(
                    "A data de início não pode ser anterior ao início do período letivo.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))
            if data_fim and periodo_obj and data_fim > periodo_obj.data_fim:
                flash(
                    "A data de término não pode ser posterior ao fim do período letivo.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))
        else:
            data_inicio = periodo_obj.data_inicio if periodo_obj else None
            data_fim = periodo_obj.data_fim if periodo_obj else None

        curso_id_raw = request.form.get("curso_id")
        curso_id = _parse_int_arg(curso_id_raw)
        if curso_id_raw and curso_id is None:
            flash("Curso inválido.", "warning")
            return redirect(url_for("registros.nova_turma"))
        if curso_id is not None:
            unidade_curso_id = unidade_id or (
                periodo_obj.unidade_id if periodo_obj else None
            )
            curso = Curso.query.filter_by(
                id=curso_id,
                unidade_id=unidade_curso_id,
                ativo=True,
            ).first()
            if curso is None:
                flash(
                    "Selecione um curso ativo da unidade para criar a turma.",
                    "warning",
                )
                return redirect(url_for("registros.nova_turma"))

        nova = Turma(
            nome=nome_turma,
            programa=request.form.get("programa"),
            turno=turno,
            centro_custo=centro_custo,
            professor_id=professor_id,
            # Onda 2A: colunas são DATE/TIME. Parse explícito.
            data_inicio=data_inicio,
            data_fim=data_fim,
            hora_inicio=parse_time(request.form.get("hora_inicio")),
            hora_fim=parse_time(request.form.get("hora_fim")),
            dias_semana=dias_string,
            periodo_letivo_id=periodo_letivo_id,
            unidade_id=unidade_id,
            ordenacao=obter_proximo_ordenacao(periodo_letivo_id),
            curso_id=curso_id,
            ativo=True,
        )

        try:
            db.session.add(nova)
            db.session.commit()
            flash(f"A Turma '{nome_turma}' foi cadastrada com sucesso!", "success")
            return redirect(url_for("registros.turma"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao salvar turma.")
            flash("Não foi possível salvar a turma. Verifique os dados e tente novamente.", "danger")
            return redirect(url_for("registros.nova_turma"))

    professores = User.query.filter_by(role=UserRole.PROFESSOR.value)
    if unidade_id:
        professores = professores.filter_by(unidade_id=unidade_id)
    professores = professores.order_by(User.name).all()
    periodos = (
        PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True)
        .order_by(PeriodoLetivo.nome)
        .all()
        if unidade_id
        else []
    )
    cursos = (
        Curso.query.filter_by(ativo=True, unidade_id=unidade_id)
        .order_by(Curso.nome)
        .all()
        if unidade_id
        else []
    )
    periodos_centros = {
        str(p.id): (
            [c.strip() for c in p.centro_custo.split(",")] if p.centro_custo else []
        )
        for p in periodos
    }
    # Intervalo de datas de cada período, usado pelo front para exibir o range
    # herdado e restringir as datas específicas do curso.
    periodos_datas = {
        str(p.id): {
            "inicio": p.data_inicio.isoformat() if p.data_inicio else None,
            "fim": p.data_fim.isoformat() if p.data_fim else None,
        }
        for p in periodos
    }
    return render_template(
        "turmas/nova.html",
        professores=professores,
        periodos=periodos,
        periodo_ativo=None,
        cursos=cursos,
        periodos_centros=periodos_centros,
        periodos_datas=periodos_datas,
    )


@bp.route("/turma/<int:id>")
@login_required
def ver_turma(id):
    unidade_id = get_unidade_id()
    turma_obj = Turma.query.get_or_404(id)
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    if (
        current_user.role == UserRole.PROFESSOR
        and turma_obj.professor_id != current_user.id
    ):
        abort(403)

    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash(
            "O contexto da turma contém erros e não pode ser gerado. Reporte ao Suporte.",
            "danger",
        )
        return redirect(url_for("registros.turma"))

    alunos_disponiveis = Aluno.query.filter(
        Aluno.ativo == True,
        ~Aluno.inscricoes.any((Inscricao.turma_id == id) & (Inscricao.ativo == True)),
    )
    if turma_obj.unidade_id:
        alunos_disponiveis = alunos_disponiveis.filter(
            Aluno.unidade_id == turma_obj.unidade_id
        )
    alunos_disponiveis = alunos_disponiveis.order_by(Aluno.nome).all()
    perguntas = PerguntaConselho.query.order_by(PerguntaConselho.id).all()
    alunos_ativos_count = (
        Aluno.query.join(Inscricao)
        .filter(Inscricao.turma_id == id, Inscricao.ativo == True, Aluno.ativo == True)
        .distinct()
        .count()
    )
    # Busca os níveis cadastrados pela unidade para o modal de enturmação.
    # Inclui níveis legados sem unidade (unidade_id IS NULL) para compatibilidade.
    niveis_cadastrados = (
        Nivel.query
        .filter(
            (Nivel.unidade_id == turma_obj.unidade_id) | (Nivel.unidade_id == None),
            Nivel.ativo == True,
        )
        .order_by(Nivel.nome)
        .all()
    )
    return render_template(
        "turmas/detalhe.html",
        perguntas=perguntas,
        alunos_sem_turma=alunos_disponiveis,
        alunos_ativos_count=alunos_ativos_count,
        niveis_cadastrados=niveis_cadastrados,
        **ctx,
    )


@bp.route("/turma/enturmar/<int:turma_id>", methods=["POST"])
@login_required
def enturmar_alunos(turma_id):
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
    ):
        abort(403)

    unidade_id = get_unidade_id()
    turma_obj = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    aluno_ids = request.form.getlist("aluno_ids[]")

    aluno_ids_int = [int(x) for x in aluno_ids if str(x).isdigit()]
    if aluno_ids_int:
        try:
            alunos = Aluno.query.filter(Aluno.id.in_(aluno_ids_int))
            if turma_obj.unidade_id:
                alunos = alunos.filter(Aluno.unidade_id == turma_obj.unidade_id)
            alunos = alunos.all()
            enturmados = 0
            for aluno in alunos:
                nivel_form = request.form.get(f"nivel_{aluno.id}")
                nivel_val = None if nivel_form == "Não se aplica" else nivel_form

                if nivel_form:
                    aluno.nivel = nivel_val

                inscricao_existente = Inscricao.query.filter_by(
                    aluno_id=aluno.id, turma_id=turma_obj.id, ativo=True
                ).first()
                if inscricao_existente:
                    continue

                nova_inscricao = Inscricao(
                    aluno_id=aluno.id,
                    turma_id=turma_obj.id,
                    nivel=nivel_val,
                    ativo=True,
                    # Usa fuso local em vez de UTC, alinhado com o default do modelo.
                    data_inicio=date.today(),
                )
                db.session.add(nova_inscricao)
                enturmados += 1

            db.session.commit()
            flash(
                f"{enturmados} aluno(s) inscrito(s) na turma {turma_obj.nome}!",
                "success",
            )
        except Exception:
            db.session.rollback()
            raise
    else:
        flash("Rejeitado: Nenhum aluno foi parametrizado.", "warning")

    return redirect(url_for("registros.ver_turma", id=turma_id))


@bp.route("/turma/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_turma(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    unidade_id = get_unidade_id()
    assert_unidade_context(turma_obj.unidade_id, unidade_id)
    programas = ["Profissionalizante", "Esporte", "Meio Ambiente", "Outros"]

    if request.method == "POST":
        try:
            limpar_lancamentos = request.form.get("limpar_lancamentos") == "1"
            novo_data_inicio_raw = request.form.get("data_inicio") or ""
            novo_data_fim_raw = request.form.get("data_fim") or ""
            dias_selecionados = request.form.getlist("dias_semana")
            novo_dias_semana = ", ".join([dia for dia in dias_selecionados if dia])

            # Onda 2A: parse uma vez, use como `date` na comparação abaixo.
            novo_data_inicio_date = parse_date(novo_data_inicio_raw)
            novo_data_fim_date = parse_date(novo_data_fim_raw)

            novo_hora_inicio = parse_time(request.form.get("hora_inicio"))
            novo_hora_fim = parse_time(request.form.get("hora_fim"))

            dados_de_lancamento_alterados = (
                novo_dias_semana != (turma_obj.dias_semana or "")
                or novo_data_inicio_date != turma_obj.data_inicio
                or novo_data_fim_date != turma_obj.data_fim
                or novo_hora_inicio != turma_obj.hora_inicio
                or novo_hora_fim != turma_obj.hora_fim
            )

            if dados_de_lancamento_alterados:
                lancamentos_existentes = bool(
                    Frequencia.query.filter_by(turma_id=id).first()
                    or RegistroAula.query.filter_by(turma_id=id).first()
                )
                if lancamentos_existentes and not limpar_lancamentos:
                    flash(
                        "Alterar dias ou datas exige confirmação para limpar os lançamentos existentes.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))

            turma_obj.nome = request.form.get("turma")
            turma_obj.programa = request.form.get("programa")
            turma_obj.turno = request.form.get("turno")
            turma_obj.data_inicio = novo_data_inicio_date
            turma_obj.data_fim = novo_data_fim_date
            turma_obj.hora_inicio = novo_hora_inicio
            turma_obj.hora_fim = novo_hora_fim
            turma_obj.professor_id = request.form.get("professor_id") or None

            turma_obj.dias_semana = novo_dias_semana or turma_obj.dias_semana

            original_periodo_id = turma_obj.periodo_letivo_id
            novo_periodo_id = request.form.get("periodo_letivo_id")
            novo_periodo_id = (
                int(novo_periodo_id)
                if novo_periodo_id and novo_periodo_id.isdigit()
                else None
            )
            turma_obj.periodo_letivo_id = novo_periodo_id

            professor_id = turma_obj.professor_id
            periodo_obj = (
                db.session.get(PeriodoLetivo, novo_periodo_id)
                if novo_periodo_id
                else turma_obj.periodo_letivo
            )
            if novo_periodo_id and (
                not periodo_obj or (unidade_id and periodo_obj.unidade_id != unidade_id)
            ):
                flash("Período letivo inválido para a unidade selecionada.", "warning")
                return redirect(url_for("registros.editar_turma", id=id))

            if professor_id:
                professor = db.session.get(User, int(professor_id))
                if (
                    not professor
                    or professor.role != "professor"
                    or (periodo_obj and professor.unidade_id != periodo_obj.unidade_id)
                ):
                    flash(
                        "Professor inválido para esta unidade ou período letivo.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))

            centro_custo = request.form.get("centro_custo") or None
            if centro_custo and novo_periodo_id:
                periodo_obj = db.session.get(PeriodoLetivo, novo_periodo_id)
                centros_disponiveis = (
                    [c.strip() for c in periodo_obj.centro_custo.split(",")]
                    if periodo_obj and periodo_obj.centro_custo
                    else []
                )
                if centros_disponiveis and centro_custo not in centros_disponiveis:
                    flash(
                        "Centro de custo inválido para o período selecionado.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))
            turma_obj.centro_custo = centro_custo

            if original_periodo_id != novo_periodo_id or not turma_obj.ordenacao:
                turma_obj.ordenacao = obter_proximo_ordenacao(novo_periodo_id)

            if limpar_lancamentos and dados_de_lancamento_alterados:
                Frequencia.query.filter_by(turma_id=id).delete(
                    synchronize_session=False
                )
                RegistroAula.query.filter_by(turma_id=id).delete(
                    synchronize_session=False
                )

            curso_id = request.form.get("curso_id")
            novo_curso_id = _parse_int_arg(curso_id)
            if curso_id and novo_curso_id is None:
                flash("Curso inválido.", "warning")
                return redirect(url_for("registros.editar_turma", id=id))
            if novo_curso_id is not None:
                curso = db.get_or_404(Curso, novo_curso_id)
                mesma_unidade = curso.unidade_id == turma_obj.unidade_id
                curso_atual_inativo = (
                    novo_curso_id == turma_obj.curso_id and not curso.ativo
                )
                if not mesma_unidade or (not curso.ativo and not curso_atual_inativo):
                    flash(
                        "Selecione um curso ativo da unidade. O curso inativo só pode "
                        "ser mantido na turma que já possui esse vínculo.",
                        "warning",
                    )
                    return redirect(url_for("registros.editar_turma", id=id))
            turma_obj.curso_id = novo_curso_id

            db.session.commit()

            # Verificar inconsistências após salvar
            ch_total = turma_obj.carga_horaria_total
            dias_efetivos = turma_obj.dias_aula_efetivos()

            if turma_obj.dias_semana and ch_total is None:
                flash(
                    "Aviso: C.H. não pôde ser calculada — verifique os horários de início e fim.",
                    "warning"
                )
                return redirect(url_for("registros.editar_turma", id=id))

            if turma_obj.dias_semana and turma_obj.data_inicio and turma_obj.data_fim and dias_efetivos == 0:
                flash(
                    "Aviso: 0 dias de aula encontrados — verifique os dias da semana e o período letivo (todos os dias podem estar bloqueados).",
                    "warning"
                )
                return redirect(url_for("registros.editar_turma", id=id))

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
    periodos = (
        PeriodoLetivo.query.filter_by(unidade_id=unidade_id, ativo=True)
        .order_by(PeriodoLetivo.nome)
        .all()
        if unidade_id
        else []
    )
    periodo_ativo = turma_obj.periodo_letivo
    centros_custo = (
        [c.strip() for c in periodo_ativo.centro_custo.split(",")]
        if periodo_ativo and periodo_ativo.centro_custo
        else []
    )
    cursos = (
        Curso.query.filter_by(ativo=True, unidade_id=unidade_id or turma_obj.unidade_id)
        .order_by(Curso.nome)
        .all()
    )
    if turma_obj.curso and not turma_obj.curso.ativo:
        cursos.append(turma_obj.curso)
        cursos.sort(key=lambda curso: curso.nome.casefold())
    periodos_centros_edit = {
        str(p.id): (
            [c.strip() for c in p.centro_custo.split(",")] if p.centro_custo else []
        )
        for p in periodos
    }
    tem_lancamentos = bool(
        Frequencia.query.filter_by(turma_id=id).first()
        or RegistroAula.query.filter_by(turma_id=id).first()
    )
    return render_template(
        "turmas/editar.html",
        turma=turma_obj,
        professores=professores,
        programas=programas,
        periodos=periodos,
        periodo_ativo=periodo_ativo,
        periodos_centros_edit=periodos_centros_edit,
        centros_custo=centros_custo,
        cursos=cursos,
        tem_lancamentos=tem_lancamentos,
    )


# ---------------------------------------------------------------------------
# Onda 4 — Fase 2: ofertas de curso na turma (TurmaCurso), cadastro incremental
# e regra do curso principal. As colunas legadas de Turma seguem intocadas
# aqui; o espelhamento controlado vive em app/services/turma_curso.py.
# ---------------------------------------------------------------------------


def _turma_para_ofertas(id):
    """Carrega a turma validando papel e unidade (padrão das rotas de turmas)."""
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)
    turma_obj = db.session.get(Turma, id)
    if turma_obj is None:
        abort(404)
    assert_unidade_context(turma_obj.unidade_id, get_unidade_id())
    return turma_obj


def _dados_oferta_form(form, turma_obj):
    """Extrai os campos de oferta do POST usando os mesmos parseadores do
    cadastro de turma (dias em CSV, datas/horas nativas — Onda 2A)."""
    dias = ", ".join([d for d in form.getlist("dias_semana") if d]) or None
    periodo_obj = turma_obj.periodo_letivo
    data_inicio = parse_date(form.get("data_inicio"))
    data_fim = parse_date(form.get("data_fim"))
    if periodo_obj:
        if data_inicio and data_inicio < periodo_obj.data_inicio:
            raise ValueError(
                "A data de início não pode ser anterior ao início do período letivo."
            )
        if data_fim and data_fim > periodo_obj.data_fim:
            raise ValueError(
                "A data de término não pode ser posterior ao fim do período letivo."
            )
    centro_custo = form.get("centro_custo") or None
    if centro_custo and periodo_obj and periodo_obj.centro_custo:
        centros_disponiveis = [
            c.strip() for c in periodo_obj.centro_custo.split(",")
        ]
        if centros_disponiveis and centro_custo not in centros_disponiveis:
            raise ValueError("Centro de custo inválido para o período selecionado.")
    return {
        "curso_id": _parse_int_arg(form.get("curso_id")),
        "principal": form.get("principal") == "on",
        "professor_id": _parse_int_arg(form.get("professor_id")),
        "turno": form.get("turno") or None,
        "dias_semana": dias,
        "hora_inicio": parse_time(form.get("hora_inicio")),
        "hora_fim": parse_time(form.get("hora_fim")),
        "data_inicio": data_inicio,
        "data_fim": data_fim,
        "centro_custo": centro_custo,
    }


@bp.route("/turma/<int:id>/ofertas")
@login_required
def turma_ofertas(id):
    """Tela de cursos da turma: lista de ofertas + formulário incremental."""
    turma_obj = _turma_para_ofertas(id)
    unidade_id = turma_obj.unidade_id

    professores = (
        User.query.filter_by(role=UserRole.PROFESSOR.value, unidade_id=unidade_id)
        .order_by(User.name)
        .all()
    )
    ids_ofertados = {o.curso_id for o in ofertas_ativas(turma_obj.id)}
    cursosDisponiveis = [
        c for c in Curso.query.filter_by(ativo=True, unidade_id=unidade_id)
        .order_by(Curso.nome).all()
        if c.id not in ids_ofertados
    ]
    centros = (
        [c.strip() for c in turma_obj.periodo_letivo.centro_custo.split(",")]
        if turma_obj.periodo_letivo and turma_obj.periodo_letivo.centro_custo
        else []
    )
    return render_template(
        "turmas/ofertas.html",
        turma=turma_obj,
        ofertas=TurmaCurso.query.filter_by(turma_id=id)
        .order_by(TurmaCurso.ativo.desc(), TurmaCurso.id)
        .all(),
        professores=professores,
        cursosDisponiveis=cursosDisponiveis,
        centros=centros,
        dias_semana=["Segunda", "Terça", "Quarta", "Quinta", "Sexta", "Sábado"],
    )


@bp.route("/turma/<int:id>/ofertas/nova", methods=["POST"])
@login_required
def turma_oferta_nova(id):
    """Adiciona uma oferta de curso à turma (cadastro incremental, sem limite)."""
    turma_obj = _turma_para_ofertas(id)
    try:
        dados = _dados_oferta_form(request.form, turma_obj)
        if dados["curso_id"] is None:
            raise ValueError("Selecione um curso para adicionar à turma.")
        nome_curso = db.session.get(Curso, dados["curso_id"]).nome
        adicionar_oferta(turma_obj, **dados)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=id))

    flash(
        f"Curso '{nome_curso}' adicionado à turma. "
        "Deseja adicionar outro curso?",
        "success",
    )
    return redirect(url_for("registros.turma_ofertas", id=id))


@bp.route("/turma/oferta/<int:oferta_id>/editar", methods=["POST"])
@login_required
def turma_oferta_editar(oferta_id):
    """Edita os atributos próprios da oferta (professor, horários, vigência)."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    try:
        dados = _dados_oferta_form(request.form, turma_obj)
        dados.pop("principal", None)
        if dados["curso_id"] is None:
            raise ValueError("A oferta precisa estar vinculada a um curso.")
        editar_oferta(oferta, **dados)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))
    flash(f"Oferta '{oferta.curso.nome}' atualizada na turma.", "success")
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/oferta/<int:oferta_id>/principal", methods=["POST"])
@login_required
def turma_oferta_principal(oferta_id):
    """Define o curso principal da turma em troca atômica."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    try:
        definir_principal(oferta)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))
    flash(
        f"'{oferta.curso.nome}' agora é o curso principal da turma.", "success"
    )
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/oferta/<int:oferta_id>/desativar", methods=["POST"])
@login_required
def turma_oferta_desativar(oferta_id):
    """Remove o curso da turma (soft delete); histórico de inscrições preservado."""
    oferta = db.session.get(TurmaCurso, oferta_id)
    if oferta is None:
        abort(404)
    turma_obj = _turma_para_ofertas(oferta.turma_id)
    try:
        desativar_oferta(oferta)
    except ValueError as erro:
        flash(str(erro), "warning")
        return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))
    flash(f"O curso '{oferta.curso.nome}' foi removido da turma.", "success")
    return redirect(url_for("registros.turma_ofertas", id=turma_obj.id))


@bp.route("/turma/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_turma(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    turma_obj = db.session.get(Turma, id)
    if turma_obj:
        try:
            turma_obj.ativo = False
            for aluno in turma_obj.alunos.all():
                turma_obj.alunos.remove(aluno)
            Frequencia.query.filter_by(turma_id=id).delete(synchronize_session=False)
            RegistroAula.query.filter_by(turma_id=id).delete(synchronize_session=False)
            db.session.commit()
            flash(
                f"Lógica Desativada: '{turma_obj.nome}' transferida para Storage Arquivo.",
                "success",
            )
        except Exception:
            db.session.rollback()
            flash("Falha ao inativar ligações.", "danger")

    return redirect(url_for("registros.turma"))


@bp.route("/turmas/carga-horaria")
@login_required
def carga_horaria_turmas():
    """
    Exibe a listagem de cursos com descrição, temas associados,
    professores que já foram associados ao curso (que seguiram associados
    até o fim do período letivo da turma) e percentual de presença
    do curso nas turmas de qualquer período até seu encerramento.
    Mantém filtros de Unidade, Período Letivo, Professor e Curso.
    """
    if current_user.role not in ["admin", "pedagogico", "gerencia", "secretaria"]:
        abort(403)

    from app.models import TemaAula

    hoje = date.today()
    unidade_id = get_unidade_id()
    unidade_id_filtro = request.args.get("unidade_id", type=int)
    periodo_id = request.args.get("periodo_id", type=int)
    professor_id = request.args.get("professor_id", type=int)
    curso_id = request.args.get("curso_id", type=int)
    status_periodo = request.args.get("status_periodo", type=str)

    # Para usuários globais, usa o filtro de unidade; para locais, usa fixo
    unidade_efetiva = unidade_id_filtro if current_user.role in ["admin", "gerencia"] else unidade_id

    # Determina o status da visualização de forma estrita e alternada: 'vigente' ou 'concluido'
    periodo_selecionado = db.session.get(PeriodoLetivo, periodo_id) if periodo_id else None
    if periodo_selecionado:
        status_view = "vigente" if periodo_selecionado.data_fim >= hoje else "concluido"
    elif status_periodo == "concluido":
        status_view = "concluido"
    else:
        # Padrão: períodos vigentes (em andamento)
        status_view = "vigente"

    # Condições de vigência de turmas baseadas no período letivo ou datas próprias
    cond_vigente = db.or_(
        Turma.periodo_letivo_id.in_(
            select(PeriodoLetivo.id).where(PeriodoLetivo.data_fim >= hoje)
        ),
        db.and_(Turma.periodo_letivo_id.is_(None), db.or_(Turma.data_fim >= hoje, Turma.data_fim.is_(None))),
    )
    cond_concluido = db.or_(
        Turma.periodo_letivo_id.in_(
            select(PeriodoLetivo.id).where(PeriodoLetivo.data_fim < hoje)
        ),
        db.and_(Turma.periodo_letivo_id.is_(None), Turma.data_fim < hoje),
    )

    # Condição da modalidade ativa
    cond_status = cond_vigente if status_view == "vigente" else cond_concluido

    # Total geral de turmas da modalidade ativa no escopo (denominador do percentual)
    stmt_geral = select(db.func.count(Turma.id)).where(
        Turma.ativo == True,
        cond_status,
    )
    if unidade_efetiva:
        stmt_geral = stmt_geral.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_geral = stmt_geral.where(Turma.periodo_letivo_id == periodo_id)
    total_geral_turmas = db.session.execute(stmt_geral).scalar() or 0

    # Consulta dos Cursos disponíveis
    stmt_cursos = select(Curso).where(Curso.ativo == True)
    if unidade_efetiva:
        stmt_cursos = stmt_cursos.where(Curso.unidade_id == unidade_efetiva)
    if curso_id:
        stmt_cursos = stmt_cursos.where(Curso.id == curso_id)

    # Restringe aos cursos ofertados no período ou na modalidade ativa
    if periodo_id:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    Turma.periodo_letivo_id == periodo_id,
                )
            )
        )
    else:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    cond_status,
                )
            )
        )

    if professor_id:
        stmt_cursos = stmt_cursos.where(
            Curso.id.in_(
                select(Turma.curso_id).where(
                    Turma.ativo == True,
                    Turma.professor_id == professor_id,
                )
            )
        )

    cursos_base = db.session.execute(stmt_cursos.order_by(Curso.nome)).scalars().all()

    cursos_dados = []
    for c in cursos_base:
        # 1. Temas associados ao curso
        temas = (
            TemaAula.query.filter_by(curso_id=c.id, ativo=True)
            .order_by(TemaAula.ordem, TemaAula.id)
            .all()
        )

        # 2. Professores da modalidade ativa (vigente ou concluído)
        stmt_prof = (
            select(User)
            .join(Turma, Turma.professor_id == User.id)
            .where(
                Turma.curso_id == c.id,
                Turma.ativo == True,
                cond_status,
            )
        )
        if unidade_efetiva:
            stmt_prof = stmt_prof.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_prof = stmt_prof.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_prof = stmt_prof.where(Turma.professor_id == professor_id)

        profs_ativos = (
            db.session.execute(stmt_prof.distinct().order_by(User.name))
            .scalars()
            .all()
        )

        # 3. Turmas deste curso na modalidade ativa
        stmt_turmas_c = select(db.func.count(Turma.id)).where(
            Turma.curso_id == c.id,
            Turma.ativo == True,
            cond_status,
        )
        if unidade_efetiva:
            stmt_turmas_c = stmt_turmas_c.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_turmas_c = stmt_turmas_c.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_turmas_c = stmt_turmas_c.where(Turma.professor_id == professor_id)

        total_turmas_c = db.session.execute(stmt_turmas_c).scalar() or 0
        percentual = (
            round((total_turmas_c / total_geral_turmas) * 100, 1)
            if total_geral_turmas > 0
            else 0.0
        )

        # 4. C.H. Total: soma de carga_horaria_total de todas as turmas do curso
        #    no filtro ativo. Carrega apenas turmas com hora configurada.
        stmt_turmas_ch = select(Turma).where(
            Turma.curso_id == c.id,
            Turma.ativo == True,
            cond_status,
            Turma.hora_inicio.isnot(None),
            Turma.hora_fim.isnot(None),
        )
        if unidade_efetiva:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.unidade_id == unidade_efetiva)
        if periodo_id:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.periodo_letivo_id == periodo_id)
        if professor_id:
            stmt_turmas_ch = stmt_turmas_ch.where(Turma.professor_id == professor_id)

        turmas_ch = db.session.execute(stmt_turmas_ch).scalars().all()
        ch_total_minutos = sum(
            (t.carga_horaria_total or 0) for t in turmas_ch
        ) or None  # None → "—" no template via formatar_ch

        cursos_dados.append({
            "curso": c,
            "temas": temas,
            "professores": profs_ativos,
            "total_turmas": total_turmas_c,
            "percentual_presenca": percentual,
            "ch_total_minutos": ch_total_minutos,
        })

    # ── DROPDOWNS DE FILTROS CASCATEADOS PELO FILTRO-MESTRE DE VIGÊNCIA ──
    # 1. Unidades (apenas para papéis globais)
    if current_user.role in ["admin", "gerencia"]:
        from app.models import Unidade
        unidades = Unidade.query.order_by(Unidade.nome).all()
    else:
        unidades = []

    # 2. Períodos Letivos: filtrados estritamente pela modalidade ativa (vigente ou concluído)
    stmt_periodos = select(PeriodoLetivo).where(PeriodoLetivo.ativo == True)
    if unidade_efetiva:
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.unidade_id == unidade_efetiva)

    if status_view == "vigente":
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.data_fim >= hoje).order_by(
            PeriodoLetivo.data_inicio.asc(), PeriodoLetivo.nome.asc()
        )
    else:
        stmt_periodos = stmt_periodos.where(PeriodoLetivo.data_fim < hoje).order_by(
            PeriodoLetivo.data_fim.desc(), PeriodoLetivo.nome.asc()
        )

    periodos = db.session.execute(stmt_periodos).scalars().all()

    # 3. Professores: apenas professores da unidade escolhida (ou todas se global "Todas")
    # que possuam turmas na modalidade ativa (e no período selecionado, se houver)
    stmt_turmas_prof_filtro = select(Turma.professor_id).where(
        Turma.ativo == True,
        cond_status,
        Turma.professor_id.isnot(None),
    )
    if unidade_efetiva:
        stmt_turmas_prof_filtro = stmt_turmas_prof_filtro.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_turmas_prof_filtro = stmt_turmas_prof_filtro.where(Turma.periodo_letivo_id == periodo_id)

    stmt_profs = select(User).where(
        User.role == "professor",
        User.id.in_(stmt_turmas_prof_filtro),
    )
    if unidade_efetiva:
        stmt_profs = stmt_profs.where(User.unidade_id == unidade_efetiva)

    professores = db.session.execute(stmt_profs.order_by(User.name)).scalars().all()

    # 4. Cursos: apenas cursos da unidade escolhida (ou todas se global "Todas")
    # que possuam turmas na modalidade ativa + período + professor selecionados
    stmt_turmas_curso_filtro = select(Turma.curso_id).where(
        Turma.ativo == True,
        cond_status,
        Turma.curso_id.isnot(None),
    )
    if unidade_efetiva:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.unidade_id == unidade_efetiva)
    if periodo_id:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.periodo_letivo_id == periodo_id)
    if professor_id:
        stmt_turmas_curso_filtro = stmt_turmas_curso_filtro.where(Turma.professor_id == professor_id)

    stmt_cursos_dropdown = select(Curso).where(
        Curso.ativo == True,
        Curso.id.in_(stmt_turmas_curso_filtro),
    )
    if unidade_efetiva:
        stmt_cursos_dropdown = stmt_cursos_dropdown.where(Curso.unidade_id == unidade_efetiva)

    cursos = db.session.execute(stmt_cursos_dropdown.order_by(Curso.nome)).scalars().all()

    return render_template(
        "turmas/carga_horaria_curso.html",
        cursos_dados=cursos_dados,
        status_view=status_view,
        status_periodo=status_periodo,
        total_geral_turmas=total_geral_turmas,
        unidades=unidades,
        periodos=periodos,
        professores=professores,
        cursos=cursos,
        unidade_id_filtro=unidade_id_filtro,
        periodo_id=periodo_id,
        professor_id=professor_id,
        curso_id=curso_id,
        formatar_ch=formatar_ch,
        hoje=hoje,
    )


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
    return render_template(
        "turmas/observacoes.html",
        obs=observacoes,
        turma=turma_obj,
        historico=observacoes,
    )


@bp.route("/turma/<int:id>/imprimir-pauta")
@login_required
def imprimir_pauta(id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        if current_user.role != "professor":
            abort(403)

    turma = Turma.query.get_or_404(id)
    assert_unidade_context(turma.unidade_id, get_unidade_id())
    if current_user.role == "professor" and turma.professor_id != current_user.id:
        abort(403)

    try:
        ctx = carregar_contexto_turma(id, pauta_impressa=True)
    except Exception:
        flash(
            "Não há informações completas para montar arquitetura de pauta.", "warning"
        )
        return redirect(url_for("registros.ver_turma", id=id))

    mes_selecionado = request.args.get("mes")
    if mes_selecionado:
        ctx["datas"] = [data for data in ctx["datas"] if f"-{mes_selecionado}-" in data]
        nomes_meses = {
            "01": "Janeiro", "02": "Fevereiro", "03": "Março", "04": "Abril",
            "05": "Maio", "06": "Junho", "07": "Julho", "08": "Agosto",
            "09": "Setembro", "10": "Outubro", "11": "Novembro", "12": "Dezembro",
        }
        ctx["mes_nome"] = nomes_meses.get(mes_selecionado, mes_selecionado)

    # Onda 2A: Frequencia.data é `date`, mas ctx["datas"] é list[str].
    # Converter para date antes do IN, senão nunca casa.
    datas_ctx = ctx["datas"]
    datas_date = [parse_date(d) for d in datas_ctx]
    datas_date = [d for d in datas_date if d is not None]

    registros = (
        Frequencia.query.filter(
            Frequencia.turma_id == id,
            Frequencia.data.in_(datas_date),
        ).all()
        if datas_date
        else []
    )

    # O template indexa por string. Mantemos as chaves no formato 'YYYY-MM-DD'.
    frequencias = {}
    for registro in registros:
        chave = registro.data.strftime('%Y-%m-%d')
        frequencias.setdefault(chave, {})[registro.aluno_id] = registro.conceito

    return render_template(
        "frequencia/imprimir_pauta.html",
        **ctx,
        frequencias=frequencias,
        now=datetime.now(),
    )

"""
================================================================================
CORE.PY - Registros pedagógicos (form legado, painel do professor, frequência,
          cursos, planejamento, níveis e temas)
================================================================================

NOTA ONDA 2B (limpeza)
    Comparações de `current_user.role` usam `UserRole` do `app.models.enums`
    em vez de strings soltas. Autocomplete e rename seguro.
================================================================================
"""

import json

from flask import flash, render_template, url_for, request, redirect, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.orm import joinedload
from datetime import datetime, date

from app.database import db
from app.models import (
    Registro,
    Turma,
    Aluno,
    Frequencia,
    RegistroAula,
    TemaAula,
    PerguntaConselho,
    User,
    ConfiguracaoSistema,
    PeriodoLetivo,
    Inscricao,
    Curso,
)
from app.models.enums import UserRole
from app.utils.datetime_parse import parse_date
from app.utils.logica import (
    calcular_carga_horaria_curso,
    calcular_estatisticas_frequencia,
    carregar_contexto_turma,
    carregar_frequencias,
    get_unidade_id,
    salvar_frequencia,
)
from . import bp
from .shared import assert_unidade_context


# ---------------------------------------------------------------------------
# FORMULÁRIO PRINCIPAL DE REGISTRO (Legacy Support)
# ---------------------------------------------------------------------------
@bp.route('/form', methods=['GET', 'POST'])
@login_required
def form():
    """Salva dados legados em estrutura JSON na tabela Registro."""
    if request.method == 'POST':
        try:
            novo = Registro(
                educador_id=current_user.id,
                turma=request.form.get('turma'),
                mes=request.form.get('mes'),
                turno=request.form.get('turno'),
                dados_json=json.dumps(request.form.to_dict())
            )
            db.session.add(novo)
            db.session.commit()
            return redirect(url_for('main.painel'))
        except Exception as e:
            from app.utils.errors import flash_and_log

            db.session.rollback()
            flash_and_log(e, location='registros.form', hint='db')

    turmas = Turma.get_ativas()
    return render_template('form.html', turmas=turmas)


@bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    registro = db.get_or_404(Registro, id)

    if request.method == 'POST':
        try:
            registro.turma = request.form['turma']
            registro.mes   = request.form['mes']
            registro.turno = request.form['turno']
            db.session.commit()
            flash("Atualização do Registro Efetivada", "success")
            return redirect(url_for('registros.form'))
        except Exception:
            db.session.rollback()
            flash("Conflito interno ao gravar nova string JSON.", "danger")

    return render_template('editar.html', registro=registro)


@bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir(id):
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    try:
        registro = db.get_or_404(Registro, id)
        db.session.delete(registro)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("O banco recusou a deleção do bloco de registro.", "warning")

    return redirect(url_for('registros.form'))


# ---------------------------------------------------------------------------
# PROFESSORES (Fluxo de Sala de Aula)
# ---------------------------------------------------------------------------
@bp.route('/professor/painel')
@login_required
def painel_professor():
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PROFESSOR,
        UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        flash("Permissões insuficientes. Autenticação RBAC Negou Rota.", "warning")
        return redirect(url_for('main.painel'))

    programa_selecionado = request.args.get('programa', 'Todos')
    unidade_id = get_unidade_id()

    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)
    lista_programas = db.session.execute(stmt_prog).scalars().all()

    if current_user.role in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        stmt = select(Turma).options(joinedload(Turma.professor)).where(Turma.ativo == True)
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)
        if programa_selecionado != 'Todos':
            stmt = stmt.where(Turma.programa == programa_selecionado)
    else:
        stmt = select(Turma).where(
            Turma.professor_id == current_user.id,
            Turma.ativo == True
        )
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)

    todas_turmas = db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()

    ids_turmas = [t.id for t in todas_turmas]
    total_alunos = 0
    if ids_turmas:
        total_alunos = (
            Aluno.query.join(Inscricao)
            .filter(
                Inscricao.turma_id.in_(ids_turmas),
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .distinct(Aluno.id)
            .count()
        )

    return render_template('dashboard/professor.html',
                           turmas=todas_turmas,
                           total_alunos=total_alunos,
                           lista_programas=lista_programas,
                           programa_ativo=programa_selecionado,
                           is_readonly=current_user.role == UserRole.SECRETARIA)


@bp.route('/frequencia', methods=['GET', 'POST'])
@login_required
def frequencia():
    """
    Controlador de Submissões em Lote do Diário Online.
    Utiliza Atomic Transactions oriundas do utilitário logica.py.
    """
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO,
        UserRole.PROFESSOR, UserRole.SECRETARIA,
    ):
        abort(403)

    if request.method == 'POST':
        if current_user.role == UserRole.SECRETARIA:
            abort(403)

        turma_post_id = request.form.get('turma', '')
        if current_user.role == UserRole.PROFESSOR and turma_post_id:
            turma_post = db.session.get(Turma, int(turma_post_id)) if turma_post_id.isdigit() else None
            if not turma_post or turma_post.professor_id != current_user.id:
                abort(403)

        data_post = (request.form.get('data') or request.form.get('data_hidden') or '').strip()
        if turma_post_id.isdigit() and data_post:
            contexto = carregar_contexto_turma(int(turma_post_id))
            if data_post not in contexto.get('datas', []):
                flash('A data informada não pertence ao calendário válido da turma.', 'warning')
                return redirect(url_for('registros.frequencia', turma_id=turma_post_id))

        turma_id, data = salvar_frequencia(request.form)
        if not data:
            flash("Preencha a data da aula antes de salvar.", "warning")
            return redirect(url_for('registros.frequencia', turma_id=turma_post_id or ''))

        flash('Frequência salva com sucesso!', 'success')
        return redirect(url_for('registros.frequencia', turma_id=turma_id, data=data))

    turma_id_raw = request.args.get('turma_id')
    turma_id = int(turma_id_raw) if turma_id_raw and str(turma_id_raw).isdigit() else None
    data     = request.args.get('data')

    unidade_id = get_unidade_id()

    if current_user.role == UserRole.PROFESSOR:
        stmt = select(Turma).where(
            Turma.ativo == True,
            Turma.professor_id == current_user.id
        )
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)
        turmas = db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()
    else:
        turmas = Turma.get_ativas()
        if unidade_id:
            turmas = [t for t in turmas if t.unidade_id == unidade_id]

    if turma_id and current_user.role == UserRole.PROFESSOR:
        turma_ids_permitidos = {t.id for t in turmas}
        if turma_id not in turma_ids_permitidos:
            flash('Você não tem permissão para acessar esta turma.', 'danger')
            return redirect(url_for('registros.frequencia'))

    ctx = {}
    freqs = {}
    tema_sel = None
    obs = ""

    if turma_id:
        ctx = carregar_contexto_turma(turma_id)
        if data:
            freqs, tema_sel, obs = carregar_frequencias(turma_id, data)

        for aluno in ctx.get('alunos', []):
            registros = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_id=turma_id
            ).all()
            if not registros:
                registros = Frequencia.query.filter_by(aluno_id=aluno.id, turma_id=None).all()

            estatisticas = calcular_estatisticas_frequencia(
                registro.conceito for registro in registros
            )
            aluno.estats_freq = type('E', (), {
                'presenca': estatisticas['presenca_percentual'],
                'falta': estatisticas['falta_percentual'],
                'justificada': estatisticas['justificada_percentual'],
                'justificadas': estatisticas['justificadas'],
                'total_aulas': estatisticas['total'],
            })()

            insc = Inscricao.query.filter_by(
                aluno_id=aluno.id, turma_id=int(turma_id)
            ).first()
            aluno.pode_receber_frequencia = bool(insc and insc.ativo)

    return render_template('frequencia/lancar.html',
                           turmas=turmas,
                           turma_id=turma_id,
                           data=data,
                           frequencias=freqs,
                           tema_selecionado=tema_sel,
                           obs_salva=obs,
                           turma=ctx.get('turma'),
                           alunos=ctx.get('alunos', []),
                           datas=ctx.get('datas', []),
                           temas=ctx.get('temas', []),
                           meses=ctx.get('meses', []),
                           is_readonly=current_user.role == UserRole.SECRETARIA)


@bp.route('/frequencia_relatorio')
@login_required
def frequencia_relatorio():
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    turma_id = request.args.get('turma')

    # Onda 2A: Frequencia.data é `date`. Os parâmetros da URL chegam como
    # string e precisam ser normalizados antes de filtrar, senão o filtro
    # nunca casa (date == str).
    data_inicio_raw = request.args.get('inicio')
    data_fim_raw = request.args.get('fim')
    data_inicio = parse_date(data_inicio_raw)
    data_fim = parse_date(data_fim_raw)

    unidade_id = get_unidade_id()
    turmas_query = Turma.query.filter_by(ativo=True)
    if unidade_id:
        turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
    turmas = turmas_query.order_by(Turma.nome).all()
    resultado         = []
    turma_selecionada = None

    if turma_id:
        turma_selecionada = next(
            (turma for turma in turmas if turma.id == int(turma_id)), None
        )
        if not turma_selecionada:
            abort(404)
        alunos = db.session.execute(
            select(Aluno)
            .join(Inscricao, Inscricao.aluno_id == Aluno.id)
            .where(
                Inscricao.turma_id == turma_selecionada.id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .order_by(Aluno.nome)
        ).scalars().all()

        for aluno in alunos:
            stmt = select(Frequencia.conceito).where(
                Frequencia.aluno_id == aluno.id,
                Frequencia.turma_id == turma_selecionada.id,
            )
            if data_inicio:
                stmt = stmt.where(Frequencia.data >= data_inicio)
            if data_fim:
                stmt = stmt.where(Frequencia.data <= data_fim)

            estatisticas = calcular_estatisticas_frequencia(
                db.session.execute(stmt).scalars().all()
            )

            resultado.append({
                "nome": aluno.nome,
                "total": estatisticas['total'],
                "presencas": estatisticas['presencas'],
                "justificadas": estatisticas['justificadas'],
                "percentual": estatisticas['presenca_percentual'],
            })

    # Preserva as strings originais no template (inputs type="date" esperam string).
    return render_template('frequencia/relatorio.html',
                           dados=resultado,
                           turmas=turmas,
                           turma_id=turma_id,
                           turma_selecionada=turma_selecionada,
                           inicio=data_inicio_raw or '',
                           fim=data_fim_raw or '')


# ---------------------------------------------------------------------------
# CURSOS
# ---------------------------------------------------------------------------

@bp.route('/cursos', methods=['GET'])
@login_required
def listar_cursos():
    """Retorna JSON com os cursos da unidade — usado pelo modal de planejamento."""
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        abort(403)
    q = Curso.query.filter_by(ativo=True, unidade_id=unidade_id)
    cursos = q.order_by(Curso.nome).all()
    return jsonify([
        {
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao or '',
            'carga_horaria': c.carga_horaria or '',
            **calcular_carga_horaria_curso(c),
        }
        for c in cursos
    ])


@bp.route('/cursos/novo', methods=['POST'])
@login_required
def novo_curso():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        return jsonify({'success': False, 'message': 'Usuário sem unidade definida.'}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Dados do curso inválidos.'}), 400
    nome = data.get('nome')
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400
    nome = nome.strip()
    descricao = data.get('descricao')
    descricao = descricao.strip() if isinstance(descricao, str) else ''
    carga = data.get('carga_horaria')
    try:
        carga_horaria = int(carga) if carga not in (None, '') else None
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Carga horária inválida.'}), 400
    if carga_horaria is not None and not 1 <= carga_horaria <= 9999:
        return jsonify({'success': False, 'message': 'Carga horária deve estar entre 1 e 9999 horas.'}), 400

    curso = Curso(
        nome=nome,
        descricao=descricao or None,
        carga_horaria=int(carga_horaria) if carga_horaria else None,
        unidade_id=unidade_id
    )
    try:
        db.session.add(curso)
        db.session.commit()
        return jsonify({
            'success': True,
            'id': curso.id,
            'nome': curso.nome,
            'descricao': curso.descricao or '',
            'carga_horaria': curso.carga_horaria or '',
            **calcular_carga_horaria_curso(curso),
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.novo_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


@bp.route('/cursos/<int:curso_id>/editar', methods=['POST'])
@login_required
def editar_curso(curso_id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    assert_unidade_context(curso.unidade_id, unidade_id)

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Dados do curso inválidos.'}), 400
    nome = data.get('nome')
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400
    nome = nome.strip()
    descricao = data.get('descricao')
    descricao = descricao.strip() if isinstance(descricao, str) else ''
    carga = data.get('carga_horaria')
    try:
        carga_horaria = int(carga) if carga not in (None, '') else None
    except (TypeError, ValueError):
        return jsonify({'success': False, 'message': 'Carga horária inválida.'}), 400
    if carga_horaria is not None and not 1 <= carga_horaria <= 9999:
        return jsonify({'success': False, 'message': 'Carga horária deve estar entre 1 e 9999 horas.'}), 400

    curso.nome = nome
    curso.descricao = descricao or None
    curso.carga_horaria = carga_horaria
    try:
        db.session.commit()
        return jsonify({
            'success': True, 'id': curso.id, 'nome': curso.nome,
            'descricao': curso.descricao or '',
            'carga_horaria': curso.carga_horaria or '',
            **calcular_carga_horaria_curso(curso),
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.editar_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


@bp.route('/cursos/<int:curso_id>/excluir', methods=['POST'])
@login_required
def excluir_curso(curso_id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    assert_unidade_context(curso.unidade_id, unidade_id)

    curso.ativo = False
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.excluir_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


# ---------------------------------------------------------------------------
# PLANEJAMENTO DE TEMAS
# ---------------------------------------------------------------------------

@bp.route('/planejamento', methods=['GET', 'POST'])
@login_required
def planejamento():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)

    unidade_id = get_unidade_id()
    if current_user.role == UserRole.SECRETARIA and unidade_id is None:
        abort(403)

    if request.method == 'POST':
        tipo_post = request.form.get('tipo_post', 'tema')

        if tipo_post == 'nivel':
            from app.models import Nivel
            nome_nivel = request.form.get('nome_nivel', '').strip()
            if nome_nivel:
                nivel_unidade_id = get_unidade_id()
                existente = Nivel.query.filter_by(
                    nome=nome_nivel,
                    unidade_id=nivel_unidade_id,
                ).first()
                if existente:
                    flash("Já existe um nível com esse nome nesta unidade.", 'warning')
                else:
                    try:
                        db.session.add(Nivel(
                            nome=nome_nivel,
                            ativo=True,
                            unidade_id=nivel_unidade_id,
                        ))
                        db.session.commit()
                        flash(f"Nível '{nome_nivel}' adicionado com sucesso!", 'success')
                    except Exception:
                        db.session.rollback()
                        flash("Erro ao salvar nível.", 'danger')
            else:
                flash("Informe o nome do nível.", 'warning')
            return redirect(url_for('registros.planejamento'))

        curso_id  = request.form.get('curso_id')
        titulo_tema = request.form.get('titulo')
        if curso_id and titulo_tema:
            try:
                curso = db.get_or_404(Curso, int(curso_id))
                if current_user.role != UserRole.ADMIN:
                    assert_unidade_context(curso.unidade_id, unidade_id)

                ultima_ordem = db.session.query(func.max(TemaAula.ordem)).filter_by(
                    curso_id=int(curso_id)
                ).scalar()
                nova_ordem = (ultima_ordem or 0) + 1

                db.session.add(TemaAula(
                    curso_id=int(curso_id),
                    titulo=titulo_tema,
                    ordem=nova_ordem,
                    unidade_id=get_unidade_id()
                ))
                db.session.commit()
                flash(f"Tema '{titulo_tema}' adicionado ao curso '{curso.nome if curso else ''}'!", "success")
            except Exception as e:
                from app.utils.errors import flash_and_log

                db.session.rollback()
                flash_and_log(e, location='registros.planejamento_tema_salvar', hint='db')
        elif not curso_id:
            flash("Selecione um curso.", "warning")
        elif not titulo_tema:
            flash("Informe o título do tema.", "warning")
        return redirect(url_for('registros.planejamento'))

    conf_i = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho').first()
    conf_f = ConfiguracaoSistema.query.filter_by(chave='fim_conselho').first()

    turmas = Turma.get_ativas()
    if unidade_id:
        turmas = [t for t in turmas if t.unidade_id == unidade_id]

    prog_filtro = request.args.get('programa', 'Todos')
    programas   = sorted({t.programa for t in turmas if t.programa})

    filtro_curso = request.args.get('curso_id', '').strip()
    try:
        curso_id_filtro = int(filtro_curso) if filtro_curso else None
    except ValueError:
        curso_id_filtro = None
        filtro_curso = ''
    busca_tema = request.args.get('q', '').strip()

    q_temas = TemaAula.query.join(Curso, TemaAula.curso_id == Curso.id).filter(
        TemaAula.curso_id.isnot(None)
    )
    if unidade_id:
        q_temas = q_temas.filter(Curso.unidade_id == unidade_id)
    if curso_id_filtro:
        q_temas = q_temas.filter(TemaAula.curso_id == curso_id_filtro)
    if busca_tema:
        termo = f'%{busca_tema}%'
        q_temas = q_temas.filter(or_(
            TemaAula.titulo.ilike(termo),
            Curso.nome.ilike(termo),
            cast(TemaAula.ordem, String).ilike(termo),
        ))

    pagina_temas = max(1, request.args.get('page', 1, type=int) or 1)
    paginacao = q_temas.order_by(
        TemaAula.curso_id, TemaAula.ordem, TemaAula.id
    ).paginate(page=pagina_temas, per_page=25, error_out=False)
    if paginacao.pages and pagina_temas > paginacao.pages:
        pagina_temas = paginacao.pages
        paginacao = q_temas.order_by(
            TemaAula.curso_id, TemaAula.ordem, TemaAula.id
        ).paginate(page=pagina_temas, per_page=25, error_out=False)
    from app.models import Nivel
    niveis = Nivel.query.order_by(Nivel.nome).all()
    if unidade_id:
        niveis = [n for n in niveis if n.unidade_id == unidade_id or n.unidade_id is None]

    q_periodos = PeriodoLetivo.query.filter_by(ativo=True)
    if unidade_id:
        q_periodos = q_periodos.filter_by(unidade_id=unidade_id)
    periodos_ativos = q_periodos.order_by(PeriodoLetivo.data_inicio.desc()).all()

    cursos = []
    if unidade_id:
        cursos = Curso.query.filter_by(
            ativo=True, unidade_id=unidade_id
        ).order_by(Curso.nome).all()
    curso_cores = {curso.id: indice % 10 for indice, curso in enumerate(cursos)}
    cargas_curso = {curso.id: calcular_carga_horaria_curso(curso) for curso in cursos}

    return render_template('planejamento/planejamento.html',
                           turmas=turmas,
                           temas=paginacao.items,
                           paginacao=paginacao,
                           busca_tema=busca_tema,
                           programas=programas,
                           prog_filtro=prog_filtro,
                           filtro_curso=filtro_curso,
                           niveis=niveis,
                           periodos_ativos=periodos_ativos,
                           cursos=cursos,
                           curso_cores=curso_cores,
                           cargas_curso=cargas_curso,
                           unidade_id=unidade_id,
                           data_inicio_atual=conf_i.valor if conf_i else '',
                           data_fim_atual=conf_f.valor if conf_f else '')


# ---------------------------------------------------------------------------
# TEMAS DE AULA — edição e inativação
# ---------------------------------------------------------------------------

@bp.route('/planejamento/tema/editar/<int:id>', methods=['POST'])
@login_required
def editar_tema(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    if current_user.role != UserRole.ADMIN:
        if current_user.role == UserRole.SECRETARIA and unidade_id is None:
            abort(403)
        curso = db.get_or_404(Curso, tema.curso_id) if tema.curso_id else None
        assert_unidade_context(tema.unidade_id or (curso.unidade_id if curso else None), unidade_id)

    novo_titulo = request.form.get('titulo', '').strip()
    nova_ordem = request.form.get('ordem')

    if novo_titulo:
        try:
            tema.titulo = novo_titulo
            if nova_ordem:
                tema.ordem = int(nova_ordem)

            db.session.flush()

            temas_curso = TemaAula.query.filter_by(curso_id=tema.curso_id).order_by(
                TemaAula.ordem,
                TemaAula.id != tema.id,
                TemaAula.id
            ).all()

            for i, t in enumerate(temas_curso, start=1):
                t.ordem = i

            db.session.commit()
            flash("Tema atualizado com sucesso!", 'success')
        except Exception:
            db.session.rollback()
            flash("Erro ao atualizar tema.", 'danger')
    else:
        flash("Título não pode ser vazio.", 'warning')
    return redirect(url_for('registros.planejamento'))


@bp.route('/planejamento/tema/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_tema(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    if current_user.role != UserRole.ADMIN:
        if current_user.role == UserRole.SECRETARIA and unidade_id is None:
            abort(403)
        curso = db.get_or_404(Curso, tema.curso_id) if tema.curso_id else None
        assert_unidade_context(tema.unidade_id or (curso.unidade_id if curso else None), unidade_id)
    try:
        tema.ativo = not tema.ativo
        db.session.commit()
        status = 'ativado' if tema.ativo else 'inativado'
        flash(f"Tema '{tema.titulo}' {status}!", 'success')
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar status do tema.", 'danger')
    return redirect(url_for('registros.planejamento'))


# ---------------------------------------------------------------------------
# NÍVEIS — edição e inativação
# ---------------------------------------------------------------------------

@bp.route('/planejamento/nivel/editar/<int:id>', methods=['POST'])
@login_required
def editar_nivel(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    from app.models import Nivel
    nivel = db.get_or_404(Nivel, id)
    if current_user.role != UserRole.ADMIN:
        unidade_id = get_unidade_id()
        if current_user.role == UserRole.SECRETARIA and unidade_id is None:
            abort(403)
        assert_unidade_context(nivel.unidade_id, unidade_id)

    novo_nome = request.form.get('nome_nivel', '').strip()
    if novo_nome:
        try:
            nivel.nome = novo_nome
            db.session.commit()
            flash("Nível atualizado com sucesso!", 'success')
        except Exception:
            db.session.rollback()
            flash("Erro ao atualizar nível.", 'danger')
    else:
        flash("O nome do nível não pode ser vazio.", 'warning')
    return redirect(url_for('registros.planejamento'))


@bp.route('/planejamento/nivel/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_nivel(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    from app.models import Nivel
    nivel = db.get_or_404(Nivel, id)
    if current_user.role != UserRole.ADMIN:
        unidade_id = get_unidade_id()
        if current_user.role == UserRole.SECRETARIA and unidade_id is None:
            abort(403)
        assert_unidade_context(nivel.unidade_id, unidade_id)
    try:
        nivel.ativo = not nivel.ativo
        db.session.commit()
        status = 'ativado' if nivel.ativo else 'inativado'
        flash(f"Nível '{nivel.nome}' {status}!", 'success')
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar status do nível.", 'warning')
    return redirect(url_for('registros.planejamento'))


# ---------------------------------------------------------------------------
# TEMAS — impressão
# ---------------------------------------------------------------------------

@bp.route('/planejamento/imprimir-temas')
@login_required
def imprimir_temas():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)

    filtro_curso = request.args.get('curso_id', '').strip()
    try:
        curso_id = int(filtro_curso) if filtro_curso else None
    except ValueError:
        curso_id = None
        filtro_curso = ''

    unidade_id = get_unidade_id()
    if current_user.role == UserRole.SECRETARIA and unidade_id is None:
        abort(403)

    q_cursos = Curso.query.filter_by(ativo=True)
    if unidade_id:
        q_cursos = q_cursos.filter_by(unidade_id=unidade_id)
    todos_cursos = q_cursos.order_by(Curso.nome).all()
    cursos = [curso for curso in todos_cursos if not curso_id or curso.id == curso_id]
    curso_ids = [curso.id for curso in cursos]

    temas = []
    if curso_ids:
        temas = TemaAula.query.filter(
            TemaAula.curso_id.in_(curso_ids),
            TemaAula.ativo == True,
        ).order_by(TemaAula.curso_id, TemaAula.ordem, TemaAula.id).all()

    temas_por_curso = {
        curso.id: [tema for tema in temas if tema.curso_id == curso.id]
        for curso in cursos
    }
    cursos_com_temas = [curso for curso in cursos if temas_por_curso[curso.id]]

    return render_template('planejamento/impressao_temas.html',
                           cursos=cursos_com_temas,
                           todos_cursos=todos_cursos,
                           temas_por_curso=temas_por_curso,
                           filtro_curso=filtro_curso,
                           now=datetime.now())

# ---------------------------------------------------------------------------
# API SERVERSIDE BINDINGS
# ---------------------------------------------------------------------------
@bp.route('/api/alunos/<int:turma_id>')
@login_required
def api_alunos(turma_id):
    """Integrações Async com Frontend AJAX para Fetch de Alunos por ID."""
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
    ):
        abort(403)

    turma = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma.unidade_id, get_unidade_id())
    alunos = turma.alunos.all()
    return jsonify([{"id": a.id, "nome": a.nome} for a in alunos])

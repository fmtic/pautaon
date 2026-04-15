from flask import flash, render_template, url_for, request, redirect, abort, jsonify
from flask_login import login_required, current_user
from app.models import (Registro, Turma, Aluno, Frequencia, RegistroAula,
                    TemaAula, PerguntaConselho, User, ConfiguracaoSistema, PeriodoLetivo,
                    Inscricao, Curso)
from app.database import db
from sqlalchemy import select, func, not_
from sqlalchemy.orm import joinedload
from datetime import datetime, date
from app.utils.logica import carregar_contexto_turma, carregar_frequencias, salvar_frequencia, get_unidade_id
from . import bp
import json


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
            return redirect(url_for('main.dashboard'))
        except Exception as e:
            db.session.rollback()
            flash(f"Falha ao persistir formulário dinâmico: {e}", "danger")

    turmas = Turma.get_ativas()
    return render_template('form.html', turmas=turmas)

@bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    if current_user.role != 'pedagogico':
        abort(403)

    registro = db.get_or_404(Registro, id)

    if request.method == 'POST':
        try:
            registro.turma = request.form['turma']
            registro.mes   = request.form['mes']
            registro.turno = request.form['turno']
            db.session.commit()
            flash("Atualização do Registro Efetivada", "success")
            return redirect(url_for('main.relatorios'))
        except Exception:
            db.session.rollback()
            flash("Conflito interno ao gravar nova string JSON.", "danger")

    return render_template('editar.html', registro=registro)

@bp.route('/excluir/<int:id>')
@login_required
def excluir(id):
    if current_user.role != 'pedagogico':
        abort(403)

    try:
        registro = db.get_or_404(Registro, id)
        db.session.delete(registro)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("O banco recusou a deleção do bloco de registro.", "warning")
        
    return redirect(url_for('main.relatorios'))


# ---------------------------------------------------------------------------
# PROFESSORES (Fluxo de Sala de Aula)
# ---------------------------------------------------------------------------
@bp.route('/professor/painel')
@login_required
def painel_professor():
    if current_user.role not in ['admin', 'professor', 'pedagogico', 'secretaria']:
        flash("Permissões insuficientes. Autenticação RBAC Negou Rota.", "warning")
        return redirect(url_for('main.dashboard'))

    programa_selecionado = request.args.get('programa', 'Todos')
    unidade_id = get_unidade_id()

    # Programas disponíveis respeitando contexto de unidade
    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)
    lista_programas = db.session.execute(stmt_prog).scalars().all()

    if current_user.role in ['admin', 'pedagogico', 'secretaria']:
        # Vê todas as turmas ativas da unidade
        stmt = select(Turma).options(joinedload(Turma.professor)).where(Turma.ativo == True)
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)
        if programa_selecionado != 'Todos':
            stmt = stmt.where(Turma.programa == programa_selecionado)
    else:
        # Professor vê apenas suas próprias turmas
        stmt = select(Turma).where(
            Turma.professor_id == current_user.id,
            Turma.ativo == True
        )
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)

    todas_turmas = db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()

    return render_template('painel_professor.html',
                           turmas=todas_turmas,
                           lista_programas=lista_programas,
                           programa_ativo=programa_selecionado,
                           is_readonly=current_user.role == 'secretaria')


@bp.route('/frequencia', methods=['GET', 'POST'])
@login_required
def frequencia():
    """
    Controlador de Submissões em Lote do Diário Online.
    Utiliza Atomic Transactions oriuntas do utilitario logica.py.
    """
    if current_user.role not in ['admin', 'pedagogico', 'professor', 'secretaria']:
        abort(403)

    if request.method == 'POST':
        # Secretaria tem acesso somente leitura — não pode salvar frequência
        if current_user.role == 'secretaria':
            abort(403)

        # Valida que professor só salva frequência das suas próprias turmas
        turma_post_id = request.form.get('turma', '')
        if current_user.role == 'professor' and turma_post_id:
            turma_post = db.session.get(Turma, int(turma_post_id)) if turma_post_id.isdigit() else None
            if not turma_post or turma_post.professor_id != current_user.id:
                abort(403)

        turma_id, data = salvar_frequencia(request.form)
        if not data:
            flash("Preencha a data da aula antes de salvar.", "warning")
            return redirect(url_for('registros.frequencia', turma_id=turma_post_id or ''))

        flash('Frequência salva com sucesso!', 'success')
        return redirect(url_for('registros.frequencia', turma_id=turma_id, data=data))

    turma_id = request.args.get('turma_id')
    data     = request.args.get('data')

    unidade_id = get_unidade_id()

    # Professor vê apenas suas próprias turmas; admin/pedagogico vê todas da unidade
    if current_user.role == 'professor':
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

    # Garante que o professor não acesse turma de outro professor via URL direta
    if turma_id and current_user.role == 'professor':
        turma_ids_permitidos = {str(t.id) for t in turmas}
        if turma_id not in turma_ids_permitidos:
            flash('Você não tem permissão para acessar esta turma.', 'danger')
            return redirect(url_for('registros.frequencia'))
    
    # Previne quebra de dict ou query se args não foram chamados inda
    ctx = {}
    freqs = {}
    tema_sel = None
    obs = ""
    
    if turma_id:
         ctx = carregar_contexto_turma(turma_id)
         if data:
              freqs, tema_sel, obs = carregar_frequencias(turma_id, data)

         # Injeta estats_freq e pode_receber_frequencia em cada aluno
         for aluno in ctx.get('alunos', []):
             # Busca registros desta turma; fallback para qualquer registro do aluno
             registros = Frequencia.query.filter_by(
                 aluno_id=aluno.id, turma_id=int(turma_id)
             ).all()
             if not registros:
                 # Compatibilidade com registros antigos sem turma_id
                 registros = Frequencia.query.filter_by(aluno_id=aluno.id).all()

             total = len(registros)
             if total:
                 presentes = sum(1 for r in registros if r.conceito in ('A','B','C','D'))
                 faltas    = sum(1 for r in registros if r.conceito == 'F')
                 justif    = sum(1 for r in registros if r.conceito == 'J')
                 contaveis = presentes + faltas   # J não entra no denominador
                 aluno.estats_freq = type('E', (), {
                     'presenca':    round(presentes / contaveis * 100, 1) if contaveis else 0,
                     'falta':       round(faltas    / contaveis * 100, 1) if contaveis else 0,
                     'justificada': round(justif    / total     * 100, 1) if total else 0,
                     'total_aulas': total,
                 })()
             else:
                 aluno.estats_freq = type('E', (), {
                     'presenca': 0, 'falta': 0, 'justificada': 0, 'total_aulas': 0
                 })()

             # Verifica se a inscrição do aluno nesta turma está ativa
             insc = Inscricao.query.filter_by(
                 aluno_id=aluno.id, turma_id=int(turma_id)
             ).first()
             aluno.pode_receber_frequencia = bool(insc and insc.ativo)

    return render_template('frequencia.html',
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
                           is_readonly=current_user.role == 'secretaria')


@bp.route('/frequencia_relatorio')
@login_required
def frequencia_relatorio():
    if current_user.role != 'pedagogico':
        abort(403)

    turma_id   = request.args.get('turma')
    data_inicio = request.args.get('inicio')
    data_fim   = request.args.get('fim')

    turmas            = Turma.query.all()
    resultado         = []
    turma_selecionada = None

    if turma_id:
        turma_selecionada = Turma.query.get(int(turma_id))
        alunos = db.session.execute(
            select(Aluno).where(Aluno.turma_id == turma_id)
        ).scalars().all()

        for aluno in alunos:
            stmt_total = select(func.count()).select_from(Frequencia).where(
                Frequencia.aluno_id == aluno.id
            )
            stmt_pres = select(func.count()).select_from(Frequencia).where(
                (Frequencia.aluno_id == aluno.id) & (Frequencia.presente == True)
            )
            if data_inicio:
                stmt_total = stmt_total.where(Frequencia.data >= data_inicio)
                stmt_pres  = stmt_pres.where(Frequencia.data >= data_inicio)
            if data_fim:
                stmt_total = stmt_total.where(Frequencia.data <= data_fim)
                stmt_pres  = stmt_pres.where(Frequencia.data <= data_fim)

            total    = db.session.execute(stmt_total).scalar() or 0
            presencas = db.session.execute(stmt_pres).scalar() or 0
            percentual = round((presencas / total) * 100, 2) if total > 0 else 0

            resultado.append({
                "nome": aluno.nome,
                "total": total,
                "presencas": presencas,
                "percentual": percentual
            })

    return render_template('frequencia_relatorio.html',
                           dados=resultado,
                           turmas=turmas,
                           turma_id=turma_id,
                           turma_selecionada=turma_selecionada,
                           inicio=data_inicio,
                           fim=data_fim)


# ---------------------------------------------------------------------------
# CURSOS
# ---------------------------------------------------------------------------

@bp.route('/cursos', methods=['GET'])
@login_required
def listar_cursos():
    """Retorna JSON com os cursos da unidade — usado pelo modal de planejamento."""
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    unidade_id = get_unidade_id()
    q = Curso.query.filter_by(ativo=True)
    if unidade_id:
        q = q.filter_by(unidade_id=unidade_id)
    cursos = q.order_by(Curso.nome).all()
    return jsonify([{'id': c.id, 'nome': c.nome, 'descricao': c.descricao or ''} for c in cursos])


@bp.route('/cursos/novo', methods=['POST'])
@login_required
def novo_curso():
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        return jsonify({'success': False, 'message': 'Usuário sem unidade definida.'}), 400

    nome = (request.json or {}).get('nome', '').strip()
    descricao = (request.json or {}).get('descricao', '').strip()
    carga_horaria = (request.json or {}).get('carga_horaria')
    if not nome:
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400

    curso = Curso(
        nome=nome,
        descricao=descricao or None,
        carga_horaria=int(carga_horaria) if carga_horaria else None,
        unidade_id=unidade_id
    )
    try:
        db.session.add(curso)
        db.session.commit()
        return jsonify({'success': True, 'id': curso.id, 'nome': curso.nome, 'descricao': curso.descricao or ''})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/cursos/<int:curso_id>/editar', methods=['POST'])
@login_required
def editar_curso(curso_id):
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    if unidade_id and curso.unidade_id != unidade_id:
        abort(403)

    data = request.json or {}
    nome = data.get('nome', '').strip()
    if not nome:
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400

    curso.nome = nome
    curso.descricao = data.get('descricao', '').strip() or None
    carga = data.get('carga_horaria')
    curso.carga_horaria = int(carga) if carga else None
    try:
        db.session.commit()
        return jsonify({
            'success': True, 'id': curso.id, 'nome': curso.nome,
            'descricao': curso.descricao or '',
            'carga_horaria': curso.carga_horaria or ''
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


@bp.route('/cursos/<int:curso_id>/excluir', methods=['POST'])
@login_required
def excluir_curso(curso_id):
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    if unidade_id and curso.unidade_id != unidade_id:
        abort(403)

    # Soft delete — preserva integridade com turmas existentes
    curso.ativo = False
    try:
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500


# ---------------------------------------------------------------------------
# PLANEJAMENTO DE TEMAS
# ---------------------------------------------------------------------------

@bp.route('/planejamento', methods=['GET', 'POST'])
@login_required
def planejamento():
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)

    if request.method == 'POST':
        tipo_post = request.form.get('tipo_post', 'tema')

        if tipo_post == 'nivel':
            from app.models import Nivel
            nome_nivel = request.form.get('nome_nivel', '').strip()
            if nome_nivel:
                try:
                    db.session.add(Nivel(
                        nome=nome_nivel,
                        ativo=True,
                        unidade_id=get_unidade_id()
                    ))
                    db.session.commit()
                    flash(f"Nível '{nome_nivel}' adicionado com sucesso!", 'success')
                except Exception as e:
                    db.session.rollback()
                    flash("Erro ao salvar nível.", 'danger')
            else:
                flash("Informe o nome do nível.", 'warning')
            return redirect(url_for('registros.planejamento'))

        # tipo_post == 'tema' (padrão)
        curso_id  = request.form.get('curso_id')
        titulo_tema = request.form.get('titulo')
        if curso_id and titulo_tema:
            try:
                curso = Curso.query.get(int(curso_id))
                db.session.add(TemaAula(
                    curso_id=int(curso_id),
                    titulo=titulo_tema,
                    unidade_id=get_unidade_id()
                ))
                db.session.commit()
                flash(f"Tema '{titulo_tema}' adicionado ao curso '{curso.nome if curso else ''}'!", "success")
            except Exception as e:
                db.session.rollback()
                flash(f"Erro ao salvar tema: {e}", "danger")
        elif not curso_id:
            flash("Selecione um curso.", "warning")
        elif not titulo_tema:
            flash("Informe o título do tema.", "warning")
        return redirect(url_for('registros.planejamento'))

    conf_i = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho').first()
    conf_f = ConfiguracaoSistema.query.filter_by(chave='fim_conselho').first()

    unidade_id = get_unidade_id()
    turmas = Turma.get_ativas()
    if unidade_id:
        turmas = [t for t in turmas if t.unidade_id == unidade_id]

    prog_filtro = request.args.get('programa', 'Todos')
    programas   = sorted({t.programa for t in turmas if t.programa})

    # Temas: filtra pela unidade via join com Curso
    q_temas = TemaAula.query.join(Curso, TemaAula.curso_id == Curso.id).filter(
        TemaAula.curso_id.isnot(None)
    )
    if unidade_id:
        q_temas = q_temas.filter(Curso.unidade_id == unidade_id)
    lista_temas = q_temas.order_by(TemaAula.curso_id).all()

    from app.models import Nivel
    niveis = Nivel.query.filter_by(ativo=True).all()
    if unidade_id:
        niveis = [n for n in niveis if n.unidade_id == unidade_id or n.unidade_id is None]

    # Períodos ativos da unidade (para o modal de calendário)
    q_periodos = PeriodoLetivo.query.filter_by(ativo=True)
    if unidade_id:
        q_periodos = q_periodos.filter_by(unidade_id=unidade_id)
    periodos_ativos = q_periodos.order_by(PeriodoLetivo.data_inicio.desc()).all()

    # Filtra temas conforme curso selecionado (filtro_curso) ou mostra todos
    filtro_curso = request.args.get('curso_id', '')
    if filtro_curso:
        lista_temas = [t for t in lista_temas if str(t.curso_id) == filtro_curso]

    # Cursos da unidade (para o modal de cursos)
    q_cursos = Curso.query.filter_by(ativo=True)
    if unidade_id:
        q_cursos = q_cursos.filter_by(unidade_id=unidade_id)
    cursos = q_cursos.order_by(Curso.nome).all()

    return render_template('planejamento.html',
                           turmas=turmas,
                           temas=lista_temas,
                           programas=programas,
                           prog_filtro=prog_filtro,
                           filtro_curso=filtro_curso,
                           niveis=niveis,
                           periodos_ativos=periodos_ativos,
                           cursos=cursos,
                           data_inicio_atual=conf_i.valor if conf_i else '',
                           data_fim_atual=conf_f.valor if conf_f else '')

# ---------------------------------------------------------------------------
# TEMAS DE AULA — edição e inativação
# ---------------------------------------------------------------------------

@bp.route('/planejamento/tema/editar/<int:id>', methods=['POST'])
@login_required
def editar_tema(id):
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    if unidade_id and tema.unidade_id and tema.unidade_id != unidade_id:
        abort(403)
    novo_titulo = request.form.get('titulo', '').strip()
    if novo_titulo:
        try:
            tema.titulo = novo_titulo
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
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    if unidade_id and tema.unidade_id and tema.unidade_id != unidade_id:
        abort(403)
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
# NÍVEIS — exclusão
# ---------------------------------------------------------------------------

@bp.route('/planejamento/nivel/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_nivel(id):
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    from app.models import Nivel
    nivel = db.get_or_404(Nivel, id)
    try:
        db.session.delete(nivel)
        db.session.commit()
        flash(f"Nível '{nivel.nome}' excluído!", 'success')
    except Exception:
        db.session.rollback()
        flash("Não foi possível excluir: o nível pode estar em uso.", 'warning')
    return redirect(url_for('registros.planejamento'))


# ---------------------------------------------------------------------------
# TEMAS — impressão
# ---------------------------------------------------------------------------

@bp.route('/planejamento/imprimir-temas')
@login_required
def imprimir_temas():
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)

    filtro_curso = request.args.get('curso_id', '')
    unidade_id = get_unidade_id()

    query = TemaAula.query.join(Curso, TemaAula.curso_id == Curso.id).filter(
        TemaAula.curso_id.isnot(None),
        TemaAula.ativo == True
    )
    if unidade_id:
        query = query.filter(Curso.unidade_id == unidade_id)
    if filtro_curso:
        query = query.filter(TemaAula.curso_id == int(filtro_curso))

    temas = query.order_by(Curso.nome, TemaAula.id).all()

    # Cursos para o select de filtro na impressão
    q_cursos = Curso.query.filter_by(ativo=True)
    if unidade_id:
        q_cursos = q_cursos.filter_by(unidade_id=unidade_id)
    cursos = q_cursos.order_by(Curso.nome).all()

    return render_template('impressao_temas.html',
                           temas=temas,
                           cursos=cursos,
                           filtro_curso=filtro_curso,
                           now=datetime.now())



@bp.route('/planejamento/configurar-conselho', methods=['POST'])
@login_required
def salvar_configuracao_conselho():
    if current_user.role not in ['admin', 'pedagogico']:
        abort(403)
    
    inicio = request.form.get('inicio_conselho')
    fim = request.form.get('fim_conselho')

    try:
        for chave, valor in [('inicio_conselho', inicio), ('fim_conselho', fim)]:
            conf = ConfiguracaoSistema.query.filter_by(chave=chave).first()
            if not conf:
                conf = ConfiguracaoSistema(chave=chave)
                db.session.add(conf)
            conf.valor = valor
        
        db.session.commit()
        flash('Ciclos Letivos (Start-End Points) alterados no Server-Side.', 'success')
    except Exception as e:
         db.session.rollback()
         flash(f"Impedimento do banco ao gravar configuração: {e}", "warning")

    return redirect(url_for('registros.planejamento'))


# ---------------------------------------------------------------------------
# API SERVERSIDE BINDINGS
# ---------------------------------------------------------------------------
@bp.route('/api/alunos/<int:turma_id>')
@login_required
def api_alunos(turma_id):
    """Integrações Async com Frontend AJAX para Fetch de Alunos por ID."""
    turma = Turma.query.get_or_404(turma_id)
    alunos = turma.alunos.all()
    return jsonify([{"id": a.id, "nome": a.nome} for a in alunos])




from flask import Blueprint, current_app, render_template, request, redirect, flash, url_for, abort, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from datetime import datetime, timedelta

from app.models import User, LogAcao, Unidade, ConfiguracaoSistema
from app.database import db
from app.services.auth_service import (
    authenticate_against_ldap,
    register_security_log,
    validate_password_strength,
)

bp = Blueprint('auth', __name__)

@bp.route('/aguardando-aprovacao')
@login_required
def aguardando_aprovacao():
    """Intermediário visual que barra usuários AD Recém-logados de acessarem o sistema até liberação de Cargo e Perfis."""
    if current_user.role != 'pendente':
        return redirect(url_for('main.dashboard'))
    return render_template('aguardando.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Controlador de Login com Autenticação de Dois Níveis Híbrida:
    1º Camada Bando Local (Prioridade 1)
    2º Camada Fallback/FirstTime AD (LDAP) -> Caso passe, cria user "pendente" automaticamente no db local.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        # Defensivo contra envio vazio
        if not email or not password:
            flash('Informe Email e Senha.', 'warning')
            return redirect(url_for('auth.login'))

        # Busca o usuário local
        user = db.session.execute(
            select(User).where(User.email == email)
        ).scalars().first()

        login_ok = False

        # === 1. TENTATIVA AUTENTICAÇÃO LOCAL (HASH) ===
        if user and user.check_password(password):
            login_ok = True

        # === 2. TENTATIVA AUTENTICAÇÃO DOMÍNIO AD ===
        elif "@" in email:
            if authenticate_against_ldap(email, password):
                login_ok = True
                # O autoprovisionamento providencia a vida local de um AD Autorizado mas sem cadastro local
                if not user:
                    try:
                        user = User(
                            name=email.split('@')[0].replace('.', ' ').title(),
                            email=email,
                            role='pendente', # Trava de segurança total no sistema
                            is_ad_user=True,
                            is_active=True
                        )
                        db.session.add(user)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception("Falha no aprovisionamento automático via LDAP.")
                        flash("Erro no banco local ao registrar sua entrada AD.", "danger")
                        login_ok = False

        # === 3. CONCLUSÃO COM SUCESSO ===
        if login_ok and user and user.is_active:
            login_user(user)
            session.permanent = True

            register_security_log("Acesso Aprovado", f"Usuário {user.name} acessou o sistema.")

            # Força troca de senha no primeiro login (todos os tipos de usuário)
            if user.first_login:
                flash('Bem-vindo! Por segurança, defina sua senha pessoal antes de continuar.', 'warning')
                return redirect(url_for('auth.trocar_senha'))

            return redirect(url_for('main.dashboard'))

        # Falha total ou Desabilitado
        register_security_log("Aviso de Invasão/Falha", f"Login declinado para alvo de e-mail: {email}")
        flash('Credenciais recusadas pelo domínio e banco de dados.', 'danger')

    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    register_security_log("Logoff", "Sessão encerrada voluntariamente.")
    logout_user()
    return redirect(url_for('auth.login'))


# ====================== ROTAS ADMINISTRAÇÃO ======================

@bp.route('/admin/painel')
@login_required
def painel_admin():
    if current_user.role != 'admin':
        flash("Quebra de Hierarquia: O Painel administrativo está bloqueado para você.", "danger")
        return redirect(url_for('main.dashboard'))

    usuarios = db.session.execute(
        select(User).order_by(User.name)
    ).scalars().all()
    
    unidades = db.session.execute(
        select(Unidade).where(Unidade.ativo == True).order_by(Unidade.nome)
    ).scalars().all()

    return render_template('admin/painel_admin.html', usuarios=usuarios, unidades=unidades)


@bp.route('/admin/cadastrar', methods=['POST'])
@login_required
def cadastrar_usuario():
    if current_user.role != 'admin':
        abort(403)

    email = request.form.get('email', '').strip()
    if db.session.execute(select(User).where(User.email == email)).scalar():
        flash("Este correio eletrônico corporativo já existe localmente!", "danger")
        return redirect(url_for('auth.painel_admin'))

    nome  = request.form.get('nome')
    senha = request.form.get('password')
    
    if not nome or not senha:
         flash("Preencha todos os dados corretamente.", "warning")
         return redirect(url_for('auth.painel_admin'))
         
    try:
        unidade_id = request.form.get('unidade_id')
        unidade_id = int(unidade_id) if unidade_id and unidade_id.isdigit() else None
        
        novo = User(name=nome, email=email, role=request.form.get('role'),
                    unidade_id=unidade_id, first_login=True)
        novo.set_password(senha)
        db.session.add(novo)
        db.session.commit()
        register_security_log("Cadastro Local", f"Admin gerou conta manual: {email}")
        flash(f"Conta para {nome} criada com sucesso!", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao cadastrar usuário manualmente.")
        flash("Não foi possível gravar o novo usuário.", "danger")

    return redirect(url_for('auth.painel_admin'))


@bp.route('/usuarios/editar/<int:id>', methods=['POST'])
@login_required
def editar_usuario(id):
    if current_user.role != 'admin':
        abort(403)

    usuario = db.session.get(User, id)
    if usuario:
        try:
            usuario.name  = request.form.get('nome')
            usuario.email = request.form.get('email')
            usuario.role  = request.form.get('role')
            unidade_id = request.form.get('unidade_id')
            usuario.unidade_id = int(unidade_id) if unidade_id and unidade_id.isdigit() else None
            db.session.commit()
            register_security_log("Alteração de Cadastros", f"Admin alterou {usuario.email}.")
            flash(f"Dados atualizados no perfil de {usuario.name}!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao editar usuário.")
            flash("Falha ao salvar edição.", "danger")

    return redirect(url_for('auth.painel_admin'))


@bp.route('/usuarios/resetar/<int:id>', methods=['POST'])
@login_required
def resetar_senha(id):
    if current_user.role != 'admin':
        abort(403)
    
    usuario = db.session.get(User, id)
    if usuario:
        try:
            default_password = current_app.config.get("ADMIN_DEFAULT_PASSWORD")
            if not default_password:
                flash("Defina ADMIN_DEFAULT_PASSWORD no ambiente para permitir o reset.", "warning")
                return redirect(url_for('auth.painel_admin'))

            usuario.set_password(default_password)
            usuario.first_login = True
            db.session.commit()
            register_security_log("Reset de Senha", f"Senha de {usuario.email} resetada pelo admin.")
            flash(f"Senha de {usuario.name} resetada. Troca obrigatória no próximo login.", "info")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao resetar senha de usuário.")
            flash("Erro ao resetar senha.", "warning")

    return redirect(url_for('auth.painel_admin'))


@bp.route('/usuarios/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_usuario(id):
    if current_user.role != 'admin':
        abort(403)

    usuario = db.session.get(User, id)
    if usuario and usuario.id != current_user.id:
        try:
            db.session.delete(usuario)
            db.session.commit()
            register_security_log("Remoção Grave", f"O perfil de {usuario.email} foi apagado.")
            flash(f"Usuário deletado de forma definitiva.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao excluir usuário.")
            flash("O banco recusou a deleção, provavelmente existem relatórios amarrados ao perfil.", "danger")
    else:
        flash("Política de suicídio de perfil barrada. Peça a outro Admin.", "danger")

    return redirect(url_for('auth.painel_admin'))


@bp.route('/admin/unidades')
@login_required
def admin_unidades():
    """Lista todas as unidades para gestão administrativa."""
    if current_user.role != 'admin':
        abort(403)
    
    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template('admin/unidades.html', unidades=unidades)

@bp.route('/admin/unidades/cadastrar', methods=['POST'])
@login_required
def cadastrar_unidade():
    """Cria uma nova unidade organizacional."""
    if current_user.role != 'admin':
        abort(403)
        
    nome = request.form.get('nome')
    if nome:
        try:
            nova = Unidade(nome=nome, ativo=True)
            db.session.add(nova)
            db.session.commit()
            register_security_log("Gestão de Unidade", f"Cadastrada nova unidade: {nome}")
            flash(f"Unidade '{nome}' criada com sucesso!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao criar unidade.")
            flash("Erro ao criar unidade.", "danger")
    
    return redirect(url_for('auth.admin_unidades'))

@bp.route('/admin/unidades/editar/<int:id>', methods=['POST'])
@login_required
def editar_unidade(id):
    """Atualiza dados de uma unidade existente."""
    if current_user.role != 'admin':
        abort(403)
        
    unidade = db.get_or_404(Unidade, id)
    nome_antigo = unidade.nome
    novo_nome = request.form.get('nome')
    
    if novo_nome:
        try:
            unidade.nome = novo_nome
            db.session.commit()
            register_security_log("Gestão de Unidade", f"Renomeada unidade: {nome_antigo} -> {novo_nome}")
            flash(f"Unidade atualizada para '{novo_nome}'!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao editar unidade.")
            flash("Erro ao atualizar unidade.", "danger")
            
    return redirect(url_for('auth.admin_unidades'))

@bp.route('/admin/unidades/alternar/<int:id>')
@login_required
def alternar_unidade_status(id):
    """Ativa ou Inativa uma unidade (Exclusão Lógica)."""
    if current_user.role != 'admin':
        abort(403)
        
    unidade = db.get_or_404(Unidade, id)
    unidade.ativo = not unidade.ativo
    
    try:
        db.session.commit()
        status = "ativada" if unidade.ativo else "inativada"
        register_security_log("Gestão de Unidade", f"Unidade {unidade.nome} foi {status}.")
        flash(f"Unidade {unidade.nome} {status} com sucesso!", "info")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao alternar status da unidade.")
        flash("Erro ao alterar status da unidade.", "danger")
        
    return redirect(url_for('auth.admin_unidades'))


# ====================== ROTAS AUDITORIA DE USO ======================

from unidecode import unidecode

@bp.route('/admin/logs')
@login_required
def ver_logs():
    if current_user.role != 'admin':
        abort(403)

    page = request.args.get('page', 1, type=int)
    usuario_busca = request.args.get('usuario', '').strip()
    acao_busca = request.args.get('acao', '').strip()
    data_busca = request.args.get('data', '').strip()

    query = LogAcao.query

    if usuario_busca:
        query = query.filter(LogAcao.usuario_nome.ilike(f'%{usuario_busca}%'))

    if data_busca:
        try:
            data_inicio = datetime.strptime(data_busca, '%Y-%m-%d').date()
            data_fim = data_inicio + timedelta(days=1)
            query = query.filter(LogAcao.data_hora >= data_inicio, LogAcao.data_hora < data_fim)
        except ValueError:
            pass

    # Paginação primeiro
    pagination = query.order_by(LogAcao.data_hora.desc()).paginate(page=page, per_page=20, error_out=False)

    # Filtro por ação (em memória, apenas nos itens da página atual)
    if acao_busca:
        termo_normalizado = unidecode(acao_busca.lower())
        pagination.items = [
            log for log in pagination.items
            if termo_normalizado in unidecode(log.acao).lower()
        ]

    return render_template('admin/logs.html', logs=pagination.items, pagination=pagination)


def _executar_limpar_logs(automatico=False):
    """Remove logs com mais de 30 dias. Retorna número de registros removidos ou -1 em erro."""
    try:
        data_limite = datetime.now() - timedelta(days=30)

        # Controle para execução automática (evita rodar várias vezes no mesmo dia)
        if automatico:
            ultima_limpeza = ConfiguracaoSistema.query.filter_by(chave='ultima_limpeza_logs').first()
            hoje = datetime.now().date()
            if ultima_limpeza and ultima_limpeza.valor == str(hoje):
                return 0
            if not ultima_limpeza:
                ultima_limpeza = ConfiguracaoSistema(
                    chave='ultima_limpeza_logs',
                    valor=str(hoje),
                    descricao="Data da última execução automática de limpeza de logs"
                )
                db.session.add(ultima_limpeza)
            else:
                ultima_limpeza.valor = str(hoje)
            db.session.commit()

        # Executa a exclusão
        qtd = LogAcao.query.filter(LogAcao.data_hora < data_limite).count()
        if qtd:
            LogAcao.query.filter(LogAcao.data_hora < data_limite).delete(synchronize_session=False)
            db.session.commit()
        return qtd
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao limpar logs antigos")
        return -1

@bp.route('/admin/logs/limpar-antigos', methods=['POST'])
@login_required
def limpar_logs_antigos():
    """Remove logs com mais de 30 dias para evitar inchaço do SQLite DB local."""
    if current_user.role != 'admin':
        abort(403)

    qtd = _executar_limpar_logs(automatico=False)
    
    if qtd >= 0:
        flash(f'Limpeza de Logs: {qtd} logs removidos!', 'success')
    else:
        flash(f'Falha técnica ao tentar limpar logs antigos.', 'danger')

    return redirect(url_for('auth.ver_logs'))


# ====================== ROTAS DO PERFIL PESSOAL ======================

@bp.route('/trocar-senha', methods=['GET', 'POST'])
@login_required
def trocar_senha():
    if request.method == 'POST':
        nova     = request.form.get('nova_senha', '')
        confirma = request.form.get('confirma_senha', '')

        # ── Validação de complexidade ──────────────────────────────────────
        erros = validate_password_strength(nova)
        if erros:
            for e in erros:
                flash(e, 'danger')
            return redirect(url_for('auth.trocar_senha'))

        if nova != confirma:
            flash('As senhas não coincidem.', 'danger')
            return redirect(url_for('auth.trocar_senha'))

        # Impede reutilizar a própria senha atual
        if current_user.check_password(nova):
            flash('A nova senha não pode ser igual à senha atual.', 'danger')
            return redirect(url_for('auth.trocar_senha'))

        try:
            current_user.set_password(nova)
            current_user.first_login = False   # libera acesso normal após troca
            db.session.commit()
            register_security_log("Troca de Senha", f"{current_user.name} definiu nova senha.")
            flash('Senha atualizada com sucesso!', 'success')
            return redirect(url_for('main.dashboard'))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao trocar senha do usuário atual.")
            flash('Erro ao salvar a nova senha. Tente novamente.', 'warning')

    return render_template('trocar_senha.html', first_login=current_user.first_login)

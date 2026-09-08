from flask import Blueprint, current_app, render_template, request, redirect, flash, url_for, abort, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from datetime import datetime, timedelta
from collections import defaultdict
import secrets

from app.models import User, LogAcao, Unidade, ConfiguracaoSistema
from app.database import db
from app.services.auth_service import (
    _build_ldap_bind_user,
    authenticate_against_ldap,
    register_security_log,
    validate_password_strength,
)

bp = Blueprint('auth', __name__)

# Nota técnica: este controle básico evita tentativas repetidas de login em sequência
# sem exigir uma nova estrutura de cache ou armazenamento externo.
_FAILED_ATTEMPTS = defaultdict(list)
_MAX_ATTEMPTS = 5
_ATTEMPT_WINDOW_SECONDS = 900


def _is_login_blocked(ip_address: str) -> bool:
    """Bloqueia temporariamente IPs com muitas tentativas consecutivas de login."""
    attempts = _FAILED_ATTEMPTS.get(ip_address, [])
    now = datetime.now()
    attempts[:] = [ts for ts in attempts if (now - ts).total_seconds() < _ATTEMPT_WINDOW_SECONDS]
    _FAILED_ATTEMPTS[ip_address] = attempts
    return len(attempts) >= _MAX_ATTEMPTS


def _register_failed_attempt(ip_address: str) -> None:
    """Registra uma tentativa falha para posterior bloqueio temporário."""
    attempts = _FAILED_ATTEMPTS.get(ip_address, [])
    attempts.append(datetime.now())
    _FAILED_ATTEMPTS[ip_address] = attempts


@bp.route('/aguardando-aprovacao')
@login_required
def aguardando_aprovacao():
    """Exibe a página de espera para usuários AD/LDAP recém-provisionados.

    Quando o usuário do domínio passa pela validação do servidor, ele é criado
    localmente com perfil `pendente`. Enquanto essa etapa não for liberada pelo
    administrador, o acesso ao sistema fica restrito a esta tela, evitando que
    o perfil alcance áreas operacionais sem a devida classificação.
    """
    if current_user.role != 'pendente':
        return redirect(url_for('main.dashboard'))
    return render_template('aguardando.html')


@bp.route('/login', methods=['GET', 'POST'])
def login():
    """Controlador de login híbrido: local primeiro e LDAP/AD como fallback.

    Usuários locais com senha persistida continuam no fluxo de troca
    obrigatória na primeira autenticação. Usuários federados pelo AD/LDAP
    são provisionados localmente apenas quando o servidor do domínio os
    valida e não precisam de senha local persistida.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip()
        password = request.form.get('password', '')

        ip_address = request.remote_addr or "unknown"
        if _is_login_blocked(ip_address):
            flash('Muitas tentativas de login foram detectadas. Tente novamente mais tarde.', 'danger')
            return redirect(url_for('auth.login'))

        # Defensivo contra envio vazio
        if not email or not password:
            flash('Informe Email e Senha.', 'warning')
            _register_failed_attempt(ip_address)
            return redirect(url_for('auth.login'))

        # Busca o usuário já registrado localmente. Para contas federadas,
        # a senha local pode estar ausente e o login é concluído pelo AD/LDAP.
        # O usuário pode ter sido provisionado localmente com e-mail canônico do AD
        # ou apenas com o nome curto do login; por isso, pesquisamos todas as formas
        # possíveis de identidade antes de criar um novo cadastro.
        lookup_candidates = [
            _build_ldap_bind_user(
                email,
                current_app.config.get("LDAP_DOMAIN"),
            )
        ]
        if lookup_candidates[0] != email:
            lookup_candidates.append(email)
        user = db.session.execute(
            select(User).where(User.email.in_(lookup_candidates))
        ).scalars().first()

        login_ok = False
        ldap_identity = email
        if "@" not in ldap_identity and current_app.config.get("LDAP_DOMAIN"):
            ldap_identity = f"{ldap_identity}@{current_app.config.get('LDAP_DOMAIN')}"

        # === 1. TENTATIVA DE AUTENTICAÇÃO LOCAL (HASH) ===
        # Este fluxo é reservado a usuários que realmente possuem credencial
        # local persistida no banco. Usuários AD/LDAP não dependem dessa senha.
        if user and user.password and user.check_password(password):
            login_ok = True

        # === 2. TENTATIVA DE AUTENTICAÇÃO NO DOMÍNIO AD/LDAP ===
        # Quando a validação no servidor do domínio acontece com sucesso, o
        # sistema apenas provisiona a identidade local em status `pendente`.
        else:
            if authenticate_against_ldap(ldap_identity, password):
                login_ok = True
                # O autoprovisionamento providencia a vida local de um AD Autorizado mas sem cadastro local
                if not user:
                    try:
                        from app.utils.logica import formatar_nome_proprio

                        user = User(
                            name=formatar_nome_proprio(ldap_identity.split('@')[0].replace('.', ' ')),
                            email=ldap_identity,
                            password="",
                            role='pendente', # Trava de segurança total no sistema
                            is_ad_user=True,
                            is_active=True,
                            first_login=False,
                        )
                        db.session.add(user)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception("Falha no aprovisionamento automático via LDAP.")
                        flash("Erro no banco local ao registrar sua entrada AD.", "danger")
                        login_ok = False
                elif user.email != ldap_identity:
                    try:
                        user.email = ldap_identity
                        db.session.add(user)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception("Falha ao normalizar o e-mail do usuário AD no banco local.")
                        flash("Erro ao normalizar seu cadastro local do AD.", "danger")
                        login_ok = False

        # === 3. CONCLUSÃO COM SUCESSO ===
        if login_ok and user and user.is_active:
            login_user(user)
            session.permanent = True
            if user.unidade_id:
                session["unidade_id"] = user.unidade_id
            else:
                session.pop("unidade_id", None)

            register_security_log("Acesso Aprovado", f"Usuário {user.name} acessou o sistema.")

            # A troca obrigatória de senha deve ocorrer apenas para usuários
            # locais com senha persistida no banco. Usuários federados pelo AD
            # seguem para a fase de aprovação do perfil e não passam por senha local.
            if user.first_login and not user.is_ad_user:
                flash('Bem-vindo! Por segurança, defina sua senha pessoal antes de continuar.', 'warning')
                return redirect(url_for('auth.trocar_senha'))

            return redirect(url_for('main.dashboard'))

        # Falha total ou Desabilitado
        register_security_log("Aviso de Invasão/Falha", f"Login declinado para alvo de e-mail: {email}")
        _register_failed_attempt(ip_address)
        flash('Credenciais recusadas pelo domínio e banco de dados.', 'danger')

    return render_template('login.html')

@bp.route('/logout')
@login_required
def logout():
    register_security_log("Logoff", "Sessão encerrada voluntariamente.")
    logout_user()
    return redirect(url_for('auth.login'))


# ====================== GOOGLE OAUTH2 ======================

_GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URI = "https://openidconnect.googleapis.com/v1/userinfo"
_GOOGLE_SCOPES = ["openid", "email", "profile"]


@bp.route('/auth/google/login')
def google_login():
    """Inicia o fluxo OAuth2 PKCE com o Google.

    Gera um ``state`` aleatório para proteção contra CSRF, armazena na sessão
    e redireciona o navegador para a tela de consentimento do Google.
    O Google retorna o usuário para ``google_callback`` com um código de
    autorização que é trocado por um ID Token com os dados do perfil.
    """
    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    redirect_uri = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")

    if not client_id or not redirect_uri:
        flash("Login com Google não está configurado neste servidor.", "warning")
        return redirect(url_for("auth.login"))

    # State anti-CSRF: valor aleatório que o Google devolve no callback e que
    # verificamos antes de processar qualquer resposta da autenticação.
    state = secrets.token_urlsafe(32)
    session["google_oauth_state"] = state

    try:
        from google_auth_oauthlib.flow import Flow

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET"),
                    "auth_uri": _GOOGLE_AUTH_URI,
                    "token_uri": _GOOGLE_TOKEN_URI,
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=_GOOGLE_SCOPES,
            state=state,
        )
        flow.redirect_uri = redirect_uri

        authorization_url, _ = flow.authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            prompt="select_account",
        )
        return redirect(authorization_url)

    except Exception:
        current_app.logger.exception("Falha ao iniciar fluxo OAuth Google.")
        flash("Não foi possível iniciar o login com Google. Tente outra forma de acesso.", "danger")
        return redirect(url_for("auth.login"))


@bp.route('/auth/google/callback')
def google_callback():
    """Processa o retorno do Google após a tela de consentimento.

    Valida o state anti-CSRF, troca o código de autorização por tokens,
    obtém o perfil do usuário via UserInfo e faz o login local —
    criando ou vinculando a conta se necessário.
    """
    # --- 1. Verificação CSRF ---
    state_retornado = request.args.get("state", "")
    state_esperado = session.pop("google_oauth_state", None)
    if not state_esperado or state_retornado != state_esperado:
        flash("Falha de segurança na verificação do estado OAuth. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    # Erro explícito do Google (usuário cancelou ou conta bloqueada)
    error = request.args.get("error")
    if error:
        flash(f"Acesso Google recusado: {error}", "warning")
        return redirect(url_for("auth.login"))

    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")

    try:
        from google_auth_oauthlib.flow import Flow
        import requests as http_requests

        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "auth_uri": _GOOGLE_AUTH_URI,
                    "token_uri": _GOOGLE_TOKEN_URI,
                    "redirect_uris": [redirect_uri],
                }
            },
            scopes=_GOOGLE_SCOPES,
            state=state_retornado,
        )
        flow.redirect_uri = redirect_uri

        # Troca o código de autorização pelos tokens de acesso
        flow.fetch_token(authorization_response=request.url)

        # --- 2. Obtém dados do perfil via UserInfo ---
        credentials = flow.credentials
        userinfo_resp = http_requests.get(
            _GOOGLE_USERINFO_URI,
            headers={"Authorization": f"Bearer {credentials.token}"},
            timeout=10,
        )
        userinfo_resp.raise_for_status()
        userinfo = userinfo_resp.json()

    except Exception:
        current_app.logger.exception("Falha no callback OAuth Google.")
        flash("Não foi possível concluir a autenticação com o Google.", "danger")
        return redirect(url_for("auth.login"))

    google_id = userinfo.get("sub")
    google_email = userinfo.get("email", "")
    google_name = userinfo.get("name") or google_email.split("@")[0]

    if not google_id:
        flash("O Google não retornou um identificador de conta válido.", "danger")
        return redirect(url_for("auth.login"))

    # --- 3. Localiza ou cria o perfil local ---
    # Prioridade: (a) conta já vinculada pelo google_id;
    #             (b) conta existente com mesmo e-mail → vincula automaticamente;
    #             (c) novo provisionamento com perfil pendente.
    user = db.session.execute(
        select(User).where(User.google_id == google_id)
    ).scalars().first()

    if not user and google_email:
        user = db.session.execute(
            select(User).where(User.email == google_email)
        ).scalars().first()

    try:
        if user:
            # Vincula/atualiza o google_id se ainda não estava registrado
            if not user.google_id:
                user.google_id = google_id
            user.google_email = google_email
            db.session.commit()
        else:
            # Auto-provisionamento: conta Google nova no sistema
            user = User(
                name=google_name,
                email=google_email,
                password="",
                role="pendente",
                is_ad_user=False,
                is_active=True,
                first_login=False,
                google_id=google_id,
                google_email=google_email,
            )
            db.session.add(user)
            db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao persistir identidade Google OAuth.")
        flash("Erro interno ao registrar sua conta Google. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    if not user.is_active:
        flash("Sua conta está desativada. Entre em contato com o administrador.", "danger")
        return redirect(url_for("auth.login"))

    login_user(user)
    session.permanent = True
    if user.unidade_id:
        session["unidade_id"] = user.unidade_id
    else:
        session.pop("unidade_id", None)

    register_security_log("Acesso via Google", f"Usuário {user.name} ({google_email}) autenticado pelo Google OAuth.")

    if user.role == "pendente":
        flash("Conta Google reconhecida. Aguarde a aprovação do administrador para acessar o sistema.", "info")
        return redirect(url_for("auth.aguardando_aprovacao"))

    return redirect(url_for("main.dashboard"))


# ====================== ROTAS ADMINISTRAÇÃO ======================

@bp.route('/admin/painel')
@login_required
def painel_admin():
    if current_user.role != 'admin':
        flash("Quebra de Hierarquia: O Painel administrativo está bloqueado para você.", "danger")
        return redirect(url_for('main.dashboard'))

    # Nota técnica: o painel administrativo só deve expor dados de usuários e unidades
    # para o perfil de administrador, preservando o modelo RBAC atual.

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
        if usuario.is_ad_user:
            flash("Usuários federados pelo LDAP não possuem senha local para resetar no banco.", "warning")
            return redirect(url_for('auth.painel_admin'))

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
    if current_user.is_ad_user:
        flash('Usuários federados pelo LDAP não precisam alterar uma senha local no banco.', 'info')
        return redirect(url_for('main.dashboard'))

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

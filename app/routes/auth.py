from flask import Blueprint, current_app, render_template, request, redirect, flash, url_for, abort, session
from flask_login import login_user, logout_user, login_required, current_user
from sqlalchemy import select
from datetime import datetime, timedelta
from collections import defaultdict
import os
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
        # _build_ldap_bind_user retorna uma string — encapsulamos em lista para o .in_().
        ldap_candidate = _build_ldap_bind_user(
            email,
            current_app.config.get("LDAP_DOMAIN"),
        )
        lookup_candidates = list({email, ldap_candidate}) if ldap_candidate else [email]
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


# =============================================================================
# ROTAS — AUTENTICAÇÃO GOOGLE OAUTH2
# =============================================================================
#
# Fluxo resumido:
#   1. /auth/google            → gera state anti-CSRF e redireciona para o Google.
#   2. /auth/google/callback   → recebe o código, troca por tokens, resolve identidade.
#   3. /auth/google/confirmar  → tela de confirmação quando um e-mail Google coincide
#                                com uma conta local (AD ou manual) ainda não vinculada.
#   4. /auth/google/desvincular → desvincula conta Google de um usuário (admin).
#
# Pré-requisito: GOOGLE_OAUTH_CLIENT_ID, GOOGLE_OAUTH_CLIENT_SECRET e
# GOOGLE_OAUTH_REDIRECT_URI devem estar definidos no ambiente.
# Quando GOOGLE_OAUTH_CLIENT_ID estiver ausente, as rotas abortam com 404
# para não expor endpoints inativos.
# =============================================================================

# Chave usada para guardar o state anti-CSRF na sessão Flask.
_GOOGLE_OAUTH_STATE_KEY = "_google_oauth_state"

# Chave usada para guardar o code_verifier PKCE na sessão Flask.
# A google_auth_oauthlib gera um code_verifier automaticamente ao chamar
# authorization_url() e inclui o code_challenge derivado na URL enviada ao Google.
# O verifier precisa ser salvo na sessão para ser reenviado no fetch_token do callback.
_GOOGLE_OAUTH_VERIFIER_KEY = "_google_oauth_verifier"

# Chave usada para guardar temporariamente os dados de um login Google pendente
# de confirmação de vínculo com conta local preexistente.
_GOOGLE_PENDING_KEY = "_google_pending_link"

# Escopos solicitados ao Google. "openid email profile" é o mínimo necessário
# para obter sub (ID permanente), e-mail verificado e nome de exibição.
_GOOGLE_SCOPES = [
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
    "https://www.googleapis.com/auth/userinfo.profile",
]


def _get_google_flow(state: str | None = None):
    """Constrói e retorna o objeto ``google_auth_oauthlib.flow.Flow``.

    Centraliza a criação para que as rotas de início e de callback usem
    exatamente a mesma configuração, evitando divergências de redirect_uri.

    O parâmetro ``state`` deve ser informado ao recriar o Flow no callback,
    para que a biblioteca possa validar internamente que o state da
    ``authorization_response`` bate com o state da sessão OAuth.

    Retorna ``None`` quando as credenciais não estão configuradas no ambiente,
    permitindo que as rotas abortem com 404 de forma limpa.
    """
    client_id = current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    redirect_uri = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")

    if not all([client_id, client_secret, redirect_uri]):
        return None

    from google_auth_oauthlib.flow import Flow

    # Formato esperado pela biblioteca: dicionário equivalente ao client_secrets.json
    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }

    flow = Flow.from_client_config(
        client_config=client_config,
        scopes=_GOOGLE_SCOPES,
        redirect_uri=redirect_uri,
        # Restaura o state interno do oauth2session para que parse_request_uri_response
        # consiga validar o state recebido na authorization_response do callback.
        state=state,
    )
    return flow


@bp.route('/auth/google')
def google_login():
    """Inicia o fluxo OAuth2 com o Google.

    Gera um ``state`` aleatório, salva na sessão para validação posterior
    (proteção CSRF do OAuth), e redireciona o navegador para a tela de
    consentimento do Google.

    Aborta com 404 quando as credenciais OAuth não estão configuradas no
    ambiente, evitando que um endpoint quebrado seja exposto.

    Em desenvolvimento com ``FLASK_DEBUG=true`` e redirect URI ``http://``,
    define ``OAUTHLIB_INSECURE_TRANSPORT=1`` automaticamente para permitir
    que a biblioteca google-auth-oauthlib aceite conexões sem TLS.
    Essa permissão nunca é ativada em produção.
    """
    # Libera transporte HTTP apenas em desenvolvimento — a biblioteca
    # google-auth-oauthlib exige HTTPS por padrão e rejeita http://localhost
    # sem esta variável, abortando o fluxo antes mesmo de redirecionar.
    if current_app.debug:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    flow = _get_google_flow()
    if flow is None:
        abort(404)

    # Gera token de estado imprevisível para proteger o callback contra CSRF.
    # O state é gravado na sessão Flask antes do redirect e recuperado no callback.
    state = secrets.token_urlsafe(32)
    session[_GOOGLE_OAUTH_STATE_KEY] = state

    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        state=state,
        # Solicita seleção de conta mesmo que o usuário já esteja autenticado,
        # evitando logins automáticos indesejados em máquinas compartilhadas.
        prompt="select_account",
    )

    # A google_auth_oauthlib gera um code_verifier PKCE automaticamente e inclui
    # o code_challenge derivado na URL de autorização. O verifier precisa ser
    # persistido na sessão para ser reenviado ao Google no fetch_token do callback.
    # Sem isso o Google rejeita a troca com "Missing code verifier".
    if flow.code_verifier:
        session[_GOOGLE_OAUTH_VERIFIER_KEY] = flow.code_verifier

    # Força gravação imediata do cookie antes do redirect cross-site.
    session.modified = True

    return redirect(authorization_url)


@bp.route('/auth/google/callback')
def google_callback():
    """Processa o retorno do Google após o consentimento do usuário.

    Etapas executadas:
      1. Garante que ``OAUTHLIB_INSECURE_TRANSPORT`` esteja ativo em dev
         (necessário para ``fetch_token`` aceitar http://localhost).
      2. Valida o ``state`` anti-CSRF.
      3. Detecta erros explícitos retornados pelo Google (ex.: acesso negado).
      4. Troca o ``code`` por tokens e extrai ``sub``, ``email`` e ``name``.
      5. Resolve a identidade no banco — três caminhos possíveis:
         a. ``google_id`` já vinculado → login direto.
         b. E-mail coincide com conta local (AD/manual) sem vínculo Google
            → guarda dados na sessão e redireciona para confirmação de fusão.
         c. Nenhum usuário encontrado → autoprovisionamento com role ``pendente``.
      6. Após resolução, aplica as mesmas regras de sessão e log do login local.
    """
    # Mantém a liberação de HTTP no callback — fetch_token também valida o esquema.
    if current_app.debug:
        os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"

    # ── 1. Validação do state anti-CSRF ──────────────────────────────────────
    state_recebido = request.args.get("state", "")
    state_esperado = session.pop(_GOOGLE_OAUTH_STATE_KEY, None)

    if not state_esperado or not secrets.compare_digest(state_recebido, state_esperado):
        current_app.logger.warning(
            "Google OAuth2: state inválido ou ausente. IP: %s", request.remote_addr
        )
        flash("Sessão expirada ou requisição inválida. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    # ── 2. Erros retornados pelo Google (ex.: usuário cancelou) ──────────────
    erro_google = request.args.get("error")
    if erro_google:
        current_app.logger.info(
            "Google OAuth2: acesso negado pelo usuário. Erro: %s. IP: %s",
            erro_google,
            request.remote_addr,
        )
        flash("Acesso negado. O login com Google foi cancelado.", "warning")
        return redirect(url_for("auth.login"))

    # Recria o Flow passando o state esperado para que a biblioteca valide
    # internamente o state contido na authorization_response.
    # Sem isso, self._state do oauth2session fica None e o fetch_token
    # pode rejeitar ou ignorar o state da URL de retorno.
    flow = _get_google_flow(state=state_esperado)
    if flow is None:
        abort(404)

    # ── 3. Troca do código por tokens e extração de identidade ───────────────
    try:
        # Recupera o code_verifier PKCE gerado automaticamente pelo flow no início.
        # Obrigatório quando o Google recebeu um code_challenge na URL de autorização.
        code_verifier = session.pop(_GOOGLE_OAUTH_VERIFIER_KEY, None)

        # Reconstrói a URL de resposta garantindo que o esquema bata com o
        # redirect_uri configurado, evitando divergências entre http/https.
        redirect_uri_base = current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI", "")
        query_string = request.query_string.decode("utf-8")
        authorization_response = f"{redirect_uri_base}?{query_string}"

        # Passa o code_verifier quando disponível — o Google rejeita a troca
        # sem ele quando code_challenge foi enviado na URL de autorização.
        fetch_kwargs: dict = {"authorization_response": authorization_response}
        if code_verifier:
            fetch_kwargs["code_verifier"] = code_verifier

        flow.fetch_token(**fetch_kwargs)

        from google.oauth2 import id_token as google_id_token
        import google.auth.transport.requests as google_requests

        # Valida e decodifica o ID Token retornado pelo Google.
        # A verificação de assinatura e expiração é feita pela biblioteca.
        # clock_skew_in_seconds tolera pequenas divergências de relógio entre
        # a máquina local e os servidores do Google (comum em ambientes de dev).
        # O valor de 10 segundos é conservador e seguro — o padrão da biblioteca é 0.
        id_info = google_id_token.verify_oauth2_token(
            flow.credentials.id_token,
            google_requests.Request(),
            current_app.config.get("GOOGLE_OAUTH_CLIENT_ID"),
            clock_skew_in_seconds=10,
        )
    except Exception as exc:
        # Loga o erro completo para diagnóstico — o flash ao usuário é genérico
        # para não expor detalhes internos do fluxo OAuth.
        current_app.logger.exception(
            "Google OAuth2: falha ao obter ou validar o token. Erro: %s. IP: %s",
            exc,
            request.remote_addr,
        )
        # Em modo debug, relança a exceção para que o Werkzeug debugger mostre
        # o traceback completo no navegador — facilita o diagnóstico sem precisar
        # olhar o terminal. Em produção, exibe apenas a mensagem genérica.
        if current_app.debug:
            raise
        flash("Falha ao comunicar com o Google. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    # Campos extraídos do ID Token (sub é imutável; email pode mudar)
    google_sub = id_info.get("sub")
    google_email = id_info.get("email", "").lower().strip()
    google_name = id_info.get("name", google_email)
    email_verificado = id_info.get("email_verified", False)

    if not google_sub or not google_email:
        flash("Não foi possível obter os dados da sua conta Google.", "danger")
        return redirect(url_for("auth.login"))

    if not email_verificado:
        flash("Somente contas Google com e-mail verificado são aceitas.", "warning")
        return redirect(url_for("auth.login"))

    # ── 4a. Conta já vinculada por google_id (caminho principal) ─────────────
    user = db.session.execute(
        select(User).where(User.google_id == google_sub)
    ).scalars().first()

    if user:
        return _concluir_login_google(user, google_email, origem="vínculo existente")

    # ── 4b. E-mail coincide com conta local (AD ou manual) sem google_id ─────
    user_por_email = db.session.execute(
        select(User).where(User.email == google_email)
    ).scalars().first()

    if user_por_email:
        # Guarda os dados Google na sessão e redireciona para confirmação explícita.
        # Não vincula automaticamente — a decisão deve ser do usuário.
        session[_GOOGLE_PENDING_KEY] = {
            "sub": google_sub,
            "email": google_email,
            "name": google_name,
            "user_id": user_por_email.id,
        }
        return redirect(url_for("auth.google_confirmar_vinculo"))

    # ── 4c. Nenhum usuário encontrado → autoprovisionamento como pendente ─────
    try:
        from app.utils.logica import formatar_nome_proprio

        nome_formatado = formatar_nome_proprio(google_name)
        novo_usuario = User(
            name=nome_formatado,
            email=google_email,
            password=None,
            role="pendente",
            is_active=True,
            is_ad_user=False,
            first_login=False,
            google_id=google_sub,
            google_email=google_email,
        )
        db.session.add(novo_usuario)
        db.session.commit()
        current_app.logger.info(
            "Google OAuth2: novo usuário provisionado como pendente. E-mail: %s", google_email
        )
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Google OAuth2: falha ao autoprovisionamento. E-mail: %s", google_email
        )
        flash("Erro ao registrar sua conta Google no sistema. Contate o administrador.", "danger")
        return redirect(url_for("auth.login"))

    return _concluir_login_google(novo_usuario, google_email, origem="autoprovisionado via Google")


@bp.route('/auth/google/confirmar', methods=['GET', 'POST'])
def google_confirmar_vinculo():
    """Tela de confirmação explícita de fusão entre conta Google e conta local.

    Exibida quando o e-mail retornado pelo Google coincide com uma conta local
    já existente (tipicamente uma conta de domínio AD/LDAP) que ainda não
    possui ``google_id`` vinculado.

    O usuário pode:
      - Confirmar a fusão: ``google_id`` é gravado na conta local e o login prossegue.
      - Recusar: os dados temporários são descartados da sessão e o usuário retorna
        ao login sem nenhuma alteração no banco.

    A confirmação é protegida por CSRF (token WTF via campo oculto no template).
    """
    dados_pendentes = session.get(_GOOGLE_PENDING_KEY)

    # Se não há dados pendentes, redireciona para login (acesso direto inválido)
    if not dados_pendentes:
        return redirect(url_for("auth.login"))

    user = db.session.get(User, dados_pendentes.get("user_id"))
    if not user:
        session.pop(_GOOGLE_PENDING_KEY, None)
        flash("Conta local não encontrada. Tente novamente.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        acao = request.form.get("acao")

        if acao == "confirmar":
            try:
                user.google_id = dados_pendentes["sub"]
                user.google_email = dados_pendentes["email"]
                db.session.commit()
                session.pop(_GOOGLE_PENDING_KEY, None)
                register_security_log(
                    "Vínculo Google",
                    f"Conta Google ({dados_pendentes['email']}) vinculada ao perfil local de {user.email}.",
                )
                flash("Conta Google vinculada com sucesso!", "success")
                return _concluir_login_google(
                    user, dados_pendentes["email"], origem="fusão confirmada pelo usuário"
                )
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Google OAuth2: falha ao vincular google_id ao usuário %s.", user.email
                )
                flash("Erro ao vincular conta Google. Tente novamente.", "danger")
                return redirect(url_for("auth.login"))

        # Ação "recusar" ou qualquer valor inválido — descarta dados e volta ao login
        session.pop(_GOOGLE_PENDING_KEY, None)
        register_security_log(
            "Vínculo Google Recusado",
            f"Usuário recusou vínculo de conta Google ({dados_pendentes.get('email')}) "
            f"ao perfil {user.email}.",
        )
        flash("Vínculo com Google cancelado. Use suas credenciais normais para entrar.", "info")
        return redirect(url_for("auth.login"))

    # GET — renderiza a tela de confirmação
    return render_template(
        "auth/confirmar_vinculo_google.html",
        google_email=dados_pendentes.get("email"),
        google_name=dados_pendentes.get("name"),
        user=user,
    )


@bp.route('/admin/usuarios/desvincular-google/<int:id>', methods=['POST'])
@login_required
def desvincular_google(id):
    """Remove o vínculo entre uma conta Google e o perfil local do usuário.

    Exclusivo para administradores. Zera os campos ``google_id`` e
    ``google_email`` do usuário indicado, sem afetar nenhum outro dado
    (role, senha local, vínculo AD, etc.).

    Casos de uso típicos:
      - Usuário trocou de conta Google e precisa vincular a nova.
      - Conta Google comprometida — admin remove o acesso social preventivamente.
    """
    if current_user.role != "admin":
        abort(403)

    usuario = db.session.get(User, id)
    if not usuario:
        flash("Usuário não encontrado.", "warning")
        return redirect(url_for("auth.painel_admin"))

    if not usuario.google_id:
        flash(f"{usuario.name} não possui conta Google vinculada.", "info")
        return redirect(url_for("auth.painel_admin"))

    try:
        google_email_anterior = usuario.google_email or usuario.google_id
        usuario.google_id = None
        usuario.google_email = None
        db.session.commit()
        register_security_log(
            "Desvínculo Google",
            f"Admin removeu vínculo Google ({google_email_anterior}) do perfil {usuario.email}.",
        )
        flash(f"Conta Google desvinculada de {usuario.name}.", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception(
            "Falha ao desvincular google_id do usuário %s.", usuario.email
        )
        flash("Erro ao desvincular conta Google. Tente novamente.", "danger")

    return redirect(url_for("auth.painel_admin"))


def _concluir_login_google(user: "User", google_email_atual: str, origem: str) -> "Response":
    """Finaliza o login de um usuário autenticado via Google.

    Centraliza a lógica pós-autenticação para os três caminhos do callback
    (vínculo existente, fusão confirmada, autoprovisionado), mantendo o
    comportamento idêntico ao login local/AD:
      - Verifica se a conta está ativa.
      - Chama ``login_user`` do Flask-Login.
      - Marca a sessão como permanente e registra ``unidade_id``.
      - Registra log de auditoria.
      - Redireciona usuários ``pendente`` para a tela de aprovação.

    O parâmetro ``origem`` é usado apenas no log de auditoria para rastreabilidade.
    """
    if not user.is_active:
        flash("Sua conta está desativada. Entre em contato com o administrador.", "danger")
        return redirect(url_for("auth.login"))

    # Atualiza o e-mail Google registrado na última autenticação (sem alterar email principal)
    try:
        if user.google_email != google_email_atual:
            user.google_email = google_email_atual
            db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.warning(
            "Google OAuth2: falha ao atualizar google_email para %s.", user.email
        )

    login_user(user)
    session.permanent = True

    if user.unidade_id:
        session["unidade_id"] = user.unidade_id
    else:
        session.pop("unidade_id", None)

    register_security_log(
        "Acesso via Google",
        f"Usuário {user.name} autenticado pelo Google OAuth2 ({origem}).",
    )

    if user.role == "pendente":
        flash(
            "Bem-vindo! Seu cadastro foi recebido e aguarda aprovação do administrador.",
            "info",
        )
        return redirect(url_for("auth.aguardando_aprovacao"))

    return redirect(url_for("main.dashboard"))

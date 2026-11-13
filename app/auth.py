"""
================================================================================
AUTH.PY - Autenticação, autorização e administração de usuários
================================================================================

Cobre:
    - Login híbrido (local + LDAP/AD + Google OAuth)
    - Rotas administrativas (painel, cadastro de usuário, unidades)
    - Auditoria (logs)
    - Troca de senha do próprio usuário
    - Disparo de e-mail para novo usuário e reset de senha
"""

from flask import (
    Blueprint,
    current_app,
    render_template,
    request,
    redirect,
    flash,
    url_for,
    abort,
    session,
)
from flask_login import logout_user, login_required, current_user
from sqlalchemy import select
from datetime import datetime, timedelta
import ipaddress
import json
import secrets
import hashlib

from app.models import User, LogAcao, Unidade, ConfiguracaoSistema
from app.models.enums import UserRole
from app.database import db
from app.services.maintenance import MANUTENCAO_CONFIG_KEY, is_maintenance_enabled
from app.services.sessao import iniciar_sessao, revogar_sem_commit, revogar_sessoes
from app.utils.disparo_email import send_email
from app.services.auth_service import (
    _build_ldap_bind_user,
    authenticate_against_ldap,
    register_security_log,
    validate_password_strength,
    generate_secure_random_password,
)

bp = Blueprint("auth", __name__)

# Rate limit por conta e por IP (S1-11). Configuráveis por ambiente.
from config import get_int

_CONTA_MAX_FALHAS = get_int("LOGIN_CONTA_MAX_FALHAS", 5)
_CONTA_JANELA_SEGUNDOS = get_int("LOGIN_CONTA_JANELA_SEGUNDOS", 900)
_CONTA_BLOQUEIO_MINUTOS_BASE = get_int("LOGIN_CONTA_BLOQUEIO_MINUTOS", 15)
_IP_MAX_FALHAS = get_int("LOGIN_IP_MAX_FALHAS", 30)
_IP_JANELA_SEGUNDOS = get_int("LOGIN_IP_JANELA_SEGUNDOS", 900)
_IP_BLOQUEIO_MINUTOS = get_int("LOGIN_IP_BLOQUEIO_MINUTOS", 15)
_RETENCAO_DIAS = get_int("LOGIN_RETENCAO_DIAS", 30)

from app.models import LoginControle
from app.utils.hash_seguro import hmac_identificador
from app.models.base import get_local_now


def _agora():
    return get_local_now().replace(tzinfo=None)


def _normalizar_email_login(email: str) -> str:
    return (email or "").strip().lower()


def chave_conta(email: str) -> str:
    """Chave (HMAC) da conta para login_controle."""
    return hmac_identificador(_normalizar_email_login(email))


_chave_conta = chave_conta


def chave_ip(ip: str) -> str:
    """Chave (HMAC) do IP para login_controle."""
    return hmac_identificador(ip or "unknown")


_chave_ip = chave_ip


def _minutos_bloqueio_conta(nivel: int) -> int:
    # escalonamento 15 -> 30 -> 60 (teto 60)
    base = _CONTA_BLOQUEIO_MINUTOS_BASE
    # nivel 1 -> 15, 2 -> 30, 3 -> 60
    if nivel <= 1:
        return base
    if nivel == 2:
        return base * 2
    return min(base * 4, 60)


def _obter_controle(escopo: str, chave_hash: str):
    return LoginControle.query.filter_by(escopo=escopo, chave_hash=chave_hash).first()


def _bloqueio_ativo(reg) -> tuple[bool, int]:
    if not reg or not reg.bloqueado_ate:
        return False, 0
    agora = _agora()
    if reg.bloqueado_ate > agora:
        restante = int((reg.bloqueado_ate - agora).total_seconds() // 60) + 1
        return True, restante
    return False, 0


def _limpar_retencao():
    # apagar linhas sem atividade há mais de 30 dias (oportunista)
    try:
        limite = _agora() - timedelta(days=_RETENCAO_DIAS)
        LoginControle.query.filter(LoginControle.atualizado_em < limite).delete()
        db.session.commit()
    except Exception:
        db.session.rollback()


def _verificar_bloqueio_conta_ou_ip(email: str, ip: str):
    """Retorna (bloqueado: bool, minutos_restantes: int)."""
    # conta
    reg_c = _obter_controle("conta", _chave_conta(email))
    bloq, mins = _bloqueio_ativo(reg_c)
    if bloq:
        return True, mins
    # ip
    reg_i = _obter_controle("ip", _chave_ip(ip))
    bloq, mins = _bloqueio_ativo(reg_i)
    if bloq:
        return True, mins
    return False, 0


def _registrar_falha_conta(email: str):
    chave = _chave_conta(email)
    agora = _agora()
    reg = _obter_controle("conta", chave)
    if reg is None:
        reg = LoginControle(
            escopo="conta",
            chave_hash=chave,
            falhas=1,
            janela_inicio=agora,
            nivel=0,
            atualizado_em=agora,
        )
        db.session.add(reg)
        db.session.commit()
        return reg
    # janela de 15 min expirou -> nova janela
    if (
        reg.janela_inicio is None
        or (agora - reg.janela_inicio).total_seconds() >= _CONTA_JANELA_SEGUNDOS
    ):
        # escalonamento dentro de 24h
        if (
            reg.janela_inicio is not None
            and (agora - reg.janela_inicio).total_seconds() < 86400
            and reg.bloqueado_ate is not None
        ):
            reg.nivel = min((reg.nivel or 0) + 1, 3)
            if reg.nivel < 1:
                reg.nivel = 1
        elif (
            reg.janela_inicio is None
            or (agora - reg.janela_inicio).total_seconds() >= 86400
        ):
            reg.nivel = 0
        reg.falhas = 1
        reg.janela_inicio = agora
        reg.bloqueado_ate = None
    else:
        reg.falhas += 1
    reg.atualizado_em = agora
    if reg.falhas >= _CONTA_MAX_FALHAS:
        nivel = reg.nivel if reg.nivel and reg.nivel >= 1 else 1
        if nivel == 1:
            mins = _CONTA_BLOQUEIO_MINUTOS_BASE
        elif nivel == 2:
            mins = _CONTA_BLOQUEIO_MINUTOS_BASE * 2
        else:
            mins = min(_CONTA_BLOQUEIO_MINUTOS_BASE * 4, 60)
        reg.bloqueado_ate = agora + timedelta(minutes=mins)
        # preparar próxima reincidência
        reg.nivel = min(nivel + 1, 3)
    db.session.commit()
    return reg


def _registrar_falha_ip(ip: str):
    chave = _chave_ip(ip)
    agora = _agora()
    reg = _obter_controle("ip", chave)
    if reg is None:
        reg = LoginControle(
            escopo="ip",
            chave_hash=chave,
            falhas=1,
            janela_inicio=agora,
            nivel=0,
            atualizado_em=agora,
        )
        db.session.add(reg)
        db.session.commit()
        return reg
    if (
        reg.janela_inicio is None
        or (agora - reg.janela_inicio).total_seconds() >= _IP_JANELA_SEGUNDOS
    ):
        reg.falhas = 1
        reg.janela_inicio = agora
        reg.bloqueado_ate = None
    else:
        reg.falhas += 1
    reg.atualizado_em = agora
    if reg.falhas >= _IP_MAX_FALHAS:
        reg.bloqueado_ate = agora + timedelta(minutes=_IP_BLOQUEIO_MINUTOS)
    db.session.commit()
    return reg


def _zerar_conta(email: str):
    chave = _chave_conta(email)
    reg = _obter_controle("conta", chave)
    if reg:
        reg.falhas = 0
        reg.nivel = 0
        reg.bloqueado_ate = None
        reg.janela_inicio = None
        reg.atualizado_em = _agora()
        db.session.commit()


@bp.route("/aguardando-aprovacao")
@login_required
def aguardando_aprovacao():
    """Exibe a página de espera para usuários AD/LDAP recém-provisionados.

    Quando o usuário do domínio passa pela validação do servidor, ele é criado
    localmente com perfil `pendente`. Enquanto essa etapa não for liberada pelo
    administrador, o acesso ao sistema fica restrito a esta tela, evitando que
    o perfil alcance áreas operacionais sem a devida classificação.
    """
    if current_user.role != UserRole.PENDENTE:
        return redirect(url_for("main.painel"))
    return render_template("aguardando.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    """Controlador de login híbrido: local primeiro e LDAP/AD como fallback.

    Usuários locais com senha persistida continuam no fluxo de troca
    obrigatória na primeira autenticação. Usuários federados pelo AD/LDAP
    são provisionados localmente apenas quando o servidor do domínio os
    valida e não precisam de senha local persistida.
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")

        ip_address = request.remote_addr or "unknown"
        try:
            _limpar_retencao()
        except Exception:
            db.session.rollback()
        # checagem de bloqueio ANTES de qualquer consulta de senha/AD
        try:
            bloqueado, mins = _verificar_bloqueio_conta_ou_ip(email, ip_address)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao consultar rate limit de login.")
            flash(
                "Sistema temporariamente indisponível. Tente novamente em instantes.",
                "danger",
            )
            return redirect(url_for("auth.login"))
        if bloqueado:
            flash(f"Muitas tentativas. Tente novamente em {mins} minutos.", "danger")
            return redirect(url_for("auth.login"))

        # Defensivo contra envio vazio
        if not email or not password:
            flash("Informe Email e Senha.", "warning")
            try:
                _registrar_falha_conta(email)
                _registrar_falha_ip(ip_address)
            except Exception:
                db.session.rollback()
            return redirect(url_for("auth.login"))

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
        try:
            user = (
                db.session.execute(
                    select(User).where(User.email.in_(lookup_candidates))
                )
                .scalars()
                .first()
            )
        except Exception:
            current_app.logger.exception(
                "Falha ao consultar usuário no banco durante login."
            )
            flash(
                "Sistema temporariamente indisponível. Tente novamente em instantes.",
                "danger",
            )
            return redirect(url_for("auth.login"))

        login_ok = False
        ldap_identity = email
        if "@" not in ldap_identity and current_app.config.get("LDAP_DOMAIN"):
            ldap_identity = f"{ldap_identity}@{current_app.config.get('LDAP_DOMAIN')}"

        # === 1. TENTATIVA DE AUTENTICAÇÃO LOCAL (HASH) ===
        # Tempo constante: se usuário não existe ou não tem senha, executar
        # check_password_hash contra hash dummy de mesmo custo.
        _DUMMY_HASH = "pbkdf2:sha256:600000$abcdefghijklmnop$0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
        if user and user.password:
            if user.check_password(password):
                login_ok = True
        else:
            from werkzeug.security import check_password_hash

            check_password_hash(_DUMMY_HASH, password)

        # === 2. TENTATIVA DE AUTENTICAÇÃO NO DOMÍNIO AD/LDAP ===
        if not login_ok:
            if authenticate_against_ldap(ldap_identity, password):
                login_ok = True
                # O autoprovisionamento providencia a vida local de um AD Autorizado mas sem cadastro local
                if not user:
                    try:
                        from app.utils.logica import formatar_nome_proprio

                        user = User(
                            name=formatar_nome_proprio(
                                ldap_identity.split("@")[0].replace(".", " ")
                            ),
                            email=ldap_identity,
                            password="",
                            role=UserRole.PENDENTE.value,  # trava de segurança total no sistema
                            is_ad_user=True,
                            is_active=True,
                            first_login=False,
                        )
                        db.session.add(user)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception(
                            "Falha no aprovisionamento automático via LDAP."
                        )
                        flash(
                            "Erro no banco local ao registrar sua entrada AD.", "danger"
                        )
                        login_ok = False
                elif user.email != ldap_identity:
                    try:
                        user.email = ldap_identity
                        db.session.add(user)
                        db.session.commit()
                    except Exception:
                        db.session.rollback()
                        current_app.logger.exception(
                            "Falha ao normalizar o e-mail do usuário AD no banco local."
                        )
                        flash("Erro ao normalizar seu cadastro local do AD.", "danger")
                        login_ok = False

        # === 3. CONCLUSÃO COM SUCESSO ===
        if login_ok and user and user.is_active:
            try:
                _zerar_conta(email)
            except Exception:
                db.session.rollback()
                current_app.logger.exception(
                    "Falha ao limpar rate limit após login válido."
                )
            iniciar_sessao(user)
            if user.unidade_id:
                session["unidade_id"] = user.unidade_id
            else:
                session.pop("unidade_id", None)

            register_security_log(
                "Acesso Aprovado", f"Usuário {user.name} acessou o sistema."
            )

            # A troca obrigatória de senha deve ocorrer apenas para usuários
            # locais com senha persistida no banco. Usuários federados pelo AD
            # seguem para a fase de aprovação do perfil e não passam por senha local.
            if user.first_login and not user.is_ad_user:
                flash(
                    "Bem-vindo! Por segurança, defina sua senha pessoal antes de continuar.",
                    "warning",
                )
                return redirect(url_for("auth.trocar_senha"))

            return redirect(url_for("main.painel"))

        # Falha total ou Desabilitado
        register_security_log(
            "Aviso de Invasão/Falha",
            f"Login declinado para alvo hash: {hmac_identificador(email)[:12]}",
        )
        try:
            _registrar_falha_conta(email)
            _registrar_falha_ip(ip_address)
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao persistir rate limit de login.")
            flash(
                "Sistema temporariamente indisponível. Tente novamente em instantes.",
                "danger",
            )
            return redirect(url_for("auth.login"))
        # mensagem
        reg_c2 = _obter_controle("conta", _chave_conta(email))
        msg = "Credenciais recusadas pelo domínio e banco de dados."
        if reg_c2 and reg_c2.falhas == 4 and reg_c2.bloqueado_ate is None:
            msg = "Credenciais recusadas pelo domínio e banco de dados. Atenção: resta 1 tentativa antes do bloqueio temporário."
        if reg_c2 and reg_c2.bloqueado_ate is not None:
            mins = int((reg_c2.bloqueado_ate - _agora()).total_seconds() // 60) + 1
            msg = f"Muitas tentativas. Tente novamente em {mins} minutos."
        flash(msg, "danger")
        return redirect(url_for("auth.login"))

    return render_template(
        "login.html",
        google_login_habilitado=bool(
            current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
            and current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")
        ),
    )


@bp.route("/logout", methods=["GET", "POST"])
def logout():
    """Encerra a sessão — só por POST (S1-16).

    GET é inócuo de propósito: link, pré-busca do navegador ou `<img>` não
    podem derrubar a sessão. Autenticado volta ao painel; anônimo, ao login.
    O POST exige CSRF (validação global do Flask-WTF).
    """
    if request.method != "POST":
        if current_user.is_authenticated:
            return redirect(url_for("main.painel"))
        return redirect(url_for("auth.login"))

    if not current_user.is_authenticated:
        return redirect(url_for("auth.login"))

    register_security_log("Logoff", "Sessão encerrada voluntariamente.")
    # S1-06: revoga a geração atual — o cookie copiado para outro navegador
    # deixa de autenticar na hora. O evento de auditoria já é o "Logoff".
    revogar_sessoes(current_user.id, "logout", registrar_log=False)
    logout_user()
    session.clear()
    return redirect(url_for("auth.login"))


# ====================== GOOGLE OAUTH2 ======================

_GOOGLE_AUTH_URI = "https://accounts.google.com/o/oauth2/v2/auth"
_GOOGLE_TOKEN_URI = "https://oauth2.googleapis.com/token"
_GOOGLE_USERINFO_URI = "https://openidconnect.googleapis.com/v1/userinfo"
_GOOGLE_SCOPES = ["openid", "email", "profile"]


@bp.route("/auth/google/login")
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
                    "client_secret": current_app.config.get(
                        "GOOGLE_OAUTH_CLIENT_SECRET"
                    ),
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
        session["google_code_verifier"] = flow.code_verifier
        return redirect(authorization_url)

    except Exception:
        current_app.logger.exception("Falha ao iniciar fluxo OAuth Google.")
        flash(
            "Não foi possível iniciar o login com Google. Tente outra forma de acesso.",
            "danger",
        )
        return redirect(url_for("auth.login"))


@bp.route("/auth/google/callback")
def google_callback():
    """Processa o retorno do Google após a tela de consentimento.

    Valida o state anti-CSRF, troca o código de autorização por tokens,
    obtém o perfil do usuário via UserInfo e faz o login local —
    criando ou vinculando a conta se necessário.
    """
    # --- 1. Verificação CSRF ---
    state_retornado = request.args.get("state", "")
    state_esperado = session.get("google_oauth_state")
    if not state_esperado or state_retornado != state_esperado:
        session.pop("google_oauth_state", None)
        flash(
            "Falha de segurança na verificação do estado OAuth. Tente novamente.",
            "danger",
        )
        return redirect(url_for("auth.login"))
    session.pop("google_oauth_state", None)

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
        flow.code_verifier = session.pop("google_code_verifier", None)

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

    if current_app.config.get(
        "GOOGLE_OAUTH_REQUIRE_EMAIL_VERIFIED", True
    ) and not userinfo.get("email_verified"):
        flash(
            "A conta Google precisa ter o e-mail verificado para continuar.", "danger"
        )
        return redirect(url_for("auth.login"))

    allowed_domains = current_app.config.get("GOOGLE_OAUTH_ALLOWED_DOMAINS") or []
    if allowed_domains:
        domain = google_email.rsplit("@", 1)[1].lower() if "@" in google_email else ""
        if domain not in {item.lower() for item in allowed_domains}:
            flash("Este e-mail não está autorizado para acesso ao sistema.", "danger")
            return redirect(url_for("auth.login"))

    # --- 3. Localiza ou cria o perfil local ---
    # Prioridade: (a) conta já vinculada pelo google_id;
    #             (b) conta existente com mesmo e-mail -> exige senha local antes de vincular;
    #             (c) novo provisionamento com perfil pendente.
    user = (
        db.session.execute(select(User).where(User.google_id == google_id))
        .scalars()
        .first()
    )

    if not user and google_email:
        user = (
            db.session.execute(select(User).where(User.email == google_email))
            .scalars()
            .first()
        )

    if user and not user.google_id:
        session["google_link_pending"] = {
            "user_id": user.id,
            "google_id": google_id,
            "google_email": google_email,
            "google_name": google_name,
            "created_at": int(datetime.now().timestamp()),
        }
        return redirect(url_for("auth.google_confirmar_vinculo"))

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
                role=UserRole.PENDENTE.value,
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
        flash(
            "Sua conta está desativada. Entre em contato com o administrador.", "danger"
        )
        return redirect(url_for("auth.login"))

    iniciar_sessao(user)
    if user.unidade_id:
        session["unidade_id"] = user.unidade_id
    else:
        session.pop("unidade_id", None)

    register_security_log(
        "Acesso via Google",
        f"Usuário {user.name} ({google_email}) autenticado pelo Google OAuth.",
    )

    if user.role == UserRole.PENDENTE:
        flash(
            "Conta Google reconhecida. Aguarde a aprovação do administrador para acessar o sistema.",
            "info",
        )
        return redirect(url_for("auth.aguardando_aprovacao"))

    return redirect(url_for("main.painel"))


# ====================== ROTAS ADMINISTRAÇÃO ======================


@bp.route("/admin/painel")
@login_required
def painel_admin():
    if current_user.role != UserRole.ADMIN:
        flash(
            "Quebra de Hierarquia: O Painel administrativo está bloqueado para você.",
            "danger",
        )
        return redirect(url_for("main.painel"))

    # Nota técnica: o painel administrativo só deve expor dados de usuários e unidades
    # para o perfil de administrador, preservando o modelo RBAC atual.

    usuarios = db.session.execute(select(User).order_by(User.name)).scalars().all()

    unidades = (
        db.session.execute(
            select(Unidade).where(Unidade.ativo == True).order_by(Unidade.nome)
        )
        .scalars()
        .all()
    )

    senha_gerada = session.pop("senha_gerada", None)

    # Bloqueios ativos (S1-11/S1-12, desbloqueio pelo admin D3)
    agora = _agora()
    bloqueios_ativos = (
        db.session.execute(
            select(LoginControle)
            .where(LoginControle.bloqueado_ate.isnot(None))
            .where(LoginControle.bloqueado_ate > agora)
            .order_by(LoginControle.bloqueado_ate.desc())
            .limit(50)
        )
        .scalars()
        .all()
    )

    return render_template(
        "admin/painel_admin.html",
        usuarios=usuarios,
        unidades=unidades,
        senha_gerada=senha_gerada,
        bloqueios_ativos=bloqueios_ativos,
        agora=agora,
    )


@bp.route("/admin/login-controle/desbloquear-conta", methods=["POST"])
@login_required
def desbloquear_conta():
    if current_user.role != UserRole.ADMIN:
        abort(403)
    email = request.form.get("email", "").strip()
    if not email or len(email) > 254:
        flash("Informe um e-mail válido.", "danger")
        return redirect(url_for("auth.painel_admin"))
    chave = chave_conta(email)
    reg = LoginControle.query.filter_by(escopo="conta", chave_hash=chave).first()
    encontrado = reg is not None
    if reg:
        reg.falhas = 0
        reg.bloqueado_ate = None
        reg.janela_inicio = None
        reg.nivel = 0
        reg.atualizado_em = _agora()
        db.session.commit()
        flash("Conta desbloqueada.", "success")
    else:
        flash("Nenhum bloqueio encontrado para esse identificador.", "warning")
    # auditoria
    log = LogAcao(
        usuario_id=current_user.id,
        usuario_nome=current_user.name,
        acao="Desbloqueio de login",
        detalhes=f'escopo=conta chave={chave[:8]} por_usuario_id={current_user.id} encontrado={"sim" if encontrado else "nao"}',
        ip=request.remote_addr,
        unidade_id=current_user.unidade_id,
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for("auth.painel_admin"))


@bp.route("/admin/login-controle/desbloquear-ip", methods=["POST"])
@login_required
def desbloquear_ip():
    if current_user.role != UserRole.ADMIN:
        abort(403)
    valor = request.form.get("ip", "").strip()
    try:
        ip_norm = str(ipaddress.ip_address(valor))
    except ValueError:
        flash("Informe um IP válido.", "danger")
        return redirect(url_for("auth.painel_admin"))
    chave = chave_ip(ip_norm)
    reg = LoginControle.query.filter_by(escopo="ip", chave_hash=chave).first()
    encontrado = reg is not None
    if reg:
        reg.falhas = 0
        reg.bloqueado_ate = None
        reg.janela_inicio = None
        reg.nivel = 0
        reg.atualizado_em = _agora()
        db.session.commit()
        flash("IP desbloqueado.", "success")
    else:
        flash("Nenhum bloqueio encontrado para esse identificador.", "warning")
    log = LogAcao(
        usuario_id=current_user.id,
        usuario_nome=current_user.name,
        acao="Desbloqueio de login",
        detalhes=f'escopo=ip chave={chave[:8]} por_usuario_id={current_user.id} encontrado={"sim" if encontrado else "nao"}',
        ip=request.remote_addr,
        unidade_id=current_user.unidade_id,
    )
    db.session.add(log)
    db.session.commit()
    return redirect(url_for("auth.painel_admin"))


@bp.route("/admin/cadastrar", methods=["POST"])
@login_required
def cadastrar_usuario():
    if current_user.role != UserRole.ADMIN:
        abort(403)

    email = request.form.get("email", "").strip()
    if db.session.execute(select(User).where(User.email == email)).scalar():
        flash("Este correio eletrônico corporativo já existe localmente!", "danger")
        return redirect(url_for("auth.painel_admin"))

    nome = (request.form.get("nome") or "").strip()
    senha = (request.form.get("password") or "").strip()
    gerar_senha_inicial = request.form.get("gerar_senha_inicial") in (
        "1",
        "true",
        "on",
        "yes",
    )

    if not nome:
        flash("Preencha todos os dados corretamente.", "warning")
        return redirect(url_for("auth.painel_admin"))

    foi_gerada = False
    if gerar_senha_inicial or not senha:
        senha = generate_secure_random_password()
        foi_gerada = True
    else:
        erros = validate_password_strength(senha)
        if erros:
            for erro in erros:
                flash(erro, "danger")
            return redirect(url_for("auth.painel_admin"))

    try:
        unidade_id = request.form.get("unidade_id")
        unidade_id = int(unidade_id) if unidade_id and unidade_id.isdigit() else None

        novo = User(
            name=nome,
            email=email,
            role=request.form.get("role"),
            unidade_id=unidade_id,
            first_login=True,
        )
        novo.set_password(senha)
        db.session.add(novo)
        db.session.commit()
        register_security_log("Cadastro Local", f"Admin gerou conta manual: {email}")
        # --- DISPARO DE E-MAIL ASSÍNCRONO ---
        # 1. Renderiza o HTML passando os dados dinâmicos para o Jinja2
        html_content = render_template(
            "emails/novo_usuario.html", nome=nome, email=email, senha=senha
        )

        # 2. Dispara o e-mail assíncrono com o HTML renderizado
        send_email(
            subject="[pautaON] Sua conta foi criada com sucesso",
            recipients=[email],
            body_html=html_content,
        )
        # -------------------------------------
        if foi_gerada:
            session["senha_gerada"] = {
                "nome": nome,
                "email": email,
                "senha": senha,
                "tipo": "cadastro",
            }
            flash(
                f"Conta para {nome} criada com sucesso! Senha inicial gerada: {senha}",
                "success",
            )
        else:
            flash(f"Conta para {nome} criada com sucesso!", "success")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao cadastrar usuário manualmente.")
        flash("Não foi possível gravar o novo usuário.", "danger")

    return redirect(url_for("auth.painel_admin"))


@bp.route("/usuarios/editar/<int:id>", methods=["POST"])
@login_required
def editar_usuario(id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    usuario = db.session.get(User, id)
    if usuario:
        try:
            # S1-22: valida role contra UserRole e e-mail (formato + unicidade).
            nome = (request.form.get("nome") or "").strip()
            email = (request.form.get("email") or "").strip()
            role = request.form.get("role")
            if not nome:
                flash("Nome é obrigatório.", "danger")
                return redirect(url_for("auth.painel_admin"))
            if not email or "@" not in email:
                flash("E-mail inválido.", "danger")
                return redirect(url_for("auth.painel_admin"))
            if role not in {r.value for r in UserRole}:
                flash("Perfil de acesso inválido.", "danger")
                return redirect(url_for("auth.painel_admin"))
            existente = db.session.execute(
                select(User).where(User.email == email, User.id != id)
            ).scalar()
            if existente:
                flash("Este e-mail já está em uso por outro usuário.", "danger")
                return redirect(url_for("auth.painel_admin"))

            # S1-06: mudar papel ou unidade muda o que a pessoa pode fazer; as
            # sessões abertas com o perfil antigo precisam cair.
            papel_antes = usuario.role
            unidade_antes = usuario.unidade_id
            alvo_id = usuario.id
            usuario.name = nome
            usuario.email = email
            usuario.role = role
            unidade_id = request.form.get("unidade_id")
            usuario.unidade_id = (
                int(unidade_id) if unidade_id and unidade_id.isdigit() else None
            )
            db.session.commit()
            if (usuario.role, usuario.unidade_id) != (papel_antes, unidade_antes):
                revogar_sessoes(alvo_id, "papel_ou_unidade")
            register_security_log(
                "Alteração de Cadastros", f"Admin alterou {usuario.email}."
            )
            flash(f"Dados atualizados no perfil de {usuario.name}!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao editar usuário.")
            flash("Falha ao salvar edição.", "danger")

    return redirect(url_for("auth.painel_admin"))


@bp.route("/usuarios/resetar/<int:id>", methods=["POST"])
@login_required
def resetar_senha(id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    usuario = db.session.get(User, id)
    if usuario:
        if usuario.is_ad_user:
            flash(
                "Usuários federados pelo LDAP não possuem senha local para resetar no banco.",
                "warning",
            )
            return redirect(url_for("auth.painel_admin"))

        try:
            nova_senha = generate_secure_random_password()
            alvo_id = usuario.id
            usuario.set_password(nova_senha)
            usuario.first_login = True
            db.session.commit()
            # S1-06: reset pelo admin derruba qualquer sessão aberta da conta.
            revogar_sessoes(alvo_id, "reset_senha_admin")
            register_security_log(
                "Reset de Senha", f"Senha de {usuario.email} resetada pelo admin."
            )
            # --- DISPARO DE E-MAIL ASSÍNCRONO ---
            html_content = render_template(
                "emails/senha_redefinida.html", nome=usuario.name, nova_senha=nova_senha
            )

            send_email(
                subject="[pautaON] Sua senha foi redefinida pelo administrador",
                recipients=[usuario.email],
                body_html=html_content,
            )
            # -------------------------------------
            session["senha_gerada"] = {
                "nome": usuario.name,
                "email": usuario.email,
                "senha": nova_senha,
                "tipo": "reset",
            }
            flash(
                f"Senha de {usuario.name} resetada com sucesso! Nova senha temporária gerada: {nova_senha}",
                "success",
            )
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao resetar senha de usuário.")
            flash("Erro ao resetar senha.", "warning")

    return redirect(url_for("auth.painel_admin"))


@bp.route("/usuarios/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_usuario(id):
    if current_user.role != UserRole.ADMIN:
        abort(403)

    usuario = db.session.get(User, id)
    if usuario and usuario.id != current_user.id:
        try:
            alvo_id = usuario.id
            email_alvo = usuario.email
            # S1-06: incrementa a geração na MESMA transação do DELETE. O
            # registro some de qualquer forma (o user_loader não acha a linha);
            # o contador evita que uma exclusão revertida deixe a sessão viva.
            revogar_sem_commit(alvo_id)
            db.session.delete(usuario)
            db.session.commit()
            register_security_log(
                "Sessões revogadas", f"motivo=exclusao usuario_id={alvo_id}"
            )
            register_security_log(
                "Remoção Grave", f"O perfil de {email_alvo} foi apagado."
            )
            flash(f"Usuário deletado de forma definitiva.", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao excluir usuário.")
            flash(
                "O banco recusou a deleção, provavelmente existem relatórios amarrados ao perfil.",
                "danger",
            )
    else:
        flash("Política de suicídio de perfil barrada. Peça a outro Admin.", "danger")

    return redirect(url_for("auth.painel_admin"))


@bp.route("/admin/unidades")
@login_required
def admin_unidades():
    """Lista todas as unidades para gestão administrativa."""
    if current_user.role != UserRole.ADMIN:
        abort(403)

    unidades = Unidade.query.order_by(Unidade.nome).all()
    return render_template("admin/unidades.html", unidades=unidades)


@bp.route("/admin/unidades/cadastrar", methods=["POST"])
@login_required
def cadastrar_unidade():
    """Cria uma nova unidade organizacional."""
    if current_user.role != UserRole.ADMIN:
        abort(403)

    nome = request.form.get("nome")
    if nome:
        try:
            nova = Unidade(nome=nome, ativo=True)
            db.session.add(nova)
            db.session.commit()
            register_security_log(
                "Gestão de Unidade", f"Cadastrada nova unidade: {nome}"
            )
            flash(f"Unidade '{nome}' criada com sucesso!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao criar unidade.")
            flash("Erro ao criar unidade.", "danger")

    return redirect(url_for("auth.admin_unidades"))


@bp.route("/admin/unidades/editar/<int:id>", methods=["POST"])
@login_required
def editar_unidade(id):
    """Atualiza dados de uma unidade existente."""
    if current_user.role != UserRole.ADMIN:
        abort(403)

    unidade = db.get_or_404(Unidade, id)
    nome_antigo = unidade.nome
    novo_nome = request.form.get("nome")

    if novo_nome:
        try:
            unidade.nome = novo_nome
            db.session.commit()
            register_security_log(
                "Gestão de Unidade", f"Renomeada unidade: {nome_antigo} -> {novo_nome}"
            )
            flash(f"Unidade atualizada para '{novo_nome}'!", "success")
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao editar unidade.")
            flash("Erro ao atualizar unidade.", "danger")

    return redirect(url_for("auth.admin_unidades"))


@bp.route("/admin/unidades/alternar/<int:id>", methods=["POST"])
@login_required
def alternar_unidade_status(id):
    """Ativa ou Inativa uma unidade (Exclusão Lógica)."""
    if current_user.role != UserRole.ADMIN:
        abort(403)

    unidade = db.get_or_404(Unidade, id)
    unidade.ativo = not unidade.ativo

    try:
        db.session.commit()
        status = "ativada" if unidade.ativo else "inativada"
        register_security_log(
            "Gestão de Unidade", f"Unidade {unidade.nome} foi {status}."
        )
        flash(f"Unidade {unidade.nome} {status} com sucesso!", "info")
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao alternar status da unidade.")
        flash("Erro ao alterar status da unidade.", "danger")

    return redirect(url_for("auth.admin_unidades"))


# ====================== ROTAS AUDITORIA DE USO ======================

from unidecode import unidecode

#: Prefixos (em minúsculo) que definem cada categoria de ação de auditoria.
#: Fonte ÚNICA do `categoria_acao` e do filtro por categoria de `ver_logs`: as
#: duas leituras têm de concordar, senão a tela põe em "Outras" uma linha que
#: ela mesma pinta com o selo de Exclusão (foi assim com 'Exclusão de Turma',
#: gravada por `registros/turmas.py`, que ficava fora de `exclusao`).
_CATEGORIAS_ACAO = {
    "login": (
        "login",
        "logoff",
        "logout",
        "cadastro local",
        "reset de senha",
        "desbloqueio de login",
        "acesso aprovado",
        "aviso de invas",
    ),
    "criacao": ("criar",),
    "edicao": ("alterar", "alteração", "editar", "trocar", "troca"),
    "exclusao": ("excluir", "exclusao", "exclusão", "remover", "remoção"),
}

#: Ação que não casa com nenhum prefixo acima (e nenhuma ação vazia).
_CATEGORIA_OUTRAS = "outras"


def categoria_acao(acao: str | None) -> str:
    """Classifica uma ação de auditoria em uma categoria estável.

    Categorias: 'login', 'criacao', 'edicao', 'exclusao', 'outras'.
    """
    texto = (acao or "").strip().lower()
    if not texto:
        return _CATEGORIA_OUTRAS
    for categoria, prefixos in _CATEGORIAS_ACAO.items():
        if texto.startswith(prefixos):
            return categoria
    return _CATEGORIA_OUTRAS


@bp.route("/admin/logs")
@login_required
def ver_logs():
    if current_user.role != UserRole.ADMIN:
        abort(403)

    page = request.args.get("page", 1, type=int)
    usuario_busca = request.args.get("usuario", "").strip()
    acao_busca = request.args.get("acao", "").strip()
    data_busca = request.args.get("data", "").strip()

    query = LogAcao.query

    if usuario_busca:
        query = query.filter(LogAcao.usuario_nome.ilike(f"%{usuario_busca}%"))

    if data_busca:
        try:
            data_inicio = datetime.strptime(data_busca, "%Y-%m-%d").date()
            data_fim = data_inicio + timedelta(days=1)
            query = query.filter(
                LogAcao.data_hora >= data_inicio, LogAcao.data_hora < data_fim
            )
        except ValueError:
            pass

    # Filtro por categoria de ação (no banco, com parâmetro; nunca f-string SQL).
    # Os prefixos vêm de `_CATEGORIAS_ACAO` — o mesmo dicionário que
    # `categoria_acao` usa, para a listagem e a classificação não divergirem.
    categoria = acao_busca.lower() if acao_busca else ""
    if categoria not in set(_CATEGORIAS_ACAO) | {_CATEGORIA_OUTRAS}:
        categoria = ""

    if categoria and categoria != _CATEGORIA_OUTRAS:
        from sqlalchemy import or_ as _or

        condicoes = [LogAcao.acao.ilike(f"{p}%") for p in _CATEGORIAS_ACAO[categoria]]
        query = query.filter(_or(*condicoes))
    elif categoria == _CATEGORIA_OUTRAS:
        from sqlalchemy import or_ as _or

        condicoes = [
            LogAcao.acao.ilike(f"{p}%")
            for prefixos in _CATEGORIAS_ACAO.values()
            for p in prefixos
        ]
        query = query.filter(~_or(*condicoes))

    # Paginação
    pagination = query.order_by(LogAcao.data_hora.desc()).paginate(
        page=page, per_page=20, error_out=False
    )

    return render_template(
        "admin/logs.html",
        logs=pagination.items,
        pagination=pagination,
        manutencao_ativa=is_maintenance_enabled(),
        usuario_selecionado=usuario_busca,
        acao_selecionada=categoria,
        data_selecionada=data_busca,
    )


@bp.route("/admin/manutencao/toggle", methods=["POST"])
@login_required
def manutencao_toggle():
    if current_user.role != UserRole.ADMIN:
        abort(403)

    manutencao_ativa = not is_maintenance_enabled()
    configuracao = ConfiguracaoSistema.query.filter_by(
        chave=MANUTENCAO_CONFIG_KEY,
        unidade_id=None,
    ).first()
    if configuracao is None:
        configuracao = ConfiguracaoSistema(
            chave=MANUTENCAO_CONFIG_KEY,
            descricao="Indica se o sistema está em modo de manutenção",
        )
        db.session.add(configuracao)

    configuracao.valor = "true" if manutencao_ativa else "false"
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao alternar o modo de manutenção.")
        flash("Não foi possível alterar o modo de manutenção.", "danger")
    else:
        status = "ativado" if manutencao_ativa else "desativado"
        current_app.logger.info(
            "Modo de manutenção %s por %s.", status, current_user.id
        )
        flash(f"Modo de manutenção {status} com sucesso.", "success")

    return redirect(url_for("auth.ver_logs"))


def _executar_limpar_logs(automatico=False):
    """Remove logs com mais de 30 dias. Retorna número de registros removidos ou -1 em erro."""
    try:
        data_limite = datetime.now() - timedelta(days=30)

        # Controle para execução automática (evita rodar várias vezes no mesmo dia)
        if automatico:
            ultima_limpeza = ConfiguracaoSistema.query.filter_by(
                chave="ultima_limpeza_logs"
            ).first()
            hoje = datetime.now().date()
            if ultima_limpeza and ultima_limpeza.valor == str(hoje):
                return 0
            if not ultima_limpeza:
                ultima_limpeza = ConfiguracaoSistema(
                    chave="ultima_limpeza_logs",
                    valor=str(hoje),
                    descricao="Data da última execução automática de limpeza de logs",
                )
                db.session.add(ultima_limpeza)
            else:
                ultima_limpeza.valor = str(hoje)
            db.session.commit()

        # Executa a exclusão
        qtd = LogAcao.query.filter(LogAcao.data_hora < data_limite).count()
        if qtd:
            LogAcao.query.filter(LogAcao.data_hora < data_limite).delete(
                synchronize_session=False
            )
            db.session.commit()
        return qtd
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao limpar logs antigos")
        return -1


@bp.route("/admin/logs/limpar-antigos", methods=["POST"])
@login_required
def limpar_logs_antigos():
    """Remove logs com mais de 30 dias para evitar inchaço do SQLite DB local."""
    if current_user.role != UserRole.ADMIN:
        abort(403)

    qtd = _executar_limpar_logs(automatico=False)

    if qtd >= 0:
        flash(f"Limpeza de Logs: {qtd} logs removidos!", "success")
    else:
        flash(f"Falha técnica ao tentar limpar logs antigos.", "danger")

    return redirect(url_for("auth.ver_logs"))


@bp.route("/auth/google/confirmar-vinculo", methods=["GET", "POST"])
def google_confirmar_vinculo():
    """Confirma com senha local o vínculo de uma conta Google existente."""
    pending = session.get("google_link_pending")
    now = int(datetime.now().timestamp())
    created_at = pending.get("created_at") if isinstance(pending, dict) else None
    if (
        not isinstance(pending, dict)
        or not isinstance(created_at, int)
        or now - created_at > 600
        or created_at > now
    ):
        session.pop("google_link_pending", None)
        flash(
            "A confirmação do vínculo expirou. Inicie novamente o login Google.",
            "warning",
        )
        return redirect(url_for("auth.login"))

    user = db.session.get(User, pending.get("user_id"))
    if not user or not user.is_active or user.google_id:
        session.pop("google_link_pending", None)
        flash("Não foi possível confirmar o vínculo desta conta.", "danger")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        action = request.form.get("acao")
        if action == "recusar":
            session.pop("google_link_pending", None)
            flash(
                "Vínculo cancelado. Você pode entrar com suas credenciais normais.",
                "info",
            )
            return redirect(url_for("auth.login"))
        if action != "confirmar":
            abort(400)

        password = request.form.get("senha_atual", "")
        if user.password and (not password or not user.check_password(password)):
            flash("Senha local incorreta. O vínculo não foi realizado.", "danger")
            return redirect(url_for("auth.google_confirmar_vinculo"))

        user.google_id = pending["google_id"]
        user.google_email = pending["google_email"]
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao confirmar vínculo Google.")
            flash("Não foi possível vincular a conta agora. Tente novamente.", "danger")
            return redirect(url_for("auth.login"))

        session.pop("google_link_pending", None)
        iniciar_sessao(user)
        if user.unidade_id:
            session["unidade_id"] = user.unidade_id
        else:
            session.pop("unidade_id", None)
        register_security_log(
            "Vínculo Google", f"Vínculo Google confirmado por {user.name}."
        )
        return redirect(url_for("main.painel"))

    return render_template(
        "auth/confirmar_vinculo_google.html",
        google_email=pending["google_email"],
        google_name=pending["google_name"],
        user=user,
    )


# ====================== ROTAS DO PERFIL PESSOAL ======================


@bp.route("/trocar-senha", methods=["GET", "POST"])
@login_required
def trocar_senha():
    if current_user.is_ad_user:
        flash(
            "Usuários federados pelo LDAP não precisam alterar uma senha local no banco.",
            "info",
        )
        return redirect(url_for("main.painel"))

    if request.method == "POST":
        nova = request.form.get("nova_senha", "")
        confirma = request.form.get("confirma_senha", "")
        senha_atual = request.form.get("senha_atual", "")

        if not current_user.first_login and not current_user.is_ad_user:
            if not senha_atual or not current_user.check_password(senha_atual):
                flash(
                    "Senha atual incorreta. Digite a senha vigente para continuar.",
                    "danger",
                )
                return redirect(url_for("auth.trocar_senha"))

        # ── Validação de complexidade ──────────────────────────────────────
        erros = validate_password_strength(nova)
        if erros:
            for e in erros:
                flash(e, "danger")
            return redirect(url_for("auth.trocar_senha"))

        if nova != confirma:
            flash("As senhas não coincidem.", "danger")
            return redirect(url_for("auth.trocar_senha"))

        # Impede reutilizar a própria senha atual
        if current_user.check_password(nova):
            flash("A nova senha não pode ser igual à senha atual.", "danger")
            return redirect(url_for("auth.trocar_senha"))

        try:
            usuario = current_user._get_current_object()
            nome = usuario.name
            usuario.set_password(nova)
            usuario.first_login = False  # libera acesso normal após troca
            db.session.commit()
            # S1-06: as outras sessões do mesmo usuário caem (o cookie antigo
            # carrega o `sv` velho); esta continua, com o carimbo renovado.
            session["sv"] = revogar_sessoes(
                usuario.id, "troca_senha", registrar_log=False
            )
            register_security_log("Troca de Senha", f"{nome} definiu nova senha.")
            flash("Senha atualizada com sucesso!", "success")
            return redirect(url_for("main.painel"))
        except Exception:
            db.session.rollback()
            current_app.logger.exception("Falha ao trocar senha do usuário atual.")
            flash("Erro ao salvar a nova senha. Tente novamente.", "warning")

    return render_template("trocar_senha.html", first_login=current_user.first_login)

# puataon/app/__init__.py

from flask import (
    Flask,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, logout_user
from flask_migrate import Migrate
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config, validar_configuracao
from app.extensions import csrf, db, login_manager, mail
from app.models import auditoria_listener  # noqa: F401
import logging
from logging.handlers import RotatingFileHandler
import os


def create_app(config_class: type[Config] = Config) -> Flask:
    """Cria a aplicação Flask sem efeitos colaterais no import."""
    app = Flask(__name__)
    app.config.from_object(config_class)
    # S1-01/S1-02: sem SECRET_KEY utilizável (ou com DEBUG em produção) a
    # aplicação não sobe — a checagem fica aqui para que classes de teste possam
    # definir a própria chave sem afrouxar a regra.
    validar_configuracao(app.config)
    # S1-15: o ProxyFix só entra quando existe proxy reverso confiável na frente
    # (TRUSTED_PROXY=true). Ligado sem proxy, qualquer cliente forja
    # X-Forwarded-Proto/X-Forwarded-For e o app passa a acreditar em HTTPS,
    # IP de origem e host que não aconteceram.
    if app.config.get("TRUSTED_PROXY"):
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Configura log em arquivo para captura de erros em produção/WSGI
    try:
        instance_path = os.path.join(app.root_path, "..", "instance")
        os.makedirs(instance_path, exist_ok=True)
        log_file = os.path.join(instance_path, "error.log")
        file_handler = RotatingFileHandler(
            log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
        )
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s in %(module)s: %(message)s"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.WARNING)
        if not app.logger.handlers:
            app.logger.addHandler(file_handler)
        else:
            # Avoid duplicate handlers when reloading in debug
            has_file = any(
                isinstance(h, RotatingFileHandler) for h in app.logger.handlers
            )
            if not has_file:
                app.logger.addHandler(file_handler)
    except Exception:
        # Falha ao configurar log em arquivo não deve interromper a inicialização
        pass
    _configure_extensions(app)
    _register_user_loader()
    _register_security_hooks(app)
    _register_blueprints(app)
    _register_template_filters(app)
    _register_context_processors(app)
    _register_cli(app)
    _register_error_handlers(app)

    return app


def _configure_extensions(app: Flask) -> None:
    db.init_app(app)
    # O efeito colateral importa: registrar a extensão Flask-Migrate no app.
    Migrate(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)


def _register_template_filters(app: Flask) -> None:
    import re
    from app.utils.formatters import formatar_ch

    app.jinja_env.filters["formatar_ch"] = formatar_ch

    @app.template_filter("format_cpf")
    def format_cpf_filter(cpf) -> str:
        """Formata CPF armazenado como dígitos puros para xxx.xxx.xxx-xx.
        Retorna string vazia se None/vazio, dígitos brutos se != 11 dígitos.
        """
        digitos = re.sub(r"\D", "", cpf or "")
        if not digitos:
            return ""
        if len(digitos) == 11:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
        return digitos  # anômalo: mostra como está, sem quebrar


def _register_security_hooks(app: Flask) -> None:
    from app.models.enums import UserRole
    from app.services.maintenance import is_maintenance_enabled
    from app.services.sessao import MENSAGENS, motivo_pendente

    @app.before_request
    def enforce_user_access_state():
        if request.endpoint in {None, "static"}:
            return None
        if request.endpoint.startswith("static"):
            return None

        # S1-06: força o `user_loader` (o Flask-Login cacheia em `g`) antes de
        # qualquer decisão. Se `sv`/`iat` não conferem — sessão de outra
        # geração, sem carimbo ou acima do limite absoluto — o pedido morre
        # aqui: o cookie antigo deixa de autenticar e o usuário volta ao login
        # com a explicação. A comparação usa a linha que o loader já carregou,
        # então não há SELECT extra por requisição.
        #
        # O `g.pop` descarta o usuário que o Flask-Login guardou no AppContext:
        # em produção cada request tem o seu, mas o `test_client` reaproveita o
        # AppContext do fixture — sem isto a revogação passaria despercebida
        # justamente nos testes. Em request real o `g` já nasce vazio.
        g.pop("_login_user", None)
        current_user.is_authenticated  # noqa: B018 — dispara o carregamento
        motivo = motivo_pendente()
        if motivo:
            logout_user()
            session.clear()
            flash(MENSAGENS.get(motivo, MENSAGENS["versao"]), "warning")
            return redirect(url_for("auth.login"))

        if is_maintenance_enabled():
            if current_user.is_authenticated and current_user.role == UserRole.ADMIN:
                return None
            if request.endpoint not in {"auth.login", "auth.logout"}:
                return render_template("erros/sistema_indisponivel.html"), 503

        if not current_user.is_authenticated:
            return None

        if current_user.role == UserRole.PENDENTE and request.endpoint not in {
            "auth.aguardando_aprovacao",
            "auth.logout",
            "auth.login",
        }:
            return redirect(url_for("auth.aguardando_aprovacao"))

        if (
            current_user.first_login
            and not current_user.is_ad_user
            and request.endpoint
            not in {"auth.trocar_senha", "auth.logout", "auth.login"}
        ):
            return redirect(url_for("auth.trocar_senha"))

        return None

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        # S1-09: HSTS só em resposta HTTPS de verdade (com terminador TLS na
        # frente o header não adianta: o navegador só o aceita em HTTPS). Sem
        # includeSubDomains e sem preload de propósito — os subdomínios da
        # instituição não são geridos por este sistema.
        max_age = app.config.get("HSTS_MAX_AGE", 15552000)
        if request.is_secure and max_age:
            response.headers.setdefault(
                "Strict-Transport-Security", f"max-age={int(max_age)}"
            )
        return response

    @app.after_request
    def set_cache_headers(response):
        """S1-10: página autenticada não fica no cache do navegador/proxy.

        `private` impede cache compartilhado; `no-store` impede o histórico em
        disco do navegador (botão Voltar após o logout). `setdefault` respeita
        rotas que já definiram o próprio `Cache-Control` e não toca em
        `/static/`, cujo cache é justamente o desejado.
        """
        if request.endpoint == "static" or request.path.startswith("/static/"):
            return response

        # `current_user.is_authenticated` do Flask-Login lê `is_active`, que é
        # coluna: num objeto expirado por commit isso dispara um SELECT extra
        # em toda resposta. O `_user_id` da sessão responde sem consulta.
        if session.get("_user_id"):
            # `send_file`/`send_from_directory` já põem `no-cache` nos
            # downloads; trocamos por `no-store` (dado de aluno não fica em
            # disco) sem sobrescrever rotas que já pediram `no-store`.
            if "no-store" not in response.headers.get("Cache-Control", ""):
                response.headers["Cache-Control"] = "no-store, private"
            response.headers.setdefault("Pragma", "no-cache")
            response.headers.setdefault("Expires", "0")
        elif response.status_code >= 400 or request.endpoint in {
            "auth.login",
            "main.home",
        }:
            # Login e páginas de erro: não guardar, mas sem `no-store` — não há
            # conteúdo de usuário e o `no-store` atrapalha fluxos (Voltar).
            response.headers.setdefault("Cache-Control", "no-cache")
        return response

    @app.after_request
    def set_csp_report_only(response):
        """S1-14: CSP em Report-Only (não bloqueia nada ainda).

        Sem endpoint de coleta: as violações aparecem no console do navegador.
        ``/static`` fica fora (o header só faz sentido em documento). Quando o
        endurecimento terminar (sem inline e com nonce), a política vira
        ``Content-Security-Policy`` de verdade.
        """
        politica = app.config.get("CSP_REPORT_ONLY_POLICY")
        if not app.config.get("CSP_REPORT_ONLY") or not politica:
            return response
        if request.endpoint == "static" or request.path.startswith("/static/"):
            return response
        response.headers.setdefault("Content-Security-Policy-Report-Only", politica)
        return response


def _register_user_loader() -> None:
    from app.models import User
    from app.services.sessao import motivo_recusa, recusar_sessao

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            usuario = db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None
        if usuario is None:
            return None
        # S1-06: `sv` (versão da sessão) e `iat` (limite absoluto) são checados
        # aqui, depois de carregar o usuário — a linha veio na mesma consulta
        # que o loader já fazia. Recusa = None + marca em `g` para o
        # `before_request` explicar e redirecionar.
        motivo = motivo_recusa(usuario)
        if motivo:
            recusar_sessao(motivo)
            return None
        return usuario


def _register_blueprints(app: Flask) -> None:
    from app.auth import bp as auth_bp
    from app.conselho import bp as conselho_bp
    from app.informacao_padrao import bp as informacao_padrao_bp
    from app.main import bp as main_bp
    from app.registros import bp as registros_bp
    from app.registros.servico_social import bp as servico_social_bp
    from app.relatorios import bp_relatorios
    from app.planejamento import bp_planejamento

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(conselho_bp)
    app.register_blueprint(informacao_padrao_bp)
    app.register_blueprint(servico_social_bp)
    app.register_blueprint(bp_relatorios)
    app.register_blueprint(bp_planejamento)


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_app_globals() -> dict[str, object]:
        from datetime import datetime
        from app.version import APP_VERSION, APP_STAGE

        return {
            "app_version": APP_VERSION,
            "app_stage": APP_STAGE,
            "ano_atual": datetime.now().year,
        }

    @app.context_processor
    def inject_unidade_context() -> dict[str, object]:
        from flask import session
        from flask_login import current_user

        from app.models import Unidade
        from app.services.informacao_padrao import get_informacao_padrao_context
        from app.utils.logica import get_unidade_id

        try:
            informacao_padrao = get_informacao_padrao_context()
        except Exception:
            app.logger.exception("Falha ao montar informacao_padrao para templates.")
            informacao_padrao = {
                "nome_instituicao": "pautaON",
                "cnpj": "",
                "endereco": "",
                "telefones": "",
                "logo_principal_url": "/static/img/logo_textual_fundoPreto.png",
                "logo_secundaria_url": "/static/img/logo.png",
                "favicon_url": "/static/img/logo_resumida.png",
                "foto_default_aluno_url": "/static/img/default.png",
            }

        allowed_roles = {"admin", "pedagogico", "gerencia", "secretaria"}
        if not current_user.is_authenticated or current_user.role not in allowed_roles:
            return {
                "unidades_lista": [],
                "unidade_contexto": "",
                "informacao_padrao": informacao_padrao,
            }

        try:
            unidade_id = get_unidade_id()
            unidades_query = Unidade.query.filter_by(ativo=True)
            if (
                current_user.role not in {"admin", "gerencia"}
                and current_user.unidade_id
            ):
                unidades_query = unidades_query.filter_by(id=current_user.unidade_id)
            unidades = unidades_query.order_by(Unidade.nome).all()
            unidade_contexto = "Visão Global"

            if unidade_id:
                unidade = next(
                    (item for item in unidades if item.id == unidade_id), None
                )
                if unidade:
                    unidade_contexto = unidade.nome

            return {
                "unidades_lista": unidades,
                "unidade_contexto": unidade_contexto,
                "informacao_padrao": informacao_padrao,
            }
        except Exception:
            app.logger.exception("Falha ao montar contexto de unidade.")
            return {
                "unidades_lista": [],
                "unidade_contexto": "Erro Contexto",
                "informacao_padrao": informacao_padrao,
            }


def _register_cli(app: Flask) -> None:
    from app.services.bootstrap import register_bootstrap_commands

    register_bootstrap_commands(app)


def _register_error_handlers(app: Flask) -> None:
    from sqlalchemy.exc import SQLAlchemyError
    from flask import render_template, request
    from werkzeug.exceptions import HTTPException

    # ==========================================
    # ERROS ESPECÍFICOS DE NAVEGAÇÃO / PERMISSÃO
    # ==========================================

    @app.errorhandler(403)
    def handle_403_error(e):
        app.logger.warning(f"Acesso Negado (403) para: {request.path}")
        return render_template("erros/403.html"), 403

    @app.errorhandler(404)
    def handle_404_error(e):
        app.logger.warning(f"Página não encontrada (404): {request.path}")
        # Caso ainda não tenha um 404.html, você pode retornar temporariamente o sistema_indisponivel
        # return render_template("erros/sistema_indisponivel.html"), 404
        return render_template("erros/404.html"), 404

    @app.errorhandler(413)
    def handle_413_error(e):
        """AJ5-B: corpo acima de MAX_CONTENT_LENGTH — flash amigável de volta
        ao form, sem stack trace.

        O POST se perde (o corpo foi cortado antes do parsing e não há como
        recuperá-lo), então o operador é devolvido à página de origem. O
        referrer só é usado quando é do mesmo host — um referrer de fora
        viraria open redirect; sem ele, cai na raiz.
        """
        from urllib.parse import urlparse

        app.logger.warning(f"Upload rejeitado por tamanho (413): {request.path}")
        limite = (app.config.get("MAX_CONTENT_LENGTH") or 0) // (1024 * 1024)
        flash(
            f"Envio recusado: os arquivos ultrapassam o limite de {limite} MB "
            "por formulário. Reduza o tamanho e tente novamente.",
            "error",
        )
        ref = request.referrer
        if ref and urlparse(ref).netloc not in ("", request.host):
            ref = None
        return redirect(ref or "/")

    # ==========================================
    # FALHAS DE SISTEMA / ERROS GERAIS
    # ==========================================

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        app.logger.error(f"Erro de banco de dados interceptado: {e}")
        if app.debug:
            raise e
        return render_template("erros/sistema_indisponivel.html"), 503

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Renderiza `sistema_indisponivel.html` para os DEMAIS erros HTTP (ex: 400, 405).
        
        Mantemos o código de status original para que caches/proxies e clientes
        recebam o código apropriado, mas sempre mostramos a mesma página ao usuário.
        """
        app.logger.warning(f"HTTP Exception genérica interceptada: {e.code} {e.description}")
        if app.debug:
            return e
        return render_template("erros/sistema_indisponivel.html"), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        """Captura exceções não previstas e mostra a página de indisponibilidade.
        
        Registra a stack trace no logger para investigação posterior.
        """
        app.logger.exception("Unhandled exception: %s", e)
        if app.debug:
            raise e
        return render_template("erros/sistema_indisponivel.html"), 500
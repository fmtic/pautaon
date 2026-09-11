# puataon/app/__init__.py

from flask import Flask
from flask_migrate import Migrate
from config import Config
from app.extensions import csrf, db, login_manager
import logging
from logging.handlers import RotatingFileHandler
import os


def create_app(config_class: type[Config] = Config) -> Flask:
    """Cria a aplicação Flask sem efeitos colaterais no import."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Configura log em arquivo para captura de erros em produção/WSGI
    try:
        instance_path = os.path.join(app.root_path, '..', 'instance')
        os.makedirs(instance_path, exist_ok=True)
        log_file = os.path.join(instance_path, 'error.log')
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
        formatter = logging.Formatter('%(asctime)s %(levelname)s in %(module)s: %(message)s')
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.WARNING)
        if not app.logger.handlers:
            app.logger.addHandler(file_handler)
        else:
            # Avoid duplicate handlers when reloading in debug
            has_file = any(isinstance(h, RotatingFileHandler) for h in app.logger.handlers)
            if not has_file:
                app.logger.addHandler(file_handler)
    except Exception:
        # Falha ao configurar log em arquivo não deve interromper a inicialização
        pass
    _configure_extensions(app)
    _register_user_loader()
    _register_blueprints(app)
    _register_template_filters(app)
    _register_context_processors(app)
    _register_cli(app)
    _register_error_handlers(app)

    return app


def _configure_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate = Migrate(app, db)
    csrf.init_app(app)
    login_manager.init_app(app)


def _register_template_filters(app: Flask) -> None:
    import re

    @app.template_filter('format_cpf')
    def format_cpf_filter(cpf) -> str:
        """Formata CPF armazenado como dígitos puros para xxx.xxx.xxx-xx.
        Retorna string vazia se None/vazio, dígitos brutos se != 11 dígitos.
        """
        digitos = re.sub(r'\D', '', cpf or '')
        if not digitos:
            return ''
        if len(digitos) == 11:
            return f"{digitos[:3]}.{digitos[3:6]}.{digitos[6:9]}-{digitos[9:]}"
        return digitos  # anômalo: mostra como está, sem quebrar


def _register_user_loader() -> None:
    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str) -> User | None:
        try:
            return db.session.get(User, int(user_id))
        except (TypeError, ValueError):
            return None


def _register_blueprints(app: Flask) -> None:
    from app.routes import auth, conselho, informacao_padrao, main
    from app.routes.registros import bp as registros_bp
    from app.routes.registros.servico_social import bp as servico_social_bp

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(conselho.bp)
    app.register_blueprint(informacao_padrao.bp)
    app.register_blueprint(servico_social_bp)


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_unidade_context() -> dict[str, object]:
        from flask import session
        from flask_login import current_user

        from app.models import Unidade
        from app.informacao_padrao import get_informacao_padrao_context
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
            if current_user.role not in {"admin", "gerencia"} and current_user.unidade_id:
                unidades_query = unidades_query.filter_by(id=current_user.unidade_id)
            unidades = unidades_query.order_by(Unidade.nome).all()
            unidade_contexto = "Visão Global"

            if unidade_id:
                unidade = next((item for item in unidades if item.id == unidade_id), None)
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
    from sqlalchemy.exc import OperationalError
    from flask import render_template
    from werkzeug.exceptions import HTTPException

    @app.errorhandler(OperationalError)
    def handle_db_down_error(e):
        app.logger.error(f"Erro de conexão com o banco de dados interceptado: {e}")
        return render_template('sistema_indisponivel.html'), 503

    @app.errorhandler(HTTPException)
    def handle_http_exception(e):
        """Renderiza `sistema_indisponivel.html` para erros HTTP (4xx/5xx).

        Mantemos o código de status original para que caches/proxies e clientes
        recebam o código apropriado, mas sempre mostramos a mesma página ao usuário.
        """
        app.logger.warning(f"HTTP Exception interceptada: {e.code} {e.description}")
        return render_template('sistema_indisponivel.html'), e.code

    @app.errorhandler(Exception)
    def handle_unexpected_exception(e):
        """Captura exceções não previstas e mostra a página de indisponibilidade.

        Registra a stack trace no logger para investigação posterior.
        """
        app.logger.exception("Unhandled exception: %s", e)
        return render_template('sistema_indisponivel.html'), 500

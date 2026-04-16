from flask import Flask

from config import Config
from app.extensions import csrf, db, login_manager


def create_app(config_class: type[Config] = Config) -> Flask:
    """Cria a aplicação Flask sem efeitos colaterais no import."""
    app = Flask(__name__)
    app.config.from_object(config_class)

    _configure_extensions(app)
    _register_user_loader()
    _register_blueprints(app)
    _register_context_processors(app)
    _register_cli(app)

    return app


def _configure_extensions(app: Flask) -> None:
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)


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

    app.register_blueprint(auth.bp)
    app.register_blueprint(main.bp)
    app.register_blueprint(registros_bp)
    app.register_blueprint(conselho.bp)
    app.register_blueprint(informacao_padrao.bp)


def _register_context_processors(app: Flask) -> None:
    @app.context_processor
    def inject_unidade_context() -> dict[str, object]:
        from flask import session
        from flask_login import current_user

        from app.models import Unidade
        from app.informacao_padrao import get_informacao_padrao_context

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
            unidades = Unidade.query.filter_by(ativo=True).order_by(Unidade.nome).all()
            unidade_id = session.get("unidade_id")
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

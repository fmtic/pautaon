"""
================================================================================
ORGANIZACAO.PY - Estrutura organizacional (multitenancy)
================================================================================

Contém:
    - Unidade             : tenant do sistema
    - ConfiguracaoSistema : parâmetros chave/valor, global ou por unidade

Toda entidade de negócio aponta para uma Unidade. É a fronteira de isolamento
de dados do sistema.
================================================================================
"""

from app.models.base import db


class Unidade(db.Model):
    """
    Unidade operacional do sistema (tenant).

    Toda entidade de negócio (usuários, turmas, alunos, períodos, etc.) aponta
    para uma `Unidade`. Isso permite que uma mesma instalação atenda várias
    unidades com dados isolados.

    Regras:
        - Unidade inativa não deve aparecer em seletores de cadastro.
        - Excluir uma Unidade em uso é proibido por integridade referencial.
    """

    __tablename__ = "unidade"

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)


class ConfiguracaoSistema(db.Model):
    """
    Parâmetros chave/valor do sistema, opcionalmente por unidade.

    Usada para toggles e parâmetros que variam por instalação ou por unidade.
    Ex.: 'permitir_auto_cadastro', 'nota_minima_aprovacao'.

    Regras:
        - `unidade_id = NULL` significa parâmetro GLOBAL.
        - A chave deve ser única dentro do escopo:
            * global: (chave) WHERE unidade_id IS NULL
            * por unidade: (chave, unidade_id) WHERE unidade_id IS NOT NULL

    Nota sobre UNIQUE com NULL:
        Em SQL padrão, dois NULLs são considerados distintos em UNIQUE
        compostos. Por isso usamos DOIS índices parciais (Postgres):
            ix_config_chave_global  -> (chave) WHERE unidade_id IS NULL
            ix_config_chave_unidade -> (chave, unidade_id) WHERE unidade_id IS NOT NULL
        Assim, é impossível ter duas configurações globais com a mesma chave.
    """

    __tablename__ = "configuracao_sistema"
    __table_args__ = (
        db.Index(
            "ix_config_chave_global",
            "chave",
            unique=True,
            postgresql_where=db.text("unidade_id IS NULL"),
        ),
        db.Index(
            "ix_config_chave_unidade",
            "chave",
            "unidade_id",
            unique=True,
            postgresql_where=db.text("unidade_id IS NOT NULL"),
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    chave: str = db.Column(db.String(50), nullable=False)  # UNIQUE via índices parciais
    valor: str = db.Column(db.String(100))
    descricao: str = db.Column(db.String(255))

    unidade_id: int = db.Column(db.Integer, db.ForeignKey("unidade.id"), nullable=True)
    unidade = db.relationship("Unidade", backref="configuracoes")

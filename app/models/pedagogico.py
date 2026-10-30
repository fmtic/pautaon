"""
================================================================================
PEDAGOGICO.PY - Catalogos pedagogicos
================================================================================

Contem:
    - Curso : oferta de uma unidade; agrupa turmas e temas de aula.
    - CentroCusto : catalogo de centros de custo por unidade.
    - Nivel : nivel pedagogico (Basico, Intermediario, Avancado).
    - ValorEsportista : valor/postura observado no lancamento de frequencia.

Ambos sao catalogos reutilizaveis escopados por unidade.
"""

from app.models.base import db, datetime, get_local_now
from sqlalchemy import UniqueConstraint


class Curso(db.Model):
    """
    Curso ofertado por uma unidade.
    """
    __tablename__ = 'curso'

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    descricao = db.Column(db.String(300))
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)

    unidade = db.relationship('Unidade', backref='cursos')


class CentroCusto(db.Model):
    """Catalogo de centros de custo de uma unidade."""
    __tablename__ = 'centro_custo'
    __table_args__ = (
        UniqueConstraint('nome', 'unidade_id', name='uq_centro_custo_nome_unidade'),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    unidade = db.relationship('Unidade', backref='centros_custo')


class Nivel(db.Model):
    """Nivel pedagogico."""
    __tablename__ = 'nivel'
    __table_args__ = (UniqueConstraint('nome', 'unidade_id', name='uq_nivel_nome_unidade'),)

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'))


class ValorEsportista(db.Model):
    """Valor / postura do esportista (catálogo do planejamento pedagógico).

    É um dado ADICIONAL do lançamento de frequência: `Frequencia`
    `.valor_esportista_id` guarda o valor observado na aula e **nenhuma**
    conta de presença/falta o lê (ver `app/utils/logica.py`).

    Regras:
        - Escopo sempre por unidade (não existe valor global, ao contrário de
          `Nivel`): `unidade_id` NOT NULL e a criação exige unidade efetiva na
          sessão.
        - Nome único por unidade **sem diferenciar maiúsculas de minúsculas**:
          o índice funcional `uix_valor_esportista_nome_unidade`
          (`lower(nome)`, `unidade_id`) garante no banco e a rota valida com
          `func.lower` para devolver mensagem amigável antes do IntegrityError.
        - `ativo=False` esconde o valor do seletor de lançamento mas **não**
          apaga o histórico: o valor inativo já lançado continua exibido.
    """
    __tablename__ = 'valor_esportista'
    __table_args__ = (
        db.Index(
            'uix_valor_esportista_nome_unidade',
            db.text('lower(nome)'),
            'unidade_id',
            unique=True,
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id = db.Column(
        db.Integer, db.ForeignKey('unidade.id'), nullable=False,
    )
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    unidade = db.relationship('Unidade', backref='valores_esportista')

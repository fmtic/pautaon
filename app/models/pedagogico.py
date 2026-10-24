"""
================================================================================
PEDAGOGICO.PY - Catalogos pedagogicos
================================================================================

Contem:
    - Curso : oferta de uma unidade; agrupa turmas e temas de aula.
    - CentroCusto : catalogo de centros de custo por unidade.
    - Nivel : nivel pedagogico (Basico, Intermediario, Avancado).

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

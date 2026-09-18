"""
================================================================================
PEDAGOGICO.PY - Catálogos pedagógicos
================================================================================

Contém:
    - Curso : oferta de uma unidade; agrupa turmas e temas de aula.
    - Nivel : nível pedagógico (Básico, Intermediário, Avançado).

Ambos são catálogos reutilizáveis escopados por unidade.
================================================================================
"""

from app.models.base import db, datetime, get_local_now


class Curso(db.Model):
    """
    Curso ofertado por uma unidade.

    Um Curso é o "guarda-chuva" pedagógico: agrupa turmas e temas de aula.
    Cada unidade mantém seu próprio catálogo.

    Regras:
        - Curso inativo não deve ser associado a novas turmas.
        - `carga_horaria` é a carga total prevista (em horas), não a executada.
    """
    __tablename__ = 'curso'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(150), nullable=False)
    descricao: str = db.Column(db.String(300))
    carga_horaria: int = db.Column(db.Integer)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade = db.relationship('Unidade', backref='cursos')


class Nivel(db.Model):
    """
    Nível pedagógico (ex.: Básico, Intermediário, Avançado).

    Usado tanto em Turma.nivel quanto em Inscricao.nivel. Hoje não há FK
    obrigatória — o campo é string livre. A existência desta tabela permite
    uma futura migração para FK.

    Notas:
        - `unidade_id` é nullable para compatibilidade com dados legados.
        - `nome` é único globalmente (não escopado por unidade).
    """
    __tablename__ = 'nivel'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), unique=True, nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'))
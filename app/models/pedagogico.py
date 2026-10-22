"""
================================================================================
PEDAGOGICO.PY - Catálogos pedagógicos
================================================================================

Contém:
    - Curso : oferta de uma unidade; agrupa turmas e temas de aula.
    - Nivel : nível pedagógico (Básico, Intermediário, Avançado).

Ambos são catálogos reutilizáveis escopados por unidade.

NOTAS DE ONDAS
    - Onda 3C: `Curso.carga_horaria` removido. A C.H. é calculada diretamente
      em cada `Turma` via `carga_horaria_aula` (minutos/aula) e
      `carga_horaria_total` (minutos totais). Use `formatar_ch()` de
      `app.utils.formatters` para exibição legível.
================================================================================
"""

from app.models.base import db, datetime, get_local_now
from sqlalchemy import UniqueConstraint


class Curso(db.Model):
    """
    Curso ofertado por uma unidade.

    Um Curso é o "guarda-chuva" pedagógico: agrupa temas de aula.
    Cada unidade mantém seu próprio catálogo.

    Regras:
        - Curso inativo não deve ser associado a novas turmas.
        - A C.H. de aula e a C.H. Total são calculadas em cada Turma vinculada
          via `Turma.carga_horaria_aula` e `Turma.carga_horaria_total`.
    """
    __tablename__ = 'curso'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(150), nullable=False)
    descricao: str = db.Column(db.String(300))
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
        - `nome` é único dentro de cada unidade.
    """
    __tablename__ = 'nivel'
    __table_args__ = (UniqueConstraint('nome', 'unidade_id', name='uq_nivel_nome_unidade'),)

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'))

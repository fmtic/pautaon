"""
================================================================================
PEDAGOGICO.PY - Catalogos pedagogicos
================================================================================

Contem:
    - Curso : oferta de uma unidade; agrupa turmas e temas de aula.
    - CentroCusto : catalogo de centros de custo por unidade.
    - Nivel : nivel pedagogico (Basico, Intermediario, Avancado).
    - ValorEsportista : valor/postura trabalhado na aula (N:N com RegistroAula).

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
    # AJ22-B: programa do curso (lista central PROGRAMAS_CURSO). NULL =
    # curso sem programa — no fechamento do conselho só permite nível
    # "Não se aplica". NÃO é o mesmo campo de `turma_curso.programa`
    # (que segue intocado e sem vínculo com esta coluna).
    programa = db.Column(db.String(50))
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
    """Nivel pedagogico.

    AJ22: `programa` (texto, nullable) vincula o nível a um programa de
    curso ('Profissionalizante', 'Esporte', 'Meio Ambiente', 'Outros').
    Nível sem programa (NULL, legado) NUNCA aparece como opção de nível no
    fechamento do conselho. A unicidade passou de
    `uq_nivel_nome_unidade` (nome+unidade) para o índice funcional
    `uq_nivel_nome_unidade_programa` (nome, unidade_id,
    COALESCE(programa,'')) — o mesmo nome pode repetir entre programas;
    legados sem programa mantêm a unicidade anterior.
    """
    __tablename__ = 'nivel'
    __table_args__ = (
        db.Index(
            'uq_nivel_nome_unidade_programa',
            'nome',
            'unidade_id',
            db.text("COALESCE(programa, '')"),
            unique=True,
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    ativo = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id = db.Column(db.Integer, db.ForeignKey('unidade.id'))
    programa = db.Column(db.String(50))


class ValorEsportista(db.Model):
    """Valor / postura do esportista (catálogo do planejamento pedagógico).

    É um dado ADICIONAL da AULA: `RegistroAula.valores` guarda os valores
    trabalhados na aula (N:N, igual aos temas) e **nenhuma** conta de
    presença/falta o lê (ver `app/utils/logica.py`).

    Regras:
        - Escopo sempre por unidade (não existe valor global, ao contrário de
          `Nivel`): `unidade_id` NOT NULL e a criação exige unidade efetiva na
          sessão.
        - Nome único por unidade **sem diferenciar maiúsculas de minúsculas**:
          o índice funcional `uix_valor_esportista_nome_unidade`
          (`lower(nome)`, `unidade_id`) garante no banco e a rota valida com
          `func.lower` para devolver mensagem amigável antes do IntegrityError.
        - `ativo=False` esconde o valor do seletor de lançamento mas **não**
          apaga o histórico: o valor inativo já vinculado à aula continua
          exibido e contado.
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

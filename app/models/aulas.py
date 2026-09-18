"""
================================================================================
AULAS.PY - Frequência e diário de aula
================================================================================

Contém:
    - Frequencia   : pauta (presença/falta por aluno/dia/turma).
    - RegistroAula : diário do professor (o que foi dado no dia).

São a base operacional da rotina pedagógica.

NOTAS ONDA 2A
    `Frequencia.data` e `RegistroAula.data` eram VARCHAR(20) no formato
    'YYYY-MM-DD'. Foram convertidas para DATE nativo.

NOTAS ONDA 2B
    `Frequencia.conceito` agora é ENUM nativo do Postgres
    (`conceito_frequencia_enum`), restrito a A/B/C/D/F/J.
    A property híbrida `presente` foi ajustada para comparar com o enum.
================================================================================
"""

from app.models.base import db, datetime, date, hybrid_property, get_local_now
from app.models.enums import ConceitoFrequencia


class Frequencia(db.Model):
    """
    Registro unitário de presença/falta de um aluno em uma turma em um dia.

    Conceitos (`conceito`), definidos em `app.models.enums.ConceitoFrequencia`:
        A, B, C, D -> presença (com gradações qualitativas)
        F          -> falta
        J          -> falta justificada (não conta para frequência)

    A property `presente` é híbrida: pode ser usada em Python e em queries
    SQL (`.filter(Frequencia.presente.is_(True))`).

    Constraints:
        - UNIQUE (aluno_id, turma_id, data): evita duplicidade de lançamento
          para o mesmo aluno/turma/dia.

    Índices:
        - (turma_id, data): "pauta da turma X no período Y".
        - (aluno_id, data): "faltas do aluno X no período Y".
    """
    __tablename__ = 'frequencia'
    __table_args__ = (
        db.UniqueConstraint('aluno_id', 'turma_id', 'data',
                            name='uix_frequencia_aluno_turma_data'),
        db.Index('ix_frequencia_turma_data', 'turma_id', 'data'),
        db.Index('ix_frequencia_aluno_data', 'aluno_id', 'data'),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data: date = db.Column(db.Date, nullable=False)

    # Onda 2B: ENUM nativo. `create_constraint=False` porque o tipo ENUM
    # do Postgres já valida os valores — não precisa de CHECK redundante.
    conceito: ConceitoFrequencia = db.Column(
        db.Enum(
            ConceitoFrequencia,
            name='conceito_frequencia_enum',
            create_constraint=False,
            native_enum=True,
        ),
        nullable=True,
    )

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='frequencias')

    @hybrid_property
    def presente(self) -> bool:
        """True se o conceito indica presença (A/B/C/D)."""
        return self.conceito in (
            ConceitoFrequencia.A,
            ConceitoFrequencia.B,
            ConceitoFrequencia.C,
            ConceitoFrequencia.D,
        )

    @presente.expression
    def presente(cls):
        """Versão SQL da property `presente` (para uso em filtros)."""
        return cls.conceito.in_([
            ConceitoFrequencia.A,
            ConceitoFrequencia.B,
            ConceitoFrequencia.C,
            ConceitoFrequencia.D,
        ])


class RegistroAula(db.Model):
    """
    Diário de aula: o que o professor registrou em uma turma em um dia.

    Guarda o tema trabalhado (`tema_id`), observações livres, e o instrutor
    responsável. É a base para o acompanhamento pedagógico.

    Notas:
        - `data` é DATE nativo (Onda 2A).
        - `turma_rel` é o nome do relacionamento com Turma; o backref `diarios`
          está no lado da Turma.
    """
    __tablename__ = 'registro_aula'

    id: int = db.Column(db.Integer, primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data: date = db.Column(db.Date, nullable=False)
    tema_id: int = db.Column(db.Integer, db.ForeignKey('tema_aula.id'), nullable=True)
    observacoes: str = db.Column(db.Text)
    instrutor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='diarios_unidade')
    turma_rel = db.relationship('Turma', backref='diarios')
    tema = db.relationship('TemaAula', foreign_keys=[tema_id])
    instrutor = db.relationship('User', foreign_keys=[instrutor_id])
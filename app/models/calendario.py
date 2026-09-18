"""
================================================================================
CALENDARIO.PY - Calendário acadêmico
================================================================================

Contém:
    - DiaBloqueado      : dia sem aula para um período letivo inteiro.
    - DiaBloqueadoTurma : exceção por turma (a turma TEM aula mesmo no dia
                          bloqueado).

Regra geral: DiaBloqueado afeta todas as turmas do período, exceto as listadas
em DiaBloqueadoTurma.

NOTAS ONDA 2A
    `DiaBloqueadoTurma.data` era VARCHAR(10). Virou DATE nativo, alinhando
    com `DiaBloqueado.data` (que já era DATE).

NOTAS ONDA 2B
    `DiaBloqueado.tipo` agora é ENUM nativo do Postgres
    (`tipo_dia_bloqueado_enum`), restrito a FERIADO / ATIVIDADE_PEDAGOGICA /
    REUNIAO_PAIS / ATIVIDADE_INTERNA / MANUTENCAO.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now
from app.models.enums import TipoDiaBloqueado


class DiaBloqueado(db.Model):
    """
    Dia sem aula para um período letivo (feriado, recesso, atividade interna).

    Afeta TODAS as turmas do período letivo, EXCETO as listadas em
    `DiaBloqueadoTurma` (exceções por turma).

    Tipos válidos (`tipo`) — ver `app.models.enums.TipoDiaBloqueado`:
        FERIADO, ATIVIDADE_PEDAGOGICA, REUNIAO_PAIS,
        ATIVIDADE_INTERNA, MANUTENCAO
    """
    __tablename__ = 'dia_bloqueado'

    id: int = db.Column(db.Integer, primary_key=True)
    data: date = db.Column(db.Date, nullable=False)

    # Onda 2B: ENUM nativo do Postgres.
    tipo: TipoDiaBloqueado = db.Column(
        db.Enum(
            TipoDiaBloqueado,
            name='tipo_dia_bloqueado_enum',
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )
    descricao: str = db.Column(db.String(200))

    periodo_letivo_id: int = db.Column(
        db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=False
    )
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    criado_por_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    periodo_letivo = db.relationship('PeriodoLetivo', backref='dias_bloqueados')
    unidade = db.relationship('Unidade', backref='dias_bloqueados')
    criado_por = db.relationship(
        'User', backref='dias_bloqueados_criados', foreign_keys=[criado_por_id]
    )


class DiaBloqueadoTurma(db.Model):
    """
    Exceção: uma turma específica que TEM aula mesmo em um dia bloqueado
    do período letivo.

    Notas:
        - `data` é DATE nativo (Onda 2A).
        - Constraint UNIQUE (turma_id, data) evita duplicidade de exceção.
    """
    __tablename__ = 'dia_bloqueado_turma'
    __table_args__ = (
        db.UniqueConstraint('turma_id', 'data', name='uix_dia_bloqueado_turma'),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data: date = db.Column(db.Date, nullable=False)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    criado_por_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    turma = db.relationship(
        'Turma',
        backref=db.backref('dias_bloqueado_excecao', cascade='all, delete-orphan'),
    )
    unidade = db.relationship('Unidade', backref='dias_bloqueado_turma')
    criado_por = db.relationship(
        'User',
        backref='dias_bloqueado_turma_criados',
        foreign_keys=[criado_por_id],
    )
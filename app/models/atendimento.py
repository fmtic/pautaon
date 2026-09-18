"""
================================================================================
ATENDIMENTO.PY - Atendimento pedagógico individual
================================================================================

Contém:
    - Atendimento : registro de atendimento individual do aluno.

Os detalhes variam por tipo e ficam em `dados` (JSON). Os campos fixos servem
para listagens rápidas.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now, JSONType


class Atendimento(db.Model):
    """
    Atendimento individual do aluno (pedagógico).

    Os detalhes variam por tipo de atendimento e ficam em `dados` (JSON).
    Os campos fixos (`resumo`, `data_atendimento`, `atendido_por_nome`) são
    mantidos para listagens e relatórios rápidos.

    Nota sobre `setor`:
        Mantido apenas por compatibilidade com dados legados. O fluxo atual é
        exclusivamente pedagógico — NÃO use `setor` em novas features.
    """

    __tablename__ = "atendimento"

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    setor: str = db.Column(db.String(50), nullable=False, default="pedagogico")
    data_atendimento: date = db.Column(db.Date, nullable=False)
    resumo: str = db.Column(db.String(255))
    # JSONB no PostgreSQL (indexável via GIN quando necessário), JSON nos demais.
    dados: dict = db.Column(JSONType, nullable=False, default=dict)

    atendido_por_id: int = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=True
    )
    atendido_por_nome: str = db.Column(db.String(150), nullable=True)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey("unidade.id"), nullable=True)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(
        db.DateTime, default=get_local_now, onupdate=get_local_now
    )

    aluno = db.relationship("Aluno", backref="atendimentos")
    unidade = db.relationship("Unidade", backref="atendimentos")
    atendido_por = db.relationship(
        "User", backref="atendimentos_registrados", foreign_keys=[atendido_por_id]
    )

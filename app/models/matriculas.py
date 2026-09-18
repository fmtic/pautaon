"""
================================================================================
MATRICULAS.PY - Matrículas e movimentações
================================================================================

Contém:
    - Inscricao     : N:N entre Aluno e Turma, com histórico.
    - Transferencia : movimentação de aluno entre turmas.

A tabela `inscricoes` é referenciada como `secondary` em `Aluno.turmas`.
Mantê-la neste módulo é seguro porque o `secondary` usa o NOME DA TABELA,
não o nome da classe.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now


class Inscricao(db.Model):
    """
    Vínculo entre Aluno e Turma (N:N com histórico).

    Possui PK própria (`id`) para permitir MÚLTIPLAS inscrições do mesmo aluno
    na mesma turma, permitindo desativar e reativar sem perder histórico.

    Regras:
        - `ativo=True` indica o vínculo atual.
        - Ao desativar: preencher `data_desativacao` e `motivo_desativacao`.
        - `nivel` sobrescreve o nível geral do aluno para esta turma.
        - `data_inicio` é DATE (não DATETIME) e usa o fuso local da aplicação.
          Histórico: até 2026-09 usava `datetime.utcnow` (default incorreto).
    """

    __tablename__ = "inscricoes"

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    turma_id: int = db.Column(db.Integer, db.ForeignKey("turma.id"), nullable=False)

    nivel: str = db.Column(db.String(30))

    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)

    # Default Python-side: retorna date no fuso local da app.
    data_inicio: date = db.Column(
        db.Date,
        nullable=False,
        default=lambda: get_local_now().date(),
    )
    data_desativacao: datetime = db.Column(db.DateTime)
    motivo_desativacao: str = db.Column(db.String(50))

    aluno = db.relationship(
        "Aluno",
        backref=db.backref("inscricoes", cascade="all, delete-orphan"),
        overlaps="turmas,alunos",
    )
    turma = db.relationship(
        "Turma",
        backref=db.backref("inscricoes", cascade="all, delete-orphan"),
        overlaps="turmas,alunos",
    )


class Transferencia(db.Model):
    """
    Registro de transferência de um aluno entre turmas.

    Guarda a turma de origem e destino para fins de auditoria e relatório.
    Não movimenta automaticamente o vínculo — a alteração em `Inscricao`
    deve ser feita pela camada de serviço.

    Regras:
        - `turma_origem_id` != `turma_destino_id`.
        - Pertence a uma unidade (para filtragem multitenant).
    """

    __tablename__ = "transferencia"

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    turma_origem_id: int = db.Column(
        db.Integer, db.ForeignKey("turma.id"), nullable=False
    )
    turma_destino_id: int = db.Column(
        db.Integer, db.ForeignKey("turma.id"), nullable=False
    )
    data_transferencia: datetime = db.Column(
        db.DateTime, nullable=False, default=get_local_now
    )
    observacoes: str = db.Column(db.Text)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey("unidade.id"), nullable=False)

    aluno = db.relationship("Aluno", backref="transferencias")
    turma_origem = db.relationship("Turma", foreign_keys=[turma_origem_id])
    turma_destino = db.relationship("Turma", foreign_keys=[turma_destino_id])

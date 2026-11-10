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

NOTA ONDA 4 (múltiplos cursos por turma):
    `turma_curso_id` referencia obrigatoriamente a oferta concreta
    (TurmaCurso). Cada linha representa o vínculo do aluno com uma oferta;
    um aluno pode ter inscrições ativas em várias ofertas da mesma turma.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now, SoftDeleteMixin, TenantMixin
from app.models.auditoria_mixin import AuditoriaMixin


class Inscricao(SoftDeleteMixin, AuditoriaMixin, db.Model):
    """
    Vínculo entre Aluno e Turma (N:N com histórico).

    Possui PK própria (`id`) para permitir MÚLTIPLAS inscrições do mesmo aluno
    na mesma turma, uma por oferta, e preservar desativações no histórico.

    Regras:
        - `ativo=True` indica o vínculo atual com a oferta.
        - Só pode existir uma inscrição ativa por aluno e oferta.
        - Ao desativar: preencher `data_desativacao` e `motivo_desativacao`.
        - `nivel` sobrescreve o nível geral do aluno para esta turma.
        - `data_inicio` é DATE (não DATETIME) e usa o fuso local da aplicação.
          Histórico: até 2026-09 usava `datetime.utcnow` (default incorreto).
    """

    __tablename__ = "inscricoes"
    __table_args__ = (
        db.Index("ix_inscricoes_turma_curso_id", "turma_curso_id"),
        db.Index(
            "uix_inscricao_ativa_aluno_oferta",
            "aluno_id",
            "turma_curso_id",
            unique=True,
            postgresql_where=db.text("ativo IS TRUE"),
            sqlite_where=db.text("ativo = 1"),
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=False)
    turma_id: int = db.Column(db.Integer, db.ForeignKey("turma.id"), nullable=False)

    # Oferta concreta (TurmaCurso) em que o aluno está matriculado.
    turma_curso_id: int = db.Column(
        db.Integer, db.ForeignKey("turma_curso.id"), nullable=False
    )

    nivel: str = db.Column(db.String(30))

    # Default Python-side: retorna date no fuso local da app.
    data_inicio: date = db.Column(
        db.Date,
        nullable=False,
        default=lambda: get_local_now().date(),
    )
    # AJ18-B: data de entrada do aluno na oferta. NULL = desde o início (sem
    # corte de frequência). Preenchida quando a enturmação ocorre após o início
    # efetivo da oferta; inscrições existentes permanecem NULL.
    data_entrada_oferta: date = db.Column(db.Date, nullable=True)
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
    turma_curso = db.relationship(
        "TurmaCurso",
        backref="inscricoes_oferta",
        overlaps="turmas,alunos",
    )


class Transferencia(TenantMixin, db.Model):
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

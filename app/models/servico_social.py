"""
================================================================================
SERVICO_SOCIAL.PY - Serviço Social
================================================================================

Contém:
    - AgendaServicoSocial : eventos do serviço social (com sync Google).
    - RespostaFormulario  : respostas de formulários dinâmicos.

Ambos apoiam o fluxo do setor de Serviço Social.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now, JSONType


class AgendaServicoSocial(db.Model):
    """
    Evento da agenda do Serviço Social, com integração Google Calendar.

    Campos:
        - `participantes_emails`: e-mails separados por vírgula.
        - `google_event_id`: ID do evento no Google (preenchido após sync).
        - `autor`: usuário que criou o evento.

    O método `get_attendees_list()` formata os e-mails para a API do Google.
    """

    __tablename__ = "agenda_servico_social"

    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    localizacao = db.Column(db.String(255), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    google_event_id = db.Column(db.String(255), nullable=True)

    # Ex.: "pai@email.com, aluno@email.com"
    participantes_emails = db.Column(db.Text, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    autor = db.relationship("User", backref="agendamentos_sociais")
    data_criacao = db.Column(db.DateTime, default=db.func.current_timestamp())

    def get_attendees_list(self):
        """Converte `participantes_emails` no formato esperado pela API do Google."""
        if not self.participantes_emails:
            return []
        emails = [e.strip() for e in self.participantes_emails.split(",")]
        return [{"email": email} for email in emails]


class RespostaFormulario(db.Model):
    """
    Resposta de qualquer formulário dinâmico do Serviço Social.

    `tipo_formulario` identifica qual formulário foi preenchido (ex.:
    'acompanhamento_familiar'). O conteúdo completo fica em `dados` (JSON).

    Regras:
        - `usuario_id` é obrigatório (quem preencheu).
        - `aluno_id` é opcional (formulários podem não ser por aluno).
    """

    __tablename__ = "respostas_formulario"

    id = db.Column(db.Integer, primary_key=True)
    tipo_formulario = db.Column(db.String(50), nullable=False)
    aluno_id = db.Column(db.Integer, db.ForeignKey("aluno.id"), nullable=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    dados = db.Column(JSONType, nullable=False)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, default=get_local_now, onupdate=get_local_now)

    aluno = db.relationship("Aluno", backref="formularios")
    usuario = db.relationship("User", backref="formularios_preenchidos")

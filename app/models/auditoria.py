"""
================================================================================
AUDITORIA.PY - Logs de auditoria
================================================================================

Contém:
    - LogAcao : registro de ações sensíveis executadas no painel.

Use este modelo em TODA operação destrutiva ou sensível (exclusões, alterações
de permissão, exportações de dados).
================================================================================
"""

from app.models.base import db, datetime, get_local_now


class LogAcao(db.Model):
    """
    Log de ações sensíveis executadas no painel.

    Uso típico:
        LogAcao(
            usuario_id=current_user.id,
            usuario_nome=current_user.name,
            acao='Excluir aluno',
            detalhes='aluno_id=42',
            ip=request.remote_addr,
            unidade_id=current_user.unidade_id,
        )

    Notas:
        - O método estático `normalize` produz uma versão sem acento e minúscula
          do texto da ação, útil para filtros/relatórios.
        - O `__init__` original tentava gravar `self.acao_normalizada` — coluna
          que NÃO existe. Foi removido para evitar dead code.
    """
    __tablename__ = 'log_acao'

    id: int = db.Column(db.Integer, primary_key=True)
    data_hora: datetime = db.Column(db.DateTime, default=get_local_now)
    usuario_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    usuario_nome: str = db.Column(db.String(100))
    acao: str = db.Column(db.String(255))
    detalhes: str = db.Column(db.Text)
    ip: str = db.Column(db.String(50))

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='logs_unidade')

    usuario = db.relationship('User', backref='logs')

    @staticmethod
    def normalize(text):
        """Remove acentos e baixa a caixa — para comparação/busca."""
        from unidecode import unidecode
        return unidecode(text).lower()
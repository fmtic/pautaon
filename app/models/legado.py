"""
================================================================================
LEGADO.PY - Modelos mantidos apenas para leitura de dados antigos
================================================================================

Contém:
    - Registro : armazenamento cru (JSON) de formulários flexíveis da base
                 antiga.

⚠️  NÃO USE ESTE MÓDULO EM CÓDIGO NOVO. ⚠️

Ele existe apenas para que telas históricas continuem funcionando. Qualquer
necessidade nova deve ser resolvida com `Atendimento` ou `RespostaFormulario`.
================================================================================
"""

from app.models.base import db, datetime, get_local_now


class Registro(db.Model):
    """
    [LEGADO] Armazenamento cru (JSON) de formulários flexíveis da base antiga.

    Não possui schema semântico: `dados_json` é uma string JSON sem contrato.
    Substituído gradualmente por `Atendimento` e `RespostaFormulario`.

    Uso recomendado: somente leitura, em telas históricas.
    """
    __tablename__ = 'registro'

    id: int = db.Column(db.Integer, primary_key=True)
    educador_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    turma: str = db.Column(db.String(100))
    mes: str = db.Column(db.String(20))
    turno: str = db.Column(db.String(20))
    dados_json: str = db.Column(db.Text)
    criado_em: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='registros_flexiveis')

    educador = db.relationship('User', backref='registros')
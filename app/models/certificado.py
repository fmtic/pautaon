"""
================================================================================
CERTIFICADO.PY - Modelo (imagem de fundo) do certificado por centro de custo
================================================================================

Contem:
    - ModeloCertificado : imagem PNG/JPG usada como modelo do certificado de
                          um centro de custo em um periodo letivo.

Regras:
    - O par (periodo_letivo, centro_custo) e UNICO: um modelo vigente por par;
      substituir apaga o arquivo anterior.
    - O arquivo vive fora do static (`UPLOAD_FOLDER`, ex.: instance/uploads)
      e so e servido por rota autenticada.
================================================================================
"""

from sqlalchemy import UniqueConstraint

from app.models.base import db, datetime, get_local_now


class ModeloCertificado(db.Model):
    """Modelo do certificado de um centro de custo em um período letivo."""

    __tablename__ = 'modelo_certificado'
    __table_args__ = (
        UniqueConstraint(
            'periodo_letivo_id',
            'centro_custo_id',
            name='uq_modelo_certificado_periodo_centro',
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    periodo_letivo_id = db.Column(
        db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=False
    )
    centro_custo_id = db.Column(
        db.Integer, db.ForeignKey('centro_custo.id'), nullable=False
    )

    # Nome do arquivo no disco (dentro de uploads/certificados/<periodo>/).
    arquivo = db.Column(db.String(255), nullable=False)
    # Nome enviado pelo usuário (usado no download) e metadados do upload.
    nome_original = db.Column(db.String(255))
    tipo = db.Column(db.String(60))
    tamanho = db.Column(db.Integer)

    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, onupdate=get_local_now)

    periodo = db.relationship('PeriodoLetivo', backref='modelos_certificado')
    centro_custo = db.relationship('CentroCusto', backref='modelos_certificado')

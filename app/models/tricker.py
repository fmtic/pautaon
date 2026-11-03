from datetime import datetime
from app import db

class AvisoTicker(db.Model):
    __tablename__ = 'aviso_ticker'
    
    id = db.Column(db.Integer, primary_key=True)
    texto = db.Column(db.String(255), nullable=False)
    ativo = db.Column(db.Boolean, default=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<AvisoTicker {self.id}>'
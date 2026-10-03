# -*- coding: utf-8 -*-
"""
AuditoriaMixin
==============
Mixin que adiciona colunas de auditoria padrão a qualquer modelo SQLAlchemy.

Colunas adicionadas:
    - ``updated_by_id``   : ID do usuário que realizou a última alteração.
    - ``updated_by_name`` : Snapshot do nome do editor no momento da edição.
    - ``updated_at``      : Timestamp da última alteração (fuso local da aplicação).

Compatibilidade com SQLAlchemy 2.x
------------------------------------
No SQLAlchemy 2.x, colunas com ``ForeignKey`` e ``relationship()`` definidos
em mixins **devem** ser declarados via ``@declared_attr``. Caso contrário, o
mapeador lança ``InvalidRequestError`` ao tentar registrar a propriedade
compartilhada entre modelos distintos.

O ``__allow_unmapped__ = True`` é necessário para que o SQLAlchemy ignore
atributos sem anotação ``Mapped[...]``.
"""

from sqlalchemy.orm import declared_attr
from app.models.base import db, get_local_now


class AuditoriaMixin:
    """Mixin de auditoria padrão para modelos SQLAlchemy.

    Herdar este mixin adiciona automaticamente três colunas ao modelo:

    Atributos
    ---------
    updated_by_id : int, nullable
        FK para ``user.id``; preserva quem fez a última alteração.
        Anulado automaticamente (``ON DELETE SET NULL``) se o usuário
        for excluído, evitando erros de integridade referencial.

    updated_by_name : str(100), nullable
        Snapshot do nome do editor no momento da edição. Permite
        rastrear a autoria mesmo após renomeação ou exclusão do usuário.

    updated_at : datetime, nullable
        Data/hora da última modificação no fuso local da aplicação.
        Permanece ``NULL`` para registros que nunca foram editados após
        o cadastro, distinguindo-os dos que já passaram por auditoria.

    updated_by : relationship → User
        Atalho de relacionamento para o ``User`` editor. Declarado
        como ``@declared_attr`` para que o SQLAlchemy recrie o
        relacionamento por classe concreta e evite conflitos de mapper.
    """

    # Permite atributos sem Mapped[] no SQLAlchemy 2.x (compatibilidade)
    __allow_unmapped__ = True

    @declared_attr
    def updated_by_id(cls):
        """FK para o usuário que realizou a última alteração.

        Declarado via ``@declared_attr`` para que o SQLAlchemy 2.x gerencie
        a coluna FK corretamente em cada modelo concreto derivado do mixin.
        """
        return db.Column(
            db.Integer,
            db.ForeignKey('user.id', ondelete='SET NULL'),
            nullable=True,
            comment='ID do usuário que fez a última alteração',
        )

    @declared_attr
    def updated_by(cls):
        """Relacionamento com ``User`` — editor da última alteração.

        ``foreign_keys`` usa a string canônica ``'<Modelo>.updated_by_id'``
        para que o SQLAlchemy resolva a FK corretamente em cada modelo
        derivado, sem ambiguidade quando há múltiplas FKs para ``user.id``.
        """
        return db.relationship(
            'User',
            foreign_keys=f'[{cls.__name__}.updated_by_id]',
            lazy='joined',
        )

    # Colunas simples (sem FK) não precisam de @declared_attr
    updated_by_name = db.Column(
        db.String(100),
        nullable=True,
        comment='Snapshot do nome do editor no momento da edição',
    )
    updated_at = db.Column(
        db.DateTime,
        default=get_local_now,
        onupdate=get_local_now,
        nullable=True,
        comment='Data/hora da última modificação (fuso local)',
    )

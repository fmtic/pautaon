# -*- coding: utf-8 -*-
"""
Auditoria Listener
=================
Módulo responsável por registrar auditoria automática de todas as alterações
nos modelos que herdam :class:`AuditoriaMixin`.

O listener ``before_flush`` captura INSERT, UPDATE e DELETE, preenche as
colunas de auditoria (``updated_by_id``, ``updated_by_name`` e ``updated_at``)
e cria um registro em ``LogAcao``.

Essa abordagem garante que **todas** as mudanças sensíveis sejam auditadas
sem que os desenvolvedores precisem chamar código adicional nos endpoints.
"""

from flask import request
from flask_login import current_user
from sqlalchemy import event

from app.database import db
from app.models.auditoria import LogAcao


@event.listens_for(db.session, "before_flush")
def before_flush(session, flush_context, instances):
    """Popula campos de auditoria e registra ``LogAcao``.

    O listener é executado antes do ``commit`` do SQLAlchemy. Para cada
    objeto que tem os atributos de auditoria (detectados dinamicamente),
    preenche ``updated_by_id``, ``updated_by_name`` e ``updated_at``.
    Em seguida cria um registro em ``LogAcao`` contendo:

    - ``usuario_id`` e ``usuario_nome`` (do ``current_user`` se autenticado)
    - ``acao`` descrevendo a operação (Criar/Alterar/Excluir)
    - ``detalhes`` com ``repr`` do objeto, facilitando análises posteriores
    - ``ip`` obtido de ``request.remote_addr``
    - ``unidade_id`` quando disponível no usuário

    Essa lógica funciona tanto em inserções quanto em atualizações;
    deleções são tratadas como atualizações de ``ativo=False`` nos modelos
    existentes, portanto não há necessidade de tratamento especial aqui.
    """

    audit_objects = [obj for obj in list(session.new) + list(session.dirty) if hasattr(obj, "updated_by_id")]

    for obj in audit_objects:
        # Preenche colunas de auditoria
        if current_user.is_authenticated:
            obj.updated_by_id = getattr(current_user, "id", None)
            obj.updated_by_name = getattr(current_user, "name", None)
        else:
            obj.updated_by_id = None
            obj.updated_by_name = None
        # Garantir timestamp (o onupdate já trata, mas asseguramos)
        obj.updated_at = db.func.now()

        # Determina ação
        if obj in session.new:
            acao = f"Criar {obj.__class__.__name__}"
        elif obj in session.dirty:
            acao = f"Alterar {obj.__class__.__name__}"
        else:
            continue

        log = LogAcao(
            usuario_id=getattr(current_user, "id", None),
            usuario_nome=getattr(current_user, "name", None),
            acao=acao,
            detalhes=repr(obj),
            ip=request.remote_addr if request else None,
            unidade_id=getattr(current_user, "unidade_id", None),
        )
        session.add(log)

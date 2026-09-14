import os
from pathlib import Path

from flask import abort, current_app
from werkzeug.utils import secure_filename

from app.models import Turma


def obter_proximo_ordenacao(periodo_letivo_id):
    if periodo_letivo_id is None:
        query = Turma.query.filter(Turma.periodo_letivo_id.is_(None))
    else:
        query = Turma.query.filter_by(periodo_letivo_id=periodo_letivo_id)

    ordenacoes_usadas = set()
    for turma in query.all():
        if turma.ordenacao and (turma.ativo or turma.alunos.count() > 0):
            ordenacoes_usadas.add(turma.ordenacao)

    proximo = 1
    while proximo in ordenacoes_usadas:
        proximo += 1
    return proximo


def assert_unidade_context(obj_unidade_id, unidade_id):
    """Impede que dados de uma unidade sejam acessados em outra.

    Este helper centraliza a regra de segurança por contexto de unidade e ajuda a
    manter consistência entre os módulos do sistema acadêmico.
    """
    if unidade_id and obj_unidade_id != unidade_id:
        abort(403)


def _build_upload_path(*parts: str) -> str:
    """Constrói um caminho de upload confiável, evitando traversal e caminhos maliciosos."""
    base_path = Path(current_app.static_folder) / "uploads"
    target_path = base_path.joinpath(*parts)
    target_path = target_path.resolve()
    base_resolved = base_path.resolve()
    if not str(target_path).startswith(str(base_resolved)):
        raise ValueError("Caminho de upload inválido.")
    return str(target_path)


def salvar_foto(foto, aluno):
    filename = secure_filename(f"aluno_{aluno.id}_{foto.filename}")
    upload_path = _build_upload_path("fotos")
    os.makedirs(upload_path, exist_ok=True)
    foto.save(os.path.join(upload_path, filename))
    aluno.foto_path = filename


def salvar_documento(documento, aluno, doc_id):
    if not documento or not documento.filename:
        return False

    _, ext = os.path.splitext(documento.filename)
    if ext.lower() != ".pdf":
        return False

    mat_folder = aluno.matricula.replace(".", "_") if aluno.matricula else f"aluno_{aluno.id}"
    upload_path = _build_upload_path("documentos", mat_folder)
    os.makedirs(upload_path, exist_ok=True)

    filename = secure_filename(f"{doc_id}.pdf")
    documento.save(os.path.join(upload_path, filename))
    return True

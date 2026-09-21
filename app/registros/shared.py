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

    Qualquer operador local sem unidade vinculada ou sem contexto de sessão
    válido deve ser bloqueado imediatamente para evitar IDOR e isolamento
    multitenant quebrado.
    """
    if obj_unidade_id is None:
        abort(403)
    if unidade_id is None:
        abort(403)
    if obj_unidade_id != unidade_id:
        abort(403)


def _get_upload_root() -> Path:
    """Retorna o diretório base seguro de uploads configurado."""
    folder = current_app.config.get("UPLOAD_FOLDER")
    if folder:
        return Path(folder)
    return Path(current_app.instance_path) / "uploads"


def _build_upload_path(*parts: str) -> str:
    """Constrói um caminho de upload confiável dentro da pasta segura de uploads,
    evitando traversal e caminhos maliciosos.
    """
    base_path = _get_upload_root()
    base_resolved = base_path.resolve()
    target_path = base_path.joinpath(*parts).resolve()
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

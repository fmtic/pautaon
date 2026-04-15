import os

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
    if unidade_id and obj_unidade_id != unidade_id:
        abort(403)


def salvar_foto(foto, aluno):
    filename = secure_filename(f"aluno_{aluno.id}_{foto.filename}")
    upload_path = os.path.join(current_app.static_folder, "uploads", "fotos")
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
    upload_path = os.path.join(
        current_app.static_folder, "uploads", "documentos", mat_folder
    )
    os.makedirs(upload_path, exist_ok=True)

    filename = secure_filename(f"{doc_id}.pdf")
    documento.save(os.path.join(upload_path, filename))
    return True

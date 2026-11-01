import os
from pathlib import Path

from flask import abort, current_app
from werkzeug.utils import secure_filename

from app.models import Turma
from app.utils.fotos import nome_foto_aluno, validar_foto


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
    """Grava a foto do aluno depois de validada (S1-08).

    Devolve a mensagem de erro em português quando o arquivo é recusado — nada
    é gravado nesse caso — ou `None` quando a foto foi salva. Quem chama decide
    como avisar o usuário (`flash`), sem derrubar o cadastro do aluno.
    """
    if not foto or not getattr(foto, "filename", ""):
        return None

    erro, extensao = validar_foto(foto)
    if erro:
        return erro

    upload_path = _build_upload_path("fotos")
    os.makedirs(upload_path, exist_ok=True)
    # Nome gerado pelo servidor: nada do `filename` do cliente chega ao disco.
    filename = nome_foto_aluno(aluno.id, extensao)
    foto.save(os.path.join(upload_path, filename))
    aluno.foto_path = filename
    return None


#: Limite de tamanho aceito por documento PDF entregue (2 MB) — AJ5-B.
DOC_MAX_BYTES = 2 * 1024 * 1024


def validar_pdf(documento, max_bytes=DOC_MAX_BYTES):
    """Valida um PDF **antes** de gravar qualquer byte (AJ5-B).

    Devolve o motivo da recusa em português ou `None` quando o arquivo é um
    PDF aceito. Regras, na mesma linha do padrão S1-08 da foto:

    - a extensão `.pdf` continua exigida (nunca confiamos só no conteúdo);
    - o tamanho vem de `seek`/`tell`, sem carregar o arquivo inteiro em
      memória: vazio é rejeitado, exatamente `max_bytes` passa, acima não;
    - a assinatura `%PDF-` é procurada nos primeiros 1024 bytes, como a
      especificação permite (um PDF pode ter até 1023 bytes de lixo antes).

    Nada é gravado nem lido por completo aqui; quem chama decide o que fazer.
    """
    if not documento or not getattr(documento, "filename", ""):
        return "documento não enviado."

    _, ext = os.path.splitext(documento.filename)
    if ext.lower() != ".pdf":
        return "use um arquivo no formato PDF."

    stream = documento.stream
    stream.seek(0, os.SEEK_END)
    tamanho = stream.tell()
    stream.seek(0)
    if tamanho == 0:
        return "o arquivo está vazio."
    if tamanho > max_bytes:
        return f"o arquivo tem mais de {max_bytes // (1024 * 1024)} MB."

    cabecalho = stream.read(1024)
    stream.seek(0)
    if b"%PDF-" not in cabecalho:
        return "o conteúdo do arquivo não é um PDF válido."

    return None


def salvar_documento(documento, aluno, doc_id):
    """Grava um documento PDF do aluno depois de validado (AJ5-B).

    Devolve o **motivo da recusa** em português quando o arquivo não é aceito
    — nada é gravado nesse caso — ou `None` quando salvou. Antes de escrever
    um byte, `validar_pdf` confere tamanho (seek/tell, sem ler tudo em
    memória) e a assinatura `%PDF-`. O nome do arquivo enviado pelo cliente
    nunca aparece: o gravado é sempre `<doc_id>.pdf`.
    """
    if not documento or not documento.filename:
        return "documento não enviado."

    erro = validar_pdf(documento)
    if erro:
        return erro

    mat_folder = aluno.matricula.replace(".", "_") if aluno.matricula else f"aluno_{aluno.id}"
    upload_path = _build_upload_path("documentos", mat_folder)
    os.makedirs(upload_path, exist_ok=True)

    filename = secure_filename(f"{doc_id}.pdf")
    documento.save(os.path.join(upload_path, filename))
    return None

"""Rotas do módulo de Atendimentos Individuais de Alunos.

Qualquer perfil operacional pode registrar e consultar atendimentos.
Apenas o próprio autor ou um admin pode editar/excluir um registro.
"""

import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zipfile import BadZipFile, ZipFile

from flask import (
    abort, current_app, jsonify, render_template, request,
    send_file, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select
from sqlalchemy.orm import contains_eager
from app.database import db
from app.models import Aluno, Atendimento
from app.registros.shared import validar_pdf
from app.utils.fotos import tipo_por_assinatura
from app.utils.logica import get_unidade_id
from . import bp
from .shared import _build_upload_path, _get_upload_root, assert_unidade_context

# Roles com acesso ao módulo de atendimentos
_ROLES_ATENDIMENTO = {"admin", "pedagogico", "gerencia", "secretaria", "servico_social"}

# Mapeamento setor → label amigável + badge color
SETORES = {
    "pedagogico":    {"label": "Pedagógico",    "color": "primary"},
    "servico_social": {"label": "Serviço Social", "color": "success"},
    "secretaria":    {"label": "Secretaria",    "color": "warning"},
    "admin":         {"label": "Administração", "color": "danger"},
}

_ANEXOS_PERMITIDOS = {
    ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt",
    ".png", ".jpg", ".jpeg",
}
_ANEXO_MIME = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".odt": "application/vnd.oasis.opendocument.text",
    ".rtf": "application/rtf",
    ".txt": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}
_MAX_ANEXO_BYTES = 2 * 1024 * 1024
_OLE_ASSINATURA = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_ODT_MIMETYPE = b"application/vnd.oasis.opendocument.text"
_DOCX_MIMETYPE = (
    b"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"
)


def _anexo_tem_assinatura(anexo, extensao: str) -> bool:
    stream = anexo.stream
    stream.seek(0)

    if extensao == ".pdf":
        return validar_pdf(anexo, max_bytes=_MAX_ANEXO_BYTES) is None
    if extensao in {".png", ".jpg", ".jpeg"}:
        tipo = tipo_por_assinatura(stream.read(32))
        esperado = "png" if extensao == ".png" else "jpg"
        return tipo == esperado
    if extensao == ".doc":
        stream.seek(0)
        conteudo = stream.read(_MAX_ANEXO_BYTES)
        return (
            conteudo.startswith(_OLE_ASSINATURA)
            and "WordDocument".encode("utf-16le") + b"\x00\x00" in conteudo
        )
    if extensao == ".rtf":
        return stream.read(5).lower() == b"{\\rtf"
    if extensao == ".txt":
        conteudo = stream.read(_MAX_ANEXO_BYTES + 1)
        controles = {byte for byte in range(32)} - {9, 10, 12, 13}
        return not any(byte in controles for byte in conteudo)
    if extensao in {".docx", ".odt"}:
        if stream.read(4) != b"PK\x03\x04":
            return False
        stream.seek(0)
        try:
            with ZipFile(stream) as arquivo_zip:
                nomes = set(arquivo_zip.namelist())
                if extensao == ".docx":
                    info_tipos = arquivo_zip.getinfo("[Content_Types].xml")
                    if info_tipos.file_size > 64 * 1024:
                        return False
                    return (
                        _DOCX_MIMETYPE in arquivo_zip.read(info_tipos)
                        and "word/document.xml" in nomes
                    )
                info_mimetype = arquivo_zip.getinfo("mimetype")
                return (
                    info_mimetype.file_size == len(_ODT_MIMETYPE)
                    and arquivo_zip.read(info_mimetype) == _ODT_MIMETYPE
                )
        except (BadZipFile, KeyError, OSError, RuntimeError):
            return False
    return False


def _ler_payload() -> dict:
    payload = request.get_json(silent=True) or {}
    if not payload and request.form:
        try:
            payload = json.loads(request.form.get("payload", "{}"))
        except (TypeError, ValueError):
            return {}
    return payload


def _salvar_anexo() -> dict | None:
    anexo = request.files.get("anexo")
    if not anexo or not anexo.filename:
        return None

    extensao = Path(anexo.filename).suffix.lower()
    if extensao not in _ANEXOS_PERMITIDOS:
        raise ValueError("Tipo de anexo não permitido.")

    anexo.stream.seek(0, 2)
    tamanho = anexo.stream.tell()
    anexo.stream.seek(0)
    if tamanho == 0:
        raise ValueError("O anexo está vazio.")
    if tamanho > _MAX_ANEXO_BYTES:
        raise ValueError("O anexo deve ter no máximo 2 MB.")
    if not _anexo_tem_assinatura(anexo, extensao):
        raise ValueError(
            "O conteúdo do anexo não corresponde ao formato "
            f"{extensao.lstrip('.').upper()} informado."
        )

    pasta = _build_upload_path("documentos", "atendimentos")
    Path(pasta).mkdir(parents=True, exist_ok=True)
    nome_final = f"{uuid4().hex}{extensao}"
    anexo.stream.seek(0)
    anexo.save(str(Path(pasta) / nome_final))
    return {
        "nome": anexo.filename,
        "arquivo": f"atendimentos/{nome_final}",
        "tamanho": tamanho,
    }


def _setor_do_usuario() -> str:
    """Mapeia o role do usuário para o setor padrão do atendimento."""
    mapa = {
        "pedagogico":    "pedagogico",
        "servico_social": "servico_social",
        "secretaria":    "secretaria",
        "admin":         "admin",
        "gerencia":      "admin",
    }
    return mapa.get(current_user.role, "admin")


# ---------------------------------------------------------------------------
# SELEÇÃO DO MÓDULO DE ATENDIMENTO
# ---------------------------------------------------------------------------
@bp.route("/alunos/atendimentos/transicao")
@login_required
def transicao_atendimentos():
    """Exibe os módulos de atendimento disponíveis para o usuário."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    return render_template("alunos/transicao_atendimentos.html")


# ---------------------------------------------------------------------------
# LISTAGEM PRINCIPAL
# ---------------------------------------------------------------------------
@bp.route("/alunos/atendimentos")
@login_required
def listar_atendimentos():
    """Lista atendimentos agrupados por aluno (1 linha = último atendimento por aluno)."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    unidade_id = get_unidade_id()
    page = request.args.get("page", 1, type=int)
    search_nome = request.args.get("nome", "").strip()
    search_matr = request.args.get("matricula", "").strip()
    search_setor = request.args.get("setor", "").strip()
    data_inicio = request.args.get("data_inicio", "").strip()
    data_fim = request.args.get("data_fim", "").strip()

    # Seleciona um único atendimento mais recente por aluno, incluindo o autor.
    ultimo_atendimento_id = (
        select(Atendimento.id)
        .where(Atendimento.aluno_id == Aluno.id)
        .order_by(
            Atendimento.data_atendimento.desc(),
            Atendimento.created_at.desc(),
            Atendimento.id.desc(),
        )
        .limit(1)
        .correlate(Aluno)
        .scalar_subquery()
    )

    query = (
        db.session.query(Atendimento)
        .join(Aluno, Aluno.id == Atendimento.aluno_id)
        .options(contains_eager(Atendimento.aluno))
        .filter(Atendimento.id == ultimo_atendimento_id)
        .filter(Aluno.ativo.is_(True))
    )

    if unidade_id:
        query = query.filter(Aluno.unidade_id == unidade_id)

    if search_nome:
        query = query.filter(
            db.or_(
                Aluno.nome.ilike(f"%{search_nome}%"),
                Aluno.nome_social.ilike(f"%{search_nome}%"),
            )
        )

    if search_matr:
        try:
            aluno_id = int(search_matr.split(".")[0])
            query = query.filter(Aluno.id == aluno_id)
        except (ValueError, IndexError):
            pass

    if search_setor:
        alunos_com_setor = (
            db.session.query(Atendimento.aluno_id)
            .filter(Atendimento.setor == search_setor)
            .distinct()
            .subquery()
        )
        query = query.filter(Aluno.id.in_(alunos_com_setor))

    if data_inicio:
        try:
            di = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            alunos_no_periodo = (
                db.session.query(Atendimento.aluno_id)
                .filter(Atendimento.data_atendimento >= di)
                .distinct()
                .subquery()
            )
            query = query.filter(Aluno.id.in_(alunos_no_periodo))
        except ValueError:
            pass

    if data_fim:
        try:
            df = datetime.strptime(data_fim, "%Y-%m-%d").date()
            alunos_no_periodo = (
                db.session.query(Atendimento.aluno_id)
                .filter(Atendimento.data_atendimento <= df)
                .distinct()
                .subquery()
            )
            query = query.filter(Aluno.id.in_(alunos_no_periodo))
        except ValueError:
            pass

    query = query.order_by(Atendimento.data_atendimento.desc())

    per_page = 20
    total = query.count()
    rows = query.offset((page - 1) * per_page).limit(per_page).all()

    class Paginator:
        def __init__(self, items, page, per_page, total):
            self.items = items
            self.page = page
            self.per_page = per_page
            self.total = total
            self.pages = max(1, (total + per_page - 1) // per_page)
            self.has_prev = page > 1
            self.has_next = page < self.pages
            self.prev_num = page - 1
            self.next_num = page + 1

    pagination = Paginator(rows, page, per_page, total)

    # H3e: dias/horário do aluno (oferta da inscrição ativa) pela grade.
    from .alunos import _grade_por_aluno

    grade_aluno_map = _grade_por_aluno(
        [row.aluno_id for row in rows if row.aluno_id]
    )

    return render_template(
        "alunos/atendimento_pedagogico.html",
        pagination=pagination,
        grade_aluno_map=grade_aluno_map,
        setores=SETORES,
        search_nome=search_nome,
        search_matr=search_matr,
        search_setor=search_setor,
        data_inicio=data_inicio,
        data_fim=data_fim,
    )


# ---------------------------------------------------------------------------
# HISTÓRICO DE ATENDIMENTOS DE UM ALUNO
# ---------------------------------------------------------------------------
@bp.route("/alunos/<int:aluno_id>/atendimentos")
@login_required
def historico_atendimentos(aluno_id):
    """Retorna JSON com todos os atendimentos de um aluno — usado pelo modal."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    atendimentos = (
        Atendimento.query.filter_by(aluno_id=aluno_id)
        .order_by(Atendimento.data_atendimento.desc(), Atendimento.created_at.desc())
        .all()
    )

    resultado = []
    for a in atendimentos:
        setor_info = SETORES.get(a.setor, {"label": a.setor, "color": "secondary"})
        resultado.append({
            "id": a.id,
            "setor": a.setor,
            "setor_label": setor_info["label"],
            "setor_color": setor_info["color"],
            "data_atendimento": a.data_atendimento.strftime("%d/%m/%Y") if a.data_atendimento else "",
            "resumo": a.resumo or "",
            "dados": a.dados or {},
            "atendido_por_nome": a.atendido_por_nome or "",
            "created_at": a.created_at.strftime("%d/%m/%Y %H:%M") if a.created_at else "",
            "anexo_url": url_for("registros.baixar_anexo_atendimento", id=a.id) if (a.dados or {}).get("anexo") else None,
            "pode_editar": (
                current_user.id == a.atendido_por_id
                or current_user.role == "admin"
            ),
        })

    return jsonify(resultado)


# ---------------------------------------------------------------------------
# REGISTRAR ATENDIMENTO
# ---------------------------------------------------------------------------
@bp.route("/alunos/<int:aluno_id>/atendimentos/novo", methods=["POST"])
@login_required
def registrar_atendimento(aluno_id):
    """Persiste um novo registro de atendimento via AJAX (JSON ou multipart)."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    payload = _ler_payload()
    if not payload:
        return jsonify({"ok": False, "erro": "Dados do atendimento inválidos."}), 400

    data_str = payload.get("data_atendimento", "")
    try:
        data_atendimento = datetime.strptime(data_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"ok": False, "erro": "Data inválida."}), 400

    setor = payload.get("setor") or _setor_do_usuario()
    if setor not in SETORES:
        return jsonify({"ok": False, "erro": "Setor inválido."}), 400

    resumo = (payload.get("resumo") or "").strip()[:255]
    dados = payload.get("dados") or {}
    if dados.get("origem") not in {"Educando", "Família", "Equipe"}:
        return jsonify({"ok": False, "erro": "Origem do atendimento inválida."}), 400
    if not str(dados.get("motivo") or "").strip():
        return jsonify({"ok": False, "erro": "O motivo do atendimento é obrigatório."}), 400

    try:
        anexo = _salvar_anexo()
    except ValueError as exc:
        current_app.logger.warning("Arquivo de anexo inválido ao registrar atendimento.")
        return jsonify({"ok": False, "erro": str(exc)}), 400
    if anexo:
        dados["anexo"] = anexo

    try:
        novo = Atendimento(
            aluno_id=aluno_id,
            setor=setor,
            data_atendimento=data_atendimento,
            resumo=resumo,
            dados=dados,
            atendido_por_id=current_user.id,
            atendido_por_nome=current_user.name,
            unidade_id=get_unidade_id(),
        )
        db.session.add(novo)
        db.session.commit()
        return jsonify({"ok": True, "id": novo.id}), 201
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao registrar atendimento.")
        return jsonify({"ok": False, "erro": "Não foi possível salvar o atendimento."}), 500


# ---------------------------------------------------------------------------
# DETALHE / EDIÇÃO
# ---------------------------------------------------------------------------
@bp.route("/atendimentos/<int:id>", methods=["GET"])
@login_required
def detalhe_atendimento(id):
    """Retorna JSON com os dados completos de um atendimento."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    a = db.get_or_404(Atendimento, id)
    assert_unidade_context(a.unidade_id, get_unidade_id())
    setor_info = SETORES.get(a.setor, {"label": a.setor, "color": "secondary"})

    return jsonify({
        "id": a.id,
        "aluno_id": a.aluno_id,
        "setor": a.setor,
        "setor_label": setor_info["label"],
        "setor_color": setor_info["color"],
        "data_atendimento": a.data_atendimento.strftime("%Y-%m-%d") if a.data_atendimento else "",
        "resumo": a.resumo or "",
        "dados": a.dados or {},
        "anexo_url": url_for("registros.baixar_anexo_atendimento", id=a.id) if (a.dados or {}).get("anexo") else None,
        "atendido_por_nome": a.atendido_por_nome or "",
        "created_at": a.created_at.strftime("%d/%m/%Y %H:%M") if a.created_at else "",
        "pode_editar": (
            current_user.id == a.atendido_por_id
            or current_user.role == "admin"
        ),
    })


@bp.route("/atendimentos/<int:id>/editar", methods=["POST"])
@login_required
def editar_atendimento(id):
    """Atualiza um atendimento existente (somente autor ou admin)."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    a = db.get_or_404(Atendimento, id)

    if current_user.id != a.atendido_por_id and current_user.role != "admin":
        return jsonify({"ok": False, "erro": "Sem permissão para editar este registro."}), 403

    payload = _ler_payload()
    if not payload:
        return jsonify({"ok": False, "erro": "Dados do atendimento inválidos."}), 400

    data_str = payload.get("data_atendimento", "")
    try:
        a.data_atendimento = datetime.strptime(data_str, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return jsonify({"ok": False, "erro": "Data inválida."}), 400

    setor = payload.get("setor") or a.setor
    if setor not in SETORES:
        return jsonify({"ok": False, "erro": "Setor inválido."}), 400

    a.setor = setor
    a.resumo = (payload.get("resumo") or "").strip()[:255]
    a.dados = payload.get("dados") or a.dados
    if a.dados.get("origem") not in {"Educando", "Família", "Equipe"}:
        return jsonify({"ok": False, "erro": "Origem do atendimento inválida."}), 400
    if not str(a.dados.get("motivo") or "").strip():
        return jsonify({"ok": False, "erro": "O motivo do atendimento é obrigatório."}), 400

    try:
        anexo = _salvar_anexo()
    except ValueError as exc:
        current_app.logger.warning("Arquivo de anexo inválido ao editar atendimento.")
        return jsonify({"ok": False, "erro": str(exc)}), 400
    if anexo:
        a.dados = {**(a.dados or {}), "anexo": anexo}

    try:
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao editar atendimento.")
        return jsonify({"ok": False, "erro": "Não foi possível atualizar o atendimento."}), 500


@bp.route("/atendimentos/<int:id>/excluir", methods=["POST"])
@login_required
def excluir_atendimento(id):
    """Remove um atendimento (somente autor ou admin)."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    a = db.get_or_404(Atendimento, id)

    if current_user.id != a.atendido_por_id and current_user.role != "admin":
        return jsonify({"ok": False, "erro": "Sem permissão para excluir este registro."}), 403

    try:
        db.session.delete(a)
        db.session.commit()
        return jsonify({"ok": True})
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Falha ao excluir atendimento.")
        return jsonify({"ok": False, "erro": "Não foi possível excluir o atendimento."}), 500


@bp.route("/atendimentos/<int:id>/anexo")
@login_required
def baixar_anexo_atendimento(id: int):
    """Serve anexo de atendimento com autenticação e validação de permissão."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    a = db.get_or_404(Atendimento, id)
    assert_unidade_context(a.unidade_id, get_unidade_id())

    anexo_info = (a.dados or {}).get("anexo")
    if not anexo_info or not isinstance(anexo_info, dict):
        abort(404)

    rel_path = anexo_info.get("arquivo", "")
    if not rel_path:
        abort(404)

    filename = Path(rel_path).name
    if not filename:
        abort(404)

    upload_root = _get_upload_root()
    pasta = upload_root / "documentos" / "atendimentos"
    target_file = pasta / filename
    if target_file.is_file():
        mimetype = _ANEXO_MIME.get(target_file.suffix.lower())
        if mimetype is None:
            abort(404)
        resposta = send_file(
            target_file,
            mimetype=mimetype,
            download_name=anexo_info.get("nome", filename),
            as_attachment=False,
        )
        resposta.headers["X-Content-Type-Options"] = "nosniff"
        resposta.headers["Cache-Control"] = "private, no-store"
        return resposta

    abort(404)

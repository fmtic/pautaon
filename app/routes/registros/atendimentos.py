"""Rotas do módulo de Atendimentos Individuais de Alunos.

Qualquer perfil operacional pode registrar e consultar atendimentos.
Apenas o próprio autor ou um admin pode editar/excluir um registro.
"""

from datetime import date, datetime

from flask import abort, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import and_, func, select

from app.database import db
from app.models import Aluno, Atendimento
from app.utils.logica import get_unidade_id
from . import bp
from .shared import assert_unidade_context

# Roles com acesso ao módulo de atendimentos
_ROLES_ATENDIMENTO = {"admin", "pedagogico", "gerencia", "secretaria", "servico_social"}

# Mapeamento setor → label amigável + badge color
SETORES = {
    "pedagogico":    {"label": "Pedagógico",    "color": "primary"},
    "servico_social": {"label": "Serviço Social", "color": "success"},
    "secretaria":    {"label": "Secretaria",    "color": "warning"},
    "admin":         {"label": "Administração", "color": "danger"},
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

    # Sub-query: data do último atendimento por aluno
    sub = (
        db.session.query(
            Atendimento.aluno_id,
            func.max(Atendimento.data_atendimento).label("ultimo_atendimento"),
        )
        .group_by(Atendimento.aluno_id)
        .subquery()
    )

    query = (
        db.session.query(Aluno, sub.c.ultimo_atendimento)
        .join(sub, Aluno.id == sub.c.aluno_id)
        .filter(Aluno.ativo == True)
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

    query = query.order_by(sub.c.ultimo_atendimento.desc())

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

    return render_template(
        "alunos/atendimentos.html",
        pagination=pagination,
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
    """Persiste um novo registro de atendimento via AJAX (JSON)."""
    if current_user.role not in _ROLES_ATENDIMENTO:
        abort(403)

    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    payload = request.get_json(silent=True) or {}

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
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "erro": str(exc)}), 500


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

    payload = request.get_json(silent=True) or {}

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

    try:
        db.session.commit()
        return jsonify({"ok": True})
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "erro": str(exc)}), 500


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
    except Exception as exc:
        db.session.rollback()
        return jsonify({"ok": False, "erro": str(exc)}), 500

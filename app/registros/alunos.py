"""
================================================================================
ALUNOS.PY - Rotas de gestão de alunos
================================================================================

Cobre:
    - Listagem com filtros (nome, matrícula, CPF, idade)
    - Cadastro, edição, exclusão, inativação
    - Histórico escolar
    - Transferência entre turmas
    - Desenturmação (remoção de vínculo)
    - Busca de instituições (autocomplete)
    - Impressão da ficha

ONDA 2A
    Datas/horas agora são tipos nativos (`date`/`time`). Parse feito via
    `parse_date`; formatação via `.strftime()`.

ONDA 2B
    Comparações de `current_user.role` usam `UserRole`.

ONDA 3B
    - Cadastro e edição gravam nas tabelas estruturadas (`EnderecoAluno`,
      `ResponsavelAluno`, `PerfilSocioeconomico`, `PerfilDiversidade`) e nas
      colunas novas de `Aluno` (nome_mae, orgao_rg, etc.).
    - Documentos entregues vão para `Aluno.documentos_entregues` (JSONB).
    - Os JSONs legados (`_identificacao_json`, etc.) NÃO são mais escritos
      pelo código novo; continuam existindo como fallback de leitura.
    - `editar_aluno` e `imprimir_aluno` passam `perfil=get_perfil_completo()`
      para o template.
================================================================================
"""

from datetime import date, datetime, timedelta
from pathlib import Path

from flask import (
    abort, current_app, flash, jsonify, redirect, render_template, request,
    send_from_directory, session, url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import select
from werkzeug.utils import secure_filename

from app.database import db
from app.models import Aluno, Frequencia, Inscricao, SituacaoEscolar, Turma
from app.models.enums import UserRole
from app.services.aluno_perfil import (
    get_perfil_completo,
    upsert_endereco,
    upsert_perfil_diversidade,
    upsert_perfil_socioeconomico,
    upsert_responsavel,
)
from app.utils.datetime_parse import parse_date
from app.utils.logica import calcular_estatisticas_frequencia, get_unidade_id
from . import bp
from .shared import (
    _get_upload_root,
    assert_unidade_context,
    salvar_documento,
    salvar_foto,
)


# =============================================================================
# HELPERS INTERNOS
# =============================================================================

def _validar_cpf(cpf: str) -> bool:
    """Valida dígitos verificadores do CPF. Retorna True se válido ou vazio."""
    cpf = (cpf or "").strip().replace(".", "").replace("-", "").replace(" ", "")
    if not cpf:
        return True  # campo opcional — vazio é aceito
    if len(cpf) != 11 or not cpf.isdigit() or len(set(cpf)) == 1:
        return False
    # Primeiro dígito verificador
    soma = sum(int(cpf[i]) * (10 - i) for i in range(9))
    d1 = 11 - (soma % 11)
    if d1 >= 10:
        d1 = 0
    if d1 != int(cpf[9]):
        return False
    # Segundo dígito verificador
    soma = sum(int(cpf[i]) * (11 - i) for i in range(10))
    d2 = 11 - (soma % 11)
    if d2 >= 10:
        d2 = 0
    return d2 == int(cpf[10])


def _sanitizar_cpf(cpf: str) -> str:
    """Remove tudo que não for dígito e devolve None se vazio."""
    if not cpf:
        return None
    limpo = "".join(c for c in cpf if c.isdigit())
    return limpo if limpo else None


def _salvar_situacao_escolar(aluno: Aluno) -> None:
    """Faz upsert da SituacaoEscolar do aluno com base no form da requisição."""
    nome = (request.form.get("nome_instituicao") or "").strip() or None
    campos_situacao = (
        "escolaridade",
        "status_escolar",
        "tipo_instituicao",
        "turno_escolar",
        "nome_instituicao",
    )
    form_tem_situacao = any(campo in request.form for campo in campos_situacao)
    tem_conteudo = any(
        (
            request.form.get("escolaridade"),
            request.form.get("status_escolar"),
            request.form.get("tipo_instituicao"),
            request.form.get("turno_escolar"),
            nome,
        )
    )
    if not tem_conteudo:
        if form_tem_situacao and aluno.situacao_escolar:
            db.session.delete(aluno.situacao_escolar)
        return
    situacao = aluno.situacao_escolar or SituacaoEscolar(aluno=aluno)
    situacao.unidade_id = aluno.unidade_id
    situacao.escolaridade = request.form.get("escolaridade")
    periodo = request.form.get("ensino_superior_periodo", type=int)
    situacao.ensino_superior_periodo = (
        periodo
        if situacao.escolaridade == "Ensino superior" and periodo in range(1, 11)
        else None
    )
    situacao.escolaridade_outro = (
        (request.form.get("escolaridade_outro") or "").strip()
        if situacao.escolaridade == "Outros"
        else None
    )
    situacao.status = request.form.get("status_escolar")
    situacao.status_outro = (
        (request.form.get("status_escolar_outro") or "").strip() or None
        if situacao.status == "Outros"
        else None
    )
    situacao.nome_instituicao = nome
    situacao.tipo_instituicao = request.form.get("tipo_instituicao")
    situacao.bolsista = (
        bool(request.form.get("bolsista"))
        if situacao.tipo_instituicao == "Privada"
        else False
    )
    situacao.tipo_instituicao_outro = (
        (request.form.get("tipo_instituicao_outro") or "").strip()
        if situacao.tipo_instituicao == "Outro"
        else None
    )
    situacao.turno = request.form.get("turno_escolar")
    situacao.turno_outro = (
        (request.form.get("turno_escolar_outro") or "").strip()
        if situacao.turno == "Outros"
        else None
    )
    db.session.add(situacao)


# Lista canônica dos documentos com checkbox no formulário.
DOC_IDS = [
    "doc_aluno",
    "doc_residencia",
    "doc_declaracao",
    "doc_atestado",
    "doc_termo",
    "doc_responsavel",
    "doc_laudo",
]


def _atualizar_documentos_entregues(aluno: Aluno) -> None:
    """
    Faz upsert dos arquivos enviados no form e grava o dict resultante em
    `aluno.documentos_entregues` (JSONB).

    Formato:
        {'doc_entregue': {'doc_aluno': True, 'doc_termo': False, ...}}
    """
    docs = dict(aluno.documentos_entregues or {})
    entregues = dict(docs.get("doc_entregue", {}))

    for doc_id in DOC_IDS:
        documento = request.files.get(doc_id)
        if (
            documento
            and documento.filename
            and salvar_documento(documento, aluno, doc_id)
        ):
            entregues[doc_id] = True

    docs["doc_entregue"] = entregues
    aluno.documentos_entregues = docs


def _aplicar_campos_civis(aluno: Aluno, form) -> None:
    """
    Aplica os campos migrados de `identificacao_json` direto em `Aluno`.

    Campos: orgao_rg, nacionalidade, natural_uf, natural_cidade, nome_mae,
    cpf_mae, nome_pai, cpf_pai, vai_acompanhado_aulas, acompanhante_aulas.
    """
    aluno.orgao_rg = (form.get("orgao_rg") or "").strip() or None
    aluno.nacionalidade = (form.get("nacionalidade") or "").strip() or None
    aluno.natural_uf = (form.get("natural_uf") or "").strip() or None
    aluno.natural_cidade = (form.get("natural_cidade") or "").strip() or None
    aluno.nome_mae = (form.get("nome_mae") or "").strip() or None
    aluno.cpf_mae = (form.get("cpf_mae") or "").strip() or None
    aluno.nome_pai = (form.get("nome_pai") or "").strip() or None
    aluno.cpf_pai = (form.get("cpf_pai") or "").strip() or None

    vai_acompanhado = bool(form.get("vai_acompanhado_aulas"))
    aluno.vai_acompanhado_aulas = vai_acompanhado
    aluno.acompanhante_aulas = (
        (form.get("acompanhante_aulas") or "").strip() or None
        if vai_acompanhado
        else None
    )


# =============================================================================
# AUTOCOMPLETE E AJUSTES RÁPIDOS
# =============================================================================

@bp.route("/alunos/instituicoes")
@login_required
def buscar_instituicoes():
    termo = (request.args.get("q") or "").strip()
    if len(termo) < 2:
        return jsonify([])

    consulta = (
        db.session.query(SituacaoEscolar.nome_instituicao)
        .filter(SituacaoEscolar.nome_instituicao.isnot(None))
        .filter(SituacaoEscolar.nome_instituicao.ilike(f"%{termo}%"))
        .distinct()
    )
    unidade_id = get_unidade_id()
    if unidade_id:
        consulta = consulta.filter(SituacaoEscolar.unidade_id == unidade_id)
    return jsonify(
        [
            nome
            for (nome,) in consulta.order_by(
                SituacaoEscolar.nome_instituicao
            ).limit(10)
        ]
    )


@bp.route("/aluno/<int:aluno_id>/atualizar-nivel", methods=["POST"])
@login_required
def atualizar_nivel_aluno(aluno_id):
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        abort(403)

    aluno = db.get_or_404(Aluno, aluno_id)
    nivel = request.form.get("nivel")
    turma_id = request.form.get("turma_id")
    if nivel == "Não se aplica":
        aluno.nivel = None
    elif nivel:
        aluno.nivel = nivel

    try:
        db.session.commit()
        flash(f"Nível do aluno {aluno.nome} atualizado com sucesso!", "success")
    except Exception as exc:
        from app.utils.errors import flash_and_log

        db.session.rollback()
        flash_and_log(exc, location="registros.atualizar_nivel_aluno", hint="db")

    if turma_id:
        return redirect(url_for("registros.ver_turma", id=turma_id))
    return redirect(url_for("registros.gerenciar_alunos"))


# =============================================================================
# LISTAGEM
# =============================================================================

@bp.route("/alunos")
@login_required
def gerenciar_alunos():
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
        UserRole.SERVICO_SOCIAL,
    ):
        abort(403)

    from app.utils.logica import calcular_idades

    page = request.args.get("page", 1, type=int)
    search_nome = request.args.get("nome", "").strip()
    search_matr = request.args.get("matricula", "").strip()
    search_cpf = request.args.get("cpf", "").strip()
    search_idade_min = request.args.get("idade_min", "", type=str).strip()
    search_idade_max = request.args.get("idade_max", "", type=str).strip()
    unidade_id = get_unidade_id()

    query = Aluno.query.filter_by(ativo=True)
    if unidade_id:
        query = query.filter_by(unidade_id=unidade_id)
    if search_nome:
        query = query.filter(
            db.or_(
                Aluno.nome.ilike(f"%{search_nome}%"),
                Aluno.nome_social.ilike(f"%{search_nome}%"),
            )
        )
    if search_cpf:
        cpf_limpo = search_cpf.replace(".", "").replace("-", "").strip()
        query = query.filter(
            db.or_(
                Aluno.cpf.ilike(f"%{search_cpf}%"),
                Aluno.cpf.ilike(f"%{cpf_limpo}%"),
            )
        )
    if search_matr:
        try:
            query = query.filter(Aluno.id == int(search_matr.split(".")[0]))
        except (ValueError, IndexError):
            pass

    alunos_lista = query.order_by(Aluno.nome).all()
    calcular_idades(alunos_lista)

    if search_idade_min or search_idade_max:
        idade_min = int(search_idade_min) if search_idade_min.isdigit() else 0
        idade_max = int(search_idade_max) if search_idade_max.isdigit() else 999
        alunos_lista = [
            a
            for a in alunos_lista
            if isinstance(a.idade_calculada, int)
            and idade_min <= a.idade_calculada <= idade_max
        ]

    per_page = 20
    total_filtrado = len(alunos_lista)
    start = (page - 1) * per_page
    items = alunos_lista[start:start + per_page]

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

    pagination = Paginator(items, page, per_page, total_filtrado)
    total_q = Aluno.query.filter_by(ativo=True)
    enturm_q = Aluno.query.filter_by(ativo=True)
    if unidade_id:
        total_q = total_q.filter_by(unidade_id=unidade_id)
        enturm_q = enturm_q.filter_by(unidade_id=unidade_id)

    return render_template(
        "alunos/gerenciar.html",
        pagination=pagination,
        total_alunos=total_q.count(),
        total_enturmados=enturm_q.filter(
            Aluno.turmas.any(Turma.ativo == True)
        ).count(),
        search_nome=search_nome,
        search_matr=search_matr,
        search_cpf=search_cpf,
        search_idade_min=search_idade_min,
        search_idade_max=search_idade_max,
        is_readonly=current_user.role == UserRole.SERVICO_SOCIAL,
    )


# =============================================================================
# CADASTRO
# =============================================================================

@bp.route("/aluno/novo", methods=["GET", "POST"])
@login_required
def novo_aluno():
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        abort(403)
    if request.method == "GET":
        return render_template("alunos/novo.html")

    from app.utils.logica import formatar_nome_proprio

    nome = request.form.get("nome")
    if not nome:
        flash(
            "O Campo 'Nome' não deve ser vazio no momento do Cadastro.",
            "warning",
        )
        return redirect(url_for("registros.gerenciar_alunos"))

    cpf_raw = request.form.get("cpf", "")
    if not _validar_cpf(cpf_raw):
        flash(
            "CPF inválido. Informe somente os 11 dígitos numéricos do CPF.",
            "danger",
        )
        return redirect(url_for("registros.novo_aluno"))

    try:
        # ---------------------------------------------------------------------
        # 1. Colunas diretas em Aluno
        # ---------------------------------------------------------------------
        novo = Aluno(
            nome=formatar_nome_proprio(nome),
            nome_social=formatar_nome_proprio(request.form.get("nome_social")),
            nivel=request.form.get("nivel"),
            ativo=True,
            unidade_id=get_unidade_id(),
            cpf=_sanitizar_cpf(cpf_raw),
            rg=request.form.get("rg") or None,
            whatsapp=request.form.get("whatsapp"),
            email=request.form.get("email"),
            data_nascimento=parse_date(request.form.get("data_nascimento")),
            created_by_id=current_user.id,
            created_by_name=current_user.name,
        )

        # Campos civis (Onda 3A) direto na tabela
        _aplicar_campos_civis(novo, request.form)

        ids_turmas = request.form.getlist("turmas_selecionadas")
        if ids_turmas:
            novo.turmas = Turma.query.filter(Turma.id.in_(ids_turmas)).all()

        db.session.add(novo)
        db.session.flush()  # gera novo.id

        # ---------------------------------------------------------------------
        # 2. SituacaoEscolar (tabela dedicada, fluxo mantido)
        # ---------------------------------------------------------------------
        _salvar_situacao_escolar(novo)

        # ---------------------------------------------------------------------
        # 3. Perfis (Onda 3B): endereço, responsável, socioeconômico, diversidade
        # ---------------------------------------------------------------------
        upsert_endereco(novo, request.form)
        upsert_responsavel(novo, request.form)
        upsert_perfil_socioeconomico(novo, request.form)
        upsert_perfil_diversidade(novo, request.form)

        # ---------------------------------------------------------------------
        # 4. Foto
        # ---------------------------------------------------------------------
        foto = request.files.get("foto")
        if foto and foto.filename:
            salvar_foto(foto, novo)

        # ---------------------------------------------------------------------
        # 5. Documentos entregues (JSONB `documentos_entregues`)
        # ---------------------------------------------------------------------
        _atualizar_documentos_entregues(novo)

        db.session.commit()
        flash(
            f"Aluno {novo.nome_social or novo.nome} cadastrado com sucesso!",
            "success",
        )
    except Exception as exc:
        from app.utils.errors import flash_and_log

        db.session.rollback()
        flash_and_log(exc, location="registros.novo_aluno", hint="db")

    return redirect(url_for("registros.gerenciar_alunos"))


# =============================================================================
# EDIÇÃO
# =============================================================================

@bp.route("/aluno/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        abort(403)

    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    if request.method == "GET":
        chave_retorno = f"retorno_edicao_aluno_{aluno.id}"
        session.pop(chave_retorno, None)
        retorno = request.args.get("retorno")
        if retorno and retorno.startswith("/") and not retorno.startswith("//"):
            session[chave_retorno] = retorno

    if request.method == "POST":
        from app.utils.logica import formatar_nome_proprio

        try:
            # -----------------------------------------------------------------
            # 1. Colunas diretas em Aluno
            # -----------------------------------------------------------------
            aluno.nome = formatar_nome_proprio(request.form.get("nome"))
            aluno.nome_social = formatar_nome_proprio(
                request.form.get("nome_social")
            )
            nivel = request.form.get("nivel")
            if nivel is not None:
                aluno.nivel = nivel

            cpf_raw = request.form.get("cpf", "")
            if not _validar_cpf(cpf_raw):
                flash(
                    "CPF inválido. Informe somente os 11 dígitos numéricos "
                    "do CPF.",
                    "danger",
                )
                return redirect(url_for("registros.editar_aluno", id=aluno.id))
            aluno.cpf = _sanitizar_cpf(cpf_raw)

            aluno.rg = request.form.get("rg") or None
            aluno.whatsapp = request.form.get("whatsapp") or None
            aluno.email = request.form.get("email") or None

            nascimento = request.form.get("data_nascimento")
            if nascimento:
                aluno.data_nascimento = parse_date(nascimento)

            # Campos civis (Onda 3A) direto na tabela
            _aplicar_campos_civis(aluno, request.form)

            # -----------------------------------------------------------------
            # 2. SituacaoEscolar
            # -----------------------------------------------------------------
            _salvar_situacao_escolar(aluno)

            # -----------------------------------------------------------------
            # 3. Perfis (Onda 3B)
            # -----------------------------------------------------------------
            upsert_endereco(aluno, request.form)
            upsert_responsavel(aluno, request.form)
            upsert_perfil_socioeconomico(aluno, request.form)
            upsert_perfil_diversidade(aluno, request.form)

            # -----------------------------------------------------------------
            # 4. Foto
            # -----------------------------------------------------------------
            foto = request.files.get("foto")
            if foto and foto.filename:
                salvar_foto(foto, aluno)

            # -----------------------------------------------------------------
            # 5. Documentos entregues (JSONB)
            # -----------------------------------------------------------------
            _atualizar_documentos_entregues(aluno)

            db.session.commit()
            flash(
                f"Aluno {aluno.nome_social or aluno.nome} editado com sucesso!",
                "success",
            )
            retorno = session.pop(f"retorno_edicao_aluno_{aluno.id}", None)
            return redirect(retorno or url_for("registros.gerenciar_alunos"))
        except Exception as exc:
            from app.utils.errors import flash_and_log

            db.session.rollback()
            flash_and_log(exc, location="registros.editar_aluno", hint="db")

    return render_template(
        "alunos/editar.html",
        aluno=aluno,
        perfil=get_perfil_completo(aluno),
    )


# =============================================================================
# EXCLUSÃO / INATIVAÇÃO / DESENTURMAÇÃO
# =============================================================================

@bp.route("/aluno/excluir/<int:id>", methods=["POST"])
@login_required
def excluir_aluno(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO):
        abort(403)
    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())
    tem_presenca = (
        db.session.execute(select(Frequencia).where(Frequencia.aluno_id == id))
        .scalars()
        .first()
    )
    if tem_presenca:
        flash(
            "Proteção Sistêmica: Aluno blindado para Exclusão Física, pois "
            "possui Diário. Desative-o apenas.",
            "warning",
        )
        return redirect(url_for("registros.gerenciar_alunos"))
    try:
        db.session.delete(aluno)
        db.session.commit()
        flash(
            "Aluno purgado dos registros institucionais permanentemente.",
            "success",
        )
    except Exception:
        db.session.rollback()
        flash("O Storage DB recusou a exclusão profunda.", "danger")
    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/aluno/inativar/<int:id>", methods=["POST"])
@login_required
def inativar_aluno(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    """
    Inativa um aluno (soft delete).

    Onda 2A: o redirecionamento original tentava `aluno.turma_id`, atributo
    que não existe no modelo. Simplificado para voltar à listagem.
    """
    try:
        aluno = db.get_or_404(Aluno, id)
        assert_unidade_context(aluno.unidade_id, get_unidade_id())
        aluno.ativo = False
        db.session.commit()
        flash(f"Aluno {aluno.nome} inativado.", "info")
    except Exception:
        db.session.rollback()
        flash("Erro ao inativar aluno.", "danger")
    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/turma/desenturmar/<int:id>", methods=["POST"])
@login_required
def desenturmar_alunos(id):
    if current_user.role not in (UserRole.PEDAGOGICO, UserRole.ADMIN):
        abort(403)

    aluno = db.get_or_404(Aluno, id)
    turma_id = request.args.get("turma_id", type=int)
    turma = db.session.get(Turma, turma_id) if turma_id else None
    if turma_id and not turma:
        flash("Turma inválida para remoção.", "danger")
        return redirect(url_for("registros.gerenciar_alunos"))

    assert_unidade_context(aluno.unidade_id, get_unidade_id())
    if turma:
        assert_unidade_context(turma.unidade_id, get_unidade_id())
        inscricao = Inscricao.query.filter_by(
            aluno_id=aluno.id, turma_id=turma.id, ativo=True
        ).first()
        if not inscricao:
            flash("Aluno não está enturmado nesta turma.", "warning")
            return redirect(url_for("registros.ver_turma", id=turma.id))

        frequencia_existente = Frequencia.query.filter(
            Frequencia.aluno_id == aluno.id,
            Frequencia.turma_id == turma.id,
            Frequencia.conceito.isnot(None),
            Frequencia.conceito != "",
        ).first()
        try:
            if frequencia_existente:
                inscricao.ativo = False
                db.session.commit()
                flash(
                    f"Aluno {aluno.nome} inativado na turma {turma.nome}.",
                    "info",
                )
            else:
                db.session.delete(inscricao)
                db.session.commit()
                flash(
                    f"Aluno {aluno.nome} removido da turma {turma.nome}.",
                    "success",
                )
        except Exception:
            db.session.rollback()
            flash(
                "Falha ao processar a associação do aluno com a turma.",
                "danger",
            )
        return redirect(url_for("registros.ver_turma", id=turma.id))

    flash("Turma não informada para remoção.", "warning")
    return redirect(url_for("registros.gerenciar_alunos"))


# =============================================================================
# HISTÓRICO / IMPRESSÃO / TRANSFERÊNCIA
# =============================================================================

@bp.route("/aluno/<int:aluno_id>/historico")
@login_required
def historico_aluno(aluno_id):
    from app.models import ConselhoClasse

    allowed_roles = {
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
    }
    if current_user.role not in allowed_roles:
        if current_user.role == UserRole.PROFESSOR:
            tem_turma_do_professor = (
                Inscricao.query.join(Turma, Inscricao.turma_id == Turma.id)
                .filter(
                    Inscricao.aluno_id == aluno_id,
                    Inscricao.ativo.is_(True),
                    Turma.professor_id == current_user.id,
                )
                .first()
            )
            if not tem_turma_do_professor:
                abort(403)
        else:
            abort(403)

    unidade_id = get_unidade_id()
    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, unidade_id)

    inscricoes = Inscricao.query.filter_by(aluno_id=aluno_id).all()
    dados = []
    for insc in inscricoes:
        turma = insc.turma
        if not turma:
            continue

        freqs = Frequencia.query.filter_by(
            aluno_id=aluno_id, turma_id=turma.id
        ).all()
        estatisticas = calcular_estatisticas_frequencia(
            freq.conceito for freq in freqs
        )

        def get_conselho(etapa):
            return ConselhoClasse.query.filter_by(
                turma_id=turma.id, aluno_id=aluno_id, etapa=etapa
            ).first()

        c_inicial = get_conselho("INICIAL")
        c_percurso = get_conselho("PERCURSO")
        c_final = get_conselho("FINAL")

        # Onda 2A: turma.hora_inicio/hora_fim são TIME, data_* são DATE.
        horario = (
            f"{turma.hora_inicio.strftime('%H:%M') if turma.hora_inicio else '--:--'}"
            f" às "
            f"{turma.hora_fim.strftime('%H:%M') if turma.hora_fim else '--:--'}"
        )

        dados.append(
            {
                "turma": turma.nome,
                "curso": turma.curso.nome if turma.curso else "—",
                "programa": turma.programa or "—",
                "professor": turma.professor.name if turma.professor else "—",
                "periodo": (
                    turma.periodo_letivo.nome if turma.periodo_letivo else "—"
                ),
                "dias": turma.dias_semana or "—",
                "horario": horario,
                "data_inicio": (
                    turma.data_inicio.strftime("%d/%m/%Y")
                    if turma.data_inicio else "—"
                ),
                "data_fim": (
                    turma.data_fim.strftime("%d/%m/%Y")
                    if turma.data_fim else "—"
                ),
                "nivel": insc.nivel or aluno.nivel or "—",
                "total_aulas": estatisticas["total"],
                "presencas": estatisticas["presencas"],
                "faltas": estatisticas["faltas"],
                "justificadas": estatisticas["justificadas"],
                "pct_presenca": estatisticas["presenca_percentual"],
                "status_inicial": (
                    c_inicial.situacao_final if c_inicial else "—"
                ),
                "status_percurso": (
                    c_percurso.situacao_final if c_percurso else "—"
                ),
                "situacao_final": (
                    c_final.situacao_final if c_final else "—"
                ),
                "ativo": insc.ativo,
            }
        )

    dados.sort(key=lambda item: (not item["ativo"], item["periodo"]))
    data_cadastro = (
        aluno.created_at.strftime("%d/%m/%Y")
        if aluno.created_at else "Não disponível"
    )
    return render_template(
        "alunos/historico.html",
        aluno=aluno,
        dados=dados,
        data_cadastro=data_cadastro,
    )


@bp.route("/aluno/imprimir/<int:id>")
@login_required
def imprimir_aluno(id):
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        abort(403)

    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    return render_template(
        "alunos/impressao.html",
        aluno=aluno,
        perfil=get_perfil_completo(aluno),
        data_matricula=aluno.created_at or datetime.now(),
    )


@bp.route("/aluno/transferir/<int:aluno_id>", methods=["GET", "POST"])
@login_required
def transferir_aluno(aluno_id):
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
    ):
        abort(403)

    aluno = db.get_or_404(Aluno, aluno_id)
    unidade_id = get_unidade_id()
    assert_unidade_context(aluno.unidade_id, unidade_id)

    turma_origem_id = request.args.get("turma_origem_id", type=int)
    if not turma_origem_id and request.method == "POST":
        turma_origem_id = request.form.get("turma_origem_id", type=int)

    if not turma_origem_id:
        flash("Turma de origem não informada.", "danger")
        return redirect(url_for("registros.gerenciar_alunos"))

    inscricao_origem = Inscricao.query.filter_by(
        aluno_id=aluno.id, turma_id=turma_origem_id, ativo=True
    ).first()
    if not inscricao_origem:
        flash(
            "Aluno não está ativo na turma de origem informada.", "danger"
        )
        return redirect(url_for("registros.gerenciar_alunos"))

    # --- GET: formulário ---
    if request.method == "GET":
        query = Turma.query.filter(
            Turma.ativo == True, Turma.id != turma_origem_id
        )
        if unidade_id is not None:
            query = query.filter(Turma.unidade_id == unidade_id)
        turmas_destino = query.order_by(Turma.nome).all()

        if not turmas_destino:
            flash(
                "Não há outras turmas ativas disponíveis para transferência.",
                "warning",
            )

        return render_template(
            "alunos/transferir.html",
            aluno=aluno,
            turma_origem=inscricao_origem.turma,
            turmas_destino=turmas_destino,
            hoje=datetime.now().date(),
        )

    # --- POST: processa a transferência ---
    turma_destino_id = request.form.get("turma_destino_id", type=int)
    data_transferencia_str = request.form.get("data_transferencia")
    observacoes = request.form.get("observacoes", "").strip()

    if not turma_destino_id or not data_transferencia_str:
        flash(
            "Selecione a turma de destino e a data da transferência.",
            "warning",
        )
        return redirect(
            url_for(
                "registros.transferir_aluno",
                aluno_id=aluno_id,
                turma_origem_id=turma_origem_id,
            )
        )

    try:
        data_transferencia = datetime.strptime(
            data_transferencia_str, "%Y-%m-%d"
        ).date()
    except ValueError:
        flash("Data inválida.", "danger")
        return redirect(
            url_for(
                "registros.transferir_aluno",
                aluno_id=aluno_id,
                turma_origem_id=turma_origem_id,
            )
        )

    turma_destino = db.get_or_404(Turma, turma_destino_id)

    # Onda 2A: turma_destino.data_inicio já é `date`.
    if turma_destino.data_inicio and data_transferencia < turma_destino.data_inicio:
        flash(
            f"A data de transferência não pode ser anterior ao início da "
            f"turma ({turma_destino.data_inicio.strftime('%d/%m/%Y')}).",
            "warning",
        )
        return redirect(
            url_for(
                "registros.transferir_aluno",
                aluno_id=aluno_id,
                turma_origem_id=turma_origem_id,
            )
        )

    try:
        inscricao_origem.ativo = False
        inscricao_origem.data_desativacao = datetime.combine(
            data_transferencia - timedelta(days=1),
            datetime.min.time(),
        )
        inscricao_origem.motivo_desativacao = "TRANSFERENCIA"

        nova_inscricao = Inscricao(
            aluno_id=aluno.id,
            turma_id=turma_destino_id,
            nivel=inscricao_origem.nivel,
            data_inicio=data_transferencia,
            ativo=True,
            data_desativacao=None,
            motivo_desativacao=None,
        )
        db.session.add(nova_inscricao)

        from app.models import Transferencia

        transferencia = Transferencia(
            aluno_id=aluno.id,
            turma_origem_id=inscricao_origem.turma_id,
            turma_destino_id=turma_destino_id,
            data_transferencia=datetime.combine(
                data_transferencia, datetime.min.time()
            ),
            observacoes=observacoes,
            unidade_id=unidade_id,
        )
        db.session.add(transferencia)

        db.session.commit()
        flash(
            f"Aluno {aluno.nome} transferido para a turma "
            f"{turma_destino.nome} com sucesso!",
            "success",
        )
    except Exception as e:
        from app.utils.errors import flash_and_log

        db.session.rollback()
        flash_and_log(e, location="registros.transferir_aluno", hint="db")

    return redirect(url_for("registros.ver_turma", id=turma_origem_id))


# =============================================================================
# DOWNLOADS E VISUALIZAÇÃO SEGURA DE ARQUIVOS (SEC-01)
# =============================================================================

@bp.route("/aluno/<int:aluno_id>/documento/<doc_id>")
@login_required
def ver_documento_aluno(aluno_id: int, doc_id: str):
    """Serve documentos e laudos do aluno de forma segura e autenticada."""
    allowed_roles = (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
        UserRole.SERVICO_SOCIAL,
    )
    if current_user.role not in allowed_roles:
        abort(403)

    if doc_id not in DOC_IDS:
        abort(404)

    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    filename = secure_filename(f"{doc_id}.pdf")
    candidate_folders = []
    if aluno.matricula:
        candidate_folders.append(aluno.matricula.replace(".", "_"))
    candidate_folders.append(f"aluno_{aluno.id}")
    candidate_folders.append("sem_matricula")

    upload_root = _get_upload_root()
    for folder in candidate_folders:
        dir_path = upload_root / "documentos" / folder
        target = dir_path / filename
        if target.is_file():
            return send_from_directory(
                str(dir_path),
                filename,
                mimetype="application/pdf",
                as_attachment=False,
            )

    abort(404)


@bp.route("/aluno/<int:aluno_id>/foto")
@login_required
def foto_aluno(aluno_id: int):
    """Serve a foto de perfil do aluno autenticada e protegida."""
    aluno = db.get_or_404(Aluno, aluno_id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    if aluno.foto_path:
        filename = secure_filename(aluno.foto_path)
        upload_root = _get_upload_root()

        foto_dir = upload_root / "fotos"
        if (foto_dir / filename).is_file():
            return send_from_directory(str(foto_dir), filename)

    from app.services.informacao_padrao import get_informacao_padrao_context

    info = get_informacao_padrao_context()
    default_url = info.get("foto_default_aluno_url", "/static/img/default.png")
    return redirect(default_url)
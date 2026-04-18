from datetime import datetime

from flask import abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from app.database import db
from app.models import Aluno, Frequencia, Inscricao, Turma
from app.utils.logica import get_unidade_id
from . import bp
from .shared import assert_unidade_context, salvar_documento, salvar_foto


@bp.route("/aluno/<int:aluno_id>/atualizar-nivel", methods=["POST"])
@login_required
def atualizar_nivel_aluno(aluno_id):
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
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
        db.session.rollback()
        flash(f"Falha ao atualizar o nível do aluno: {exc}", "danger")

    if turma_id:
        return redirect(url_for("registros.ver_turma", id=turma_id))
    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/alunos")
@login_required
def gerenciar_alunos():
    if current_user.role not in ["admin", "pedagogico", "secretaria", "servico_social"]:
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
                Aluno.cpf.ilike(f"%{search_cpf}%"), Aluno.cpf.ilike(f"%{cpf_limpo}%")
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
    items = alunos_lista[start : start + per_page]

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
        total_enturmados=enturm_q.filter(Aluno.turmas.any(Turma.ativo == True)).count(),
        search_nome=search_nome,
        search_matr=search_matr,
        search_cpf=search_cpf,
        search_idade_min=search_idade_min,
        search_idade_max=search_idade_max,
        is_readonly=current_user.role == "servico_social",
    )


@bp.route("/aluno/novo", methods=["GET", "POST"])
@login_required
def novo_aluno():
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)
    if request.method == "GET":
        return render_template("aluno_novo.html")

    nome = request.form.get("nome")
    if not nome:
        flash("O Campo 'Nome' não deve ser vazio no momento do Cadastro.", "warning")
        return redirect(url_for("registros.gerenciar_alunos"))

    try:
        nascimento = request.form.get("data_nascimento")
        data_nascimento = (
            datetime.strptime(nascimento, "%Y-%m-%d").date() if nascimento else None
        )
        novo = Aluno(
            nome=nome,
            nome_social=request.form.get("nome_social"),
            nivel=request.form.get("nivel"),
            ativo=True,
            unidade_id=get_unidade_id(),
            cpf=request.form.get("cpf"),
            rg=request.form.get("rg"),
            whatsapp=request.form.get("whatsapp"),
            email=request.form.get("email"),
            data_nascimento=data_nascimento,
            created_by_id=current_user.id,
            created_by_name=current_user.name,
        )

        novo.identificacao_json = {
            "nome_social": request.form.get("nome_social"),
            "orgao_rg": request.form.get("orgao_rg"),
            "nacionalidade": request.form.get("nacionalidade"),
            "natural_uf": request.form.get("natural_uf"),
            "natural_cidade": request.form.get("natural_cidade"),
            "nome_mae": request.form.get("nome_mae"),
            "cpf_mae": request.form.get("cpf_mae"),
            "nome_pai": request.form.get("nome_pai"),
            "cpf_pai": request.form.get("cpf_pai"),
            "responsavel_tipo": request.form.get("responsavel_tipo"),
            "responsavel_nome": request.form.get("responsavel_nome"),
            "responsavel_cpf": request.form.get("responsavel_cpf"),
            "telefone_resp": request.form.get("telefone_resp"),
            "endereco": {
                "cep": request.form.get("cep"),
                "rua": request.form.get("rua"),
                "numero": request.form.get("numero"),
                "bairro": request.form.get("bairro"),
                "cidade": request.form.get("cidade"),
                "uf": request.form.get("uf"),
            },
        }
        novo.socioeconomico_json = {
            "renda_familiar": request.form.get("renda_familiar"),
            "residente_maior_renda": request.form.get("residente_maior_renda"),
            "pessoas_residencia": request.form.get("pessoas_residencia"),
            "ocupacao": request.form.get("ocupacao"),
            "beneficio_social_status": request.form.get("beneficio_social_status"),
            "beneficio_social_nome": request.form.get("beneficio_social_nome"),
            "meio_transporte": request.form.get("meio_transporte"),
        }
        novo.diversidade_json = {
            "genero": request.form.get("genero"),
            "raca_cor": request.form.get("raca_cor"),
            "saude_laudo": bool(request.form.get("saude_laudo")),
            "saude_medicacao": request.form.get("saude_medicacao"),
            "saude_medicamento_nome": request.form.get("saude_medicamento_nome"),
            "saude_observacoes": request.form.get("saude_observacoes"),
            "autorizacao_imagem": bool(request.form.get("autorizacao_imagem")),
        }
        ids_turmas = request.form.getlist("turmas_selecionadas")
        if ids_turmas:
            novo.turmas = Turma.query.filter(Turma.id.in_(ids_turmas)).all()

        db.session.add(novo)
        db.session.flush()

        foto = request.files.get("foto")
        if foto and foto.filename:
            salvar_foto(foto, novo)

        docs = novo.escolaridade_json or {}
        entregues = docs.get("doc_entregue", {})
        for doc_id in [
            "doc_aluno",
            "doc_residencia",
            "doc_declaracao",
            "doc_atestado",
            "doc_termo",
            "doc_responsavel",
            "doc_laudo",
        ]:
            documento = request.files.get(doc_id)
            if (
                documento
                and documento.filename
                and salvar_documento(documento, novo, doc_id)
            ):
                entregues[doc_id] = True
        docs["doc_entregue"] = entregues
        novo.escolaridade_json = docs

        db.session.commit()
        flash(
            f"Aluno {novo.nome_social or novo.nome} cadastrado com sucesso!", "success"
        )
    except Exception as exc:
        db.session.rollback()
        flash(f"Erro em cascata local a nível de Banco: {exc}", "danger")

    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/aluno/editar/<int:id>", methods=["GET", "POST"])
@login_required
def editar_aluno(id):
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())

    if request.method == "POST":
        try:
            aluno.nome = request.form.get("nome")
            aluno.nome_social = request.form.get("nome_social")
            nivel = request.form.get("nivel")
            if nivel is not None:
                aluno.nivel = nivel
            aluno.cpf = request.form.get("cpf")
            aluno.rg = request.form.get("rg")
            aluno.whatsapp = request.form.get("whatsapp")
            aluno.email = request.form.get("email")

            nascimento = request.form.get("data_nascimento")
            if nascimento:
                aluno.data_nascimento = datetime.strptime(nascimento, "%Y-%m-%d").date()

            aluno.identificacao_json = {
                "nome_social": request.form.get("nome_social"),
                "orgao_rg": request.form.get("orgao_rg"),
                "nacionalidade": request.form.get("nacionalidade"),
                "natural_uf": request.form.get("natural_uf"),
                "natural_cidade": request.form.get("natural_cidade"),
                "nome_mae": request.form.get("nome_mae"),
                "cpf_mae": request.form.get("cpf_mae"),
                "nome_pai": request.form.get("nome_pai"),
                "cpf_pai": request.form.get("cpf_pai"),
                "responsavel_tipo": request.form.get("responsavel_tipo"),
                "responsavel_nome": request.form.get("responsavel_nome"),
                "responsavel_cpf": request.form.get("responsavel_cpf"),
                "telefone_resp": request.form.get("telefone_resp"),
                "endereco": {
                    "cep": request.form.get("cep"),
                    "rua": request.form.get("rua"),
                    "numero": request.form.get("numero"),
                    "bairro": request.form.get("bairro"),
                    "cidade": request.form.get("cidade"),
                    "uf": request.form.get("uf"),
                },
            }
            aluno.socioeconomico_json = {
                "renda_familiar": request.form.get("renda_familiar"),
                "residente_maior_renda": request.form.get("residente_maior_renda"),
                "pessoas_residencia": request.form.get("pessoas_residencia"),
                "ocupacao": request.form.get("ocupacao"),
                "beneficio_social_status": request.form.get("beneficio_social_status"),
                "beneficio_social_nome": request.form.get("beneficio_social_nome"),
                "meio_transporte": request.form.get("meio_transporte"),
            }
            aluno.diversidade_json = {
                "genero": request.form.get("genero"),
                "raca_cor": request.form.get("raca_cor"),
                "saude_laudo": bool(request.form.get("saude_laudo")),
                "saude_medicacao": request.form.get("saude_medicacao"),
                "saude_medicamento_nome": request.form.get("saude_medicamento_nome"),
                "saude_observacoes": request.form.get("saude_observacoes"),
                "autorizacao_imagem": bool(request.form.get("autorizacao_imagem")),
            }

            foto = request.files.get("foto")
            if foto and foto.filename:
                salvar_foto(foto, aluno)

            docs = aluno.escolaridade_json or {}
            entregues = docs.get("doc_entregue", {})
            for doc_id in [
                "doc_aluno",
                "doc_residencia",
                "doc_declaracao",
                "doc_atestado",
                "doc_termo",
                "doc_responsavel",
                "doc_laudo",
            ]:
                documento = request.files.get(doc_id)
                if (
                    documento
                    and documento.filename
                    and salvar_documento(documento, aluno, doc_id)
                ):
                    entregues[doc_id] = True
            docs["doc_entregue"] = entregues
            aluno.escolaridade_json = docs

            db.session.commit()
            flash(
                f"Aluno {aluno.nome_social or aluno.nome} editado com sucesso!",
                "success",
            )
            return redirect(url_for("registros.gerenciar_alunos"))
        except Exception as exc:
            db.session.rollback()
            flash(f"Atenção, falha de integridade referencial: {exc}", "danger")

    return render_template("alunos/editar.html", aluno=aluno)


@bp.route("/aluno/excluir/<int:id>")
@login_required
def excluir_aluno(id):
    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())
    tem_presenca = (
        db.session.execute(select(Frequencia).where(Frequencia.aluno_id == id))
        .scalars()
        .first()
    )
    if tem_presenca:
        flash(
            "Proteção Sistêmica: Aluno blindado para Exclusão Física, pois possui Diário. Desative-o apenas.",
            "warning",
        )
        return redirect(url_for("registros.gerenciar_alunos"))
    try:
        db.session.delete(aluno)
        db.session.commit()
        flash("Aluno purgado dos registros institucionais permanentemente.", "success")
    except Exception:
        db.session.rollback()
        flash("O Storage DB recusou a exclusão profunda.", "danger")
    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/aluno/inativar/<int:id>")
@login_required
def inativar_aluno(id):
    try:
        aluno = db.get_or_404(Aluno, id)
        assert_unidade_context(aluno.unidade_id, get_unidade_id())
        aluno.ativo = False
        db.session.commit()
    except Exception:
        db.session.rollback()
    try:
        return redirect(url_for("registros.ver_turma", id=aluno.turma_id))
    except Exception:
        return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/turma/desenturmar/<int:id>")
@login_required
def desenturmar_alunos(id):
    if current_user.role not in ["pedagogico", "admin"]:
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
                    f"Aluno {aluno.nome} inativado na turma {turma.nome} devido à frequência registrada.",
                    "info",
                )
            else:
                db.session.delete(inscricao)
                db.session.commit()
                flash(f"Aluno {aluno.nome} removido da turma {turma.nome}.", "success")
        except Exception:
            db.session.rollback()
            flash("Falha ao processar a associação do aluno com a turma.", "danger")
        return redirect(url_for("registros.ver_turma", id=turma.id))

    flash("Turma não informada para remoção.", "warning")
    return redirect(url_for("registros.gerenciar_alunos"))


@bp.route("/aluno/<int:aluno_id>/historico")
@login_required
def historico_aluno(aluno_id):
    from app.models import ConselhoClasse

    unidade_id = get_unidade_id()
    aluno = db.get_or_404(Aluno, aluno_id)
    if unidade_id and aluno.unidade_id and aluno.unidade_id != unidade_id:
        abort(403)

    inscricoes = Inscricao.query.filter_by(aluno_id=aluno_id).all()
    dados = []
    for insc in inscricoes:
        turma = insc.turma
        if not turma:
            continue

        freqs = Frequencia.query.filter_by(aluno_id=aluno_id, turma_id=turma.id).all()
        total = len(freqs)
        presentes = sum(1 for freq in freqs if freq.conceito in ("A", "B", "C", "D"))
        faltas = sum(1 for freq in freqs if freq.conceito == "F")
        justif = sum(1 for freq in freqs if freq.conceito == "J")
        contaveis = presentes + faltas
        pct_presenca = round(presentes / contaveis * 100, 1) if contaveis else 0

        def get_conselho(etapa):
            return ConselhoClasse.query.filter_by(
                turma_id=turma.id, aluno_id=aluno_id, etapa=etapa
            ).first()

        c_inicial = get_conselho("INICIAL")
        c_percurso = get_conselho("PERCURSO")
        c_final = get_conselho("FINAL")
        dados.append(
            {
                "turma": turma.nome,
                "curso": turma.curso.nome if turma.curso else "—",
                "programa": turma.programa or "—",
                "professor": turma.professor.name if turma.professor else "—",
                "periodo": turma.periodo_letivo.nome if turma.periodo_letivo else "—",
                "dias": turma.dias_semana or "—",
                "horario": f"{turma.hora_inicio or '--:--'} às {turma.hora_fim or '--:--'}",
                "data_inicio": turma.data_inicio or "—",
                "data_fim": turma.data_fim or "—",
                "nivel": insc.nivel or aluno.nivel or "—",
                "total_aulas": total,
                "presencas": presentes,
                "faltas": faltas,
                "justificadas": justif,
                "pct_presenca": pct_presenca,
                "status_inicial": c_inicial.situacao_final if c_inicial else "—",
                "status_percurso": c_percurso.situacao_final if c_percurso else "—",
                "situacao_final": c_final.situacao_final if c_final else "—",
                "ativo": insc.ativo,
            }
        )

    dados.sort(key=lambda item: (not item["ativo"], item["periodo"]))
    data_cadastro = (
        aluno.created_at.strftime("%d/%m/%Y") if aluno.created_at else "Não disponível"
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
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    aluno = db.get_or_404(Aluno, id)
    assert_unidade_context(aluno.unidade_id, get_unidade_id())
    return render_template(
        "alunos/impressao.html",
        aluno=aluno,
        data_matricula=aluno.created_at or datetime.now(),
    )


@bp.route("/aluno/transferir/<int:aluno_id>")
@login_required
def transferir_aluno(aluno_id):
    flash("Transferência de Aluno em desenvolvimento.", "info")
    return redirect(url_for("registros.gerenciar_alunos"))

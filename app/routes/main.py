from flask import (
    Blueprint,
    render_template,
    request,
    abort,
    send_file,
    redirect,
    url_for,
    flash,
)
from flask_login import login_required, current_user
from sqlalchemy import select, func
from app.database import db
from datetime import date, datetime
from app.models import (
    Turma,
    Aluno,
    Frequencia,
    Unidade,
    User,
    ConfiguracaoSistema,
    AgendaServicoSocial,
)
from app.utils.logica import (
    calcular_frequencias_relatorio,
    calcular_estatisticas_idade,
    calcular_metricas_conselho,
    get_unidade_id,
)
import pandas as pd
from io import BytesIO

bp = Blueprint("main", __name__)


# ---------------------------------------------------------------------------
# PÚBLICO
# ---------------------------------------------------------------------------
@bp.route("/")
def home():
    """Portal de Entrada do Sistema."""
    return render_template("login.html")


# ---------------------------------------------------------------------------
# DASHBOARD ADMINISTRADOR, PEDAGÓGICO
# ---------------------------------------------------------------------------
@bp.route("/dashboard")
@login_required
def dashboard():
    """
    Controlador central de visão.
    Dependendo do papel (Role Based Access Control), renderiza métricas distintas (Admin vs Professor).
    """
    # 1. Trava anti-vazamento de sistema para não ativados
    if current_user.role == "pendente":
        return redirect(url_for("auth.aguardando_aprovacao"))

    # 2. Visão Global (Gerencial)
    if current_user.role in ["admin", "pedagogico"]:
        # Secretaria vai direto para o dashboard da secretaria
        pass

    if current_user.role == "secretaria":
        return redirect(url_for("main.dashboard_secretaria"))

    if current_user.role in ["admin", "pedagogico"]:
        try:
            unidade_id = get_unidade_id()
            if unidade_id:
                total_turmas = Turma.query.filter_by(
                    ativo=True, unidade_id=unidade_id
                ).count()
                total_alunos = Aluno.query.filter_by(
                    ativo=True, unidade_id=unidade_id
                ).count()
                total_professores = User.query.filter_by(
                    role="professor", unidade_id=unidade_id
                ).count()
            else:
                total_turmas = Turma.query.filter_by(ativo=True).count()
                total_alunos = Aluno.query.filter_by(ativo=True).count()
                total_professores = (
                    db.session.query(func.count(func.distinct(Turma.professor_id)))
                    .filter(Turma.ativo == True)
                    .scalar()
                    or 0
                )

            return render_template(
                "dashboard.html",
                total_turmas=total_turmas,
                total_alunos=total_alunos,
                total_professores=total_professores,
            )
        except Exception as e:
            flash(f"Erro ao computar dados para o dashboard gerencial: {e}", "danger")
            return render_template(
                "dashboard.html",
                total_turmas=0,
                total_alunos=0,
                total_professores=0,
                show_excel=False,
            )

    # 3. Visão Operacional (Professor)
    if current_user.role == "professor":
        try:
            minhas_turmas = Turma.query.filter_by(
                professor_id=current_user.id, ativo=True
            ).all()

            ids_turmas = [t.id for t in minhas_turmas]

            total_meus_alunos = 0
            if ids_turmas:
                total_meus_alunos = (
                    Aluno.query.join(Aluno.turmas)
                    .filter(Turma.id.in_(ids_turmas), Aluno.ativo == True)
                    .distinct()
                    .count()
                )

            from app.models import DiaBloqueado, Inscricao
            from app.utils.logica import gerar_datas

            hoje = date.today()
            periodo_ids = {
                t.periodo_letivo_id for t in minhas_turmas if t.periodo_letivo_id
            }
            dias_bloqueados = []
            if periodo_ids:
                dias_bloqueados = (
                    DiaBloqueado.query.filter(
                        DiaBloqueado.periodo_letivo_id.in_(periodo_ids),
                        DiaBloqueado.data >= hoje,
                    )
                    .order_by(DiaBloqueado.data)
                    .all()
                )

            # ── Aulas com frequência pendente ──────────────────────────────
            # Para cada turma, verifica datas passadas onde algum aluno ativo
            # não tem conceito lançado (A, B, C, D, F ou J).
            aulas_pendentes = []
            for turma in minhas_turmas:
                # Dias bloqueados do período desta turma
                blocked = set()
                if turma.periodo_letivo_id:
                    blocked = {
                        d.data.strftime('%Y-%m-%d')
                        for d in DiaBloqueado.query.filter_by(
                            periodo_letivo_id=turma.periodo_letivo_id
                        ).all()
                    }

                datas_aula = gerar_datas(turma, incluir_futuro=False,
                                         blocked_dates=blocked)

                # Alunos ativos desta turma
                alunos_turma = (
                    Aluno.query.join(Inscricao)
                    .filter(
                        Inscricao.turma_id == turma.id,
                        Inscricao.ativo == True,
                        Aluno.ativo == True,
                    )
                    .all()
                )
                if not alunos_turma:
                    continue

                aluno_ids = [a.id for a in alunos_turma]

                for data_str in datas_aula:
                    # Quantos alunos têm conceito lançado nesta data/turma
                    lancados = Frequencia.query.filter(
                        Frequencia.turma_id == turma.id,
                        Frequencia.data == data_str,
                        Frequencia.aluno_id.in_(aluno_ids),
                        Frequencia.conceito.isnot(None),
                        Frequencia.conceito != '',
                    ).count()

                    if lancados < len(aluno_ids):
                        faltando = len(aluno_ids) - lancados
                        aulas_pendentes.append({
                            'turma':    turma,
                            'data':     data_str,
                            'faltando': faltando,
                            'total':    len(aluno_ids),
                        })

            # Ordena por data mais antiga primeiro
            aulas_pendentes.sort(key=lambda x: x['data'])

            return render_template(
                "dashboard_professor.html",
                turmas=minhas_turmas,
                total_alunos=total_meus_alunos,
                dias_bloqueados=dias_bloqueados,
                aulas_pendentes=aulas_pendentes,
            )
        except Exception as e:
            flash("Erro ao processar as turmas do professor.", "warning")
            return render_template(
                "dashboard_professor.html",
                turmas=[],
                total_alunos=0,
                dias_bloqueados=[],
                aulas_pendentes=[],
            )

    # 4. Visão Serviço Social
    if current_user.role == 'servico_social':
        cat_filtro = request.args.get('categoria')
        total_alunos = total_turmas = 0
        ultimos = []
        try:
            unidade_id = get_unidade_id()
            q_alunos = Aluno.query.filter_by(ativo=True)
            if unidade_id:
                q_alunos = q_alunos.filter_by(unidade_id=unidade_id)
            total_alunos = q_alunos.count()

            q_turmas = Turma.query.filter_by(ativo=True)
            if unidade_id:
                q_turmas = q_turmas.filter_by(unidade_id=unidade_id)
            total_turmas = q_turmas.count()

            from app.models import AgendaServicoSocial
            query = AgendaServicoSocial.query
            if cat_filtro and cat_filtro != 'Limpar Filtros':
                query = query.filter_by(categoria=cat_filtro)
            ultimos = query.order_by(AgendaServicoSocial.id.desc()).limit(10).all()

        except Exception as e:
            flash("Erro ao carregar dados do painel.", "warning")

        return render_template(
            'dashboard_servico_social.html',
            total_alunos=total_alunos,
            total_turmas=total_turmas,
            ano_atual=date.today().year,
            ultimos_agendamentos=ultimos,
            categoria_ativa=cat_filtro,
        )

    # Fallback — role não mapeado
    abort(403)

# ---------------------------------------------------------------------------
# DASHBOARD SECRETARIA
# ---------------------------------------------------------------------------
@bp.route('/dashboard/secretaria')
@login_required
def dashboard_secretaria():
    """Dashboard da Secretaria — acessível por secretaria, admin, pedagogico, gerencia e servico_social."""
    if current_user.role not in ['admin', 'pedagogico', 'secretaria', 'gerencia', 'servico_social']:
        abort(403)

    from flask import session
    from app.models import DiaBloqueado, Inscricao
    from app.utils.logica import gerar_datas

    unidade_id = get_unidade_id()

    # ── Totais ──
    q_alunos = Aluno.query.filter_by(ativo=True)
    q_turmas = Turma.query.filter_by(ativo=True)
    if unidade_id:
        q_alunos = q_alunos.filter_by(unidade_id=unidade_id)
        q_turmas = q_turmas.filter_by(unidade_id=unidade_id)

    total_alunos = q_alunos.count()
    total_turmas = q_turmas.count()

    # ── Próximos dias sem aula ──
    hoje = date.today()
    from app.models import PeriodoLetivo
    periodo_ids_ativos = [
        p.id for p in PeriodoLetivo.query.filter_by(ativo=True).all()
        if not unidade_id or p.unidade_id == unidade_id
    ]
    proximas_datas_vagas = []
    if periodo_ids_ativos:
        proximas_datas_vagas = (
            DiaBloqueado.query
            .filter(
                DiaBloqueado.periodo_letivo_id.in_(periodo_ids_ativos),
                DiaBloqueado.data >= hoje,
            )
            .order_by(DiaBloqueado.data)
            .limit(5)
            .all()
        )
    total_dias_sem_aula = len(proximas_datas_vagas)

    # ── Frequências pendentes (turmas ativas da unidade) ──
    turmas_ativas = q_turmas.all()
    total_pendencias_frequencia = 0
    for turma in turmas_ativas:
        blocked = set()
        if turma.periodo_letivo_id:
            blocked = {
                d.data.strftime('%Y-%m-%d')
                for d in DiaBloqueado.query.filter_by(
                    periodo_letivo_id=turma.periodo_letivo_id
                ).all()
            }
        datas_aula = gerar_datas(turma, incluir_futuro=False, blocked_dates=blocked)
        aluno_ids = [
            a.id for a in Aluno.query.join(Inscricao).filter(
                Inscricao.turma_id == turma.id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            ).all()
        ]
        if not aluno_ids:
            continue
        for data_str in datas_aula:
            lancados = Frequencia.query.filter(
                Frequencia.turma_id == turma.id,
                Frequencia.data == data_str,
                Frequencia.aluno_id.in_(aluno_ids),
                Frequencia.conceito.isnot(None),
                Frequencia.conceito != '',
            ).count()
            if lancados < len(aluno_ids):
                total_pendencias_frequencia += 1

    # ── Agendamentos do Serviço Social (se modelo existir) ──
    agendamentos_ss = []
    try:
        agendamentos_ss = (
            AgendaServicoSocial.query
            .order_by(AgendaServicoSocial.id.desc())
            .limit(5)
            .all()
        )
    except Exception:
        pass

    # Contexto de unidade para exibição
    unidade_nome = 'Visão Global'
    if unidade_id:
        from app.models import Unidade
        u = Unidade.query.get(unidade_id)
        if u:
            unidade_nome = u.nome

    return render_template(
        'dashboard_secretaria.html',
        total_alunos=total_alunos,
        total_turmas=total_turmas,
        total_pendencias_frequencia=total_pendencias_frequencia,
        total_dias_sem_aula=total_dias_sem_aula,
        proximas_datas_vagas=proximas_datas_vagas,
        agendamentos_ss=agendamentos_ss,
        unidade_contexto=unidade_nome,
    )

# ---------------------------------------------------------------------------
# RELATÓRIOS ANALÍTICOS
# ---------------------------------------------------------------------------
@bp.route("/relatorios")
@login_required
def relatorio_geral():
    """Controlador que invoca os serviços analíticos agregados para tela do Gestor."""
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    try:
        unidade_id = get_unidade_id()
        turmas_query = Turma.query.filter_by(ativo=True)
        if unidade_id:
            turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
        todas_as_turmas = turmas_query.all()

        # Chama a lógica pesada em camada inferior (logica.py)
        estatisticas_idade = calcular_estatisticas_idade(unidade_id=unidade_id)
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(
            todas_as_turmas, unidade_id=unidade_id
        )
        metricas = calcular_metricas_conselho(unidade_id=unidade_id)

        total_alunos_query = Aluno.query.filter_by(ativo=True)
        total_professores_query = User.query.filter_by(role="professor")
        if unidade_id:
            total_alunos_query = total_alunos_query.filter_by(unidade_id=unidade_id)
            total_professores_query = total_professores_query.filter_by(
                unidade_id=unidade_id
            )

        # Distribuição por sexo via diversidade_json
        total_masculino = total_feminino = total_outro = 0
        MASC = {"masculino", "homem", "masc", "m"}
        FEM = {"feminino", "mulher", "fem", "f"}
        for aluno in total_alunos_query.all():
            genero = (aluno.diversidade_json.get("genero") or "").strip().lower()
            if genero in MASC:
                total_masculino += 1
            elif genero in FEM:
                total_feminino += 1
            elif genero:
                total_outro += 1

        return render_template(
            "relatorios.html",
            total_alunos=total_alunos_query.count(),
            total_professores=total_professores_query.count(),
            total_turmas=len(todas_as_turmas),
            p_presenca=p_geral,
            media_geral=estatisticas_idade.get("media_geral"),
            media_programa=estatisticas_idade.get("media_programa"),
            media_turma=estatisticas_idade.get("media_turma"),
            conselho=metricas,
            freq_programa=f_prog,
            freq_turma=f_turma,
            freq_professor=f_prof,
            todas_as_turmas=todas_as_turmas,
            total_masculino=total_masculino,
            total_feminino=total_feminino,
            total_outro=total_outro,
        )
    except Exception as e:
        flash(f"Ocorreu um erro gerando o relatório dinâmico: {e}", "danger")
        return redirect(url_for("main.dashboard"))


@bp.route("/relatorios/exportar")
@login_required
def exportar_relatorio():
    """
    Gera as métricas usando PANDAS e exporta em Excel nativamente via Streaming.
    """
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    try:
        unidade_id = get_unidade_id()
        turmas_query = Turma.query.filter_by(ativo=True)
        if unidade_id:
            turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
        todas_as_turmas = turmas_query.all()
        estatisticas_idade = calcular_estatisticas_idade(unidade_id=unidade_id)
        p_geral, f_prog, f_turma, f_prof = calcular_frequencias_relatorio(
            todas_as_turmas, unidade_id=unidade_id
        )
        df_idade_prog = pd.DataFrame(
            list(estatisticas_idade["media_programa"].items()),
            columns=["Programa", "Média de Idade"],
        )
        df_idade_turma = pd.DataFrame(
            list(estatisticas_idade["media_turma"].items()),
            columns=["Turma", "Média de Idade"],
        )

        df_freq_prog = pd.DataFrame(
            list(f_prog.items()), columns=["Programa", "% Presença"]
        )
        df_freq_prof = pd.DataFrame(
            list(f_prof.items()), columns=["Professor", "% Presença"]
        )
        df_freq_turma = pd.DataFrame(
            list(f_turma.items()), columns=["Turma", "% Presença"]
        )

        # Escrita em Buffer RAM (BytesIO) sem salvar arquivo permanente e causar lock de sistema
        output = BytesIO()
        with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
            df_idade_prog.to_excel(writer, sheet_name="Idade por Programa", index=False)
            df_idade_turma.to_excel(writer, sheet_name="Idade por Turma", index=False)
            df_freq_prog.to_excel(writer, sheet_name="Freq por Programa", index=False)
            df_freq_prof.to_excel(writer, sheet_name="Freq por Professor", index=False)
            df_freq_turma.to_excel(writer, sheet_name="Freq por Turma", index=False)

        output.seek(0)

        return send_file(
            output,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"Relatorio_PautaON_{date.today()}.xlsx",
        )
    except Exception as e:
        flash(
            "Falha ao exportar o relatório Excel devido a um erro algorítmico interno.",
            "danger",
        )
        return redirect(url_for("main.relatorio_geral"))


@bp.route("/configurar-conselho", methods=["POST"])
@login_required
def salvar_configuracao_conselho():
    """Grava as delimitações atemporais ou estáticas de conselho no Config KVS do Sistema."""
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    inicio = request.form.get("inicio_conselho")
    fim = request.form.get("fim_conselho")

    if inicio and fim:
        try:
            for chave, valor in [("inicio_conselho", inicio), ("fim_conselho", fim)]:
                conf = ConfiguracaoSistema.query.filter_by(chave=chave).first()
                if not conf:
                    conf = ConfiguracaoSistema(chave=chave)
                    db.session.add(conf)
                conf.valor = valor

            db.session.commit()
            flash("Parâmetros do conselho gravados de forma segura!", "success")
        except Exception as e:
            db.session.rollback()
            flash(f"Falha de gravação de Parâmetro: {e}", "danger")

    return redirect(url_for("registros.planejamento"))


@bp.route("/turma/alternar-conselho/<int:turma_id>")
@login_required
def alternar_conselho(turma_id):
    """Ação Rápida: Inverte o toggle booleano (Flag) indicando se conselho findou para a turma."""
    if current_user.role not in ["admin", "pedagogico"]:
        abort(403)

    try:
        turma = Turma.query.get_or_404(turma_id)
        turma.conselho_concluido = not turma.conselho_concluido
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash("Erro ao salvar mudança de Status do conselho.", "danger")

    return redirect(url_for("registros.planejamento"))


@bp.route("/relatorios/alunos")
@login_required
def relatorio_alunos():
    """Gera o painel de listagem de alunos com filtros dinâmicos."""
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    from app.models import PeriodoLetivo
    from app.utils.logica import get_unidade_id

    # 1. Captura Filtros da Requisição
    periodo_id = request.args.get("periodo_letivo_id", type=int)
    selected_cols = request.args.getlist("colunas")

    # Se for o primeiro acesso sem colunas, define um set padrão amigável
    if not selected_cols and "periodo_letivo_id" not in request.args:
        selected_cols = ["nome", "idade", "turmas_aluno"]
    elif not selected_cols:
        # Se o usuário desmarcou tudo, manterá vazio (template trata)
        pass

    # 2. Dados de Contexto para Filtros (Unidade Logada)
    u_id = get_unidade_id()
    periodos_query = PeriodoLetivo.query
    if u_id:
        periodos_query = periodos_query.filter_by(unidade_id=u_id)
    periodos = periodos_query.order_by(PeriodoLetivo.nome).all()

    # 3. Query Base de Alunos
    query = Aluno.query.filter_by(ativo=True)
    if u_id:
        query = query.filter_by(unidade_id=u_id)

    if periodo_id:
        # Filtra alunos que possuem vínculo com turmas do período selecionado
        query = query.join(Aluno.turmas).filter(Turma.periodo_letivo_id == periodo_id)

    alunos_lista = query.distinct().all()

    # 4. Normalização de dados para o template (acesso via aluno[coluna.key])
    alunos_data = []
    for a in alunos_lista:
        d = {
            "id": a.id,
            "nome": a.nome,
            "nome_social": a.nome_social or "-",
            "data_nascimento": (
                a.data_nascimento.strftime("%d/%m/%Y") if a.data_nascimento else "-"
            ),
            "idade": a.idade,
            "nivel": a.nivel or "-",
            "pcd": False,  # Campo futuro a ser integrado no schema físico
            "turmas_aluno": True,  # Flag para lógica de expansão no template
        }
        # Injeta turmas vinculadas (Top 3 conforme layout do template)
        turmas_vinculadas = a.turmas[:3] if hasattr(a, "turmas") else []
        for i in range(1, 4):
            d[f"turma_{i}"] = (
                turmas_vinculadas[i - 1].nome if len(turmas_vinculadas) >= i else "-"
            )

        alunos_data.append(d)

    column_options = [
        {"key": "nome", "label": "Nome Completo"},
        {"key": "nome_social", "label": "Nome Social"},
        {"key": "data_nascimento", "label": "Data Nascimento"},
        {"key": "idade", "label": "Idade"},
        {"key": "nivel", "label": "Nível"},
        {"key": "pcd", "label": "PCD"},
        {"key": "turmas_aluno", "label": "Turmas Vinculadas"},
    ]

    return render_template(
        "relatorios_alunos.html",
        periodos=periodos,
        selected_periodo_id=periodo_id,
        column_options=column_options,
        selected_cols=selected_cols,
        alunos=alunos_data,
    )


@bp.route("/relatorios/alunos/exportar")
@login_required
def exportar_relatorio_alunos():
    """Gera exportação Excel da listagem de alunos filtrada."""
    if current_user.role not in ["admin", "pedagogico", "secretaria"]:
        abort(403)

    from app.models import PeriodoLetivo
    from app.utils.logica import get_unidade_id

    periodo_id = request.args.get("periodo_letivo_id", type=int)
    selected_cols = request.args.getlist("colunas")

    if not selected_cols:
        flash("Selecione ao menos um dado para exportação.", "warning")
        return redirect(url_for("main.relatorio_alunos"))

    u_id = get_unidade_id()
    query = Aluno.query.filter_by(ativo=True)
    if u_id:
        query = query.filter_by(unidade_id=u_id)
    if periodo_id:
        query = query.join(Aluno.turmas).filter(Turma.periodo_letivo_id == periodo_id)

    alunos_lista = query.distinct().all()

    # Mapeamento de Labels para o Excel
    column_labels = {
        "nome": "Nome Completo",
        "nome_social": "Nome Social",
        "data_nascimento": "Data Nascimento",
        "idade": "Idade",
        "nivel": "Nível",
        "pcd": "PCD",
        "turmas_aluno": "Turmas",
    }

    data_to_df = []
    for a in alunos_lista:
        row = {}
        for col in selected_cols:
            if col == "turmas_aluno":
                row[column_labels[col]] = ", ".join([t.nome for t in a.turmas])
            elif col == "idade":
                row[column_labels[col]] = a.idade
            elif col == "pcd":
                row[column_labels[col]] = "Sim" if getattr(a, "pcd", False) else "Não"
            else:
                row[column_labels[col]] = getattr(a, col, "-")
        data_to_df.append(row)

    df = pd.DataFrame(data_to_df)

    output = BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        df.to_excel(writer, sheet_name="Lista de Alunos", index=False)

    output.seek(0)

    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=f"Alunos_PautaON_{date.today()}.xlsx",
    )


@bp.route("/relatorios/conselho")
@login_required
def resultado_conselho():
    """
    Relatório consolidado do Resultado do Conselho de Classe.
    Cada unidade tem seu próprio contexto: períodos, turmas, alunos, professores.
    Filtra por período letivo e, opcionalmente, por turmas específicas.
    """
    if current_user.role not in ["admin", "pedagogico", "secretaria", "gerencia"]:
        abort(403)

    from app.models import PeriodoLetivo, ConselhoClasse, OpcaoProximaTurma

    unidade_id = get_unidade_id()

    # ------------------------------------------------------------------
    # 1. Períodos letivos da unidade atual (para o filtro do formulário)
    # ------------------------------------------------------------------
    periodos_query = PeriodoLetivo.query
    if unidade_id:
        periodos_query = periodos_query.filter_by(unidade_id=unidade_id)
    periodos = periodos_query.order_by(PeriodoLetivo.data_inicio.desc()).all()

    # ------------------------------------------------------------------
    # 2. Parâmetros de filtro da requisição
    # ------------------------------------------------------------------
    selected_periodo_id = request.args.get("periodo_letivo_id", type=int)
    selected_turma_ids = request.args.getlist("turmas", type=int)
    selected_all_turmas = bool(request.args.get("turmas_all"))

    periodo_selecionado = None
    periodos_turmas = []  # turmas do período para popular o select
    registros = []  # linhas da tabela de resultados
    resumo_status = {}
    turma_count = 0
    aluno_count = 0
    conselho_inicio = None
    conselho_fim = None

    if selected_periodo_id:
        periodo_selecionado = PeriodoLetivo.query.get(selected_periodo_id)

    if periodo_selecionado:
        # Turmas deste período (respeitando unidade)
        turmas_query = Turma.query.filter_by(periodo_letivo_id=selected_periodo_id)
        if unidade_id:
            turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
        periodos_turmas = turmas_query.order_by(Turma.nome).all()

        # Quais turmas exibir
        if selected_all_turmas or not selected_turma_ids:
            turmas_exibir = periodos_turmas
        else:
            turmas_exibir = [t for t in periodos_turmas if t.id in selected_turma_ids]

        turma_count = len(turmas_exibir)
        alunos_vistos = set()

        # Contadores de situação final
        contadores = {
            "Aprovado": 0,
            "Reprovado por Falta": 0,
            "Evadido": 0,
            "Desistente": 0,
            "Empregado": 0,
            "Sem Registro": 0,
        }

        # Datas extremas do ciclo de conselho (para o card de resumo)
        datas_inicio = []
        datas_fim = []

        for turma in turmas_exibir:
            # Alunos ativos da turma
            alunos_turma = [a for a in turma.alunos if a.ativo]

            for aluno in alunos_turma:
                alunos_vistos.add(aluno.id)

                # Busca o registro de fechamento final deste aluno nesta turma
                cc = ConselhoClasse.query.filter_by(
                    turma_id=turma.id, aluno_id=aluno.id, etapa="FINAL"
                ).first()

                situacao = (
                    cc.situacao_final if cc and cc.situacao_final else "Sem Registro"
                )
                prox_turma = ""
                if cc and cc.proxima_turma_obj:
                    prox_turma = cc.proxima_turma_obj.nome
                elif cc and cc.proxima_turma_id:
                    prox_turma = str(cc.proxima_turma_id)

                if cc and cc.data_inicio:
                    datas_inicio.append(cc.data_inicio)
                if cc and cc.data_fim:
                    datas_fim.append(cc.data_fim)

                # Frequência global do aluno nesta turma
                freq_regs = Frequencia.query.filter_by(
                    aluno_id=aluno.id, turma_id=turma.id
                ).all()
                total_freq = len(freq_regs)
                counts = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0, "J": 0}
                for fr in freq_regs:
                    if fr.conceito in counts:
                        counts[fr.conceito] += 1

                _presentes = counts["A"] + counts["B"] + counts["C"] + counts["D"]
                _contaveis = _presentes + counts["F"]   # J não entra no denominador
                presenca = round((_presentes / _contaveis * 100), 1) if _contaveis > 0 else 0

                # Constrói linha da tabela
                registros.append(
                    {
                        "turma": turma.nome,
                        "programa": turma.programa or "-",
                        "professor": turma.professor.name if turma.professor else "-",
                        "aluno": aluno.nome_social or aluno.nome,
                        "nivel": aluno.nivel or "-",
                        "presenca": presenca,
                        "situacao_final": situacao,
                        "proxima_turma": prox_turma,
                        "concluido": cc.concluido if cc else False,
                    }
                )

                # Acumula contador normalizado
                situacao_norm = situacao
                if situacao == "APROVADO":
                    situacao_norm = "Aprovado"
                elif situacao == "REPROVADO_POR_FALTA":
                    situacao_norm = "Reprovado por Falta"
                elif situacao == "EVADIDO":
                    situacao_norm = "Evadido"
                elif situacao == "DESISTENTE":
                    situacao_norm = "Desistente"
                elif situacao == "EMPREGADO":
                    situacao_norm = "Empregado"

                if situacao_norm in contadores:
                    contadores[situacao_norm] += 1
                else:
                    contadores["Sem Registro"] += 1

        aluno_count = len(alunos_vistos)
        conselho_inicio = min(datas_inicio) if datas_inicio else None
        conselho_fim = max(datas_fim) if datas_fim else None

        total_registros = sum(contadores.values())
        resumo_status = {
            label: {
                "count": v,
                "percent": (
                    round(v / total_registros * 100, 1) if total_registros > 0 else 0
                ),
            }
            for label, v in contadores.items()
        }
        resumo_status["total"] = total_registros

    return render_template(
        "resultado_conselho.html",
        periodos=periodos,
        selected_periodo_id=selected_periodo_id,
        selected_turma_ids=selected_turma_ids,
        selected_all_turmas=selected_all_turmas,
        periodo_selecionado=periodo_selecionado,
        periodos_turmas=periodos_turmas,
        registros=registros,
        resumo_status=resumo_status,
        turma_count=turma_count,
        aluno_count=aluno_count,
        conselho_inicio=conselho_inicio,
        conselho_fim=conselho_fim,
    )


@bp.route("/trocar-unidade/<int:id>")
@login_required
def trocar_unidade(id):
    from flask import session

    if id == 0:
        session.pop("unidade_id", None)
        flash("Visão Global (Todas as Unidades) ativada.", "success")
    else:
        session["unidade_id"] = id
        uni = Unidade.query.get(id)
        flash(f"Você agora está na Unidade {uni.nome}", "info")
    return redirect(url_for("main.dashboard"))

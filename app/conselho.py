"""
================================================================================
CONSELHO.PY - Conselho de classe
================================================================================

Cobre:
    - Painel geral de conselhos
    - Gerenciamento de perguntas
    - Lançamento e fechamento
    - Avaliação geral da turma
    - Períodos de conselho

NOTA ONDA 2B
    Comparações de `current_user.role` usam `UserRole` e comparações de etapa
    usam `EtapaConselho`. Valores vindos de formulário/querystring permanecem
    strings (SQLAlchemy aceita ambos no Enum column).

NOTA ONDA 4 — D5.2 (escrita do conselho por oferta)
    Lançamento, fechamento e avaliação coletiva trabalham POR OFERTA
    (TurmaCurso) com o padrão do M1: 1 oferta ativa = uso direto; 2+ exige
    escolha (`?oferta_sel=` no GET, campo `turma_curso_id` no POST) validada
    contra `ofertas_ativas(turma)`; 0 ofertas recusa. Todo ConselhoClasse
    novo nasce com `turma_curso_id`; linhas legadas (NULL) não são tocadas
    nem adotadas. Pareceres coletivos (perguntas tipo TURMA) passam a viver
    em `TurmaCurso.avaliacao_*` (Q1) e deixam de ser gravadas em
    ConselhoResposta. Isolamento por unidade (B3/B4) vale para todos os
    perfis em todas as rotas de escrita daqui.
================================================================================
"""

import json
import logging

from flask import Blueprint, render_template, request, redirect, flash, abort, url_for, jsonify
from flask_login import login_required, current_user
from app.models import (PerguntaConselho, Turma, Aluno, Frequencia,
                    OpcaoProximaTurma, ConselhoClasse, ConselhoResposta, Inscricao,
                    PeriodoConselho, PeriodoLetivo)
from app.models.enums import (
    ETAPA_PARA_CAMPO_AVALIACAO,
    EtapaConselho,
    SituacaoFinal,
    UserRole,
)
from app.database import db
from app.extensions import csrf
from app.registros.shared import assert_unidade_context
from app.services.turma_curso import (
    contar_ofertas_conselho,
    ofertas_ativas,
    ofertas_do_painel_conselho,
)
from app.services.turma_curso_horario import grades_para_exibicao
from sqlalchemy import select, case
from datetime import datetime, date
from collections import OrderedDict
from app.utils.logica import calcular_estatisticas_frequencia, get_unidade_id

logger = logging.getLogger(__name__)
bp = Blueprint('conselho', __name__)


def _resolver_oferta_conselho(turma, oferta_id=None):
    """Resolve a oferta na qual a rota de conselho vai trabalhar (D5.2, M1).

    Regras: 1 oferta ativa = usa direto (dispensa escolha); 2+ exige
    `oferta_id` apontando para uma oferta ATIVA da própria turma (oferta
    inativa ou de outra turma cai fora de `ofertas_ativas` e é recusada);
    0 ofertas = turma não abre conselho.

    Retorna ``(oferta, ativas, exigir_escolha)`` — `oferta` é None quando
    não há oferta válida; `exigir_escolha` é True somente com 2+ ativas e
    escolha ausente/inválida (a tela precisa mostrar o seletor).
    """
    ativas = ofertas_ativas(turma.id)
    if not ativas:
        return None, ativas, False
    if len(ativas) == 1:
        return ativas[0], ativas, False
    oferta = next((o for o in ativas if o.id == oferta_id), None)
    return oferta, ativas, oferta is None


def _escolha_fora_das_ativas(oferta_id, oferta):
    """True quando o pedido apontou explicitamente para uma oferta que não é
    a ativa resolveada (inativa, de outra turma, ou inexistente) mesmo com
    oferta única — D5.2 exige recusa, não uso silencioso da outra ponta.
    Com escolha ausente ou já batendo com a oferta resolvida, é False.
    """
    return (oferta_id is not None and oferta is not None
            and oferta.id != oferta_id)


def _normalizar_situacao_final(valor):
    """Converte o código enviado pelo select do fechamento no valor válido
    do CHECK `ck_conselho_situacao_final` (enum `SituacaoFinal`).

    Aceita o VALOR do enum ('Aprovado', 'Reprovado por Falta', ...) — forma
    enviada pelo select a partir da D5.2b — e, por compatibilidade, os nomes
    do enum ('APROVADO', 'REPROVADO_POR_FALTA', ...), incluindo o apelido
    histórico 'PARTICIPANTE' (a tela antiga usava esse rótulo para
    'Participação'). Vazio/None = situação não informada. Valor desconhecido
    levanta ValueError — o chamador recusa o pedido em vez de gravar às cegas.
    """
    if valor is None:
        return None
    texto = str(valor).strip()
    if texto in ("", "None", "none"):
        return None
    for situacao in SituacaoFinal:
        if texto == situacao.value:
            return situacao.value
    codigo = texto.upper()
    if codigo == "PARTICIPANTE":
        codigo = "PARTICIPACAO"
    try:
        return SituacaoFinal[codigo].value
    except KeyError:
        raise ValueError(f"Situação final inválida: {valor}") from None


def _build_turma_avaliacao_payload(form_data, perguntas) -> str:
    """Serializa respostas de avaliação coletiva (perguntas tipo TURMA) em JSON,
    ignorando campos vazios.

    D5.2/Q1: a avaliação coletiva passa a viver em `TurmaCurso.avaliacao_*`
    (campo da OFERTA), preservando a mesma codificação JSON em uso desde a
    criação das colunas em D5.1 — sem nova tabela.
    """
    respostas = {}
    for pergunta in perguntas:
        campo = f"resp_turma_{pergunta.id}"
        valor = form_data.get(campo, "")
        if valor is None:
            continue
        valor_limpo = str(valor).strip()
        if valor_limpo:
            respostas[str(pergunta.id)] = valor_limpo
    return json.dumps(respostas, ensure_ascii=False)


def _get_turma_avaliacao_respostas(obj, etapa: str) -> dict:
    """Recupera respostas previamente gravadas da avaliação coletiva da etapa.

    Desde D5.2 o objeto é a OFERTA (`TurmaCurso.avaliacao_*`); desde a D5.5 o
    mapa etapa→campo vem de `ETAPA_PARA_CAMPO_AVALIACAO` (os campos de
    `TurmaCurso` têm os mesmos nomes dos de `Turma`).
    """
    valor = getattr(
        obj,
        ETAPA_PARA_CAMPO_AVALIACAO.get(etapa, "avaliacao_inicial"),
        "",
    ) or ""
    if not valor:
        return {}

    try:
        dados = json.loads(valor)
    except (TypeError, json.JSONDecodeError):
        return {}

    if not isinstance(dados, dict):
        return {}
    return {str(chave): str(valor_item) for chave, valor_item in dados.items() if valor_item}


def _normalize_conselho_request(form_data) -> dict:
    """Normaliza os campos do formulário de conselho para evitar valores inválidos.

    Esta função é usada para padronizar entradas vindas do formulário antes do
    processamento, preservando o fluxo atual do sistema acadêmico sem novos módulos.
    """
    normalized = {
        "turma_id": None,
        "etapa": form_data.get("etapa", EtapaConselho.INICIAL.value),
        "data_inicio": form_data.get("data_inicio", ""),
        "data_fim": form_data.get("data_fim", ""),
        "respostas": {},
    }

    turma_id = form_data.get("turma_id", "")
    if turma_id not in (None, ""):
        try:
            normalized["turma_id"] = int(str(turma_id).strip())
        except ValueError:
            normalized["turma_id"] = None

    for key, value in form_data.items():
        if key.startswith("resp_"):
            parts = key.split("_")
            # D5.2: só existem respostas de ALUNO neste formulário. Campos
            # 'resp_turma_*' não são mais parseados aqui — a avaliação
            # coletiva (tipo TURMA) vive em TurmaCurso.avaliacao_* e é
            # gravada exclusivamente pela rota avaliar_turma.
            if len(parts) >= 3:
                aluno_id = parts[1]
                pergunta_id = parts[2]
                if aluno_id.isdigit() and pergunta_id.isdigit():
                    normalized["respostas"][f"{aluno_id}_{pergunta_id}"] = str(value).strip()

    return normalized


# ---------------------------------------------------------------------------
# PAINEL GERAL
# ---------------------------------------------------------------------------

@bp.route('/conselho')
@login_required
def index_conselho():
    """Painel do conselho — UMA LINHA POR OFERTA (D5.3).

    O encerramento é manual e por oferta (`TurmaCurso.conselho_concluido`);
    o status exibido vem SEMPRE da oferta. Turma sem oferta ativa não abre
    conselho e não aparece na lista (só no aviso discreto abaixo).
    """
    unidade_id = get_unidade_id()
    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)

    lista_programas = [p for p in db.session.execute(stmt_prog).scalars().all() if p]

    programa_ativo = request.args.get('programa', 'Todos')
    turno_ativo    = request.args.get('turno', 'Todos')

    professor_id = None
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.GERENCIA):
        professor_id = current_user.id

    ofertas = ofertas_do_painel_conselho(
        unidade_id,
        programa=programa_ativo,
        turno=turno_ativo,
        professor_id=professor_id,
    )

    # Aviso discreto (não conta como pendência): turmas ativas do filtro que
    # não têm oferta ativa e por isso ficaram fora da lista/contagens.
    stmt = select(Turma).where(Turma.ativo == True)
    if unidade_id:
        stmt = stmt.where(Turma.unidade_id == unidade_id)
    if programa_ativo != 'Todos':
        stmt = stmt.where(Turma.programa == programa_ativo)
    if turno_ativo != 'Todos':
        stmt = stmt.where(Turma.turno == turno_ativo)
    if professor_id is not None:
        stmt = stmt.where(Turma.professor_id == professor_id)
    turma_ids_com_oferta = {item['turma'].id for item in ofertas}
    turmas_sem_oferta = sum(
        1 for turma in db.session.execute(stmt).scalars().all()
        if turma.id not in turma_ids_com_oferta
    )

    # H3e: grade de exibição das ofertas do painel (uma leitura em lote).
    grade_oferta_map = grades_para_exibicao(
        [item['oferta'] for item in ofertas]
    )

    return render_template('conselho/painel.html',
                           ofertas=ofertas,
                           grade_oferta_map=grade_oferta_map,
                           turmas_sem_oferta=turmas_sem_oferta,
                           lista_programas=lista_programas,
                           programa_ativo=programa_ativo,
                           turno_ativo=turno_ativo)


# ---------------------------------------------------------------------------
# GERENCIAMENTO DE PERGUNTAS
# ---------------------------------------------------------------------------

@bp.route('/conselho/perguntas')
@login_required
def gerenciar_perguntas():
    if current_user.role not in (UserRole.PEDAGOGICO, UserRole.ADMIN, UserRole.GERENCIA):
        abort(403)

    ordem_manual = [EtapaConselho.INICIAL, EtapaConselho.PERCURSO, EtapaConselho.FINAL]

    ordem_etapas = case(
        {EtapaConselho.INICIAL: 1, EtapaConselho.PERCURSO: 2, EtapaConselho.FINAL: 3},
        value=PerguntaConselho.etapa
    )

    # Chamada preservada pelo efeito colateral: normaliza o contexto de
    # unidade na sessão (perfis operacionais). O resultado não é usado aqui —
    # PerguntaConselho é global.
    get_unidade_id()
    query = PerguntaConselho.query.filter_by(ativo=True).order_by(ordem_etapas, PerguntaConselho.id)
    # PerguntaConselho é global — perguntas são compartilhadas entre unidades
    perguntas_raw = query.all()

    # Agrupa preservando a ordem manual. As chaves são strings ('INICIAL', ...)
    # para compatibilidade com templates que fazem `perguntas_agrupadas.items()`.
    perguntas_agrupadas = OrderedDict()
    for etapa in ordem_manual:
        etapa_str = etapa.value if isinstance(etapa, EtapaConselho) else etapa
        lista = [p for p in perguntas_raw if p.etapa == etapa]
        if lista:
            perguntas_agrupadas[etapa_str] = lista

    return render_template('conselho/perguntas.html', perguntas_agrupadas=perguntas_agrupadas)


@bp.route('/conselho/imprimir', methods=['GET'])
@login_required
def imprimir_conselho():
    if current_user.role not in (UserRole.PEDAGOGICO, UserRole.ADMIN, UserRole.GERENCIA):
        abort(403)

    etapa_raw = request.args.get('etapa')
    quantidade_raw = request.args.get('quantidade')
    if etapa_raw is None and quantidade_raw is None:
        return redirect(url_for('conselho.index_conselho'))

    try:
        etapa = EtapaConselho(etapa_raw)
    except (TypeError, ValueError):
        flash("Selecione uma etapa válida para imprimir.", "warning")
        return redirect(url_for('conselho.imprimir_conselho'))

    try:
        quantidade = int(quantidade_raw)
    except (TypeError, ValueError):
        flash("Informe uma quantidade válida de alunos.", "warning")
        return redirect(url_for('conselho.imprimir_conselho'))

    if not 1 <= quantidade <= 100:
        flash("A quantidade deve estar entre 1 e 100 alunos.", "warning")
        return redirect(url_for('conselho.imprimir_conselho'))

    perguntas = (
        PerguntaConselho.query
        .filter_by(etapa=etapa, ativo=True)
        .order_by(PerguntaConselho.id)
        .all()
    )
    perguntas_turma = [p for p in perguntas if p.tipo == 'TURMA']
    perguntas_aluno = [p for p in perguntas if p.tipo == 'ALUNO']

    return render_template(
        'conselho/imprimir_formulario.html',
        etapa=etapa,
        quantidade=quantidade,
        perguntas_turma=perguntas_turma,
        perguntas_aluno=perguntas_aluno,
        now=datetime.now(),
    )


@bp.route('/conselho/pergunta/salvar', methods=['POST'])
@login_required
def salvar_pergunta():
    if current_user.role not in (UserRole.PEDAGOGICO, UserRole.ADMIN, UserRole.GERENCIA):
        abort(403)

    pergunta_id = request.form.get('id')
    etapa  = request.form.get('etapa')
    tipo   = request.form.get('tipo')
    texto  = request.form.get('texto')
    opcoes = request.form.get('opcoes')

    if pergunta_id:
        pergunta        = db.get_or_404(PerguntaConselho, int(pergunta_id))
        pergunta.etapa  = etapa
        pergunta.tipo   = tipo
        pergunta.texto  = texto
        pergunta.opcoes = opcoes
    else:
        db.session.add(PerguntaConselho(
            etapa=etapa,
            tipo=tipo,
            texto=texto,
            opcoes=opcoes,
        ))

    db.session.commit()
    flash("Pergunta salva com sucesso!", "success")
    return redirect(url_for('conselho.gerenciar_perguntas'))


@bp.route('/conselho/pergunta/excluir/<int:id>', methods=['POST'])
@login_required
def excluir_pergunta(id):
    if current_user.role not in (UserRole.PEDAGOGICO, UserRole.ADMIN, UserRole.GERENCIA):
        abort(403)

    pergunta = db.get_or_404(PerguntaConselho, id)
    pergunta.ativo = False
    db.session.commit()
    flash("Pergunta removida com sucesso!", "info")
    return redirect(url_for('conselho.gerenciar_perguntas'))


# ---------------------------------------------------------------------------
# LANÇAMENTO DO CONSELHO
# ---------------------------------------------------------------------------

@bp.route('/conselho/lancamento')
@login_required
def lancamento_conselho():
    turma_id = request.args.get('turma')
    etapa    = request.args.get('etapa', EtapaConselho.INICIAL.value)
    programa_filtro = request.args.get('programa', 'Todos')
    turno_filtro    = request.args.get('turno', 'Todos')

    unidade_id = get_unidade_id()
    stmt_prog = select(Turma.programa).distinct().where(Turma.ativo == True)
    if unidade_id:
        stmt_prog = stmt_prog.where(Turma.unidade_id == unidade_id)
    lista_programas = db.session.execute(stmt_prog).scalars().all()

    opcoes_proximas = OpcaoProximaTurma.query.filter_by(ativo=True).all()

    if current_user.role in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.GERENCIA):
        stmt = select(Turma).where(Turma.ativo == True)
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)

        if programa_filtro != 'Todos':
            stmt = stmt.where(Turma.programa == programa_filtro)
        if turno_filtro != 'Todos':
            stmt = stmt.where(Turma.turno == turno_filtro)
    else:
        stmt = select(Turma).where(
            Turma.professor_id == current_user.id, Turma.ativo == True
        )
    turmas_para_select = db.session.execute(stmt).scalars().all()

    # Sem turma selecionada: renderiza apenas os filtros
    if not turma_id:
        return render_template('conselho/lancamento.html',
                               turmas=turmas_para_select,
                               lista_programas=lista_programas,
                               programa_ativo=programa_filtro,
                               turno_ativo=turno_filtro,
                               etapa=etapa,
                               turma=None)

    turma_obj = db.get_or_404(Turma, turma_id)
    # D5.2/B4: o lançamento escreve ConselhosClasse, então o isolamento por
    # unidade vale para todos os perfis, inclusive admin sem unidade na
    # sessão (Visão Global é somente leitura).
    assert_unidade_context(turma_obj.unidade_id, unidade_id)

    # D5.2 (M1): conselho é por OFERTA. 0 ofertas = turma não abre conselho;
    # 2+ sem escolha válida = tela só mostra o seletor, sem tocar em dados.
    sel_id = request.args.get('oferta_sel', type=int)
    oferta, ofertas_turma, exigir_escolha = _resolver_oferta_conselho(
        turma_obj, sel_id
    )
    if _escolha_fora_das_ativas(sel_id, oferta):
        # Oferta inativa, de outra turma ou inexistente pedida explicitamente:
        # recusa sem criar nada (volta aos filtros; com 1 ativa o seletor nem
        # é necessário — mas a escolha maliciosa não é usada).
        flash("A oferta escolhida não é uma oferta ativa desta turma.", "warning")
        return redirect(url_for('conselho.lancamento_conselho',
                                programa=programa_filtro,
                                turno=turno_filtro,
                                etapa=etapa))
    render_base = dict(
        turmas=turmas_para_select,
        lista_programas=lista_programas,
        programa_ativo=programa_filtro,
        turno_ativo=turno_filtro,
        etapa=etapa,
        opcoes_proximas_turmas=opcoes_proximas,
    )
    if not ofertas_turma:
        flash(
            f'Não é possível abrir o conselho: a turma {turma_obj.nome} não '
            'possui curso (oferta) ativa. Cadastre o curso antes de lançar.',
            'warning',
        )
        return redirect(url_for('conselho.lancamento_conselho',
                            programa=programa_filtro,
                            turno=turno_filtro,
                            etapa=etapa))
    if exigir_escolha:
        return render_template('conselho/lancamento.html',
                               turma=turma_obj,
                               ofertas=ofertas_turma,
                               oferta=None,
                               exigir_escolha=True,
                               **render_base)

    # Alunos da OFERTA (inscrição ativa nela; distinct: 2 inscrições ativas
    # da mesma oferta não podem duplicar o aluno na lista).
    alunos = Aluno.query.join(Inscricao).filter(
        Inscricao.turma_curso_id == oferta.id,
        Inscricao.ativo == True,
        Aluno.ativo == True
    ).distinct().order_by(Aluno.nome).all()
    if not alunos:
        flash(f'Não é possível abrir o conselho: A turma {turma_obj.nome} não possui alunos ativos.', 'warning')
        return redirect(url_for('conselho.lancamento_conselho',
                            programa=programa_filtro,
                            turno=turno_filtro,
                            etapa=etapa,
                            oferta_sel=oferta.id))

    # Busca ou cria registros de conselho POR OFERTA para a etapa. Linhas
    # legadas (turma_curso_id NULL) não são tocadas nem adotadas.
    for aluno in alunos:
        existe = ConselhoClasse.query.filter_by(
            turma_curso_id=oferta.id,
            aluno_id=aluno.id,
            etapa=etapa
        ).first()
        if not existe:
            db.session.add(ConselhoClasse(
                turma_id=turma_obj.id,
                turma_curso_id=oferta.id,
                aluno_id=aluno.id,
                etapa=etapa,
                unidade_id=unidade_id
            ))
    try:
        db.session.commit()
    except Exception as e:
        from app.utils.errors import flash_and_log

        db.session.rollback()
        flash_and_log(e, location='conselho.lancamento_conselho', hint='db')
        return redirect(url_for('conselho.lancamento_conselho', etapa=etapa,
                                oferta_sel=oferta.id))

    # Usa o primeiro registro da oferta como referência de conselho_id
    db.session.expire_all()
    conselho = ConselhoClasse.query.filter_by(
        turma_curso_id=oferta.id, etapa=etapa
    ).first()

    perguntas = PerguntaConselho.query.filter_by(etapa=etapa, ativo=True).order_by(PerguntaConselho.id).all()

    respostas_db = ConselhoResposta.query.join(ConselhoClasse).filter(
        ConselhoClasse.turma_curso_id == oferta.id,
        ConselhoClasse.etapa == etapa
    ).all()
    respostas_map = {f"{r.aluno_id}_{r.pergunta_id}": r.resposta for r in respostas_db}

    return render_template('conselho/lancamento.html',
                           turma=turma_obj,
                           oferta=oferta,
                           ofertas=ofertas_turma,
                           exigir_escolha=False,
                           alunos=alunos,
                           perguntas=perguntas,
                           conselho=conselho,
                           respostas=respostas_map,
                           **render_base)


@bp.route('/conselho/salvar', methods=['POST'])
@login_required
def salvar_conselho():
    normalized = _normalize_conselho_request(request.form)
    turma_id = normalized["turma_id"]
    etapa = normalized["etapa"]

    if not turma_id or not etapa:
        flash("Dados insuficientes para salvar.", "warning")
        return redirect(url_for('conselho.lancamento_conselho'))

    turma_obj = db.get_or_404(Turma, turma_id)
    unidade_id = get_unidade_id()
    # D5.2/B4: escrita de conselho — isolamento vale para todos os perfis.
    assert_unidade_context(turma_obj.unidade_id, unidade_id)

    # D5.2 (M1): a oferta vem do formulário (turma_curso_id); 1 oferta ativa
    # é usada direto. 0 ou escolha ausente/inválida (oferta inativa, de outra
    # turma/unidade) = recusa sem gravar nada.
    oferta_id_form = request.form.get("turma_curso_id", type=int)
    oferta, ativas, exigir_escolha = _resolver_oferta_conselho(
        turma_obj, oferta_id_form
    )
    if _escolha_fora_das_ativas(oferta_id_form, oferta):
        flash("A oferta enviada não é uma oferta ativa desta turma.", "warning")
        return redirect(url_for('conselho.lancamento_conselho',
                                turma=turma_id, etapa=etapa))
    if not ativas:
        flash(
            f"A turma {turma_obj.nome} não possui curso (oferta) ativa; "
            "o conselho não pode ser salvo.",
            "warning",
        )
        return redirect(url_for('conselho.lancamento_conselho'))
    if exigir_escolha:
        flash("Selecione o curso (oferta) antes de salvar o conselho.", "warning")
        return redirect(url_for('conselho.lancamento_conselho',
                                turma=turma_id, etapa=etapa))

    data_inicio = normalized["data_inicio"]
    data_fim = normalized["data_fim"]

    # Só os conselhos DA OFERTA naquela etapa (legados NULL ficam de fora).
    conselhos_turma = ConselhoClasse.query.filter_by(
        turma_curso_id=oferta.id, etapa=etapa
    ).all()
    conselho_map = {c.aluno_id: c for c in conselhos_turma}

    for c in conselhos_turma:
        if data_inicio:
            try:
                c.data_inicio = datetime.strptime(data_inicio, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data inicial inválido.", "warning")
                return redirect(url_for('conselho.lancamento_conselho', turma=turma_id, etapa=etapa, oferta_sel=oferta.id))
        if data_fim:
            try:
                c.data_fim = datetime.strptime(data_fim, "%Y-%m-%d").date()
            except ValueError:
                flash("Formato de data final inválido.", "warning")
                return redirect(url_for('conselho.lancamento_conselho', turma=turma_id, etapa=etapa, oferta_sel=oferta.id))

    # Alunos com inscrição ATIVA na oferta: resposta de aluno de fora é
    # ignorada (nunca anexada a outro conselho).
    alunos_oferta = {
        aluno_id for (aluno_id,) in db.session.query(Inscricao.aluno_id).filter(
            Inscricao.turma_curso_id == oferta.id,
            Inscricao.ativo == True,
        ).distinct()
    }

    for key, value in normalized["respostas"].items():
        parts = key.split('_')
        if len(parts) < 2:
            continue
        aluno_id = int(parts[0])
        pergunta_id = int(parts[1])

        if aluno_id not in alunos_oferta:
            continue

        conselho = conselho_map.get(aluno_id)
        if conselho is None:
            # Aluno matriculado na oferta sem conselho criado ainda: nasce já
            # vinculado à oferta (regra D5.2 — nada de linha sem turma_curso_id).
            conselho = ConselhoClasse(
                turma_id=turma_obj.id,
                turma_curso_id=oferta.id,
                aluno_id=aluno_id,
                etapa=etapa,
                unidade_id=unidade_id,
            )
            db.session.add(conselho)
            db.session.flush()
            conselho_map[aluno_id] = conselho

        resposta = ConselhoResposta.query.filter_by(
            conselho_id=conselho.id,
            aluno_id=aluno_id,
            pergunta_id=pergunta_id
        ).first()

        if resposta:
            resposta.resposta = value
        else:
            db.session.add(ConselhoResposta(
                conselho_id=conselho.id,
                aluno_id=aluno_id,
                pergunta_id=pergunta_id,
                resposta=value
            ))

    db.session.commit()
    flash("Conselho atualizado com sucesso!", "success")
    return redirect(url_for('conselho.lancamento_conselho',
                            turma=turma_id, etapa=etapa, oferta_sel=oferta.id))


# ---------------------------------------------------------------------------
# FECHAMENTO DE TURMA
# ---------------------------------------------------------------------------

@bp.route('/conselho/fechamento/<int:turma_id>')
@login_required
def fechamento_turma(turma_id):
    turma = Turma.query.get_or_404(turma_id)
    # D5.2/B4: o fechamento grava ConselhosClasse FINAL — isolamento para
    # todos os perfis.
    assert_unidade_context(turma.unidade_id, get_unidade_id())

    # D5.2 (M1): fechamento por OFERTA — mesmos 0/1/2+ de lançamento.
    sel_id = request.args.get('oferta_sel', type=int)
    oferta, ofertas_turma, exigir_escolha = _resolver_oferta_conselho(
        turma, sel_id
    )
    if _escolha_fora_das_ativas(sel_id, oferta):
        flash("A oferta escolhida não é uma oferta ativa desta turma.", "warning")
        return redirect(url_for('conselho.fechamento_turma', turma_id=turma.id))
    if not ofertas_turma:
        flash(
                        f'A turma "{turma.nome}" não possui curso (oferta) ativa; não há conselho a fechar.',
            'warning',
        )
        return redirect(url_for('conselho.lancamento_conselho'))
    if exigir_escolha:
        return render_template('conselho/fechamento.html',
                               turma=turma,
                               oferta=None,
                               grade_oferta=None,
                               ofertas=ofertas_turma,
                               exigir_escolha=True,
                               dados=[],
                               opcoes_turma=[])

    # Alunos da OFERTA (inscrição ativa nela, distinct por aluno).
    alunos = Aluno.query.join(Inscricao).filter(
        Inscricao.turma_curso_id == oferta.id,
        Inscricao.ativo == True,
        Aluno.ativo == True
    ).distinct().order_by(Aluno.nome).all()

    # BLOQUEIO: Se não houver alunos ativos, não prossegue para os cálculos
    if not alunos:
        flash(f'A turma "{turma.nome}" não possui alunos ativos para fechamento.', 'warning')
        return redirect(url_for('conselho.lancamento_conselho'))

    # D5.2 (Passo 5): a lista hardcoded de "próximas turmas" sai de cena —
    # o catálogo OpcaoProximaTurma (ativos) é a fonte das opções.
    proximas_opcoes = OpcaoProximaTurma.query.filter_by(ativo=True).order_by(
        OpcaoProximaTurma.nome
    ).all()

    dados_alunos = []
    for aluno in alunos:
        # Frequência filtrada pela OFERTA (D5.2); registros legados com
        # turma_curso_id NULL não entram na conta da oferta.
        registros = Frequencia.query.filter_by(
            aluno_id=aluno.id, turma_id=turma.id, turma_curso_id=oferta.id
        ).all()
        estatisticas = calcular_estatisticas_frequencia(
            registro.conceito for registro in registros
        )

        dados_alunos.append({
            'obj':      aluno,
            'counts':   estatisticas['counts'],
            'percs': {
                conceito: round(
                    quantidade / estatisticas['total_registros'] * 100, 1
                ) if estatisticas['total_registros'] else 0
                for conceito, quantidade in estatisticas['counts'].items()
            },
            'presenca': estatisticas['presenca_percentual'],
            'falta':    estatisticas['falta_percentual'],
            'justificadas': estatisticas['justificadas'],
        })

    return render_template('conselho/fechamento.html',
                           turma=turma,
                           oferta=oferta,
                           grade_oferta=grades_para_exibicao([oferta]).get(oferta.id),
                           ofertas=ofertas_turma,
                           exigir_escolha=False,
                           dados=dados_alunos,
                           opcoes_turma=proximas_opcoes)


@bp.route('/conselho/fechamento/<int:turma_id>/salvar', methods=['POST'])
@login_required
def salvar_fechamento_data(turma_id):
    """Salva situação final de cada aluno da OFERTA via JSON (chamado pelo JS).

    D5.2: a rota passa a exigir a oferta (mesmo padrão 0/1/2+ das outras) e
    o caminho alinha o JS antigo (`<path da página>/salvar`). Itens de alunos
    sem inscrição ativa na oferta são ignorados.
    """
    data = request.get_json(silent=True) or {}
    registros = data.get('dados', [])

    turma = Turma.query.get_or_404(turma_id)
    unidade_id = get_unidade_id()
    assert_unidade_context(turma.unidade_id, unidade_id)

    oferta_id = data.get('oferta_id') or request.args.get('oferta_sel', type=int)
    try:
        oferta_id = int(oferta_id) if oferta_id not in (None, "", "None") else None
    except (TypeError, ValueError):
        oferta_id = None
    oferta, ativas, exigir_escolha = _resolver_oferta_conselho(turma, oferta_id)
    if _escolha_fora_das_ativas(oferta_id, oferta):
        return jsonify({"success": False, "message": "A oferta enviada não é uma oferta ativa desta turma."}), 400
    if not ativas:
        return jsonify({"success": False, "message": "Turma sem curso (oferta) ativa — nada a fechar."}), 400
    if exigir_escolha:
        return jsonify({"success": False, "message": "Selecione o curso (oferta) cujo conselho será fechado."}), 400

    alunos_oferta = {
        aluno_id for (aluno_id,) in db.session.query(Inscricao.aluno_id).filter(
            Inscricao.turma_curso_id == oferta.id,
            Inscricao.ativo == True,
        ).distinct()
    }

    try:
        # Valida situações ANTES de mutar qualquer linha (pedido atômico).
        validados = []
        for item in registros:
            aluno_id = int(item['aluno_id'])
            if aluno_id not in alunos_oferta:
                continue
            situacao = _normalizar_situacao_final(item.get('situacao'))
            validados.append((aluno_id, situacao, item.get('proxima_turma_id')))

        for aluno_id, situacao, p_turma_id in validados:
            if p_turma_id in ("", "None", None):
                p_turma_id = None
            else:
                p_turma_id = int(p_turma_id)

            conselho = ConselhoClasse.query.filter_by(
                turma_curso_id=oferta.id,
                aluno_id=aluno_id,
                etapa=EtapaConselho.FINAL
            ).first()

            if not conselho:
                conselho = ConselhoClasse(
                    turma_id=turma.id,
                    turma_curso_id=oferta.id,
                    aluno_id=aluno_id,
                    etapa=EtapaConselho.FINAL.value,
                    data_inicio=date.today(),
                    instrutor_id=current_user.id,
                    unidade_id=unidade_id
                )
                db.session.add(conselho)

            conselho.situacao_final         = situacao
            conselho.proxima_turma_id       = p_turma_id
            conselho.concluido              = True
            conselho.data_fim               = date.today()

        db.session.commit()
        return jsonify({"success": True})

    except ValueError as e:
        db.session.rollback()
        return jsonify({"success": False, "message": str(e)})
    except Exception:
        db.session.rollback()
        logger.exception("Erro no salvamento do fechamento da turma %s", turma_id)
        return jsonify({"success": False, "message": "Falha ao salvar o fechamento da turma. Veja o log para detalhes."})


# ---------------------------------------------------------------------------
# AVALIAÇÃO COLETIVA DA OFERTA (feita pelo professor)
# ---------------------------------------------------------------------------

@bp.route('/turma/<int:turma_id>/avaliacao', methods=['GET', 'POST'])
@login_required
def avaliar_turma(turma_id):
    turma = db.get_or_404(Turma, turma_id)

    if current_user.role == UserRole.PROFESSOR and turma.professor_id != current_user.id:
        abort(403)
    # D5.2/B4: isolamento por unidade também aqui (todos os perfis).
    assert_unidade_context(turma.unidade_id, get_unidade_id())

    etapa_selecionada = request.values.get('etapa', EtapaConselho.INICIAL.value)

    # D5.2 (Q1): a avaliação coletiva (perguntas tipo TURMA) é da OFERTA —
    # grava e lê em TurmaCurso.avaliacao_*, não mais em Turma.avaliacao_*.
    oferta_id_req = (request.values.get('oferta_sel', type=int)
                     or request.values.get('turma_curso_id', type=int))
    oferta, ativas, exigir_escolha = _resolver_oferta_conselho(
        turma, oferta_id_req,
    )
    if _escolha_fora_das_ativas(oferta_id_req, oferta):
        flash("A oferta escolhida não é uma oferta ativa desta turma.", "warning")
        return redirect(url_for('conselho.avaliar_turma', turma_id=turma.id))
    if not ativas:
        flash(
                        f'A turma {turma.nome} não possui curso (oferta) ativa — a avaliação coletiva é por oferta.',
            'warning',
        )
        return redirect(url_for('registros.painel_professor'))
    if exigir_escolha:
        return render_template('conselho/turma_aval.html',
                               turma=turma,
                               oferta=None,
                               ofertas=ativas,
                               exigir_escolha=True,
                               etapa_atual=etapa_selecionada,
                               perguntas=[],
                               respostas={})

    perguntas = PerguntaConselho.query.filter_by(
        tipo='TURMA', etapa=etapa_selecionada, ativo=True
    ).order_by(PerguntaConselho.id).all()
    respostas = _get_turma_avaliacao_respostas(oferta, etapa_selecionada)

    if request.method == 'POST':
        # Nota técnica (D5.2): a avaliação coletiva persiste no registro da
        # OFERTA (colunas criadas na D5.1), com a mesma codificação JSON.
        try:
            payload = _build_turma_avaliacao_payload(request.form, perguntas)
            # D5.5: mapa único etapa→campo (os nomes são iguais em TurmaCurso).
            setattr(oferta, ETAPA_PARA_CAMPO_AVALIACAO[etapa_selecionada], payload)
            db.session.add(oferta)
            db.session.commit()
            flash(f"Avaliação da oferta {oferta.curso.nome} (turma {turma.nome}) salva!", "success")
            return redirect(url_for('registros.painel_professor'))
        except Exception:
            db.session.rollback()
            logger.exception("Falha ao salvar avaliação coletiva da oferta da turma %s", turma_id)
            flash("Não foi possível salvar a avaliação da oferta. Tente novamente.", "danger")

    return render_template('conselho/turma_aval.html',
                           turma=turma,
                           oferta=oferta,
                           ofertas=ativas,
                           exigir_escolha=False,
                           etapa_atual=etapa_selecionada,
                           perguntas=perguntas,
                           respostas=respostas)


# ---------------------------------------------------------------------------
# INFORMAÇÕES DE CONSELHO (PERÍODOS)
# ---------------------------------------------------------------------------

@bp.route('/informacoes', methods=['GET', 'POST'])
@login_required
def informacoes():
    unidade_id = get_unidade_id()
    if request.method == 'POST':
        pass

    periodos_ativos = PeriodoLetivo.query.filter_by(ativo=True, unidade_id=unidade_id).order_by(PeriodoLetivo.id.desc()).all()
    conselhos = PeriodoConselho.query.filter_by(unidade_id=unidade_id).join(PeriodoLetivo).filter(PeriodoLetivo.ativo == True).order_by(PeriodoLetivo.id.desc(), PeriodoConselho.data_inicio).all()

    # D5.3: pendências contadas por OFERTA (turma sem oferta ativa nunca
    # entra como pendente).
    concluidas, total = contar_ofertas_conselho(unidade_id)
    ofertas_pendentes = total - concluidas

    return render_template('conselho/informacoes.html',
                           conselhos=conselhos,
                           periodos_ativos=periodos_ativos,
                           ofertas_pendentes=ofertas_pendentes,
                           ofertas_total=total)


@bp.route('/api/conselho-periodo', methods=['POST'])
@csrf.exempt
@login_required
def salvar_periodo_conselho():
    try:
        unidade_id = get_unidade_id()
        data = request.get_json(force=True, silent=True)
        if data is None:
            logger.error("salvar_periodo_conselho: body JSON inválido ou ausente. Content-Type: %s | Body: %s",
                         request.content_type, request.get_data(as_text=True)[:500])
            return jsonify({"success": False, "msg": "Requisição inválida (JSON não recebido)."}), 400
        logger.debug("salvar_periodo_conselho: unidade_id=%s data=%s", unidade_id, data)
    except Exception:
        logger.exception("salvar_periodo_conselho: erro ao inicializar requisição.")
        return jsonify({"success": False, "msg": "Erro ao processar requisição."}), 500

    conselho_id = data.get('id') or None
    if conselho_id:
        try:
            conselho_id = int(conselho_id)
        except (ValueError, TypeError):
            conselho_id = None
    nome = data.get('nome')
    data_inicio = data.get('data_inicio')
    data_fim = data.get('data_fim')
    conselho_final = data.get('conselho_final', False)
    periodo_letivo_id = data.get('periodo_letivo_id')
    try:
        periodo_letivo_id = int(periodo_letivo_id) if periodo_letivo_id else None
    except (ValueError, TypeError):
        periodo_letivo_id = None

    if not nome or not data_inicio or not data_fim or not periodo_letivo_id:
        return jsonify({"success": False, "msg": "Preencha todos os campos obrigatórios."}), 400

    periodo_letivo = PeriodoLetivo.query.filter_by(id=periodo_letivo_id, unidade_id=unidade_id, ativo=True).first()
    if not periodo_letivo:
        return jsonify({"success": False, "msg": "Período letivo inválido ou inativo."}), 400

    try:
        dt_ini = datetime.strptime(data_inicio, '%Y-%m-%d').date()
        dt_fim = datetime.strptime(data_fim, '%Y-%m-%d').date()

        if dt_ini < periodo_letivo.data_inicio or dt_fim > periodo_letivo.data_fim:
            return jsonify({"success": False, "msg": f"As datas do conselho devem estar dentro do período letivo ({periodo_letivo.data_inicio.strftime('%d/%m/%Y')} a {periodo_letivo.data_fim.strftime('%d/%m/%Y')})."}), 400
    except Exception:
        return jsonify({"success": False, "msg": "Datas inválidas."}), 400

    if conselho_final:
        # Desmarca o anterior se houver
        PeriodoConselho.query.filter_by(unidade_id=unidade_id, conselho_final=True).update({'conselho_final': False})

    if conselho_id:
        conselho = PeriodoConselho.query.filter_by(id=conselho_id, unidade_id=unidade_id).first()
        if not conselho:
            return jsonify({"success": False, "msg": "Conselho não encontrado."}), 404
        conselho.nome = nome
        conselho.data_inicio = dt_ini
        conselho.data_fim = dt_fim
        conselho.conselho_final = conselho_final
        conselho.periodo_letivo_id = periodo_letivo_id
    else:
        conselho = PeriodoConselho(
            nome=nome,
            data_inicio=dt_ini,
            data_fim=dt_fim,
            conselho_final=conselho_final,
            periodo_letivo_id=periodo_letivo_id,
            unidade_id=unidade_id
        )
        db.session.add(conselho)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Erro ao salvar período de conselho.")
        return jsonify({"success": False, "msg": "Erro interno ao salvar. Tente novamente."}), 500
    return jsonify({"success": True})


@bp.route('/api/conselho-periodo/<int:conselho_id>', methods=['DELETE'])
@csrf.exempt
@login_required
def deletar_periodo_conselho(conselho_id):
    unidade_id = get_unidade_id()
    conselho = PeriodoConselho.query.filter_by(id=conselho_id, unidade_id=unidade_id).first()
    if not conselho:
        return jsonify({"success": False, "msg": "Conselho não encontrado."}), 404

    try:
        db.session.delete(conselho)
        db.session.commit()
    except Exception:
        db.session.rollback()
        logger.exception("Erro ao deletar período de conselho.")
        return jsonify({"success": False, "msg": "Erro interno ao excluir. Tente novamente."}), 500
    return jsonify({"success": True})
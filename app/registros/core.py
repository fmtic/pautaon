"""
================================================================================
CORE.PY - Registros pedagógicos (registros legados, painel do professor,
          frequência, cursos, planejamento, níveis e temas)
================================================================================

NOTA ONDA 2B (limpeza)
    Comparações de `current_user.role` usam `UserRole` do `app.models.enums`
    em vez de strings soltas. Autocomplete e rename seguro.
================================================================================
"""

from flask import current_app, flash, render_template, url_for, request, redirect, abort, jsonify
from flask_login import login_required, current_user
from sqlalchemy import select, func, or_, cast, String
from sqlalchemy.exc import IntegrityError
from werkzeug.exceptions import HTTPException
from datetime import datetime, date

from app.database import db
from app.models import (
    Registro,
    Turma,
    TurmaCurso,
    Aluno,
    Frequencia,
    TemaAula,
    ConfiguracaoSistema,
    PeriodoLetivo,
    Inscricao,
    Curso,
    ValorEsportista,
)
from app.models.enums import UserRole
from app.utils.datetime_parse import parse_date
from app.utils.formatters import formatar_ch
from app.utils.timezone import get_local_now
from app.utils.logica import (
    PendenciaValorAula,
    ValorAulaInvalido,
    calcular_dias_aula_turma,
    calcular_estatisticas_frequencia,
    carregar_contexto_turma,
    carregar_frequencias_e_valores,
    get_unidade_id,
    salvar_frequencia,
    _blocked_dates_str,
)
from app.services.turma_curso import (
    datas_aula_oferta,
    ofertas_ativas,
    resolver_oferta_lancamento,
    _alunos_da_oferta,
)
from app.services.turma_curso_horario import grades_para_exibicao
from . import bp
from .shared import assert_unidade_context


# ---------------------------------------------------------------------------
# ABAS DO PLANEJAMENTO — preservar a aba (e os filtros) após uma escrita
# ---------------------------------------------------------------------------
_ABAS_PLANEJAMENTO = ('temas', 'valores', 'niveis')


def _aba_planejamento(valor) -> str | None:
    """Normaliza a aba do planejamento; `None` quando não é uma aba válida."""
    aba = (valor or '').strip().lower()
    return aba if aba in _ABAS_PLANEJAMENTO else None


def _voltar_planejamento(aba=None):
    """Redirect pós-escrita mantendo a aba e os filtros da aba Temas.

    A aba vem do `hidden` `aba` (ou do argumento) e os filtros do contexto em
    que o formulário foi aberto (`filtro_curso`, `filtro_q`, `filtro_page`).
    Tudo passa por whitelist/validação: valor inválido cai na aba padrão
    (Temas) sem querystring, como o redirect antigo fazia.
    """
    aba = _aba_planejamento(aba) or _aba_planejamento(request.form.get('aba'))
    params = {}
    if aba and aba != 'temas':
        params['aba'] = aba

    curso_id = (request.form.get('filtro_curso') or '').strip()
    if curso_id.isdigit():
        params['curso_id'] = int(curso_id)
    termo = (request.form.get('filtro_q') or '').strip()
    if termo:
        params['q'] = termo
    pagina = (request.form.get('filtro_page') or '').strip()
    if pagina.isdigit() and int(pagina) > 1:
        params['page'] = int(pagina)

    return redirect(url_for('registros.planejamento', **params))


def _valor_esportista_duplicado(
    nome: str, unidade_id: int | None, ignorar_id: int | None = None,
) -> bool:
    """Já existe valor com esse nome na unidade? (sem diferenciar maiúsculas).

    Espelha o índice funcional `uix_valor_esportista_nome_unidade`
    (`lower(nome)`, `unidade_id`) para devolver mensagem amigável antes do
    `IntegrityError`. `ignorar_id` permite renomear o próprio registro.
    """
    if unidade_id is None:
        return False
    query = ValorEsportista.query.filter(
        ValorEsportista.unidade_id == unidade_id,
        func.lower(ValorEsportista.nome) == nome.lower(),
    )
    if ignorar_id is not None:
        query = query.filter(ValorEsportista.id != ignorar_id)
    return query.first() is not None


# ---------------------------------------------------------------------------
# FORMULÁRIO PRINCIPAL DE REGISTRO (Legacy Support)
# ---------------------------------------------------------------------------
# AJ6-B7: a rota `/form` foi REMOVIDA como código morto. Ela renderizava
# `form.html` na raiz de `templates/` — arquivo que não existe (500
# TemplateNotFound até para o pedagógico, o único papel liberado pela guarda
# do AJ6-B6). Sem chamadores: nenhum `url_for('registros.form')` em
# templates/JS/menu, nenhuma referência em `<a href>`/`fetch` (prova grep no
# relatório AJ6B7). As irmãs `editar`/`excluir` abaixo eram as únicas
# chamadoras internas e passaram a redirecionar ao painel canônico.


@bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
def editar(id):
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    registro = db.get_or_404(Registro, id)

    if request.method == 'POST':
        try:
            registro.turma = request.form['turma']
            registro.mes   = request.form['mes']
            registro.turno = request.form['turno']
            db.session.commit()
            flash("Atualização do Registro Efetivada", "success")
            # AJ6-B7: destino era `registros.form` (rota removida — código
            # morto que além de tudo caía no 500 do template ausente).
            return redirect(url_for('main.painel'))
        except Exception:
            db.session.rollback()
            flash("Conflito interno ao gravar nova string JSON.", "danger")

    return render_template('editar.html', registro=registro)


@bp.route('/excluir/<int:id>', methods=['POST'])
@login_required
def excluir(id):
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    try:
        registro = db.get_or_404(Registro, id)
        db.session.delete(registro)
        db.session.commit()
    except Exception:
        db.session.rollback()
        flash("O banco recusou a deleção do bloco de registro.", "warning")

    # AJ6-B7: destino era `registros.form` (rota removida — código morto).
    return redirect(url_for('main.painel'))


# ---------------------------------------------------------------------------
# PROFESSORES (Fluxo de Sala de Aula)
# ---------------------------------------------------------------------------
@bp.route('/professor/painel')
@login_required
def painel_professor():
    """Rota legada do painel do professor: apenas redireciona para a canônica.

    Esta view montava um contexto próprio para `dashboard/professor.html`
    (`turmas`, `total_alunos`, `lista_programas`, `programa_ativo`,
    `is_readonly`), mas o template consome `entradas`, `aulas_pendentes` e
    `dias_bloqueados` — montados só por `main.painel`
    (`render_dashboard_professor`). Pela rota legada o painel abria com
    "Minhas Turmas" vazia e sem os cards laterais. A montagem duplicada foi
    removida (solução B da unificação das duas rotas); o filtro de programa e
    o `is_readonly` que ela oferecia nunca foram lidos pelo template.

    O destino roteia por perfil: professor vê o painel completo, admin /
    gerência / pedagógico o painel gerencial e secretaria o painel dela.
    """
    return redirect(url_for('main.painel'))


_NOMES_MESES = {
    '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
    '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
    '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro',
}


def _meses_disponiveis(datas_iso: list) -> list:
    """Meses (numero, nome) presentes numa lista de datas 'YYYY-MM-DD', em ordem.

    Espelha os `meses_disponiveis` de `carregar_contexto_turma`, mas para o
    calendário filtrado de uma oferta (seletor "Data da Aula").
    """
    meses, vistos = [], set()
    for dia in sorted(datas_iso):
        mes_num = dia[5:7]
        if mes_num not in vistos:
            meses.append({
                'numero': mes_num,
                'nome': _NOMES_MESES.get(mes_num, 'Mês Desconhecido'),
            })
            vistos.add(mes_num)
    return meses


@bp.route('/frequencia', methods=['GET', 'POST'])
@login_required
def frequencia():
    """
    Controlador de Submissões em Lote do Diário Online.
    Utiliza Atomic Transactions oriundas do utilitário logica.py.
    """
    if current_user.role not in (
        UserRole.ADMIN, UserRole.PEDAGOGICO,
        UserRole.PROFESSOR, UserRole.SECRETARIA,
    ):
        abort(403)

    if request.method == 'POST':
        if current_user.role == UserRole.SECRETARIA:
            abort(403)

        turma_post_id = request.form.get('turma', '')
        if current_user.role == UserRole.PROFESSOR and turma_post_id:
            # E3 (I1): só lança na pauta quem é professor de alguma OFERTA ativa
            # desta turma (regra por oferta, sem herdar `turma.professor_id`).
            from app.services.aluno_info_professor import (
                professor_de_alguma_oferta_ativa,
            )

            turma_post = db.session.get(Turma, int(turma_post_id)) if turma_post_id.isdigit() else None
            if not turma_post or not professor_de_alguma_oferta_ativa(
                turma_post.id, current_user
            ):
                abort(403)

        data_post = (request.form.get('data') or request.form.get('data_hidden') or '').strip()

        # Onda 4 (Fase 4, D2): resolve a oferta ANTES de gravar.
        # Decisão do responsável: com 2+ ofertas ativas a escolha é exigida e
        # a oferta passa validação completa (vigência, dia da grade, tema de
        # outro curso) — data fora da grade/vigência é BLOQUEADA. Com oferta
        # única (ou sem oferta) não há validação extra: o resolver é chamado
        # sem turma_curso_id e apenas escolhe a oferta automaticamente /
        # cai no legado. O hidden `turma_curso` enviado pela tela com oferta
        # única é ignorado de propósito aqui. ValueError → flash com a
        # mensagem e retorno sem gravar.
        oferta_raw_post = (request.form.get('turma_curso') or '').strip()
        oferta_id_post = int(oferta_raw_post) if oferta_raw_post.isdigit() else None
        temas_raw_post = request.form.getlist('tema_ids')
        if not temas_raw_post:
            tema_raw_post = (request.form.get('tema_id') or '').strip()
            temas_raw_post = [tema_raw_post] if tema_raw_post else []
        if any(not valor.isdigit() or int(valor) <= 0 for valor in temas_raw_post):
            flash('Um ou mais temas selecionados são inválidos.', 'warning')
            return redirect(url_for('registros.frequencia', turma_id=turma_post_id or ''))
        tema_ids_post = list(dict.fromkeys(
            int(valor) for valor in temas_raw_post
        ))
        data_alvo_post = parse_date(data_post)

        redirect_back = {'turma_id': turma_post_id, 'data': data_post}
        if oferta_id_post:
            redirect_back['turma_curso'] = oferta_id_post

        oferta_post = None
        ativas_todas_post = (
            ofertas_ativas(int(turma_post_id)) if turma_post_id.isdigit() else []
        )
        # AJ6-B: só o professor da OFERTA escreve nela (sem "professor da
        # turma"). A exigência de escolha e a autoescolha consideram apenas as
        # ofertas dele; numa turma com outras ofertas, a dele é amarrada ao
        # resolver. A guarda final abaixo confirma a oferta resolvida.
        from app.services.aluno_info_professor import (
            ofertas_do_professor,
            professor_pode_acessar_oferta,
        )

        if current_user.role == UserRole.PROFESSOR:
            ativas_post = ofertas_do_professor(current_user, ativas_todas_post)
            if len(ativas_post) == 1 and oferta_id_post is None:
                oferta_id_post = ativas_post[0].id
        else:
            ativas_post = ativas_todas_post
        exigir_validacao_oferta = len(ativas_post) >= 2
        if turma_post_id.isdigit() and data_alvo_post:
            try:
                if current_user.role == UserRole.PROFESSOR:
                    # Sempre amarra a oferta (a dele, já resolvida acima) para
                    # que o auto-resolver não escolha uma oferta de outro
                    # professor numa turma com 2+ ofertas.
                    resolver_curso_id = oferta_id_post
                else:
                    resolver_curso_id = (
                        oferta_id_post if exigir_validacao_oferta else None
                    )
                oferta_post = resolver_oferta_lancamento(
                    int(turma_post_id), data_alvo_post,
                    turma_curso_id=resolver_curso_id,
                    tema_ids=tema_ids_post,
                )
            except ValueError as exc:
                flash(str(exc), 'warning')
                return redirect(url_for('registros.frequencia', **redirect_back))

        # AJ6-B: guarda FINAL por OFERTA — mesmo que o resolver tenha
        # devolvido uma oferta, o professor só escreve na dele. Nega 403 sem
        # gravar. Demais perfis: `professor_pode_acessar_oferta` devolve True.
        # Quando `oferta_post` é None (sem data no form, caminho que ainda vai
        # cair na validação de data de `salvar_frequencia`), não há oferta para
        # negar: a guarda de adesão acima já garantiu que ele leciona alguma
        # oferta ativa da turma, e nada é gravado sem data.
        if (
            current_user.role == UserRole.PROFESSOR
            and oferta_post is not None
            and not professor_pode_acessar_oferta(current_user, oferta_post)
        ):
            abort(403)

        if turma_post_id.isdigit() and data_post:
            # AJ16-E: a data precisa pertencer ao MESMO calendário que a tela
            # oferece no <select name="data"> — com oferta resolvida é a grade
            # da oferta (`datas_aula_oferta`, mesma fonte de `situacao_datas` e
            # do seletor do GET); sem oferta é o calendário legado da turma
            # (`gerar_datas` via `carregar_contexto_turma`). Antes o POST
            # validava sempre contra o calendário da turma, o que rejeitava
            # datas legítimas da oferta — inclusive a "próxima pendente" —
            # quando a vigência da oferta divergia da vigência da turma (ou a
            # turma não tinha vigência própria).
            contexto_post = carregar_contexto_turma(int(turma_post_id))
            if oferta_post is not None:
                datas_lancaveis = {
                    dia.strftime('%Y-%m-%d')
                    for dia in datas_aula_oferta(
                        oferta_post,
                        limite=get_local_now().date(),
                        blocked=_blocked_dates_str(contexto_post['turma']),
                    )
                }
            else:
                datas_lancaveis = set(contexto_post.get('datas', []))
            if data_post not in datas_lancaveis:
                flash(
                    'A data informada não pertence ao calendário válido da turma.',
                    'warning',
                )
                return redirect(url_for('registros.frequencia', **redirect_back))

        form_data = request.form
        if oferta_post is not None:
            # Rejeita lançamentos de alunos fora da pauta da oferta: chaves
            # aluno_<id> fora da pauta são ignorados e contabilizados no log.
            # A pauta segue a mesma regra do GET: inscrição sempre apontada
            # para a oferta (Inscricao.turma_curso_id NOT NULL desde a Onda 4).
            permitidos = {
                a.id for a in _alunos_da_oferta(
                    int(turma_post_id), oferta_post.id,
                )
            }
            # Mantém os campos repetidos (`tema_ids`) ao fazer a cópia mutável
            # usada para remover alunos que não pertencem à pauta da oferta.
            form_data = request.form.copy()
            if current_user.role == UserRole.PROFESSOR:
                # AJ6-B: amarra a oferta dele (já conferida pela guarda final)
                # para que o resolver interno de `salvar_frequencia` grave
                # exatamente nela — nunca numa oferta de outro professor.
                form_data['turma_curso'] = str(oferta_post.id)
            elif not exigir_validacao_oferta:
                # Oferta única: retira o id do form para que o resolver
                # interno de salvar_frequencia reautoescolha a mesma oferta
                # sem validação extra (decisão D2 — sem dupla checagem de
                # vigência/dia no caminho de oferta única).
                form_data.pop('turma_curso', None)
            ignorados = 0
            for chave in list(form_data.keys()):
                # `valor_ids` é da AULA (não do aluno), então nunca sai junto.
                if chave.startswith('aluno_'):
                    aluno_raw = chave[len('aluno_'):]
                    if aluno_raw.isdigit() and int(aluno_raw) not in permitidos:
                        form_data.pop(chave)
                        ignorados += 1
            if ignorados:
                current_app.logger.warning(
                    'Frequência: %s lançamento(s) ignorado(s) fora da pauta da '
                    'oferta %s (turma %s)',
                    ignorados, oferta_post.id, turma_post_id,
                )

        try:
            turma_id, data = salvar_frequencia(form_data)
        except (PendenciaValorAula, ValorAulaInvalido) as exc:
            # AJ16-B: nada foi gravado (nem conceitos, nem diário, nem valores).
            flash(str(exc), 'warning')
            return redirect(url_for('registros.frequencia', **redirect_back))
        if not data:
            if data_post:
                # AJ16-E: a data foi enviada e já passou pela validação de
                # calendário — um retorno sem data aqui só acontece por uma
                # exceção interna de `salvar_frequencia` (já registrada no
                # log). Não é "falta de data": mostra erro honesto em vez da
                # mensagem enganosa "Preencha a data da aula antes de salvar.".
                flash(
                    'Não foi possível salvar a frequência. Tente novamente.',
                    'danger',
                )
            else:
                flash("Preencha a data da aula antes de salvar.", "warning")
            return redirect(url_for('registros.frequencia', turma_id=turma_post_id or ''))

        flash('Frequência salva com sucesso!', 'success')
        params = {'turma_id': turma_id, 'data': data}
        if oferta_id_post:
            params['turma_curso'] = oferta_id_post
        return redirect(url_for('registros.frequencia', **params))

    turma_id_raw = request.args.get('turma_id')
    turma_id = int(turma_id_raw) if turma_id_raw and str(turma_id_raw).isdigit() else None
    data     = request.args.get('data')
    oferta_raw = request.args.get('turma_curso')
    oferta_id_param = (
        int(oferta_raw) if oferta_raw and str(oferta_raw).isdigit() else None
    )

    unidade_id = get_unidade_id()

    if current_user.role == UserRole.PROFESSOR:
        # E3 (I1): a lista de turmas do professor é quem tem OFERTA ativa dele
        # (sem herdar `turma.professor_id`); admin e gestão seguem no else.
        from app.services.aluno_info_professor import condicao_professor_da_oferta

        stmt = (
            select(Turma)
            .join(TurmaCurso, TurmaCurso.turma_id == Turma.id)
            .where(
                Turma.ativo == True,
                TurmaCurso.ativo.is_(True),
                condicao_professor_da_oferta(current_user.id),
            )
            .distinct()
        )
        if unidade_id:
            stmt = stmt.where(Turma.unidade_id == unidade_id)
        turmas = db.session.execute(stmt.order_by(Turma.ordenacao, Turma.nome)).scalars().all()
    else:
        turmas = Turma.get_ativas()
        if unidade_id:
            turmas = [t for t in turmas if t.unidade_id == unidade_id]

    if turma_id and current_user.role == UserRole.PROFESSOR:
        turma_ids_permitidos = {t.id for t in turmas}
        if turma_id not in turma_ids_permitidos:
            flash('Você não tem permissão para acessar esta turma.', 'danger')
            return redirect(url_for('registros.frequencia'))

    ctx = {}
    freqs = {}
    tema_sel = []
    obs = ""
    ofertas = []
    oferta_atual = None
    exigir_escolha = False
    valores_aula = []
    atividades_salvas = ""

    if turma_id:
        # Onda 4 (Fase 4, D2): 0 ofertas ativas = legado (pauta por turma);
        # exatamente 1 = uso automático sem seletor; 2+ = exige escolha do
        # curso antes de carregar a pauta (sem escolha, não lista alunos).
        #
        # AJ6-B: não existe mais "professor da turma" — só o professor da
        # OFERTA (TurmaCurso.professor_id). O seletor e a autoescolha usam
        # apenas as ofertas dele; as demais nem aparecem. Pedir oferta alheia
        # de forma explícita é negado (403), sem revelar se ela existe.
        # A estatística por oferta (abaixo) continua decidida pelo TOTAL de
        # ofertas ativas da turma, para não misturar linhas de outra oferta.
        from app.services.aluno_info_professor import (
            ofertas_do_professor,
        )

        ofertas_todas = ofertas_ativas(turma_id)
        ofertas = ofertas_do_professor(current_user, ofertas_todas)
        # AJ6-B: o professor que pede explicitamente uma oferta fora das dele
        # recebe 403, com quantas ofertas próprias ele tenha (a oferta alheia
        # não é autoescolhida nem considerada). Demais perfis: inalterados.
        if (
            current_user.role == UserRole.PROFESSOR
            and oferta_id_param is not None
            and oferta_id_param not in {o.id for o in ofertas}
        ):
            abort(403)
        if len(ofertas) == 1:
            oferta_atual = ofertas[0]
        elif len(ofertas) >= 2:
            if oferta_id_param:
                oferta_atual = next(
                    (o for o in ofertas if o.id == oferta_id_param), None
                )
                if oferta_atual is None:
                    if current_user.role == UserRole.PROFESSOR:
                        # Oferta que não é dele → nega (403) sem vazar.
                        abort(403)
                    flash('Curso selecionado inválido para esta turma.', 'warning')
                    return redirect(url_for('registros.frequencia', turma_id=turma_id))
            else:
                exigir_escolha = True
            # ETAPA L1 (A3): o aviso "sem curso definido" (contador de
            # inscrições com turma_curso_id NULL) foi removido — código morto
            # desde o NOT NULL de Inscricao.turma_curso_id (c3d4e5f6a7b8).

        ctx = carregar_contexto_turma(turma_id)
        if exigir_escolha:
            ctx['alunos'] = []
            ctx['temas'] = []
            # AJ6-B4: só para o PROFESSOR. Sem curso escolhido, o calendário da
            # turma é a união de TODAS as ofertas (inclusive as que ele não
            # leciona) e poderia nascer link de pauta sem turma_curso (403).
            # Zerar datas/meses fecha isso; o seletor de oferta continua e
            # escolher o curso reabre o calendário da oferta. Admin/pedagógico
            # etc. mantêm a união da turma (a rota deles não vaza oferta alheia;
            # comportamento V3a inalterado).
            if current_user.role == UserRole.PROFESSOR:
                ctx['datas'] = []
                ctx['meses'] = []
        elif oferta_atual is not None:
            # Pauta da oferta: inscrição sempre apontada para a oferta
            # (Inscricao.turma_curso_id NOT NULL desde a Onda 4). Temas são os
            # do curso da oferta (coerente com a validação de tema do resolver).
            ctx['alunos'] = _alunos_da_oferta(
                turma_id, oferta_atual.id,
            )
            ctx['temas'] = TemaAula.query.filter_by(
                curso_id=oferta_atual.curso_id, ativo=True
            ).all()

        # T2 (29/10/2026): com oferta escolhida (2+ ofertas) ou única automática,
        # o seletor "Data da Aula" lista SOMENTE as datas do calendário da oferta
        # até hoje (vigência + grade, feriados/dias bloqueados descontados —
        # `datas_aula_oferta`, mesma fonte das marcas/resumo da V3a). Sem oferta
        # escolhida em 2+ (exigir_escolha) e turma sem oferta ativa (legado) seguem
        # com a união da turma, como antes. A validação do POST não é tocada.
        if oferta_atual is not None and not exigir_escolha:
            datas_calendario = [
                dia.strftime('%Y-%m-%d')
                for dia in datas_aula_oferta(
                    oferta_atual, limite=get_local_now().date(),
                    blocked=_blocked_dates_str(ctx['turma']),
                )
            ]
            ctx['datas'] = datas_calendario
            ctx['meses'] = _meses_disponiveis(datas_calendario)
            if data and data not in datas_calendario:
                # Data fora do calendário da oferta (ex.: troca de oferta):
                # cai na data mais recente da oferta, sem erro.
                data = datas_calendario[-1] if datas_calendario else None

        if data and not exigir_escolha:
            # AJ16-B: conceitos + valores da AULA (N:N no diário) na mesma
            # leitura da pauta; a relação `valores` é `selectin`.
            freqs, valores_aula, tema_sel, obs, atividades_salvas = (
                carregar_frequencias_e_valores(
                    turma_id, data,
                    turma_curso_id=oferta_atual.id if oferta_atual else None,
                )
            )

        # ETAPA D3b.2: estatísticas em lote — o loop anterior fazia 2 queries
        # por aluno (N+1) e tinha um fallback morto (`turma_id=None`, coluna
        # NOT NULL). Mesma semântica: estatísticas POR TURMA (todas as linhas
        # do aluno na turma, como na tela antiga), primeira inscrição define
        # se o aluno pode receber frequência.
        alunos_ctx = ctx.get('alunos', [])
        aluno_ids = [a.id for a in alunos_ctx]
        # ETAPA D3b-2.4: estatísticas por oferta em turma com 2+ ofertas.
        # 0 ou 1 oferta: inalterado (todas as linhas, inclui legado NULL).
        # AJ6-B: usa o TOTAL de ofertas ativas (não as visíveis ao professor),
        # para que a pauta de uma oferta nunca traga linhas de outra oferta.
        somente_oferta = (
            len(ofertas_todas) >= 2 and oferta_atual is not None
        )
        conceitos_por_aluno: dict = {}
        if aluno_ids:
            from app.services.frequencia_oferta import (
                conceitos_frequencia_por_aluno,
            )

            conceitos_por_aluno = conceitos_frequencia_por_aluno(
                aluno_ids,
                turma_id,
                oferta_id=oferta_atual.id if oferta_atual is not None else None,
                somente_oferta=somente_oferta,
            )
            inscricoes_por_aluno: dict = {}
            for insc in (
                Inscricao.query
                .filter(Inscricao.aluno_id.in_(aluno_ids),
                        Inscricao.turma_id == turma_id)
                .order_by(Inscricao.id)
                .all()
            ):
                # primeira inscrição (menor id) manda, como o .first() antigo
                inscricoes_por_aluno.setdefault(insc.aluno_id, insc)
            for aluno in alunos_ctx:
                estatisticas = calcular_estatisticas_frequencia(
                    conceitos_por_aluno.get(aluno.id, [])
                )
                aluno.estats_freq = type('E', (), {
                    'presenca': estatisticas['presenca_percentual'],
                    'falta': estatisticas['falta_percentual'],
                    'justificada': estatisticas['justificada_percentual'],
                    'justificadas': estatisticas['justificadas'],
                    'total_aulas': estatisticas['total'],
                })()
                insc = inscricoes_por_aluno.get(aluno.id)
                aluno.pode_receber_frequencia = bool(insc and insc.ativo)

    # A1: opções do seletor de Valor do Esportista — SEMPRE ativas, no escopo
    # da unidade da turma (a sessão pode estar em Visão Global). Um valor
    # inativo já gravado entra como opção extra no loop do template.
    escopo_valores = (
        ctx.get('turma').unidade_id if ctx.get('turma') else unidade_id
    )
    q_valores = ValorEsportista.query.filter(ValorEsportista.ativo.is_(True))
    if escopo_valores:
        q_valores = q_valores.filter(ValorEsportista.unidade_id == escopo_valores)
    valores_esportista_ativos = q_valores.order_by(
        func.lower(ValorEsportista.nome)
    ).all()

    # I1: ícone "Informações para o professor". Só para PROFESSOR e só para
    # aluno com inscrição qualificada E pelo menos um bloco preenchido — uma
    # consulta para a pauta inteira (sem N+1).
    alunos_com_info: set[int] = set()
    if current_user.role == UserRole.PROFESSOR:
        alunos_do_ctx = [aluno.id for aluno in ctx.get('alunos', [])]
        if alunos_do_ctx:
            from app.services.aluno_info_professor import (
                alunos_com_info_professor,
            )

            alunos_com_info = alunos_com_info_professor(
                alunos_do_ctx, current_user,
            )

    # V3a: datas já lançadas / pendentes da oferta selecionada (mesma definição
    # das pendências do dashboard) e coerência do botão Imprimir.
    from app.utils.dias_semana import weekday_para_abrev
    from app.utils.frequencia import situacao_datas_oferta

    situacao_datas = {
        "status": {},
        "lancadas": 0,
        "total_ate_hoje": 0,
        "pendentes": 0,
        "proxima_pendente": None,
    }
    if oferta_atual is not None and not exigir_escolha and ctx.get('turma'):
        situacao_datas = situacao_datas_oferta(ctx['turma'], oferta_atual)

    # Abreviação do dia da semana de cada data do seletor ("Seg", "Qua"...).
    dias_abrev = {}
    for dia_iso in ctx.get('datas', []):
        try:
            dias_abrev[dia_iso] = weekday_para_abrev(
                date.fromisoformat(dia_iso).weekday()
            )
        except ValueError:
            continue

    # V3a (R10): o botão Imprimir só aparece quando a impressão é permitida —
    # 2+ ofertas sem escolha ou professor que não é o professor da oferta
    # (a guarda da impressão é por OFERTA, sem herdar o professor da turma).
    # G1-4: exigir_escolha vai ao template para esconder o botão também
    # enquanto o curso não foi escolhido (nenhum link sai sem turma_curso).
    pode_imprimir_pauta = True
    if len(ofertas) >= 2 and oferta_atual is None:
        pode_imprimir_pauta = False
    elif current_user.role == UserRole.PROFESSOR:
        from app.services.aluno_info_professor import professor_da_oferta

        if oferta_atual is None or not professor_da_oferta(
            oferta_atual, current_user
        ):
            pode_imprimir_pauta = False

    return render_template('frequencia/lancar.html',
                           alunos_com_info=alunos_com_info,
                           turmas=turmas,
                           turma_id=turma_id,
                           data=data,
                           frequencias=freqs,
                           valores_esportista_ativos=valores_esportista_ativos,
                           valores_aula=valores_aula,
                           valores_aula_ids={v.id for v in valores_aula},
                           valores_aula_inativos=[
                               v for v in valores_aula if not v.ativo
                           ],
                           # V2: aviso "Cadastre os valores no Planejamento" só
                           # para quem gerencia o planejamento (mesmos perfis da
                           # rota /planejamento, onde o catálogo é cadastrado).
                           pode_gerenciar_planejamento=current_user.role in (
                               UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA,
                           ),
                           tema_selecionado=tema_sel or [],
                           obs_salva=obs,
                           atividades_salvas=atividades_salvas,
                           turma=ctx.get('turma'),
                           alunos=ctx.get('alunos', []),
                           datas=ctx.get('datas', []),
                           temas=ctx.get('temas', []),
                           meses=ctx.get('meses', []),
                           ofertas=ofertas,
                           # H3e: horário do seletor de oferta pela grade.
                           grade_oferta_map=grades_para_exibicao(ofertas),
                           oferta_atual=oferta_atual,
                           exigir_escolha=exigir_escolha,
                           situacao_datas=situacao_datas,
                           dias_abrev=dias_abrev,
                           pode_imprimir_pauta=pode_imprimir_pauta,
                           is_readonly=current_user.role == UserRole.SECRETARIA)


@bp.route('/frequencia_relatorio')
@login_required
def frequencia_relatorio():
    if current_user.role != UserRole.PEDAGOGICO:
        abort(403)

    # D3b.2: `type=int` — antes, `?turma=abc` chegava cru e o `int(turma_id)`
    # de baixo derrubava a página com 500; valor inválido agora é None.
    turma_id = request.args.get('turma', type=int)

    # Onda 2A: Frequencia.data é `date`. Os parâmetros da URL chegam como
    # string e precisam ser normalizados antes de filtrar, senão o filtro
    # nunca casa (date == str).
    data_inicio_raw = request.args.get('inicio')
    data_fim_raw = request.args.get('fim')
    data_inicio = parse_date(data_inicio_raw)
    data_fim = parse_date(data_fim_raw)

    unidade_id = get_unidade_id()
    turmas_query = Turma.query.filter_by(ativo=True)
    if unidade_id:
        turmas_query = turmas_query.filter_by(unidade_id=unidade_id)
    turmas = turmas_query.order_by(Turma.nome).all()
    resultado         = []
    turma_selecionada = None

    if turma_id:
        turma_selecionada = next(
            (turma for turma in turmas if turma.id == turma_id), None
        )
        if not turma_selecionada:
            abort(404)
        # .distinct(): aluno com inscrição ativa em 2+ ofertas da mesma turma
        # aparecia duplicado na lista do relatório (uma linha por inscrição).
        alunos = db.session.execute(
            select(Aluno)
            .distinct()
            .join(Inscricao, Inscricao.aluno_id == Aluno.id)
            .where(
                Inscricao.turma_id == turma_selecionada.id,
                Inscricao.ativo == True,
                Aluno.ativo == True,
            )
            .order_by(Aluno.nome)
        ).scalars().all()

        for aluno in alunos:
            stmt = select(Frequencia.conceito).where(
                Frequencia.aluno_id == aluno.id,
                Frequencia.turma_id == turma_selecionada.id,
            )
            if data_inicio:
                stmt = stmt.where(Frequencia.data >= data_inicio)
            if data_fim:
                stmt = stmt.where(Frequencia.data <= data_fim)

            estatisticas = calcular_estatisticas_frequencia(
                db.session.execute(stmt).scalars().all()
            )

            resultado.append({
                "nome": aluno.nome,
                "total": estatisticas['total'],
                "presencas": estatisticas['presencas'],
                "justificadas": estatisticas['justificadas'],
                "percentual": estatisticas['presenca_percentual'],
            })

    # Preserva as strings originais no template (inputs type="date" esperam string).
    return render_template('frequencia/relatorio.html',
                           dados=resultado,
                           turmas=turmas,
                           turma_id=turma_id,
                           turma_selecionada=turma_selecionada,
                           inicio=data_inicio_raw or '',
                           fim=data_fim_raw or '')


# ---------------------------------------------------------------------------
# CURSOS
# ---------------------------------------------------------------------------

@bp.route('/cursos', methods=['GET'])
@login_required
def listar_cursos():
    """Retorna JSON com os cursos da unidade — usado pelo modal de planejamento."""
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        abort(403)
    cursos = Curso.query.filter_by(ativo=True, unidade_id=unidade_id).order_by(Curso.nome).all()
    return jsonify([
        {
            'id': c.id,
            'nome': c.nome,
            'descricao': c.descricao or '',
        }
        for c in cursos
    ])


@bp.route('/cursos/inativos', methods=['GET'])
@login_required
def listar_cursos_inativos():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        abort(403)
    cursos = Curso.query.filter_by(
        ativo=False,
        unidade_id=unidade_id,
    ).order_by(Curso.nome).all()
    return jsonify([
        {
            'id': curso.id,
            'nome': curso.nome,
            'descricao': curso.descricao or '',
        }
        for curso in cursos
    ])


@bp.route('/cursos/novo', methods=['POST'])
@login_required
def novo_curso():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    if not unidade_id:
        return jsonify({'success': False, 'message': 'Usuário sem unidade definida.'}), 400

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Dados do curso inválidos.'}), 400
    nome = data.get('nome')
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400
    nome = nome.strip()
    descricao = data.get('descricao')
    descricao = descricao.strip() if isinstance(descricao, str) else ''

    curso = Curso(
        nome=nome,
        descricao=descricao or None,
        unidade_id=unidade_id
    )
    try:
        db.session.add(curso)
        db.session.commit()
        return jsonify({
            'success': True,
            'id': curso.id,
            'nome': curso.nome,
            'descricao': curso.descricao or '',
            'dias_aula': 0,
            # Curso recém-criado não tem turmas ainda.
            'carga_total_fmt': '—',
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.novo_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


@bp.route('/cursos/<int:curso_id>/editar', methods=['POST'])
@login_required
def editar_curso(curso_id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA, UserRole.GERENCIA):
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    # ETAPA B3: isolamento por unidade vale para todos os perfis, inclusive
    # ADMIN/GERENCIA (que escolhem a unidade após o login; Visão Global é
    # somente leitura). Igual a inativar_curso/reativar_curso.
    assert_unidade_context(curso.unidade_id, unidade_id)
    if not curso.ativo:
        return jsonify({
            'success': False,
            'message': 'Reative o curso antes de editá-lo.',
        }), 409

    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({'success': False, 'message': 'Dados do curso inválidos.'}), 400
    nome = data.get('nome')
    if not isinstance(nome, str) or not nome.strip():
        return jsonify({'success': False, 'message': 'Nome é obrigatório.'}), 400
    nome = nome.strip()
    descricao = data.get('descricao')
    descricao = descricao.strip() if isinstance(descricao, str) else ''

    curso.nome = nome
    curso.descricao = descricao or None
    try:
        db.session.commit()
        dias = sum(calcular_dias_aula_turma(t) for t in curso.turmas if t.ativo)
        carga_fmt = formatar_ch(
            next(
                (t.carga_horaria_total for t in curso.turmas if t.ativo and t.carga_horaria_total),
                None,
            )
        )
        return jsonify({
            'success': True, 'id': curso.id, 'nome': curso.nome,
            'descricao': curso.descricao or '',
            'dias_aula': dias,
            'carga_total_fmt': carga_fmt,
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.editar_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


@bp.route('/cursos/<int:curso_id>/inativar', methods=['POST'])
@login_required
def inativar_curso(curso_id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    assert_unidade_context(curso.unidade_id, unidade_id)

    if not curso.ativo:
        return jsonify({
            'success': False,
            'message': 'Este curso já está inativo.',
        }), 409

    curso.ativo = False
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'message': 'Curso inativado. Os temas e o histórico foram preservados.',
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.inativar_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


@bp.route('/cursos/<int:curso_id>/reativar', methods=['POST'])
@login_required
def reativar_curso(curso_id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, curso_id)
    assert_unidade_context(curso.unidade_id, unidade_id)

    if curso.ativo:
        return jsonify({
            'success': False,
            'message': 'Este curso já está ativo.',
        }), 409

    curso.ativo = True
    try:
        db.session.commit()
        return jsonify({
            'success': True,
            'id': curso.id,
            'nome': curso.nome,
            'descricao': curso.descricao or '',
            'dias_aula': 0,
            'carga_total_fmt': '—',
        })
    except Exception as e:
        db.session.rollback()
        from app.utils.errors import log_error_code

        code = log_error_code(e, location='registros.reativar_curso', hint='db')
        return jsonify({'success': False, 'message': 'Erro interno. Contate o suporte.', 'code': code}), 500


# ---------------------------------------------------------------------------
# PLANEJAMENTO DE TEMAS
# ---------------------------------------------------------------------------

@bp.route('/planejamento', methods=['GET', 'POST'])
@login_required
def planejamento():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)

    unidade_id = get_unidade_id()
    if current_user.role == UserRole.SECRETARIA and unidade_id is None:
        abort(403)

    if request.method == 'POST':
        tipo_post = request.form.get('tipo_post', 'tema')

        if tipo_post == 'nivel':
            from app.models import Nivel
            nome_nivel = request.form.get('nome_nivel', '').strip()
            if nome_nivel:
                nivel_unidade_id = get_unidade_id()
                # ETAPA B6: criar nível exige unidade efetiva na sessão; a
                # Visão Global (unidade None) é somente leitura, como nos
                # demais ramos de escrita do planejamento.
                assert_unidade_context(nivel_unidade_id, nivel_unidade_id)
                existente = Nivel.query.filter_by(
                    nome=nome_nivel,
                    unidade_id=nivel_unidade_id,
                ).first()
                if existente:
                    flash("Já existe um nível com esse nome nesta unidade.", 'warning')
                else:
                    try:
                        db.session.add(Nivel(
                            nome=nome_nivel,
                            ativo=True,
                            unidade_id=nivel_unidade_id,
                        ))
                        db.session.commit()
                        flash(f"Nível '{nome_nivel}' adicionado com sucesso!", 'success')
                    except Exception:
                        db.session.rollback()
                        flash("Erro ao salvar nível.", 'danger')
            else:
                flash("Informe o nome do nível.", 'warning')
            return _voltar_planejamento()

        if tipo_post == 'valor':
            # A1 — Valores do Esportista: catálogo usado no lançamento de
            # frequência como dado ADICIONAL (não entra em conta alguma).
            nome_valor = request.form.get('nome_valor', '').strip()
            valor_unidade_id = get_unidade_id()
            # Mesmo escopo do nível: escrever exige unidade efetiva; a Visão
            # Global (unidade None) é somente leitura.
            assert_unidade_context(valor_unidade_id, valor_unidade_id)
            if not nome_valor:
                flash("Informe o nome do valor.", 'warning')
            elif len(nome_valor) > 100:
                flash(
                    "O nome do valor deve ter no máximo 100 caracteres.",
                    'warning',
                )
            elif _valor_esportista_duplicado(nome_valor, valor_unidade_id):
                flash(
                    f"Já existe um valor com o nome '{nome_valor}' "
                    "nesta unidade.",
                    'warning',
                )
            else:
                try:
                    db.session.add(ValorEsportista(
                        nome=nome_valor,
                        ativo=True,
                        unidade_id=valor_unidade_id,
                    ))
                    db.session.commit()
                    flash(f"Valor '{nome_valor}' adicionado com sucesso!", 'success')
                except IntegrityError:
                    db.session.rollback()
                    flash(
                        "Já existe um valor com esse nome nesta unidade.",
                        'warning',
                    )
                except Exception:
                    db.session.rollback()
                    flash("Erro ao salvar valor.", 'danger')
            return _voltar_planejamento()

        curso_id  = request.form.get('curso_id')
        titulo_tema = request.form.get('titulo')
        if curso_id and titulo_tema:
            try:
                curso = db.get_or_404(Curso, int(curso_id))
                # ETAPA B4: isolamento por unidade vale para todos os perfis,
                # inclusive ADMIN (Visão Global é somente leitura).
                assert_unidade_context(curso.unidade_id, unidade_id)
                if not curso.ativo:
                    flash(
                        "Não é possível adicionar temas a um curso inativo. Reative-o primeiro.",
                        "warning",
                    )
                    return _voltar_planejamento()

                ultima_ordem = db.session.query(func.max(TemaAula.ordem)).filter_by(
                    curso_id=int(curso_id)
                ).scalar()
                nova_ordem = (ultima_ordem or 0) + 1

                db.session.add(TemaAula(
                    curso_id=int(curso_id),
                    titulo=titulo_tema,
                    ordem=nova_ordem,
                    unidade_id=get_unidade_id()
                ))
                db.session.commit()
                flash(f"Tema '{titulo_tema}' adicionado ao curso '{curso.nome if curso else ''}'!", "success")
            except HTTPException:
                # ETAPA B4: o 403 do assert_unidade_context (e o 404 do
                # get_or_404) devem chegar ao cliente — não podem ser
                # engolidos pelo except Exception genérico abaixo.
                raise
            except Exception as e:
                from app.utils.errors import flash_and_log

                db.session.rollback()
                flash_and_log(e, location='registros.planejamento_tema_salvar', hint='db')
        elif not curso_id:
            flash("Selecione um curso.", "warning")
        elif not titulo_tema:
            flash("Informe o título do tema.", "warning")
        return _voltar_planejamento()

    conf_i = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho').first()
    conf_f = ConfiguracaoSistema.query.filter_by(chave='fim_conselho').first()

    turmas = Turma.get_ativas()
    if unidade_id:
        turmas = [t for t in turmas if t.unidade_id == unidade_id]

    prog_filtro = request.args.get('programa', 'Todos')
    programas   = sorted({t.programa for t in turmas if t.programa})

    filtro_curso = request.args.get('curso_id', '').strip()
    try:
        curso_id_filtro = int(filtro_curso) if filtro_curso else None
    except ValueError:
        curso_id_filtro = None
        filtro_curso = ''
    busca_tema = request.args.get('q', '').strip()

    q_temas = TemaAula.query.join(Curso, TemaAula.curso_id == Curso.id).filter(
        TemaAula.curso_id.isnot(None),
        Curso.ativo.is_(True),
    )
    if unidade_id:
        q_temas = q_temas.filter(Curso.unidade_id == unidade_id)
    if curso_id_filtro:
        q_temas = q_temas.filter(TemaAula.curso_id == curso_id_filtro)
    if busca_tema:
        termo = f'%{busca_tema}%'
        q_temas = q_temas.filter(or_(
            TemaAula.titulo.ilike(termo),
            Curso.nome.ilike(termo),
            cast(TemaAula.ordem, String).ilike(termo),
        ))

    pagina_temas = max(1, request.args.get('page', 1, type=int) or 1)
    paginacao = q_temas.order_by(
        TemaAula.curso_id, TemaAula.ordem, TemaAula.id
    ).paginate(page=pagina_temas, per_page=25, error_out=False)
    if paginacao.pages and pagina_temas > paginacao.pages:
        pagina_temas = paginacao.pages
        paginacao = q_temas.order_by(
            TemaAula.curso_id, TemaAula.ordem, TemaAula.id
        ).paginate(page=pagina_temas, per_page=25, error_out=False)
    from app.models import Nivel
    niveis = Nivel.query.order_by(Nivel.nome).all()
    if unidade_id:
        niveis = [n for n in niveis if n.unidade_id == unidade_id or n.unidade_id is None]

    # A1: catálogo de valores do esportista da unidade, ordenado por nome sem
    # diferenciar maiúsculas (mesma variável usada no KPI, na aba e no loop).
    q_valores = ValorEsportista.query
    if unidade_id:
        q_valores = q_valores.filter(ValorEsportista.unidade_id == unidade_id)
    valores_esportista = q_valores.order_by(func.lower(ValorEsportista.nome)).all()

    # Aba que o usuário estava usando; um valor inválido cai em Temas.
    aba_ativa = _aba_planejamento(request.args.get('aba')) or 'temas'

    q_periodos = PeriodoLetivo.query.filter_by(ativo=True)
    if unidade_id:
        q_periodos = q_periodos.filter_by(unidade_id=unidade_id)
    periodos_ativos = q_periodos.order_by(PeriodoLetivo.data_inicio.desc()).all()

    cursos = []
    if unidade_id:
        cursos = Curso.query.filter_by(
            ativo=True, unidade_id=unidade_id
        ).order_by(Curso.nome).all()
    curso_cores = {curso.id: indice % 10 for indice, curso in enumerate(cursos)}

    return render_template('planejamento/planejamento.html',
                           turmas=turmas,
                           temas=paginacao.items,
                           paginacao=paginacao,
                           busca_tema=busca_tema,
                           programas=programas,
                           prog_filtro=prog_filtro,
                           filtro_curso=filtro_curso,
                           niveis=niveis,
                           valores_esportista=valores_esportista,
                           periodos_ativos=periodos_ativos,
                           cursos=cursos,
                           curso_cores=curso_cores,
                           unidade_id=unidade_id,
                           aba_ativa=aba_ativa,
                           data_inicio_atual=conf_i.valor if conf_i else '',
                           data_fim_atual=conf_f.valor if conf_f else '')


# ---------------------------------------------------------------------------
# TEMAS DE AULA — edição e inativação
# ---------------------------------------------------------------------------

@bp.route('/planejamento/tema/editar/<int:id>', methods=['POST'])
@login_required
def editar_tema(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, tema.curso_id) if tema.curso_id else None
    # ETAPA B6: o isolamento por unidade vem ANTES da checagem de curso
    # inativo, para que um tema de curso de outra unidade devolva 403
    # (e não um 302 com flash que revelaria a existência do curso).
    # ETAPA B4: sem isenção de ADMIN; o assert abaixo também recusa sessão
    # sem unidade (antes coberta só pelo cheque de SECRETARIA).
    assert_unidade_context(tema.unidade_id or (curso.unidade_id if curso else None), unidade_id)
    if curso and not curso.ativo:
        flash("Reative o curso antes de editar seus temas.", "warning")
        return _voltar_planejamento()

    novo_titulo = request.form.get('titulo', '').strip()
    nova_ordem = request.form.get('ordem')

    if novo_titulo:
        try:
            tema.titulo = novo_titulo
            if nova_ordem:
                tema.ordem = int(nova_ordem)

            db.session.flush()

            temas_curso = TemaAula.query.filter_by(curso_id=tema.curso_id).order_by(
                TemaAula.ordem,
                TemaAula.id != tema.id,
                TemaAula.id
            ).all()

            for i, t in enumerate(temas_curso, start=1):
                t.ordem = i

            db.session.commit()
            flash("Tema atualizado com sucesso!", 'success')
        except Exception:
            db.session.rollback()
            flash("Erro ao atualizar tema.", 'danger')
    else:
        flash("Título não pode ser vazio.", 'warning')
    return _voltar_planejamento()


@bp.route('/planejamento/tema/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_tema(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    tema = db.get_or_404(TemaAula, id)
    unidade_id = get_unidade_id()
    curso = db.get_or_404(Curso, tema.curso_id) if tema.curso_id else None
    # ETAPA B6: o isolamento por unidade vem ANTES da checagem de curso
    # inativo, para que um tema de curso de outra unidade devolva 403
    # (e não um 302 com flash que revelaria a existência do curso).
    # ETAPA B4: sem isenção de ADMIN; o assert abaixo também recusa sessão
    # sem unidade (antes coberta só pelo cheque de SECRETARIA).
    assert_unidade_context(tema.unidade_id or (curso.unidade_id if curso else None), unidade_id)
    if curso and not curso.ativo:
        flash("Reative o curso antes de alterar o status de seus temas.", "warning")
        return _voltar_planejamento()
    try:
        tema.ativo = not tema.ativo
        db.session.commit()
        status = 'ativado' if tema.ativo else 'inativado'
        flash(f"Tema '{tema.titulo}' {status}!", 'success')
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar status do tema.", 'danger')
    return _voltar_planejamento()


# ---------------------------------------------------------------------------
# NÍVEIS — edição e inativação
# ---------------------------------------------------------------------------

@bp.route('/planejamento/nivel/editar/<int:id>', methods=['POST'])
@login_required
def editar_nivel(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    from app.models import Nivel
    nivel = db.get_or_404(Nivel, id)
    # ETAPA B4: isolamento por unidade vale para todos os perfis (sem isenção
    # de ADMIN; sessão sem unidade efetiva é recusada pelo assert).
    unidade_id = get_unidade_id()
    assert_unidade_context(nivel.unidade_id, unidade_id)

    novo_nome = request.form.get('nome_nivel', '').strip()
    if novo_nome:
        try:
            nivel.nome = novo_nome
            db.session.commit()
            flash("Nível atualizado com sucesso!", 'success')
        except Exception:
            db.session.rollback()
            flash("Erro ao atualizar nível.", 'danger')
    else:
        flash("O nome do nível não pode ser vazio.", 'warning')
    return _voltar_planejamento()


@bp.route('/planejamento/nivel/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_nivel(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    from app.models import Nivel
    nivel = db.get_or_404(Nivel, id)
    # ETAPA B4: isolamento por unidade vale para todos os perfis (sem isenção
    # de ADMIN; sessão sem unidade efetiva é recusada pelo assert).
    unidade_id = get_unidade_id()
    assert_unidade_context(nivel.unidade_id, unidade_id)
    try:
        nivel.ativo = not nivel.ativo
        db.session.commit()
        status = 'ativado' if nivel.ativo else 'inativado'
        flash(f"Nível '{nivel.nome}' {status}!", 'success')
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar status do nível.", 'warning')
    return _voltar_planejamento()


# ---------------------------------------------------------------------------
# VALORES DO ESPORTISTA — edição e inativação (A1)
# ---------------------------------------------------------------------------

@bp.route('/planejamento/valor/editar/<int:id>', methods=['POST'])
@login_required
def editar_valor(id):
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    valor = db.get_or_404(ValorEsportista, id)
    # Mesmo isolamento dos níveis: sem isenção de ADMIN e sessão sem unidade
    # efetiva recusada pelo assert (a Visão Global é somente leitura).
    unidade_id = get_unidade_id()
    assert_unidade_context(valor.unidade_id, unidade_id)

    novo_nome = request.form.get('nome_valor', '').strip()
    if not novo_nome:
        flash("O nome do valor não pode ser vazio.", 'warning')
    elif len(novo_nome) > 100:
        flash("O nome do valor deve ter no máximo 100 caracteres.", 'warning')
    elif _valor_esportista_duplicado(novo_nome, valor.unidade_id, ignorar_id=valor.id):
        flash(
            f"Já existe um valor com o nome '{novo_nome}' nesta unidade.",
            'warning',
        )
    else:
        try:
            valor.nome = novo_nome
            db.session.commit()
            flash("Valor atualizado com sucesso!", 'success')
        except IntegrityError:
            db.session.rollback()
            flash("Já existe um valor com esse nome nesta unidade.", 'warning')
        except Exception:
            db.session.rollback()
            flash("Erro ao atualizar valor.", 'danger')
    return _voltar_planejamento()


@bp.route('/planejamento/valor/inativar/<int:id>', methods=['POST'])
@login_required
def inativar_valor(id):
    """Alterna ativo/inativo. Valor NUNCA é apagado com uso (histórico)."""
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)
    valor = db.get_or_404(ValorEsportista, id)
    unidade_id = get_unidade_id()
    assert_unidade_context(valor.unidade_id, unidade_id)
    try:
        valor.ativo = not valor.ativo
        db.session.commit()
        status = 'ativado' if valor.ativo else 'inativado'
        flash(f"Valor '{valor.nome}' {status}!", 'success')
    except Exception:
        db.session.rollback()
        flash("Erro ao alterar status do valor.", 'danger')
    return _voltar_planejamento()


# ---------------------------------------------------------------------------
# TEMAS — impressão
# ---------------------------------------------------------------------------

@bp.route('/planejamento/imprimir-temas')
@login_required
def imprimir_temas():
    if current_user.role not in (UserRole.ADMIN, UserRole.PEDAGOGICO, UserRole.SECRETARIA):
        abort(403)

    filtro_curso = request.args.get('curso_id', '').strip()
    try:
        curso_id = int(filtro_curso) if filtro_curso else None
    except ValueError:
        curso_id = None
        filtro_curso = ''

    unidade_id = get_unidade_id()
    if current_user.role == UserRole.SECRETARIA and unidade_id is None:
        abort(403)

    q_cursos = Curso.query.filter_by(ativo=True)
    if unidade_id:
        q_cursos = q_cursos.filter_by(unidade_id=unidade_id)
    todos_cursos = q_cursos.order_by(Curso.nome).all()
    cursos = [curso for curso in todos_cursos if not curso_id or curso.id == curso_id]
    curso_ids = [curso.id for curso in cursos]

    temas = []
    if curso_ids:
        temas = TemaAula.query.filter(
            TemaAula.curso_id.in_(curso_ids),
            TemaAula.ativo == True,
        ).order_by(TemaAula.curso_id, TemaAula.ordem, TemaAula.id).all()

    temas_por_curso = {
        curso.id: [tema for tema in temas if tema.curso_id == curso.id]
        for curso in cursos
    }
    cursos_com_temas = [curso for curso in cursos if temas_por_curso[curso.id]]

    return render_template('planejamento/impressao_temas.html',
                           cursos=cursos_com_temas,
                           todos_cursos=todos_cursos,
                           temas_por_curso=temas_por_curso,
                           filtro_curso=filtro_curso,
                           now=datetime.now())

# ---------------------------------------------------------------------------
# API SERVERSIDE BINDINGS
# ---------------------------------------------------------------------------
@bp.route('/api/alunos/<int:turma_id>')
@login_required
def api_alunos(turma_id):
    """Integrações Async com Frontend AJAX para Fetch de Alunos por ID."""
    if current_user.role not in (
        UserRole.ADMIN,
        UserRole.PEDAGOGICO,
        UserRole.SECRETARIA,
        UserRole.GERENCIA,
    ):
        abort(403)

    turma = Turma.query.get_or_404(turma_id)
    assert_unidade_context(turma.unidade_id, get_unidade_id())
    alunos = turma.alunos.all()
    return jsonify([{"id": a.id, "nome": a.nome} for a in alunos])

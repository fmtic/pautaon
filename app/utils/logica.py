from datetime import datetime, date, timedelta, timezone
from flask import current_app, session
from flask_login import current_user
from app.database import db
from app.models import User, Turma, Aluno, Frequencia, TemaAula, RegistroAula, ConfiguracaoSistema, Inscricao
from typing import List, Dict, Tuple, Any, Optional

from app.utils.timezone import get_local_now

def get_unidade_id() -> Optional[int]:
    """Retorna o ID da unidade atual a partir da sessão HTTP."""
    if 'unidade_id' in session:
        try:
            return int(session.get('unidade_id'))
        except (ValueError, TypeError):
            pass
    return None

def gerar_datas(turma: Turma, incluir_futuro: bool = False,
                blocked_dates: set = None) -> List[str]:
    """
    Gera array cronológico de datas aula-a-aula, calculando de acordo com dias da semana cadastrados.
    Exclui automaticamente qualquer data presente em `blocked_dates` (set de strings YYYY-MM-DD).

    :param turma: Instância do modelo Turma contendo as strings de data_inicio e dias_semana.
    :param incluir_futuro: Caso se imprima relatórios legados físicos de pauta, inclua a projeção de encerramento futuro.
    :param blocked_dates: Conjunto opcional de datas bloqueadas (DiaBloqueado) a serem excluídas.
    :return: Lista de strings no formato %Y-%m-%d
    """
    blocked_dates = blocked_dates or set()
    datas: List[str] = []
    if not turma or not turma.data_inicio or not turma.data_fim:
        return datas

    mapa_dias = {
        'Segunda': 0, 'Terça': 1, 'Quarta': 2, 'Quinta': 3,
        'Sexta': 4, 'Sábado': 5, 'Domingo': 6,
        'Segunda-feira': 0, 'Terça-feira': 1, 'Quarta-feira': 2,
        'Quinta-feira': 3, 'Sexta-feira': 4, 'Sábado-feira': 5
    }

    try:
        inicio = datetime.strptime(turma.data_inicio, "%Y-%m-%d")
        fim    = datetime.strptime(turma.data_fim,    "%Y-%m-%d")

        if incluir_futuro:
            data_limite = fim
        else:
            hoje = datetime.now()
            data_limite = min(fim, hoje)

    except ValueError:
        return datas

    dias_permitidos = [
        mapa_dias[d.strip()]
        for d in (turma.dias_semana or "").split(',')
        if d.strip() in mapa_dias
    ]

    atual = inicio
    while atual <= data_limite:
        if atual.weekday() in dias_permitidos:
            ds = atual.strftime("%Y-%m-%d")
            if ds not in blocked_dates:
                datas.append(ds)
        atual += timedelta(days=1)

    if incluir_futuro:
        return datas
    return datas[::-1]  # Retorna do mais atual pro mais antigo


def calcular_idades(alunos: List[Aluno]) -> None:
    """Acopla a propriedade computada `.idade_calculada` a cada instância da lista de alunos iterada."""
    hoje = date.today()
    for aluno in alunos:
        if aluno.data_nascimento:
            nasc = (
                aluno.data_nascimento
                if isinstance(aluno.data_nascimento, date)
                else datetime.strptime(str(aluno.data_nascimento), "%Y-%m-%d").date()
            )
            # Acopla a idade no objeto efêmero durante ciclo de requisição
            aluno.idade_calculada = (
                hoje.year - nasc.year
                - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
            )
        else:
            aluno.idade_calculada = "?"


def carregar_contexto_turma(turma_id: int, pauta_impressa: bool = False) -> Dict[str, Any]:
    """Retorna um DICIONÁRIO de contexto com base numa turma_id para o Jinja2.
    Injeta automaticamente os dias bloqueados do período letivo da turma.
    """
    from app.models import DiaBloqueado

    turma = Turma.query.get_or_404(turma_id)

    # Carrega dias bloqueados do período letivo da turma
    blocked_dates: set = set()
    if turma.periodo_letivo_id:
        dias = DiaBloqueado.query.filter_by(
            periodo_letivo_id=turma.periodo_letivo_id
        ).all()
        blocked_dates = {d.data.strftime("%Y-%m-%d") for d in dias}

    alunos = Aluno.query.join(Inscricao).filter(
        Inscricao.turma_id == turma_id,
        Inscricao.ativo == True,
        Aluno.ativo == True
    ).order_by(Aluno.nome).all()
    calcular_idades(alunos)

    datas = gerar_datas(turma, incluir_futuro=pauta_impressa, blocked_dates=blocked_dates)

    meses_disponiveis = []
    vistos = set()
    nomes_meses = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    for d in datas:
        mes_num = d[5:7] 
        if mes_num not in vistos:
            meses_disponiveis.append({
                'numero': mes_num, 
                'nome': nomes_meses.get(mes_num, 'Mês Desconhecido')
            })
            vistos.add(mes_num)

    # Busca temas pelo curso da turma (novo fluxo) ou pelo turma_id legado
    if turma.curso_id:
        temas = TemaAula.query.filter_by(curso_id=turma.curso_id, ativo=True).all()
    else:
        temas = TemaAula.query.filter_by(turma_id=turma_id, ativo=True).all()

    return dict(
        turma=turma,
        alunos=alunos,
        datas=datas,
        temas=temas,
        meses=meses_disponiveis
    )


def carregar_frequencias(turma_id: int, data: str) -> Tuple[Dict[int, str], Optional[int], str]:
    """Retorna os conceitos daquela turma e se há um tema ou nota do educador acoplada ao registro de aula"""
    frequencias: Dict[int, str] = {}
    tema_selecionado: Optional[int] = None
    obs_salva: str = ""

    if turma_id and data:
        registros = Frequencia.query.filter_by(
            turma_id=turma_id, data=data
        ).all()
        frequencias = {f.aluno_id: f.conceito for f in registros}

        diario = RegistroAula.query.filter_by(turma_id=turma_id, data=data).first()
        if diario:
            tema_selecionado = diario.tema_id
            obs_salva = diario.observacoes or ""

    return frequencias, tema_selecionado, obs_salva


def salvar_frequencia(form: Dict[str, str]) -> Tuple[int, Optional[str]]:
    """O serviço consolida todos os inserts de diário num Atomic Commit."""
    try:
        # Aceita 'turma' (select) ou 'turma' (hidden)
        turma_raw = form.get('turma', '0').strip()
        turma_id = int(turma_raw) if turma_raw and turma_raw.isdigit() else 0

        # Aceita 'data' (select) ou 'data_hidden' (fallback hidden)
        data = (form.get('data', '') or form.get('data_hidden', '')).strip()

        tema_id_raw = form.get('tema_id', '').strip()
        tema_id = int(tema_id_raw) if tema_id_raw and tema_id_raw.isdigit() else None
        texto_observacoes = form.get('observacoes', '').strip() or None

        if not data or turma_id == 0:
            return turma_id, None

        registro = RegistroAula.query.filter_by(turma_id=turma_id, data=data).first()
        if registro:
            registro.observacoes = texto_observacoes
            registro.tema_id = tema_id
            registro.instrutor_id = current_user.id
        else:
            db.session.add(RegistroAula(
                turma_id=turma_id,
                data=data,
                tema_id=tema_id,
                observacoes=texto_observacoes,
                instrutor_id=current_user.id,
            ))

        alunos_post = Aluno.query.join(Inscricao).filter(
            Inscricao.turma_id == turma_id,
            Inscricao.ativo == True,
            Aluno.ativo == True
        ).all()

        for aluno in alunos_post:
            conceito = form.get(f'aluno_{aluno.id}', '').strip()
            if not conceito:
                continue

            freq = Frequencia.query.filter_by(
                aluno_id=aluno.id, turma_id=turma_id, data=data
            ).first()

            if freq:
                freq.conceito = conceito
            else:
                db.session.add(Frequencia(
                    aluno_id=aluno.id,
                    turma_id=turma_id,
                    data=data,
                    conceito=conceito,
                ))

        db.session.commit()
        return turma_id, data

    except Exception as e:
        db.session.rollback()
        import traceback
        traceback.print_exc()
        return 0, None


def calcular_estatisticas_idade(unidade_id: Optional[int] = None) -> Dict[str, Any]:
    hoje = date.today()
    alunos_query = Aluno.query.filter(Aluno.ativo == True)
    if unidade_id:
        alunos_query = alunos_query.filter_by(unidade_id=unidade_id)
    alunos = alunos_query.all()
    if not alunos:
        return {'media_geral': 0, 'media_programa': {}, 'media_turma': {}}

    idades_geral = [aluno.idade for aluno in alunos]
    media_geral = sum(idades_geral) / len(idades_geral) if idades_geral else 0

    media_por_programa = {}
    prog_query = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        prog_query = prog_query.filter(Turma.unidade_id == unidade_id)
    for prog, in prog_query.all():
        q = Aluno.query.join(Aluno.turmas).filter(
            Turma.programa == prog,
            Aluno.ativo == True,
            Turma.ativo == True
        )
        if unidade_id:
            q = q.filter(Aluno.unidade_id == unidade_id, Turma.unidade_id == unidade_id)
        alunos_prog = q.all()
        if alunos_prog:
            idades = [a.idade for a in alunos_prog]
            media_por_programa[prog] = sum(idades) / len(idades)

    media_por_turma = {}
    turma_query = Turma.query.filter_by(ativo=True)
    if unidade_id:
        turma_query = turma_query.filter_by(unidade_id=unidade_id)
    for t in turma_query.all():
        idades = [a.idade for a in t.alunos if a.ativo and (not unidade_id or a.unidade_id == unidade_id)]
        if idades:
            media_por_turma[t.nome] = sum(idades) / len(idades)

    return {
        'media_geral': round(media_geral, 1),
        'media_programa': media_por_programa,
        'media_turma': media_por_turma
    }

def calcular_frequencias_relatorio(todas_as_turmas: List[Turma], unidade_id: Optional[int] = None) -> Tuple[float, Dict[str, float], Dict[str, float], Dict[str, float]]:
    def calc_pc(p: int, f: int) -> float:
        """Presença = A+B+C+D, Falta = F. J não entra no denominador."""
        total = p + f
        return round((p / total * 100), 1) if total > 0 else 0.0

    q_geral = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.ativo == True)
    if unidade_id:
        q_geral = q_geral.filter(Turma.unidade_id == unidade_id)
    p_geral = calc_pc(q_geral.filter(Frequencia.presente == True).count(),
                      q_geral.filter(Frequencia.conceito == 'F').count())

    f_prog: Dict[str, float] = {}
    prog_query = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        prog_query = prog_query.filter(Turma.unidade_id == unidade_id)
    for prog, in prog_query.all():
        q = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.programa == prog, Turma.ativo == True)
        if unidade_id:
            q = q.filter(Turma.unidade_id == unidade_id)
        f_prog[prog] = calc_pc(q.filter(Frequencia.presente == True).count(), 
                               q.filter(Frequencia.conceito == 'F').count())

    f_turma: Dict[str, float] = {}
    for t in todas_as_turmas:
        q = Frequencia.query.filter(Frequencia.turma_id == t.id)
        f_turma[t.nome] = calc_pc(q.filter(Frequencia.presente == True).count(),
                                  q.filter(Frequencia.conceito == 'F').count())

    f_prof: Dict[str, float] = {}
    prof_query = User.query.filter_by(role='professor')
    if unidade_id:
        prof_query = prof_query.filter_by(unidade_id=unidade_id)
    for prof in prof_query.all():
        q = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.professor_id == prof.id, Turma.ativo == True)
        if unidade_id:
            q = q.filter(Turma.unidade_id == unidade_id)
        if q.count() > 0:
            f_prof[prof.name] = calc_pc(q.filter(Frequencia.presente == True).count(),
                                        q.filter(Frequencia.conceito == 'F').count())

    return p_geral, f_prog, f_turma, f_prof


def calcular_metricas_conselho(unidade_id: Optional[int] = None) -> Dict[str, float]:
    if unidade_id:
        conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho', unidade_id=unidade_id).first()
        if not conf_inicio:
            conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho', unidade_id=None).first()
        conf_fim = ConfiguracaoSistema.query.filter_by(chave='fim_conselho', unidade_id=unidade_id).first()
        if not conf_fim:
            conf_fim = ConfiguracaoSistema.query.filter_by(chave='fim_conselho', unidade_id=None).first()
    else:
        conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho', unidade_id=None).first()
        conf_fim = ConfiguracaoSistema.query.filter_by(chave='fim_conselho', unidade_id=None).first()
    
    prog_aulas = 0.0
    if conf_inicio and conf_fim:
        try:
            inicio = datetime.strptime(conf_inicio.valor, "%Y-%m-%d").date()
            fim = datetime.strptime(conf_fim.valor, "%Y-%m-%d").date()
            tema_query = TemaAula.query.filter(TemaAula.data.between(inicio, fim))
            registro_query = RegistroAula.query.filter(RegistroAula.data.between(inicio, fim))
            if unidade_id:
                tema_query = tema_query.filter_by(unidade_id=unidade_id)
                registro_query = registro_query.filter_by(unidade_id=unidade_id)
            total = tema_query.count()
            real = registro_query.count()
            prog_aulas = round((real / total * 100), 1) if total > 0 else 0.0
        except: pass

    total_t = Turma.query.filter_by(ativo=True)
    concluidas = Turma.query.filter_by(ativo=True, conselho_concluido=True)
    if unidade_id:
        total_t = total_t.filter_by(unidade_id=unidade_id)
        concluidas = concluidas.filter_by(unidade_id=unidade_id)
    total_t = total_t.count()
    concluidas = concluidas.count()
    prog_reunioes = float(round((concluidas / total_t * 100), 1) if total_t > 0 else 0.0)

    return {
        'progresso_aulas': prog_aulas,
        'progresso_reunioes': prog_reunioes,
        'turmas_concluidas': concluidas,
        'total_turmas': total_t
    }
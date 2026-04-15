from datetime import datetime, date, timedelta
from flask import ctx, render_template
from flask_login import current_user
from models import User, db, Turma, Aluno, Frequencia, TemaAula, RegistroAula, ConfiguracaoSistema, Nivel, Transferencia
from database import db
from flask import session

def get_unidade_id():
    """Retorna o ID da unidade atual da sessão."""
    return session.get('unidade_id')

def gerar_datas(turma, incluir_futuro=False): # Adicione o parâmetro
    datas = []
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
        
        # LÓGICA ALTERADA AQUI:
        if incluir_futuro:
            data_limite = fim # Para impressão, vai até o fim do curso
        else:
            hoje = datetime.now()
            data_limite = min(fim, hoje) # Para o diário online, para em hoje
            
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
            datas.append(atual.strftime("%Y-%m-%d"))
        atual += timedelta(days=1)

    # Para impressão, talvez você prefira ordem CRESCENTE (remova o [::-1])
    # Para o diário online, DECRESCENTE é melhor.
    if incluir_futuro:
        return datas # Ordem Cronológica para o papel
    return datas[::-1]


def calcular_idades(alunos):
    """Anota .idade_calculada em cada aluno da lista. Sem retorno."""
    hoje = date.today()
    for aluno in alunos:
        if aluno.data_nascimento:
            nasc = (
                aluno.data_nascimento
                if isinstance(aluno.data_nascimento, date)
                else datetime.strptime(str(aluno.data_nascimento), "%Y-%m-%d").date()
            )
            aluno.idade_calculada = (
                hoje.year - nasc.year
                - ((hoje.month, hoje.day) < (nasc.month, nasc.day))
            )
        else:
            aluno.idade_calculada = "?"


def carregar_contexto_turma(turma_id, pauta_impressa=False, data_frequencia=None):
    turma = Turma.query.get_or_404(turma_id)
    
    # 1. Busca alunos (Muitos-para-Muitos) apenas ativos pra este turma/período
    alunos = sorted(turma.alunos_ativos, key=lambda a: a.nome)
    calcular_idades(alunos)
    
    # 2. Marcar alunos transferidos se data_frequencia for fornecida
    if data_frequencia:
        data_obj = datetime.strptime(data_frequencia, "%Y-%m-%d").date()
        for aluno in alunos:
            transferencia = Transferencia.query.filter(
                Transferencia.aluno_id == aluno.id,
                Transferencia.turma_origem_id == turma_id,
                Transferencia.data_transferencia <= data_obj
            ).first()
            aluno.pode_receber_frequencia = not transferencia
    else:
        for aluno in alunos:
            aluno.pode_receber_frequencia = True  # Por padrão, pode

    # 2. Gera as datas da turma
    datas = gerar_datas(turma, incluir_futuro=pauta_impressa) # Presumindo que retorna ['2026-03-30', '2026-04-01', ...]

    # 3. Extração dinâmica dos meses para o menu de impressão
    meses_disponiveis = []
    vistos = set()
    nomes_meses = {
        '01': 'Janeiro', '02': 'Fevereiro', '03': 'Março', '04': 'Abril',
        '05': 'Maio', '06': 'Junho', '07': 'Julho', '08': 'Agosto',
        '09': 'Setembro', '10': 'Outubro', '11': 'Novembro', '12': 'Dezembro'
    }

    for d in datas:
        # Pega o mês da string 'YYYY-MM-DD'
        mes_num = d[5:7] 
        if mes_num not in vistos:
            meses_disponiveis.append({
                'numero': mes_num, 
                'nome': nomes_meses.get(mes_num, 'Mês Desconhecido')
            })
            vistos.add(mes_num)

    # 4. Outros dados (Temas ativos, etc)
    temas = TemaAula.query.filter_by(turma_id=turma_id, ativo=True).all()

    # 5. Busca níveis disponíveis
    niveis = Nivel.query.filter_by(ativo=True).order_by(Nivel.nome).all()

    return dict(
        turma=turma, 
        alunos=alunos, 
        datas=datas, 
        temas=temas, 
        meses=meses_disponiveis,
        niveis=niveis
    )


def carregar_frequencias(turma_id, data):
    frequencias = {}
    tema_selecionado = None
    obs_salva = ""

    if turma_id and data:
        # Busca presenças - Filtramos pela Turma e Data na Frequência
        registros = Frequencia.query.filter(
            Frequencia.data == data, Frequencia.turma_id == turma_id
        ).all()
        frequencias = {f.aluno_id: f.conceito for f in registros}
        
        # BUSCA O DIÁRIO (Fonte da verdade para Tema e Obs)
        diario = RegistroAula.query.filter_by(turma_id=turma_id, data=data).first()
        if diario:
            tema_selecionado = diario.tema_id
            obs_salva = diario.observacoes

    return frequencias, tema_selecionado, obs_salva # Retorna os 3

def salvar_frequencia(form):
    """
    Processa o formulário de frequência (request.form).
    Retorna (turma_id, data) para o redirect após o commit.
    """
    turma_id          = int(form.get('turma'))
    data              = form.get('data')
    tema_id           = form.get('tema_id')
    texto_observacoes = form.get('observacoes')

    # Valida data antes de qualquer escrita
    if not data:
        return turma_id, None  # sinaliza que não havia data

    # Cria ou atualiza o RegistroAula do dia
    registro = RegistroAula.query.filter_by(turma_id=turma_id, data=data).first()
    if registro:
        registro.observacoes = texto_observacoes
        registro.tema_id     = tema_id
        registro.instrutor_id = current_user.id
    else:
        db.session.add(RegistroAula(
            turma_id=turma_id,
            data=data,
            tema_id=tema_id,
            observacoes=texto_observacoes,
            instrutor_id=current_user.id,
            unidade_id=get_unidade_id()
        ))

    # Cria ou atualiza a frequência de cada aluno
    turma = Turma.query.get(turma_id)
    alunos_post = turma.alunos_ativos
    
    # Filtrar alunos que não foram transferidos desta turma antes da data
    data_obj = datetime.strptime(data, "%Y-%m-%d").date()
    alunos_validos = []
    for aluno in alunos_post:
        # Verificar se há transferência desta turma antes da data
        transferencia = Transferencia.query.filter(
            Transferencia.aluno_id == aluno.id,
            Transferencia.turma_origem_id == turma_id,
            Transferencia.data_transferencia <= data_obj
        ).first()
        if not transferencia:
            alunos_validos.append(aluno)
    
    for aluno in alunos_validos:
        conceito = form.get(f'aluno_{aluno.id}')
        if not conceito:
            continue

        esta_presente = conceito in ['A', 'B', 'C', 'D', 'J']
        freq = Frequencia.query.filter_by(aluno_id=aluno.id, data=data).first()

        if freq:
            freq.conceito  = conceito
            freq.presente  = esta_presente
            freq.tema_id   = tema_id
        else:
            db.session.add(Frequencia(
                aluno_id=aluno.id,
                data=data,
                conceito=conceito,
                presente=esta_presente,
                tema_id=tema_id,
                unidade_id=get_unidade_id(),
                turma_id=turma_id
            ))

    db.session.commit()
    return turma_id, data

def calcular_estatisticas_idade():
    hoje = date.today()
    unidade_id = get_unidade_id()
    
    query_aluno = Aluno.query.filter(Aluno.ativo == True)
    if unidade_id:
        query_aluno = query_aluno.filter(Aluno.unidade_id == unidade_id)
        
    alunos = query_aluno.all()
    if not alunos:
        return {'media_geral': 0, 'media_programa': {}, 'media_turma': {}}

    idades_geral = [aluno.idade for aluno in alunos]
    media_geral = sum(idades_geral) / len(idades_geral) if idades_geral else 0

    media_por_programa = {}
    q_progs = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        q_progs = q_progs.filter(Turma.unidade_id == unidade_id)
        
    for prog, in q_progs.all():
        q_ap = Aluno.query.join(Aluno.turmas).filter(Turma.programa == prog, Aluno.ativo == True)
        if unidade_id:
            q_ap = q_ap.filter(Aluno.unidade_id == unidade_id)
        
        alunos_prog = q_ap.all()
        if alunos_prog:
            idades = [a.idade for a in alunos_prog]
            media_por_programa[prog] = sum(idades) / len(idades)

    media_por_turma = {}
    q_turmas = Turma.query.filter_by(ativo=True)
    if unidade_id:
        q_turmas = q_turmas.filter_by(unidade_id=unidade_id)
        
    for t in q_turmas.all():
        idades = [a.idade for a in t.alunos if a.ativo]
        if idades:
            media_por_turma[t.nome] = sum(idades) / len(idades)

    return {
        'media_geral': round(media_geral, 1),
        'media_programa': media_por_programa,
        'media_turma': media_por_turma
    }
 
    # Função auxiliar para calcular porcentagem
# utils/logica.py

def calcular_frequencias_relatorio(todas_as_turmas):
    def calc_pc(p, f, j):
        # Falta Justificada (j) não conta no total para o percentual
        total = p + f 
        return round((p / total * 100), 1) if total > 0 else 0

    # 1. Geral
    unidade_id = get_unidade_id()
    q_geral = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.ativo == True)
    if unidade_id:
        q_geral = q_geral.filter(Turma.unidade_id == unidade_id)
        
    p_geral = calc_pc(q_geral.filter(Frequencia.presente == True).count(),
                      q_geral.filter(Frequencia.conceito == 'F').count(),
                      q_geral.filter(Frequencia.conceito == 'J').count())

    # 2. Por Programa
    f_prog = {}
    q_progs_f = db.session.query(Turma.programa).distinct().filter(Turma.ativo == True)
    if unidade_id:
        q_progs_f = q_progs_f.filter(Turma.unidade_id == unidade_id)
        
    for prog, in q_progs_f.all():
        q = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.programa == prog, Turma.ativo == True)
        if unidade_id:
            q = q.filter(Turma.unidade_id == unidade_id)
            
        f_prog[prog] = calc_pc(q.filter(Frequencia.presente == True).count(), 
                               q.filter(Frequencia.conceito == 'F').count(), 
                               q.filter(Frequencia.conceito == 'J').count())

    # 3. Por Turma
    f_turma = {}
    for t in todas_as_turmas:
        q = Frequencia.query.filter(Frequencia.turma_id == t.id)
        f_turma[t.nome] = calc_pc(q.filter(Frequencia.presente == True).count(),
                                  q.filter(Frequencia.conceito == 'F').count(),
                                  q.filter(Frequencia.conceito == 'J').count())

    # 4. Por Professor
    f_prof = {}
    q_profs = User.query.filter_by(role='professor')
    if unidade_id:
        q_profs = q_profs.filter_by(unidade_id=unidade_id)
        
    for prof in q_profs.all():
        q = Frequencia.query.join(Aluno).join(Aluno.turmas).filter(Turma.professor_id == prof.id, Turma.ativo == True)
        if q.count() > 0:
            f_prof[prof.name] = calc_pc(q.filter(Frequencia.presente == True).count(),
                                        q.filter(Frequencia.conceito == 'F').count(),
                                        q.filter(Frequencia.conceito == 'J').count())

    return p_geral, f_prog, f_turma, f_prof

def calcular_metricas_conselho():
    prog_aulas = 0
    unidade_id = get_unidade_id()
    conf_inicio = ConfiguracaoSistema.query.filter_by(chave='inicio_conselho', unidade_id=unidade_id).first()
    conf_fim = ConfiguracaoSistema.query.filter_by(chave='fim_conselho', unidade_id=unidade_id).first()
    
    if conf_inicio and conf_fim:
        try:
            inicio = datetime.strptime(conf_inicio.valor, "%Y-%m-%d").date()
            fim = datetime.strptime(conf_fim.valor, "%Y-%m-%d").date()
            
            q_temas = TemaAula.query.filter(TemaAula.data.between(inicio, fim))
            q_regs = RegistroAula.query.filter(RegistroAula.data.between(inicio, fim))
            if unidade_id:
                q_temas = q_temas.filter(TemaAula.unidade_id == unidade_id)
                q_regs = q_regs.filter(RegistroAula.unidade_id == unidade_id)
                
            total = q_temas.count()
            real = q_regs.count()
            prog_aulas = round((real / total * 100), 1) if total > 0 else 0
        except: pass

    q_turma_t = Turma.query.filter_by(ativo=True)
    if unidade_id:
        q_turma_t = q_turma_t.filter_by(unidade_id=unidade_id)
        
    total_t = q_turma_t.count()
    concluidas = q_turma_t.filter_by(conselho_concluido=True).count()
    prog_reunioes = round((concluidas / total_t * 100), 1) if total_t > 0 else 0

    return {
        'progresso_aulas': prog_aulas,
        'progresso_reunioes': prog_reunioes,
        'turmas_concluidas': concluidas,
        'total_turmas': total_t
    }

def anotar_estatisticas_aluno_turma(alunos, turma_id):
    """Calcula estatísticas de frequência para uma lista de alunos em uma dada turma."""
    for aluno in alunos:
        # Busca conceitos A, B, C, D (Presença), F (Falta), J (Justificada)
        registros = Frequencia.query.filter_by(aluno_id=aluno.id, turma_id=turma_id).all()
        total = len(registros)
        
        counts = {'P': 0, 'F': 0, 'J': 0}
        for r in registros:
            if r.conceito in ['A', 'B', 'C', 'D']:
                counts['P'] += 1
            elif r.conceito == 'F':
                counts['F'] += 1
            elif r.conceito == 'J':
                counts['J'] += 1
        
        def perc(val, is_special=False):
            # Para Presença (P) e Falta (F), o total exclui Justificadas (J)
            # Para Justificada (J), o total inclui tudo para fins de proporção real
            total_calc = (counts['P'] + counts['F']) if not is_special else total
            return round((val / total_calc * 100), 1) if total_calc > 0 else 0
            
        aluno.estats_freq = {
            'presenca': perc(counts['P']),
            'falta': perc(counts['F']),
            'justificada': perc(counts['J'], is_special=True),
            'total_aulas': total
        }

def calcular_frequencia_geral_turma(turma_id):
    """Calcula o percentual geral de presença (A+B+C+D) da turma."""
    # Busca todas as frequências da turma EXCLUINDO Justificadas (J) do total para cálculo
    q = Frequencia.query.filter_by(turma_id=turma_id)
    total_calculo = q.filter(Frequencia.conceito != 'J').count()
    if total_calculo == 0:
        return 0
    
    # Presenças: A, B, C, D
    presencas = q.filter(Frequencia.conceito.in_(['A', 'B', 'C', 'D'])).count()
    return round((presencas / total_calculo * 100), 1)
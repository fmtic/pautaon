import json

from app.database import db
from datetime import datetime, date, timezone
from app.utils.timezone import get_local_now
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import select
from sqlalchemy.ext.hybrid import hybrid_property
from typing import List, Optional

# ---------------------------------------------------------------------------
# TABELA DE ASSOCIAÇÃO (Muitos-para-Muitos: Aluno <-> Turma)
# ---------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# TABELA DE ASSOCIAÇÃO (Muitos-para-Muitos: Aluno <-> Turma)
# ---------------------------------------------------------------------------
class Inscricao(db.Model):
    __tablename__ = 'inscricoes'
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), primary_key=True)

    # Nível do aluno nesta turma específica
    nivel: str = db.Column(db.String(30))

    # Metadados de Auditoria / Status
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    data_desativacao: datetime = db.Column(db.DateTime)
    motivo_desativacao: str = db.Column(db.String(50))

    aluno = db.relationship('Aluno', backref=db.backref('inscricoes', cascade='all, delete-orphan'),
                            overlaps='turmas,alunos')
    turma = db.relationship('Turma', backref=db.backref('inscricoes', cascade='all, delete-orphan'),
                            overlaps='turmas,alunos')


# ---------------------------------------------------------------------------
# UNIDADES (Multitenancy)
# ---------------------------------------------------------------------------
class Unidade(db.Model):
    __tablename__ = 'unidade'
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)

# ---------------------------------------------------------------------------
# PERÍODOS LETIVOS
# ---------------------------------------------------------------------------
class PeriodoLetivo(db.Model):
    __tablename__ = 'periodo_letivo'
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(150), nullable=False)
    data_inicio: date = db.Column(db.Date, nullable=False)
    data_fim: date = db.Column(db.Date, nullable=False)
    centro_custo: str = db.Column(db.String(150))
    estimativa_alunos: int = db.Column(db.Integer, default=0, nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    unidade = db.relationship('Unidade', backref='periodos')

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(db.DateTime, onupdate=get_local_now)

    def alunos_enturmados(self) -> int:
        """
        Calcula o total de alunos únicos matriculados em turmas pertencentes a este período.
        """
        from app.models import Aluno, Turma
        return Aluno.query.join(Aluno.turmas).filter(Turma.periodo_letivo_id == self.id).distinct().count()


# ---------------------------------------------------------------------------
# CURSOS
# ---------------------------------------------------------------------------
class Curso(db.Model):
    """
    Curso disponível para associação às turmas de uma unidade.
    Cada unidade gerencia seu próprio catálogo de cursos.
    """
    __tablename__ = 'curso'

    id: int              = db.Column(db.Integer, primary_key=True)
    nome: str            = db.Column(db.String(150), nullable=False)
    descricao: str       = db.Column(db.String(300))
    carga_horaria: int   = db.Column(db.Integer)          # horas totais do curso
    ativo: bool          = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id: int      = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade = db.relationship('Unidade', backref='cursos')

# ---------------------------------------------------------------------------
# DIAS BLOQUEADOS (sem aula) POR PERÍODO LETIVO
# ---------------------------------------------------------------------------
class DiaBloqueado(db.Model):
    """
    Registra dias em que não haverá aula em um período letivo de uma unidade.
    Esses dias são excluídos da pauta de frequência de todas as turmas do período.

    Tipos válidos: FERIADO, ATIVIDADE_PEDAGOGICA, REUNIAO_PAIS,
                   ATIVIDADE_INTERNA, MANUTENCAO
    """
    __tablename__ = 'dia_bloqueado'

    id: int                  = db.Column(db.Integer, primary_key=True)
    data: date               = db.Column(db.Date, nullable=False)
    tipo: str                = db.Column(db.String(50), nullable=False)
    descricao: str           = db.Column(db.String(200))
    periodo_letivo_id: int   = db.Column(db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=False)
    unidade_id: int          = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    criado_por_id: int       = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_at: datetime     = db.Column(db.DateTime, default=get_local_now)

    periodo_letivo = db.relationship('PeriodoLetivo', backref='dias_bloqueados')
    unidade        = db.relationship('Unidade', backref='dias_bloqueados')
    criado_por     = db.relationship('User', backref='dias_bloqueados_criados', foreign_keys=[criado_por_id])

# ---------------------------------------------------------------------------
# USUÁRIOS E AUTENTICAÇÃO
# ---------------------------------------------------------------------------
class User(db.Model, UserMixin):
    """
    Modelo responsável pela gestão de acessos e perfis do sistema (Admins, Professores, etc).
    O UserMixin acopla automaticamente métodos necessários para o Flask-Login.
    """
    __tablename__ = 'user'
    
    id: int = db.Column(db.Integer, primary_key=True)
    name: str = db.Column(db.String(100), nullable=False)
    email: str = db.Column(db.String(120), unique=True, nullable=False)
    password: str = db.Column(db.String(200), nullable=False)
    
    # Perfis comuns: 'admin', 'pedagogico', 'professor', 'secretaria', 'pendente'
    role: str = db.Column(db.String(20), nullable=False)
    
    is_active: bool = db.Column(db.Boolean, default=True, nullable=False)
    is_ad_user: bool = db.Column(db.Boolean, default=False, nullable=False)
    
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='usuarios')
    
    first_login: bool = db.Column(db.Boolean, default=True)

    def set_password(self, password: str) -> None:
        """Gera e armazena o hash criptografado da senha."""
        self.password = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Compara a string em texto limpo com o hash armazenado no banco."""
        return check_password_hash(self.password, password)

# ---------------------------------------------------------------------------
# TURMAS E CURSOS
# ---------------------------------------------------------------------------
class Turma(db.Model):
    """
    Representa o agrupamento de alunos em uma dada disciplina/programa, ministrado por um professor.
    """
    __tablename__ = 'turma'
    
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    
    # NOTA TÉCNICA: Estes campos são armazenados como strings (YYYY-MM-DD / HH:MM).
    # Caso necessite de refatoração para cálculos temporais mais refinados com banco Postgres, converta para `db.Date` futuramente.
    data_inicio: str = db.Column(db.String(10))
    data_fim: str = db.Column(db.String(10))
    hora_inicio: str = db.Column(db.String(5))
    hora_fim: str = db.Column(db.String(5))
    
    dias_semana: str = db.Column(db.String(20))   # Ex: "Segunda,Quarta,Sexta"
    programa: str = db.Column(db.String(50))      # Esporte, Profissionalizante, etc.
    turno: str = db.Column(db.String(20))
    centro_custo: str = db.Column(db.String(150))
    ordenacao: int = db.Column(db.Integer)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='turmas')

    periodo_letivo_id: int = db.Column(db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=True)
    periodo_letivo = db.relationship('PeriodoLetivo', backref='turmas')

    curso_id: int = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=True)
    curso = db.relationship('Curso', backref='turmas')

    # Relacionamento M:1 com o Professor (User)
    professor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    professor = db.relationship('User', backref='turmas_vinculadas')

    avaliacao_inicial: str = db.Column(db.Text)
    avaliacao_percurso: str = db.Column(db.Text)
    avaliacao_final: str = db.Column(db.Text)
    conselho_concluido: bool = db.Column(db.Boolean, default=False, nullable=False)

    conselhos = db.relationship('ConselhoClasse', backref='turma', lazy=True)

    @property
    def freq_geral(self) -> float:
        """
        Calcula a frequência da turma.
        Presença: A, B, C, D
        Falta: F
        J (justificada): não conta nem como presença nem como falta
        Denominador: apenas registros A+B+C+D+F
        """
        try:
            from app.models import Frequencia
            registros = Frequencia.query.filter_by(turma_id=self.id).all()
            contaveis = [r for r in registros if r.conceito in ('A', 'B', 'C', 'D', 'F')]
            total = len(contaveis)
            presentes = sum(1 for r in contaveis if r.conceito in ('A', 'B', 'C', 'D'))
            return round((presentes / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            return 0.0

    @property
    def alunos_ativos_count(self) -> int:
        """Retorna o total de alunos ativos vinculados a esta turma."""
        from app.models import Aluno
        return self.alunos.filter(Aluno.ativo == True).count()

    @classmethod
    def get_ativas(cls) -> List['Turma']:
        """Retorna todas as turmas ativas no sistema ordenadas numericamente/alfabeticamente por nome."""
        return db.session.execute(
            select(cls).where(cls.ativo == True).order_by(cls.nome)
        ).scalars().all()

# ---------------------------------------------------------------------------
# ALUNOS
# ---------------------------------------------------------------------------
class Aluno(db.Model):
    """
    Estudante matriculado. Contém relacionamento M-N com Turma para que um indivíduo possa cursar vários programas simultaneamente.
    """
    __tablename__ = 'aluno'
    
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    nome_social: str = db.Column(db.String(100))
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    data_nascimento: date = db.Column(db.Date)
    foto_path: str = db.Column(db.String(255))
    _escolaridade_json: str = db.Column('escolaridade_json', db.Text)
    _identificacao_json: str = db.Column('identificacao_json', db.Text)
    _socioeconomico_json: str = db.Column('socioeconomico_json', db.Text)
    _diversidade_json: str = db.Column('diversidade_json', db.Text)
    cpf: str = db.Column(db.String(20))
    rg: str = db.Column(db.String(50))
    whatsapp: str = db.Column(db.String(30))
    email: str = db.Column(db.String(120))
    nivel: str = db.Column(db.String(20)) # Básico, Intermediário, Avançado

    created_by_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    created_by_name: str = db.Column(db.String(100))
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)

    @property
    def matricula(self) -> str:
        if not self.id:
            return None
        return f"{self.id:05d}.{datetime.utcnow().year}"

    @property
    def foto(self) -> str:
        return self.foto_path

    @property
    def escolaridade_json(self):
        if not self._escolaridade_json:
            return {}
        try:
            return json.loads(self._escolaridade_json)
        except Exception:
            return {}

    @escolaridade_json.setter
    def escolaridade_json(self, value):
        if value is None:
            self._escolaridade_json = None
        else:
            self._escolaridade_json = json.dumps(value)

    @property
    def identificacao_json(self):
        if not self._identificacao_json:
            return {}
        try:
            return json.loads(self._identificacao_json)
        except Exception:
            return {}

    @identificacao_json.setter
    def identificacao_json(self, value):
        if value is None:
            self._identificacao_json = None
        else:
            self._identificacao_json = json.dumps(value)

    @property
    def socioeconomico_json(self):
        if not self._socioeconomico_json:
            return {}
        try:
            return json.loads(self._socioeconomico_json)
        except Exception:
            return {}

    @socioeconomico_json.setter
    def socioeconomico_json(self, value):
        if value is None:
            self._socioeconomico_json = None
        else:
            self._socioeconomico_json = json.dumps(value)

    @property
    def diversidade_json(self):
        if not self._diversidade_json:
            return {}
        try:
            return json.loads(self._diversidade_json)
        except Exception:
            return {}

    @diversidade_json.setter
    def diversidade_json(self, value):
        if value is None:
            self._diversidade_json = None
        else:
            self._diversidade_json = json.dumps(value)

    unidade = db.relationship('Unidade', backref='alunos_unidade')
    created_by = db.relationship('User', backref='alunos_criados', foreign_keys=[created_by_id])

    # Relacionamento M:N cruzado na tabela inscricoes
    turmas = db.relationship(
        'Turma',
        secondary='inscricoes',
        backref=db.backref('alunos', lazy='dynamic',
                           overlaps='inscricoes,turma'),
        overlaps='inscricoes,turma'
    )


    @property
    def idade(self) -> int:
        """
        Calcula no runtime a idade atual do aluno.
        A lógia subtrai 1 ano dependendo se a data contemporânea antecede ou não o mês/dia natalino.
        """
        if not self.data_nascimento:
            return 0
        hoje = date.today()
        # Expressão matemática onde False é 0 e True é 1 subtraindo do total (M, D) < (M, D)
        return hoje.year - self.data_nascimento.year - (
            (hoje.month, hoje.day) < (self.data_nascimento.month, self.data_nascimento.day)
        )

# ---------------------------------------------------------------------------
# FREQUÊNCIA E DIÁRIO DE AULA MÓDULO PÚBLICO
# ---------------------------------------------------------------------------
class Frequencia(db.Model):
    """Registro Unitário de Pauta de presença/Conceito de Aluno por Turma e Dia."""
    __tablename__ = 'frequencia'
    
    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data: str = db.Column(db.String(20), nullable=False)
    conceito: str = db.Column(db.String(1))   # A, B, C, D, F, J
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='frequencias')

    @hybrid_property
    def presente(self) -> bool:
        return self.conceito in ['A', 'B', 'C', 'D']

    @presente.expression
    def presente(cls):
        return cls.conceito.in_(['A', 'B', 'C', 'D'])

class RegistroAula(db.Model):
    """Assinatura do Educador do que ocorreu numa Aula/Turma em determinado dia."""
    __tablename__ = 'registro_aula'
    
    id: int = db.Column(db.Integer, primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data: str = db.Column(db.String(20), nullable=False)  # YYYY-MM-DD
    tema_id: int = db.Column(db.Integer, db.ForeignKey('tema_aula.id'), nullable=True)
    observacoes: str = db.Column(db.Text)
    instrutor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade    = db.relationship('Unidade', backref='diarios_unidade')
    turma_rel  = db.relationship('Turma', backref='diarios')
    tema       = db.relationship('TemaAula', foreign_keys=[tema_id])
    instrutor  = db.relationship('User', foreign_keys=[instrutor_id])


class TemaAula(db.Model):
    """Tópico macro de ensino (Planejamento Pedagógico). Associado a um Curso."""
    __tablename__ = 'tema_aula'

    id: int       = db.Column(db.Integer, primary_key=True)
    curso_id: int = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=True)   # legado
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    titulo: str   = db.Column(db.String(200))
    programa: str = db.Column(db.String(50))
    ativo: bool   = db.Column(db.Boolean, default=True, nullable=False)
    data: str     = db.Column(db.String(20))

    unidade = db.relationship('Unidade', backref='temas_unidade')
    turma   = db.relationship('Turma',   backref='temas_disponiveis')
    curso   = db.relationship('Curso',   backref='temas')


class Registro(db.Model):
    """
    Armazenamento cru flexível (JSON) para fluxos de formulários flexíveis construídos na base anterior.
    """
    __tablename__ = 'registro'
    
    id: int = db.Column(db.Integer, primary_key=True)
    educador_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    turma: str = db.Column(db.String(100))
    mes: str = db.Column(db.String(20))
    turno: str = db.Column(db.String(20))
    dados_json: str = db.Column(db.Text)
    criado_em: datetime = db.Column(db.DateTime, default=get_local_now)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='registros_flexiveis')

    educador = db.relationship('User', backref='registros')


# ---------------------------------------------------------------------------
# CONSELHO DE CLASSE
# ---------------------------------------------------------------------------
class ConfiguracaoSistema(db.Model):
    """Tabela Chave/Valor para parametrizações e toggles de sistema."""
    __tablename__ = 'configuracao_sistema'
    
    id: int = db.Column(db.Integer, primary_key=True)
    chave: str = db.Column(db.String(50), unique=True, nullable=False)
    valor: str = db.Column(db.String(100))
    descricao: str = db.Column(db.String(255))
    
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='configuracoes')


class PerguntaConselho(db.Model):
    __tablename__ = 'conselho_pergunta'
    id: int = db.Column(db.Integer, primary_key=True)
    etapa: str = db.Column(db.String(20))                   # INICIAL, PERCURSO, FINAL
    tipo: str = db.Column(db.String(20), default='ALUNO')  # TURMA ou ALUNO
    texto: str = db.Column(db.Text, nullable=False)
    opcoes: str = db.Column(db.Text)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)

class OpcaoProximaTurma(db.Model):
    __tablename__ = 'opcao_proxima_turma'
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)

class Nivel(db.Model):
    __tablename__ = 'nivel'
    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), unique=True, nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'))


class ConselhoClasse(db.Model):
    """Estado final e sumário da passagem de um Aluno em conselho pedagógico ou ciclo."""
    __tablename__ = 'conselho_classe'
    
    id: int = db.Column(db.Integer, primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    etapa: str = db.Column(db.String(20), nullable=False)  # INICIAL, PERCURSO, FINAL
    data_inicio: date = db.Column(db.Date)
    data_fim: date = db.Column(db.Date)
    concluido: bool = db.Column(db.Boolean, default=False, nullable=False)
    instrutor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    observacao: str = db.Column(db.Text)
    situacao_final: str = db.Column(db.String(30))  # Aprovado, Reprovado por Falta, Desistente, Evadido
    proxima_turma_id: int = db.Column(db.Integer, db.ForeignKey('opcao_proxima_turma.id'))
    proxima_turma_obj = db.relationship('OpcaoProximaTurma')

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='conselhos_unidade')

    respostas = db.relationship('ConselhoResposta', backref='conselho', lazy=True)


class Transferencia(db.Model):
    __tablename__ = 'transferencia'
    id: int = db.Column(db.Integer, primary_key=True)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    turma_origem_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    turma_destino_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    data_transferencia: datetime = db.Column(db.DateTime, nullable=False, default=get_local_now)
    observacoes: str = db.Column(db.Text)
    
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)

    aluno = db.relationship('Aluno', backref='transferencias')
    turma_origem = db.relationship('Turma', foreign_keys=[turma_origem_id])
    turma_destino = db.relationship('Turma', foreign_keys=[turma_destino_id])


class ConselhoResposta(db.Model):
    __tablename__ = 'conselho_resposta'
    id: int = db.Column(db.Integer, primary_key=True)
    conselho_id: int = db.Column(db.Integer, db.ForeignKey('conselho_classe.id'), nullable=False)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    pergunta_id: int = db.Column(db.Integer, db.ForeignKey('conselho_pergunta.id'), nullable=False)
    resposta: str = db.Column(db.Text)
    observacao: str = db.Column(db.Text)
    
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='respostas_conselho')

# ---------------------------------------------------------------------------
# SERVIÇO SOCIAL
# ---------------------------------------------------------------------------
class AgendaServicoSocial(db.Model):
    __tablename__ = 'agenda_servico_social'
    
    id = db.Column(db.Integer, primary_key=True)
    titulo = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(100), nullable=False)
    data = db.Column(db.Date, nullable=False)
    hora = db.Column(db.String(5), nullable=False)
    localizacao = db.Column(db.String(255), nullable=True)
    descricao = db.Column(db.Text, nullable=True)
    google_event_id = db.Column(db.String(255), nullable=True)
    
    # Armazena e-mails dos participantes separados por vírgula
    # Ex: "pai@email.com, aluno@email.com"
    participantes_emails = db.Column(db.Text, nullable=True) 
    # Relação com o usuário que criou o registro
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    autor = db.relationship('User', backref='agendamentos_sociais')
    data_criacao = db.Column(db.DateTime, default=db.func.current_timestamp())

    def get_attendees_list(self):
        """Converte a string de e-mails em uma lista formatada para a API do Google."""
        if not self.participantes_emails:
            return []
        emails = [e.strip() for e in self.participantes_emails.split(',')]
        return [{'email': email} for email in emails]

# ---------------------------------------------------------------------------
# LOGS DE AUDITORIA DE SEGURANÇA
# ---------------------------------------------------------------------------
class LogAcao(db.Model):
    """Log de atividades e registros sensíveis executados pelos usuários via painel."""
    __tablename__ = 'log_acao'
    
    id: int = db.Column(db.Integer, primary_key=True)
    data_hora: datetime = db.Column(db.DateTime, default=get_local_now)
    usuario_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    usuario_nome: str = db.Column(db.String(100))
    acao: str = db.Column(db.String(255))
    detalhes: str = db.Column(db.Text)
    ip: str = db.Column(db.String(50))
    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='logs_unidade')

    usuario = db.relationship('User', backref='logs')

    @staticmethod
    def normalize(text):
        from unidecode import unidecode
        return unidecode(text).lower()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if 'acao' in kwargs:
            self.acao_normalizada = self.normalize(kwargs['acao'])
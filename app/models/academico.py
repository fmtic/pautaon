"""
================================================================================
ACADEMICO.PY - Estrutura acadêmica
================================================================================

Contém:
    - PeriodoLetivo : semestre/módulo/ciclo de uma unidade.
    - Turma         : agrupamento operacional de alunos.
    - TemaAula      : tópico macro do planejamento pedagógico.

Turma é a entidade mais conectada do sistema: liga unidade, período letivo,
curso, professor (User) e alunos (N:N via Inscricao).

NOTAS DE ONDAS
    - Onda 2A: `data_inicio`, `data_fim`, `hora_inicio`, `hora_fim` e
      `TemaAula.data` agora são DATE/TIME nativos.
    - Onda 2B (limpeza): a property `freq_geral` usa `CONCEITOS_PRESENCA` e
      `CONCEITOS_CONTABEIS` do `app.models.enums` em vez de strings soltas.
    - Onda 3C: `carga_horaria_aula` (minutos/aula) e `carga_horaria_total`
      (minutos totais) são properties calculadas em `Turma`. `Curso.carga_horaria`
      foi removido. Use `formatar_ch()` de `app.utils.formatters` para exibição.
================================================================================
"""

from datetime import time

from app.models.base import db, datetime, date, select, get_local_now, List
from app.models.enums import CONCEITOS_PRESENCA, CONCEITOS_CONTABEIS
from app.models.auditoria_mixin import AuditoriaMixin
from app.models.base import SoftDeleteMixin, TenantMixin


class PeriodoLetivo(SoftDeleteMixin, TenantMixin, db.Model):
    """
    Período letivo (semestre, módulo, ciclo) de uma unidade.

    Delimita datas, agrega turmas e centraliza indicadores (ex.: estimativa de
    alunos, alunos enturmados). Também serve de âncora para Dias Bloqueados e
    Períodos de Conselho.

    Regras:
        - `data_fim` deve ser posterior a `data_inicio` (validação de negócio).
        - Inativar um período não inativa automaticamente suas turmas.
    """
    __tablename__ = 'periodo_letivo'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(150), nullable=False)
    data_inicio: date = db.Column(db.Date, nullable=False)
    data_fim: date = db.Column(db.Date, nullable=False)
    centro_custo: str = db.Column(db.String(150))
    estimativa_alunos: int = db.Column(db.Integer, default=0, nullable=False)

    unidade = db.relationship('Unidade', backref='periodos')

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)
    updated_at: datetime = db.Column(db.DateTime, onupdate=get_local_now)

    @property
    def nome_exibicao(self) -> str:
        unidade_nome = self.unidade.nome if self.unidade else None
        return f"{unidade_nome} {self.nome}" if unidade_nome else self.nome

    def alunos_enturmados(self) -> int:
        """
        Retorna o total de alunos ÚNICOS matriculados em qualquer turma
        pertencente a este período letivo.

        Importante: um aluno em duas turmas do mesmo período conta UMA vez.
        """
        from app.models.pessoas import Aluno

        return (
            Aluno.query
            .join(Aluno.turmas)
            .filter(Turma.periodo_letivo_id == self.id)
            .distinct()
            .count()
        )


class Turma(SoftDeleteMixin, TenantMixin, AuditoriaMixin, db.Model):
    """
    Turma: agrupamento operacional de alunos em um curso/período.

    Uma Turma conecta:
        - Unidade (tenant)                 -> unidade_id
        - Período Letivo                   -> periodo_letivo_id
        - Curso                            -> curso_id
        - Professor responsável (User)     -> professor_id
        - Alunos (N:N via Inscricao)       -> alunos (backref)

    Regras:
        - `dias_semana` é uma string CSV (ex.: "Segunda,Quarta,Sexta").
        - `conselho_concluido` é o flag que libera o encerramento da turma.
        - `carga_horaria_aula` e `carga_horaria_total` são inteiros em MINUTOS.
          Use `formatar_ch()` de `app.utils.formatters` para exibição legível.
    """
    __tablename__ = 'turma'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)

    # Datas/horas nativas (Onda 2A - antes eram VARCHAR).
    data_inicio: date = db.Column(db.Date)
    data_fim: date = db.Column(db.Date)
    hora_inicio: time = db.Column(db.Time)
    hora_fim: time = db.Column(db.Time)

    dias_semana: str = db.Column(db.String(20))
    programa: str = db.Column(db.String(50))
    turno: str = db.Column(db.String(20))
    centro_custo: str = db.Column(db.String(150))
    ordenacao: int = db.Column(db.Integer)

    unidade = db.relationship('Unidade', backref='turmas')

    periodo_letivo_id: int = db.Column(db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=True)
    periodo_letivo = db.relationship('PeriodoLetivo', backref='turmas')

    curso_id: int = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=True)
    curso = db.relationship('Curso', backref='turmas')

    professor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    professor = db.relationship(
        'User', foreign_keys=[professor_id], backref='turmas_vinculadas'
    )

    avaliacao_inicial: str = db.Column(db.Text)
    avaliacao_percurso: str = db.Column(db.Text)
    avaliacao_final: str = db.Column(db.Text)
    conselho_concluido: bool = db.Column(db.Boolean, default=False, nullable=False)

    conselhos = db.relationship('ConselhoClasse', backref='turma', lazy=True)

    @property
    def freq_geral(self) -> float:
        """
        Frequência geral da turma (0.0 a 100.0).

        Regras de contagem (via `app.models.enums`):
            - `CONCEITOS_PRESENCA` (A/B/C/D) = presença.
            - `CONCEITOS_CONTABEIS` = presença + F (denominador).
            - J (justificada) não entra em nenhum dos dois.
            - Se não houver registros contáveis, retorna 0.0.
        """
        try:
            from app.models.aulas import Frequencia

            registros = Frequencia.query.filter_by(turma_id=self.id).all()

            # Comparação funciona com enum ou string porque os enums herdam de str.
            contaveis = [r for r in registros if r.conceito in CONCEITOS_CONTABEIS]
            total = len(contaveis)
            presentes = sum(
                1 for r in contaveis if r.conceito in CONCEITOS_PRESENCA
            )
            return round((presentes / total) * 100, 1) if total > 0 else 0.0
        except Exception:
            return 0.0

    @property
    def alunos_ativos_count(self) -> int:
        """Total de alunos com `ativo=True` vinculados a esta turma."""
        from app.models.pessoas import Aluno
        return self.alunos.filter(Aluno.ativo == True).count()

    def dias_aula_efetivos(self) -> int:
        """
        Quantidade de dias de aula desta turma no período letivo.

        Usa o mesmo calendário da pauta: dias da semana entre data_inicio e
        data_fim, excluindo DiaBloqueado do período (com exceções de
        DiaBloqueadoTurma já descontadas).
        """
        from app.utils.logica import calcular_dias_aula_turma
        return calcular_dias_aula_turma(self)

    @property
    def carga_horaria_aula(self) -> int | None:
        """
        Duração de uma aula em MINUTOS (hora_fim - hora_inicio).

        Retorna None se hora_inicio ou hora_fim não estiverem definidas ou se
        hora_fim <= hora_inicio.
        """
        if not self.hora_inicio or not self.hora_fim:
            return None
        delta = (
            self.hora_fim.hour * 60 + self.hora_fim.minute
            - self.hora_inicio.hour * 60 - self.hora_inicio.minute
        )
        return delta if delta > 0 else None

    @property
    def carga_horaria_total(self) -> int | None:
        """
        C.H. Total em MINUTOS = carga_horaria_aula × dias_aula_efetivos().

        Retorna None se carga_horaria_aula for None ou se não houver dias de
        aula calculáveis (sem data_inicio/data_fim/dias_semana).
        """
        ch_aula = self.carga_horaria_aula
        if ch_aula is None:
            return None
        dias = self.dias_aula_efetivos()
        return ch_aula * dias if dias else None

    @classmethod
    def get_ativas(cls) -> List['Turma']:
        """Lista todas as turmas ativas, ordenadas por nome."""
        return db.session.execute(
            select(cls).where(cls.ativo == True).order_by(cls.nome)
        ).scalars().all()


class TemaAula(SoftDeleteMixin, TenantMixin, AuditoriaMixin, db.Model):
    """
    Tópico macro de ensino (planejamento pedagógico).

    Um TemaAula pertence preferencialmente a um Curso e é referenciado por
    RegistroAula para indicar "o que foi dado" em uma aula.

    Campos:
        - `turma_id` é legado (temas eram por turma). Prefira `curso_id`.
        - `ordem` define a sequência didática dentro do curso.
        - `ativo=False` esconde o tema de seletores, mas não apaga histórico.
    """
    __tablename__ = 'tema_aula'

    id: int = db.Column(db.Integer, primary_key=True)
    curso_id: int = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=True)  # legado
    titulo: str = db.Column(db.String(200))
    programa: str = db.Column(db.String(50))
    data: date = db.Column(db.Date)
    ordem: int = db.Column(db.Integer, default=0, nullable=False)

    unidade = db.relationship('Unidade', backref='temas_unidade')
    turma = db.relationship('Turma', backref='temas_disponiveis')
    curso = db.relationship('Curso', backref='temas')

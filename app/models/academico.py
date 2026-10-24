"""
================================================================================
ACADEMICO.PY - Estrutura acadêmica
================================================================================

Contém:
    - PeriodoLetivo : semestre/módulo/ciclo de uma unidade.
    - Turma         : agrupamento operacional de alunos.
    - TurmaCurso    : oferta concreta de um curso dentro de uma turma.
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
    - Onda 4 (Fase 1, múltiplos cursos por turma): `TurmaCurso` é a unidade
      acadêmica concreta; os atributos de horário/professor/turno replicam-se
      na oferta e as colunas legadas de `Turma` permanecem até o contrato final.
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

    def freq_geral_oferta(self, turma_curso_id: int) -> float:
        """
        Frequência geral de UMA oferta da turma (0.0 a 100.0) — Onda 4 D3a.

        Mesmo cálculo da property `freq_geral` (que não aceita parâmetro e
        segue misturando cursos quando a turma tem 2+ ofertas ativas), mas
        filtrado por `turma_curso_id`. Regras de contagem idênticas:
        CONCEITOS_PRESENCA no numerador, CONCEITOS_CONTABEIS no denominador,
        J fora de ambos.

        PENDÊNCIA DE OTIMIZAÇÃO (Onda 4, Etapa K): faz 1 consulta por oferta;
        numa lista com N turmas × M ofertas isso vira N+1. Trocar por
        agregação em lote (SELECT turma_curso_id, conceito, COUNT(*) ... WHERE
        turma_id IN (...) GROUP BY turma_curso_id, conceito).
        """
        try:
            from app.models.aulas import Frequencia

            registros = Frequencia.query.filter_by(
                turma_id=self.id, turma_curso_id=turma_curso_id
            ).all()

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


class TurmaCurso(SoftDeleteMixin, TenantMixin, AuditoriaMixin, db.Model):
    """
    Oferta concreta de um Curso dentro de uma Turma (Onda 4 — Fase 1).

    A Turma é o agrupador lógico; o vínculo acadêmico efetivo do aluno é a
    matrícula em uma oferta (TurmaCurso). Frequência, diário, conselho e
    transferências passam a apontar para a oferta nas fases seguintes.

    Regras:
        - `UNIQUE(turma_id, curso_id)`: cada curso é ofertado no máximo uma
          vez na mesma turma, independentemente de professor/turno/horário.
          O mesmo curso pode ser ofertado em turmas diferentes.
        - `principal` pertence ao vínculo turma↔curso (nunca ao aluno nem ao
          curso globalmente). No máximo um por turma: garantido por índice
          único parcial. A obrigatoriedade de exatamente um quando houver
          2+ ofertas ativas é validada pela camada de serviço/UI (Fase 2).
        - `centro_custo` NULL ⇒ herda o valor compartilhado da turma
          (modalidades compartilhado/individual — Fase 3).
        - Atributos próprios da oferta (professor, turno, dias, horários,
          datas) foram replicados de `Turma`; durante a transição a camada
          de compatibilidade mantém as colunas legadas da turma para turmas
          com oferta única (não-remove sem migrar leitores).
    """
    __tablename__ = 'turma_curso'
    __table_args__ = (
        db.UniqueConstraint('turma_id', 'curso_id', name='uix_turma_curso_oferta'),
        # No máximo um curso principal por turma ativa (índice único parcial).
        db.Index(
            'uix_turma_curso_principal',
            'turma_id',
            unique=True,
            postgresql_where=db.text('principal AND ativo'),
            sqlite_where=db.text('principal = 1 AND ativo = 1'),
        ),
        db.Index('ix_turma_curso_curso_id', 'curso_id'),
        db.Index('ix_turma_curso_professor_id', 'professor_id'),
    )

    id: int = db.Column(db.Integer, primary_key=True)

    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    curso_id: int = db.Column(db.Integer, db.ForeignKey('curso.id'), nullable=False)

    principal: bool = db.Column(
        db.Boolean, default=False, nullable=False,
        comment='Curso principal da turma (vínculo, não atributo do aluno/curso)',
    )

    # Atributos da oferta (legado: ficavam em Turma; migrados fase a fase).
    professor_id: int = db.Column(
        db.Integer, db.ForeignKey('user.id'), nullable=True,
        comment='Professor responsável pela oferta do curso na turma',
    )
    turno: str = db.Column(db.String(20))
    dias_semana: str = db.Column(db.String(20))
    hora_inicio: time = db.Column(db.Time)
    hora_fim: time = db.Column(db.Time)
    data_inicio: date = db.Column(db.Date)
    data_fim: date = db.Column(db.Date)
    centro_custo: str = db.Column(
        db.String(150),
        comment='Centro de custo individual; NULL = usa o compartilhado da turma',
    )
    programa: str = db.Column(db.String(50))

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    turma = db.relationship(
        'Turma',
        backref=db.backref('ofertas_curso', cascade='all, delete-orphan'),
    )
    curso = db.relationship('Curso', backref='ofertas_turma')
    # foreign_keys explícito: o modelo tem duas FKs para user.id
    # (professor_id + updated_by_id do AuditoriaMixin). Convenção do MER §1.
    professor = db.relationship(
        'User', foreign_keys=[professor_id], backref='ofertas_como_responsavel'
    )

    @property
    def carga_horaria_aula(self) -> int | None:
        """
        Duração de uma aula da OFERTA em MINUTOS (Onda 4, Etapa K).

        Mesma regra de `Turma.carga_horaria_aula`: `hora_fim - hora_inicio`,
        herdando os horários da turma quando a oferta não define os próprios
        (NULL = compartilhado). None se ausente ou `hora_fim <= hora_inicio`.
        """
        inicio = self.hora_inicio
        fim = self.hora_fim
        if (not inicio or not fim) and self.turma is not None:
            inicio = inicio or self.turma.hora_inicio
            fim = fim or self.turma.hora_fim
        if not inicio or not fim:
            return None
        delta = (
            fim.hour * 60 + fim.minute
            - inicio.hour * 60 - inicio.minute
        )
        return delta if delta > 0 else None

    @property
    def carga_horaria_total(self) -> int | None:
        """
        C.H. Total da OFERTA em MINUTOS = carga_horaria_aula × nº de dias de
        aula da oferta (Onda 4, Etapa K).

        Reaproveita `datas_aula_oferta` (agenda própria da oferta, até a
        data_fim efetiva) e o MESMO helper de bloqueios usado pela turma
        (`_blocked_dates_str` sobre a turma da oferta). None se a aula não
        tiver duração ou se não houver dias calculáveis.
        """
        ch_aula = self.carga_horaria_aula
        if ch_aula is None:
            return None
        from app.services.turma_curso import datas_aula_oferta
        from app.utils.logica import _blocked_dates_str

        blocked = _blocked_dates_str(self.turma) if self.turma is not None else set()
        datas = datas_aula_oferta(self, blocked=blocked)
        return ch_aula * len(datas) if datas else None


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

"""
================================================================================
ACADEMICO.PY - Estrutura acadêmica
================================================================================

Contém:
    - PeriodoLetivo : semestre/módulo/ciclo de uma unidade.
    - Turma         : agrupamento operacional de alunos.
    - TurmaCurso    : oferta concreta de um curso dentro de uma turma.
    - TurmaCursoHorario : grade de horário por dia da oferta (H1).
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
    - H1 (horário por dia na oferta): `TurmaCursoHorario` nasce como fonte dos
      dias e horários da oferta; `dias_semana`/`hora_inicio`/`hora_fim` da
      oferta viram PROJEÇÃO transitória (removidas só no H5) e as colunas
      `dias_semana` de `Turma`/`TurmaCurso` ampliam-se para `String(80)`.
================================================================================
"""

from datetime import time

from sqlalchemy import SmallInteger

from app.models.base import db, datetime, date, select, get_local_now, List
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
        Retorna o total de alunos ÚNICOS enturmados neste período letivo.

        ETAPA D3b.3: delega ao serviço único `app.services.enturmado` —
        definição canônica (`Aluno.ativo` + inscrição ativa em turma ativa +
        oferta efetiva/regra M4). Antes qualquer linha de inscrição contava
        (sem `Aluno.ativo`, `Inscricao.ativo`, `Turma.ativo` nem oferta).

        Importante: um aluno em duas turmas do mesmo período conta UMA vez.
        """
        # Import local: modelos não importam serviços no topo (ciclo de
        # inicialização da app — mesmo padrão de `freq_geral`).
        from app.services.enturmado import contar_alunos_enturmados

        return contar_alunos_enturmados(periodo_letivo_id=self.id)


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
        - O encerramento do conselho NÃO vive na turma: desde a D5.5 ele é da
          OFERTA (`turma_curso.conselho_concluido`) e a turma é DERIVADA em
          leitura.
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

    # H1-P2: String(80) — o CSV canônico dos sete dias não cabe em 20.
    dias_semana: str = db.Column(db.String(80))
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

    # LEGADO: parecer coletivo agora em turma_curso.avaliacao_*; remover após
    # conferir dump autêntico (decisão D5.5 — nenhuma leitura/escrita nova).
    avaliacao_inicial: str = db.Column(db.Text)
    avaliacao_percurso: str = db.Column(db.Text)
    avaliacao_final: str = db.Column(db.Text)

    conselhos = db.relationship('ConselhoClasse', backref='turma', lazy=True)

    @property
    def freq_geral(self) -> float:
        """
        Frequência geral da turma (0.0 a 100.0) — ETAPA D3b.2.

        Delegado ao serviço único `app.services.frequencia_oferta`:
        soma de TODAS as linhas da turma (ofertas + legado) — regra POR
        TURMA, mesmo número de antes (refactor puro).
        Regras de contagem no serviço: `CONCEITOS_PRESENCA` no numerador,
        presença + F no denominador, J fora de ambos, 1 casa decimal.
        """
        try:
            # Import local do serviço para não criar ciclo models → services.
            from app.services.frequencia_oferta import agregar_por_turma

            info = agregar_por_turma([self.id]).get(self.id)
            return info.pct_turma if info else 0.0
        except Exception:
            return 0.0

    def freq_geral_oferta(self, turma_curso_id: int) -> float:
        """
        Frequência geral de UMA oferta da turma (0.0 a 100.0) — D3b.2.

        Delegado ao serviço único: só as linhas da oferta, com as linhas
        legadas (`turma_curso_id IS NULL`) entrando apenas quando a oferta
        é a única ativa da turma (regra D2 da pauta — caso DECIDIDO na
        etapa: numa turma de oferta única o legado agora conta).
        Fora da turma (ou sem linha contável) → 0.0, como antes.
        """
        try:
            from app.services.frequencia_oferta import agregar_por_oferta

            info = agregar_por_oferta(
                [turma_curso_id], por_turma=self.id
            ).get(turma_curso_id)
            if info is None or info.turma_id != self.id:
                return 0.0
            return info.pct
        except Exception:
            return 0.0

    @property
    def alunos_ativos_count(self) -> int:
        """Total de alunos ativos, sem contar separadamente cada oferta."""
        from app.models.pessoas import Aluno
        from app.models.matriculas import Inscricao

        return (
            db.session.query(db.func.count(db.func.distinct(Aluno.id)))
            .join(Inscricao, Inscricao.aluno_id == Aluno.id)
            .filter(
                Inscricao.turma_id == self.id,
                Inscricao.ativo.is_(True),
                Aluno.ativo.is_(True),
            )
            .scalar()
            or 0
        )

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
        Duração uniforme da oferta principal em minutos.

        Grades não uniformes não têm uma duração única e retornam ``None``.
        Sem ofertas ativas, preserva o escalar legado da turma.
        """
        from app.services.turma_curso_horario import cargas_horarias_turmas_em_lote
        return cargas_horarias_turmas_em_lote([self])[self.id].carga_horaria_aula

    @property
    def carga_horaria_total(self) -> int | None:
        """
        Tempo físico em minutos da turma. Em cada data, intervalos ativos são
        unidos, contando sobreposições uma vez e somando intervalos disjuntos.
        Sem oferta ativa, preserva o cálculo escalar legado com aviso.
        """
        from app.services.turma_curso_horario import carga_horaria_total_turma
        return carga_horaria_total_turma(self)

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
        - D5.1: a oferta ganha `conselho_concluido` e os pareceres coletivos
          `avaliacao_inicial/percurso/final` (mesmos tipos de `Turma`),
          preparando a migração do conselho por oferta (rotas em D5.2+).
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
    # H1-P2: String(80); desde o H2 esta coluna é PROJEÇÃO da grade
    # (`TurmaCursoHorario`) gravada por `sincronizar_projecao_horario` —
    # não escreva nela diretamente. Removida no H5.
    dias_semana: str = db.Column(db.String(80))
    hora_inicio: time = db.Column(db.Time)
    hora_fim: time = db.Column(db.Time)
    data_inicio: date = db.Column(db.Date)
    data_fim: date = db.Column(db.Date)
    centro_custo: str = db.Column(
        db.String(150),
        comment='Centro de custo individual; NULL = usa o compartilhado da turma',
    )
    programa: str = db.Column(db.String(50), nullable=False)

    # D5.1 (Onda 4): conselho de classe por oferta. Espelham os campos
    # legados de `Turma` (mesmos tipos); as colunas da turma permanecem
    # intactas e continuam sendo a fonte das rotas atuais até D5.2/D5.3.
    conselho_concluido: bool = db.Column(
        db.Boolean, default=False, server_default=db.text('false'),
        nullable=False,
        comment='Encerramento do conselho da OFERTA (D5.1); legado vive em Turma',
    )
    avaliacao_inicial: str = db.Column(db.Text)
    avaliacao_percurso: str = db.Column(db.Text)
    avaliacao_final: str = db.Column(db.Text)

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
    # H1: grade de horário por dia — fonte dos dias/horários da oferta
    # (decisão 5). lazy="selectin": uma consulta por lote, sem N+1 em
    # listagens. Cascade físico acompanha o de `ofertas_curso`.
    horarios = db.relationship(
        'TurmaCursoHorario',
        order_by='TurmaCursoHorario.dia_semana',
        lazy='selectin',
        cascade='all, delete-orphan',
        passive_deletes=True,
        back_populates='oferta',
    )

    @property
    def carga_horaria_aula(self) -> int | None:
        """
        Duração única da oferta em minutos; grade não uniforme retorna ``None``.
        Oferta sem grade usa a compatibilidade escalar legada, com aviso.
        """
        from app.services.turma_curso_horario import cargas_horarias_ofertas_em_lote
        return cargas_horarias_ofertas_em_lote([self])[self.id].carga_horaria_aula

    @property
    def carga_horaria_total(self) -> int | None:
        """
        Soma em minutos a duração da grade de cada ocorrência válida da oferta.
        """
        from app.services.turma_curso_horario import cargas_horarias_ofertas_em_lote
        return cargas_horarias_ofertas_em_lote([self])[self.id].carga_horaria_total


class TurmaCursoHorario(db.Model):
    """
    Grade de horário por dia de aula de uma OFERTA (H1).

    Fonte dos dias E dos horários da oferta (decisão 5): cada linha é um
    dia da semana (0 = segunda … 6 = domingo, `date.weekday()`) com um par
    de horários opcional. As colunas escalares de `TurmaCurso` são apenas
    projeção transitória desta grade (removidas no H5).

    Regras (decisão 2, garantidas por CHECK no schema):
        - `dia_semana` ∈ 0–6, único por oferta (`uix_turma_curso_horario_dia`).
        - Linha com `hora_inicio` e `hora_fim` ambos NULL é permitida (dia
          sem horário); só um extremo preenchido é inválido.
        - Quando ambos preenchidos: `hora_fim` > `hora_inicio` (mesmo dia,
          sem virar meia-noite).

    Sem `unidade_id`, sem `AuditoriaMixin`, sem `ativo`: o escopo vem da
    oferta (como `inscricoes`); a grade vale retroativamente para todo o
    período da oferta (decisão 4, sem versionar).
    """
    __tablename__ = 'turma_curso_horario'

    id: int = db.Column(db.Integer, primary_key=True)
    turma_curso_id: int = db.Column(
        db.Integer,
        db.ForeignKey('turma_curso.id', ondelete='CASCADE'),
        nullable=False,
    )
    # 0 = segunda … 6 = domingo (date.weekday(); decisão 1).
    dia_semana: int = db.Column(SmallInteger, nullable=False)
    hora_inicio: time | None = db.Column(db.Time)
    hora_fim: time | None = db.Column(db.Time)

    created_at: datetime = db.Column(db.DateTime, default=get_local_now)

    oferta = db.relationship('TurmaCurso', back_populates='horarios')

    __table_args__ = (
        # Um dia por oferta (unicidade plena; também cobre o índice FK).
        db.UniqueConstraint(
            'turma_curso_id', 'dia_semana',
            name='uix_turma_curso_horario_dia',
        ),
        db.CheckConstraint(
            'dia_semana >= 0 AND dia_semana <= 6', name='ck_tch_dia',
        ),
        db.CheckConstraint(
            '(hora_inicio IS NULL AND hora_fim IS NULL) '
            'OR (hora_inicio IS NOT NULL AND hora_fim IS NOT NULL)',
            name='ck_tch_par',
        ),
        db.CheckConstraint(
            'hora_inicio IS NULL OR hora_fim IS NULL OR hora_fim > hora_inicio',
            name='ck_tch_fim_maior',
        ),
    )


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

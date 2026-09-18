"""
================================================================================
CONSELHO.PY - Conselho de classe
================================================================================

Contém:
    - PeriodoConselho    : janela de tempo em que o conselho ocorre.
    - PerguntaConselho   : perguntas padronizadas do formulário.
    - OpcaoProximaTurma  : destinos possíveis após o conselho final.
    - ConselhoClasse     : resultado por aluno/turma/etapa.
    - ConselhoResposta   : resposta de uma pergunta para um aluno.

Fluxo: PeríodoLetivo -> PeriodoConselho -> ConselhoClasse -> ConselhoResposta.

NOTAS ONDA 2B
    - `PerguntaConselho.etapa`, `PerguntaConselho.tipo` e
      `ConselhoClasse.etapa` agora são ENUM nativo do Postgres.
    - `ConselhoClasse.situacao_final` continua VARCHAR, mas ganhou CHECK
      constraint restrita ao enum `SituacaoFinal`.
================================================================================
"""

from app.models.base import db, datetime, date, get_local_now
from app.models.enums import EtapaConselho, SituacaoFinal, TipoPergunta


# Fragmento SQL com os valores válidos de situacao_final, montado a partir
# do enum. Mantém a CHECK em sincronia com o Python.
_SITUACAO_FINAL_VALUES_SQL = ", ".join(f"'{s.value}'" for s in SituacaoFinal)


class PeriodoConselho(db.Model):
    """
    Janela de tempo em que o conselho de classe de um período letivo ocorre.

    `conselho_final=True` marca o conselho de encerramento (define aprovação,
    reprovação por falta, desistência, evasão).

    Regras:
        - Vinculado a um `PeriodoLetivo` e a uma `Unidade`.
        - Ao excluir o período letivo, os conselhos são removidos em cascata.
    """
    __tablename__ = 'periodo_conselho'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    data_inicio: date = db.Column(db.Date, nullable=False)
    data_fim: date = db.Column(db.Date, nullable=False)
    conselho_final: bool = db.Column(db.Boolean, default=False, nullable=False)

    periodo_letivo_id: int = db.Column(
        db.Integer, db.ForeignKey('periodo_letivo.id'), nullable=False
    )
    periodo_letivo = db.relationship(
        'PeriodoLetivo',
        backref=db.backref('conselhos', cascade='all, delete-orphan'),
    )

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=False)
    unidade = db.relationship('Unidade', backref='periodos_conselho')


class PerguntaConselho(db.Model):
    """
    Pergunta padronizada do formulário de conselho.

    Campos:
        - `etapa`: INICIAL, PERCURSO ou FINAL (enum nativo).
        - `tipo`:  TURMA (avaliação coletiva) ou ALUNO (avaliação individual)
                   (enum nativo).
        - `opcoes`: string com as alternativas (formato definido pelo frontend).
        - `ativo=False` esconde a pergunta sem apagar respostas históricas.
    """
    __tablename__ = 'conselho_pergunta'

    id: int = db.Column(db.Integer, primary_key=True)

    # Onda 2B: ENUM nativo.
    etapa: EtapaConselho = db.Column(
        db.Enum(
            EtapaConselho,
            name='etapa_conselho_enum',
            create_constraint=False,
            native_enum=True,
        ),
        nullable=True,
    )
    tipo: TipoPergunta = db.Column(
        db.Enum(
            TipoPergunta,
            name='tipo_pergunta_enum',
            create_constraint=False,
            native_enum=True,
        ),
        default=TipoPergunta.ALUNO,
        nullable=True,
    )

    texto: str = db.Column(db.Text, nullable=False)
    opcoes: str = db.Column(db.Text)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)


class OpcaoProximaTurma(db.Model):
    """
    Catálogo de destinos possíveis após o conselho final.
    Ex.: 'Aprovado para Avançado', 'Reencaminhado para Básico', 'Egresso'.
    """
    __tablename__ = 'opcao_proxima_turma'

    id: int = db.Column(db.Integer, primary_key=True)
    nome: str = db.Column(db.String(100), nullable=False)
    ativo: bool = db.Column(db.Boolean, default=True, nullable=False)


class ConselhoClasse(db.Model):
    """
    Resultado do conselho para UM aluno em UMA turma em UMA etapa.

    Campos-chave:
        - `etapa`: INICIAL, PERCURSO ou FINAL (enum nativo).
        - `situacao_final`: Aprovado, Reprovado por Falta, Desistente, Evadido,
          Participação, Concluído (VARCHAR + CHECK).
        - `proxima_turma_id`: destino sugerido após conselho final.
        - `concluido=True` indica que o conselho foi fechado.

    Constraints:
        - UNIQUE (turma_id, aluno_id, etapa): evita dois conselhos abertos
          simultaneamente para o mesmo aluno/turma/etapa.
        - CHECK (situacao_final): restrita ao enum SituacaoFinal.
    """
    __tablename__ = 'conselho_classe'
    __table_args__ = (
        db.UniqueConstraint('turma_id', 'aluno_id', 'etapa',
                            name='uix_conselho_turma_aluno_etapa'),
        db.CheckConstraint(
            f"situacao_final IS NULL OR "
            f"situacao_final IN ({_SITUACAO_FINAL_VALUES_SQL})",
            name='ck_conselho_situacao_final',
        ),
    )

    id: int = db.Column(db.Integer, primary_key=True)
    turma_id: int = db.Column(db.Integer, db.ForeignKey('turma.id'), nullable=False)
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)

    # Onda 2B: ENUM nativo.
    etapa: EtapaConselho = db.Column(
        db.Enum(
            EtapaConselho,
            name='etapa_conselho_enum',
            create_constraint=False,
            native_enum=True,
        ),
        nullable=False,
    )

    data_inicio: date = db.Column(db.Date)
    data_fim: date = db.Column(db.Date)
    concluido: bool = db.Column(db.Boolean, default=False, nullable=False)
    instrutor_id: int = db.Column(db.Integer, db.ForeignKey('user.id'))
    observacao: str = db.Column(db.Text)

    # Continua VARCHAR; a CHECK constraint garante os valores válidos.
    situacao_final: str = db.Column(db.String(30))

    proxima_turma_id: int = db.Column(
        db.Integer, db.ForeignKey('opcao_proxima_turma.id')
    )
    proxima_turma_obj = db.relationship('OpcaoProximaTurma')

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='conselhos_unidade')

    respostas = db.relationship('ConselhoResposta', backref='conselho', lazy=True)


class ConselhoResposta(db.Model):
    """
    Resposta de UMA pergunta do conselho para UM aluno.

    Cada linha é uma resposta individual; o conjunto de respostas forma o
    parecer do aluno naquela etapa.
    """
    __tablename__ = 'conselho_resposta'

    id: int = db.Column(db.Integer, primary_key=True)
    conselho_id: int = db.Column(
        db.Integer, db.ForeignKey('conselho_classe.id'), nullable=False
    )
    aluno_id: int = db.Column(db.Integer, db.ForeignKey('aluno.id'), nullable=False)
    pergunta_id: int = db.Column(
        db.Integer, db.ForeignKey('conselho_pergunta.id'), nullable=False
    )
    resposta: str = db.Column(db.Text)
    observacao: str = db.Column(db.Text)

    unidade_id: int = db.Column(db.Integer, db.ForeignKey('unidade.id'), nullable=True)
    unidade = db.relationship('Unidade', backref='respostas_conselho')
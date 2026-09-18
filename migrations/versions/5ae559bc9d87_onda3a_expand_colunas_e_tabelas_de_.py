"""onda3a: expand - colunas e tabelas de perfil do aluno

Revision ID: 5ae559bc9d87
Revises: ef4e5af7e876
Create Date: 2026-09-17

Onda 3A — Expand
----------------
Adiciona a estrutura nova (4 tabelas + 10 colunas em `aluno`) e faz
backfill a partir dos JSONs legados. Nada é removido nesta migração:
os 4 campos JSON continuam existindo como fallback durante a transição.

DÍVIDA REGISTRADA
-----------------
- `escolaridade_json` (só tem `doc_entregue`) não é migrado nesta onda.
  Decisão adiada para a Onda 3C.
- Backfill é feito em Python (portável entre SQLite e Postgres). Para
  bases muito grandes (>100k alunos), reescrever com SQL nativo.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# Identificadores desta revisão
revision: str = '5ae559bc9d87'
down_revision: str | None = 'ef4e5af7e876'
branch_labels: str | None = None
depends_on: str | None = None


# =============================================================================
# UPGRADE
# =============================================================================

def upgrade() -> None:
    # -------------------------------------------------------------------------
    # 1. Criar as 4 tabelas novas
    # -------------------------------------------------------------------------
    op.create_table(
        'endereco_aluno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=True),
        sa.Column('cep', sa.String(length=10), nullable=True),
        sa.Column('rua', sa.String(length=200), nullable=True),
        sa.Column('numero', sa.String(length=20), nullable=True),
        sa.Column('bairro', sa.String(length=100), nullable=True),
        sa.Column('cidade', sa.String(length=100), nullable=True),
        sa.Column('uf', sa.String(length=2), nullable=True),
        sa.Column('zona', sa.String(length=20), nullable=True),
        sa.Column('possui_acesso_internet', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['aluno.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidade.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aluno_id'),
    )

    op.create_table(
        'perfil_diversidade',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=True),
        sa.Column('genero', sa.String(length=30), nullable=True),
        sa.Column('raca_cor', sa.String(length=30), nullable=True),
        sa.Column('saude_laudo', sa.Boolean(), nullable=False),
        sa.Column('saude_medicacao', sa.String(length=5), nullable=True),
        sa.Column('saude_medicamento_nome', sa.String(length=150), nullable=True),
        sa.Column('saude_observacoes', sa.Text(), nullable=True),
        sa.Column('informacoes_para_professor', sa.Text(), nullable=True),
        sa.Column('autorizacao_imagem', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['aluno.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidade.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aluno_id'),
    )

    op.create_table(
        'perfil_socioeconomico',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=True),
        sa.Column('renda_familiar', sa.String(length=50), nullable=True),
        sa.Column('residente_maior_renda', sa.String(length=50), nullable=True),
        sa.Column('pessoas_residencia', sa.Integer(), nullable=True),
        sa.Column('ocupacao', sa.String(length=50), nullable=True),
        sa.Column('beneficio_social_status', sa.String(length=20), nullable=True),
        sa.Column('beneficio_social_nome', sa.String(length=100), nullable=True),
        sa.Column('meio_transporte', sa.String(length=30), nullable=True),
        sa.Column('vulnerabilidade_social', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['aluno.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidade.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('aluno_id'),
    )

    op.create_table(
        'responsavel_aluno',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('aluno_id', sa.Integer(), nullable=False),
        sa.Column('unidade_id', sa.Integer(), nullable=True),
        sa.Column('tipo', sa.String(length=30), nullable=True),
        sa.Column('nome', sa.String(length=150), nullable=True),
        sa.Column('cpf', sa.String(length=20), nullable=True),
        sa.Column('telefone', sa.String(length=30), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['aluno_id'], ['aluno.id']),
        sa.ForeignKeyConstraint(['unidade_id'], ['unidade.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    # -------------------------------------------------------------------------
    # 2. Adicionar as 10 colunas em `aluno`
    #
    # `vai_acompanhado_aulas` é NOT NULL e a tabela tem dados, então
    # server_default é obrigatório no ALTER.
    # -------------------------------------------------------------------------
    with op.batch_alter_table('aluno', schema=None) as batch_op:
        batch_op.add_column(sa.Column('orgao_rg', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('nacionalidade', sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column('natural_uf', sa.String(length=2), nullable=True))
        batch_op.add_column(sa.Column('natural_cidade', sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column('nome_mae', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('cpf_mae', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('nome_pai', sa.String(length=150), nullable=True))
        batch_op.add_column(sa.Column('cpf_pai', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column(
            'vai_acompanhado_aulas', sa.Boolean(),
            nullable=False, server_default=sa.false(),
        ))
        batch_op.add_column(sa.Column('acompanhante_aulas', sa.String(length=150), nullable=True))

    # -------------------------------------------------------------------------
    # 3. Backfill a partir dos JSONs legados
    # -------------------------------------------------------------------------
    _backfill_onda3a()


# =============================================================================
# DOWNGRADE
# =============================================================================

def downgrade() -> None:
    # Remover as colunas (batch mode lida com SQLite)
    with op.batch_alter_table('aluno', schema=None) as batch_op:
        batch_op.drop_column('acompanhante_aulas')
        batch_op.drop_column('vai_acompanhado_aulas')
        batch_op.drop_column('cpf_pai')
        batch_op.drop_column('nome_pai')
        batch_op.drop_column('cpf_mae')
        batch_op.drop_column('nome_mae')
        batch_op.drop_column('natural_cidade')
        batch_op.drop_column('natural_uf')
        batch_op.drop_column('nacionalidade')
        batch_op.drop_column('orgao_rg')

    # Remover as tabelas novas
    op.drop_table('responsavel_aluno')
    op.drop_table('perfil_socioeconomico')
    op.drop_table('perfil_diversidade')
    op.drop_table('endereco_aluno')


# =============================================================================
# BACKFILL — implementação
# =============================================================================

def _backfill_onda3a() -> None:
    """
    Popula as colunas e tabelas novas a partir dos JSONs legados do Aluno.

    Estratégia:
        - Lê TODOS os alunos em uma passada (1 query).
        - Para cada aluno, faz parse dos 3 JSONs relevantes.
        - Atualiza colunas diretas em `aluno` (1 UPDATE por aluno, só se houver dado).
        - Insere em `endereco_aluno`, `responsavel_aluno`,
          `perfil_socioeconomico`, `perfil_diversidade` (só se houver dado).

    Portabilidade:
        - Escrito em Python, funciona em SQLite e PostgreSQL.
        - Volume esperado: ~1k alunos. Se crescer para >100k, reescrever em
          SQL nativo específico do dialeto.
    """
    import json as _json

    conn = op.get_bind()

    rows = conn.execute(sa.text("""
        SELECT id, unidade_id, identificacao_json, socioeconomico_json, diversidade_json
        FROM aluno
    """)).fetchall()

    def parse(valor) -> dict:
        if not valor:
            return {}
        if isinstance(valor, dict):
            return valor
        try:
            dado = _json.loads(valor) if isinstance(valor, str) else valor
        except (TypeError, ValueError):
            return {}
        return dado if isinstance(dado, dict) else {}

    def s(v):
        """Normaliza string: '' -> None."""
        if v is None:
            return None
        t = str(v).strip()
        return t if t else None

    def i(v):
        """Converte para int, tolerante."""
        if v is None or v == '':
            return None
        try:
            return int(v)
        except (ValueError, TypeError):
            return None

    for row in rows:
        aluno_id = row[0]
        unidade_id = row[1]
        ident = parse(row[2])
        socio = parse(row[3])
        divers = parse(row[4])

        # ---------------------------------------------------------------------
        # 1. Colunas diretas em `aluno`
        # ---------------------------------------------------------------------
        campos_diretos = {
            'orgao_rg': s(ident.get('orgao_rg')),
            'nacionalidade': s(ident.get('nacionalidade')),
            'natural_uf': s(ident.get('natural_uf')),
            'natural_cidade': s(ident.get('natural_cidade')),
            'nome_mae': s(ident.get('nome_mae')),
            'cpf_mae': s(ident.get('cpf_mae')),
            'nome_pai': s(ident.get('nome_pai')),
            'cpf_pai': s(ident.get('cpf_pai')),
            'vai_acompanhado_aulas': bool(ident.get('vai_acompanhado_aulas', False)),
            'acompanhante_aulas': s(ident.get('acompanhante_aulas')),
        }

        # Só atualiza se houver algum campo com dado real
        tem_dado = any(v not in (None, False) for v in campos_diretos.values())
        if tem_dado:
            sets = ", ".join(f"{k} = :{k}" for k in campos_diretos)
            params = {**campos_diretos, 'aluno_id': aluno_id}
            conn.execute(sa.text(f"UPDATE aluno SET {sets} WHERE id = :aluno_id"), params)

        # ---------------------------------------------------------------------
        # 2. Endereço (1:1)
        # ---------------------------------------------------------------------
        end = ident.get('endereco') or {}
        if isinstance(end, dict) and any(v not in (None, '', False) for v in end.values()):
            conn.execute(sa.text("""
                INSERT INTO endereco_aluno
                    (aluno_id, unidade_id, cep, rua, numero, bairro, cidade,
                     uf, zona, possui_acesso_internet)
                VALUES
                    (:aluno_id, :unidade_id, :cep, :rua, :numero, :bairro,
                     :cidade, :uf, :zona, :internet)
            """), {
                'aluno_id': aluno_id,
                'unidade_id': unidade_id,
                'cep': s(end.get('cep')),
                'rua': s(end.get('rua')),
                'numero': s(end.get('numero')),
                'bairro': s(end.get('bairro')),
                'cidade': s(end.get('cidade')),
                'uf': s(end.get('uf')),
                'zona': s(end.get('zona')),
                'internet': bool(end.get('possui_acesso_internet', True)),
            })

        # ---------------------------------------------------------------------
        # 3. Responsável (1:N — cria 1 linha por aluno com dados)
        # ---------------------------------------------------------------------
        resp_tipo = s(ident.get('responsavel_tipo'))
        resp_nome = s(ident.get('responsavel_nome'))
        resp_cpf = s(ident.get('responsavel_cpf'))
        resp_tel = s(ident.get('telefone_resp'))
        if any([resp_tipo, resp_nome, resp_cpf, resp_tel]):
            conn.execute(sa.text("""
                INSERT INTO responsavel_aluno
                    (aluno_id, unidade_id, tipo, nome, cpf, telefone)
                VALUES
                    (:aluno_id, :unidade_id, :tipo, :nome, :cpf, :telefone)
            """), {
                'aluno_id': aluno_id,
                'unidade_id': unidade_id,
                'tipo': resp_tipo,
                'nome': resp_nome,
                'cpf': resp_cpf,
                'telefone': resp_tel,
            })

        # ---------------------------------------------------------------------
        # 4. Perfil socioeconômico (1:1)
        # ---------------------------------------------------------------------
        if isinstance(socio, dict) and any(v not in (None, '', False) for v in socio.values()):
            conn.execute(sa.text("""
                INSERT INTO perfil_socioeconomico
                    (aluno_id, unidade_id, renda_familiar, residente_maior_renda,
                     pessoas_residencia, ocupacao, beneficio_social_status,
                     beneficio_social_nome, meio_transporte, vulnerabilidade_social)
                VALUES
                    (:aluno_id, :unidade_id, :renda, :residente, :pessoas,
                     :ocupacao, :benef_status, :benef_nome, :transporte, :vulnerab)
            """), {
                'aluno_id': aluno_id,
                'unidade_id': unidade_id,
                'renda': s(socio.get('renda_familiar')),
                'residente': s(socio.get('residente_maior_renda')),
                'pessoas': i(socio.get('pessoas_residencia')),
                'ocupacao': s(socio.get('ocupacao')),
                'benef_status': s(socio.get('beneficio_social_status')),
                'benef_nome': s(socio.get('beneficio_social_nome')),
                'transporte': s(socio.get('meio_transporte')),
                'vulnerab': bool(socio.get('vulnerabilidade_social', False)),
            })

        # ---------------------------------------------------------------------
        # 5. Perfil diversidade (1:1)
        # ---------------------------------------------------------------------
        if isinstance(divers, dict) and any(v not in (None, '', False) for v in divers.values()):
            conn.execute(sa.text("""
                INSERT INTO perfil_diversidade
                    (aluno_id, unidade_id, genero, raca_cor, saude_laudo,
                     saude_medicacao, saude_medicamento_nome, saude_observacoes,
                     informacoes_para_professor, autorizacao_imagem)
                VALUES
                    (:aluno_id, :unidade_id, :genero, :raca, :laudo, :medicacao,
                     :medicamento, :obs, :info_prof, :autz_img)
            """), {
                'aluno_id': aluno_id,
                'unidade_id': unidade_id,
                'genero': s(divers.get('genero')),
                'raca': s(divers.get('raca_cor')),
                'laudo': bool(divers.get('saude_laudo', False)),
                'medicacao': s(divers.get('saude_medicacao')),
                'medicamento': s(divers.get('saude_medicamento_nome')),
                'obs': s(divers.get('saude_observacoes')),
                'info_prof': s(divers.get('informacoes_para_professor')),
                'autz_img': bool(divers.get('autorizacao_imagem', False)),
            })
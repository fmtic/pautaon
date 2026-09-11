"""Importador de alunos via planilha Excel.

Regras de negócio implementadas neste fluxo:
- a coluna de unidade é obrigatória em todas as linhas com dados;
- a unidade informada precisa existir no cadastro de unidades do sistema;
- valores longos são truncados para respeitar o schema do banco;
- linhas sem nome são ignoradas para evitar cadastros incompletos.
"""

import sys
from pathlib import Path
from typing import Any

import pandas as pd
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / '.env')

sys.path.append(str(ROOT))

from app import create_app
from app.database import db
from app.models import Aluno, Unidade


def find_unidade_mgb() -> Unidade | None:
    return db.session.query(Unidade).filter(Unidade.nome.ilike('%MGB%')).first()


def find_unidade_por_nome(nome: str | None) -> Unidade | None:
    if not nome:
        return None
    return db.session.query(Unidade).filter(Unidade.nome.ilike(nome.strip())).first()


def normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, str):
        value = value.strip()
        if not value:
            return None
        return value.replace('\u00a0', ' ').strip()
    return value


def safe_date(value: Any):
    if value is None:
        return None
    if isinstance(value, pd.Timestamp):
        return value.to_pydatetime().date()
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        try:
            return pd.to_datetime(text, dayfirst=True).date()
        except Exception:
            return None
    if hasattr(value, 'to_pydatetime'):
        try:
            return value.to_pydatetime().date()
        except Exception:
            return None
    return value


def get_value(row: pd.Series, *candidates: str) -> Any:
    for candidate in candidates:
        if candidate in row.index:
            return row[candidate]
    normalized_map = {}
    for col in row.index:
        if col is None:
            continue
        normalized_map[str(col).strip().lower()] = col
    for candidate in candidates:
        key = str(candidate).strip().lower()
        if key in normalized_map:
            return row[normalized_map[key]]
    return None


def import_from_excel(path: str) -> int:
    """Importa alunos a partir de uma planilha Excel.

    A função valida a presença da unidade antes de gravar qualquer registro e garante
    que a importação seja cancelada quando houver dados incompletos, preservando a
    integridade do cadastro.
    """
    app = create_app()
    with app.app_context():
        unidade_default = find_unidade_mgb()
        if not unidade_default:
            raise RuntimeError('Unidade MGB não encontrada no banco')

        df = pd.read_excel(path)
        if df.empty:
            return 0

        # Validação preventiva antes da persistência: qualquer linha sem unidade
        # deve impedir a importação para evitar cadastro incorreto em uma unidade errada.
        # Essa regra é crítica para manter a consistência do cadastro por unidade.
        missing_unit_rows = []
        for idx, row in df.iterrows():
            unidade_value = normalize_value(get_value(row, 'unidade', 'Unidade', 'UNIDADE'))
            if not unidade_value:
                missing_unit_rows.append(idx + 2)

        if missing_unit_rows:
            raise ValueError(
                'Não há unidade informada na planilha nas linhas: '
                + ', '.join(str(x) for x in missing_unit_rows)
            )

        rows_imported = 0
        for _, row in df.iloc[1:].iterrows():
            nome = normalize_value(get_value(row, 'Nome', 'nome', 'NOME'))
            if not nome:
                continue

            data_nascimento = safe_date(
                get_value(row, 'Data de Nascimento', 'Data de Nascimento Preencher: XX/XX/XXXX', 'data_nascimento', 'Data Nascimento')
            )
            cpf = normalize_value(get_value(row, 'CPF do Aluno', 'cpf', 'CPF'))
            if isinstance(cpf, str):
                cpf = cpf[:20]

            whatsapp = normalize_value(get_value(row, 'Telefone  Celular do Responsável', 'whatsapp', 'WhatsApp', 'WhatsApp do Responsável'))
            if isinstance(whatsapp, str) and len(whatsapp) > 30:
                whatsapp = whatsapp[:30]

            email = normalize_value(get_value(row, 'E-mail', 'email', 'EMAIL'))
            if isinstance(email, str) and len(email) > 120:
                email = email[:120]

            nivel = normalize_value(get_value(row, 'Nivel', 'Nível', 'nivel', 'NIVEL'))
            if isinstance(nivel, str) and len(nivel) > 20:
                nivel = nivel[:20]

            # A unidade informada precisa existir no banco e ser resolvida para um ID
            # antes de persistir o aluno, preservando a relação correta entre aluno e unidade.
            # Se a unidade não existir, a importação deve ser abortada para não criar dados órfãos.
            unidade_value = normalize_value(get_value(row, 'unidade', 'Unidade', 'UNIDADE'))
            unidade_aluno = find_unidade_por_nome(unidade_value)
            if not unidade_aluno:
                raise ValueError(
                    f'Unidade não encontrada no banco para o valor "{unidade_value}" na planilha'
                )

            nome_final = str(nome)[:100]
            nome_social = normalize_value(get_value(row, 'Nome Social', 'nome_social', 'NOME SOCIAL'))
            if isinstance(nome_social, str):
                nome_social = nome_social[:100]

            aluno = Aluno(
                nome=nome_final,
                nome_social=nome_social,
                ativo=True,
                data_nascimento=data_nascimento,
                cpf=cpf,
                rg=normalize_value(get_value(row, 'RG', 'rg', 'RG do Aluno')),
                whatsapp=whatsapp,
                email=email,
                nivel=nivel,
                unidade_id=unidade_aluno.id,
            )
            db.session.add(aluno)
            rows_imported += 1

        # A confirmação final da transação garante que todos os registros válidos
        # sejam gravados de forma consistente e atômica na base.
        db.session.commit()
        return rows_imported


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print('Uso: python scripts/importar_matriculas.py <arquivo.xlsx>')
        sys.exit(1)
    path = sys.argv[1]
    print(f'Importando {path}')
    try:
        count = import_from_excel(path)
        print(f'Foram importados {count} alunos')
    except Exception as exc:
        print(f'ERRO: {exc}')
        sys.exit(2)

"""Constantes e helpers compartilhados entre as rotas de relatórios."""

from sqlalchemy import cast, or_
from sqlalchemy.dialects.postgresql import JSONB

from app.models import Aluno, Turma

# Perfis com acesso aos relatórios administrativos/pedagógicos.
ROLES_RELATORIOS = ["admin", "pedagogico", "secretaria", "gerencia"]


def ler_filtros_alunos(args):
    """Lê, a partir da querystring, os filtros usados na listagem e na
    exportação de alunos (mesmo conjunto de parâmetros nos dois casos)."""
    return {
        "periodo_letivo_id": args.get("periodo_letivo_id", type=int),
        "sexo": args.get("sexo"),
        "etnia": args.get("etnia"),
        "cidade": args.get("cidade"),
        "bairro": args.get("bairro"),
        "beneficio_social": args.get("beneficio_social"),
        "vulnerabilidade_social": args.get("vulnerabilidade_social"),
        "zona": args.get("zona"),
        "acesso_internet": args.get("acesso_internet"),
    }


def aplicar_filtros_alunos(query, filtros):
    """Aplica, sobre uma query de Aluno, os filtros de relatório compartilhados
    entre `relatorio_alunos` (listagem) e `exportar_relatorio_alunos` (Excel).

    Centralizado aqui para que os dois pontos de uso nunca fiquem
    dessincronizados quanto às regras de filtro — antes cada rota reimplementava
    a mesma lógica separadamente.
    """
    periodo_id = filtros.get("periodo_letivo_id")
    if periodo_id:
        query = query.join(Aluno.turmas).filter(Turma.periodo_letivo_id == periodo_id)

    if filtros.get("sexo"):
        query = query.filter(Aluno.diversidade_json['genero'].astext == filtros["sexo"])

    if filtros.get("etnia"):
        query = query.filter(Aluno.diversidade_json['raca_cor'].astext == filtros["etnia"])

    if filtros.get("cidade"):
        query = query.filter(
            Aluno.identificacao_json['endereco']['cidade'].astext.ilike(f"%{filtros['cidade']}%")
        )

    if filtros.get("bairro"):
        query = query.filter(
            Aluno.identificacao_json['endereco']['bairro'].astext.ilike(f"%{filtros['bairro']}%")
        )

    beneficio_social = filtros.get("beneficio_social")
    if beneficio_social == "1":
        query = query.filter(Aluno.socioeconomico_json['beneficio_social_status'].astext == "Sim")
    elif beneficio_social == "0":
        query = query.filter(Aluno.socioeconomico_json['beneficio_social_status'].astext != "Sim")

    vulnerabilidade_social = filtros.get("vulnerabilidade_social")
    vulnerabilidade = cast(Aluno._socioeconomico_json, JSONB)["vulnerabilidade_social"].astext
    if vulnerabilidade_social == "1":
        query = query.filter(vulnerabilidade == "true")
    elif vulnerabilidade_social == "0":
        query = query.filter(or_(vulnerabilidade == "false", vulnerabilidade.is_(None)))

    zona = filtros.get("zona")
    zona_residencia = cast(Aluno._identificacao_json, JSONB)["endereco"]["zona"].astext
    if zona:
        query = query.filter(zona_residencia == zona)

    acesso_internet = filtros.get("acesso_internet")
    possui_internet = cast(Aluno._identificacao_json, JSONB)["possui_acesso_internet"].astext
    if acesso_internet == "1":
        query = query.filter(or_(possui_internet == "true", possui_internet.is_(None)))
    elif acesso_internet == "0":
        query = query.filter(possui_internet == "false")

    return query

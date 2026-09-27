"""Constantes e helpers compartilhados entre as rotas de relatórios.

ONDA 3B
    Os filtros passam a usar as tabelas estruturadas (PerfilDiversidade,
    PerfilSocioeconomico, EnderecoAluno) via JOIN, em vez de JSON path
    em `Aluno.*_json`.

    JOINs são LEFT (outerjoin) para não excluir alunos que ainda não
    foram migrados. Quando o filtro é aplicado, esses alunos caem fora
    naturalmente — é o comportamento esperado.
"""

from sqlalchemy import or_

from app.models import (
    Aluno,
    EnderecoAluno,
    PerfilDiversidade,
    PerfilSocioeconomico,
    Turma,
)

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


def _ensure_join(query, model, joined_models):
    """
    Faz outerjoin uma única vez por modelo.

    Evita duplicação quando múltiplos filtros usam a mesma tabela
    (ex.: sexo e etnia ambos em PerfilDiversidade).
    """
    if model not in joined_models:
        query = query.outerjoin(model)
        joined_models.add(model)
    return query


def aplicar_filtros_alunos(query, filtros):
    """
    Aplica, sobre uma query de Aluno, os filtros de relatório compartilhados
    entre `relatorio_alunos` (listagem) e `exportar_relatorio_alunos` (Excel).

    ONDA 3B: usa as tabelas estruturadas em vez de JSON path. Alunos ainda
    não migrados ficam fora quando um filtro específico é aplicado — o que
    é o comportamento correto (eles não têm o dado).
    """
    joined_models = set()

    # -------------------------------------------------------------------------
    # Período letivo (não mudou — usa relação N:N existente)
    # -------------------------------------------------------------------------
    periodo_id = filtros.get("periodo_letivo_id")
    if periodo_id:
        query = query.join(Aluno.turmas).filter(Turma.periodo_letivo_id == periodo_id)

    # -------------------------------------------------------------------------
    # Diversidade (gênero, raça/cor) — PerfilDiversidade
    # -------------------------------------------------------------------------
    if filtros.get("sexo"):
        query = _ensure_join(query, PerfilDiversidade, joined_models)
        query = query.filter(PerfilDiversidade.genero == filtros["sexo"])

    if filtros.get("etnia"):
        query = _ensure_join(query, PerfilDiversidade, joined_models)
        query = query.filter(PerfilDiversidade.raca_cor == filtros["etnia"])

    # -------------------------------------------------------------------------
    # Endereço (cidade, bairro, zona, internet) — EnderecoAluno
    # -------------------------------------------------------------------------
    if filtros.get("cidade"):
        query = _ensure_join(query, EnderecoAluno, joined_models)
        query = query.filter(
            EnderecoAluno.cidade.ilike(f"%{filtros['cidade']}%")
        )

    if filtros.get("bairro"):
        query = _ensure_join(query, EnderecoAluno, joined_models)
        query = query.filter(
            EnderecoAluno.bairro.ilike(f"%{filtros['bairro']}%")
        )

    zona = filtros.get("zona")
    if zona:
        query = _ensure_join(query, EnderecoAluno, joined_models)
        query = query.filter(EnderecoAluno.zona == zona)

    acesso_internet = filtros.get("acesso_internet")
    if acesso_internet == "1":
        query = _ensure_join(query, EnderecoAluno, joined_models)
        # Inclui sem-endereço como "tem internet" (default otimista, mesma
        # semântica do filtro antigo).
        query = query.filter(
            or_(
                EnderecoAluno.id.is_(None),
                EnderecoAluno.possui_acesso_internet.is_(True),
            )
        )
    elif acesso_internet == "0":
        query = _ensure_join(query, EnderecoAluno, joined_models)
        query = query.filter(EnderecoAluno.possui_acesso_internet.is_(False))

    # -------------------------------------------------------------------------
    # Socioeconômico (benefício social, vulnerabilidade) — PerfilSocioeconomico
    # -------------------------------------------------------------------------
    beneficio_social = filtros.get("beneficio_social")
    if beneficio_social == "1":
        query = _ensure_join(query, PerfilSocioeconomico, joined_models)
        query = query.filter(
            PerfilSocioeconomico.beneficio_social_status == "Sim"
        )
    elif beneficio_social == "0":
        query = _ensure_join(query, PerfilSocioeconomico, joined_models)
        # Inclui alunos sem perfil (não-migrados) como "sem benefício".
        query = query.filter(
            or_(
                PerfilSocioeconomico.id.is_(None),
                PerfilSocioeconomico.beneficio_social_status != "Sim",
                PerfilSocioeconomico.beneficio_social_status.is_(None),
            )
        )

    vulnerabilidade_social = filtros.get("vulnerabilidade_social")
    if vulnerabilidade_social == "1":
        query = _ensure_join(query, PerfilSocioeconomico, joined_models)
        query = query.filter(
            PerfilSocioeconomico.vulnerabilidade_social.is_(True)
        )
    elif vulnerabilidade_social == "0":
        query = _ensure_join(query, PerfilSocioeconomico, joined_models)
        query = query.filter(
            or_(
                PerfilSocioeconomico.id.is_(None),
                PerfilSocioeconomico.vulnerabilidade_social.is_(False),
            )
        )

    return query
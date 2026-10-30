"""Engajamento da turma — valores/posturas do esportista mais atribuídos (V3b).

Bloco do Painel Pedagógico do professor, logo abaixo do gráfico "Evolução de
Assiduidade Aula a Aula". Mostra os ``limite`` valores mais atribuídos na
**oferta** escolhida no filtro, com contagem e percentual sobre o total de
atribuições da oferta.

Regras (fechadas na V3b):
    - conta linhas de ``Frequencia`` da oferta com ``valor_esportista_id``
      preenchido, em **todas** as datas da oferta;
    - **empate** desfaz-se pela ordem alfabética do nome;
    - valor **inativo** já lançado continua contando (o histórico não é
      escondido — mesma regra do catálogo em §7 do MER);
    - menos de ``limite`` valores: devolve os que houver; nenhum: lista vazia;
    - o percentual é sobre o **total da oferta**, não sobre o top N;
    - **legado D2**: linhas com ``turma_curso_id`` NULL só entram quando a
      oferta é a ÚNICA ativa da turma (``ofertas_unicas_ativas`` em
      ``services/frequencia_oferta.py``) — nenhuma regra nova aqui;
    - **uma** consulta agregada (GROUP BY valor), sem N+1 e sem dado por aluno.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_

from app.database import db
from app.models import Frequencia, ValorEsportista
from app.services.frequencia_oferta import ofertas_unicas_ativas

LIMITE_PADRAO = 3


def _condicoes_do_escopo(turma_id: int, turma_curso_id: int | None) -> list:
    """Filtros de escopo da oferta, com a regra D2 do legado já aplicada."""
    if turma_curso_id is None:
        # Turma sem oferta ativa (ramo legado): as linhas são as da turma.
        return [Frequencia.turma_id == turma_id]

    if turma_curso_id in ofertas_unicas_ativas([turma_curso_id]):
        # D2: com uma única oferta ativa, as linhas legado (NULL) são dela.
        return [
            or_(
                Frequencia.turma_curso_id == turma_curso_id,
                and_(
                    Frequencia.turma_curso_id.is_(None),
                    Frequencia.turma_id == turma_id,
                ),
            )
        ]
    return [Frequencia.turma_curso_id == turma_curso_id]


def valores_mais_atribuidos(
    turma_id: int | None,
    turma_curso_id: int | None,
    limite: int = LIMITE_PADRAO,
) -> dict:
    """Top ``limite`` valores da oferta e o total de atribuições.

    Devolve ``{"itens": [{"nome", "quantidade", "percentual"}], "total": int}``
    — ``percentual`` com 1 casa decimal sobre ``total`` (todas as atribuições da
    oferta, não só as do top). Nunca devolve dado por aluno.
    """
    if turma_id is None or limite <= 0:
        return {"itens": [], "total": 0}

    condicoes = _condicoes_do_escopo(turma_id, turma_curso_id)

    # Única consulta agregada: GROUP BY valor (o JOIN interno já garante
    # `valor_esportista_id` preenchido).
    linhas = (
        db.session.query(
            ValorEsportista.nome,
            func.count(Frequencia.id),
        )
        .select_from(Frequencia)
        .join(
            ValorEsportista,
            ValorEsportista.id == Frequencia.valor_esportista_id,
        )
        .filter(Frequencia.valor_esportista_id.isnot(None), *condicoes)
        .group_by(ValorEsportista.id, ValorEsportista.nome)
        .all()
    )

    total = sum(quantidade for _nome, quantidade in linhas)
    if not total:
        return {"itens": [], "total": 0}

    # Empate: ordem alfabética do nome (casefold é determinístico entre bancos;
    # o nome é único por unidade a menos de caixa).
    ordenadas = sorted(
        linhas,
        key=lambda linha: (
            -linha[1], (linha[0] or "").casefold(), linha[0] or ""
        ),
    )

    itens = [
        {
            "nome": nome,
            "quantidade": quantidade,
            "percentual": round(quantidade * 100.0 / total, 1),
        }
        for nome, quantidade in ordenadas[:limite]
    ]
    return {"itens": itens, "total": total}

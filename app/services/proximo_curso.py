"""AJ22 — Regra de "próximo curso + nível" no fechamento do conselho.

Fonte única da regra (AJ22-C):

- O próximo curso é um `Curso` JÁ CADASTRADO da unidade da turma
  (`curso.ativo=True`), a mesma fonte/escopo dos selects de curso de
  turma/oferta. Não existe catálogo paralelo: `opcao_proxima_turma` é
  LEGADO (somente leitura histórica, sem novas escritas).
- O nível pertence a um CURSO (`nivel.curso_id`): cada curso tem sua
  nomenclatura de níveis. Nível sem curso (NULL, legado) nunca entra.
- O nível é elegível quando: existe, está ativo (salvo a exceção de
  "inalterado" tratada no chamador), pertence ao curso escolhido e à
  unidade da turma (ou é global `unidade_id IS NULL`, mesmo critério dos
  demais leitores de nível).
"""

from __future__ import annotations

from sqlalchemy import or_

from app.models import Curso, Nivel, OpcaoProximaTurma


def cursos_da_unidade(unidade_id: int, apenas_ativos: bool = True):
    """Cursos da unidade da turma — mesma fonte/escopo dos selects de curso
    de turma/oferta (`registros/turmas.py`)."""
    query = Curso.query.filter(Curso.unidade_id == unidade_id)
    if apenas_ativos:
        query = query.filter(Curso.ativo == True)  # noqa: E712
    return query.order_by(Curso.nome).all()


def _niveis_da_unidade(unidade_id: int, apenas_ativos: bool = False):
    """Níveis elegíveis à unidade da turma: os da unidade + os globais
    (`unidade_id IS NULL`), mesmo critério de `registros/turmas.py`."""
    query = Nivel.query.filter(
        or_(Nivel.unidade_id == unidade_id, Nivel.unidade_id.is_(None))
    )
    if apenas_ativos:
        query = query.filter(Nivel.ativo == True)  # noqa: E712
    return query.all()


def _serializar_nivel(nivel: Nivel) -> dict:
    return {
        "id": nivel.id,
        "nome": nivel.nome,
        "ativo": bool(nivel.ativo),
    }


def niveis_por_curso(curso_id: int, unidade_id: int) -> list[dict]:
    """Níveis de UM curso na unidade da turma (ou globais).

    Inclui ativos E inativos (o inativo já gravado continua aparecendo na
    edição com etiqueta); níveis sem curso NÃO entram.
    Cada item: ``{'id', 'nome', 'ativo'}``.
    """
    if not curso_id:
        return []
    itens = [
        _serializar_nivel(nivel)
        for nivel in _niveis_da_unidade(unidade_id)
        if nivel.curso_id == curso_id
    ]
    itens.sort(key=lambda item: item["nome"].lower())
    return itens


def mapa_niveis_por_curso(cursos, unidade_id: int) -> dict:
    """Mapa ``{curso_id: [nivel, ...]}`` em LOTE (1 consulta).

    Inclui todos os cursos pedidos (mesmo sem níveis, com lista vazia),
    ativos e inativos, para embutir no fechamento sem N+1.
    """
    ids = {
        getattr(curso, "id", curso)
        for curso in cursos or []
        if getattr(curso, "id", curso)
    }
    mapa = {curso_id: [] for curso_id in ids}
    if not ids:
        return mapa
    for nivel in _niveis_da_unidade(unidade_id):
        if nivel.curso_id in mapa:
            mapa[nivel.curso_id].append(_serializar_nivel(nivel))
    for itens in mapa.values():
        itens.sort(key=lambda item: item["nome"].lower())
    return mapa


def curso_tem_niveis(curso_id: int, unidade_id: int) -> bool:
    """Existe ao menos um nível ATIVO da unidade da turma no curso?"""
    if not curso_id:
        return False
    return any(
        nivel.curso_id == curso_id
        for nivel in _niveis_da_unidade(unidade_id, apenas_ativos=True)
    )


def nivel_elegivel(
    nivel_id: int,
    *,
    curso_id: int,
    unidade_id: int,
) -> Nivel | None:
    """Devolve o `Nivel` se ele pode ser escolhido para o curso, senão None.

    Elegível = existe, ativo, do curso escolhido e unidade da turma (ou
    global). Nível sem curso (NULL) nunca é elegível.
    """
    nivel = Nivel.query.get(nivel_id)
    if nivel is None or not nivel.ativo:
        return None
    return nivel if nivel_compativel(nivel, curso_id, unidade_id) else None


def nivel_compativel(
    nivel: Nivel, curso_id: int, unidade_id: int
) -> bool:
    """Mesma regra de elegibilidade sem exigir `ativo` (a exceção de
    "inalterado" do AJ22 é decidida pelo chamador, que já checou o ativo)."""
    if not curso_id or nivel.curso_id != curso_id:
        return False
    if nivel.unidade_id is not None and nivel.unidade_id != unidade_id:
        return False
    return True


def curso_da_escolha(proximo_curso_id) -> Curso | None:
    """Curso por id; ids inválidos/None viram None."""
    if proximo_curso_id in (None, "", "None"):
        return None
    try:
        return Curso.query.get(int(proximo_curso_id))
    except (TypeError, ValueError):
        return None


def destinos_por_conselho(conselhos) -> dict:
    """Resolve, EM LOTE, o destino exibido por conselho.

    Devolve ``{conselho_id: {'curso', 'nivel', 'legado', 'texto',
    'curso_inativo'}}``. Regras do AJ22-B/C:

    - `proximo_curso_id` presente → mostra `curso.nome` (e o nível, se
      houver). Curso hoje inativo continua sendo exibido (histórico).
    - `proximo_curso_id` NULL e `proxima_turma_id` presente → fallback
      LEGADO com o nome da opção, sem nível.
    - Nada gravado → texto vazio (os leitores exibem "—").

    1 consulta por tabela de destino, independente do número de linhas.
    """
    conselhos = list(conselhos)
    cursos_ids = {
        c.proximo_curso_id for c in conselhos if c.proximo_curso_id
    }
    niveis_ids = {
        c.proximo_nivel_id for c in conselhos if c.proximo_nivel_id
    }
    legados_ids = {
        c.proxima_turma_id
        for c in conselhos
        if not c.proximo_curso_id and c.proxima_turma_id
    }

    cursos = (
        {
            c.id: c
            for c in Curso.query.filter(Curso.id.in_(cursos_ids)).all()
        }
        if cursos_ids
        else {}
    )
    niveis = (
        {
            n.id: n
            for n in Nivel.query.filter(Nivel.id.in_(niveis_ids)).all()
        }
        if niveis_ids
        else {}
    )
    legados = (
        {
            o.id: o
            for o in OpcaoProximaTurma.query.filter(
                OpcaoProximaTurma.id.in_(legados_ids)
            ).all()
        }
        if legados_ids
        else {}
    )

    destinos = {}
    for cons in conselhos:
        curso = cursos.get(cons.proximo_curso_id)
        nivel = niveis.get(cons.proximo_nivel_id)
        legado = None
        if cons.proximo_curso_id:
            partes = []
            if curso is not None:
                partes.append(curso.nome)
            if nivel is not None:
                partes.append(nivel.nome)
            texto = " · ".join(partes)
        else:
            legado = legados.get(cons.proxima_turma_id)
            texto = legado.nome if legado is not None else ""
        destinos[cons.id] = {
            "curso": curso,
            "nivel": nivel,
            "legado": legado,
            "texto": texto,
            "curso_inativo": bool(curso is not None and not curso.ativo),
        }
    return destinos

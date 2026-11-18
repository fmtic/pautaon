"""AJ22 — Regra de "próximo curso + nível" no fechamento do conselho.

Fonte única da regra (E1–E4 do AJ22-B):

- O próximo curso é um `Curso` JÁ CADASTRADO da unidade da turma
  (`curso.ativo=True`), a mesma fonte/escopo dos selects de curso de
  turma/oferta. Não existe mais catálogo paralelo: `opcao_proxima_turma`
  é LEGADO (somente leitura histórica, sem novas escritas).
- `PROGRAMAS_CURSO`: lista central dos programas de curso, gravada em
  `curso.programa` (o campo de `turma_curso.programa` segue intocado e
  sem vínculo com esta coluna).
- "Programa com níveis" é DERIVADO (D4): existe ao menos um nível ATIVO
  da unidade da turma com aquele programa. Nível sem programa (NULL,
  legado) nunca entra (D2).
- O nível é elegível quando: existe, está ativo (salvo a exceção de
  "inalterado" tratada no chamador), pertence à unidade da turma (ou é
  global `unidade_id IS NULL`, mesmo critério dos demais leitores de
  nível) e tem `programa` igual ao do curso escolhido.
"""

from __future__ import annotations

from app.models import Curso, Nivel, OpcaoProximaTurma

# Lista ÚNICA de programas de curso (AJ22). Mantida aqui para os selects
# de curso e nível; `_PROGRAMAS_OFERTA` (registros/turmas.py) não foi
# refatorado.
PROGRAMAS_CURSO = ("Profissionalizante", "Esporte", "Meio Ambiente", "Outros")


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
    from sqlalchemy import or_

    query = Nivel.query.filter(
        or_(Nivel.unidade_id == unidade_id, Nivel.unidade_id.is_(None))
    )
    if apenas_ativos:
        query = query.filter(Nivel.ativo == True)  # noqa: E712
    return query.all()


def niveis_por_programa(unidade_id: int) -> dict:
    """Mapa ``{programa: [nivel, ...]}`` para embutir no fechamento.

    Inclui ativos E inativos (o inativo já gravado continua aparecendo na
    edição com etiqueta); níveis sem programa (NULL) NÃO entram (D2).
    Cada item: ``{'id', 'nome', 'ativo'}``.
    """
    mapa: dict[str, list] = {}
    for nivel in _niveis_da_unidade(unidade_id):
        programa = (nivel.programa or "").strip()
        if not programa:
            continue
        mapa.setdefault(programa, []).append(
            {"id": nivel.id, "nome": nivel.nome, "ativo": bool(nivel.ativo)}
        )
    for itens in mapa.values():
        itens.sort(key=lambda item: item["nome"].lower())
    return mapa


def programa_tem_niveis(programa: str | None, unidade_id: int) -> bool:
    """D4: "programa com níveis" = existe nível ATIVO da unidade da turma
    com aquele programa."""
    programa = (programa or "").strip()
    if not programa:
        return False
    return any(
        (n.programa or "").strip() == programa and n.ativo
        for n in _niveis_da_unidade(unidade_id, apenas_ativos=True)
    )


def nivel_elegivel(
    nivel_id: int,
    *,
    programa_curso: str | None,
    unidade_id: int,
) -> Nivel | None:
    """Devolve o `Nivel` se ele pode ser escolhido para o curso, senão None.

    Elegível = existe, ativo, programa igual ao do curso e unidade da
    turma (ou global). Nível sem programa (NULL) nunca é elegível (D2).
    """
    nivel = Nivel.query.get(nivel_id)
    if nivel is None or not nivel.ativo:
        return None
    return nivel if nivel_compativel(nivel, programa_curso, unidade_id) else None


def nivel_compativel(
    nivel: Nivel, programa_curso: str | None, unidade_id: int
) -> bool:
    """Mesma regra de elegibilidade sem exigir `ativo` (a exceção de
    "inalterado" do AJ22 é decidida pelo chamador, que já checou o ativo)."""
    programa = (programa_curso or "").strip()
    if not programa:
        return False
    if (nivel.programa or "").strip() != programa:
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


def programa_do_curso(curso: Curso | None) -> str:
    """Programa normalizado do curso ('' quando não há)."""
    return (getattr(curso, "programa", None) or "").strip()


def destinos_por_conselho(conselhos) -> dict:
    """Resolve, EM LOTE, o destino exibido por conselho.

    Devolve ``{conselho_id: {'curso', 'nivel', 'legado', 'texto',
    'curso_inativo'}}``. Regras do AJ22-B:

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

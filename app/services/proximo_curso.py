"""AJ22 — Regra de "próximo curso + nível" no fechamento do conselho.

Fonte única da regra (D1–D8 do AJ22):

- `PROGRAMAS_CURSO`: lista central dos programas de curso (texto livre na
  oferta `turma_curso.programa`). Os novos selects (opção de próximo
  curso e nível) usam ESTA lista; `_PROGRAMAS_OFERTA` de
  `registros/turmas.py` segue intacto (não foi refatorado).
- "Programa com níveis" é DERIVADO (D4): existe ao menos um nível ATIVO
  da unidade da turma com aquele programa. Nível sem programa (NULL,
  legado) nunca entra (D2).
- O nível é elegível quando: existe, está ativo (salvo a exceção de
  "inalterado" tratada no chamador), pertence à unidade da turma (ou é
  global `unidade_id IS NULL`, mesmo critério dos demais leitores de
  nível) e tem `programa` igual ao da opção escolhida.
"""

from __future__ import annotations

from app.models import Nivel, OpcaoProximaTurma

# Lista ÚNICA de programas de curso (AJ22). Mantida aqui para os novos
# selects; `_PROGRAMAS_OFERTA` (registros/turmas.py) não foi refatorado.
PROGRAMAS_CURSO = ("Profissionalizante", "Esporte", "Meio Ambiente", "Outros")


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
    programa_opcao: str | None,
    unidade_id: int,
) -> Nivel | None:
    """Devolve o `Nivel` se ele pode ser escolhido para a opção, senão None.

    Elegível = existe, ativo, programa igual ao da opção e unidade da
    turma (ou global). Nível sem programa (NULL) nunca é elegível (D2).
    """
    nivel = Nivel.query.get(nivel_id)
    if nivel is None or not nivel.ativo:
        return None
    return nivel if nivel_compativel(nivel, programa_opcao, unidade_id) else None


def nivel_compativel(nivel: Nivel, programa_opcao: str | None, unidade_id: int) -> bool:
    """Mesma regra de elegibilidade sem exigir `ativo` (a exceção de
    "inalterado" do AJ22 é decidida pelo chamador, que já checou o ativo)."""
    programa = (programa_opcao or "").strip()
    if not programa:
        return False
    if (nivel.programa or "").strip() != programa:
        return False
    if nivel.unidade_id is not None and nivel.unidade_id != unidade_id:
        return False
    return True


def opcao_da_escolha(proxima_turma_id) -> OpcaoProximaTurma | None:
    """Opção do catálogo por id; ids inválidos/None viram None."""
    if proxima_turma_id in (None, "", "None"):
        return None
    try:
        return OpcaoProximaTurma.query.get(int(proxima_turma_id))
    except (TypeError, ValueError):
        return None

"""Leitura do conselho de classe POR OFERTA (D5.4).

Regras do desenho (docs/D5_0_desenho.md §2.5/§2.6, D5.4):
    - A unidade de resultado é (oferta, aluno, etapa): toda consulta casa
      `ConselhoClasse.turma_curso_id` com a oferta (`TurmaCurso`).
    - Desde a D5.5 `turma_curso_id` é NOT NULL: linha legada sem oferta não
      existe mais (a resolução manual pré-endurecimento ficou registrada em
      `scripts/verificar_onda4_d5.py`).
    - Nenhum acoplamento com `Turma`: o encerramento do conselho é da OFERTA
      (`TurmaCurso.conselho_concluido`) — a coluna `Turma.conselho_concluido`
      foi REMOVIDA na D5.5, a turma não tem coluna de conclusão e não existe
      ponte de escrita. `Turma.avaliacao_*` são LEGADO (§12.19) e não são
      lidas por este módulo.

As funções são de leitura pura (nada de commit) e servem aos leitores de
histórico, ficha, relatórios e certificado.
"""

from __future__ import annotations

from sqlalchemy import and_, or_

from app.models import ConselhoClasse, TurmaCurso
from app.models.enums import EtapaConselho


def _etapa_valor(etapa) -> str:
    """Normaliza a etapa para o VALOR gravado no banco ('INICIAL', ...)."""
    if isinstance(etapa, EtapaConselho):
        return etapa.value
    return str(etapa)


def rotulo_oferta(oferta: TurmaCurso | None, turma=None) -> str:
    """Rótulo humano da oferta: 'Turma — Curso' (D5.3/D5.4).

    Sem oferta (linha legada/sem vínculo) devolve apenas o nome da turma
    quando disponível, ou '—'.
    """
    if oferta is None:
        return turma.nome if turma is not None else "—"
    nome_turma = (turma or oferta.turma).nome if (turma or oferta.turma) else "—"
    nome_curso = (
        oferta.curso.nome if oferta.curso is not None
        else f"curso #{oferta.curso_id}"
    )
    return f"{nome_turma} — {nome_curso}"


def conselho_do_aluno(aluno_id: int, turma_curso_id: int | None, etapa) -> ConselhoClasse | None:
    """Conselho FINAL/INICIAL/… de UM aluno em UMA oferta.

    `turma_curso_id` NULL (legado) sempre devolve `None` — o registro não é
    exibido nem adotado por leitor algum.
    """
    if aluno_id is None or turma_curso_id is None:
        return None
    return ConselhoClasse.query.filter_by(
        aluno_id=aluno_id,
        turma_curso_id=turma_curso_id,
        etapa=_etapa_valor(etapa),
    ).first()


def conselhos_por_oferta(pares_aluno_oferta, etapas=None) -> dict:
    """Busca conselhos em LOTE por (aluno, oferta) — uma única consulta.

    `pares_aluno_oferta`: iterável de `(aluno_id, turma_curso_id)`; pares com
    aluno ou oferta `None` são ignorados (linhas legadas não são adotadas).

    `etapas`: iterável de etapas para restringir (ex.: `['FINAL']`); `None`
    traz todas.

    Devolve `{(aluno_id, turma_curso_id, etapa): ConselhoClasse}`.
    """
    pares = {
        (int(aluno_id), int(turma_curso_id))
        for aluno_id, turma_curso_id in pares_aluno_oferta
        if aluno_id is not None and turma_curso_id is not None
    }
    if not pares:
        return {}

    condicoes = [
        and_(
            ConselhoClasse.aluno_id == aluno_id,
            ConselhoClasse.turma_curso_id == turma_curso_id,
        )
        for aluno_id, turma_curso_id in pares
    ]
    query = ConselhoClasse.query.filter(or_(*condicoes))
    if etapas is not None:
        valores = [_etapa_valor(e) for e in etapas]
        if not valores:
            return {}
        query = query.filter(ConselhoClasse.etapa.in_(valores))

    saida = {}
    for conselho in query.all():
        if conselho.turma_curso_id is None:
            continue
        chave = (
            conselho.aluno_id,
            conselho.turma_curso_id,
            _etapa_valor(conselho.etapa),
        )
        saida[chave] = conselho
    return saida


def mapa_por_aluno_oferta(conselhos: dict, etapa) -> dict:
    """Filtra o resultado do lote para uma etapa: {(aluno, oferta): conselho}."""
    valor = _etapa_valor(etapa)
    return {
        (aluno_id, oferta_id): conselho
        for (aluno_id, oferta_id, etapa_chave), conselho in conselhos.items()
        if etapa_chave == valor
    }


def ofertas_do_grupo(turma_curso_ids) -> dict[int, TurmaCurso]:
    """Carrega as ofertas (com curso) em uma consulta, por id."""
    from sqlalchemy.orm import joinedload

    ids = [i for i in turma_curso_ids if i is not None]
    if not ids:
        return {}
    linhas = (
        TurmaCurso.query
        .options(joinedload(TurmaCurso.curso), joinedload(TurmaCurso.turma))
        .filter(TurmaCurso.id.in_(set(ids)))
        .all()
    )
    return {oferta.id: oferta for oferta in linhas}

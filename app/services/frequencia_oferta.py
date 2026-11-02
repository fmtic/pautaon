"""
ETAPA D3b.2 — serviço único de frequência por oferta.

Fonte de verdade única para percentual e faixas de frequência, consumida pelo
modelo (`Turma.freq_geral` / `Turma.freq_geral_oferta`), pelo painel pedagógico
(turma, período, ficha 360) e pela tela de lançamento/relatório.

Regras canônicas (decisão do responsável — docs/D3b_0_desenho.md, D3b.2):
    - percentual = presentes / (presentes + faltas), J FORA do denominador,
      arredondado a 1 casa decimal (regra atual, preservada);
    - faixas comparam o valor JÁ ARREDONDADO a 1 casa:
      hi >= LIMIAR_ATENCAO (90), mid >= LIMIAR_CRITICO (75), lo abaixo —
      isso fecha a brecha em que 89,96% ficava fora de todas as faixas;
    - frequência POR OFERTA = só as linhas da oferta; as linhas legadas
      (`turma_curso_id IS NULL`) entram apenas quando a oferta é a ÚNICA
      ativa da turma (regra D2 da pauta);
    - frequência POR TURMA = soma de TODAS as linhas da turma (ofertas +
      legado), exatamente como era feito antes do serviço (os números das
      telas atuais não mudam).

Sem N+1: `agregar_por_oferta` e `agregar_por_turma` fazem UMA consulta na
tabela `frequencia` cada, independentemente da quantidade de ids. A unidade
é filtrada quando o chamador tem escopo de unidade (parâmetro `unidade_id`).

Nota de arquitetura: os limiares vêm de `regras.py` (painel pedagógico) com
import LAZY dentro de função — `app.relatorios.__init__` importa blueprints
que importam `app.services`, e um import top-level criaria ciclo.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

from sqlalchemy import func

from app import db
from app.models import Frequencia, TurmaCurso
from app.models.enums import CONCEITOS_CONTABEIS, CONCEITOS_PRESENCA


# ---------------------------------------------------------------------------
# Regras puras (percentual e faixa)
# ---------------------------------------------------------------------------

def percentual(presentes: int, faltas: int) -> float:
    """Regra única: presentes/(presentes+faltas), J fora, 1 casa decimal."""
    total = presentes + faltas
    return round(presentes / total * 100, 1) if total else 0.0


def faixa(valor: float) -> str:
    """hi/mid/lo sobre o valor JÁ ARREDONDADO a 1 casa (fecha a brecha do 89,96)."""
    # Import local: evita ciclo services → relatorios → services (ver cabeçalho).
    from app.relatorios.painel_pedagogico.regras import (
        LIMIAR_ATENCAO,
        LIMIAR_CRITICO,
    )

    arredondado = round(valor, 1)
    if arredondado >= LIMIAR_ATENCAO:
        return "hi"
    if arredondado >= LIMIAR_CRITICO:
        return "mid"
    return "lo"


# ---------------------------------------------------------------------------
# Estruturas de retorno
# ---------------------------------------------------------------------------

@dataclass
class TurmaFrequencia:
    """Agregado de frequência POR TURMA (todas as linhas, ofertas + legado).

    Mesma estrutura do antigo `painel_pedagogico.frequencia.FrequenciaTurma`:
    `por_aluno` preserva a lista ordenada (data, conceito) inclusive o J
    (consumida pelas séries semanais e sequências de falta do painel).
    """
    por_aluno: dict[int, list[tuple[date, str]]] = field(default_factory=dict)
    por_aluno_pct: dict[int, float] = field(default_factory=dict)
    total: int = 0
    presentes: int = 0
    pct_turma: float = 0.0


@dataclass
class AlunoOfertaFrequencia:
    """Agregado de um aluno em uma oferta (presentes/faltas/percentual)."""
    presentes: int = 0
    faltas: int = 0
    total: int = 0
    pct: float = 0.0

    def __getitem__(self, chave: str):
        """Acesso por chave (dict-like) além do acesso por atributo."""
        return getattr(self, chave)


@dataclass
class OfertaFrequencia:
    """Agregado de frequência POR OFERTA (regra D2 do legado aplicada)."""
    turma_id: int | None = None
    presentes: int = 0
    faltas: int = 0
    total: int = 0
    pct: float = 0.0
    por_aluno: dict[int, AlunoOfertaFrequencia] = field(default_factory=dict)

    @property
    def pct_turma(self) -> float:
        """Alias para leitores que usam o mesmo nome da visão por turma."""
        return self.pct

    def __getitem__(self, chave: str):
        """Acesso por chave (dict-like) além do acesso por atributo."""
        return getattr(self, chave)


def _count(c: str | None) -> tuple[int, int]:
    """(presença, falta) de um conceito; J/NULL/qualquer outro não conta."""
    if c in CONCEITOS_PRESENCA:
        return 1, 0
    if c in CONCEITOS_CONTABEIS:  # presença + F; se não é presença, é falta
        return 0, 1
    return 0, 0


# ---------------------------------------------------------------------------
# Regra D2 do legado
# ---------------------------------------------------------------------------

def ofertas_unicas_ativas(oferta_ids: Iterable[int]) -> set[int]:
    """Subconjunto de `oferta_ids` composto das ofertas que são a ÚNICA
    oferta ativa da sua turma. Uma única consulta agregada sobre `turma_curso`
    (COUNT por turma com HAVING = 1) — sem N+1."""
    oferta_ids = list(oferta_ids)
    if not oferta_ids:
        return set()

    # 1) turma de cada oferta pedida.
    turmas_das_ofertas: dict[int, int] = {
        id_: turma_id
        for id_, turma_id in db.session.query(TurmaCurso.id, TurmaCurso.turma_id)
        .filter(TurmaCurso.id.in_(oferta_ids))
        .all()
    }
    if not turmas_das_ofertas:
        return set()

    # 2) turmas com exatamente UMA oferta ativa (a oferta ativa é única então).
    turmas_unicas = {
        turma_id
        for (turma_id,) in db.session.query(TurmaCurso.turma_id)
        .filter(
            TurmaCurso.turma_id.in_(set(turmas_das_ofertas.values())),
            TurmaCurso.ativo.is_(True),
        )
        .group_by(TurmaCurso.turma_id)
        .having(func.count(TurmaCurso.id) == 1)
        .all()
    }

    return {
        oferta_id
        for oferta_id, turma_id in turmas_das_ofertas.items()
        if turma_id in turmas_unicas
    }


def oferta_unica_com_legado(oferta_id: int) -> bool:
    """A oferta é a única ativa da sua turma? (suas linhas legadas contam)."""
    return oferta_id in ofertas_unicas_ativas([oferta_id])


# ---------------------------------------------------------------------------
# Agregação POR OFERTA (uma consulta de frequência, regra D2 do legado)
# ---------------------------------------------------------------------------

def agregar_por_oferta(
    oferta_ids: Iterable[int],
    por_turma: int | None = None,
) -> dict[int, OfertaFrequencia]:
    """Agregado por oferta em UMA consulta na tabela `frequencia`.

    Agrupa `GROUP BY turma_curso_id, aluno_id, conceito` com COUNT e monta o
    percentual pela regra única. As linhas legadas (`turma_curso_id IS NULL`)
    entram no agregado de uma oferta apenas quando ela é a única ativa da
    turma (regra D2) — decisão da etapa, aplicada dentro do serviço.

    `unidade_id`: estreita para o escopo de unidade do chamador, quando ele
    já filtra por unidade hoje (Frequencia é TenantMixin; o filtro é direto
    na coluna `unidade_id` da tabela).
    `por_turma`: restrinje às linhas dessa turma (propriedade do modelo).
    Ofertas sem nenhuma linha retornam agregado zerado (presentes=faltas=0,
    pct=0.0), preservando o `else 0.0` dos consumidores.
    """
    oferta_ids = list(oferta_ids)
    if not oferta_ids:
        return {}

    # Regra D2: ofertas candidatas a receber as linhas legadas da sua turma.
    unicas = ofertas_unicas_ativas(oferta_ids)
    turmas_unicas = {
        id_: turma_id
        for id_, turma_id in db.session.query(
            TurmaCurso.id, TurmaCurso.turma_id
        )
        .filter(TurmaCurso.id.in_(sorted(unicas)))
        .all()
    } if unicas else {}

    # UMA consulta de frequência: linhas das ofertas + (regra D2) linhas
    # legadas das turmas em que a oferta pedida é a única ativa.
    q = db.session.query(
        Frequencia.turma_id,
        Frequencia.turma_curso_id,
        Frequencia.aluno_id,
        Frequencia.conceito,
        func.count(Frequencia.id),
    )
    if unicas and turmas_unicas:
        legadas = (
            Frequencia.turma_curso_id.is_(None),
            Frequencia.turma_id.in_(set(turmas_unicas.values())),
        )
        q = q.filter(
            db.or_(
                Frequencia.turma_curso_id.in_(oferta_ids),
                db.and_(*legadas),
            )
        )
    else:
        q = q.filter(Frequencia.turma_curso_id.in_(oferta_ids))
    if por_turma is not None:
        q = q.filter(Frequencia.turma_id == por_turma)
    rows = q.group_by(
        Frequencia.turma_id,
        Frequencia.turma_curso_id,
        Frequencia.aluno_id,
        Frequencia.conceito,
    ).all()

    # Bucketing em Python: oferta própria (turma_curso_id) ou legado atribuído
    # à oferta única da sua turma (regra D2).
    baldes: dict[int, dict[int, list[int]]] = defaultdict(dict)
    totais: dict[int, list[int]] = defaultdict(lambda: [0, 0])
    for turma_id, tcurso_id, aluno_id, conceito, n in rows:
        if tcurso_id is None:
            # legado: pertence à única oferta ativa daquela turma
            alvo = next(
                (
                    id_
                    for id_, t in turmas_unicas.items()
                    if t == turma_id and id_ in oferta_ids
                ),
                None,
            )
        else:
            alvo = tcurso_id
        if alvo is None or alvo not in oferta_ids:
            continue
        p, f = _count(conceito)
        if p == 0 and f == 0:
            continue  # J e afins não entram em nenhum agregado
        atual = baldes[alvo].get(aluno_id)
        if atual is None:
            atual = [0, 0]
            baldes[alvo][aluno_id] = atual
        atual[0] += p * n
        atual[1] += f * n
        totais[alvo][0] += p * n
        totais[alvo][1] += f * n

    resultado: dict[int, OfertaFrequencia] = {}
    for oferta_id in oferta_ids:
        info = OfertaFrequencia(turma_id=turmas_unicas.get(oferta_id))
        per_aluno = baldes.get(oferta_id, {})
        for aluno_id, (p, f) in per_aluno.items():
            info.por_aluno[aluno_id] = AlunoOfertaFrequencia(
                presentes=p,
                faltas=f,
                total=p + f,
                pct=percentual(p, f),
            )
        info.presentes, info.faltas = totais.get(oferta_id, [0, 0])
        info.total = info.presentes + info.faltas
        info.pct = percentual(info.presentes, info.faltas)
        resultado[oferta_id] = info

    # turma_id das ofertas não-únicas (uma consulta, só para preenchimento)
    sem_turma = [
        id_ for id_, info in resultado.items() if info.turma_id is None
    ]
    if sem_turma:
        for id_, turma_id in db.session.query(
            TurmaCurso.id, TurmaCurso.turma_id
        ).filter(TurmaCurso.id.in_(sem_turma)).all():
            resultado[id_].turma_id = turma_id

    return resultado


# ---------------------------------------------------------------------------
# Agregação POR TURMA (uma consulta; mesma estrutura do painel atual)
# ---------------------------------------------------------------------------

def agregar_por_turma(
    turmas_ids: Iterable[int],
) -> dict[int, TurmaFrequencia]:
    """Soma de TODAS as linhas da turma (ofertas + legado), exatamente como
    fazia o agregador do painel antes do serviço — UMA consulta bruta
    ordenada por (turma, aluno, data), preservando a lista (data, conceito)
    por aluno (inclusive o J) para as séries/sequências do painel.

    Turmas sem nenhuma linha de frequência não entram no dict (mesmo
    comportamento de `painel_pedagogico.frequencia` e da visão por período
    — §12.21). `unidade_id` estreita o escopo quando o chamador já filtra
    por unidade (preserva os números em dados bem-comportados de unidade
    única).
    """
    turmas_ids = list(turmas_ids)
    if not turmas_ids:
        return {}

    q = db.session.query(
        Frequencia.turma_id,
        Frequencia.aluno_id,
        Frequencia.data,
        Frequencia.conceito,
    ).filter(Frequencia.turma_id.in_(turmas_ids))
    rows = q.order_by(
        Frequencia.turma_id, Frequencia.aluno_id, Frequencia.data
    ).all()

    bruto: dict[int, dict] = defaultdict(
        lambda: {"por_aluno": defaultdict(list), "total": 0, "presentes": 0}
    )
    for turma_id, aluno_id, data_aula, conceito in rows:
        bruto[turma_id]["por_aluno"][aluno_id].append((data_aula, conceito))
        p, f = _count(conceito)
        if p or f:
            bruto[turma_id]["total"] += 1
            bruto[turma_id]["presentes"] += p

    resultado: dict[int, TurmaFrequencia] = {}
    for turma_id, info in bruto.items():
        pct_por_aluno: dict[int, float] = {}
        for aluno_id, lista in info["por_aluno"].items():
            contabeis = sum(1 for _, c in lista if c in CONCEITOS_CONTABEIS)
            if contabeis:
                pres = sum(1 for _, c in lista if c in CONCEITOS_PRESENCA)
                pct_por_aluno[aluno_id] = percentual(pres, contabeis - pres)
        resultado[turma_id] = TurmaFrequencia(
            por_aluno={aid: list(l) for aid, l in info["por_aluno"].items()},
            por_aluno_pct=pct_por_aluno,
            total=info["total"],
            presentes=info["presentes"],
            pct_turma=percentual(info["presentes"], info["total"] - info["presentes"]),
        )
    return resultado

# ---------------------------------------------------------------------------
# Leituras em LOTE (D3b-2.2) — mapas pré-calculados para a listagem de
# turmas. Mesma fórmula do serviço (J fora do denominador, 1 casa decimal,
# 0.0 sem registros contáveis). Sem N+1: UMA consulta por mapa.
# ---------------------------------------------------------------------------


def freq_geral_turmas_em_lote(
    turmas_ids: Iterable[int],
) -> dict[int, float]:
    """`{turma_id: pct}` para uma lista de turmas — UMA consulta.

    Reusa `agregar_por_turma` (soma de todas as linhas da turma, ofertas +
    legado). Turmas sem lançamento ficam com 0.0 (mesmo comportamento da
    property `Turma.freq_geral`).
    """
    turmas_ids = list(turmas_ids)
    if not turmas_ids:
        return {}
    agregado = agregar_por_turma(turmas_ids)
    return {
        tid: (agregado.get(tid).pct_turma if agregado.get(tid) is not None else 0.0)
        for tid in turmas_ids
    }


def freq_geral_ofertas_em_lote(
    oferta_ids: Iterable[int],
    por_turma: int | None = None,
) -> dict[int, float]:
    """`{oferta_id: pct}` para uma lista de ofertas — UMA consulta.

    Reusa `agregar_por_oferta` (regra D2 do legado aplicada). Ofertas sem
    lançamento ficam com 0.0 (mesmo comportamento de `Turma.freq_geral_oferta`).
    `por_turma` restringe a um único `turma_id` (equivalente ao parâmetro
    do serviço), preservando a semântica de `freq_geral_oferta`.
    """
    oferta_ids = list(oferta_ids)
    if not oferta_ids:
        return {}
    agregado = agregar_por_oferta(
        oferta_ids, por_turma=por_turma
    )
    return {
        oid: (agregado.get(oid).pct if agregado.get(oid) is not None else 0.0)
        for oid in oferta_ids
    }

# ---------------------------------------------------------------------------
# Leitura em LOTE do histórico do aluno (D3b-2.3) — UMA consulta para todas
# as inscrições. Mesma fórmula de `app.utils.logica.calcular_estatisticas_frequencia`
# (J fora do denominador, 1 casa decimal). Sem N+1.
# ---------------------------------------------------------------------------


def frequencias_aluno_por_inscricao(
    aluno_id: int,
    pares: Iterable[tuple[int, int | None]],
) -> dict[tuple[int, int | None], dict]:
    """`{(turma_id, oferta_id): stats}` para um aluno — UMA consulta de frequência.

    `stats` é o mesmo dict devolvido por `calcular_estatisticas_frequencia`
    (presenças, faltas, justificadas, total, percentuais). Inscrição sem
    lançamento devolve o dict zerado (mesmo comportamento do cálculo antigo).

    Regra D2 do legado (a MESMA de `agregar_por_oferta`): as linhas com
    `turma_curso_id IS NULL` entram na inscrição da oferta apenas quando ela é
    a única ativa da turma (`ofertas_unicas_ativas`); em turma com 2+ ofertas
    ativas, ou sem oferta ativa, o legado não entra em nenhuma. O par com
    `oferta_id=None` (inscrição legada, schema anterior a `c3d4e5f6a7b8`) lê
    somente as linhas legadas da própria turma.
    """
    from collections import defaultdict

    from app.utils.logica import calcular_estatisticas_frequencia

    pares = list(dict.fromkeys(pares))
    if not pares:
        return {}

    # Regra D2: candidatas a absorver o legado da turma (helper único).
    oferta_ids = sorted({oferta_id for _, oferta_id in pares if oferta_id is not None})
    unicas = ofertas_unicas_ativas(oferta_ids)
    turmas_unicas = {turma_id for turma_id, oferta_id in pares if oferta_id in unicas}
    turmas_legadas = {turma_id for turma_id, oferta_id in pares if oferta_id is None}

    from app import db
    from app.models import Frequencia

    condicoes = []
    if oferta_ids:
        condicoes.append(Frequencia.turma_curso_id.in_(oferta_ids))
    if turmas_unicas:
        condicoes.append(
            db.and_(
                Frequencia.turma_curso_id.is_(None),
                Frequencia.turma_id.in_(turmas_unicas),
            )
        )
    if turmas_legadas:
        condicoes.append(
            db.and_(
                Frequencia.turma_curso_id.is_(None),
                Frequencia.turma_id.in_(turmas_legadas),
            )
        )

    contagens: dict[tuple[int, int | None], list[str]] = defaultdict(list)
    if condicoes:
        linhas = (
            db.session.query(
                Frequencia.turma_id,
                Frequencia.turma_curso_id,
                Frequencia.conceito,
                func.count(Frequencia.id),
            )
            .filter(Frequencia.aluno_id == aluno_id, db.or_(*condicoes))
            .group_by(
                Frequencia.turma_id,
                Frequencia.turma_curso_id,
                Frequencia.conceito,
            )
            .all()
        )
        for turma_id, oferta_id, conceito, n in linhas:
            contagens[(turma_id, oferta_id)].extend([conceito] * n)

    resultado: dict[tuple[int, int | None], dict] = {}
    for turma_id, oferta_id in pares:
        conceitos = list(contagens.get((turma_id, oferta_id), ()))
        if oferta_id is not None and oferta_id in unicas:
            # D2: a oferta única ativa absorve as linhas legadas da turma.
            conceitos.extend(contagens.get((turma_id, None), ()))
        resultado[(turma_id, oferta_id)] = calcular_estatisticas_frequencia(conceitos)
    return resultado


# ---------------------------------------------------------------------------
# Estatísticas do GET /frequencia por aluno (D3b-2.4) — sem N+1.
# ---------------------------------------------------------------------------


def conceitos_frequencia_por_aluno(
    aluno_ids: Iterable[int],
    turma_id: int,
    oferta_id: int | None = None,
    somente_oferta: bool = False,
) -> dict[int, list[str]]:
    """`{aluno_id: [conceito, ...]}` para a tela de lançamento.

    - `somente_oferta=True` e `oferta_id` informado: apenas linhas da oferta
      (`turma_curso_id == oferta_id`) — usado em turma com 2+ ofertas.
    - caso contrário: todas as linhas da turma (`turma_id`), incluindo o
      legado NULL (oferta única / 0 ofertas) — comportamento anterior.
    UMA consulta, sem N+1.
    """
    from sqlalchemy import func

    from app import db
    from app.models import Frequencia

    aluno_ids = list(aluno_ids)
    if not aluno_ids:
        return {}
    q = db.session.query(
        Frequencia.aluno_id, Frequencia.conceito, func.count(Frequencia.id)
    ).filter(Frequencia.aluno_id.in_(aluno_ids))
    if somente_oferta and oferta_id is not None:
        q = q.filter(Frequencia.turma_curso_id == oferta_id)
    else:
        q = q.filter(Frequencia.turma_id == turma_id)
    rows = q.group_by(Frequencia.aluno_id, Frequencia.conceito).all()

    resultado: dict[int, list[str]] = {aid: [] for aid in aluno_ids}
    for aluno_id, conceito, n in rows:
        resultado.setdefault(aluno_id, []).extend([conceito] * n)
    return resultado

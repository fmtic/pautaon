"""Ordenação A-Z de nomes em memória (AJ22-D).

A ordem de exibição NÃO depende do `collation` do banco: a chave é
normalizada em Python (casefold + remoção de acentos via `unicodedata`),
com desempate por `id` para nomes que só diferem em caixa/acentuação.

Usado nos dois pontos que consomem o catálogo de `Nivel` fora do
fechamento:

- aba "Níveis" do planejamento (`app/registros/core.py`);
- selects de nível de `turmas/detalhe.html` (`app/registros/turmas.py`).

Nenhuma consulta extra: os objetos já vêm carregados (join/select
simples) e a ordenação/grouping acontece na aplicação.
"""
from __future__ import annotations

import unicodedata


def chave_ordenacao(valor) -> str:
    """Chave A-Z normalizada: sem acentos e em minúsculas (casefold).

    ``'Álgebra'`` e ``'algebra'`` produzem a mesma chave; ``'avançado'``
    e ``'Avançado'`` também (o desempate é feito pelo `id` em quem ordena
    objetos). `None`/vazio viram ``''`` (grupo "sem curso" primeiro).
    """
    texto = unicodedata.normalize('NFD', str(valor or ''))
    return ''.join(
        caractere
        for caractere in texto
        if unicodedata.category(caractere) != 'Mn'
    ).casefold()


def _chave_nivel(nivel) -> tuple:
    """Ativos primeiro (A-Z); inativos no fim do bloco (também A-Z)."""
    return (
        not bool(nivel.ativo),
        chave_ordenacao(nivel.nome),
        nivel.id or 0,
    )


def agrupar_niveis_por_curso(niveis) -> list[dict]:
    """Devolve ``[{'curso', 'niveis', 'total'}, ...]`` em ordem A-Z.

    - o grupo "sem curso" (legado) vem sempre primeiro;
    - os demais grupos são ordenados pelo nome do curso (normalizado,
      desempate por `id`);
    - dentro de cada grupo, níveis ativos em A-Z e inativos no fim;
    - cursos sem nível não geram grupo (o grupo só nasce de um nível).

    Não faz consultas: usa apenas os objetos recebidos e o relacionamento
    ``Nivel.curso`` (já carregado com `joinedload` pelos chamadores).
    """
    sem_curso = []
    por_curso: dict = {}
    for nivel in niveis or []:
        if nivel.curso_id is None:
            sem_curso.append(nivel)
        else:
            curso = nivel.curso
            por_curso.setdefault((nivel.curso_id, curso), []).append(nivel)

    grupos = []
    if sem_curso:
        itens = sorted(sem_curso, key=_chave_nivel)
        grupos.append({'curso': None, 'niveis': itens, 'total': len(itens)})

    def chave_grupo(item):
        (curso_id, curso), _ = item
        nome = getattr(curso, 'nome', '') if curso is not None else ''
        return chave_ordenacao(nome), curso_id or 0

    for (_curso_id, curso), itens in sorted(por_curso.items(), key=chave_grupo):
        ordenados = sorted(itens, key=_chave_nivel)
        grupos.append({
            'curso': curso,
            'niveis': ordenados,
            'total': len(ordenados),
        })
    return grupos


def ordenar_niveis(niveis) -> list:
    """Lista plana na ordem dos grupos: sem curso, depois curso A-Z.

    Dentro de cada bloco, ativos A-Z e inativos no fim. Usada pelos
    selects de nível (que recebem só níveis ativos) e pelo loop dos
    modais de edição do planejamento.
    """
    return [
        nivel
        for grupo in agrupar_niveis_por_curso(niveis)
        for nivel in grupo['niveis']
    ]

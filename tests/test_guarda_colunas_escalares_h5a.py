"""Guarda H5a: nenhum acesso às 6 colunas escalares de agenda fora de models.

As colunas ``dias_semana``/``hora_inicio``/``hora_fim`` de ``Turma`` e
``TurmaCurso`` permanecem no schema até o H5b, mas são LEGADO SEM USO desde o
H5a: a agenda é a grade ``turma_curso_horario``. Este teste varre a AST de
``app/`` e ``scripts/`` e falha se algum código de produção voltar a acessar
esses atributos mapeados.

A exceção são os acessos legítimos aos campos homônimos de outras classes:

- ``Linha`` (DTO da grade) → ``self.dia_semana``/``self.hora_inicio``/...
- linhas de ``TurmaCursoHorario`` → ``linha.dia_semana``, ``l.hora_inicio``,
  ``item.hora_fim`` (as três variáveis convencionadas no serviço);
- comparação de coluna da própria grade → ``TurmaCursoHorario.hora_inicio``.

Modelos e migrations ficam fora da varredura (lá as colunas são declaradas /
lidas pelo backfill histórico).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[1]
ATRIBUTOS = {"dias_semana", "hora_inicio", "hora_fim"}
BASES_DE_LINHA = {"l", "linha", "item"}
CLASSES_DTO = {"Linha", "GradeExibicao"}


def _violacoes(caminho: Path) -> list[str]:
    arvore = ast.parse(caminho.read_text(encoding="utf-8"), filename=str(caminho))
    achados: list[str] = []

    class Visitador(ast.NodeVisitor):
        def __init__(self) -> None:
            self.classe: list[str] = []

        def visit_ClassDef(self, no: ast.ClassDef) -> None:  # noqa: N802
            self.classe.append(no.name)
            self.generic_visit(no)
            self.classe.pop()

        def visit_Attribute(self, no: ast.Attribute) -> None:  # noqa: N802
            if no.attr not in ATRIBUTOS:
                self.generic_visit(no)
                return
            base = no.value
            permitido = False
            if isinstance(base, ast.Name):
                if base.id in BASES_DE_LINHA:
                    permitido = True
                elif base.id == "TurmaCursoHorario":
                    permitido = True
                elif (
                    base.id == "self"
                    and self.classe
                    and self.classe[-1] in CLASSES_DTO
                ):
                    permitido = True
            if not permitido:
                rel = caminho.relative_to(RAIZ)
                achados.append(
                    f"{rel}:{no.lineno}: acesso a .{no.attr} "
                    f"(base={ast.unparse(base)!r})"
                )
            self.generic_visit(no)

    Visitador().visit(arvore)
    return achados


def test_nenhum_acesso_as_colunas_escalares_em_app_e_scripts():
    violacoes: list[str] = []
    for pasta in ("app", "scripts"):
        for caminho in sorted((RAIZ / pasta).rglob("*.py")):
            if "__pycache__" in caminho.parts:
                continue
            violacoes.extend(_violacoes(caminho))

    assert not violacoes, (
        "H5a: a agenda vive só em turma_curso_horario; acessos às colunas "
        "escalares de Turma/TurmaCurso encontrados:\n" + "\n".join(violacoes)
    )


def test_templates_e_js_nao_leem_colunas_escalares_de_turma_ou_oferta():
    """Guarda complementar: Jinja/JS não podem voltar a ler as colunas.

    ``grade_oferta.hora_inicio``/``grade_linha.hora_inicio`` são objetos de
    exibição da GRADE e continuam permitidos; o padrão abaixo só casa os
    receptores ``turma``/``turma_obj``/``oferta``/``oferta_<algo>``.
    """
    import re

    padrao = re.compile(
        r"\b(?:turma|turma_obj|oferta|oferta_[a-z_]+)\.(?:"
        r"dias_semana|hora_inicio|hora_fim)\b"
    )
    violacoes: list[str] = []
    for pasta in ("app/templates", "app/static/js"):
        for caminho in sorted((RAIZ / pasta).rglob("*")):
            if not caminho.is_file() or caminho.suffix not in {".html", ".js"}:
                continue
            for numero, linha in enumerate(
                caminho.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if padrao.search(linha):
                    rel = caminho.relative_to(RAIZ)
                    violacoes.append(f"{rel}:{numero}: {linha.strip()}")

    assert not violacoes, (
        "H5a: template/JS lendo coluna escalar de agenda:\n"
        + "\n".join(violacoes)
    )

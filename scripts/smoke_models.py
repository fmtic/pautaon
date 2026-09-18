"""
================================================================================
SMOKE TEST - Pacote de modelos (app/models/)
================================================================================

Objetivo:
    Validar que a modularização do antigo `models.py` em `app/models/` não
    quebrou NADA em runtime. Testa:

        1. Importação pública (from app.models import ...)
        2. Relacionamentos diretos e inversos (backrefs)
        3. Extensão 1:1 (Aluno <-> SituacaoEscolar)
        4. Properties derivadas (matricula, idade, foto)
        5. Properties JSON (escolaridade_json, etc.)
        6. Property híbrida SQL (Frequencia.presente)
        7. Métodos que fazem import local (freq_geral, alunos_enturmados, ...)
        8. Backrefs de auditoria (logs, alunos_criados, ...)
        9. Ausência de mappers duplicados (sinal de import duplo)

Como rodar:
    # Dentro do venv, na raiz do projeto
    python scripts/smoke_models.py

    # Ou como task Flask (se registrada no app):
    flask smoke-models

Exit code:
    0 -> todos os testes passaram
    1 -> pelo menos um teste falhou (útil em CI)

IMPORTANTE:
    O script funciona em bancos vazios: os testes que precisam de dados são
    marcados como "SKIP" quando não há registros. Isso garante que dá para
    rodar em CI limpo.
================================================================================
"""

from __future__ import annotations

import os
import sys
import traceback
from contextlib import contextmanager
from typing import Callable, Optional

# Garante que a raiz do projeto está no sys.path para importar `app`.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


# -----------------------------------------------------------------------------
# Infraestrutura mínima de teste
# -----------------------------------------------------------------------------

class _Result:
    """Resultado de um teste individual."""
    PASSED = "PASS"
    FAILED = "FAIL"
    SKIPPED = "SKIP"


class SmokeRunner:
    """Executor de testes com relatório final e exit code."""

    def __init__(self):
        self.total = 0
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.failures: list[tuple[str, str]] = []   # (nome, traceback)

    @contextmanager
    def section(self, title: str):
        """Agrupa visualmente os testes por seção."""
        print()
        print(f"── {title} " + "─" * max(0, 60 - len(title)))
        yield

    def check(self, name: str, fn: Callable[[], Optional[str]]):
        """
        Executa uma verificação.

        `fn` pode retornar:
            - None    -> passou
            - 'SKIP: motivo' -> pulado
            - qualquer outra string -> falhou com essa mensagem
        Exceções também contam como falha.
        """
        self.total += 1
        try:
            result = fn()
        except Exception:
            self.failed += 1
            tb = traceback.format_exc()
            self.failures.append((name, tb))
            print(f"  [FAIL] {name}")
            for line in tb.strip().splitlines()[-3:]:
                print(f"         {line}")
            return

        if result is None:
            self.passed += 1
            print(f"  [PASS] {name}")
        elif isinstance(result, str) and result.startswith("SKIP"):
            self.skipped += 1
            print(f"  [SKIP] {name}  ({result[4:].strip(' :')})")
        else:
            self.failed += 1
            self.failures.append((name, str(result)))
            print(f"  [FAIL] {name}  ->  {result}")

    def summary(self) -> int:
        print()
        print("=" * 70)
        print(f"RESUMO: {self.total} testes | "
              f"{self.passed} passaram | "
              f"{self.skipped} pulados | "
              f"{self.failed} falharam")
        print("=" * 70)

        if self.failures:
            print("\nDetalhes das falhas:\n")
            for name, tb in self.failures:
                print(f"■ {name}")
                print(tb)
                print("-" * 70)

        return 0 if self.failed == 0 else 1


# -----------------------------------------------------------------------------
# Helpers de banco
# -----------------------------------------------------------------------------

def _has_data(*models) -> bool:
    """True se QUALQUER um dos modelos tiver ao menos 1 registro."""
    return any(m.query.first() is not None for m in models)


def _skip_if_empty(*models) -> Optional[str]:
    """Retorna 'SKIP: banco vazio' se todos estiverem vazios, senão None."""
    if not _has_data(*models):
        return "SKIP: banco vazio (sem registros para testar)"
    return None


# -----------------------------------------------------------------------------
# Bateria de testes
# -----------------------------------------------------------------------------

def run_all_checks() -> int:
    # Imports TARDIOS: só depois do app context.
    from app.models import (
        Aluno, Turma, User, Inscricao, SituacaoEscolar, Atendimento,
        Frequencia, RegistroAula, PeriodoLetivo, ConselhoClasse,
        DiaBloqueado, TemaAula, Curso, Nivel, Unidade,
        ConfiguracaoSistema, Transferencia,
    )
    from app.database import db

    runner = SmokeRunner()

    # -------------------------------------------------------------------------
    # 1. Ausência de mappers duplicados
    # -------------------------------------------------------------------------
    with runner.section("1. Integridade do registry do SQLAlchemy"):

        def _no_duplicate_tables():
            from sqlalchemy import inspect
            insp = inspect(db.engine)
            # Se houvesse tabela duplicada, o próprio registry teria explodido
            # no import. Aqui só confirmamos que o registry tem as tabelas.
            tables = set(insp.get_table_names())
            esperadas = {
                'unidade', 'configuracao_sistema', 'user', 'curso', 'nivel',
                'periodo_letivo', 'turma', 'tema_aula', 'aluno',
                'situacao_escolar', 'inscricoes', 'transferencia',
                'dia_bloqueado', 'dia_bloqueado_turma', 'frequencia',
                'registro_aula', 'periodo_conselho', 'conselho_pergunta',
                'opcao_proxima_turma', 'conselho_classe', 'conselho_resposta',
                'atendimento', 'agenda_servico_social', 'respostas_formulario',
                'log_acao', 'registro',
            }
            faltando = esperadas - tables
            if faltando:
                return f"tabelas ausentes no banco: {sorted(faltando)}"
            return None

        runner.check("Todas as tabelas esperadas existem", _no_duplicate_tables)

        def _no_class_identity_conflict():
            # Cada classe deve aparecer uma única vez no registry.
            from app.models import __all__ as public
            vistos = {}
            for nome in public:
                cls = getattr(__import__('app.models', fromlist=[nome]), nome)
                if cls in vistos.values():
                    return f"classe duplicada: {nome}"
                vistos[nome] = cls
            return None

        runner.check("Sem classes duplicadas em app.models", _no_class_identity_conflict)

    # -------------------------------------------------------------------------
    # 2. Relacionamentos diretos e inversos
    # -------------------------------------------------------------------------
    with runner.section("2. Relacionamentos diretos e inversos"):

        def _aluno_inscricoes():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            # apenas acessa; se o backref não existir, levanta AttributeError
            _ = a.inscricoes
            _ = a.turmas
            _ = a.atendimentos
            _ = a.transferencias
            return None

        runner.check("Aluno -> inscricoes / turmas / atendimentos / transferencias",
                     _aluno_inscricoes)

        def _aluno_situacao_escolar():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            se = a.situacao_escolar
            # pode ser None se o aluno não tiver situação cadastrada
            if se is not None and se.aluno is not a:
                return "SituacaoEscolar.aluno não aponta de volta para o Aluno"
            return None

        runner.check("Aluno <-> SituacaoEscolar (1:1, uselist=False)",
                     _aluno_situacao_escolar)

        def _turma_relacionamentos():
            skip = _skip_if_empty(Turma)
            if skip:
                return skip
            t = Turma.query.first()
            _ = t.inscricoes
            _ = t.alunos          # backref N:N
            _ = t.diarios         # backref de RegistroAula.turma_rel
            _ = t.temas_disponiveis
            _ = t.conselhos
            _ = t.periodo_letivo
            _ = t.curso
            _ = t.professor
            return None

        runner.check("Turma -> inscricoes / alunos / diarios / temas / conselhos",
                     _turma_relacionamentos)

        def _turma_alunos_retorna_aluno():
            skip = _skip_if_empty(Turma)
            if skip:
                return skip
            t = Turma.query.first()
            alunos = t.alunos.all() if hasattr(t.alunos, 'all') else list(t.alunos)
            if not alunos:
                return "SKIP: turma sem alunos vinculados"
            if not all(isinstance(a, Aluno) for a in alunos):
                return "turma.alunos contém objetos que não são Aluno"
            return None

        runner.check("Turma.alunos retorna instâncias de Aluno",
                     _turma_alunos_retorna_aluno)

        def _user_backrefs():
            skip = _skip_if_empty(User)
            if skip:
                return skip
            u = User.query.first()
            _ = u.turmas_vinculadas
            _ = u.alunos_criados
            _ = u.logs
            _ = u.dias_bloqueados_criados
            _ = u.dias_bloqueado_turma_criados
            _ = u.atendimentos_registrados
            _ = u.registros
            _ = u.agendamentos_sociais
            _ = u.formularios_preenchidos
            return None

        runner.check("User -> turmas_vinculadas / logs / alunos_criados / ...",
                     _user_backrefs)

        def _periodo_letivo_backrefs():
            skip = _skip_if_empty(PeriodoLetivo)
            if skip:
                return skip
            p = PeriodoLetivo.query.first()
            _ = p.turmas
            _ = p.conselhos
            _ = p.dias_bloqueados
            return None

        runner.check("PeriodoLetivo -> turmas / conselhos / dias_bloqueados",
                     _periodo_letivo_backrefs)

        def _inscricao_volta():
            skip = _skip_if_empty(Inscricao)
            if skip:
                return skip
            i = Inscricao.query.first()
            if i.aluno is None:
                return "Inscricao sem aluno associado"
            if i.turma is None:
                return "Inscricao sem turma associada"
            return None

        runner.check("Inscricao -> aluno / turma", _inscricao_volta)

    # -------------------------------------------------------------------------
    # 3. Properties derivadas
    # -------------------------------------------------------------------------
    with runner.section("3. Properties derivadas de Aluno"):

        def _matricula():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            m = a.matricula
            if not isinstance(m, str):
                return f"matricula não é string: {type(m).__name__}"
            if "." not in m or len(m.split(".")[0]) != 5:
                return f"formato inesperado: {m!r}"
            return None

        runner.check("Aluno.matricula no formato NNNNN.YYYY", _matricula)

        def _idade():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            i = a.idade
            if not isinstance(i, int) or i < 0:
                return f"idade inválida: {i!r}"
            return None

        runner.check("Aluno.idade é int >= 0", _idade)

        def _foto_alias():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            if a.foto != a.foto_path:
                return "foto != foto_path"
            return None

        runner.check("Aluno.foto espelha Aluno.foto_path", _foto_alias)

        def _jsons():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            for prop in ("escolaridade_json", "identificacao_json",
                         "socioeconomico_json", "diversidade_json"):
                v = getattr(a, prop)
                if not isinstance(v, dict):
                    return f"{prop} não é dict (é {type(v).__name__})"
            return None

        runner.check("Aluno.*_json devolve dict (mesmo se vazio)", _jsons)

        def _json_roundtrip():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            original = a.escolaridade_json
            a.escolaridade_json = {"teste": "roundtrip", "n": 1}
            lido = a.escolaridade_json
            # restaura para não sujar o banco (não commitamos)
            a.escolaridade_json = original
            if lido != {"teste": "roundtrip", "n": 1}:
                return f"roundtrip falhou: {lido!r}"
            return None

        runner.check("Setter/Getter JSON faz roundtrip", _json_roundtrip)

    # -------------------------------------------------------------------------
    # 4. Híbrida SQL (Frequencia.presente)
    # -------------------------------------------------------------------------
    with runner.section("4. Property híbrida de Frequencia"):

        def _presente_python():
            skip = _skip_if_empty(Frequencia)
            if skip:
                return skip
            f = Frequencia.query.first()
            if f.conceito in ("A", "B", "C", "D"):
                if not f.presente:
                    return f"conceito={f.conceito!r} deveria ser presente=True"
            elif f.conceito == "F":
                if f.presente:
                    return "conceito='F' deveria ser presente=False"
            return None

        runner.check("Frequencia.presente (Python)", _presente_python)

        def _presente_sql():
            skip = _skip_if_empty(Frequencia)
            if skip:
                return skip
            total_sql = Frequencia.query.filter(Frequencia.presente.is_(True)).count()
            total_py = sum(1 for f in Frequencia.query.all() if f.presente)
            if total_sql != total_py:
                return (f"divergência Python vs SQL: "
                        f"py={total_py}, sql={total_sql}")
            return None

        runner.check("Frequencia.presente (SQL) bate com Python", _presente_sql)

    # -------------------------------------------------------------------------
    # 5. Métodos que usam import local
    # -------------------------------------------------------------------------
    with runner.section("5. Métodos com import interno"):

        def _turma_ativas():
            lista = Turma.get_ativas()
            if not isinstance(lista, list):
                return f"get_ativas não retornou list: {type(lista).__name__}"
            return None

        runner.check("Turma.get_ativas()", _turma_ativas)

        def _freq_geral():
            skip = _skip_if_empty(Turma)
            if skip:
                return skip
            t = Turma.query.first()
            v = t.freq_geral
            if not isinstance(v, float):
                return f"freq_geral não é float: {type(v).__name__}"
            if not (0.0 <= v <= 100.0):
                return f"freq_geral fora de [0,100]: {v}"
            return None

        runner.check("Turma.freq_geral (usa import de Frequencia)", _freq_geral)

        def _alunos_ativos_count():
            skip = _skip_if_empty(Turma)
            if skip:
                return skip
            t = Turma.query.first()
            v = t.alunos_ativos_count
            if not isinstance(v, int) or v < 0:
                return f"alunos_ativos_count inválido: {v!r}"
            return None

        runner.check("Turma.alunos_ativos_count (usa import de Aluno)",
                     _alunos_ativos_count)

        def _alunos_enturmados():
            skip = _skip_if_empty(PeriodoLetivo)
            if skip:
                return skip
            p = PeriodoLetivo.query.first()
            v = p.alunos_enturmados()
            if not isinstance(v, int) or v < 0:
                return f"alunos_enturmados inválido: {v!r}"
            return None

        runner.check("PeriodoLetivo.alunos_enturmados (import de Aluno)",
                     _alunos_enturmados)

    # -------------------------------------------------------------------------
    # 6. Auditoria / backrefs de criação
    # -------------------------------------------------------------------------
    with runner.section("6. Backrefs de auditoria"):

        def _log_acao_normalize():
            from app.models import LogAcao
            try:
                from unidecode import unidecode  # noqa: F401
            except ImportError:
                return "SKIP: unidecode não instalado"
            if LogAcao.normalize("Ação Teste") != "acao teste":
                return "normalize não remove acento/minúscula corretamente"
            return None

        runner.check("LogAcao.normalize remove acentos e caixa",
                     _log_acao_normalize)

        def _consistencia_inscricoes():
            """Inscricao.aluno e Inscricao.turma devem estar sempre preenchidos."""
            skip = _skip_if_empty(Inscricao)
            if skip:
                return skip
            for i in Inscricao.query.all():
                if i.aluno is None:
                    return f"Inscricao {i.id} sem aluno"
                if i.turma is None:
                    return f"Inscricao {i.id} sem turma"
            return None

        runner.check("Toda Inscricao tem aluno e turma válidos",
                     _consistencia_inscricoes)

    # -------------------------------------------------------------------------
    # 7. Consistência entre relacionamentos cruzados
    # -------------------------------------------------------------------------
    with runner.section("7. Relacionamentos cruzados"):

        def _aluno_turmas_bate_com_inscricoes():
            skip = _skip_if_empty(Aluno)
            if skip:
                return skip
            a = Aluno.query.first()
            # turmas via N:N
            via_nn = {t.id for t in a.turmas}
            # turmas via Inscricao (apenas as ativas)
            via_insc = {
                i.turma_id for i in a.inscricoes
                if i.ativo and i.turma is not None
            }
            if not via_insc.issubset(via_nn):
                return (f"aluno {a.id}: turmas via Inscricao {via_insc} "
                        f"não está contido em turmas via N:N {via_nn}")
            return None

        runner.check("Aluno.turmas ⊇ turmas com Inscricao ativa",
                     _aluno_turmas_bate_com_inscricoes)

        def _turma_alunos_bate():
            skip = _skip_if_empty(Turma)
            if skip:
                return skip
            t = Turma.query.first()
            via_nn = {a.id for a in (t.alunos.all() if hasattr(t.alunos, 'all') else t.alunos)}
            via_insc = {
                i.aluno_id for i in t.inscricoes
                if i.ativo and i.aluno is not None
            }
            if not via_insc.issubset(via_nn):
                return (f"turma {t.id}: alunos via Inscricao {via_insc} "
                        f"não contido em alunos via N:N {via_nn}")
            return None

        runner.check("Turma.alunos ⊇ alunos com Inscricao ativa",
                     _turma_alunos_bate)

    return runner.summary()


# -----------------------------------------------------------------------------
# Entrypoint
# -----------------------------------------------------------------------------

def main() -> int:
    # Bootstrap: cada projeto tem um jeito de criar a app. Ajuste abaixo
    # para a factory real do seu projeto, se o nome for diferente.
    try:
        from app import create_app  # tipo: ignore[attr-defined]
        app = create_app()
    except ImportError:
        try:
            from app import app  # tipo: ignore[attr-defined]
        except ImportError:
            print("ERRO: não foi possível importar a app "
                  "(esperado `create_app()` em app/__init__.py ou `app` global).")
            return 2

    with app.app_context():
        return run_all_checks()


if __name__ == "__main__":
    sys.exit(main())
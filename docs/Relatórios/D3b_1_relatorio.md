# ETAPA D3b.1 — Limpeza: docstring da ponte, derivado sem leitor e achados do ruff

**Risco:** baixo. **Mudança de comportamento:** nenhuma (suíte 359P → 359P, ruff 9 → 0).
**Fontes:** `docs/D3b_0_desenho.md` (D3b.1 e §3.3), MER §12.20.

---

## 1. Leitura (Passo 1)

### 1.a — Referências a `turma_conselho_concluido`

| Local | Tipo | Situação |
|---|---|---|
| `app/services/turma_curso.py:57` | **definição** | único código de aplicação que a continha |
| `tests/test_d5_encerramento.py` (import + 7 asserts em 4 testes) | **só teste** | reescrito nesta etapa |
| `app/templates/**` | — | **zero** referências (grep em `*.html`) |
| demais `.py` em `app/` | — | **zero** chamadores |
| `app/models/MER.md`, `docs/*`, `backlog_desenvolvimento.md` | documentação | citam a função (§7.7, §8.2, §10, §12.20) — **não alterados** (fora do escopo autorizado) |

**Conclusão:** confirmada a nota do MER §12.20 — a função **não tem leitor de produção**.
Os leitores reais do encerramento são `contar_ofertas_conselho()` (usado em
`app/conselho.py` `/informacoes` e `app/utils/logica.calcular_metricas_conselho`) e
`ofertas_do_painel_conselho()` (painel do conselho), que leem a flag da OFERTA
(`TurmaCurso.conselho_concluido`) — verificados por grep antes da remoção.

### 1.b — Docstrings citando a ponte removida

- `app/services/turma_curso.py:64-65` — "a coluna permanece apenas como ponte de escrita
  até a D5.5" — dentro da própria função removida (some com ela).
- `app/services/conselho_leitura.py:6-10` — "resolução manual antes da D5.5" e
  "(a coluna da turma é ponte de escrita até a D5.5)".
- Grep `ponte|até a D5.5|antes da D5.5` em `app/` achou ainda, fora dos dois citados:
  - `app/relatorios/painel_pedagogico/conselho.py:5-7` — "a lista fica em
    `scripts/verificar_onda4_d5.py` até a resolução manual antes da D5.5".
- As demais ocorrências de "D5.5" em `app/` são marcadores históricos corretos
  ("Desde D5.5 …", "D5.5: …") — **não alteradas**.

### 1.c — Os 9 achados do ruff (`ruff check app --select F821,F811,F841`)

Reproduzidos exatamente os 9 do §3.3 do desenho (0 F821). Confirmação de efeito por achado:

| # | Arquivo:linha | Achado | Efeito do removido? | Tratamento |
|---|---|---|---|---|
| 1 | `app/__init__.py:60` | `migrate = Migrate(app, db)` | **Sim** — o construtor registra a extensão no app | **chamada mantida**, só a variável saiu |
| 2 | `app/conselho.py:279` | `unidade_id = get_unidade_id()` | **Sim** — `get_unidade_id()` escreve/limpa `session["unidade_id"]` (normalização p/ perfis operacionais, `logica.py:180-185`); o resultado é que não era usado (perguntas são globais) | **chamada mantida**, só a variável saiu (com comentário) |
| 3 | `app/conselho.py:785` | `except Exception as e` sem uso | Não — o `str(e)` pertence ao handler `ValueError` anterior | `except Exception:` |
| 4 | `app/planejamento.py:90` | `except Exception as e` sem uso | Não — nada usa `e` no bloco | `except Exception:` |
| 5 | `app/registros/servico_social.py:277` | `socio = perfil["socioeconomico"]` | Não — indexação de dict já materializado por `get_perfil_completo`; `socio` nunca relido na função | linha removida |
| 6 | `app/relatorios/bi_alunos.py:2369` | reimport de `PerfilDiversidade` | Não — já importado no topo (`:11`); sem o import local o nome resolve ao mesmo objeto global | import local removido |
| 7 | `app/relatorios/bi_alunos.py:2527` | idem (em `from … import ConselhoClasse, PerfilDiversidade, Turma`) | Não — só `PerfilDiversidade` era redundante; `ConselhoClasse` (não está no topo) e `Turma` continuam | `PerfilDiversidade` saiu da linha |
| 8 | `app/relatorios/bi_routes.py:208` | `fmt_valor` não usado | Marginal — `add_format` apenas registra no workbook; o formato nunca é aplicado a célula | **chamada mantida**, só a variável saiu (com comentário) |
| 9 | `app/relatorios/bi_routes.py:211` | `fmt_item` não usado | idem | idem |

## 2. Remoção (Passo 2)

Sem leitor de produção confirmado em 1.a → **função removida**:

- `app/services/turma_curso.py` — `turma_conselho_concluido()` removida (−27 linhas).
  `contar_ofertas_conselho()` e `ofertas_do_painel_conselho()` permanecem intactas.
- `tests/test_d5_encerramento.py` — **nenhum teste removido** (13 → 13). Os 7 asserts
  de derivação foram **reescritos** como asserts das funções que ficam, preservando a
  cobertura das mesmas regras (≥1 oferta ativa e todas concluídas; oferta inativa fora;
  turma sem oferta fora):
  - `test_derivacao_uma_oferta`: pendente→`(0,1)`/`[False]`, concluída→`(1,1)`/`[True]`
    via `contar_ofertas_conselho` + `ofertas_do_painel_conselho`.
  - `test_derivacao_duas_ofertas_uma_pendente`: `(1,2)` com `[False, True]` (ordem
    insensível), depois `(2,2)`/`all(concluida)`.
  - `test_turma_sem_oferta_ativa_nao_conclui_nem_conta`: mantém `(0,0)` e acrescenta
    `ofertas_do_painel_conselho == []`.
  - `test_oferta_inativa_ignorada`: mantém `(1,1)` e acrescenta que o painel lista só a
    oferta ativa, com `concluida=True`.
  - O assert "aceita o objeto Turma" perdeu o objeto (função fora) — sem substituto: a
    entrada por objeto era conveniência do derivado removido, não regra de negócio.

## 3. Docstrings corrigidas (Passo 3)

- `app/services/conselho_leitura.py` — módulo passa a declarar o estado real:
  `turma_curso_id` NOT NULL desde a D5.5 (linha legada sem oferta não existe mais; a
  conferência prévia ficou registrada em `scripts/verificar_onda4_d5.py`); encerramento
  é da OFERTA; `Turma.conselho_concluido` foi REMOVIDA, a turma não tem coluna de
  conclusão e **não existe ponte**; `Turma.avaliacao_*` são LEGADO (§12.19).
- `app/relatorios/painel_pedagogico/conselho.py` — idem quanto ao NOT NULL da D5.5
  (a frase "até a resolução manual antes da D5.5" descrevia estado passado).
- `app/services/turma_curso.py:64-65` — resolvida pela remoção da função (item 1.b).
- `tests/test_d5_encerramento.py` — cabeçalho atualizado: a visão da turma é lida por
  `contar_ofertas_conselho()`/`ofertas_do_painel_conselho()`; "não existe ponte".

## 4. Ruff (Passo 4)

`ruff check app --select F821,F811,F841` → **All checks passed! (0 achados)**,
antes: 9. Nenhum comportamento alterado (vide coluna "Tratamento" em 1.c — onde havia
efeito colateral, a chamada foi mantida e só a vinculação à variável saiu).

## 5. Decisões

1. **Remover (não consumir) `turma_conselho_concluido()`** — o desenho D3b.1 admitia as
   duas rotas; o enunciado desta etapa manda remover quando (a) confirme ausência de
   leitor de produção, e (a) confirmou. Os leitores refazem o derivado por conta própria
   (`contar_ofertas_conselho`/painel/certificado) e não pedem a função.
2. **Chamadas com efeito colateral mantidas sem variável** (`Migrate(app, db)`,
   `get_unidade_id()`, `workbook.add_format(...)`) — critério "zero mudança de
   comportamento" do passo 1(c).
3. **Zero testes removidos** — reescrita de asserts em vez de remoção de funções de
   teste, preservando a contagem da suíte.

## 6. Pendências (não autorizadas nesta etapa)

- `app/models/MER.md` §7.7 (L435), §8.2 (L960-963) e §12.20 ainda descrevem
  `turma_conselho_concluido()` como o derivado oficial — **agora obsoletos pela remoção**;
  §12.20 pode ser encerrado como dívida paga. Documentação fora do escopo ("NÃO altere
  MER"): fica para a etapa de sincronização de docs (padrão L2).
- `backlog_desenvolvimento.md` (resíduos do conselho) e `docs/L3_relatorio.md` citam a
  função — mesma razão, não alterados.
- Os demais ~24 achados F401/E712/I001 pré-existentes em `app/` continuam fora do
  conjunto selecionado (`F821,F811,F841`) — fora do escopo.

## 7. Testes

Suíte completa com pytest (`.venv`): **359 passed, 0 failed** (66s), mesma contagem da
linha de chegada (D5.5: 359P) — **nenhum teste removido**; os 13 de
`test_d5_encerramento.py` permanecem, 4 deles com asserts de derivação reescritos sobre
`contar_ofertas_conselho()`/`ofertas_do_painel_conselho()`.

**Resumo pytest:** `359 passed, 83 warnings in 66.27s (0:01:06)`

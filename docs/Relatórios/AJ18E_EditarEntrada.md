# AJ18-E — Edição da data de entrada na oferta

**Branch:** `aj18-e-editar-entrada` (a partir de `nova_feature` @ `c5a257b`) · **Data:** 11/11/2026 · **Sem push** · Trabalho no repositório real `D:\pautaon`, com o `.venv` existente (sem worktree, sem cópia e sem venv novo).

**Escopo:** permitir corrigir `Inscricao.data_entrada_oferta` de um aluno **já enturmado**, sem desenturmar, para que entradas lançadas incorretamente como `NULL` (aluno que entrou atrasado) deixem de gerar pendências nas datas anteriores. **Sem migration** — a coluna `1fdc7c03bdc2` já existe. Enturmação, transferência, pauta impressa, BI, histórico, certificado e agregados não foram alterados.

**Commit de código/testes:** `894c042`.

---

## 1. Regra implementada

A correção reutiliza exatamente a interpretação e a validação da enturmação, centralizadas em `app/services/entrada_oferta.py`:

- `"inicio"`/`"desde_inicio"` → grava `NULL` (desde o início);
- `"hoje"` e `AAAA-MM-DD` passam por `parse_escolha_entrada`/`validar_entrada_na_vigencia` — data fora de `[início efetivo, fim efetivo]` é recusada com a mesma mensagem;
- oferta **ainda não iniciada** só aceita `NULL`: data específica (inclusive `"hoje"`) é recusada com `"A oferta ainda não iniciou: só é possível registrar "Desde o início"."`;
- escolha **igual** ao valor atual é **no-op**: não altera a coluna, não grava `LogAcao` e apenas informa que nada mudou;
- **avançar** a data (inclusive sair de `NULL`) quando já existem frequências do aluno na oferta com `data` anterior à nova entrada exige **confirmação explícita**;
- mover a data para trás ou para `NULL` **nunca** exige confirmação.

API do serviço:

```python
alterar_entrada(inscricao, escolha, hoje, *, confirmar=False) -> (anterior, nova)
contar_frequencias_anteriores(inscricao, entrada) -> int
EntradaComLinhasAnteriores(ValueError)  # carrega .quantidade
```

`alterar_entrada` **não commita**; a rota controla a transação. `contar_frequencias_anteriores` usa a mesma resolução D2 dos leitores: quando a oferta é a única ativa da turma, linhas com `turma_curso_id IS NULL` também contam como dela (`ofertas_unicas_ativas`). Nenhuma linha de `Frequencia` é apagada ou alterada (**D4**).

---

## 2. Rota POST

`POST /turma/<turma_id>/oferta/<oferta_id>/inscricao/<inscricao_id>/entrada` (`app/registros/turmas.py::alterar_entrada_aluno`), com CSRF:

| Situação | Resultado |
|---|---|
| perfil fora de admin/pedagógico/secretaria (ex.: professor, gerência) | **403** |
| unidade da turma diferente do contexto | **403** |
| inscrição inexistente, inativa ou de outra turma/oferta | **404** |
| oferta inexistente/inativa ou de outra turma | **404** |
| avanço com frequências anteriores e sem `confirmar=1` | **302** reabrindo o modal com a contagem |
| `ValueError` de vigência/oferta não iniciada | **302** com flash de aviso |
| sucesso | grava coluna + `LogAcao` no **mesmo commit** |

O `LogAcao` usa a ação `"Alteração da data de entrada na oferta"` (categoria `edicao` no filtro de auditoria) e `detalhes` no formato dos logs de enturmação:

```
aluno_id=<id> nome="<nome>" turma_id=<id> oferta_id=<id> entrada_anterior=<ISO|desde o início> entrada_nova=<ISO|desde o início>
```

Qualquer exceção inesperada faz `rollback` e é reenviada, de modo que a data e o log nunca divergem.

---

## 3. Interface (`turmas/detalhe.html`)

- Cada aluno da oferta passa a mostrar a entrada atual: `"Entrou em dd/mm/aaaa"` ou `"Desde o início"`.
- Botão **"Entrada"** por aluno, visível apenas para `admin`/`pedagogico`/`secretaria` e **somente com a oferta já iniciada** (`início efetivo <= hoje`).
- Um único `#modalEntrada` reutilizado, com o mesmo markup de escolha da enturmação (`hoje` / `Desde o início` / data específica), reutilizando `.entrada-celula`/`.entrada-radio`/`.entrada-date` e o JS de sincronização (o seletor foi generalizado de `#modalEnturmar .entrada-celula` para `.entrada-celula`).
- O botão carrega `data-*` com aluno, data atual, URL, inscrição e vigência da oferta; o JS preenche o modal.
- A **contagem de frequências anteriores é sempre calculada no servidor**: o POST recusa, redireciona com `modal=entrada&inscricao=...&entrada_escolha=...&entrada_pendentes=N` e a tela reabre o modal já com o aviso e o `checkbox` de confirmação renderizados. O POST é a única fonte da verdade.

---

## 4. Testes

`tests/test_aj18e_editar_entrada.py` — **16 testes** (SQLite, relógio congelado em `2026-10-29`):

1. `NULL → data` remove pendências por data (`situacao_datas_oferta` e contador do dashboard) e desabilita o aluno nas datas anteriores no lançamento;
2. voltar para `NULL` restaura as pendências;
3. data fora da vigência recusada, sem gravar nem auditar;
4. oferta não iniciada recusa `"hoje"` e data específica, aceitando só `NULL`;
5. no-op não grava e não audita;
6. frequência anterior exige confirmação, mostra a contagem, preserva as linhas e só então grava com log;
7. mover a data para trás não exige confirmação;
8. professor recebe 403;
9. outra unidade recebe 403;
10. inscrição inativa → 404;
11. oferta/turma divergentes → 404;
12. CSRF obrigatório (400 sem token);
13. atomicidade: falha ao gravar o log não altera a data;
14. botão visível só para admin/pedagógico/secretaria (não para professor/gerência);
15. botão ausente com oferta não iniciada;
16. lista sem N+1 (mesma contagem de consultas com 1 e 5 alunos).

**Regressões direcionadas:** `test_aj18b_entrada_oferta`, `test_aj18c1_entrada_backend`, `test_aj18c2_entrada_ui`, `test_enturmacao_oferta`, `test_transferencia_oferta`, `test_aj4_logs_drift` e `test_aj6b6_matriz_rotas_professor` — **145 passed**. Ruff (`F821,F811,F841,F401`) limpo nos arquivos tocados.

**Drift de logs:** o rótulo `"Alteração da data de entrada na oferta"` foi registrado em `ROTULOS_SEM_LINHA` (contagem 10 → 11) e em `CATEGORIA_ESPERADA` como `edicao`, seguindo o padrão de `"Enturmação de aluno na oferta"`.

**Snapshot:** `tests/snapshots/aj6b6_admin_registros_ver_turma.txt` regenerado após conferir que a diferença palavra a palavra se limita à nova região (linha "Desde o início" na célula do aluno, botão "Entrada", modal AJ18-E e bloco JS); nenhuma alteração fora dela.

---

## 5. Arquivos alterados

- `app/services/entrada_oferta.py` — `alterar_entrada`, `contar_frequencias_anteriores`, `EntradaComLinhasAnteriores`.
- `app/registros/turmas.py` — rota `alterar_entrada_aluno` e contexto de reabertura do modal em `ver_turma`.
- `app/templates/turmas/detalhe.html` — exibição da entrada, botão por aluno, modal e JS.
- `tests/test_aj18e_editar_entrada.py` — novos testes.
- `tests/test_aj4_logs_drift.py` — novo rótulo/categoria.
- `tests/snapshots/aj6b6_admin_registros_ver_turma.txt` — regenerado.
- `app/models/MER.md` — §7.15/§8.3 (edição, confirmação, preservação D4).
- `backlog_desenvolvimento.md` — entrada AJ18-E.

---

## 6. Pendências

- **Deploy:** o AJ18-E **não adiciona migration**; continua valendo o deploy conjunto do AJ18 com a revisão pendente `1fdc7c03bdc2` (produção em `f2a3b4c5d6e7`).
- **Decisão de produto:** agregados/relatórios e demais leitores (histórico, BI, certificados) continuam lendo as linhas gravadas sem filtro pela data de entrada (D4); nenhum deles foi alterado nesta rodada.
- **Teste manual:** corrigir a entrada de um aluno real para uma data posterior, conferir a remoção das pendências anteriores, o bloqueio no lançamento e a reabertura do modal com a contagem quando houver frequência anterior.

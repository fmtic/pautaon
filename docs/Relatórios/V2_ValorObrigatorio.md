# V2 — Valor/Postura do Esportista obrigatório para presença

**Branch:** `nova_feature` · **Head Alembic:** `c8d9e0f1a2b3` (inalterado — sem migration) · **Suíte:** 826 → **870 passed**, 0 falhas · **Sem push** · **Data:** 28/10/2026

**Commits da entrega**

| Commit | Conteúdo |
|---|---|
| `26c52e4` | Limpeza: fecha o card da pauta em `lancar.html` + `tests/test_lancar_template_estrutura.py` |
| `80f4fb6` | P2: caracterização do comportamento antigo (A–D sem valor salvava) |
| `dc3a2be` | Regra no servidor (`_planejar_frequencia`, `PendenciaValorEsportista`, rota) + inversão da caracterização + ajustes de teste |
| `9369449` | Cliente: `required`/bloqueio no `frequencia.js` + template + `tests/test_valor_obrigatorio_ui.py` |
| último | Docs (MER §7.19/§8.1, backlog) + este relatório |

---

## 1. P0/P1 — pré-condições e leitura (sem editar)

- **`git status` limpo** no início: o usuário já havia commitado a troca de rótulo ("Observações da Aula") em `2185afe`, que também **removeu `lancar copy.html`**. Nada pendente de terceiros.
- **Suíte base verde:** `826 passed` (188 s) antes de qualquer alteração.
- **Nomes confirmados** (nada divergiu do briefing): campo de conceito `aluno_<id>` (radios `btn-check`, valores A/B/C/D/F/J), campo do valor `postura_aluno_<id>`, resolução em `_resolver_valor_esportista(valor_raw, conceito, unidade_id, valor_atual_id)`, gravação em `salvar_frequencia(form)`, escopo do catálogo pela **unidade da turma** (`turma.unidade_id`, com fallback `get_unidade_id()`).
- **Erros hoje:** só `flash()` + `redirect` (não existe re-render com erro na rota). `salvar_frequencia` devolve `(0, None)` em qualquer exceção → a rota flasha "Preencha a data da aula antes de salvar.".
- **Aluno sem inscrição ativa:** não entra em `alunos_post` (join em `Inscricao` com `ativo=True` e `Aluno.ativo=True`); o `POST` dele é ignorado e, com oferta resolvida, as chaves `aluno_*`/`postura_aluno_*` fora da pauta da oferta são removidas antes de salvar (`core.py`).
- **TRAVA leve (declarada):** a mensagem de pendência usa **flash + redirect** (a mesma turma/data/oferta), e **não** re-renderização preservando o digitado. Re-renderizar exigiria extrair todo o bloco de contexto do `GET` (≈160 linhas) para um helper e remontar `frequencias`/`valores_por_aluno` a partir do form — mudança grande em rota crítica, com risco de regressão em ~40 testes de `GET /frequencia`. Efeito prático: o professor perde o que digitou naquela tentativa, mas recebe a lista exata de quem falta.

## 2. P1 — testes afetados pela regra (9, dentro do limite de 10)

Levantados rodando a suíte **depois** da regra e antes dos ajustes: 13 falhas = **9 testes antigos** + 4 testes de caracterização criados na P2 para serem invertidos.

| # | Arquivo::teste | Por que quebra |
|---|---|---|
| 1 | `test_valor_esportista_lancamento.py::test_sem_campo_de_valor_nao_apaga_conceito` | posta A sem valor e esperava `("A", None)` |
| 2 | `…::test_valor_de_outra_unidade_e_ignorado` | esperava conceito salvo + valor descartado |
| 3 | `…::test_valor_inativo_e_ignorado` | idem (inativo novo) |
| 4 | `…::test_valor_inexistente_nao_derruba_o_salvamento` | idem (id inexistente) |
| 5 | `…::test_estatisticas_nao_mudam_com_valor` | o 1º POST era A **sem** valor |
| 6 | `test_valor_esportista_nao_regressao.py::test_pauta_impressa_identica_com_e_sem_valor` | produzia o "sem valor" pelo caminho HTTP |
| 7 | `…::test_relatorio_de_frequencia_identico` | idem |
| 8 | `…::test_exportacao_xlsx_identica` | idem |
| 9 | `…::test_registro_antigo_sem_valor_carrega` | idem (B sem valor) |

**Testes em unidade sem catálogo ativo continuam passando sem ajuste** — é o efeito da exceção 2. Confirmado na suíte cheia: os `POST /frequencia` de `test_turma_curso_fase4.py`, `test_atividades_aula.py`, `test_frequencia_oferta.py`, `test_pauta_professor.py`, `test_diario_observacoes_acesso.py` etc. não criam catálogo e seguem verdes.

## 3. P2 — caracterização antigo × novo

`tests/test_valor_obrigatorio_caracterizacao.py`, criado em `80f4fb6` (verde contra o código antigo) e **invertido** em `dc3a2be`:

| Cenário | Antes (A1) | Agora (V2) |
|---|---|---|
| A/B/C/D sem valor, unidade com catálogo | salva o conceito, valor `NULL` | **recusa**, nenhuma linha |
| Valor inativo novo / inexistente / de outra unidade | descarta o valor e salva o conceito | **recusa**, nenhuma linha |

## 4. P3 — implementação

**Servidor (`app/utils/logica.py`)**

- `_planejar_frequencia(form, alunos, oferta_id, turma_id, data_alvo, unidade_id, exige_valor)` — fase de **leitura**: por aluno com conceito enviado resolve a linha existente e o `valor_id` via `_resolver_valor_esportista`; devolve `(plano, pendentes)`.
- `unidade_tem_valores_ativos(unidade_id)` — `EXISTS` de `valor_esportista.ativo` no escopo da unidade (sem unidade → catálogo global, mesmo escopo do seletor).
- `PendenciaValorEsportista` + `mensagem_valor_obrigatorio` — mensagem única (até 10 nomes + "e mais N").
- `salvar_frequencia` foi **reordenada**: parse → oferta → alunos → **validação** → `RegistroAula` → frequência → `commit`. O `except` genérico ganhou um ramo anterior que re-lança a pendência (senão ela viraria "Preencha a data…"). Nada é gravado antes da validação, e o `rollback` do ramo garante sessão limpa.

**Rota (`app/registros/core.py`)** — captura `PendenciaValorEsportista`, flasha a mensagem e volta para `turma_id`/`data`/`turma_curso`. O render do `GET` passa `pode_gerenciar_planejamento` (ADMIN/PEDAGOGICO/SECRETARIA — os mesmos perfis da rota `/planejamento`).

**Cliente** — `lancar.html`: `required` no select quando A–D (com catálogo na unidade), `data-valor-obrigatorio="1"` no form só nesse caso, aviso de cadastro para quem gerencia o planejamento e `#aviso-valor-pendente` oculto. `frequencia.js`: funções puras exportadas para node, `tratarConceitoAluno` aplicando/removendo `required`, `validarPendencias` no submit (`is-invalid` + mensagem + foco) e tratamento do evento `invalid` do `required` nativo.

**Sem migration.** A coluna continua nullable: registros antigos e lançamentos anteriores à V2 permanecem `NULL`.

## 5. P4 — testes (antigo × novo × motivo)

Ajustes nos 9 testes listados:

| Teste | Antigo | Novo | Motivo |
|---|---|---|---|
| `test_sem_campo_de_valor_nao_apaga_conceito` → **`test_a_d_sem_valor_vira_pendencia`** | `assert _valor_gravado == ("A", None)` | `_linha is None` + mensagem na pauta | o comportamento invertido é o objetivo da V2 |
| `test_valor_de_outra_unidade_e_ignorado` → **`…_vira_pendencia`** | conceito salvo, valor `None` | nada gravado + mensagem | regra 3: externo = ausente |
| `test_valor_inativo_e_ignorado` → **`test_valor_inativo_novo_vira_pendencia`** | idem | idem | regra 3: inativo não salvo = ausente |
| `test_valor_inexistente_nao_derruba_o_salvamento` → **`…_vira_pendencia_sem_derrubar`** | `("A", None)` | 302 (não 500) + nada gravado | id inexistente é pendência, não erro |
| `test_estatisticas_nao_mudam_com_valor` (nome mantido) | POST A sem valor → POST A com valor | POST A com **Alegria** → POST A com **Disciplina** (2º valor ativo criado no teste) | não existe mais "A sem valor" pelo HTTP; a intenção (P/F/J não dependem do valor) é preservada |
| `test_pauta_impressa_identica_com_e_sem_valor` | salva sem valor, captura, salva com valor, compara | salva **com** valor, captura, **anula a coluna direto no banco** (`_anular_valor`), compara | simula o registro antigo sem passar pela regra |
| `test_relatorio_de_frequencia_identico` | idem | idem (+ consome o flash de sucesso antes de comparar) | o flash "Frequência salva!" diferenciava o HTML |
| `test_exportacao_xlsx_identica` | idem | idem | idem |
| `test_registro_antigo_sem_valor_carrega` | salvava B sem valor | salva B com valor e anula no banco | idem |

**Testes novos** (44 no total): `test_valor_obrigatorio.py` (26), `test_valor_obrigatorio_ui.py` (12), `test_valor_obrigatorio_caracterizacao.py` (4), `test_lancar_template_estrutura.py` (2).

Cobertura por requisito da P4:

| Requisito | Teste |
|---|---|
| A–D sem valor recusa e NADA grava (conceitos, valores e diário; contagem igual) | `test_presenca_sem_valor_recusa_e_nao_grava_nada` (A, B, C, D) — compara `(frequencia, registro_aula)` antes/depois |
| Com valor grava | `test_presenca_com_valor_grava_conceito_valor_e_diario` (A–D) |
| F/J ok e limpa valor | `test_falta_e_justificada_sem_valor_salvam_e_limpam` (F, J) |
| Sem conceito ok | `test_aluno_sem_conceito_nao_cria_linha`, `test_sem_conceito_preserva_linha_e_valor_existentes` |
| Unidade sem valores ativos isenta | `test_unidade_sem_valores_ativos_isenta_a_regra` (A–D) |
| Aviso só para perfil de planejamento | `test_aviso_de_cadastro_so_para_quem_gerencia_planejamento` |
| Valor inativo já salvo aceito; inativo novo/inexistente/outra unidade = pendência | `test_valor_inativo_ja_salvo_continua_valendo`, `test_valor_sem_validade_e_pendencia[3 casos]` |
| Mensagem lista alunos + truncamento | `test_mensagem_lista_os_alunos_pendentes`, `test_mensagem_trunca_acima_de_dez_alunos` (12 alunos → 10 nomes + "e mais 2") |
| 2 ofertas: valida só a pauta do formulário | `test_duas_ofertas_valida_so_alunos_da_oferta_do_formulario`, `test_duas_ofertas_pendencia_na_oferta_do_formulario` |
| Estatísticas e pauta impressa idênticas | `test_estatisticas_e_pauta_impressa_nao_dependem_do_valor` + os 3 de não regressão ajustados |
| Secretaria 403 | `test_secretaria_continua_recebendo_403` |
| HTML: `required` em A–D, sem `required` nos demais, estado inicial ao reabrir | `test_select_exige_valor_quando_ha_presenca_salva`, `test_select_sem_conceito_fica_desabilitado_e_sem_required`, `test_select_desabilitado_em_falta_e_justificada[F, J]`, `test_sem_required_quando_unidade_nao_tem_catalogo` |

## 6. P5 — ensaio (`pautaon_ensaio`)

Alvo mascarado impresso e conferido antes de qualquer escrita: `postgresql+psycopg://postgres:***@localhost:5432/pautaon_ensaio`, `alembic_version = c8d9e0f1a2b3`. O script `scripts/ensaio_shell.ps1` foi usado em `-Diagnostico` para atestar alvo/revisão; a execução em si rodou em processo próprio com a mesma DSN derivada do `.env` (o script abre um shell **interativo**, não é scriptável, e alterá-lo estava fora do escopo).

Cenário real: turma 10 ("Informática", unidade 2), oferta 14, aluno 1448, data 2026-10-28 (sem lançamento). O scratch do M1 **não tinha** catálogo ativo na unidade — o valor `Ensaio V2` foi criado pela própria rota `POST /planejamento` e removido no fim.

```
alembic_version = c8d9e0f1a2b3
POST /planejamento (cria catalogo) = 302   → valor criado: 1
POST A SEM valor   → 302 | linhas antes=(18, 4) depois=(18, 4) → atomico=True
                     mensagem de pendencia na pauta = True
POST A COM valor   → 302 | linhas antes=(18, 4) depois=(19, 5) | linha gravada = (A, 1)
limpeza: linhas finais = (18, 4) (esperado = (18, 4)) | catalogo desfeito = 1
```

Banco principal **não foi tocado** (nenhuma conexão).

## 7. Casos limite e decisões

- **Aluno sem conceito NÃO limpa o valor:** a coluna é preservada junto com a linha (contrato da A1: `select` desabilitado não envia campo). O briefing diz "F, J e sem conceito não exigem (e continuam limpando o valor)" — interpretado como "F/J continuam limpando"; apagar a linha de quem nem foi enviado seria perda de histórico. Documentado aqui e em MER §8.1.
- **Unidade com catálogo só inativo** conta como "sem valores ativos" → isenta (o professor não teria opção para escolher).
- **Turma sem unidade** (`unidade_id IS NULL`) usa o catálogo global, o mesmo escopo do seletor da pauta.
- **Regra vale em qualquer data**, inclusive reescrita de lançamento antigo (sem exceção por data). Registros históricos `NULL` que **não** são reescritos continuam intactos e continuam aparecendo na pauta/relatórios.
- **A pendência é por oferta:** as chaves de alunos fora da pauta da oferta são removidas na rota antes da validação, então só a pauta do formulário é cobrada.

## 8. Desvios em relação ao pedido

1. **Re-render preservando o digitado:** não feito — usado flash + redirect (TRAVA leve autorizada, motivo no §1).
2. **`git rm "lancar copy.html"`:** não executado porque o arquivo **já não existia** (removido pelo usuário em `2185afe`); a confirmação por grep (zero referências em `app/`, `tests/`, `scripts/`) foi registrada.
3. **`scripts/ensaio_shell.ps1`:** usado em modo diagnóstico, não como shell interativo (ver §6); não foi modificado por estar fora do escopo declarado.
4. **Tamanho dos commits:** a flag `pode_gerenciar_planejamento` entrou junto do commit do servidor (`dc3a2be`) porque está no mesmo arquivo (`core.py`) das demais mudanças da rota; o template que a consome veio no commit do cliente.

## 9. Validação final

- `pytest -q` → **870 passed**, 0 falhas (826 + 44).
- `ruff check --select F821,F811 app tests migrations scripts` → limpo.
- `git diff --check` → limpo.
- Sem push.

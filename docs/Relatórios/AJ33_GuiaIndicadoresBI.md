# AJ33 — Guia de Indicadores da Central de BI

**Data:** 27/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma · **Push/merge/deploy:** não realizados · **Versão do catálogo:** 1.1 · **Última revisão:** 2026-11-27

## 1. Objetivo e garantias

Eliminar indicadores redundantes da Central de BI sem mexer em nenhum número, fórmula, consulta, filtro ou regra de negócio, e entregar um Guia de Indicadores legível, auditável e imprimível.

Garantias verificadas:

- Os **61 códigos originais** continuam no catálogo. Nenhum foi apagado ou reutilizado.
- Nenhuma função de execução, consulta SQL, filtro aceito ou retorno foi alterado. Mudanças foram apenas de **metadados, visibilidade, resolução de alias, interface, testes e documentação**.
- Os quatro pares idênticos foram **provados empiricamente** com os mesmos dados e nove cenários de filtro antes de virar alias.
- Indicadores parecidos com base diferente **não foram removidos**; seus nomes/descrições foram esclarecidos e os casos discutíveis ficaram listados para decisão.
- O Guia usa o catálogo como **fonte única**; não há SQL nem identificador de tarefa no texto exibido ao usuário.

## 2. Descoberta (somente leitura)

| Fonte | O que foi mapeado |
|---|---|
| `app/relatorios/catalogo.py` | 61 códigos, 8 categorias, nome, tipo, unidade, fonte e dimensões de cada indicador. |
| `app/relatorios/bi.py` | Função executada por código; assinatura que define quais filtros cada indicador realmente aceita. |
| `app/relatorios/bi_routes.py` | Central (`/relatorios/bi`), API (`/indicador/<codigo>`), XLSX, gráfico e impressão; `ROLES_RELATORIOS` e isolamento por unidade. |
| `app/templates/relatorios/bi.html` | Antes: a lista percorria todo o catálogo, incluindo duplicados e indisponíveis. Depois: usa `indicadores_visiveis_na_central()` e linka o guia. |
| `docs/Relatórios/AJ12_AuditoriaBI.md` | Duplicatas, nomes enganosos, invariantes numéricos e pegadinhas já conhecidas. |
| `app/relatorios/indicadores.md` | Inventário e descrições antigas, atualizadas sem tocar em cálculo. |

Distribuição atual: **22** indicadores em `alunos`, **11** em `frequencia`, **8** em `inscricoes`, **8** em `turmas`, **8** em `aulas`, **2** em `conselho`, **1** em `atendimento` e **1** em `matriculas`. Por tipo: **30** contagens, **28** distribuições e **3** médias. A Central passou a oferecer **55** códigos; os outros **6** continuam no catálogo, mas ocultos da lista.

### Filtros

Os três controles visíveis da Central seguem sendo **Período Letivo**, **Unidade** e **Turno**. Curso, turma, professor e `data_inicio` continuam aceitos pela API/exportação conforme a assinatura de cada função, sem controle visível novo.

## 3. Matriz de redundância — todos os 61 códigos

Legenda: **A** = alias idêntico provado (oculto); **B** = nome/base parecida, porém medida diferente (mantido); **C** = nome enganoso ajustado (mantido); **D** = canônico (visível); **E** = indisponível (oculto); **F** = sem sobreposição identificada (mantido).

| Código | Nome atual no catálogo | Classe | Critério / razão | Destino |
|---|---|:---:|---|---|
| ALU-001 | Alunos ativos no período (enturmados + não enturmados) | C | O nome antigo dizia "cadastro ativo no período"; a soma é ALU-011 + ALU-012. | Mantido, renomeado |
| ALU-002 | Alunos com cadastro ativo (base cadastral) | C | Base cadastral; não mede enturmação e não equivale a ALU-001/ALU-011. | Mantido, renomeado |
| ALU-003 | Alunos com cadastro inativo | B | Cadastro inativo não é inscrição inativa (INS-003). | Mantido |
| ALU-004 | Cadastros novos no intervalo (data de criação) | C | `Aluno.created_at`; não é "aluno novo no período" (ALU-013). | Mantido, renomeado |
| ALU-005 | Alunos enturmados por sexo | B | Distribuição de ALU-011 por sexo; não é novo total. | Mantido |
| ALU-006 | Alunos enturmados por faixa etária | B | Distribuição de ALU-011 por faixa etária. | Mantido |
| ALU-007 | Alunos PCD enturmados no período (base P) | C | Base restrita a enturmados; não comparável com DIV-001. | Mantido, renomeado |
| ALU-008 | Alunos cadastrados por unidade | B | Não filtra cadastro ativo; não equivale a ALU-002. | Mantido |
| ALU-009 | Alunos enturmados por curso | B | Distribuição por oferta; a soma pode passar do total de alunos distintos. | Mantido |
| ALU-010 | Alunos enturmados por turma | D | Canônico da distribuição por turma; TUR-003 é o mesmo código. | Mantido, visível |
| ALU-011 | Alunos enturmados no período (status P) | C | Status P; exclui não enturmados e não é o total ALU-001. | Mantido, renomeado |
| ALU-012 | Alunos não enturmados no período | B | Complemento de ALU-011; "Outros" é resíduo, não inscrição. | Mantido |
| ALU-013 | Alunos novos no período (sem histórico na unidade) | C | Sem inscrição em período anterior da mesma unidade; não é ALU-004. | Mantido, renomeado |
| ALU-014 | Alunos renovados | B | Igual a ALU-018 na base pequena de teste, mas regra é outra. | Mantido; decisão registrada: mantido |
| ALU-015 | Alunos retornantes | F | Situação própria do classificador. | Mantido |
| ALU-016 | Alunos não renovados | F | Situação própria, dentro dos não enturmados. | Mantido |
| ALU-017 | Alunos em janela de renovação | F | Situação própria, dentro dos não enturmados. | Mantido |
| ALU-018 | Alunos desenturmados | B | Pode coincidir com ALU-014 em base pequena; regra distinta. | Mantido; decisão registrada: mantido |
| INS-001 | Total de inscrições | D | Canônico; INS-004 executa a mesma consulta, inclusive com intervalo de datas. | Mantido, visível |
| INS-002 | Inscrições ativas | B | Subconjunto de INS-001; distinto de INS-003. | Mantido |
| INS-003 | Inscrições encerradas | D | Canônico; INS-005 conta exatamente a mesma condição. | Mantido, visível |
| INS-004 | Inscrições no intervalo (código legado de INS-001) | A | Prova: 9/9 cenários iguais a INS-001. | Oculto; alias de INS-001 na API/XLSX |
| INS-005 | Inscrições inativas (código legado de INS-003) | A | Prova: 9/9 cenários iguais a INS-003. | Oculto; alias de INS-003 na API/XLSX |
| INS-006 | Motivos de desativação | E | Sem dado de motivo no banco; chamada direta responde não implementado. | Oculto, catalogado |
| INS-007 | Tempo médio de permanência | E | Sem implementação; chamada direta responde não implementado. | Oculto, catalogado |
| INS-008 | Inscrições por curso | B | Distribuição por curso; pode não fechar com INS-001 quando falta oferta. | Mantido; decisão registrada: mantido |
| FRE-001 | Total de lançamentos de frequência | F | Conta linhas lançadas; não é aluno nem dia. | Mantido |
| FRE-002 | Total de presenças | B | Subconjunto das linhas de FRE-001; faltas justificadas ficam fora. | Mantido |
| FRE-003 | Total de faltas | B | Linhas de falta; distinto de FRE-004. | Mantido |
| FRE-004 | Total de faltas justificadas | B | Parte das faltas, fora do cálculo das taxas. | Mantido |
| FRE-005 | Frequência média ponderada por lançamentos | C | Taxa global por linha, não média das porcentagens por aluno. | Mantido, renomeado |
| FRE-006 | Alunos com frequência igual ou superior a 90% | B | Faixa alta após arredondamento a 1 casa. | Mantido |
| FRE-007 | Alunos com frequência entre 75% e 89% | B | Faixa média; 89,95 arredonda e muda de faixa. | Mantido |
| FRE-008 | Alunos com frequência inferior a 75% | B | Faixa baixa; base da CRU-001. | Mantido |
| FRE-009 | Frequência por turma | B | Mesmo tipo de taxa, agregada por turma. | Mantido |
| FRE-010 | Frequência por curso | B | Taxa por curso com regra D2 para linhas legadas. | Mantido |
| TUR-001 | Turmas ativas (código legado de TUR-002) | A | Prova: 9/9 cenários iguais a TUR-002; nome antigo "total" era enganoso. | Oculto; alias de TUR-002 na API/XLSX |
| TUR-002 | Turmas ativas | D | Canônico; nunca contou inativas. | Mantido, visível |
| TUR-003 | Alunos por turma (código legado de ALU-010) | A | Prova: 9/9 cenários iguais a ALU-010, mesma função. | Oculto; alias de ALU-010 na API/XLSX |
| TUR-004 | Média de inscrições vigentes por turma (não alunos distintos) | C | Conta inscrições, não pessoas; não exige cadastro ativo. | Mantido, renomeado; decisão registrada: mantido |
| TUR-005 | Turmas por curso | B | Distribuição por oferta ativa; turma sem oferta fica de fora. | Mantido |
| TUR-006 | Turmas por período | B | Distribuição de TUR-002 por período. | Mantido |
| TUR-007 | Turmas por unidade | B | Distribuição de TUR-002 por unidade. | Mantido |
| TUR-008 | Turmas por professor | B | Distribuição por oferta ativa, não pelo campo legado da turma. | Mantido |
| AUL-001 | Total de aulas registradas | F | Conta registros de aula; unidade é aula, não dia. | Mantido |
| AUL-002 | Aulas por turma | B | Distribuição de AUL-001 por turma. | Mantido |
| AUL-003 | Aulas por período | B | Distribuição de AUL-001 por período. | Mantido |
| AUL-004 | Aulas por professor | B | Distribuição de AUL-001 por professor. | Mantido |
| AUL-005 | Aulas por curso | B | Distribuição por curso com regra D2. | Mantido |
| AUL-006 | Aulas por unidade | B | Distribuição por unidade; filtro de período da Central não é repassado. | Mantido |
| AUL-007 | Aulas por tema | B | Relação N:N; a soma por tema pode passar de AUL-001. | Mantido; decisão registrada: mantido |
| AUL-008 | Aulas por dia | B | Conta registros por data, não dias com aula. | Mantido |
| SOC-001 | Alunos por faixa de renda familiar | F | Base socioeconômica própria. | Mantido |
| SOC-002 | Alunos beneficiários de programas sociais | F | Marcador distinto da faixa de renda. | Mantido |
| DIV-001 | Alunos com perfil PCD por tipo (todos os cadastros) | C | Perfil completo; um aluno pode entrar em vários tipos. Não é ALU-007. | Mantido, renomeado; decisão registrada: mantido |
| ATD-001 | Total de atendimentos | F | Sem indicador próximo no catálogo. | Mantido |
| CRU-001 | Frequência crítica (< 75%) por vulnerabilidade social | B | Usa a faixa de FRE-008, mas cruza com vulnerabilidade. | Mantido |
| CRU-002 | Alunos por raça/cor no Conselho de Classe | B | Conselho por raça/cor; CRU-005 é por renda. | Mantido |
| CRU-003 | Alunos sem acesso à internet por bairro e zona | B | Marca explícita de sem acesso; não é faixa de renda. | Mantido |
| CRU-004 | Transferências por curso de origem | B | Curso da turma de origem, não da oferta atual. | Mantido |
| CRU-005 | Desempenho no Conselho de Classe por faixa de renda | B | Conselho por renda; só com situação final preenchida. | Mantido |

### Decisão registrada em 27/11/2026 — itens parecidos mantidos

Nenhum foi removido nem teve cálculo alterado. Todos os pares abaixo foram **mantidos** porque as regras são distintas; a diferenciação está no nome e no texto do guia:

- **ALU-014 × ALU-018** — valores iguais na base de teste, regras diferentes (renovado × desenturmado).
- **INS-008 × INS-001** — soma igual em certa base, mas um é distribuição por curso e o outro é total; registros sem oferta podem divergir.
- **TUR-004 × ALU-010** — média de inscrições × contagem de alunos distintos com cadastro ativo.
- **DIV-001 × ALU-007** — perfis PCD completos × somente enturmados; um aluno pode aparecer em mais de um tipo em DIV-001.
- **FRE-005 × média por aluno** — a taxa atual pondera por lançamento; não foi trocada por média aritmética de percentuais.
- **AUL-007 × AUL-001** — soma por tema pode exceder o total por causa da relação N:N.
- **CRU-002 × CRU-005** — mesmos registros de Conselho, dimensões diferentes (raça/cor × renda), com regras próprias de preenchimento.

## 4. Prova de equivalência dos aliases

Base de teste: 2 unidades, 2 períodos por unidade, 4 turmas, 2 cursos, 1 professor, 5 alunos e 6 inscrições com combinações de `ativo`, unidade, turno, curso, turma e professor. Para cada par, os dois códigos foram executados na **mesma base** com os **mesmos filtros aceitos pela assinatura da função**.

Cenários aplicados (quando aceitos pelo indicador): sem filtro; unidade; período atual; turno; curso; turma; professor; unidade + período; e `data_inicio` relativo.

| Canônico | Alias | Resultados nos 9 cenários (sequência) | Igualdade |
|---|---|---|---|
| INS-001 | INS-004 | 6, 5, 4, 6, 1, 4, 6, 4, 6 | 9/9 |
| INS-003 | INS-005 | 2, 2, 1, 2, 1, 1, 2, 1, 2 | 9/9 |
| TUR-002 | TUR-001 | 4, 2, 1, 4, 0, 1, 0, 1, 0 | 9/9 |
| ALU-010 | TUR-003 | 2, 1, 1, 2, 0, 1, 2, 1, 2 turmas na distribuição; mesmos ids, nomes e valores | 9/9 |

Regressões numéricas fixadas na suíte: `INS-003 = 2`, `TUR-002 = 2` e `ALU-010` com distribuição não vazia para a unidade semeada. O detalhe de cada cenário, incluindo os filtros efetivamente aceitos, está em `docs/Relatórios/aj33_evidencias/equivalencia.json`.

## 5. Mudanças entregues

| Arquivo | Mudança |
|---|---|
| `app/relatorios/catalogo.py` | `ALIASES`, `INDICADORES_INDISPONIVEIS`, `CODIGOS_OCULTOS_DA_CENTRAL`, `resolver_codigo()`, `eh_alias()`, `indicadores_visiveis_na_central()`, filtros/Glossário/`GUIA_METADADOS`, validação e projeção do guia. Versão 1.1 e revisão 2026-11-27. Nomes de 13 indicadores esclarecidos, sem tocar em consulta. |
| `app/relatorios/bi.py` | `executar_indicador()` resolve alias antes de chamar a função canônica. |
| `app/relatorios/bi_routes.py` | Central lista só códigos visíveis; nova rota `/relatorios/bi/indicadores` com o mesmo `@login_required` e `ROLES_RELATORIOS`; API, XLSX e gráfico resolvem alias. |
| `app/templates/relatorios/bi.html` | Link "Guia de indicadores" no cabeçalho e "Como é calculado" no card de informações/resultado, apontando para `#<código>`. |
| `app/templates/relatorios/guia_indicadores.html` | Guia gerado do catálogo: capa de impressão, glossário, índice, busca, seções recolhíveis e detalhes técnicos. |
| `app/static/css/relatorios/guia_indicadores.css` | Layout responsivo, `@page` único A4, `#conteudo-impressao`, `.print-only`, `d-print-none` e `break-inside: avoid`. |
| `app/static/js/relatorios/guia_indicadores.js` | Busca client-side, expandir/recolher, abertura por âncora e `hashchange`. |
| `tests/test_aj33_guia_indicadores.py` | 9 testes: integridade, metadados, equivalência, API/XLSX, Central, acesso por perfil, conteúdo/âncoras/busca e impressão. |
| `tests/test_bi_indicadores.py` | Comentário sobre INS-006/INS-007 passar a seguir a seleção centralizada de visibilidade. |
| `app/relatorios/indicadores.md`, `backlog_desenvolvimento.md`, `app/models/MER.md`, este relatório | Documentação atualizada. MER registra apenas que metadados do catálogo não criam esquema nem migration. |

API e XLSX continuam devolvendo o **código solicitado** no payload/cabeçalho (`"indicador": alias`, `Código: alias`); apenas a resolução interna usa o canônico. Assim, nenhum integrate existente que já chama um código legado foi quebrado.

## 6. Guia de Indicadores

- Rota: **`/relatorios/bi/indicadores`**, com o mesmo controle de acesso e escopo da Central (admin/pedagogico liberados; professor e anônimo negados/redirecionados).
- Conteúdo por indicador: código, nome, categoria, o que mede, como é calculado sem SQL, unidade, tipo, filtros aplicáveis e não aplicáveis, pegadinhas do glossário, relacionados com âncora e detalhes técnicos.
- Alias aparece como **"Substituído por <canônico>"**; indisponíveis aparecem com o rótulo **"Indisponível"**. Ambos continuam no guia para auditoria.
- Interface: busca local por código/nome/categoria/filtro/explicação, índice por categoria, recolhíveis, "expandir tudo", "recolher tudo" e abertura direta por `#CODIGO`.
- Impressão: um único `@page` A4 retrato, capa `.print-only`, controles `.d-print-none`, painéis abertos no papel e blocos protegidos contra quebra no meio. Nome padrão via `data-pdf-nome="Guia de Indicadores - pautaON - {data}"` e `impressao_pdf.js`.

## 7. Evidências

Evidências reais geradas em **Chromium/Playwright** em `docs/Relatórios/aj33_evidencias/` (pasta ignorada pelo Git):

| Arquivo | Evidência |
|---|---|
| `central_desktop.png` | Central sem os seis códigos ocultos e com link do guia. |
| `central_resultado_como_calculado.png` | Resultado de ALU-010 com link `/relatorios/bi/indicadores#ALU-010`. |
| `guia_desktop_topo.png` | Topo do guia com versão/revisão e glossário. |
| `guia_busca.png` | Busca por ALU-010 filtrando 4 indicadores. |
| `guia_expandido.png` | 61 seções abertas por "Expandir tudo". |
| `guia_ancora.png` | Âncora `#ALU-010` abrindo o painel correspondente. |
| `guia_mobile.png` | Celular 390×844 sem rolagem horizontal (`scrollWidth = innerWidth = 390`). |
| `guia_impressao.png` | Prévia em mídia de impressão sem controles visíveis. |
| `Guia_de_Indicadores.pdf` | PDF A4 com 33 páginas; título na capa; nenhum controle de tela no texto; 61 códigos com "O que mede" e "Como é calculado" na mesma página. |
| `equivalencia.json` | 36 execuções (4 pares × 9 cenários), todas com `igual: true`. |
| `evidencias.json` | 16 verificações automatizadas de navegação, busca, âncora, PDF e celular, todas `ok: true`. |
| `estado_sessao.json` | Estado da sessão usado na reprodução. |

Nome de arquivo observado no navegador: `Guia-de-Indicadores-pautaON-2026-11-27`, com restauração do título original após `afterprint`.

## 8. Testes

| Comando | Resultado |
|---|---|
| `python -m pytest -q -p no:cacheprovider tests/test_aj33_guia_indicadores.py` | 9 passed |
| `python -m pytest -q -p no:cacheprovider tests/test_bi_indicadores.py tests/test_bi_oferta.py tests/test_bi_turma_desativada.py tests/test_a1_bi_turma_ativa.py tests/test_aj1_servico_social_relatorios.py tests/test_aj29_nome_pdf.py tests/test_aj29_nome_pdf_js.py tests/test_aj31_informacoes_gerais_periodo.py` | 94 passed |
| `python -m pytest -q -p no:cacheprovider` | 2085 passed, 1275 warnings em 2177,63 s (36 min 17 s) |

A suíte específica também falharia se faltasse descrição, fórmula ou unidade de qualquer indicador, se aparecesse identificador de tarefa no texto do guia, ou se um alias deixasse de resolver na API/XLSX.

## 9. Pendências futuras registradas em 27/11/2026

- **TUR-004:** passar a contar **aluno distinto** por turma; hoje conta inscrições vigentes. Nenhuma mudança de cálculo foi feita nesta entrega.
- **Central de BI:** avisar **"filtro não aplicado a este indicador"** quando um filtro visível for ignorado. Exemplos: AUL-006 ignora período; ALU-009 usa o turno apenas para selecionar a coorte e não restringe a distribuição por curso. O guia já explica essas limitações; o aviso na Central ficou para o próximo ciclo.
- **Novo indicador:** avaliar uma medida explícita de **"inscrições com início no período"**. `INS-004` continua apenas como alias de `INS-001` e não pode ser reutilizado para essa nova semântica.

## 10. Conclusão

Os duplicados idênticos saíram da lista da Central, mas permanecem como aliases explícitos e auditáveis; os demais indicadores foram diferenciados por nome/descrição e oficialmente mantidos por decisão de 27/11/2026, sem mudança de cálculo. O Guia de Indicadores passa a ser a referência única de leitura, com a mesma permissão da Central, busca, âncoras, celular e impressão padronizada. As pendências futuras ficaram registradas para o próximo ciclo. Nenhum commit, push ou deploy foi realizado.

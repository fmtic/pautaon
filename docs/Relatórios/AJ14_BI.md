# AJ14 — Correções mínimas do BI

## Ambiente e baseline

- Worktree: `D:\pautaon-aj14`, branch `aj14-bi`; sem push.
- Ambiente virtual novo: `.venv`, Python 3.14.7.
- `requirements.txt` e `requirements-dev.txt` foram instalados com sucesso.
- Versão de Python da produção: desconhecida. Não foi possível confirmar se `pip install -r requirements.txt` funciona nessa versão.
- `pip freeze` (pacotes principais): Flask 3.1.3, Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.0.48, Werkzeug 3.1.9, Pillow 13.0.0, psycopg 3.3.6, pytest 9.0.3, pytest-timeout 2.4.0 e Ruff 0.17.1.
- Suíte completa antes de qualquer alteração: **1.635 passaram, 2 falharam, 1 ignorado**, 956 warnings.

As duas falhas iniciais foram `test_anexo_pdf_valido_usa_uuid_e_download_protegido` e `test_modelo_png_valido_usa_uuid_headers_e_download`. Elas comparavam o `FileStorage.filename` recebido literalmente com um caminho fornecido no multipart. No ambiente Windows, o valor recebido foi normalizado pelo stack de upload (`....anexo.pdf` / `....modelo.png`), portanto não correspondia à string de entrada. O caminho persistido continuou usando UUID e o download protegido funcionava. A correção foi tornar a asserção do nome independente da forma do caminho, sem relaxar as verificações de UUID, conteúdo ou proteção do download; não foi necessária mudança no código de upload.

O único skip é justificado: `tests/test_aj5c_form_rerender.py::test_nada_gravado_no_disco_na_falha` requer a pasta de uploads e explicitamente pula quando ela não existe; a pasta não foi criada no ambiente de testes.

## Correções e regressões

- **INS-006/INS-007:** removidos da lista servida à Central enquanto não implementados. A chamada direta continua retornando o erro que já retornava.
- **TUR-008:** agrupamento por professor da oferta ativa (`TurmaCurso.professor_id`), contando cada turma uma vez por professor.
- **TUR-005:** agrupamento por curso da oferta ativa (`TurmaCurso.curso_id`), contando cada turma uma vez por curso.
- **CRU-002:** conta somente alunos com ao menos uma `ConselhoResposta` preenchida na turma/período.
- **CRU-005:** considera somente `ConselhoClasse` com `situacao_final` não nula.

Foram adicionados testes de regressão que exercitam cada código individualmente, incluindo ofertas múltiplas com professores/cursos distintos e conselho com registro-base sem resposta preenchida. Os testes dos indicadores passaram (**35 passed**) e os testes AJ5-D passaram (**24 passed**).

Na primeira suíte completa após a implementação, um teste de caracterização D5 falhou porque seu cenário CRU-002 criava conselhos sem nenhuma resposta preenchida. O cenário foi atualizado para semear uma resposta preenchida, preservando o objetivo do teste e a regra de CRU-002. Uma repetição posterior falhou apenas porque a chave de teste temporária tinha menos de 32 caracteres; a execução final usou uma chave de teste válida, sem novas alterações de código.

## Valores no clone restaurado

Contagens obtidas com `executar_indicador` antes e depois das alterações. Os valores foram idênticos; os arrays representam somente contagens e não contêm dados pessoais.

| Indicador | Antes | Depois |
|---|---:|---:|
| INS-006 | `ValueError` | `ValueError` |
| INS-007 | `ValueError` | `ValueError` |
| TUR-005 | `[3, 1, 3, 1, 3, 1]` | `[3, 1, 3, 1, 3, 1]` |
| TUR-008 | `[3, 1, 1, 1, 2, 4]` | `[3, 1, 1, 1, 2, 4]` |
| CRU-002 | `[]` | `[]` |
| CRU-005 | `[0, 0, 0, 0]` | `[0, 0, 0, 0]` |

O clone local foi restaurado do dump solicitado e atualizado até `c1d2e3f4a5b6` antes da coleta. Nenhuma migration foi criada ou aplicada ao repositório. O banco clone `pautaon_aj14_20261105` foi removido com `DROP DATABASE` e sua ausência foi confirmada; o cluster PostgreSQL temporário dedicado também foi parado e removido.

## Validações finais

- Suíte completa após as alterações: **1.643 passed, 1 skipped**, 956 warnings, em 913,66 s.
- Ruff (`F821,F811,F841,F401`): **62 achados preexistentes** no repositório; nenhum nos arquivos alterados.
- `git diff --check`: sem erros.

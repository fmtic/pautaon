# AJ16-C — Lista de Deploy

**Data:** 09/11/2026
**Tag implantada:** `release-2026-11-05` (commit `0e14fef`)
**HEAD da nova_feature:** `ed21a6b` (após merge do AJ16-B)
**Migration nova:** `f2a3b4c5d6e7` (depois de `c1d2e3f4a5b6`)

---

## 1. Arquivos para COPIAR (A/M)

```
app/models/aulas.py                                  M
app/models/__init__.py                               M
app/models/MER.md                                    M
app/models/pedagogico.py                             M
app/registros/core.py                                M
app/services/engajamento_turma.py                    M
app/static/js/frequencia.js                          M
app/templates/dashboard/painel_pedagogico.html        M
app/templates/frequencia/lancar.html                 M
app/utils/logica.py                                  M
backlog_desenvolvimento.md                           M
docs/Relatórios/AJ16B_ValorAula.md                   A
migrations/versions/f2a3b4c5d6e7_valor_esportista_na_aula.py  A
tests/_valor_aula.py                                 A
tests/snapshots/aj6b6_secretaria_registros_frequencia.txt  M
tests/test_d3b2_4_estatisticas.py                    M
tests/test_f1_autor_lancamento.py                    M
tests/test_lancar_template_estrutura.py              M
tests/test_v3a_datas_lancadas.py                      M
tests/test_v3b_engajamento_turma.py                  M
tests/test_valor_esportista_lancamento.py            M
tests/test_valor_esportista_migration.py             M
tests/test_valor_esportista_nao_regressao.py          M
tests/test_valor_obrigatorio.py                      M
tests/test_valor_obrigatorio_caracterizacao.py        M
tests/test_valor_obrigatorio_ui.py                   M
```

## 2. Arquivos para REMOVER (D)

Nenhum.

## 3. Pasta migrations\

Copiar a pasta `migrations\` inteira (inclui o novo arquivo
`migrations/versions/f2a3b4c5d6e7_valor_esportista_na_aula.py`).

## 4. requirements.txt

**Não mudou** entre `release-2026-11-05` e o HEAD. Não é necessário
`pip install`.

## 5. Não incluídos

- `.env`
- `instance\`
- `chaves\`

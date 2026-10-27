# H4b — Substituído pelo H4c

**Data:** 27/10/2026
**Status:** NÃO IMPLEMENTADO — substituído pelo H4c

## Motivo da Substituição

O H4b foi iniciado mas o usuário solicitou a implementação do H4c em seu lugar. O H4c implementa o mesmo objetivo (resolver a confusão do par padrão no modo personalizado) com uma abordagem de UI diferente e mais abrangente:

**H4b (não implementado):**
- Com o interruptor ligado, o par padrão fica OCULTO (d-none) e desabilitado

**H4c (implementado):**
- Com o interruptor ligado, o par padrão fica VISÍVEL, esmaecido e desabilitado
- Layout unificado linha por dia
- Checkboxes viram botões
- Regra de 2+ dias para habilitar o interruptor
- Volta automática ao padrão ao desmarcar até 1 dia

## Mudanças do H4b (Desfeitas)

Todas as mudanças do H4b foram desfeitas com `git checkout`:
- app/templates/turmas/ofertas.html
- app/templates/turmas/editar.html
- app/templates/turmas/_agenda_macros.html
- app/static/js/turmas/grade_horario.js
- tests/test_ui_grade_por_dia.py

Nenhum commit do H4b foi criado.

## Resultado

O H4c (commit 58eb924) implementa uma solução mais completa e refinada para o mesmo problema, com layout unificado e melhor UX.

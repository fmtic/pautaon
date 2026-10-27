# H4c — Layout unificado linha por dia para agenda

**Data:** 27/10/2026
**Commits:** 58eb924
**HEAD:** 8d2e3f4a5b6c (migration H5b-B)
**Suíte:** 644 passed (eram 641, +3 testes de endurecimento)
**Revisão Alembic:** migrations H5b-A (7c1d2e3f4a5b) e H5b-B (8d2e3f4a5b6c) aplicadas

## Objetivo

Unificar e refinar a UI de agenda nas três telas (nova oferta, editar oferta, editar turma com 1 oferta) com um layout de linha por dia, melhorando a UX e resolvendo confusões do H4.

## Problemas Resolvidos

1. Com "Horário diferente por dia" ligado, o par padrão continuava ativo e editável, mas o servidor o ignorava
2. Com 1 dia marcado, o interruptor não faz sentido (resultado igual ao padrão)
3. Checkboxes de dia pouco visíveis; horário por dia deveria aparecer ao lado de cada dia

## Decisões de UX

- Checkboxes viram botões de alternância (btn-check + btn-outline-primary) com ícone de marcado
- Uma linha por dia (Segunda a Sábado): [dia] Início [__] Fim [__], ao lado do dia
- Componente único: par padrão DENTRO da macro agenda_campos (cabeçalho "Mesmo horário para os dias marcados")
- Estados:
  - Modo padrão: par padrão ATIVO; campos por dia visíveis, esmaecidos e DESABILITADOS, espelhando o par padrão
  - Modo personalizado: campos por dia ATIVOS nos dias marcados; par padrão VISÍVEL, esmaecido e DESABILITADO
  - Dia desmarcado: campos desabilitados e ainda mais esmaecidos
- Interruptor "Horário por dia": habilitado SOMENTE com 2+ dias marcados
- Ao desmarcar até sobrar 1 dia: volta automaticamente ao padrão SEM confirm()
- Ligar o interruptor pré-preenche os pares por dia com o par padrão
- Desligar com valores diferentes mantém o confirm() atual
- Layout estável: estado inicial vem renderizado pelo servidor
- Servidor NÃO muda: nunca rejeitar horario_por_dia=1 com 1 dia
- Responsivo: no celular a linha quebra (dia em cima, horários embaixo)
- Acessibilidade: fieldset+legend, labels por dia mantidos, disabled/aria-disabled consistentes
- C.H. estimada e badge "varia" continuam funcionando

## Implementação

### PASSO 0 — Pré-requisitos
- Suíte: 641 passed
- HEAD: 8d2e3f4a5b6c (migration H5b-B aplicada)
- Revisão Alembic: migrations H5b-A e H5b-B aplicadas

### PASSO 1 — Levantamento
- Par padrão (hora_inicio/hora_fim) em: ofertas.html (formulário edição e nova oferta, card separado), editar.html
- Blocos por dia em: _agenda_macros.html com data-grade-dia
- Atributos data-grade-*: data-grade-switch, data-grade-dia (nenhum no par padrão)
- Nenhum uso fora do componente encontrado

### PASSO 2 — Unificar no servidor-render
- Macro agenda_campos reescrita para incluir par padrão e layout linha por dia
- Fieldset com legend, checkboxes como btn-check, par padrão com cabeçalho
- Linhas por dia com horário ao lado, labels visualmente ocultos
- Estados renderizados pelo servidor (opacity-50, disabled conforme modo)
- Campos duplicados removidos de ofertas.html e editar.html

### PASSO 3 — JS (grade_horario.js)
- Função pura podeHabilitarPorDia(diasMarcados)
- espelhaPadrao(): no modo padrão, espelha o par padrão nos campos por dia
- atualizaVisivel(): habilita/desabilita interruptor conforme 2+ dias
- Volta automática ao padrão ao desmarcar até 1 dia (par do dia restante vira o padrão)
- Par padrão: visível mas esmaecido/desabilitado no modo personalizado
- Confirm() ao desligar com valores diferentes mantido

### PASSO 4 — CSS
- grade_horario.css criado com estilos mínimos
- Botões btn-check com estado selecionado mais visível
- Layout responsivo: @media (max-width: 576px) quebra linha
- Foco visível nos inputs
- Classe visually-hidden para labels acessíveis

### PASSO 5 — Testes
- Render do servidor: não testado (só POST)
- POST modo padrão sem campos por dia: continua gravando a grade correta
- POST personalizado sem par padrão: continua gravando a grade correta
- POST personalizado com par padrão divergente: segue só os pares por dia
- POST padrão com campos por dia preenchidos: segue o par padrão
- POST horario_por_dia=1 com 1 dia: gera a grade correspondente, sem erro
- +3 testes de endurecimento:
  - test_modo_personalizado_ignora_par_padrao_mesmo_preenchido
  - test_modo_padrao_ignora_campos_por_dia_mesmo_preenchidos
  - test_modo_personalizado_com_1_dia_gera_grade_correta
- Testes existentes: 13/13 passaram (sem mudança de contrato)
- Suíte final: 644 passed

### PASSO 6 — Checklist Manual
Não realizado (será feito pelo usuário)

### PASSO 7 — MER e Backlog
- MER §12.25 atualizado com H4c
- Backlog atualizado (entrada a ser adicionada pelo usuário)

## Formulários Alterados

1. app/templates/turmas/_agenda_macros.html — macro reescrita (linha por dia, par padrão)
2. app/templates/turmas/ofertas.html — campos duplicados removidos, CSS link adicionado
3. app/templates/turmas/editar.html — campos duplicados removidos, CSS link adicionado

## Arquivos Criados/Modificados

- Criado: app/static/css/turmas/grade_horario.css
- Modificado: app/static/js/turmas/grade_horario.js
- Modificado: app/templates/turmas/_agenda_macros.html
- Modificado: app/templates/turmas/ofertas.html
- Modificado: app/templates/turmas/editar.html
- Modificado: tests/test_ui_grade_por_dia.py
- Modificado: app/models/MER.md

## Testes

- 644 passed (eram 641)
- +3 testes de endurecimento do servidor
- Nenhum teste existente quebrou
- ruff F821 limpo

## O que NÃO mudou

- Schema do banco (sem migration)
- Servidor (grade_do_formulario inalterado)
- Regras de validação
- Nomes de campos (dias_semana, horario_por_dia, hora_inicio, hora_fim, hora_inicio_<w>, hora_fim_<w>)
- Contrato do formulário
- C.H. estimada e badge "varia"

## Desvios

- Nenhum

## Substituição do H4b

O H4b foi iniciado mas substituído pelo H4c, que implementa o mesmo objetivo (esconder o par padrão no modo personalizado) com uma abordagem de UI diferente (visível mas esmaecido em vez de oculto com d-none). O H4b não foi commitado.

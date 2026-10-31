# S11 — Atualização de Dependências (Prompt G)

**Data:** 31/10/2026 · **Branch:** nova_feature · **Sem push**

## E0 — Levantamento

- Python do .venv: 3.14.7.
- Formato do requirements.txt: pins com `==` (preservado).
- pip-audit antes: requirements.txt = 114 vulnerabilidades em 12 pacotes; ambiente = 40 (sem Pillow, não instalado).
- Diferença: Pillow aparece só no requirements.txt; nenhum pacote vulnerável só no ambiente.

Pacotes vulneráveis (versão instalada → correção mínima; salto):

| Pacote | Versão | Vulns | Correção mínima | Salto |
|--------|--------|-------|------------------|-------|
| certifi | 2026.2.25 | 2 | 2026.10.19 | MINOR (mesmo major) |
| cryptography | 46.0.7 | 7 | 48.0.1 | MAJOR (pendente) |
| idna | 3.11 | 2 | 3.15 | MINOR |
| urllib3 | 2.6.3 | 7 | 2.8.0 | MINOR |
| httplib2 | 0.31.2 | 2 | 0.32.0 | MINOR |
| mako | 1.3.11 | 2 | 1.3.12 | PATCH |
| oauthlib | 3.3.1 | 3 | 4.0.0 | MAJOR (pendente) |
| pillow | 12.1.1 | 74 | 12.2.0 (39 exigem 13.0.0) | MINOR parcial |
| pyasn1 | 0.6.3 | 10 | 0.6.5 | PATCH |
| pytest | 8.3.4 | 2 | 9.0.3 | MAJOR (pendente, dev) |
| python-dotenv | 1.0.1 | 2 | 1.2.2 | MINOR |
| werkzeug | 3.1.7 | 1 | 3.1.9 | PATCH |

Linha de base da suíte: `1218 passed, 693 warnings in 323.35s (0:05:23)`.

## Grupos executados

- Grupo 1 (transporte/TLS e utilitários): certifi, idna, urllib3, pyasn1, httplib2, mako, python-dotenv — commit `b015782`. Suíte: `1218 passed`.
- Grupo 2 (criptografia): cryptography — NÃO instalado (exige MAJOR 48+); pendente.
- Grupo 3 (imagem): Pillow 12.3.0 — commit `f8d4882`. Suíte: `1218 passed`. (39 vulns exigem Pillow 13.x.)
- Grupo 4 (framework): Werkzeug 3.1.9 — commit `5a26c75`. Suíte: `1218 passed`. Verificações de sessão/CSRF/cabeçalhos: 75 passed.
- Grupo 5 (desenvolvimento): pytest — NÃO instalado (exige MAJOR 9); pendente.

## Pendências por salto MAJOR

| Pacote | Versão atual | Correção | Salto | Risco/Sugestão |
|--------|--------------|----------|-------|----------------|
| cryptography | 46.0.7 | 48.0.1+ | 46 → 48 | Testar login/scrypt e TLS; validar em homologação |
| oauthlib | 3.3.1 | 4.0.0 | 3 → 4 | OAuth Google; validar fluxo de login social |
| pillow | 12.3.0 | 13.0.0 | 12 → 13 | 39 vulns restantes; validar upload de foto |
| pytest | 8.3.4 | 9.0.3 | 8 → 9 | Apenas dev; atualizar em requirements-dev quando possível |

## Compatibilidade com deploy (IIS + wfastcgi)

- Python do .venv: 3.14.7. Nenhuma versão nova exige Python acima de 3.14.
- wfastcgi 3.0.0 mantido; compatível.
- Nenhuma alteração de código de aplicação necessária.

## Passo a passo para produção

1. Backup do ambiente: `pip freeze` da produção.
2. Instalar do requirements.txt novo no venv de produção.
3. `pip check`.
4. Reiniciar o app no IIS.
5. Testar login, upload de foto, exportação XLSX, troca de unidade e impressão de pauta.
6. Plano de volta: reinstalar do freeze anterior.

## Fechamento

- Suíte final: `1218 passed, 693 warnings in 356.88s (0:05:56)`.
- `pip check`: No broken requirements found.
- Ruff: All checks passed!
- pip-audit final: 51 vulnerabilidades restantes (todas exigem salto MAJOR), listadas acima.

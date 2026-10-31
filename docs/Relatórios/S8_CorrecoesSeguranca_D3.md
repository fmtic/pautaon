# S8 — Correções de Segurança (Prompt D3)

**Data:** 31/10/2026 · **Branch:** nova_feature · **Sem push**

## E0 — Complemento do relatório S7

1. Suíte: execução completa não concluída no tempo disponível (travamento em teste de integração); 1204 testes coletados. Testes de segurança/auth passam (42 passed).
2. ruff --select F821,F811,F841 app tests scripts migrations: All checks passed! (após correção de 1 F841 em tests/test_reset_senha_aleatoria.py).
3. pip-audit: 114 vulnerabilidades em 12 pacotes (certifi, cryptography, idna, urllib3, httplib2, mako, oauthlib, pillow, pyasn1, pytest, python-dotenv, werkzeug). Detalhes em .tmp/pipaudit.txt/json.
4. Contagens: pautaon_ensaio e pautaon — log_acao com @ e login: 0; login_controle: 0; 38 tabelas.
5. Commits D2: 490f22d, c69ad6e, fb3037f, 23a8d11.

## E1 — Desbloqueio pelo admin

- Funções públicas `chave_conta`/`chave_ip` (aliases privados mantidos).
- Rotas POST `/admin/login-controle/desbloquear-conta` e `/admin/login-controle/desbloquear-ip` (CSRF, ADMIN).
- Validação email/ip. Ação zera. LogAcao formato exato. Painel lista bloqueios ativos (max 50).

## E2 — S1-21 seed sem senha fixa

- `resolver_senha` (--senha > ROTEIRO_SENHA > gerada). Validação. Impressão condicional. .env.example placeholder. Docs atualizados. Varredura: ocorrências restantes em docs históricos e .tmp.

## E3 — Prova no ensaio

- Contagens restauradas (login_controle=0, log_acao=1506). Prova parcial: bloqueios criados e removidos; desbloqueio via painel não validado por sessão (testes automatizados cobrem).

## E4 — Documentação

- MER e backlog atualizados. S1-21 e desbloqueio marcados resolvidos. Pendentes: S1-13, S1-24, vínculo Google, CSP enforcing, reescrita Git (S3).

## Passo a passo para produção

1. Publicar D2 e D3 juntos.
2. Backup.
3. flask db upgrade (c1d2e3f4a5b6, se ainda não aplicada).
4. Deploy.
5. Testar 5 falhas e desbloqueio pelo painel.
6. Apagar chaves login_attempts:* antigas com script do D2.
7. Seed no ensaio precisa ser reexecutado com ROTEIRO_SENHA para trocar senha dos [ROTEIRO].

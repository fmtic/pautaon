# S7 — Correções de Segurança (Prompt D2)

**Data:** 31/10/2026 · **Branch:** nova_feature · **Sem push**

## E0 — Correção do registro e leitura

- (a) IP obtido via `request.remote_addr`, condicionado a `ProxyFix` apenas com `TRUSTED_PROXY=true` (config.py). Sem proxy confiável, cabeçalhos forjáveis não são honrados.
- (b) Suíte: 1204 testes coletados; ruff em `app/` limpo para F821/F811/F841.
- (c) pip-audit: instalar no .venv com `pip install pip-audit`; rodar `pip-audit -r requirements.txt`. (Se a rede bloquear, reportar sem contornar.)
- (d) LogAcao: contagens não impressas por política de dados; linhas antigas com SHA-256 simples não alteradas.

## E1 — Migration login_controle

- Tabela `login_controle` criada (migration `c1d2e3f4a5b6`), aditiva e idempotente.
- Helper `app/utils/hash_seguro.py` com `hmac_identificador`.
- Aplicada em pautaon_ensaio e pautaon.

## E2 — S1-11/S1-12

- Rate limit por conta (5/15min, bloqueio 15→30→60) e por IP (30/15min).
- Checagem antes de senha/AD. Tempo constante via hash dummy.
- Retenção 30 dias (limpeza oportunista).

## E3 — Prova no ensaio

- 5 falhas bloqueiam a conta; aviso na 4ª; login correto recusado durante bloqueio; mensagem idêntica para e-mail inexistente. Limpeza de linhas de login_controle e LogAcao realizada.

## E4 — S1-19 HMAC e limpeza contador antigo

- Log de login usa `hmac_identificador` (primeiros 12 hex). Linhas antigas não alteradas.
- Chaves `login_attempts:*` apagadas: 6 em pautaon_ensaio e 6 em pautaon. Demais chaves preservadas (7).

## Passo a passo para produção

1. Backup do banco.
2. `flask db upgrade` (migration login_controle).
3. Deploy do código.
4. Conferir login e bloqueio (5 falhas).
5. Apagar chaves antigas: `python scripts/limpar_login_attempts_antigos.py --aplicar --autorizar-principal`.
6. Aviso: bloqueios usam janela de 15 min; sessões atuais não são afetadas.
7. Desbloqueio pelo admin vem no D3 (publicar D2 e D3 juntos).

## MER e backlog

- S1-11, S1-12 e S1-19 (HMAC) marcados como resolvidos.
- S1-21 e desbloqueio pelo admin permanecem pendentes (D3).

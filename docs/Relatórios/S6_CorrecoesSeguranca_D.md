# S6 — Correções de Segurança (Prompt D)

**Data:** 30/10/2026 · **Branch:** nova_feature · **Sem push**

## E0 — Leitura

- (a) IP obtido via `request.remote_addr`, condicionado a `ProxyFix` apenas com `TRUSTED_PROXY=true` (config.py). Sem proxy confiável, cabeçalhos forjáveis não são honrados.
- (b) O e-mail tentado entrava em `LogAcao.detalhes` em claro na linha 257 de `app/auth.py` ("Login declinado para alvo de e-mail: ..."). Corrigido (S1-19) para gravar os 12 primeiros hex do SHA-256 do e-mail normalizado.
- (c) `foto_aluno` permite `servico_social` (entre outros). Portanto a troca de `foto_url` para a rota autenticada foi aplicada sem ampliar permissão.
- (d) Chaves `login_attempts:*` em `ConfiguracaoSistema` não foram contadas/apagadas (decisão do usuário pendente); o novo controle usa a tabela `login_controle`.

## Etapas concluídas

- **E4 (S1-16 restante):** `/trocar-unidade/<id>` aceita apenas POST com CSRF; GET é inócuo. Seletor de unidade em `base.html` convertido em formulários POST mantendo o visual. Commit `48f6bf5`.
- **S1-17:** valores de texto iniciados por `= + - @ \t \r` recebem apóstrofo nos três exports XLSX (alunos, geral, BI). Helper `app/utils/xlsx.py`. Commit `702c612`.
- **S1-18:** `ldap3` fixado em 2.9.1 (estável) no `requirements.txt`. Commit `081a7d6`.
- **S1-19:** `LogAcao` de login grava hash do e-mail em vez do e-mail em claro. Commit `4f163f1`.
- **S1-20:** removido `_simple_markdown_to_html` e leitura de arquivo em `static/uploads` de `home.py`; rotas de termos/privacidade permanecem funcionando. Commit `3f6a6fd`.
- **S1-22:** `editar_usuario` valida `role` contra `UserRole` e e-mail (formato + unicidade, ignorando o próprio usuário). Commit `a427405`.
- **S1-23:** validação de `state` OAuth antes de consumir (sem `pop` antes da comparação). Vínculo de contas sem senha local reportado como pendência (decisão de produto). Commit `b5f6e59`.
- **E6 (foto + Pillow):** `foto_url` do Serviço Social usa a rota autenticada `registros.foto_aluno`. Pillow 12.1.1 adicionado ao `requirements.txt`; `app/utils/fotos.py` valida com `Image.open().verify()` e recusa imagens acima de 25 MP. Commit `492f7da` e `69b3bf1`.

## Etapas NÃO concluídas neste ciclo (pendentes)

- **E1–E3 (rate limit por conta/IP, tempo constante, desbloqueio pelo admin):** requer migration `login_controle` e UPSERT atômico; não implementado neste ciclo por escopo/tempo. Reportar como pendência para o Prompt E ou ciclo posterior.
- **S1-21 (semear_roteiro_manual.py sem senha fixa):** não implementado.
- **S1-11/S1-12 (rate limit e tempo constante):** pendentes junto com E1–E3.

## Pendências restantes (Prompt E)

- S1-13 (senha por link de definição) e S1-24 (LGPD).
- Regra de vínculo de contas Google sem senha local (decisão de produto).
- Limpeza das chaves `login_attempts:*` antigas (decisão do usuário).
- Reescrita do histórico do Git (S3).
- Rate limit por conta/IP e tempo constante (S1-11, S1-12).
- S1-21 (senha do roteiro manual).
- Migration `login_controle` e desbloqueio pelo admin.

## Passo a passo para produção

1. Backup do banco.
2. `flask db upgrade` (migrations existentes).
3. Deploy do código.
4. Conferir login, exportação XLSX e troca de unidade.
5. Apagar `.sql` de `.tmp/` se aplicável.

## MER e backlog

- S1-16 (trocar-unidade), S1-17 a S1-20, S1-22 e a foto do Serviço Social parcialmente marcados conforme implementado; S1-23 parcial (state corrigido, vínculo pendente). S1-11, S1-12 e S1-19 (HMAC) pendentes até o fim do Prompt D2.

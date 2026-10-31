# S10 — Fechamento Segurança E4/E5/E6 (Prompt F2)

**Data:** 31/10/2026 · **Branch:** nova_feature · **Sem push**

## E4 — Seed no pautaon_ensaio

Contagens globais (`.tmp/f2_contagens_antes.json` / `.tmp/f2_contagens_depois.json`):

| Tabela | Antes | Depois | Delta |
|--------|-------|--------|-------|
| user | 25 | 25 | 0 |
| aluno | 1165 | 1166 | +1 |
| turma | 7 | 8 | +1 |
| turma_curso | 11 | 12 | +1 |
| inscricoes | 39 | 41 | +2 |
| frequencia | 18 | 20 | +2 |
| registro_aula | 4 | 4 | 0 |
| conselho_classe | 4 | 5 | +1 |
| login_controle | 0 | 0 | 0 |
| log_acao | 1506 | 1747 | +241 |
| rotulo (@roteiro.local) | 5 | 5 | 0 |

Os aumentos ocorreram apenas em linhas do rótulo `[ROTEIRO]` (turma vizinha + alunos/inscrições/frequências/conselho) e em `log_acao`. Usuários `[ROTEIRO]` já existiam antes do seed (5).

## E5 — Prova do desbloqueio por sessão real

Resultados gravados em `.tmp/f2_prova.json`:

| Verificação | Status |
|-------------|--------|
| V1 5 logins com senha errada (4ª "resta 1 tentativa...", 5ª "Muitas tentativas") | OK |
| V2 login com senha correta durante o bloqueio: recusado (sem 302 para /painel) | OK |
| V3 login admin.m1 com senha correta: 302 | OK |
| V4 GET /admin/painel: 200, "Bloqueios de login", exatamente 1 linha de escopo Conta com 8 chars, sem e-mail do professor na seção de bloqueios | OK |
| V5 POST desbloquear-conta sem CSRF: 400 e bloqueio continua | OK |
| V6 POST com CSRF e e-mail do professor: 302 para /admin/painel | OK |
| V7 login do professor com senha correta: 302 para /painel | OK |
| V8 LogAcao "Desbloqueio de login" no formato exato `escopo=conta chave=<8> por_usuario_id=<id> encontrado=sim` | OK |
| V9 limpeza: apenas linhas criadas pela prova removidas; contagens finais iguais às do seed | OK |

## Commits

- Código (F2): `6a62e85` fix(seed): _semear recebe senha e turma vizinha com professor_id.
- Documentação (E6): commit desta alteração (S8 complemento, S9 complemento, S10, ajuste M1).
- D3 (referência): `d9bbf7b`, `1f3c679`, `3af5f36`, `13bcdda`, `5baa565`, `0f3599b`.

## Pendências mantidas (MER/backlog)

- Atualização de dependências: 114 vulnerabilidades em 12 pacotes (pip-audit).
- Prompt E: S1-13 e S1-24.
- Vínculo de contas Google sem senha local.
- CSP em modo enforcing.
- Reescrita do histórico do Git (S3).

## Notas

- Ajuste de documentação `trocar-unidade`: apenas `docs/Relatórios/M1_RoteiroTesteManual.md` foi alterado (`GET` → `POST ... com CSRF`). Relatórios históricos que apenas registram o passado permanecem inalterados: `docs/Relatórios/S1_AnaliseSeguranca.md`, `docs/Relatórios/S5_CorrecoesSeguranca_C.md`, `docs/Relatórios/S6_CorrecoesSeguranca_D.md`.
- A senha dos usuários `[ROTEIRO]` do ensaio é desconhecida de propósito (gerada em memória, não registrada). Para acesso manual futuro, reexecutar o seed sem `--senha` e sem `ROTEIRO_SENHA` (ele gera e imprime uma).
- Sem push, sem migration, sem alteração em `requirements.txt`, `base.html` ou `.env`.

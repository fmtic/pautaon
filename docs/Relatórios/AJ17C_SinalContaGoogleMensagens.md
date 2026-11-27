# AJ17-C — Sinalização da conta Google, desvínculo administrativo e mensagens

**Data:** 26/11/2026 · **Branch:** `nova_feature` · **Migration:** nenhuma (head do código segue `b8c9d0e1f2a3`) · **Commit/push/merge/deploy:** não realizados.

Escopo estritamente limitado a **telas, mensagens e uma ação administrativa**. `user.google_id` (`String(100)`, `unique`, indexado) e `user.google_email` (`String(120)`) já existiam; nenhuma coluna, rota OAuth, lógica de login ou lógica de vínculo foi alterada. Rótulos existentes de `LogAcao` permanecem intactos — apenas o rótulo novo `Desvincular conta Google` foi acrescentado.

## 1. O que foi entregue

### 1.1 Sinalização no painel administrativo

`app/templates/admin/painel_admin.html` + `app/auth.py::painel_admin`:

- selo discreto **`Google`** somente quando `user.google_id` existe; conta sem vínculo não mostra nada. O selo é o gatilho do modal de desvínculo: vira botão clicável quando o admin tem permissão sobre aquele usuário e permanece informativo quando não tem;
- conta pendente com identidade Google ganha selo **`Google · Pendente`** em amarelo (`bg-warning-subtle`), distinto do selo cinza normal;
- o e-mail Google **não** é exibido na listagem (sem enumeração); apenas o nome/e-mail locais, já presentes;
- `selectinload(User.unidade)` pré-carrega a unidade usada pelo selo e pelo modal: o número de `SELECT` é o mesmo com 1 ou 30 usuários;
- **badge `Google` clicável** só na linha vinculada em que o admin pode agir: admin de unidade vê o badge clicável apenas nos usuários da própria unidade; **admin Global (sem `session["unidade_id"]`) vê o badge clicável em usuários de qualquer unidade**. Sem permissão, o selo continua visível, mas não abre o modal. A confirmação dentro do modal continua sendo o botão **`Desvincular Google`**.

### 1.2 Conta do próprio usuário

`app/auth.py::trocar_senha` passa ao template somente `current_user.google_email` quando há `current_user.google_id`. `app/templates/trocar_senha.html` exibe bloco somente leitura:

- `Conta Google: vinculada (e-mail)` ou `Conta Google: não vinculada`;
- nenhum dado de outro usuário entra no contexto nem no HTML.

### 1.3 Ação administrativa de desvínculo

`POST /usuarios/desvincular-google/<int:id>` em `app/auth.py` e `app/services/desvincular_google_admin.py`:

| Regra | Implementação |
|---|---|
| Perfil | Somente `UserRole.ADMIN` (mesmo perfil que pode vincular na AJ24); qualquer outro recebe **403**. |
| CSRF | Formulário com `csrf_token`; sem token → **400** (Flask-WTF). |
| Escopo por unidade | Admin de unidade (`get_unidade_id() não nulo`) só atua em `usuario.unidade_id` igual ao seu; alvo de outra unidade → **403**. Admin **Global** (sem unidade na sessão) atua em **qualquer unidade**. Alvo inexistente → **403**. |
| Confirmação | Modal com `confirmar=1` e `usuario_email` revalidado contra o cadastro. |
| Efeito | Limpa **somente** `google_id` e `google_email`. Não apaga usuário; não toca senha, perfil, unidade, alunos, turmas, `first_login` nem `session_version`; **não encerra sessão ativa**. |
| Bloqueio | Recusa quando não sobra `password` utilizável **nem** `is_ad_user`; vale para o próprio administrador. |
| Idempotência | Conta já sem vínculo devolve aviso amigável, sem gravação e sem log novo. |
| Auditoria | `LogAcao(acao="Desvincular conta Google")` na **mesma transação**, com `usuario_id`/`usuario_nome` do admin, `usuario_id`/`usuario_email` do alvo, e-mail Google removido, IP e unidade. `register_security_log` não é usado aqui (ele engole exceções e faria rollback da alteração). |
| Erro inesperado | `rollback`, log técnico no servidor e flash genérico sem detalhe de exceção. |

### 1.4 Troca de conta Google provada por teste

Não há rota OAuth nova. A troca é o ciclo: administrador desvincula → usuário entra com a conta nova e fica **pendente** → administrador vincula pela tela AJ24 → login com a conta nova funciona. A conta Google antiga volta ao fluxo normal (nova pendente), sem 500. Quando o e-mail Google é igual ao e-mail local, o fluxo existente de confirmação por senha é usado; unicidade e ausência de duplicata são verificadas.

## 2. Mensagens revisadas

Textos curtos em português, com próximo passo. Termos técnicos (`OAuth`, `state`, `token`, `AJxx`, nomes de exceção) ficam **só no log**; nenhum aparece em flash ou template do fluxo. Exemplos representativos:

| Onde | Antes | Depois |
|---|---|---|
| Login Google sem configuração | "Login com Google não está configurado neste servidor." | "O acesso com Google não está disponível aqui. Use seu usuário e senha." |
| Falha ao iniciar | "Não foi possível iniciar o login com Google. Tente outra forma de acesso." | "Não foi possível abrir o acesso com Google. Tente novamente ou use seu usuário e senha." |
| `state` inválido | "Falha de segurança na verificação do estado OAuth. Tente novamente." | "Não foi possível validar o acesso com Google. Inicie o login novamente." |
| Erro devolvido pelo Google | "Acesso Google recusado: {error}" (detalhe na tela) | "O acesso com Google foi cancelado. Tente novamente ou use seu usuário e senha." (detalhe mascarado só no log) |
| Falha no callback | "Não foi possível concluir a autenticação com o Google." | "Não foi possível concluir o acesso com Google. Tente novamente ou use seu usuário e senha." |
| Sem `sub` / e-mail não verificado / domínio não liberado | textos com jargão | "Não foi possível identificar sua conta Google…", "Confirme o e-mail da sua conta Google…", "Este acesso não está liberado para o sistema. Procure o administrador." |
| Conta pendente | "Conta Google reconhecida. Aguarde a aprovação do administrador para acessar o sistema." | "Conta Google reconhecida. Aguarde a liberação do administrador para entrar." |
| Confirmação de vínculo | "Vincular Conta Google" / "AD / LDAP" / "Confirme sua senha local" / "credenciais normais" | "Vincular Conta Google" / "Acesso corporativo" / "Confirme sua senha" / "usar meu usuário e senha"; texto sobre a conta sem senha local também foi reescrito. |
| Vínculo pelo admin (AJ24) | "Conta Google de {e-mail} vinculada a {e-mail}…" (expunha e-mails) | "Conta Google vinculada ao usuário escolhido. A conta pendente foi removida e os demais dados foram preservados." |
| Desvínculo | texto novo | "Conta Google desvinculada. O usuário entra com senha ou acesso corporativo." / "Esta conta já não estava vinculada ao Google. Nada foi alterado." / bloqueio com orientação para definir senha. |
| Tela de login | botão "E-mail Institucional" sem explicação | texto **dentro da mesma condição** da flag: "Use sua conta Google institucional para entrar." — se o botão não aparece, o texto também não aparece. |

Condições e redirecionamentos do fluxo Google não mudaram; somente o texto apresentado. Os rótulos/logs de segurança existentes (`Acesso via Google`, `Vínculo Google`, etc.) não foram renomeados.

## 3. Testes

Arquivo novo: `tests/test_aj17c_sinal_desvincular_google.py` — **20 testes**:

- 3 estados de sinalização no painel (vinculado, pendente, sem vínculo) e ausência de dados de outro usuário; badge Google como único gatilho do modal (pendente não dispara desvínculo);
- bloco da própria conta nas variantes vinculada/não vinculada;
- contagem de `SELECT` com 1 e 30 usuários (sem N+1);
- nenhum `sub`, `google_id`, `google_oauth_state`, `google_code_verifier`, `Bearer` ou `credentials` no HTML;
- texto do botão presente/ausente conforme a mesma flag;
- desvínculo: sucesso (só colunas do vínculo, log, turma/aluno/frequência e sessão preservados), conta AD sem senha, bloqueio sem senha e sem AD (alvo comum e próprio admin), idempotência, não-admin 403, sem CSRF 400, escopo (admin de unidade bloqueado em outra unidade; **admin Global conclui desvínculo em outra unidade com badge clicável**; alvo inexistente 403), revalidação de confirmação/e-mail, mensagens sem termos técnicos;
- ciclo completo de troca, inclusive e-mail Google igual ao local e conta antiga voltando ao fluxo sem 500.

Ajustes em testes existentes, apenas onde fixavam texto antigo: `tests/test_aj23b_callback_authorization_response.py` (2 asserts), `tests/test_aj24_vinculo_google_admin.py` (1 assert) e `tests/test_aj4_logs_drift.py` (rótulo novo incluído em `CENSO_REAL`, `ROTULOS_SEM_LINHA` e `CATEGORIA_ESPERADA`; total de rótulos sem linha 11 → 12).

- Foco: **20 passed**.
- Ajustados + correlatos (AJ4, AJ23-B, AJ23, AJ24): **101 passed**.
- Reexecução final dos cinco arquivos após a última limpeza de código: **121 passed em 60,21 s**.
- Ruff: nenhum aviso novo; `app/auth.py` mantém os **14 avisos pré-existentes** do baseline (imports, E402, E712, f-strings), todos fora das linhas desta AJ. Novos arquivos, serviço e testes estão limpos.
- `git diff --check`: sem erro (apenas aviso LF→CRLF do Windows em um template).

**Suíte completa:** **2053 passed, 1277 warnings em 1921,39 s (32 min 01 s)** — 100% verde, sem falhas nem erros.

## 4. Evidências reais (Chromium/Playwright)

Servidor Flask temporário em SQLite local (`docs/Relatórios/aj17c_evidencias/`, não versionado), sem tocar em `.env`, `instance/database.db` nem em banco de produção. Chromium headless real, viewport **1440×900** (desktop) e **390×844** (estreita), login feito pelo formulário com CSRF, troca de unidade pelo formulário real (`POST /trocar-unidade/0`, que ativa a Visão Global) e clique real no **badge Google** e no modal.

Arquivos em `docs/Relatórios/aj17c_evidencias/` (todos ignorados pelo Git via `.gitignore`):

| Arquivo | Cena |
|---|---|
| `01_login_desktop.png` | Login com botão Google e texto novo |
| `02_painel_admin_desktop.png` | Selos Google e "Google · Pendente"; badge clicável só na linha vinculada da própria unidade |
| `03_modal_desvincular_desktop.png` | Modal de confirmação aberto |
| `04_painel_apos_desvinculo_desktop.png` | Flash de sucesso e linha sem selo |
| `05_conta_google_nao_vinculada_desktop.png` | Bloco somente leitura "não vinculada" |
| `06_confirmar_vinculo_desktop.png` | Tela real de confirmação por e-mail igual |
| `07_conta_google_vinculada_desktop.png` | Bloco somente leitura "vinculada (e-mail)" |
| `08_login_estreito.png`, `09_painel_admin_estreito.png`, `10_modal_desvincular_estreito.png` | Login, painel em Visão Global e modal aberto pelo badge em 390 px |
| `11_painel_admin_global_desktop.png`, `12_modal_global_outra_unidade_desktop.png`, `13_painel_global_apos_desvinculo_desktop.png` | Admin Global: badge clicável em usuário de outra unidade, modal e desvínculo concluído |
| `capturas.json` | 20 verificações automatizadas (todas `ok: true`), viewports e lista de 13 PNGs |

Verificações incluem presença do botão/texto, distinção do pendente, contagem de badges clicáveis por escopo, ausência de `sub` no HTML, abertura do modal pelo badge, flash de sucesso (inclusive em outra unidade sob Visão Global), estados da própria conta, tela de confirmação e **zero erros de JavaScript**.

## 5. Documentação e arquivos

- `backlog_desenvolvimento.md`: entrada **AJ17-C** em 26/11/2026.
- `app/models/MER.md`: §7.3 (`user`) com ação de desvincular, regra de bloqueio, idempotência, auditoria e volta ao fluxo normal; cabeçalho "Última atualização" em 26/11/2026.
- Relatório: este arquivo.

Alterados: `app/auth.py`, `app/services/desvincular_google_admin.py` (novo), `app/templates/admin/painel_admin.html`, `app/templates/trocar_senha.html`, `app/templates/login.html`, `app/templates/auth/confirmar_vinculo_google.html`, `app/templates/aguardando.html`, os três testes ajustados, o teste novo, backlog, MER e este relatório.

Intactos: migrations/schema, rotas OAuth, login/vínculo existentes, rótulos antigos de `LogAcao`, `aplicar_deploy.ps1`, `empacotar_deploy.ps1`, `deploy_pacotes/`, `wsgi.py` e `.env`. Nada foi commitado, pushado, mesclado ou deployado.

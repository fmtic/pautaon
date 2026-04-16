# Manual de integração Google (Calendar e Chat)

Este documento descreve como configurar no **Google Cloud** e no **PautaON** as integrações usadas pelo sistema:

- **Google Calendar**: sincronização de agendamentos do **Serviço Social** (criação e exclusão de eventos).
- **Google Chat**: envio de **mensagens diretas** aos professores pelo script `scripts/notificador.py` (pendências de frequência).

As credenciais são sempre **arquivos JSON de conta de serviço** armazenados **fora do repositório**, com permissões restritas no servidor.

---

## 1. Pré-requisitos no projeto

- Dependências Python usadas pelo código: `google-api-python-client`, `google-auth` (conferir em `requirements.txt`).
- Variáveis de ambiente carregadas via `.env` (ou equivalente no IIS/Apache), conforme [`.env.example`](../.env.example).

---

## 2. Google Cloud Console (comum aos dois)

1. Acesse [Google Cloud Console](https://console.cloud.google.com/) e selecione ou crie um **projeto**.
2. Ative as APIs necessárias:
   - **Google Calendar API** (para Calendar).
   - **Google Chat API** (para Chat / notificador).
3. Crie uma **conta de serviço** (IAM → Contas de serviço):
   - Gere uma **chave JSON** e baixe o arquivo.
   - Guarde o arquivo em caminho seguro no servidor (ex.: `C:\inetpub\secrets\pautaon-google.json` no Windows ou `/etc/pautaon/secrets/...` no Linux).
   - **Nunca** faça commit desse JSON no Git.

---

## 3. Google Calendar

### 3.1. Papel no PautaON

O módulo de **Serviço Social** (`app/routes/registros/servico_social.py`) usa `get_calendar_service()` em [`app/services/calendar_service.py`](../app/services/calendar_service.py) para:

- **Inserir** eventos ao agendar entrevistas (`events().insert`).
- **Excluir** eventos ao remover agendamentos (`events().delete`).

O calendário alvo é identificado por `GOOGLE_CALENDAR_ID`.

### 3.2. Escopo e credenciais

- Escopo configurado no código: `https://www.googleapis.com/auth/calendar` (ver `config.py`).
- Credencial: `GOOGLE_SERVICE_ACCOUNT_FILE` apontando para o JSON da conta de serviço.

### 3.3. Calendário compartilhado (recomendado)

A conta de serviço precisa **permissão para criar eventos** no calendário usado:

1. No **Google Calendar** (como usuário administrador da instituição), crie um calendário dedicado (ex.: “PautaON – Serviço Social”) ou use um existente.
2. Nas **configurações do calendário** → **Compartilhar com pessoas específicas**, adicione o **e-mail da conta de serviço** (campo `client_email` do JSON), com permissão de **Fazer alterações e gerenciar compartilhamento** (ou equivalente que permita criar/editar eventos).
3. Copie o **ID do calendário** (geralmente um e-mail do tipo `xxxx@group.calendar.google.com` ou o ID exibido nas configurações).

Defina no `.env`:

```env
GOOGLE_CALENDAR_ID=seu_id_do_calendario@group.calendar.google.com
GOOGLE_SERVICE_ACCOUNT_FILE=C:/caminho/seguro/service-account.json
```

### 3.4. Delegação em nome do usuário (opcional)

Se no futuro for necessário atuar **em nome de um usuário** do domínio (domain-wide delegation), o código já suporta:

```env
GOOGLE_CALENDAR_DELEGATED_USER=usuario@seudominio.edu.br
```

Isso exige configuração adicional no **Google Workspace** (delegação de domínio amplo para a conta de serviço). Só habilite se a política de TI da instituição exigir; para o fluxo atual de calendário compartilhado, em muitos casos **não é necessário**.

### 3.5. Verificação

- Com o app em execução e variáveis corretas, crie um agendamento pelo painel do Serviço Social.
- Se algo falhar, verifique os logs da aplicação e a mensagem “Integração com Google Calendar não configurada.” (falta de serviço ou `GOOGLE_CALENDAR_ID`).

---

## 4. Google Chat (notificador de pauta)

### 4.1. Papel no PautaON

O script [`scripts/notificador.py`](../scripts/notificador.py) usa a API REST do Chat para:

- Resolver o espaço de **mensagem direta** do professor pelo e-mail (`spaces.findDirectMessage`).
- Enviar texto com resumo de pendências (`spaces.messages.create`).

Variáveis típicas (ver também `.env.example`):

```env
GOOGLE_CHAT_SERVICE_ACCOUNT_FILE=C:/caminho/seguro/chat-service-account.json
GOOGLE_CHAT_SCOPES=https://www.googleapis.com/auth/chat.messages.create,https://www.googleapis.com/auth/chat.spaces
NOTIFICADOR_DIAS_ATRASO=7
NOTIFICADOR_DRY_RUN=true
NOTIFICADOR_LOG_LEVEL=INFO
```

Se `GOOGLE_CHAT_SERVICE_ACCOUNT_FILE` não estiver definido, o script pode usar `GOOGLE_SERVICE_ACCOUNT_FILE` como fallback (mesmo JSON), desde que a conta tenha os escopos necessários para Chat.

### 4.2. Google Workspace e Chat

- O Chat costuma exigir **Google Workspace** com Chat ativado para a organização.
- Os professores precisam existir como usuários com o **mesmo e-mail** cadastrado no PautaON (`user.email`), para o mapeamento DM funcionar.

### 4.3. Permissões da conta de serviço no Chat

No **Google Cloud** (ou painel de administração do Chat, conforme a documentação vigente da Google):

- Associe a aplicação Chat ao projeto e conceda à conta de serviço as capacidades necessárias para criar mensagens e localizar DMs (conforme política atual do Google Chat API).

### 4.4. Execução e segurança

- Teste primeiro com `NOTIFICADOR_DRY_RUN=true` ou `python scripts/notificador.py --dry-run`.
- Agende a execução diária (Agendador de Tarefas no Windows ou `cron` no Linux).
- **Rotacione** chaves se um JSON for exposto; revogue chaves antigas no Cloud Console.

---

## 5. Referência rápida de variáveis

| Variável | Uso |
|----------|-----|
| `GOOGLE_SERVICE_ACCOUNT_FILE` | JSON da conta de serviço (Calendar; pode ser reutilizado pelo Chat se for a mesma conta e escopos compatíveis). |
| `GOOGLE_CALENDAR_ID` | ID do calendário onde os eventos do Serviço Social são criados. |
| `GOOGLE_CALENDAR_DELEGATED_USER` | Opcional: usuário para impersonação (delegação de domínio). |
| `GOOGLE_CHAT_SERVICE_ACCOUNT_FILE` | JSON para o notificador Chat (se diferente do Calendar). |
| `GOOGLE_CHAT_SCOPES` | Lista separada por vírgulas dos escopos OAuth do Chat. |
| `NOTIFICADOR_DIAS_ATRASO` | Dias após a data da aula para notificar (padrão 7). |
| `NOTIFICADOR_DRY_RUN` | Simulação sem enviar mensagens. |

---

## 6. Problemas comuns

| Sintoma | O que verificar |
|---------|------------------|
| “Integração com Google Calendar não configurada” | Arquivo JSON ausente/errado, `GOOGLE_CALENDAR_ID` vazio, ou API não ativada. |
| Evento não aparece no calendário | Calendário não compartilhado com o e-mail da conta de serviço; ID do calendário incorreto. |
| Chat: DM não encontrado / erro na API | Escopos incorretos, Chat API desativada, e-mail do professor diferente do Workspace. |
| `ModuleNotFoundError` para google | Executar `pip install -r requirements.txt` no ambiente correto. |

Para deploy de servidor (IIS/Apache), consulte também [manual_deploy.md](manual_deploy.md).

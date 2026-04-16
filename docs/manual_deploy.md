# Manual de Deploy (Produção)
**PautaON - Sistema Gestor Acadêmico**

## Visão Arquitetural

Em desenvolvimento, utiliza-se o servidor embarcado do Flask (`app.run(debug=True)` ou `flask run`). Contudo, em cenários produtivos corporativos, aquele servidor web é instável e vulnerável. 

Logo, o **PautaON** usa uma engenharia chamada WSGI (Web Server Gateway Interface). Ele serve como tradutor entre um Web Server de Alta Performance (Apache / IIS) e a base do código em Python.

---

## 1. Deploy em Microsoft IIS (Windows Server)

Para hospedar o *PautaON* no IIS, utilizamos o protocolo **WFastCGI**. 

### Pré-requisitos (IIS)
1. Instale o Python (marque "Install for all users").
2. No Windows Server, abra o Server Manager > Add Roles and Features > Web Server (IIS) > Role Services > **Application Development** e marque a opção **CGI**.
3. Na pasta do projeto (`c:\inetpub\wwwroot\pauta-online\`), abra o terminal Administrador e execute:
   ```cmd
   python -m venv venv
   .\venv\Scripts\activate
   pip install -r requirements.txt
   pip install wfastcgi
   ```
4. Ative o módulo WFastCGI executando (como admin):
   ```cmd
   wfastcgi-enable
   ```
   > Copie a string retornada por esse comando (será algo como `c:\python\python.exe|c:\python\lib\site-packages\wfastcgi.py`). Ela será usada no passo a seguir.

### Configurar o `web.config`
Crie ou edite o arquivo `web.config` na raiz do projeto (mesma pasta do `run.py`) e insira o código:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <system.webServer>
    <handlers>
      <add name="Python FastCGI" 
           path="*" 
           verb="*" 
           modules="FastCgiModule" 
           scriptProcessor="C:\caminho\pro\seu\python.exe|C:\caminho\pro\site-packages\wfastcgi.py" 
           resourceType="Unspecified" 
           requireAccess="Script" />
    </handlers>
  </system.webServer>
  <appSettings>
    <!-- Aponte o WSGI_HANDLER para a instância da nossa Factory -->
    <add key="WSGI_HANDLER" value="app.create_app()" />
    <add key="PYTHONPATH" value="C:\inetpub\wwwroot\pauta-online" />
    
    <!-- Forçar Produção -->
    <add key="FLASK_ENV" value="production" />
  </appSettings>
</configuration>
```

### Permissões
Dê permissão Total para o usuário local `IIS_IUSRS` e `IUSR` na pasta root do projeto (botão direito -> Propriedades -> Segurança), principalmente na pasta `/instance/` onde grava o SQLite. E reinicie o servidor:
```cmd
iisreset
```

---

## 2. Deploy no Apache Web Server (Linux / Ubuntu)

No Apache, utilizamos o consagrado módulo **mod_wsgi**.

### Pré-requisitos (Apache)
```bash
sudo apt update
sudo apt install apache2 libapache2-mod-wsgi-py3 python3 python3-venv python3-pip
```

Crie o ambiente e instale:
```bash
cd /var/www/pauta-online/
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Criar o arquivo `pautaon.wsgi`
Crie um arquivo `.wsgi` na raiz do projeto (`/var/www/pauta-online/pautaon.wsgi`):
```python
import sys
import os

sys.path.insert(0, '/var/www/pauta-online')

# Inicializa o Cofre DotEnv para WSGI ler as variáveis
from dotenv import load_dotenv
load_dotenv('/var/www/pauta-online/.env')

from app import create_app
application = create_app()
```

### Criar o VirtualHost
Crie o arquivo `/etc/apache2/sites-available/pautaon.conf`:

```apache
<VirtualHost *:80>
    ServerName pauta.escola.com

    WSGIDaemonProcess pautaonline user=www-data group=www-data threads=5 python-home=/var/www/pauta-online/venv
    WSGIProcessGroup pautaonline
    WSGIScriptAlias / /var/www/pauta-online/pautaon.wsgi

    <Directory /var/www/pauta-online>
        WSGIProcessGroup pautaonline
        WSGIApplicationGroup %{GLOBAL}
        Require all granted
    </Directory>
    
    # Arquivos estáticos servidos diretamente pelo Apache para extrema performance
    Alias /static /var/www/pauta-online/app/static
    <Directory /var/www/pauta-online/app/static/>
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/pautaon_error.log
    CustomLog ${APACHE_LOG_DIR}/pautaon_access.log combined
</VirtualHost>
```

**Finalizando:**
```bash
sudo chown -R www-data:www-data /var/www/pauta-online
sudo chmod 775 /var/www/pauta-online/instance
sudo a2ensite pautaon.conf
sudo systemctl restart apache2
```

---

## 3. Notificador de Pauta Pendente (Google Chat)

Instruções completas de **Google Cloud**, credenciais, Calendar e Chat estão em **[manual_google_integracao.md](manual_google_integracao.md)** — use este item como referência rápida de execução.

O script `scripts/notificador.py` notifica professores por mensagem direta no Google Chat quando houver pendencia de frequencia em aula com atraso maior/igual a 7 dias (regra: `data_aula + 7`).

### Requisitos de seguranca
- Nunca versionar JSON de credencial real no repositorio.
- Salvar o arquivo de service account em pasta protegida no servidor (exemplo Windows: `C:\\inetpub\\secrets\\google_chat_key.json`).
- Configurar permissao de leitura apenas para a conta de execucao do servico.

### Variaveis de ambiente
Adicionar no `.env` de producao:

```env
GOOGLE_CHAT_SERVICE_ACCOUNT_FILE=C:/inetpub/secrets/google_chat_key.json
GOOGLE_CHAT_SCOPES=https://www.googleapis.com/auth/chat.messages.create,https://www.googleapis.com/auth/chat.spaces
NOTIFICADOR_DIAS_ATRASO=7
NOTIFICADOR_DRY_RUN=false
NOTIFICADOR_LOG_LEVEL=INFO
```

### Execucao manual
No diretorio raiz do projeto:

```bash
python scripts/notificador.py --dry-run
python scripts/notificador.py
```

### Agendamento sugerido
- Windows Task Scheduler: executar 1 vez por dia (ex.: 07:00).
- Linux cron: `0 7 * * * /caminho/venv/bin/python /var/www/pauta-online/scripts/notificador.py`

### Observacoes operacionais
- O envio usa DM por e-mail do professor (`user.email`) no Google Chat.
- O script ignora turmas fora de vigencia (`hoje > data_fim`).
- Primeiro execute em `--dry-run` para validar o volume antes de ativar envio real.

---

## 4. Integração Google (Calendar e Chat) — manual completo

Para criar o projeto no Google Cloud, ativar APIs, compartilhar calendário com a conta de serviço, escopos, variáveis de ambiente e solução de problemas, consulte:

**[docs/manual_google_integracao.md](manual_google_integracao.md)**

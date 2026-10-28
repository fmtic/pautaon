# Uso: pwsh -NoProfile -File scripts/ensaio_shell.ps1  ->  abre um PowerShell filho com DATABASE_URL no banco de ensaio (pautaon_ensaio); use -Diagnostico para so conferir alvo e revisao.
#
# Objetivo: dar um terminal descartável que só enxerga o banco de ensaio (scratch), sem
# tocar no banco principal (`pautaon`). A sessão atual NÃO é alterada: a variável
# DATABASE_URL só existe dentro do processo filho iniciado no final.
#
# Regras de segurança:
#   * A DSN de origem vem de $env:DATABASE_URL (se existir) ou da linha DATABASE_URL do .env.
#   * Só o nome do banco é trocado na DSN crua (preserva credenciais e query string).
#   * O script recusa qualquer alvo cujo nome de banco não contenha "ensaio".
#   * A senha nunca é impressa: o alvo é exibido mascarado.
[CmdletBinding()]
param(
    [string]$Banco = "pautaon_ensaio",
    [string]$Python = "",
    [switch]$Diagnostico
)

$ErrorActionPreference = "Stop"

$Raiz = Split-Path -Parent $PSScriptRoot
$EnvFile = Join-Path $Raiz ".env"

function Mascarar-Dsn {
    param([string]$Dsn)
    # postgresql+psycopg://usuario:SENHA@host:porta/banco -> postgresql+psycopg://usuario:***@host:porta/banco
    return ($Dsn -replace '(://[^:/@]+:)[^@]*@', '$1***@')
}

function Ler-Dsn {
    param([string]$CaminhoEnv)
    if ($env:DATABASE_URL) {
        return $env:DATABASE_URL.Trim()
    }
    if (-not (Test-Path -LiteralPath $CaminhoEnv)) {
        throw "DATABASE_URL ausente no ambiente e $CaminhoEnv nao encontrado."
    }
    $linha = Get-Content -LiteralPath $CaminhoEnv |
        Where-Object { $_ -match '^\s*DATABASE_URL\s*=' } |
        Select-Object -Last 1
    if (-not $linha) {
        throw "Nenhuma linha DATABASE_URL ativa em $CaminhoEnv."
    }
    $valor = ($linha -replace '^\s*DATABASE_URL\s*=', '').Trim()
    return $valor.Trim('"').Trim("'")
}

function Trocar-Banco {
    param([string]$Dsn, [string]$NovoBanco)
    $corte = $Dsn.LastIndexOf('/')
    if ($corte -lt 0) {
        throw "DSN sem segmento de banco: $(Mascarar-Dsn $Dsn)"
    }
    $prefixo = $Dsn.Substring(0, $corte + 1)
    $resto = $Dsn.Substring($corte + 1)
    $query = ""
    $posQuery = $resto.IndexOf('?')
    if ($posQuery -ge 0) {
        $query = $resto.Substring($posQuery)
    }
    return $prefixo + $NovoBanco + $query
}

function Nome-Banco {
    param([string]$Dsn)
    $corte = $Dsn.LastIndexOf('/')
    $resto = $Dsn.Substring($corte + 1)
    $posQuery = $resto.IndexOf('?')
    if ($posQuery -ge 0) { return $resto.Substring(0, $posQuery) }
    return $resto
}

function Resolver-Python {
    param([string]$Informado, [string]$DiretorioRaiz)
    if ($Informado) { return $Informado }
    $venv = Join-Path $DiretorioRaiz ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venv) { return $venv }
    return "python"
}

$origem = Ler-Dsn -CaminhoEnv $EnvFile
if ($origem -notmatch '^postgresql') {
    throw "Este script so aceita DSN PostgreSQL (recebida: $(Mascarar-Dsn $origem))."
}

$alvo = Trocar-Banco -Dsn $origem -NovoBanco $Banco
$nomeBanco = Nome-Banco -Dsn $alvo
if ($nomeBanco -notmatch 'ensaio') {
    throw "Recusado: o banco de destino '$nomeBanco' nao contem 'ensaio'. Nada foi aberto."
}

$pythonExe = Resolver-Python -Informado $Python -DiretorioRaiz $Raiz

# Sonda somente-leitura da revisao aplicada (a DSN vai por argumento, nao por ambiente).
$sonda = @'
import sys

from sqlalchemy import create_engine, text

url = sys.argv[1]
try:
    engine = create_engine(url)
    with engine.connect() as conexao:
        versoes = [linha[0] for linha in conexao.execute(text("select version_num from alembic_version"))]
    print(", ".join(versoes) if versoes else "(alembic_version vazia)")
except Exception as exc:  # noqa: BLE001 - o shell deve abrir mesmo sem revisao legivel
    print(f"(nao foi possivel ler alembic_version: {type(exc).__name__})")
'@

$revisao = (& $pythonExe -c $sonda $alvo 2>&1 | Out-String).Trim()

Write-Host "Banco de ensaio : $(Mascarar-Dsn $alvo)"
Write-Host "Revisao alembic : $revisao"

if ($Diagnostico) {
    Write-Host "Modo diagnostico: nenhum shell filho foi aberto."
    return
}

Write-Host "Shell filho     : PowerShell novo; a sessao atual permanece intacta."
Write-Host ""

$alvoEscapado = $alvo -replace "'", "''"
$raizEscapada = $Raiz -replace "'", "''"
$filho = @"
`$env:DATABASE_URL = '$alvoEscapado'
Set-Location -LiteralPath '$raizEscapada'
Write-Host 'Ambiente pautaON em ENSAIO: $Banco' -ForegroundColor Yellow
Write-Host 'Sessao pai inalterada. Use exit para voltar.' -ForegroundColor DarkGray
"@

$pwshExe = (Get-Process -Id $PID).Path
& $pwshExe -NoLogo -NoProfile -NoExit -Command $filho

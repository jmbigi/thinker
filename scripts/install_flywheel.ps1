# Instala el gateway local de Flywheel y deja preparado el entorno para thinker.
# Uso:
#   .\scripts\install_flywheel.ps1              # solo revisa/instala (dry-run por defecto)
#   .\scripts\install_flywheel.ps1 -Run       # ejecuta los pasos de instalacion
#   .\scripts\install_flywheel.ps1 -Run -Debug # con salida detallada
#   .\scripts\install_flywheel.ps1 -Run -LogDir "C:\logs\flywheel"

param(
    [switch]$Run,
    [switch]$Debug,
    [string]$LogDir = "$env:TEMP\flywheel_install_logs"
)

$ErrorActionPreference = "Stop"

$script:steps = New-Object System.Collections.Generic.List[string]
function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] $msg"
    $script:steps.Add($msg)
}
function Log-Fail($msg) {
    Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] [FAIL] $msg" -ForegroundColor Red
    $script:steps.Add("FAIL: $msg")
}

# --- Preparar log ---
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogDir ("flywheel_install_" + $timestamp + ".log")
Start-Transcript -Path $logFile -Append | Out-Null
Log "Inicio script install_flywheel.ps1 (Run=$Run, Debug=$Debug)"
Log "Log: $logFile"

try {
    # --- Paso 1: comprobar si flywheel ya esta instalado ---
    Log "Comprobando si el comando 'flywheel' esta disponible..."
    $cmd = Get-Command flywheel -ErrorAction SilentlyContinue
    if ($cmd) {
        Log "Flywheel detectado: $($cmd.Source)"
        Log "Version: $((& flywheel --version) -join ' ' 2>$null)"
    } else {
        Log "Flywheel NO esta instalado."
        if ($Run) {
            Log "Intentando instalacion con winget..."
            $winget = Get-Command winget -ErrorAction SilentlyContinue
            if ($winget) {
                Log "winget encontrado. Instalando paquete Flywheel..."
                winget install --id "Flywheel.Flywheel" --silent --accept-source-agreements --accept-package-agreements 2>&1 | ForEach-Object { Log $_ }
            } else {
                Log-Fail "winget no esta disponible. Instala el binario Flywheel manualmente desde la fuente oficial."
            }
        } else {
            Log "Modo dry-run: no se ejecuto instalacion. Usa -Run para intentar la instalacion con winget."
        }
    }

    # --- Paso 2: tras intentar instalacion, comprobar de nuevo ---
    $cmd2 = Get-Command flywheel -ErrorAction SilentlyContinue
    if (-not $cmd2) {
        Log "No se pudo confirmar la instalacion automatica."
        Log "Pasos manuales: 1) descarga e instala Flywheel desde su fuente oficial; 2) ejecuta 'flywheel up'; 3) 'flywheel gateway-key create'; 4) define FLYWHEEL_GATEWAY_URL y FLYWHEEL_GATEWAY_KEY."
    } else {
        Log "Flywheel esta listo (version consultada)."
    }

    # --- Paso 3: recordar variables de entorno ---
    Log "Variables de entorno necesarias: FLYWHEEL_GATEWAY_URL (default http://127.0.0.1:8799/v1) y FLYWHEEL_GATEWAY_KEY (fwk_...)."

    Log "FIN OK"
    $final = 0
} catch {
    Log-Fail "Error durante la ejecucion: $($_.Exception.Message)"
    $final = 1
} finally {
    Stop-Transcript | Out-Null
}

if ($final -ne 0) { exit 1 }
exit 0

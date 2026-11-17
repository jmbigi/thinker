#!/usr/bin/env pwsh
# Test script para validar la integracion de Flywheel con thinker.
# Uso:
#   .\scripts\test_flywheel_integration.ps1              # solo revisa requisitos
#   .\scripts\test_flywheel_integration.ps1 -Run       # ejecuta tests reales (requiere Flywheel ejecutandose)
#   .\scripts\test_flywheel_integration.ps1 -Run -Debug # salida detallada

param(
    [switch]$Run,
    [switch]$Debug,
    [string]$LogDir = "$env:TEMP\test_flywheel_integration"
)

$ErrorActionPreference = "Stop"

$script:pasados = 0
$script:fallidos = 0

function Log($msg) {
    $ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    Write-Host "[$ts] $msg"
}

function TestCheck($nombre, $condicion, $detalle = "") {
    if ($condicion) {
        $script:pasados++
        Log "PASS: $nombre"
        return $true
    } else {
        $script:fallidos++
        Log "FAIL: $nombre - $detalle"
        return $false
    }
}

function Ejecutar($comando, $descripcion) {
    Log "EJECUTANDO: $descripcion"
    Log "  $comando"
    try {
        $resultado = & $comando 2>&1
        Log "  SALIDA: $resultado"
        return $true
    } catch {
        Log "  ERROR: $($_.Exception.Message)"
        return $false
    }
}

# --- Preparar log ---
if (-not (Test-Path -LiteralPath $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$logFile = Join-Path $LogDir ("test_flywheel_integration_" + $timestamp + ".log")
Start-Transcript -Path $logFile -Append | Out-Null
Log "=== INICIO test_flywheel_integration.ps1 (Run=$Run, Debug=$Debug) ==="
Log "Log: $logFile"

try {
    # --- Test 1: ¿Esta instalado flywheel? ---
    $cmdFlywheel = Get-Command flywheel -ErrorAction SilentlyContinue
    TestCheck "Flywheel instalado" ($null -ne $cmdFlywheel) "Ejecute install_flywheel.ps1 o instale Flywheel manualmente"

    # --- Test 2: ¿Esta ejecutandose el gateway? ---
    $gatewayUrl = $env:FLYWHEEL_GATEWAY_URL
    if (-not $gatewayUrl) { $gatewayUrl = "http://127.0.0.1:8799/v1" }
    $gatewayOk = $false
    if ($Run) {
        try {
            $respuesta = Invoke-WebRequest -Uri "$gatewayUrl/" -Method Get -TimeoutSec 5 -ErrorAction Stop
            $gatewayOk = $true
        } catch {
            $gatewayOk = $false
        }
    } else {
        Log "  (modo dry-run: no se consulta el gateway)"
    }
    TestCheck "Flywheel gateway responde en $gatewayUrl" $gatewayOk "Levante el gateway con 'flywheel up'"

    # --- Test 3: ¿Esta definida la clave? ---
    $gatewayKey = $env:FLYWHEEL_GATEWAY_KEY
    TestCheck "FLYWHEEL_GATEWAY_KEY definida" (-not [string]::IsNullOrEmpty($gatewayKey)) "Cree una clave con 'flywheel gateway-key create' y defina la variable"

    # --- Test 4: ¿Esta instalado thinker y disponible el comando research? ---
    $cmdResearch = Get-Command research -ErrorAction SilentlyContinue
    TestCheck "Comando 'research' disponible" ($null -ne $cmdResearch) "Instale thinker (pip install .) o desde fuente"

    # --- Test 5: Test de integracion real (requiere gateway activo y clave) ---
    if ($Run -and $gatewayOk -and -not [string]::IsNullOrEmpty($gatewayKey)) {
        $pregunta = "Cual es la capital de Espana?"
        $comando = "research --provider flywheel --flywheel-url '" + $gatewayUrl + "' --flywheel-key '" + $gatewayKey + "' '" + $pregunta + "'"
        $resultadoOk = Ejecutar $comando "Test de investigacion con Flywheel"
        if ($resultadoOk) {
            TestCheck "Respuesta obtenida de Flywheel" $true
        } else {
            TestCheck "Respuesta obtenida de Flywheel" $false "El comando research fallo"
        }
    } elseif ($Run) {
        Log "  (saltado test de integracion: falta gateway o clave)"
    } else {
        Log "  (modo dry-run: no se ejecuta test de integracion)"
    }

    # --- Resumen ---
    $total = $script:pasados + $script:fallidos
    Log "=== RESUMEN ==="
    Log "Tests pasados: $script:pasados / $total"
    Log "Tests fallidos: $script:fallidos / $total"
    if ($script:fallidos -gt 0) {
        Log "RESULTADO: CON FALLOS"
        $final = 1
    } else {
        Log "RESULTADO: TODO OK"
        $final = 0
    }
} catch {
    Log "ERROR no controlado: $($_.Exception.Message)"
    $final = 1
} finally {
    Stop-Transcript | Out-Null
}

if ($final -ne 0) { exit 1 }
exit 0

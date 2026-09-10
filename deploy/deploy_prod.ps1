# Deploy ApolloSupport v3.2.3 — frontend + backend
# Ejecutar en el SERVIDOR DE PRODUCCION (donde corre Apache + ApolloBackend).
# Desde dev: .\deploy\deploy_prod.ps1 -Server \\192.168.10.220

param(
    [string]$Server = "",           # ej. \\192.168.10.220  (vacío = local)
    [string]$FrontendRoot = "C:\Apache24\htdocs\apollosupport",
    [string]$BackendRoot  = "C:\ApolloSupport\backend",
    [string]$ServiceName = "ApolloBackend",
    [switch]$SkipBuild,
    [switch]$SkipBackendRestart
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path $PSScriptRoot -Parent
Set-Location $RepoRoot

function Resolve-DeployPath([string]$Path) {
    if ($Server) { return ($Server + "\C$\" + ($Path -replace ':\\','\' -replace '^\\','')) }
    return $Path
}

Write-Host "=== ApolloSupport Deploy ===" -ForegroundColor Cyan
Write-Host "Repo:     $RepoRoot"
Write-Host "Frontend: $(Resolve-DeployPath $FrontendRoot)"
Write-Host "Backend:  $(Resolve-DeployPath $BackendRoot)"
Write-Host ""

if (-not $SkipBuild) {
    Write-Host "[1/4] Build frontend..." -ForegroundColor Yellow
    Push-Location "$RepoRoot\frontend"
    if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
        throw "npm no encontrado. Instalar Node.js LTS o usar -SkipBuild."
    }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "npm run build fallo" }
    Pop-Location
    $ver = Get-Content "$RepoRoot\frontend\dist\version.txt" -Raw
    Write-Host "  dist/version.txt:`n$ver"
} else {
    Write-Host "[1/4] Build omitido (-SkipBuild)" -ForegroundColor DarkGray
}

Write-Host "[2/4] Copiar frontend dist..." -ForegroundColor Yellow
$feTarget = Resolve-DeployPath $FrontendRoot
New-Item -ItemType Directory -Force -Path $feTarget | Out-Null
robocopy "$RepoRoot\frontend\dist" $feTarget /MIR /R:2 /W:3 /NFL /NDL /NJH /NJS /NP
if ($LASTEXITCODE -ge 8) { throw "robocopy frontend fallo (exit $LASTEXITCODE)" }

Write-Host "[3/4] Copiar backend..." -ForegroundColor Yellow
$beTarget = Resolve-DeployPath $BackendRoot
New-Item -ItemType Directory -Force -Path $beTarget | Out-Null
$backendFiles = @(
    "main.py", "auth.py", "models.py", "schemas.py", "database.py",
    "requirements.txt", "erp_licensing.py", "audit_schema.py"
)
foreach ($f in $backendFiles) {
    $src = Join-Path "$RepoRoot\backend" $f
    if (Test-Path $src) {
        Copy-Item $src (Join-Path $beTarget $f) -Force
        Write-Host "  $f"
    }
}
New-Item -ItemType Directory -Force -Path "$beTarget\updates" | Out-Null
Copy-Item "$RepoRoot\backend\updates\version.json" "$beTarget\updates\version.json" -Force -ErrorAction SilentlyContinue
Copy-Item "$RepoRoot\backend\updates\ApolloSetup.exe" "$beTarget\updates\ApolloSetup.exe" -Force -ErrorAction SilentlyContinue
Copy-Item "$RepoRoot\backend\updates\ApolloSetup_x64.exe" "$beTarget\updates\ApolloSetup_x64.exe" -Force -ErrorAction SilentlyContinue
Copy-Item "$RepoRoot\backend\updates\ApolloSetup_x86.exe" "$beTarget\updates\ApolloSetup_x86.exe" -Force -ErrorAction SilentlyContinue

Write-Host "[4/4] Reiniciar backend..." -ForegroundColor Yellow
if ($SkipBackendRestart) {
    Write-Host "  Omitido (-SkipBackendRestart)" -ForegroundColor DarkGray
} elseif ($Server) {
    $result = sc.exe "\\$($Server.TrimStart('\'))" query $ServiceName 2>&1
    if ($LASTEXITCODE -eq 0) {
        sc.exe "\\$($Server.TrimStart('\'))" stop $ServiceName | Out-Null
        Start-Sleep -Seconds 3
        sc.exe "\\$($Server.TrimStart('\'))" start $ServiceName | Out-Null
        Write-Host "  Servicio $ServiceName reiniciado en $Server"
    } else {
        Write-Host "  AVISO: servicio $ServiceName no encontrado en $Server. Reiniciar manualmente." -ForegroundColor Red
    }
} else {
    $svc = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
    if ($svc) {
        Restart-Service $ServiceName -Force
        Write-Host "  Servicio $ServiceName reiniciado"
    } else {
        Write-Host "  AVISO: servicio $ServiceName no encontrado. Ejecutar: nssm restart $ServiceName" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "=== Verificacion ===" -ForegroundColor Green
Write-Host "  https://support.ultimate.net.ar/version.txt  -> version=3.2.2"
Write-Host "  https://support.ultimate.net.ar/api/version  -> 3.2.2"
Write-Host "  https://support.ultimate.net.ar/api/hq-test  -> 3.2.2"
Write-Host "  Navegador: Ctrl+Shift+R o incognito (purga SW)"
Write-Host ""

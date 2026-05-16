# Script de Instalación ApolloSupport Centinela como Servicio de Windows
# Descripción: Instala el agente de soporte para que se inicie automáticamente con Windows.

$ServiceName = "ApolloCentinela"
$PythonPath = "pythonw.exe" # Usa pythonw para ocultar la terminal
$ScriptPath = Join-Path (Get-Location) "centinela.py"

# Verificar si ya existe
if (Get-Service $ServiceName -ErrorAction SilentlyContinue) {
    Write-Host "El servicio ya existe. Deteniendo..." -ForegroundColor Yellow
    Stop-Service $ServiceName -ErrorAction SilentlyContinue
}

# Instalación mediante NSSM (Recomendado) o New-Service nativo
# Para New-Service nativo (requiere que el script maneje eventos de servicio)

Write-Host "--- Instalación de Apollo Centinela ---" -ForegroundColor Cyan
Write-Host "Paso 1: Asegúrese de tener instaladas las dependencias: pip install websockets pystray Pillow"
Write-Host "Paso 2: Instalando servicio nativo..."

# Nota: El script centinela.py debe estar diseñado para persistir. 
# Si el usuario tiene NSSM.exe en la carpeta, es mucho más estable:
if (Test-Path "nssm.exe") {
    .\nssm.exe install $ServiceName $PythonPath $ScriptPath
    .\nssm.exe set $ServiceName Description "Agente Centinela de ApolloSupport (Master IS)"
    .\nssm.exe start $ServiceName
    Write-Host "Servicio instalado y ejecutándose vía NSSM con éxito." -ForegroundColor Green
} else {
    Write-Host "No se encontró nssm.exe. Utilizando comando nativo (Limitado)..." -ForegroundColor Yellow
    New-Service -Name $ServiceName -BinaryPathName "$PythonPath $ScriptPath" -DisplayName "Apollo Centinela Agent" -StartupType Automatic
    Start-Service $ServiceName
    Write-Host "Servicio registrado como automático." -ForegroundColor Green
}

Write-Host "El agente ahora vivirá en la bandeja del sistema (Tray Icon)." -ForegroundColor Green

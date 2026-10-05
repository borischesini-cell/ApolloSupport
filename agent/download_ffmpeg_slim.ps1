# Descarga ffmpeg essentials (gyan.dev) y reemplaza agent\ffmpeg.exe
# El full build (~193 MB) se mueve a ffmpeg_full.bak.exe si existe.
$ErrorActionPreference = 'Stop'
$AgentDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ZipPath = Join-Path $AgentDir 'ffmpeg-essentials.zip'
$ExtractDir = Join-Path $AgentDir '_ffmpeg_essentials'
$Url = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'

Write-Host "[ffmpeg] Descargando essentials desde gyan.dev ..."
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
Invoke-WebRequest -Uri $Url -OutFile $ZipPath -UseBasicParsing

if (Test-Path $ExtractDir) { Remove-Item $ExtractDir -Recurse -Force }
Expand-Archive -Path $ZipPath -DestinationPath $ExtractDir -Force

$NewExe = Get-ChildItem -Path $ExtractDir -Filter 'ffmpeg.exe' -Recurse | Select-Object -First 1
if (-not $NewExe) { throw "No se encontro ffmpeg.exe dentro del zip essentials" }

$Dest = Join-Path $AgentDir 'ffmpeg.exe'
$Bak = Join-Path $AgentDir 'ffmpeg_full.bak.exe'
if (Test-Path $Dest) {
    $oldSize = (Get-Item $Dest).Length
    if ($oldSize -gt 120MB -and -not (Test-Path $Bak)) {
        Move-Item $Dest $Bak -Force
        Write-Host "[ffmpeg] Backup del full: $Bak ($([int]($oldSize/1MB)) MB)"
    } else {
        Remove-Item $Dest -Force
    }
}
Copy-Item $NewExe.FullName $Dest -Force
$newSize = (Get-Item $Dest).Length
Write-Host "[ffmpeg] Nuevo ffmpeg.exe: $([int]($newSize/1MB)) MB"

Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
Remove-Item $ExtractDir -Recurse -Force -ErrorAction SilentlyContinue
Write-Host "[ffmpeg] Listo."

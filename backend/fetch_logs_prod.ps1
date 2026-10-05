# Bitacora produccion — device 773 por defecto
param(
    [int]$DeviceId = 773,
    [int]$Limit = 150
)

$secret = if ($env:APOLLO_SECRET_KEY) { $env:APOLLO_SECRET_KEY } else { "apollo_super_secreto_para_master_is_2026_x" }

function B64Url([byte[]]$data) {
    [Convert]::ToBase64String($data).TrimEnd('=').Replace('+','-').Replace('/','_')
}

$headerJson = '{"alg":"HS256","typ":"JWT"}'
$exp = [int][double]::Parse((Get-Date -UFormat %s)) + 3600
$payloadJson = "{`"sub`":`"boris@ultimate.net.ar`",`"rol`":`"admin`",`"exp`":$exp}"
$header = B64Url([Text.Encoding]::UTF8.GetBytes($headerJson))
$payload = B64Url([Text.Encoding]::UTF8.GetBytes($payloadJson))
$hmac = New-Object System.Security.Cryptography.HMACSHA256
$hmac.Key = [Text.Encoding]::UTF8.GetBytes($secret)
$sig = B64Url($hmac.ComputeHash([Text.Encoding]::UTF8.GetBytes("$header.$payload")))
$token = "$header.$payload.$sig"

$url = "https://support.ultimate.net.ar/api/centinelas/logs?device_id=$DeviceId&limit=$Limit"
$headers = @{ Authorization = "Bearer $token" }

try {
    $logs = Invoke-RestMethod -Uri $url -Headers $headers -TimeoutSec 45
} catch {
    Write-Host "Error HTTP: $_"
    exit 1
}

Write-Host "=== Bitacora device $DeviceId | $($logs.Count) entradas ==="
Write-Host ""

$keywords = @('SESSION','SWITCH','login','TIMEOUT','HQ','WEBCODECS','FRONTEND','JMUXER','Reinicio','FFmpeg','agent_version','3.1.23')
$filtered = @($logs | Where-Object {
    $msg = $_.message
    ($keywords | Where-Object { $msg -match $_ }) -or $_.level -in @('ERROR','WARNING')
})

Write-Host "--- Filtradas ($($filtered.Count)) ---"
foreach ($l in ($filtered | Select-Object -Last 60)) {
    $m = $l.message
    if ($m.Length -gt 500) { $m = $m.Substring(0, 500) }
    Write-Host "[$($l.timestamp)] $($l.source) [$($l.level)]"
    Write-Host "  $m"
    Write-Host ""
}

if ($filtered.Count -eq 0) {
    Write-Host "sin coincidencias - ultimas 20 crudas"
    foreach ($l in ($logs | Select-Object -First 20)) {
        $m = $l.message
        if ($m.Length -gt 200) { $m = $m.Substring(0, 200) }
        Write-Host "[$($l.timestamp)] $($l.source) $m"
    }
}

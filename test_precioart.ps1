$body = '{"c":"0100037","cli":"0100054","lis":"28"}'

Write-Host "POST body: $body"

try {

  $r1 = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/api/precioart' -Method POST -ContentType 'application/json' -Body $body -TimeoutSec 8

  $r1 | ConvertTo-Json -Compress

  Write-Host ("pu={0} av={1} src={2} lis={3}" -f $r1.pu, $r1.av, $r1.src, $r1.lis)

} catch {

  Write-Host "POST ERROR: $($_.Exception.Message)"

}



Write-Host "GET query"

try {

  $r2 = Invoke-RestMethod -Uri 'http://127.0.0.1:8085/api/precioart?c=0100037&cli=0100054&lis=28' -Method GET -TimeoutSec 8

  $r2 | ConvertTo-Json -Compress

} catch {

  Write-Host "GET ERROR: $($_.Exception.Message)"

}


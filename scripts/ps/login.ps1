param(
  [string]$Email = "api-test@example.com",
  [string]$Password = "Test!12345",
  [string]$Base = "http://127.0.0.1:8000/api/v1"
)

# 1) JSON payload
$payload = @{ email = $Email; password = $Password } | ConvertTo-Json -Compress

# 2) BOM'suz UTF-8 dosya
$tmp = Join-Path $PWD "tmp-login.json"
[System.IO.File]::WriteAllText($tmp, $payload, [System.Text.UTF8Encoding]::new($false))

# 3) POST (body + HTTP kodu birlikte)
$resp = curl.exe -sS -H "Content-Type: application/json" --data-binary "@$tmp" `
  "$Base/auth/login" -w "`n%{http_code}`n"
$http = ($resp -split "`r?`n")[-1]
$body = ($resp -replace "`r?`n\d{3}$","")

if ($http -ne "200") {
  Write-Error "Login failed. HTTP $http`nBody:`n$body"
  switch ($http) {
    "401" { Write-Host "401 Unauthorized → E-posta/şifre hatalı veya kullanıcı yok." -ForegroundColor Yellow }
    "422" { Write-Host "422 Unprocessable Entity → JSON decode error (çoğunlukla BOM/format/quote)." -ForegroundColor Yellow }
    "500" { Write-Host "500 Internal Server Error → Sunucu istisnası; 'docker compose logs api' incele." -ForegroundColor Yellow }
  }
  exit 1
}

try {
  $tok = ($body | ConvertFrom-Json).access_token
} catch {
  Write-Error "JSON parse failed for 200 OK. Raw:`n$body"
  exit 2
}
if (-not $tok) {
  Write-Error "Token not found in response body."
  exit 3
}

Write-Host ("Token preview: Bearer {0}..." -f $tok.Substring(0, [Math]::Min(12, $tok.Length)))

# Yetkili çağrı ile doğrula
$pairsEndpoint = "$Base/pairs?limit=10&offset=0"
$pairsBody = curl.exe -sS -H ("Authorization: Bearer {0}" -f $tok) $pairsEndpoint
Write-Host ("Pairs body: {0}" -f $pairsBody)

curl.exe -sS -D - -o NUL -H ("Authorization: Bearer {0}" -f $tok) $pairsEndpoint |
  findstr /I "^x-total-count:"

# Alternatif: inline JSON → stdin (örnek, otomatik çalıştırmıyoruz)
Write-Host "Alt kullanım: '{\"email\":\"$Email\",\"password\":\"$Password\"}' | curl.exe -sS -H \"Content-Type: application/json\" --data-binary '@-' $Base/auth/login"

# Script output: token
$tok

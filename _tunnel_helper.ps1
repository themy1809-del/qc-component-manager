# Smart tunnel helper — capture URL, save to file, copy to clipboard
$ErrorActionPreference = "Continue"
Set-Location $PSScriptRoot

$urlSaved = $false

& .\cloudflared.exe tunnel --url http://localhost:8501 2>&1 | ForEach-Object {
    $line = $_.ToString()
    Write-Host $line

    if (-not $urlSaved -and $line -match 'https://[a-z0-9\-]+\.trycloudflare\.com') {
        $url = $matches[0]
        try {
            Set-Content -Path (Join-Path $PSScriptRoot 'URL_HIEN_TAI.txt') -Value $url -Encoding UTF8 -NoNewline
        } catch {}
        try {
            Set-Clipboard -Value $url
        } catch {}

        Write-Host ""
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host "   URL DA SAN SANG !" -ForegroundColor Green
        Write-Host ""
        Write-Host "   $url" -ForegroundColor Yellow
        Write-Host ""
        Write-Host "   ==> Da COPY vao clipboard - paste vao Zalo bang Ctrl+V" -ForegroundColor Cyan
        Write-Host "   ==> Da luu vao file: URL_HIEN_TAI.txt" -ForegroundColor Cyan
        Write-Host "============================================================" -ForegroundColor Green
        Write-Host ""
        $urlSaved = $true
    }
}

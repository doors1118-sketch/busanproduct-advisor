param(
    [string]$EnvPath = (Join-Path (Split-Path $PSScriptRoot -Parent) ".env"),
    [string]$Model = "gpt-5-mini"
)

$secure = Read-Host "OPENAI_API_KEY를 붙여넣고 Enter를 누르세요" -AsSecureString
$ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
try {
    $apiKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
}

if ([string]::IsNullOrWhiteSpace($apiKey)) {
    Write-Host "입력된 키가 없어 중단합니다."
    exit 1
}

$lines = @()
if (Test-Path $EnvPath) {
    $lines = Get-Content -Path $EnvPath -Encoding UTF8
}

$foundKey = $false
$foundModel = $false
$updated = foreach ($line in $lines) {
    if ($line -match '^OPENAI_API_KEY=') {
        $foundKey = $true
        "OPENAI_API_KEY=$apiKey"
    } elseif ($line -match '^OPENAI_MODEL=') {
        $foundModel = $true
        "OPENAI_MODEL=$Model"
    } else {
        $line
    }
}

if (-not $foundKey) {
    $updated += "OPENAI_API_KEY=$apiKey"
}
if (-not $foundModel) {
    $updated += "OPENAI_MODEL=$Model"
}

$updated | Set-Content -Path $EnvPath -Encoding UTF8
Write-Host "OPENAI_API_KEY와 OPENAI_MODEL 설정을 완료했습니다. 키 값은 표시하지 않았습니다."

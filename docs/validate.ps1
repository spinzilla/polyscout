# Run offline acceptance and preserve version-bound evidence inside the checkout.
$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location -LiteralPath $projectRoot
$env:UV_CACHE_DIR = Join-Path $projectRoot '.cache/uv'
$env:PIP_CACHE_DIR = Join-Path $projectRoot '.cache/pip'
$env:TMP = Join-Path $projectRoot '.tmp'
$env:TEMP = $env:TMP
$env:TMPDIR = $env:TMP
$env:PYTEST_DEBUG_TEMPROOT = $env:TMP
$env:UV_PYTHON_DOWNLOADS = 'never'
$env:UV_OFFLINE = 'true'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:NO_COLOR = '1'
$env:COLUMNS = '120'
$stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ') + '-' + [Guid]::NewGuid().ToString('N').Substring(0,8)
$evidenceRoot = Join-Path $projectRoot ('docs/validation/' + $stamp)
New-Item -ItemType Directory -Path $evidenceRoot | Out-Null
New-Item -ItemType Directory -Force -Path $env:TMP | Out-Null

# Invoke the required commands directly; do not use network-enabled test plugins.
& uv run pytest --tb=short 2>&1 | Tee-Object -FilePath (Join-Path $evidenceRoot 'pytest.txt')
if ($LASTEXITCODE -ne 0) { throw 'Offline pytest failed' }
& uv run polyscout --help 2>&1 | Tee-Object -FilePath (Join-Path $evidenceRoot 'help.txt')
if ($LASTEXITCODE -ne 0) { throw 'CLI help failed' }
& uv run polyscout research --help 2>&1 | Tee-Object -FilePath (Join-Path $evidenceRoot 'research-help.txt')
if ($LASTEXITCODE -ne 0) { throw 'Research help failed' }

$artifactPaths = @('pyproject.toml', 'uv.lock', 'README.md', '.gitignore', 'BLOCKED.md', 'docs/ARCHITECTURE.md', 'docs/validate.ps1')
$artifactPaths += @(Get-ChildItem -LiteralPath (Join-Path $projectRoot 'src'),(Join-Path $projectRoot 'tests') -Recurse -File -Filter '*.py' | ForEach-Object { $_.FullName.Substring($projectRoot.Length + 1).Replace('\','/') })
$hashes = @($artifactPaths | Sort-Object -Unique | ForEach-Object {
    [ordered]@{ path = $_; sha256 = (Get-FileHash -LiteralPath (Join-Path $projectRoot $_) -Algorithm SHA256).Hash.ToLowerInvariant() }
})
$hashes | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $evidenceRoot 'files.sha256.json') -Encoding UTF8
$metadata = [ordered]@{
    version = '0.1.0'
    verified_at_utc = [DateTime]::UtcNow.ToString('o')
    layer = 'offline mocks and actual local CLI help'
    actual_research_api_calls = 0
    real_environment = 'unverified'
    session_tokens_used = $null
    session_token_note = 'Agent session usage is not exposed; no estimate is claimed.'
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $evidenceRoot 'acceptance.json') -Encoding UTF8
Write-Output "Acceptance evidence: $evidenceRoot"

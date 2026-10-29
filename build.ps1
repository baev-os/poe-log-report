# Build through the project environment from any working directory.
param(
    [string]$Output = "",
    [ValidateRange(1, 256)]
    [int]$Jobs = 2
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$projectRoot = $PSScriptRoot
$python = Join-Path $projectRoot ".venv/Scripts/python.exe"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "The .venv environment was not found. Set it up as described in README.md."
}

if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = "build/standalone-$(Get-Date -Format 'yyyyMMdd-HHmmss')-$PID"
}

$temporary = Join-Path $projectRoot "build/tmp"
$environment = @{
    TMPDIR = $temporary
    TEMP = $temporary
    TMP = $temporary
    PYTHONDONTWRITEBYTECODE = "1"
    PYTHONUTF8 = "1"
    PYTHONIOENCODING = "utf-8"
}
$previousEnvironment = @{}
$previousEncoding = [Console]::OutputEncoding
$buildExitCode = 1
Push-Location -LiteralPath $projectRoot

try {
    foreach ($name in $environment.Keys) {
        $previousEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, "Process")
        [Environment]::SetEnvironmentVariable($name, $environment[$name], "Process")
    }

    [Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
    New-Item -ItemType Directory -Force -Path $temporary | Out-Null
    & $python -B scripts/build_desktop.py --output $Output --jobs $Jobs
    $buildExitCode = $LASTEXITCODE
}
finally {
    foreach ($name in $previousEnvironment.Keys) {
        [Environment]::SetEnvironmentVariable($name, $previousEnvironment[$name], "Process")
    }

    [Console]::OutputEncoding = $previousEncoding
    Pop-Location
}

exit $buildExitCode

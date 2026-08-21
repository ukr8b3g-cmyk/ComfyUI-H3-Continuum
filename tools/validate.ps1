param(
    [string]$Python = 'python',
    [string]$ComfyRoot = '',
    [switch]$SkipTests,
    [switch]$SkipRuntime
)

$ErrorActionPreference = 'Stop'
$repository = Split-Path -Parent $PSScriptRoot
Push-Location $repository
try {
    & $Python -m compileall -q .
    if ($LASTEXITCODE -ne 0) { throw 'compileall failed' }

    if (-not $SkipTests) {
        & $Python -m pytest -q
        if ($LASTEXITCODE -ne 0) { throw 'pytest failed' }
    }

    if (-not $SkipRuntime) {
        $arguments = @('tools/verify_runtime.py')
        if ($ComfyRoot) { $arguments += @('--comfy-root', $ComfyRoot) }
        & $Python @arguments
        if ($LASTEXITCODE -ne 0) { throw 'runtime verification failed' }
    }
}
finally {
    Pop-Location
}

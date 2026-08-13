param(
    [string]$ComfyUIRoot = "D:\StabilityMatrix\Data\Packages\ComfyUI_W"
)

$ErrorActionPreference = "Stop"
$source = (Resolve-Path $PSScriptRoot).Path
$customNodes = Join-Path $ComfyUIRoot "custom_nodes"
$destination = Join-Path $customNodes "ComfyUI-H3-Continuum"
$legacyDestination = Join-Path $customNodes "ComfyUI-H3-Continuum-Join"

if (-not (Test-Path $ComfyUIRoot -PathType Container)) {
    throw "ComfyUI root not found: $ComfyUIRoot"
}
if (-not (Test-Path (Join-Path $ComfyUIRoot "comfy") -PathType Container)) {
    throw "The selected folder does not look like a ComfyUI installation: $ComfyUIRoot"
}
New-Item -ItemType Directory -Force -Path $customNodes | Out-Null

if ([System.StringComparer]::OrdinalIgnoreCase.Equals($source, $destination)) {
    Write-Host "Already installed at: $destination"
    exit 0
}

$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
foreach ($old in @($destination, $legacyDestination)) {
    if ((Test-Path $old) -and -not [System.StringComparer]::OrdinalIgnoreCase.Equals($source, $old)) {
        $backup = "$old.backup-$stamp"
        Move-Item -LiteralPath $old -Destination $backup
        Write-Host "Existing installation moved to: $backup"
    }
}

New-Item -ItemType Directory -Force -Path $destination | Out-Null
$exclude = @(".git", ".pytest_cache", "__pycache__")
Get-ChildItem -LiteralPath $source -Force | Where-Object { $exclude -notcontains $_.Name } | ForEach-Object {
    Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force
}

$python = Join-Path $ComfyUIRoot "venv\Scripts\python.exe"
if (Test-Path $python) {
    & $python (Join-Path $destination "tools\verify_runtime.py") --comfy-root $ComfyUIRoot
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime verification failed. See the output above."
    }
} else {
    Write-Warning "venv Python was not found; installation was copied but runtime verification was skipped."
}

Write-Host "Installed H3 Continuum to: $destination"
Write-Host "Restart ComfyUI. If the browser cached the old frontend, use a hard reload."

param(
    [string]$ComfyUIRoot = 'D:\StabilityMatrix\Data\Packages\ComfyUI_W'
)

$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot 'gpu_diagnostic_node'
$customNodes = Join-Path $ComfyUIRoot 'custom_nodes'
$destination = Join-Path $customNodes 'H3_Continuum_GPU_Diagnostics'

if (-not (Test-Path -LiteralPath $source -PathType Container)) {
    throw "Diagnostic source was not found: $source"
}
if (-not (Test-Path -LiteralPath $customNodes -PathType Container)) {
    throw "ComfyUI custom_nodes directory was not found: $customNodes"
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
foreach ($name in @('__init__.py', 'capture.py', 'nodes.py', 'README.md')) {
    Copy-Item -LiteralPath (Join-Path $source $name) -Destination (Join-Path $destination $name) -Force
}

$sourceCount = (Get-ChildItem -LiteralPath $source -File).Count
$destinationCount = (Get-ChildItem -LiteralPath $destination -File).Count
if ($destinationCount -lt $sourceCount) {
    throw "Diagnostic install verification failed: $destinationCount < $sourceCount"
}

Write-Output "Installed standalone diagnostics: $destination"
Write-Output 'Restart ComfyUI before using the diagnostic node.'

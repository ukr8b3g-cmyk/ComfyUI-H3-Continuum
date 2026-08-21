param(
    [string]$Source = (Split-Path -Parent $PSScriptRoot),
    [string]$SnapshotRoot = 'D:\Codex\_snapshots\ComfyUI-H3-Continuum',
    [string]$Label = 'pre-change'
)

$ErrorActionPreference = 'Stop'
$sourcePath = (Resolve-Path -LiteralPath $Source).Path
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$safeLabel = $Label -replace '[^A-Za-z0-9._-]', '-'
$destination = Join-Path $SnapshotRoot "$safeLabel-$stamp"
$rootFull = [IO.Path]::GetFullPath($SnapshotRoot)
$destinationFull = [IO.Path]::GetFullPath($destination)

if (-not $destinationFull.StartsWith($rootFull, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Snapshot destination escaped the configured snapshot root.'
}

New-Item -ItemType Directory -Path $destination -Force | Out-Null
Get-ChildItem -LiteralPath $sourcePath -Force |
    Where-Object { $_.Name -ne '.git' } |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination $destination -Recurse -Force }

$sourceCount = (Get-ChildItem -LiteralPath $sourcePath -Recurse -Force -File |
    Where-Object { $_.FullName -notmatch '[\\/]\.git[\\/]' } |
    Measure-Object).Count
$destinationCount = (Get-ChildItem -LiteralPath $destination -Recurse -Force -File | Measure-Object).Count

if ($sourceCount -ne $destinationCount) {
    throw "Snapshot verification failed: source=$sourceCount destination=$destinationCount"
}

[pscustomobject]@{
    Source = $sourcePath
    Snapshot = $destination
    Files = $destinationCount
}

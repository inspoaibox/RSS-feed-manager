param(
    [Parameter(Mandatory=$true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
$sourceRepo = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$destinationRepo = [IO.Path]::GetFullPath($Destination)
if (Test-Path -LiteralPath $destinationRepo) { throw 'Destination must not exist.' }
if ($destinationRepo -eq $sourceRepo) { throw 'Choose a separate destination.' }
git -C $sourceRepo clone --mirror --no-hardlinks $sourceRepo $destinationRepo
if ($LASTEXITCODE -ne 0) { throw 'Mirror clone failed.' }
$excludedPaths = @(
    '.dotnet/', 'tmp_argos_pkg/', 'android/MRSS/.gradle/',
    'desktop/MRSS.Native/bin/', 'desktop/MRSS.Native/obj/', 'desktop/MRSS.Native/publish/',
    'desktop/MRSS.Native/installer-output/', 'desktop/MRSS/installer-output/',
    'backend/rss_manager.db.bak_20260611_215021', 'frontend/src/pages/SettingsPage.tsx.backup'
)
$filterArgs = @('git-filter-repo', '--force', '--invert-paths')
foreach ($excludedPath in $excludedPaths) { $filterArgs += @('--path', $excludedPath) }
Push-Location -LiteralPath $destinationRepo
try {
    uvx @filterArgs
    if ($LASTEXITCODE -ne 0) { throw 'History filtering failed; original repository is unchanged.' }
    git count-objects -vH
} finally {
    Pop-Location
}
Write-Output "Clean history preview: $destinationRepo. No remote changes were made."

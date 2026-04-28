# sync_from_dev.ps1
# Sync library-only content from refwindcycle dev workspace into biwipy repo.
# Usage: .\sync_from_dev.ps1 [-Commit] [-Push]
#   -Commit  : auto-commit after sync with a timestamped message
#   -Push    : push to GitHub after commit (implies -Commit)

param(
    [switch]$Commit,
    [switch]$Push
)

$ErrorActionPreference = "Stop"

$src  = "c:\Users\jacme\Nextcloud\Python Scripts\refwindcycle"
$dest = "c:\Users\jacme\Nextcloud\Python Scripts\biwipy"

Write-Host "=== biwipy sync from dev ===" -ForegroundColor Cyan
Write-Host "  src : $src"
Write-Host "  dest: $dest"

# Sync library package
Write-Host "`nSyncing refwindcycle/..." -ForegroundColor Yellow
robocopy "$src\refwindcycle" "$dest\refwindcycle" /MIR /XD __pycache__ /XF "*.pyc" "*.pyo" /NJH /NJS /NFL /NDL
if ($LASTEXITCODE -ge 8) { throw "robocopy failed with code $LASTEXITCODE" }

# Sync packaging and CI files
Write-Host "Syncing packaging files..." -ForegroundColor Yellow
Copy-Item -Force "$src\pyproject.toml" "$dest\pyproject.toml"
Copy-Item -Force "$src\README.md"      "$dest\README.md"
robocopy "$src\.github" "$dest\.github" /MIR /NJH /NJS /NFL /NDL
if ($LASTEXITCODE -ge 8) { throw "robocopy .github failed with code $LASTEXITCODE" }

# Sync docs/source (sans fichiers générés)
Write-Host "Syncing docs/source/..." -ForegroundColor Yellow
robocopy "$src\docs\source" "$dest\docs\source" /MIR /XD __pycache__ /XF "*.pyc" /NJH /NJS /NFL /NDL
if ($LASTEXITCODE -ge 8) { throw "robocopy docs failed with code $LASTEXITCODE" }

Write-Host "`nSync done." -ForegroundColor Green
git -C $dest status --short

if ($Push) { $Commit = $true }

if ($Commit) {
    $msg = "chore: sync from dev $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
    git -C $dest add .
    $changes = git -C $dest status --short
    if ($changes) {
        git -C $dest commit -m $msg
        Write-Host "Committed: $msg" -ForegroundColor Green
    } else {
        Write-Host "Nothing to commit." -ForegroundColor Gray
    }
}

if ($Push) {
    git -C $dest push origin main
    Write-Host "Pushed to GitHub." -ForegroundColor Green
}

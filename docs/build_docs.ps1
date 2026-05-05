# build_docs.ps1
# Documentation build script for Biwipy

param(
    [switch]$Clean,
    [switch]$Open
)

$ErrorActionPreference = "Stop"

$docs_root = Split-Path -Parent $MyInvocation.MyCommand.Path
$source_dir = "$docs_root\source"
$build_dir = "$docs_root\build"

if ($Clean) {
    Write-Host "Cleaning build directory..." -ForegroundColor Yellow
    if (Test-Path $build_dir) { Remove-Item -Recurse -Force $build_dir }
}

Write-Host "Building documentation..." -ForegroundColor Cyan
sphinx-build -b html "$source_dir" "$build_dir\html"

if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] Documentation built successfully!" -ForegroundColor Green
    Write-Host "  Output: $build_dir\html\" -ForegroundColor Gray
    Write-Host "  Index:  $build_dir\html\index.html" -ForegroundColor Gray
    
    if ($Open) {
        Write-Host "Opening in browser..." -ForegroundColor Cyan
        Start-Process "file:///$build_dir/html/index.html"
    }
} else {
    Write-Host "[FAILED] Build failed" -ForegroundColor Red
    exit 1
}

# build_docs.ps1
# Multi-language documentation build script for Biwipy

param(
    [ValidateSet('en', 'fr', 'all')][string]$Language = 'all',
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

# Ensure sphinx-intl is installed
Write-Host "Checking for Sphinx and sphinx-intl..." -ForegroundColor Cyan
pip show sphinx-intl >$null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "Installing sphinx-intl..." -ForegroundColor Yellow
    pip install sphinx-intl
}

function Build-Language {
    param([string]$Lang)
    
    $lang_dir = "$build_dir\html\$Lang"
    Write-Host "`nBuilding $Lang documentation..." -ForegroundColor Cyan
    
    sphinx-build -D language=$Lang -b html "$source_dir" $lang_dir
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "✓ Built: $lang_dir" -ForegroundColor Green
    } else {
        Write-Host "✗ Build failed for language: $Lang" -ForegroundColor Red
        exit 1
    }
}

if ($Language -eq 'all' -or $Language -eq 'en') {
    Build-Language 'en'
}

if ($Language -eq 'all' -or $Language -eq 'fr') {
    Build-Language 'fr'
}

# Create index page
$index_file = "$build_dir\html\index.html"
@'
<!DOCTYPE html>
<html>
<head>
    <title>Biwipy Documentation</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #333; }
        .languages { list-style: none; padding: 0; }
        .languages li { margin: 10px 0; }
        .languages a { font-size: 18px; text-decoration: none; color: #0066cc; }
        .languages a:hover { text-decoration: underline; }
    </style>
</head>
<body>
    <h1>Biwipy Documentation</h1>
    <p>Select a language:</p>
    <ul class="languages">
        <li><a href="en/index.html">🇬🇧 English</a></li>
        <li><a href="fr/index.html">🇫🇷 Français</a></li>
    </ul>
</body>
</html>
'@ | Set-Content $index_file

Write-Host "`n✓ Documentation built successfully!" -ForegroundColor Green
Write-Host "  Output: $build_dir\html\" -ForegroundColor Gray
Write-Host "  Index:  $index_file" -ForegroundColor Gray

if ($Open) {
    Write-Host "`nOpening in browser..." -ForegroundColor Cyan
    Start-Process "file:///$index_file"
}

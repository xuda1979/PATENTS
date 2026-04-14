# ============================================
# Patent LaTeX to PDF Compiler
# 专利LaTeX文档编译脚本
# ============================================

Write-Host ""
Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  量子安全门限签名专利 - LaTeX 编译器" -ForegroundColor Cyan
Write-Host "  QTS-Falcon Patent LaTeX Compiler" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""

# Set working directory
$latexDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $latexDir) {
    $latexDir = Get-Location
}
Set-Location $latexDir
Write-Host "Working directory: $latexDir" -ForegroundColor Gray

# Check if pdflatex is available
$pdflatex = Get-Command pdflatex -ErrorAction SilentlyContinue
$xelatex = Get-Command xelatex -ErrorAction SilentlyContinue

if (-not $pdflatex -and -not $xelatex) {
    Write-Host ""
    Write-Host "ERROR: LaTeX compiler not found!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install a LaTeX distribution:" -ForegroundColor Yellow
    Write-Host "  1. MiKTeX (Recommended for Windows):" -ForegroundColor White
    Write-Host "     https://miktex.org/download" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  2. TeX Live:" -ForegroundColor White
    Write-Host "     https://tug.org/texlive/" -ForegroundColor Gray
    Write-Host ""
    Write-Host "After installation, restart PowerShell and run this script again." -ForegroundColor Yellow
    exit 1
}

# Prefer XeLaTeX for better Chinese support
if ($xelatex) {
    $compiler = "xelatex"
    Write-Host "Using XeLaTeX (better Chinese support)" -ForegroundColor Green
} else {
    $compiler = "pdflatex"
    Write-Host "Using pdfLaTeX" -ForegroundColor Green
}

Write-Host ""

# Create output directory if not exists
if (-not (Test-Path "output")) {
    New-Item -ItemType Directory -Path "output" | Out-Null
    Write-Host "Created output directory" -ForegroundColor Gray
}

# Compile main document (run three times for TOC and references)
Write-Host "Compiling main.tex..." -ForegroundColor Yellow
Write-Host ""

$passes = @("Pass 1/3 (Initial)", "Pass 2/3 (References)", "Pass 3/3 (Final)")
$success = $true

foreach ($pass in $passes) {
    Write-Host "  $pass..." -ForegroundColor Gray
    
    $result = & $compiler -interaction=nonstopmode -output-directory=output main.tex 2>&1
    
    if ($LASTEXITCODE -ne 0) {
        # Check if it's a real error or just warnings
        $errors = $result | Select-String -Pattern "^!" -SimpleMatch
        if ($errors) {
            Write-Host "    Warning: Compilation issues detected" -ForegroundColor Yellow
        }
    }
}

# Check if PDF was created
$pdfPath = Join-Path $latexDir "output\main.pdf"
if (Test-Path $pdfPath) {
    $pdfSize = (Get-Item $pdfPath).Length / 1KB
    Write-Host ""
    Write-Host "============================================" -ForegroundColor Green
    Write-Host "  Compilation Successful!" -ForegroundColor Green
    Write-Host "============================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "Output file: $pdfPath" -ForegroundColor Cyan
    Write-Host "File size: $([math]::Round($pdfSize, 2)) KB" -ForegroundColor Cyan
    Write-Host ""
    
    # Copy to main output location
    $finalPdf = Join-Path $latexDir "..\专利申请_量子安全门限签名.pdf"
    Copy-Item $pdfPath $finalPdf -Force
    Write-Host "Copied to: $finalPdf" -ForegroundColor Green
    
} else {
    Write-Host ""
    Write-Host "ERROR: PDF file was not created!" -ForegroundColor Red
    Write-Host "Check output\main.log for details" -ForegroundColor Yellow
    $success = $false
}

Write-Host ""

# Ask to clean auxiliary files
$cleanup = Read-Host "Clean up auxiliary files? (y/n) [default: y]"
if ($cleanup -eq "" -or $cleanup -eq "y" -or $cleanup -eq "Y") {
    $auxFiles = @("*.aux", "*.log", "*.toc", "*.out", "*.fls", "*.fdb_latexmk", "*.synctex.gz")
    foreach ($pattern in $auxFiles) {
        Remove-Item -Path "output\$pattern" -ErrorAction SilentlyContinue
    }
    # Also clean sections folder
    Remove-Item -Path "sections\*.aux" -ErrorAction SilentlyContinue
    Write-Host "Auxiliary files cleaned." -ForegroundColor Green
}

Write-Host ""

# Ask to open PDF
if ($success) {
    $openPdf = Read-Host "Open PDF file? (y/n) [default: y]"
    if ($openPdf -eq "" -or $openPdf -eq "y" -or $openPdf -eq "Y") {
        Start-Process $pdfPath
    }
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green
Write-Host ""

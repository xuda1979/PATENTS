# Patent Document Compilation Script
# Convert LaTeX files to Word documents (.docx)
# Requires Pandoc: https://pandoc.org/installing.html

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Patent Document Compilation Script" -ForegroundColor Cyan
Write-Host "LaTeX to Word Converter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# Check if Pandoc is installed
$pandocPath = Get-Command pandoc -ErrorAction SilentlyContinue
if (-not $pandocPath) {
    Write-Host "`n[ERROR] Pandoc is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Please visit https://pandoc.org/installing.html to install Pandoc" -ForegroundColor Yellow
    Write-Host "Or run: winget install --source winget --exact --id JohnMacFarlane.Pandoc" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n[INFO] Pandoc found: $($pandocPath.Source)" -ForegroundColor Green

# Set paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $scriptDir "output"

# Create output directory
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
    Write-Host "[INFO] Created output directory: $outputDir" -ForegroundColor Green
}

# Define files to convert
$files = @(
    @{
        Source = "jiaodishu.tex"
        Output = "Patent_Technical_Disclosure.docx"
        Description = "Technical Disclosure Document"
    },
    @{
        Source = "jiansuo_baogao.tex"
        Output = "Prior_Art_Search_Report.docx"
        Description = "Prior Art Search Report"
    }
)

Write-Host "`nStarting conversion..." -ForegroundColor Cyan

$successCount = 0
$failCount = 0

foreach ($file in $files) {
    $sourcePath = Join-Path $scriptDir $file.Source
    $outputPath = Join-Path $outputDir $file.Output
    
    Write-Host "`n----------------------------------------" -ForegroundColor Gray
    Write-Host "Processing: $($file.Description)" -ForegroundColor White
    Write-Host "Source: $($file.Source)" -ForegroundColor Gray
    Write-Host "Output: $($file.Output)" -ForegroundColor Gray
    
    if (-not (Test-Path $sourcePath)) {
        Write-Host "[ERROR] Source file not found: $sourcePath" -ForegroundColor Red
        $failCount++
        continue
    }
    
    try {
        $pandocArgs = @(
            "-f", "latex",
            "-t", "docx",
            "-o", $outputPath,
            "--toc",
            "--toc-depth=3",
            $sourcePath
        )
        
        Write-Host "[RUN] pandoc $($pandocArgs -join ' ')" -ForegroundColor DarkGray
        
        & pandoc $pandocArgs
        
        if ($LASTEXITCODE -eq 0 -and (Test-Path $outputPath)) {
            $fileSize = (Get-Item $outputPath).Length
            Write-Host "[SUCCESS] Generated: $outputPath ($fileSize bytes)" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "[ERROR] Conversion failed" -ForegroundColor Red
            $failCount++
        }
    }
    catch {
        Write-Host "[ERROR] $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "Conversion completed" -ForegroundColor Cyan
Write-Host "Success: $successCount files" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "Failed: $failCount files" -ForegroundColor Red
}
Write-Host "Output directory: $outputDir" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# List generated files
Write-Host "`nGenerated files:" -ForegroundColor White
Get-ChildItem -Path $outputDir -Filter "*.docx" | ForEach-Object {
    Write-Host "  - $($_.Name) ($($_.Length) bytes)" -ForegroundColor Gray
}

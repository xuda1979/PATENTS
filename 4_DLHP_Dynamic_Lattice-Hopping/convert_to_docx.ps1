param(
    [string[]]$Files = @('交底书.tex','检索报告.tex')
)

$ErrorActionPreference = 'Stop'

# Check for pandoc
$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
if (-not $pandoc) {
    Write-Host "ERROR: pandoc not found. Install from https://pandoc.org/installing.html" -ForegroundColor Red
    exit 1
}

# Optional: path to a reference .docx for styling (margins, fonts, heading styles)
# Create one by: pandoc -o reference.docx --print-default-data-file reference.docx
# Then edit reference.docx in Word to set your preferred styles.
$refDoc = Join-Path $PSScriptRoot 'reference.docx'
$useRef = Test-Path $refDoc

foreach ($f in $Files) {
    if (-not (Test-Path $f)) {
        Write-Host "SKIP: $f not found" -ForegroundColor Yellow
        continue
    }
    $outName = [System.IO.Path]::ChangeExtension($f, '.docx')

    Write-Host "`n=== Converting $f -> $outName ===" -ForegroundColor Cyan

    # Build pandoc arguments
    $args = @(
        $f                          # input
        '-o', $outName              # output
        '-f', 'latex'               # from LaTeX
        '-t', 'docx'               # to DOCX
        '--wrap=none'               # don't wrap lines
        '--toc'                     # include table of contents
        '--number-sections'         # number sections like LaTeX
        # Preserve math as OMML (native Word math) — best quality
    )

    if ($useRef) {
        $args += '--reference-doc'
        $args += $refDoc
        Write-Host "  Using reference style: $refDoc"
    }

    try {
        & pandoc @args 2>&1
        if ($LASTEXITCODE -eq 0) {
            $size = (Get-Item $outName).Length / 1KB
            Write-Host "  OK: $outName ({0:N0} KB)" -f $size -ForegroundColor Green
        } else {
            Write-Host "  WARN: pandoc returned exit code $LASTEXITCODE" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "  ERROR: $_" -ForegroundColor Red
    }
}

Write-Host "`n--- Done ---" -ForegroundColor Cyan
Write-Host @"

Tips for best quality:
  1. Math renders as native Word equations (OMML) - editable in Word
  2. To customize fonts/margins, create a reference.docx:
       pandoc -o reference.docx --print-default-data-file reference.docx
     Edit it in Word (set font to SimSun/SimHei, margins, heading styles),
     then re-run this script — it will auto-detect reference.docx
  3. For tikz/pgf figures, pre-render to PNG/PDF and \includegraphics them
  4. Tables may need minor width adjustments in Word
"@

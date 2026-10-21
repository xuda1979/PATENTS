Write-Host "Compiling Patent Documents..." -ForegroundColor Cyan

$fileMap = @{
    "交底书" = "temp_jiaodishu"
    "检索报告" = "temp_jiansuobaogao"
}

$compiler = "xelatex"
$latexDir = "c:\Users\Lenovo\patents\5_QTS-Falcon_Threshold_Signature\latex"

Set-Location $latexDir

if (-not (Get-Command $compiler -ErrorAction SilentlyContinue)) {
    Write-Error "xelatex not found."
    exit 1
}

New-Item -ItemType Directory -Path "output" -ErrorAction SilentlyContinue | Out-Null

foreach ($name in $fileMap.Keys) {
    $tempName = $fileMap[$name]
    Write-Host "Preparing to compile $name ($tempName)..." -ForegroundColor Yellow
    
    # Copy to temp file to avoid encoding issues with xelatex filename handling
    Copy-Item "$name.tex" "$tempName.tex" -Force
    
    # Compile
    for ($i=1; $i -le 2; $i++) {
        Write-Host "  Pass $i..." -ForegroundColor Gray
        $process = Start-Process -FilePath "cmd" -ArgumentList "/c $compiler -interaction=nonstopmode -output-directory=output `"$tempName.tex`"" -Wait -PassThru -NoNewWindow
    }
    
    $logFile = "output\$tempName.log"
    $hasError = $false
    
    if (Test-Path $logFile) {
        $content = Get-Content $logFile
        $errors = $content | Select-String "^!"
        if ($errors) {
            Write-Host "$name had errors during compilation:" -ForegroundColor Red
            $errors | ForEach-Object { Write-Host $_.Line -ForegroundColor Red }
            $hasError = $true
        } else {
             $warnings = $content | Select-String "Warning:"
             if ($warnings) {
                 Write-Host "$name compiled with warnings:" -ForegroundColor Yellow
                 $warnings | Select-Object -First 5 | ForEach-Object { Write-Host $_.Line -ForegroundColor Yellow }
             } else {
                 Write-Host "$name compiled successfully clean." -ForegroundColor Green
             }
        }
    }
    
    if (Test-Path "output\$tempName.pdf") {
         $finalPdf = "output\$name.pdf"
         Copy-Item "output\$tempName.pdf" $finalPdf -Force
         if (-not $hasError) {
            Write-Host "Generated: $finalPdf" -ForegroundColor Green
         }
    }
    
    # Cleanup temp tex
    Remove-Item "$tempName.tex" -ErrorAction SilentlyContinue
    # Cleanup temp output files
    Remove-Item "output\$tempName.*" -Exclude "*.pdf" -ErrorAction SilentlyContinue
    
    Write-Host ""
}

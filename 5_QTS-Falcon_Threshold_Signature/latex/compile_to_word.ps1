# 专利文档编译脚本
# 将 LaTeX 文件转换为 Word 文档 (.docx)
# 需要安装 Pandoc: https://pandoc.org/installing.html

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "专利文档编译脚本" -ForegroundColor Cyan
Write-Host "LaTeX to Word Converter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 检查 Pandoc 是否安装
$pandocPath = Get-Command pandoc -ErrorAction SilentlyContinue
if (-not $pandocPath) {
    Write-Host "`n[错误] Pandoc 未安装或不在 PATH 中" -ForegroundColor Red
    Write-Host "请访问 https://pandoc.org/installing.html 安装 Pandoc" -ForegroundColor Yellow
    Write-Host "或运行: winget install --source winget --exact --id JohnMacFarlane.Pandoc" -ForegroundColor Yellow
    exit 1
}

Write-Host "`n[信息] Pandoc 已找到: $($pandocPath.Source)" -ForegroundColor Green

# 设置路径
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDir = Join-Path $scriptDir "output"

# 创建输出目录
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
    Write-Host "[信息] 创建输出目录: $outputDir" -ForegroundColor Green
}

# 定义要转换的文件
$files = @(
    @{
        Source = "交底书.tex"
        Output = "专利技术交底书.docx"
        Description = "技术交底书 (Patent Technical Disclosure)"
    },
    @{
        Source = "检索报告.tex"
        Output = "现有技术检索报告.docx"
        Description = "检索报告 (Prior Art Search Report)"
    }
)

Write-Host "`n开始转换文件..." -ForegroundColor Cyan

$successCount = 0
$failCount = 0

foreach ($file in $files) {
    $sourcePath = Join-Path $scriptDir $file.Source
    $outputPath = Join-Path $outputDir $file.Output
    
    Write-Host "`n----------------------------------------" -ForegroundColor Gray
    Write-Host "处理: $($file.Description)" -ForegroundColor White
    Write-Host "源文件: $($file.Source)" -ForegroundColor Gray
    Write-Host "输出: $($file.Output)" -ForegroundColor Gray
    
    if (-not (Test-Path $sourcePath)) {
        Write-Host "[错误] 源文件不存在: $sourcePath" -ForegroundColor Red
        $failCount++
        continue
    }
    
    try {
        # 使用 Pandoc 转换 LaTeX 到 Word
        # 参数说明:
        # -f latex: 输入格式为 LaTeX
        # -t docx: 输出格式为 Word
        # --toc: 生成目录
        # --reference-doc: 使用参考样式文档（如果有）
        
        $pandocArgs = @(
            "-f", "latex",
            "-t", "docx",
            "-o", $outputPath,
            "--toc",
            "--toc-depth=3",
            $sourcePath
        )
        
        Write-Host "[运行] pandoc $($pandocArgs -join ' ')" -ForegroundColor DarkGray
        
        & pandoc $pandocArgs
        
        if ($LASTEXITCODE -eq 0 -and (Test-Path $outputPath)) {
            $fileSize = (Get-Item $outputPath).Length
            Write-Host "[成功] 已生成: $outputPath ($fileSize bytes)" -ForegroundColor Green
            $successCount++
        } else {
            Write-Host "[错误] 转换失败" -ForegroundColor Red
            $failCount++
        }
    }
    catch {
        Write-Host "[错误] $($_.Exception.Message)" -ForegroundColor Red
        $failCount++
    }
}

Write-Host "`n========================================" -ForegroundColor Cyan
Write-Host "转换完成" -ForegroundColor Cyan
Write-Host "成功: $successCount 个文件" -ForegroundColor Green
if ($failCount -gt 0) {
    Write-Host "失败: $failCount 个文件" -ForegroundColor Red
}
Write-Host "输出目录: $outputDir" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# 列出生成的文件
Write-Host "`n生成的文件列表:" -ForegroundColor White
Get-ChildItem -Path $outputDir -Filter "*.docx" | ForEach-Object {
    Write-Host "  - $($_.Name) ($($_.Length) bytes)" -ForegroundColor Gray
}

Write-Host "`n[提示] 如果需要更好的格式，可以：" -ForegroundColor Yellow
Write-Host "  1. 使用 Word 打开生成的文件" -ForegroundColor Yellow
Write-Host "  2. 调整样式和格式" -ForegroundColor Yellow
Write-Host "  3. 确保表格和公式正确显示" -ForegroundColor Yellow

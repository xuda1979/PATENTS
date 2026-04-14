param(
    [string[]]$Files = @()
)

$ErrorActionPreference = 'Stop'

function Get-TexCommand {
    $candidates = @('xelatex','latexmk','lualatex','pdflatex')
    foreach ($cmd in $candidates) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($null -ne $found) { return $cmd }
    }
    return $null
}

function New-UnicodeString {
    param(
        [int[]]$CodePoints
    )

    return (-join ($CodePoints | ForEach-Object { [char]$_ }))
}

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $root) {
    $root = Get-Location
}
Set-Location $root

$miktexRoot = Join-Path $root ".miktex-local"
$dirs = @(
    (Join-Path $miktexRoot "config"),
    (Join-Path $miktexRoot "data"),
    (Join-Path $miktexRoot "install"),
    (Join-Path $miktexRoot "cache"),
    (Join-Path $miktexRoot "temp")
)

foreach ($dir in $dirs) {
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

$env:MIKTEX_USERCONFIG = $dirs[0]
$env:MIKTEX_USERDATA = $dirs[1]
$env:MIKTEX_USERINSTALL = $dirs[2]
$env:TEMP = $dirs[4]
$env:TMP = $dirs[4]

$texCmd = Get-TexCommand
if (-not $texCmd) {
    Write-Host 'No LaTeX engine found (xelatex/pdflatex/lualatex/latexmk).'
    exit 2
}

Write-Host "Using LaTeX command: $texCmd"

if (-not $Files -or $Files.Count -eq 0) {
    $preferredOrder = @(
        (New-UnicodeString @(0x4EA4, 0x5E95, 0x4E66, 0x002E, 0x0074, 0x0065, 0x0078)),
        (New-UnicodeString @(0x68C0, 0x7D22, 0x62A5, 0x544A, 0x002E, 0x0074, 0x0065, 0x0078)),
        (New-UnicodeString @(0x6743, 0x5229, 0x8981, 0x6C42, 0x4E66, 0x002E, 0x0074, 0x0065, 0x0078)),
        (New-UnicodeString @(0x6743, 0x5229, 0x8981, 0x6C42, 0x4E66, 0x005F, 0x5BA1, 0x67E5, 0x7A33, 0x7248, 0x002E, 0x0074, 0x0065, 0x0078)),
        (New-UnicodeString @(0x6458, 0x8981, 0x002E, 0x0074, 0x0065, 0x0078)),
        (New-UnicodeString @(0x8BF4, 0x660E, 0x4E66, 0x002E, 0x0074, 0x0065, 0x0078))
    )

    $remaining = @(
        Get-ChildItem -File -Filter *.tex |
            Where-Object { $_.Name -notin $preferredOrder } |
            Sort-Object Name |
            ForEach-Object { $_.Name }
    )

    $Files = @($preferredOrder + $remaining | Where-Object { Test-Path $_ })
}

foreach ($f in $Files) {
    if (-not (Test-Path $f)) {
        Write-Host "Skipping missing file: $f"
        continue
    }

    Write-Host "`n=== Building $f ==="

    if ($texCmd -eq 'latexmk') {
        & latexmk -xelatex -interaction=nonstopmode -halt-on-error $f
        if ($LASTEXITCODE -ne 0) { throw "Build failed for $f" }
    } else {
        & $texCmd -interaction=nonstopmode -halt-on-error $f
        if ($LASTEXITCODE -ne 0) { throw "Build failed for $f" }
        & $texCmd -interaction=nonstopmode -halt-on-error $f
        if ($LASTEXITCODE -ne 0) { throw "Build failed for $f" }
    }
}

Write-Host "`nDone."

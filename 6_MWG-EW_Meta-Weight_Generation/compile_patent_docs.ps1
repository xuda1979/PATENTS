$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
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

# Prevent first-run update checks from blocking compilation and allow package installation if needed.
initexmf --set-config-value="[MPM]AutoCheckUpdates=0"
initexmf --set-config-value="[MPM]AutoUpdate=0"
initexmf --enable-installer

$docs = Get-ChildItem -File -Filter *.tex |
    Where-Object { $_.Name -notlike '__*' } |
    Sort-Object Name |
    Select-Object -ExpandProperty Name

foreach ($doc in $docs) {
    pdflatex -interaction=nonstopmode -halt-on-error $doc
    pdflatex -interaction=nonstopmode -halt-on-error $doc
}

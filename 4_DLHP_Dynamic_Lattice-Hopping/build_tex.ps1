param(
    [string[]]$Files = @('algorithms.tex','math_proofs.tex','symbols.tex')
)

# Allow passing a single comma-separated string (common in some invocations)
$Files = @($Files | ForEach-Object { $_ -split '\s*,\s*' } | Where-Object { $_ -and $_.Trim() -ne '' } | ForEach-Object { $_.Trim() })

$ErrorActionPreference = 'Stop'

function Get-TexCommand {
    # Prefer direct engines first because MiKTeX's latexmk frequently depends on Perl,
    # which may not be installed on Windows.
    $candidates = @('pdflatex','xelatex','lualatex','latexmk')
    foreach ($cmd in $candidates) {
        $found = Get-Command $cmd -ErrorAction SilentlyContinue
        if ($null -ne $found) { return $cmd }
    }
    return $null
}

$texCmd = Get-TexCommand
if (-not $texCmd) {
    Write-Host 'No LaTeX engine found (latexmk/pdflatex/xelatex/lualatex). Install MiKTeX or TeX Live, then rerun.'
    exit 2
}

Write-Host "Using LaTeX command: $texCmd"

foreach ($f in $Files) {
    if (-not (Test-Path $f)) {
        Write-Host "Skipping missing file: $f"
        continue
    }

    Write-Host "\n=== Building $f ==="

    if ($texCmd -eq 'latexmk') {
        try {
            & latexmk -pdf -interaction=nonstopmode -halt-on-error $f
        } catch {
            Write-Host "latexmk failed (often due to missing Perl on Windows MiKTeX)."
            Write-Host "Falling back to a direct LaTeX engine if available."

            $fallbackCandidates = @('pdflatex','xelatex','lualatex')
            $fallback = $null
            foreach ($c in $fallbackCandidates) {
                $cmd = Get-Command $c -ErrorAction SilentlyContinue
                if ($null -ne $cmd) { $fallback = $c; break }
            }

            if (-not $fallback) {
                throw
            }

            Write-Host "Using fallback engine: $fallback"
            & $fallback -interaction=nonstopmode -halt-on-error $f
            & $fallback -interaction=nonstopmode -halt-on-error $f
        }
    } else {
        # Two passes helps resolve cross-refs.
        & $texCmd -interaction=nonstopmode -halt-on-error $f
        & $texCmd -interaction=nonstopmode -halt-on-error $f
    }
}

Write-Host "\nDone."

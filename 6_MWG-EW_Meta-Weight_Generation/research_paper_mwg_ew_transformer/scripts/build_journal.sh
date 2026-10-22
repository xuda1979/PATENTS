#!/usr/bin/env bash
set -euo pipefail
project_root=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
python_bin=${PYTHON_BIN:-python3}
build_root=${MWG_BUILD_ROOT:-/tmp/mwg-journal-build}
cd "$project_root"
"$python_bin" scripts/audit_journal_evidence.py --tables
"$python_bin" scripts/make_journal_figures.py
for format in article tmlr; do
  if [[ "$format" == article ]]; then
    source_dir="$project_root/paper"
    document=main
  else
    source_dir="$project_root/paper/tmlr"
    document=main_tmlr
  fi
  output_dir="$build_root/$format"
  mkdir -p "$output_dir"
  (
    cd "$source_dir"
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$output_dir" "$document.tex" > "$output_dir/build.log"
    (
      cd "$output_dir"
      BIBINPUTS="$project_root/paper:" BSTINPUTS="$source_dir:" bibtex "$document" >> build.log
    )
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$output_dir" "$document.tex" >> "$output_dir/build.log"
    pdflatex -interaction=nonstopmode -halt-on-error -output-directory "$output_dir" "$document.tex" >> "$output_dir/build.log"
    if rg -q 'undefined|multiply defined|Overfull|LaTeX Error' "$output_dir/$document.log"; then
      rg -n 'undefined|multiply defined|Overfull|LaTeX Error' "$output_dir/$document.log"
      exit 1
    fi
    cp "$output_dir/$document.pdf" "$source_dir/$document.pdf"
  )
  printf 'Built %s\n' "$source_dir/$document.pdf"
done

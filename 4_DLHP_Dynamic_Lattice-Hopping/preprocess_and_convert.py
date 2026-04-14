#!/usr/bin/env python3
"""
Preprocess LaTeX files for pandoc conversion to high-quality DOCX.

Pandoc 2.x has trouble with certain LaTeX constructs:
  - \mathtt{"string"} — literal double-quotes inside math
  - \DeclareMathOperator and custom macros
  - CJK-specific packages (ctex, CJKutf8)
  - tikz/algorithm environments (no DOCX equivalent)
  - longtable column widths sometimes lost

This script creates a cleaned _pandoc.tex copy, then calls pandoc.
"""

import re
import subprocess
import sys
import os
import shutil

WORKSPACE = os.path.dirname(os.path.abspath(__file__))

# ---- Preprocessing rules -----------------------------------------------

def preprocess_latex(src: str) -> str:
    """Apply all fixups to LaTeX source string."""

    # 1. Replace \mathtt{"..."} with \texttt{...} outside math,
    #    or just remove the inner quotes to avoid pandoc choking.
    #    Pattern: \mathtt{"some text"}  →  \text{some\_text}
    def fix_mathtt_quotes(m):
        inner = m.group(1)
        # escape underscores for text mode if not already
        return r'\text{' + inner + '}'

    src = re.sub(
        r'\\mathtt\{["\u201c]([^""\u201d]*)["\u201d]\}',
        fix_mathtt_quotes,
        src,
    )

    # 2. Also handle bare "..." inside \text{} / \mathtt{} that pandoc
    #    might still choke on (e.g. \text{"ratchet"})
    def fix_text_quotes(m):
        cmd = m.group(1)
        inner = m.group(2)
        return '\\' + cmd + '{' + inner + '}'

    src = re.sub(
        r'\\(text|mathtt|texttt)\{["\u201c]([^""\u201d]*)["\u201d]\}',
        fix_text_quotes,
        src,
    )

    # 2b. Handle bare "string" inside math $...$ — replace with \text{string}
    #     e.g. $...,\ "ratchet")$  →  $...,\ \text{ratchet})$
    #     Only match inside $...$ inline math to avoid touching prose text
    def fix_math_quotes(m):
        math_content = m.group(1)
        # Replace "word" with \text{word} inside the math
        fixed = re.sub(r'"(\w+)"', r'\\text{\1}', math_content)
        return '$' + fixed + '$'

    src = re.sub(r'\$([^$]+)\$', fix_math_quotes, src)

    # 3. Remove \DeclareMathOperator lines FIRST (before expanding macros)
    src = re.sub(r'\\DeclareMathOperator\{[^}]*\}\{[^}]*\}\s*\n?', '', src)

    # 4. Remove \newcommand / \renewcommand definition LINES BEFORE expanding macros
    #    Must happen before \SeqID replacement to avoid \newcommand{\text{SeqID}}
    #    Match entire line including trailing % comments
    src = re.sub(r'^\\newcommand\{[^}]*\}.*$\n?', '', src, flags=re.MULTILINE)

    # 5. Replace \SeqID (custom macro) with \text{SeqID}
    src = src.replace(r'\SeqID', r'\text{SeqID}')
    # Replace \HPC with \mathcal{C}
    src = src.replace(r'\HPC', r'\mathcal{C}')

    # 6. Replace any remaining custom operators that were declared
    #    \HKDF, \KDF etc. — wrap in \text{}
    for op in ['HKDF', 'KDF', 'PRF', 'MAC', 'AEAD', 'Enc', 'Dec',
               'Sign', 'Verify', 'KEM', 'Encaps', 'Decaps']:
        src = src.replace(f'\\{op}', f'\\text{{{op}}}')

    # 7. Remove tikzpicture environments (no DOCX equivalent)
    #    Replace with a placeholder note
    src = re.sub(
        r'\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}',
        r'\\textit{[Diagram — see PDF version]}',
        src,
        flags=re.DOTALL,
    )

    # 7. Remove algorithm/algorithmic environments — replace with verbatim-like
    src = re.sub(
        r'\\begin\{algorithm\}.*?\\end\{algorithm\}',
        r'\\textit{[Algorithm pseudocode — see PDF version]}',
        src,
        flags=re.DOTALL,
    )

    # 8. Remove remaining \renewcommand{\arraystretch}{...}
    src = re.sub(r'\\renewcommand\{\\arraystretch\}\{[^}]*\}', '', src)

    # 9. Replace \bigstar with Unicode ★
    src = src.replace(r'\bigstar', '★')
    src = src.replace(r'$\bigstar$', '★')
    src = src.replace(r'$★$', '★')

    # 10. Handle \textbf inside longtable headers with \newline
    #     pandoc handles \newline poorly in tables — replace with space
    #     (only inside table cells, heuristic: lines with & and \newline)
    def fix_table_newlines(line):
        if '&' in line and r'\newline' in line:
            return line.replace(r'\newline', ' ')
        return line

    src = '\n'.join(fix_table_newlines(l) for l in src.split('\n'))

    # 11. colortbl \cellcolor — remove (no equivalent)
    src = re.sub(r'\\cellcolor\{[^}]*\}', '', src)
    src = re.sub(r'\\rowcolor\{[^}]*\}', '', src)

    # 12. Remove \fancyhdr commands
    for cmd in ['\\pagestyle{fancy}', '\\fancyhf{}']:
        src = src.replace(cmd, '')
    src = re.sub(r'\\[lr]head\{[^}]*\}', '', src)
    src = re.sub(r'\\[lr]foot\{[^}]*\}', '', src)
    src = re.sub(r'\\cfoot\{[^}]*\}', '', src)
    src = re.sub(r'\\renewcommand\{\\headrulewidth\}\{[^}]*\}', '', src)

    # 13. Remove CJK font selection commands that pandoc doesn't handle
    src = re.sub(r'\\setCJK(main|sans|mono)font\{[^}]*\}', '', src)
    src = re.sub(r'\\set(main|sans|mono)font\{[^}]*\}', '', src)

    # 14. Ensure pandoc can handle \section* — keep as-is (pandoc knows them)

    # 15. Fix \textit{注：...} that might span multiple lines — should be fine

    return src


def convert_file(tex_path: str, ref_docx: str = None):
    """Preprocess a .tex file and convert to .docx via pandoc."""
    base = os.path.splitext(tex_path)[0]
    pandoc_tex = base + '_pandoc.tex'
    out_docx = base + '.docx'

    print(f'\n{"="*60}')
    print(f'  Converting: {tex_path} -> {out_docx}')
    print(f'{"="*60}')

    # Read source
    with open(tex_path, 'r', encoding='utf-8') as f:
        src = f.read()

    # Preprocess
    cleaned = preprocess_latex(src)

    # Write preprocessed copy
    with open(pandoc_tex, 'w', encoding='utf-8') as f:
        f.write(cleaned)
    print(f'  Preprocessed: {pandoc_tex}')

    # Build pandoc command
    cmd = [
        'pandoc',
        pandoc_tex,
        '-o', out_docx,
        '-f', 'latex',
        '-t', 'docx',
        '--wrap=none',
    ]

    if ref_docx and os.path.isfile(ref_docx):
        cmd += ['--reference-doc', ref_docx]
        print(f'  Using reference style: {ref_docx}')

    print(f'  Running: {" ".join(cmd)}')
    result = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8')

    if result.stderr:
        # Filter out common non-fatal warnings
        warnings = [l for l in result.stderr.strip().split('\n')
                     if l.strip() and 'Could not convert TeX math' not in l]
        if warnings:
            print(f'  Warnings ({len(warnings)}):')
            for w in warnings[:10]:
                print(f'    {w}')
        # Count math conversion issues separately
        math_warns = [l for l in result.stderr.strip().split('\n')
                       if 'Could not convert TeX math' in l]
        if math_warns:
            print(f'  Math conversion warnings: {len(math_warns)} (some formulas will show as raw TeX)')

    if result.returncode == 0 and os.path.isfile(out_docx):
        size_kb = os.path.getsize(out_docx) / 1024
        print(f'  ✓ Success: {out_docx} ({size_kb:.0f} KB)')
    else:
        print(f'  ✗ Failed (exit code {result.returncode})')
        if result.stderr:
            print(f'  stderr: {result.stderr[:500]}')
    
    return out_docx


def main():
    os.chdir(WORKSPACE)

    ref_docx = os.path.join(WORKSPACE, 'reference.docx')
    if not os.path.isfile(ref_docx):
        ref_docx = None

    files = sys.argv[1:] if len(sys.argv) > 1 else ['交底书.tex', '检索报告.tex']

    results = []
    for f in files:
        if os.path.isfile(f):
            out = convert_file(f, ref_docx)
            results.append(out)
        else:
            print(f'  SKIP: {f} not found')

    print(f'\n{"="*60}')
    print('  Conversion complete!')
    print(f'{"="*60}')
    print()
    print('Tips for best quality in the DOCX output:')
    print('  1. Math formulas render as Word OMML equations (editable)')
    print('  2. Some complex TeX math may show as raw LaTeX — manually fix in Word')
    print('  3. TikZ diagrams are replaced with placeholders — paste from PDF')
    print('  4. Table column widths may need adjustment in Word')
    print('  5. To improve styles: edit reference.docx, then re-run this script')
    print()
    for r in results:
        print(f'  Output: {r}')


if __name__ == '__main__':
    main()

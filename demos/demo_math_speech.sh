#!/usr/bin/env bash
# demo_math_speech.sh — Compare raw LaTeX vs speech text for math formulas.
#
# Usage: ./demos/demo_math_speech.sh
#
# Shows how each math formula is converted from raw LaTeX markup to
# natural-language speech text using both the SRE and MathJax engines.

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

TEX="benchmarks/homework/bu-cs237-hw.tex"

echo "═══════════════════════════════════════════════════════════════"
echo "  Math-to-Speech Demo"
echo "  Source: $TEX"
echo "═══════════════════════════════════════════════════════════════"
echo

echo "── Raw LaTeX (no conversion) ─────────────────────────────────"
echo
python -m altex "$TEX" --dump-tree --math-speech none | python3 -c "
import sys, json
tree = json.load(sys.stdin)
def find(d, tag):
    if d.get('tag') == tag: yield d.get('text','')
    for c in d.get('children', []): yield from find(c, tag)
formulas = list(find(tree, 'Formula'))
for i, f in enumerate(formulas[:6], 1):
    cleaned = f.replace(chr(10), ' ').strip()
    if len(cleaned) > 80: cleaned = cleaned[:77] + '...'
    print(f'  [{i}] {cleaned}')
print(f'  ... ({len(formulas)} total)')
"

echo
echo "── SRE engine (latex2mathml + Speech Rule Engine) ────────────"
echo
python -m altex "$TEX" --dump-tree --math-speech sre | python3 -c "
import sys, json
tree = json.load(sys.stdin)
def find(d, tag):
    if d.get('tag') == tag: yield d.get('text','')
    for c in d.get('children', []): yield from find(c, tag)
formulas = list(find(tree, 'Formula'))
for i, f in enumerate(formulas[:6], 1):
    cleaned = f.replace(chr(10), ' ').strip()
    if len(cleaned) > 80: cleaned = cleaned[:77] + '...'
    print(f'  [{i}] {cleaned}')
print(f'  ... ({len(formulas)} total)')
"

echo
echo "── MathJax engine (mathjax-full + SRE) ───────────────────────"
echo
python -m altex "$TEX" --dump-tree --math-speech mathjax | python3 -c "
import sys, json
tree = json.load(sys.stdin)
def find(d, tag):
    if d.get('tag') == tag: yield d.get('text','')
    for c in d.get('children', []): yield from find(c, tag)
formulas = list(find(tree, 'Formula'))
for i, f in enumerate(formulas[:6], 1):
    cleaned = f.replace(chr(10), ' ').strip()
    if len(cleaned) > 80: cleaned = cleaned[:77] + '...'
    print(f'  [{i}] {cleaned}')
print(f'  ... ({len(formulas)} total)')
"

echo
echo "Screen readers will speak the natural-language text instead of"
echo "raw LaTeX markup, making math formulas accessible."

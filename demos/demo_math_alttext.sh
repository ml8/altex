#!/usr/bin/env bash
# demo_math_alttext.sh — Focus demo showing math formula alt-text.
#
# Usage: ./demos/demo_math_alttext.sh
#
# Picks a math-heavy document (exam1) and shows how each formula gets
# its raw LaTeX source preserved as alt-text in the tagged PDF, making
# the math accessible to screen readers.

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

TEX="theory/exam/exam1.tex"
PDF="theory/exam/exam1.pdf"
OUT="/tmp/exam1_tagged.pdf"

echo "═══════════════════════════════════════════════════════════════"
echo "  Math Alt-Text Demo"
echo "  Source: $TEX"
echo "═══════════════════════════════════════════════════════════════"
echo
echo "The exam contains many mathematical expressions that are"
echo "rendered as graphics in the PDF.  Without alt-text, screen"
echo "readers cannot convey these formulas to users."
echo

# Tag the PDF
python -m altex "$TEX" "$PDF" -o "$OUT" > /dev/null

# Extract and display all formula alt-text
python3 - "$OUT" <<'PYTHON'
import pikepdf

pdf = pikepdf.open("/tmp/exam1_tagged.pdf")

def find_formulas(elem, results=None):
    if results is None:
        results = []
    if isinstance(elem, pikepdf.Dictionary):
        if str(elem.get("/S", "")) == "/Formula":
            alt = elem.get("/Alt")
            if alt:
                results.append(str(alt))
        kids = elem.get("/K")
        if isinstance(kids, pikepdf.Array):
            for i in range(len(kids)):
                find_formulas(kids[i], results)
    return results

formulas = find_formulas(pdf.Root["/StructTreeRoot"]["/K"])

# Separate inline and display math
inline = [f for f in formulas if f.startswith("$") and not f.startswith("$$")]
display = [f for f in formulas if f.startswith("\\[") or f.startswith("\\begin")]

print(f"Found {len(formulas)} formulas total ({len(inline)} inline, {len(display)} display)")
print()

print("── Display math (alt-text a screen reader would expose) ─────")
print()
for i, f in enumerate(display, 1):
    # Clean up for display
    cleaned = f.replace("\n", " ").replace("    ", " ")
    print(f"  [{i}] {cleaned}")
    print()

print("── Inline math (first 10) ──────────────────────────────────")
print()
for f in inline[:10]:
    print(f"  • {f}")

print()
print("Each formula's LaTeX source is stored as /Alt text in the PDF")
print("structure tree, making it available to assistive technology.")
PYTHON

#!/usr/bin/env bash
# demo_alt_document.sh — Show the embedded alternative HTML document.
#
# Usage: ./demos/demo_alt_document.sh
#
# Demonstrates embedding an accessible HTML alternative inside a PDF.
# The HTML preserves document structure and includes MathML for formulas.

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

TEX="theory/exam/exam1.tex"
PDF="theory/exam/exam1.pdf"
OUT="/tmp/exam1_alt_demo.pdf"

echo "═══════════════════════════════════════════════════════════════"
echo "  Embedded Alternative Document Demo"
echo "  Source: $TEX"
echo "═══════════════════════════════════════════════════════════════"
echo

echo "Step 1: Tag PDF with math speech + embedded HTML alternative"
echo
python -m altex "$TEX" "$PDF" --math-speech sre --embed-alt -o "$OUT"
echo

echo "Step 2: Verify embedded attachment"
echo

python3 - "$OUT" <<'PYTHON'
import pikepdf

pdf = pikepdf.open(__import__('sys').argv[1])
attachments = list(pdf.attachments.keys())
print(f"  Attachments: {attachments}")

if "accessible_alt.html" in pdf.attachments:
    data = pdf.attachments["accessible_alt.html"].get_file().read_bytes()
    html = data.decode("utf-8")
    lines = html.split("\n")
    print(f"  HTML size: {len(html)} chars, {len(lines)} lines")
    print()
    print("  ── First 15 lines of embedded HTML ──")
    print()
    for line in lines[:15]:
        print(f"    {line}")
    print("    ...")
    print()

    # Count MathML elements
    mathml_count = html.count("<math ")
    aria_count = html.count("aria-label")
    print(f"  MathML elements:  {mathml_count}")
    print(f"  aria-label attrs: {aria_count}")
    print()
    print("  ✅ Users can extract this HTML as a fully accessible")
    print("     fallback when PDF structure tagging is imperfect.")
PYTHON

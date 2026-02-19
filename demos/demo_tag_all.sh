#!/usr/bin/env bash
# demo_tag_all.sh — Tag every available PDF and summarize results.
#
# Usage: ./demos/demo_tag_all.sh
#
# Processes all .tex/.pdf pairs under theory/ and writes tagged PDFs to
# demos/output/.  Produces two variants per document:
#   *_tagged.pdf           — structure tags + metadata
#   *_tagged_encoded.pdf   — same, with Ghostscript font encoding fix
#
# Prints a summary table showing the structure elements found.

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

OUT=demos/output
rm -rf "$OUT"
mkdir -p "$OUT"

echo "═══════════════════════════════════════════════════════════════"
echo "  altex — tagging all available PDFs"
echo "═══════════════════════════════════════════════════════════════"
echo

pairs=(
    "theory/364syllabus_fall12.tex  theory/364syllabus_fall12.pdf"
    "theory/exam/exam1.tex         theory/exam/exam1.pdf"
    "theory/exam/exam2.tex         theory/exam/exam2.pdf"
    "theory/exam/exam3.tex         theory/exam/exam3.pdf"
    "theory/hw/01induction.tex     theory/hw/01induction.pdf"
    "theory/hw/02pumping-sol.tex   theory/hw/02pumping-sol.pdf"
    "theory/lecture/01problems.tex theory/lecture/01problems.pdf"
    "theory/lecture/04closure.tex  theory/lecture/04closure.pdf"
)

for pair in "${pairs[@]}"; do
    read -r tex pdf <<< "$pair"
    name=$(basename "$pdf" .pdf)
    if [ ! -f "$pdf" ]; then
        echo "SKIP $tex (no PDF)"
        continue
    fi

    # Standard tagged version.
    python -m altex "$tex" "$pdf" -o "$OUT/${name}_tagged.pdf" 2>&1

    # Variant with Ghostscript font encoding fix.
    if command -v gs &>/dev/null; then
        python -m altex "$tex" "$pdf" --fix-encoding -o "$OUT/${name}_tagged_encoded.pdf" 2>&1
    fi
done

echo
echo "═══════════════════════════════════════════════════════════════"
echo "  Structure summary"
echo "═══════════════════════════════════════════════════════════════"
echo

python3 - "$OUT" <<'PYTHON'
import sys, pikepdf
from pathlib import Path

def count_elems(elem, counts=None):
    if counts is None:
        counts = {}
    if isinstance(elem, pikepdf.Dictionary) and "/S" in elem:
        s = str(elem["/S"]).lstrip("/")
        counts[s] = counts.get(s, 0) + 1
        kids = elem.get("/K")
        if isinstance(kids, pikepdf.Array):
            for i in range(len(kids)):
                count_elems(kids[i], counts)
    return counts

out_dir = Path(sys.argv[1])
for pdf_path in sorted(out_dir.glob("*_tagged.pdf")):
    pdf = pikepdf.open(pdf_path)
    counts = count_elems(pdf.Root["/StructTreeRoot"]["/K"])
    del counts["Document"]
    parts = "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
    enc = "✓" if pdf_path.with_stem(pdf_path.stem + "_encoded").exists() else " "
    print(f"  {pdf_path.name:35s} {parts}")

PYTHON

if command -v gs &>/dev/null; then
    echo
    echo "  Encoded variants (*_tagged_encoded.pdf) also written."
else
    echo
    echo "  ⚠  Ghostscript not found — encoded variants skipped."
    echo "     Install: brew install ghostscript"
fi

echo
echo "Tagged PDFs written to $OUT/"

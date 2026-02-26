#!/usr/bin/env bash
# demo_tag_all.sh — Tag every available benchmark PDF and summarize results.
#
# Usage: ./demos/demo_tag_all.sh
#
# Processes all .tex/.pdf pairs under benchmarks/ and writes tagged PDFs to
# demos/output/.  Produces two variants per document:
#   *_tagged.pdf           — structure tags + metadata (no Ghostscript)
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
echo "  altex — tagging benchmark PDFs"
echo "═══════════════════════════════════════════════════════════════"
echo

# Representative subset for quick demo runs.
pairs=(
    "benchmarks/syllabus/utoledo-math2850.tex benchmarks/syllabus/utoledo-math2850.pdf"
    "benchmarks/exam/duke-exam.tex            benchmarks/exam/duke-exam.pdf"
    "benchmarks/homework/bu-cs237-hw.tex      benchmarks/homework/bu-cs237-hw.pdf"
    "benchmarks/homework/ucsd-math184a-hw.tex benchmarks/homework/ucsd-math184a-hw.pdf"
    "benchmarks/beamer/tufts-beamer.tex       benchmarks/beamer/tufts-beamer.pdf"
    "benchmarks/beamer/metropolis-demo.tex    benchmarks/beamer/metropolis-demo.pdf"
    "benchmarks/paper/elegantpaper-en.tex     benchmarks/paper/elegantpaper-en.pdf"
    "benchmarks/cv/duke-cv.tex               benchmarks/cv/duke-cv.pdf"
)

for pair in "${pairs[@]}"; do
    read -r tex pdf <<< "$pair"
    name=$(basename "$pdf" .pdf)
    if [ ! -f "$pdf" ]; then
        echo "SKIP $tex (no PDF)"
        continue
    fi

    # Tagged without Ghostscript encoding fix.
    python -m altex "$tex" "$pdf" --no-fix-encoding -o "$OUT/${name}_tagged.pdf" 2>&1

    # Tagged with Ghostscript encoding fix (default behavior).
    if command -v gs &>/dev/null; then
        python -m altex "$tex" "$pdf" -o "$OUT/${name}_tagged_encoded.pdf" 2>&1
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

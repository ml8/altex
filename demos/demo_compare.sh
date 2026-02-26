#!/usr/bin/env bash
# demo_compare.sh — Side-by-side comparison of original vs tagged PDF metadata.
#
# Usage: ./demos/demo_compare.sh <tex_file> <pdf_file>
#
# Example:
#   ./demos/demo_compare.sh benchmarks/homework/bu-cs237-hw.tex benchmarks/homework/bu-cs237-hw.pdf
#
# Shows:
#   1. Whether the original PDF has structure tags (spoiler: it doesn't)
#   2. The semantic tree extracted from the LaTeX source
#   3. The structure tags embedded in the tagged PDF
#   4. (If gs available) A font-encoded variant for comparison

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

TEX="${1:?Usage: demo_compare.sh <tex_file> <pdf_file>}"
PDF="${2:?Usage: demo_compare.sh <tex_file> <pdf_file>}"
NAME=$(basename "$PDF" .pdf)
OUT="/tmp/${NAME}_tagged.pdf"
OUT_ENC="/tmp/${NAME}_tagged_encoded.pdf"

echo "═══════════════════════════════════════════════════════════════"
echo "  BEFORE: original PDF — $PDF"
echo "═══════════════════════════════════════════════════════════════"

python3 - "$PDF" <<'PYTHON'
import sys, pikepdf
pdf = pikepdf.open(sys.argv[1])
mark = pdf.Root.get("/MarkInfo")
struct = pdf.Root.get("/StructTreeRoot")
print(f"  /MarkInfo:       {mark or '(absent — not tagged)'}")
print(f"  /StructTreeRoot: {struct or '(absent — no structure)'}")
print()
print("  ⚠  Screen readers have NO semantic structure to work with.")
print("     Math formulas are invisible to assistive technology.")
PYTHON

echo
echo "═══════════════════════════════════════════════════════════════"
echo "  PARSING: semantic tree from $TEX"
echo "═══════════════════════════════════════════════════════════════"
echo

python -m altex "$TEX" --dump-tree | python3 -c "
import sys, json

tree = json.load(sys.stdin)

def show(node, indent=0, max_depth=4):
    if indent > max_depth * 2:
        if node.get('children'):
            print(' ' * indent + '...')
        return
    tag = node['tag']
    text = node.get('text', '')
    # Truncate long text
    if len(text) > 70:
        text = text[:67] + '...'
    # Show alt-text indicator for formulas
    if tag == 'Formula':
        print(' ' * indent + f'📐 {tag}: {repr(text)}')
    elif tag == 'Code':
        print(' ' * indent + f'💻 {tag}: {repr(text)}')
    elif tag == 'Figure':
        print(' ' * indent + f'🖼  {tag}: {repr(text)}')
    elif text:
        print(' ' * indent + f'{tag}: {repr(text)}')
    else:
        print(' ' * indent + f'{tag}')

    for child in node.get('children', []):
        show(child, indent + 2, max_depth)

show(tree)
"

echo
echo "═══════════════════════════════════════════════════════════════"
echo "  TAGGING: embedding structure into PDF"
echo "═══════════════════════════════════════════════════════════════"
echo

python -m altex "$TEX" "$PDF" -o "$OUT"

echo
echo "═══════════════════════════════════════════════════════════════"
echo "  AFTER: tagged PDF — $OUT"
echo "═══════════════════════════════════════════════════════════════"

python3 - "$OUT" <<'PYTHON'
import sys, pikepdf
pdf = pikepdf.open(sys.argv[1])
mark = pdf.Root.get("/MarkInfo")
struct = pdf.Root.get("/StructTreeRoot")
print(f"  /MarkInfo:       {mark}")
print(f"  /StructTreeRoot: present ✓")
print()

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

def count_alt(elem, n=0):
    if isinstance(elem, pikepdf.Dictionary):
        if "/Alt" in elem:
            n += 1
        kids = elem.get("/K")
        if isinstance(kids, pikepdf.Array):
            for i in range(len(kids)):
                n = count_alt(kids[i], n)
    return n

counts = count_elems(pdf.Root["/StructTreeRoot"]["/K"])
alt_count = count_alt(pdf.Root["/StructTreeRoot"]["/K"])
del counts["Document"]

print("  Structure elements:")
for k, v in sorted(counts.items()):
    print(f"    {k:12s} {v}")
print()
print(f"  Elements with /Alt text: {alt_count}")
print(f"  ✅ Screen readers can now navigate the document structure")
print(f"     and read alt-text for {alt_count} math/code/figure elements.")

# Show new metadata
lang = str(pdf.Root.get("/Lang", "(not set)"))
tabs = str(pdf.pages[0].obj.get("/Tabs", "(not set)"))
with pdf.open_metadata() as meta:
    title = meta.get("dc:title", "(not set)")
vp = pdf.Root.get("/ViewerPreferences", {})
ddt = vp.get("/DisplayDocTitle", False) if vp else False
ops = pikepdf.parse_content_stream(pdf.pages[0])
bdc = sum(1 for op in ops if str(op.operator) == "BDC")
print()
print(f"  /Lang:             {lang}")
print(f"  dc:title:          {title}")
print(f"  DisplayDocTitle:   {ddt}")
print(f"  /Tabs:             {tabs}")
print(f"  BDC markers (p1):  {bdc}")
PYTHON

# --- Encoded variant ---
if command -v gs &>/dev/null; then
    echo
    echo "═══════════════════════════════════════════════════════════════"
    echo "  ENCODING FIX: Ghostscript font re-encoding — $OUT_ENC"
    echo "═══════════════════════════════════════════════════════════════"
    echo
    python -m altex "$TEX" "$PDF" --fix-encoding -o "$OUT_ENC"
    echo

    python3 - "$PDF" "$OUT_ENC" <<'PYENC'
import sys, pikepdf
orig = pikepdf.open(sys.argv[1])
fixed = pikepdf.open(sys.argv[2])

def font_info(pdf):
    fonts = pdf.pages[0].obj.get("/Resources", {}).get("/Font", {})
    total = len(list(fonts.keys()))
    with_enc = sum(1 for n in fonts.keys()
                   if fonts[n].get("/Encoding") not in (None,))
    with_tu = sum(1 for n in fonts.keys() if "/ToUnicode" in fonts[n])
    return total, with_enc, with_tu

ot, oe, ou = font_info(orig)
ft, fe, fu = font_info(fixed)
print(f"  Font encoding comparison (page 1):")
print(f"    {'':20s} {'Fonts':>6s}  {'w/Encoding':>10s}  {'w/ToUnicode':>11s}")
print(f"    {'Original':20s} {ot:6d}  {oe:10d}  {ou:11d}")
print(f"    {'GS + tagged':20s} {ft:6d}  {fe:10d}  {fu:11d}")
print()
print(f"  Ghostscript normalizes font encodings with proper glyph names,")
print(f"  improving character mapping for assistive technology.")
PYENC
else
    echo
    echo "  ⚠  Ghostscript not found — encoding fix demo skipped."
    echo "     Install: brew install ghostscript"
fi

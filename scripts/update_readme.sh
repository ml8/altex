#!/usr/bin/env bash
# update_readme.sh — Generate a terminal "screenshot" and update the README.
#
# Runs altex + verapdf on a benchmark file and replaces the [[TUI]]
# section in README.md with the formatted output.
#
# Usage: ./scripts/update_readme.sh

set -uo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

TEX="benchmarks/homework/bu-cs237-hw.tex"
PDF="benchmarks/homework/bu-cs237-hw.pdf"
OUT="/tmp/altex_readme_demo.pdf"
TUI_FILE="/tmp/altex_tui_output.txt"

# ── Helper: run verapdf and format output ─────────────────────────────

format_verapdf() {
    local pdf="$1"
    verapdf -f ua1 --format json "$pdf" 2>/dev/null | python3 -c "
import json, sys
d = json.load(sys.stdin)['report']['jobs'][0]['validationResult'][0]['details']
print(f'  Passed rules: {d[\"passedRules\"]}')
print(f'  Failed rules: {d[\"failedRules\"]}')
print(f'  Failed checks: {d[\"failedChecks\"]}')
for r in d['ruleSummaries']:
    if r['ruleStatus'] == 'FAILED':
        desc = r['description'][:65]
        print(f'    [{r[\"clause\"]}:{r[\"testNumber\"]}] x{r[\"failedChecks\"]}: {desc}')
"
}

# ── Generate the TUI output ───────────────────────────────────────────

# Tag the PDF first (outside the capture block).
python -m altex "$TEX" "$PDF" -o "$OUT" >/dev/null 2>&1

# Now build the formatted output.
{
    echo '```'
    echo "$ verapdf -f ua1 $PDF"
    format_verapdf "$PDF"
    echo ""
    echo "$ python -m altex $TEX $PDF -o tagged.pdf"
    echo "Tagged PDF written to tagged.pdf"
    echo ""
    echo "$ verapdf -f ua1 tagged.pdf"
    format_verapdf "$OUT"
    echo '```'
} > "$TUI_FILE"

# ── Replace [[TUI]] section in README.md ──────────────────────────────

python3 -c "
import re

tui = open('$TUI_FILE').read().rstrip()
readme = open('README.md').read()
pattern = r'<!-- \[\[TUI\]\] -->.*?<!-- \[\[/TUI\]\] -->'
replacement = '<!-- [[TUI]] -->\n' + tui + '\n<!-- [[/TUI]] -->'
if re.search(pattern, readme, re.DOTALL):
    open('README.md', 'w').write(re.sub(pattern, replacement, readme, flags=re.DOTALL))
    print('✓ README.md updated with TUI output')
else:
    raise SystemExit('ERROR: TUI markers not found in README.md')
"

rm -f "$OUT" "$TUI_FILE"

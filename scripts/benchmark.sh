#!/usr/bin/env bash
# benchmark.sh — Run altex + verapdf PDF/UA-1 benchmarks.
#
# Usage:
#   ./scripts/benchmark.sh              # validate existing tagged PDFs
#   ./scripts/benchmark.sh --tag-first  # regenerate tagged PDFs first
#
# Requires: verapdf in PATH, .venv with altex dependencies

set -euo pipefail
cd "$(dirname "$0")/.."

source .venv/bin/activate

# Verify verapdf is available.
if ! command -v verapdf &>/dev/null; then
    echo "ERROR: verapdf not found. Install from https://verapdf.org/software/"
    exit 1
fi

echo "verapdf $(verapdf --version 2>&1 | head -1)"
echo

python3 scripts/benchmark_report.py "$@"

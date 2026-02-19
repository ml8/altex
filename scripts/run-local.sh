#!/usr/bin/env bash
# Run the altex web service locally (no Docker).
#
# Usage: ./scripts/run-local.sh
#
# Starts Flask dev server on http://localhost:5000

set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
    echo "Creating virtualenv…"
    python3 -m venv .venv
fi

source .venv/bin/activate
pip install -q -r requirements.txt flask

echo "Starting altex web service on http://localhost:5000"
FLASK_APP=web.app flask run --host=0.0.0.0 --port=5001

"""Run verapdf PDF/UA-1 validation on a PDF file.

This module wraps the ``verapdf`` command-line tool and parses its JSON
output into a simple dict.  Shared by the web API (``web/app.py``) and
the benchmark runner (``scripts/benchmark_report.py``).

verapdf is the industry-standard open-source PDF/UA validator, developed
by the Open Preservation Foundation.  See https://verapdf.org/.

Public API
----------
    validate(pdf_path, timeout=60) -> dict | None
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


def validate(pdf_path: Path, *, timeout: int = 60) -> dict | None:
    """Run verapdf PDF/UA-1 validation and return a summary.

    Returns ``None`` if verapdf is not installed or times out.
    Otherwise returns::

        {
            "passed_rules": int,
            "failed_rules": int,
            "passed_checks": int,
            "failed_checks": int,
            "details": [
                {"clause": "7.1:3", "description": "...", "count": 199},
                ...
            ],
        }
    """
    try:
        result = subprocess.run(
            ["verapdf", "-f", "ua1", "--format", "json", str(pdf_path)],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None

    try:
        data = json.loads(result.stdout)
        vr = data["report"]["jobs"][0]["validationResult"][0]["details"]

        failed_details = []
        for rs in vr.get("ruleSummaries", []):
            if rs["ruleStatus"] == "FAILED":
                failed_details.append({
                    "clause": f"{rs['clause']}:{rs['testNumber']}",
                    "description": rs["description"],
                    "count": rs["failedChecks"],
                })

        return {
            "passed_rules": vr["passedRules"],
            "failed_rules": vr["failedRules"],
            "passed_checks": vr["passedChecks"],
            "failed_checks": vr["failedChecks"],
            "details": failed_details,
        }
    except (json.JSONDecodeError, KeyError, IndexError):
        return None

"""Convert LaTeX math formulas to speech text.

Public API
----------
    latex_to_speech(formulas, engine="sre") -> list[str]

Engines:
    "sre"     — latex2mathml (Python) + Speech Rule Engine (Node.js)
    "mathjax" — mathjax-full + SRE (all Node.js)
    "none"    — return raw LaTeX (no conversion)

Both engines use a short-lived batch subprocess: start one Node process,
pipe all formulas in, read all results, process exits.  No persistent
state or IPC.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).parent.parent / "scripts"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def latex_to_speech(
    formulas: list[str],
    engine: str = "sre",
) -> list[str]:
    """Convert *formulas* to speech text using the specified engine.

    Returns a list the same length as *formulas*.  On failure, individual
    entries fall back to the raw LaTeX string.
    """
    if engine == "none" or not formulas:
        return list(formulas)

    dispatch = {
        "sre": _engine_sre,
        "mathjax": _engine_mathjax,
    }
    fn = dispatch.get(engine)
    if fn is None:
        raise ValueError(f"Unknown math-speech engine: {engine!r}")
    return fn(formulas)


# ---------------------------------------------------------------------------
# Engine: sre (latex2mathml + SRE)
# ---------------------------------------------------------------------------


def _engine_sre(formulas: list[str]) -> list[str]:
    """LaTeX → MathML (Python) → speech (SRE Node subprocess)."""
    try:
        import latex2mathml.converter as l2m
    except ImportError:
        return list(formulas)  # fallback

    mathml_lines = []
    for f in formulas:
        try:
            clean = _strip_delimiters(f)
            mathml_lines.append(l2m.convert(clean))
        except Exception:
            mathml_lines.append("")

    speech = _run_worker("sre_worker.js", mathml_lines, formulas)
    return speech


# ---------------------------------------------------------------------------
# Engine: mathjax (mathjax-full + SRE, all Node.js)
# ---------------------------------------------------------------------------


def _engine_mathjax(formulas: list[str]) -> list[str]:
    """LaTeX → speech via mathjax-full + SRE Node subprocess."""
    cleaned = [_strip_delimiters(f) for f in formulas]
    return _run_worker("mathjax_worker.js", cleaned, formulas)


# ---------------------------------------------------------------------------
# Shared subprocess runner
# ---------------------------------------------------------------------------


def _run_worker(
    script_name: str,
    input_lines: list[str],
    fallbacks: list[str],
) -> list[str]:
    """Run a Node worker script, sending input lines and reading JSON results."""
    node = shutil.which("node")
    if node is None:
        return list(fallbacks)

    script = _SCRIPTS_DIR / script_name
    if not script.is_file():
        return list(fallbacks)

    stdin_data = "\n".join(line.replace("\n", " ") for line in input_lines) + "\n"

    try:
        result = subprocess.run(
            [node, str(script)],
            input=stdin_data,
            capture_output=True,
            text=True,
            timeout=60,
        )
    except (subprocess.TimeoutExpired, OSError):
        return list(fallbacks)

    output_lines = result.stdout.strip().split("\n") if result.stdout.strip() else []

    speeches: list[str] = []
    for i, fallback in enumerate(fallbacks):
        if i < len(output_lines):
            try:
                data = json.loads(output_lines[i])
                speeches.append(data.get("speech", fallback))
            except (json.JSONDecodeError, KeyError):
                speeches.append(fallback)
        else:
            speeches.append(fallback)

    return speeches


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_delimiters(latex: str) -> str:
    """Remove surrounding $ or \\[...\\] delimiters from a LaTeX string."""
    s = latex.strip()
    if s.startswith("$$") and s.endswith("$$"):
        return s[2:-2].strip()
    if s.startswith("$") and s.endswith("$"):
        return s[1:-1].strip()
    if s.startswith("\\[") and s.endswith("\\]"):
        return s[2:-2].strip()
    # Strip \begin{env}...\end{env}
    for env in ("equation", "equation*", "align", "align*",
                "gather", "gather*", "multline", "multline*",
                "displaymath"):
        begin = f"\\begin{{{env}}}"
        end = f"\\end{{{env}}}"
        if s.startswith(begin) and s.endswith(end):
            return s[len(begin):-len(end)].strip()
    return s

"""Fix PDF font encoding by re-processing through Ghostscript.

This module is intentionally isolated — it has no imports from other
altex modules.  Its sole job is to shell out to Ghostscript (``gs``)
to re-encode fonts with proper ToUnicode CMaps.

Public API
----------
    fix_encoding(input_path, output_path) -> None
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


class GhostscriptNotFoundError(RuntimeError):
    """Raised when Ghostscript is not found on PATH."""


def fix_encoding(input_path: Path, output_path: Path) -> None:
    """Re-encode *input_path* via Ghostscript, writing to *output_path*.

    Ghostscript re-processes the PDF and generates ToUnicode CMaps for
    fonts that lack them, fixing character-encoding accessibility failures.

    Raises ``GhostscriptNotFoundError`` if ``gs`` is not on PATH.
    """
    gs = shutil.which("gs")
    if gs is None:
        raise GhostscriptNotFoundError(
            "Ghostscript (gs) is not installed or not on PATH.\n"
            "Install it with: brew install ghostscript  (macOS)\n"
            "                 apt install ghostscript   (Debian/Ubuntu)"
        )

    cmd = [
        gs,
        "-dNOPAUSE",
        "-dBATCH",
        "-dQUIET",
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.7",
        "-dPDFSETTINGS=/prepress",
        "-dSubsetFonts=false",
        "-dEmbedAllFonts=true",
        f"-sOutputFile={output_path}",
        str(input_path),
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(
            f"Ghostscript failed (exit {result.returncode}):\n{result.stderr}"
        )

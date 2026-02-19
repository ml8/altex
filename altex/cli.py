"""Command-line interface for altex.

Usage
-----
    python -m altex source.tex input.pdf -o output.pdf
    python -m altex source.tex input.pdf --fix-encoding -o output.pdf
    python -m altex source.tex --dump-tree
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from altex.latex_parser import extract_title, parse
from altex.pdf_tagger import tag


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Step 1: parse LaTeX source into a semantic tree.
    tree = parse(args.tex)

    # Optional: dump the intermediate tree as JSON and exit.
    if args.dump_tree:
        print(tree.to_json(indent=2))
        return

    # Step 2: embed the tree as PDF structure tags.
    if args.pdf is None:
        print("error: PDF path is required unless --dump-tree is used", file=sys.stderr)
        sys.exit(1)

    pdf_input = args.pdf
    output = args.output or args.pdf.with_stem(args.pdf.stem + "_tagged")

    # Optional: fix font encoding via Ghostscript first.
    if args.fix_encoding:
        from altex.encoding_fixer import fix_encoding

        intermediate = output.with_stem(output.stem + "_tmp_enc")
        fix_encoding(pdf_input, intermediate)
        pdf_input = intermediate

    # Extract title from LaTeX source.
    title = extract_title(args.tex)

    tag(pdf_input, tree, output, lang=args.lang, title=title)
    print(f"Tagged PDF written to {output}")

    # Clean up intermediate file.
    if args.fix_encoding:
        intermediate.unlink(missing_ok=True)


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="altex",
        description="Post-process LaTeX-generated PDFs for accessibility.",
    )
    p.add_argument("tex", type=Path, help="LaTeX source file (.tex)")
    p.add_argument("pdf", type=Path, nargs="?", help="Compiled PDF to tag")
    p.add_argument("-o", "--output", type=Path, help="Output PDF path")
    p.add_argument(
        "--dump-tree",
        action="store_true",
        help="Print the semantic tree as JSON and exit (no PDF needed)",
    )
    p.add_argument(
        "--lang",
        default="en",
        help="Document language (default: en)",
    )
    p.add_argument(
        "--fix-encoding",
        action="store_true",
        help="Pre-process PDF with Ghostscript to fix font encoding (requires gs)",
    )
    return p.parse_args(argv)

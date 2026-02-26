"""Command-line interface for altex.

Usage
-----
    python -m altex source.tex input.pdf -o output.pdf
    python -m altex source.tex input.pdf --fix-encoding -o output.pdf
    python -m altex source.tex input.pdf --math-speech sre -o output.pdf
    python -m altex source.tex --dump-tree
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from altex.latex_parser import extract_title, parse
from altex.models import DocumentNode, Tag
from altex.pdf_tagger import tag


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    # Step 1: parse LaTeX source into a semantic tree.
    tree = parse(args.tex)

    # Generate alt HTML from raw tree (before speech conversion).
    alt_html = None
    if args.embed_alt and not args.dump_tree:
        from altex.alt_document import generate_alt_html

        title_for_alt = extract_title(args.tex) or args.tex.stem
        alt_html = generate_alt_html(tree, title_for_alt)

    # Convert formula alt-text to speech.
    if args.math_speech != "none":
        _apply_math_speech(tree, args.math_speech)

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

    # Fix font encoding via Ghostscript (on by default for PDF/UA §7.21.7
    # compliance).  Falls back gracefully if gs is not installed.
    encoding_fixed = False
    intermediate = None
    if args.fix_encoding:
        from altex.encoding_fixer import GhostscriptNotFoundError, fix_encoding

        intermediate = output.with_stem(output.stem + "_tmp_enc")
        try:
            fix_encoding(pdf_input, intermediate)
            pdf_input = intermediate
            encoding_fixed = True
        except GhostscriptNotFoundError:
            print(
                "warning: Ghostscript not found — skipping font encoding fix.\n"
                "  Install with: brew install ghostscript (macOS) or "
                "apt install ghostscript (Linux)\n"
                "  Use --no-fix-encoding to suppress this warning.",
                file=sys.stderr,
            )

    # Extract title from LaTeX source.
    title = extract_title(args.tex)

    tag(pdf_input, tree, output, lang=args.lang, title=title)

    # Embed the alternative HTML document.
    if alt_html:
        from altex.alt_document import embed_alt_document

        embed_alt_document(output, alt_html, output)

    print(f"Tagged PDF written to {output}")

    # Clean up intermediate file.
    if encoding_fixed and intermediate:
        intermediate.unlink(missing_ok=True)


def _apply_math_speech(tree: DocumentNode, engine: str) -> None:
    """Walk the tree, collect formula texts, convert in batch, update nodes."""
    from altex.math_speech import latex_to_speech

    formula_nodes = tree.collect_by_tag(Tag.FORMULA)
    if not formula_nodes:
        return

    raw_texts = [n.text for n in formula_nodes]
    speeches = latex_to_speech(raw_texts, engine=engine)
    for node, speech in zip(formula_nodes, speeches):
        node.text = speech


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
        default=True,
        help="Pre-process PDF with Ghostscript to fix font encoding (default: on)",
    )
    p.add_argument(
        "--no-fix-encoding",
        action="store_false",
        dest="fix_encoding",
        help="Skip Ghostscript font encoding fix",
    )
    p.add_argument(
        "--math-speech",
        choices=["sre", "mathjax", "none"],
        default="none",
        help="Math-to-speech engine (default: none — raw LaTeX as alt-text)",
    )
    p.add_argument(
        "--embed-alt",
        action="store_true",
        help="Embed an accessible HTML alternative as a PDF attachment",
    )
    return p.parse_args(argv)

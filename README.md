# accessible-latex

**altex** — a proof-of-concept tool that post-processes LaTeX-generated PDFs
to embed accessibility structure tags and alt-text.

## Quick start

```bash
# Install everything
make setup

# Tag a PDF
make tag TEX=source.tex PDF=input.pdf OUT=output.pdf

# Or use the CLI directly
.venv/bin/python3 -m altex source.tex input.pdf -o output.pdf

# Start the web interface
make run
# → http://localhost:5001

# Run all demos
make demo

# See all available commands
make help
```

### Manual setup (without Make)

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install --production    # for math-to-speech

# Tag a PDF (two inputs: LaTeX source + compiled PDF)
python -m altex source.tex input.pdf -o output.pdf

# With Ghostscript font encoding fix
python -m altex source.tex input.pdf --fix-encoding -o output.pdf

# Inspect the parsed structure (no PDF needed)
python -m altex source.tex --dump-tree
```

## What it does

1. **Parses LaTeX source** — extracts semantic structure (sections, headings,
   lists, math, code blocks, figures) into a document tree.
2. **Embeds PDF structure tags** — writes a PDF structure tree with proper
   hierarchy, `/ActualText` for text, `/Alt` for formulas (raw LaTeX source),
   code blocks, and figures.
3. **Tags content streams** — wraps text blocks with BDC/EMC marked-content
   operators and links them to structure elements via MCIDs.
4. **Sets accessibility metadata** — document language, title, tab order,
   viewer preferences.
5. **Fixes font encoding** (optional) — uses Ghostscript to normalize font
   encodings for better character mapping.

## Supported LaTeX commands

| Category   | Commands                                                  |
|------------|-----------------------------------------------------------|
| Sections   | `\section`, `\subsection`, `\subsubsection`, `\paragraph` |
| Lists      | `\begin{itemize}`, `\begin{enumerate}`, `\begin{description}`, `\item` |
| Math       | `$...$`, `\[...\]`, `equation`, `align`, `gather` (and starred variants) |
| Code       | `verbatim`, `lstlisting`, `minted`                        |
| Figures    | `\begin{figure}`, `\includegraphics`, `\caption`          |
| Includes   | `\input{}`, `\include{}`                                  |

Unknown macros are handled generically by extracting readable text from
their arguments.

## CLI options

```
python -m altex <source.tex> [<input.pdf>] [-o <output.pdf>] [options]

Options:
  --dump-tree       Print the semantic tree as JSON and exit (no PDF needed)
  --lang LANG       Document language (default: en)
  --fix-encoding    Pre-process PDF with Ghostscript to fix font encoding
  --math-speech ENGINE  Math-to-speech engine: sre, mathjax, or none (default: none)
  --embed-alt       Embed an accessible HTML alternative as a PDF attachment
```

## Web interface

Upload `.tex` + `.pdf` in a browser, get a tagged PDF + accessibility summary.

```bash
# Local dev server
make run
# → http://localhost:5001

# Docker
make docker-run
# → http://localhost:5000
```

The web UI shows an accessibility summary (structure element counts, alt-text
count, metadata) and provides a download link for the tagged PDF.

## Project structure

```
altex/
├── __init__.py        # Package metadata
├── __main__.py        # python -m altex entry point
├── cli.py             # Argument parsing and orchestration
├── models.py          # Tag enum + DocumentNode dataclass (shared interface)
├── latex_parser.py    # LaTeX source → DocumentNode tree
├── pdf_tagger.py      # Embed structure tree + MCIDs into PDF
├── math_speech.py     # Pluggable math-to-speech (sre/mathjax/none)
├── alt_document.py    # Generate + embed alternative HTML in PDF
└── encoding_fixer.py  # Isolated Ghostscript wrapper (no altex imports)
web/
├── app.py             # Flask API service
└── static/
    └── index.html     # Single-file frontend (HTML/CSS/JS, no build step)
scripts/
├── sre_worker.js      # Batch MathML→speech via SRE
├── mathjax_worker.js  # Batch LaTeX→speech via mathjax-full+SRE
└── run-local.sh       # Start dev server without Docker
docs/
├── design.md          # Architecture and design decisions
├── pdf-tagging-reference.md  # PDF structure tag reference
└── math-speech-and-alt-document.md  # Phase 4 design plan
demos/
├── demo_compare.sh    # Before/after comparison with encoding variant
├── demo_math_alttext.sh  # Math formula alt-text showcase
├── demo_math_speech.sh   # Math-to-speech engine comparison
├── demo_alt_document.sh  # Embedded alternative HTML demo
└── demo_tag_all.sh    # Batch-tag all test documents
Makefile               # Build, run, test, clean commands
Dockerfile             # Single container (Flask + Ghostscript + Node)
docker-compose.yml     # Convenience wrapper
```

## Architecture

The pipeline has two stages connected by a single shared data structure
(`DocumentNode` in `models.py`):

```
LaTeX source (.tex)          Compiled PDF (.pdf)
        │                            │
        ▼                            │
  latex_parser.py                    │
  (pylatexenc)                       │
        │                            │
        │  DocumentNode tree         │
        ▼                           ▼
              pdf_tagger.py
              (pikepdf + pymupdf)
                    │
                    ▼
             Tagged PDF (.pdf)
```

The `encoding_fixer.py` module is fully isolated (zero altex imports) and
optionally pre-processes the PDF through Ghostscript before tagging.

## Limitations (proof of concept)

- Content-stream MCIDs use page-level BT/ET block matching (heuristic).
- Preamble macros may produce noise in the parsed text.
- Custom class/package commands are handled generically, not semantically.
- Font encoding fix depends on Ghostscript being installed.

## Dependencies

- [pikepdf](https://pikepdf.readthedocs.io/) — PDF structure manipulation
- [pymupdf](https://pymupdf.readthedocs.io/) — PDF text extraction
- [pylatexenc](https://pylatexenc.readthedocs.io/) — LaTeX parsing
- [Flask](https://flask.palletsprojects.com/) — web service (optional)
- [Ghostscript](https://www.ghostscript.com/) — font encoding fix (optional)

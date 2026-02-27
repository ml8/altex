# AGENTS.md — Handoff Guide for AI Agents

This document provides context for any AI agent or developer picking up
work on the **altex** project.  Read this first.

## Project Summary

**altex** is a proof-of-concept tool that post-processes LaTeX-generated
PDFs to embed PDF/UA accessibility structure tags and alt-text.  It has
three interfaces: a CLI, a Flask web API, and a Docker container.

## Key Architecture Rules

1. **`DocumentNode` is the only shared data structure.**  Defined in
   `altex/models.py`.  The parser produces one, the tagger consumes one.
   No other state is shared between pipeline stages.

2. **`encoding_fixer.py` is fully isolated.**  It imports nothing from
   altex.  It communicates only through file paths.  Keep it this way.

3. **Minimize grab-bag data structures.**  No `dict` kwargs, no context
   objects, no shared config singletons.  Each function takes explicit
   typed parameters.

4. **pylatexenc v2 API only.**  v3 has a different API.  We pin `<3` in
   requirements.txt.  The key classes are `LatexWalker`, `LatexMacroNode`,
   `LatexEnvironmentNode`, `LatexMathNode`, `LatexCharsNode`.

## File Map

```
altex/                     # Core pipeline (no web dependencies)
|-- models.py              # Tag enum + DocumentNode dataclass
|-- latex_parser.py        # parse(tex_path) -> DocumentNode
|                          #   Uses pylatexenc LatexWalker with custom context
|                          #   (_latex_context adds \paragraph, \href, \url specs)
|-- pdf_tagger.py          # tag(pdf_path, tree, output_path, lang, title)
|                          #   1. Sets metadata (Lang, title, tabs, MarkInfo, pdfuaid)
|                          #   2. Tags content streams (per-TJ BDC/EMC with MCIDs)
|                          #   3. Marks non-text content as Artifact
|                          #   4. Builds structure tree + parent tree
|                          #   5. Links structure elements to MCIDs via text matching
|                          #   6. Links PDF annotations to /Link StructElems
|-- verapdf.py             # validate(pdf_path) -> dict | None
|                          #   Shared verapdf wrapper for web UI and benchmarks
|-- math_speech.py         # latex_to_speech(formulas, engine) -> list[str]
|                          #   Pluggable: "sre" (latex2mathml+SRE), "mathjax", "none"
|                          #   Isolated: imports only stdlib + latex2mathml
|                          #   Uses short-lived batch subprocess (not IPC daemon)
|-- alt_document.py        # generate_alt_html(tree, title) -> str
|                          #   embed_alt_document(pdf_path, html, output_path)
|                          #   Isolated: imports only models + pikepdf + latex2mathml
|-- encoding_fixer.py      # fix_encoding(input_path, output_path)
|                          #   Isolated: shells out to Ghostscript (gs)
|-- cli.py                 # CLI: python -m altex source.tex input.pdf -o out.pdf
`-- __main__.py            # Entry point for python -m altex

scripts/                   # Benchmarks and Node.js workers
|-- benchmark.sh           # Run PDF/UA-1 benchmarks via verapdf
|-- benchmark_report.py    # Benchmark runner + report generator
|-- sre_worker.js          # Batch MathML->speech via SRE (stdin/stdout)
|-- mathjax_worker.js      # Batch LaTeX->speech via mathjax-full+SRE
`-- run-local.sh           # Start Flask dev server locally

web/                       # Flask web interface
|-- app.py                 # POST /api/tag, GET /api/download/<id>, GET /
`-- static/index.html      # Single-file frontend (vanilla HTML/CSS/JS)

docs/                      # Project documentation
|-- design.md              # Architecture, design decisions, feature status
|-- pdf-tagging-reference.md  # PDF structure tag types reference
`-- math-speech-and-alt-document.md  # Phase 4 design plan

demos/                     # Demo scripts (run against benchmarks/)
|-- demo_compare.sh        # Before/after comparison
|-- demo_math_alttext.sh   # Math formula alt-text showcase
|-- demo_math_speech.sh    # Math-to-speech engine comparison
|-- demo_alt_document.sh   # Embedded alternative HTML demo
`-- demo_tag_all.sh        # Batch-tag representative benchmark docs

benchmarks/                # PDF/UA benchmark corpus (.tex + .pdf pairs)
|-- beamer/                # Beamer presentations (Tufts, Stanford, etc.)
|-- cv/                    # CV templates
|-- exam/                  # Exam templates
|-- homework/              # Homework (ML, combinatorics, HPC, etc.)
|-- paper/                 # Papers and lecture notes
|-- syllabus/              # Course syllabi
`-- manifest.json          # Metadata for all benchmark documents
```

## How to Build and Run

```bash
# CLI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m altex benchmarks/homework/bu-cs237-hw.tex benchmarks/homework/bu-cs237-hw.pdf -o /tmp/out.pdf

# Web (local)
pip install flask
FLASK_APP=web.app flask run --port=5001

# Docker
docker compose up --build
# → http://localhost:5000

# Benchmarks
./scripts/benchmark.sh --tag-first
```

## Test Data

The `benchmarks/` directory contains .tex + .pdf pairs from .edu sites and
academic repositories, covering diverse document types:

| Category | Examples |
|----------|----------|
| Beamer slides | Tufts Math, Stanford, UC Davis, Metropolis theme |
| Homework | BU probability, UPenn ML, UCSD combinatorics, SFSU HPC |
| Papers | Cambridge distributed systems, W&M thesis, ElegantPaper |
| Exams | Duke math exam template |
| Syllabi | U. Toledo calculus |
| CVs | Duke CV template |

Run all benchmarks: `make benchmark-full`

## Known Issues and Technical Debt

### Preamble noise
The parser doesn't skip content before `\begin{document}`.  Preamble
macros like `\pagestyle{empty}` get their args extracted as paragraph
text.  Empty headings from preamble noise are pruned by
`_prune_empty_headings`, but other noise nodes may remain.

### Content-stream MCID linking uses fuzzy text matching
Each TJ/Tj operator gets its own MCID (per-operator granularity), but
linking MCIDs to StructElems uses word-overlap heuristic scoring
(`_match_score` in `pdf_tagger.py`).  Some structure elements may
remain unlinked when font encoding prevents readable text extraction.

### Font ToUnicode (§7.21.7:1)
The only remaining verapdf failure category.  Math/symbol fonts
(CMSY10, etc.) in some PDFs lack ToUnicode CMaps.  Ghostscript
(`--fix-encoding`, on by default) resolves most; the rest require
re-compilation with modern LaTeX engines (lualatex/xelatex).

### Port conflict on macOS
Port 5000 is used by AirPlay Receiver on macOS.  The Makefile and
`run-local.sh` use port 5001.

## Adobe Accessibility Checker Results

An Adobe accessibility report is saved in `pumping_report.md`.  After
Phase 2 remediation, the tool addresses all 7 originally-failing rules:

| Rule | Fix |
|------|-----|
| Primary language | `/Lang` in catalog |
| Title | `dc:title` + `/DisplayDocTitle` |
| Tab order | `/Tabs /S` on pages |
| Tagged content | BDC/EMC MCIDs in content streams |
| Character encoding | Ghostscript `--fix-encoding` |
| Alt text associated | MCR links from StructElems |
| Other elements alt text | MCR links from StructElems |

## Future Work Priorities

1. **Preamble filtering** — skip before `\begin{document}` (easy, high impact)
2. **Finer MCID granularity** — per-Tj/TJ rather than per-BT/ET (medium)
3. **Correct parent tree** — map MCIDs to actual parent StructElems (medium)
4. **Math-to-speech** — convert LaTeX to natural-language alt-text (hard)
5. **Artifact marking** — mark decorative content as `/Artifact` (medium)
6. **PDF/UA validation** — integrate PAC or veraPDF (easy)

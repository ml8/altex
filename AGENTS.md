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
├── models.py              # Tag enum + DocumentNode dataclass
├── latex_parser.py        # parse(tex_path) → DocumentNode
│                          #   Uses pylatexenc LatexWalker with custom context
│                          #   (_latex_context adds \paragraph spec)
├── pdf_tagger.py          # tag(pdf_path, tree, output_path, lang, title)
│                          #   1. Sets metadata (Lang, title, tabs, MarkInfo)
│                          #   2. Tags content streams (BDC/EMC with MCIDs)
│                          #   3. Builds structure tree + parent tree
│                          #   4. Links structure elements to MCIDs via text matching
├── math_speech.py         # latex_to_speech(formulas, engine) → list[str]
│                          #   Pluggable: "sre" (latex2mathml+SRE), "mathjax", "none"
│                          #   Isolated: imports only stdlib + latex2mathml
│                          #   Uses short-lived batch subprocess (not IPC daemon)
├── alt_document.py        # generate_alt_html(tree, title) → str
│                          #   embed_alt_document(pdf_path, html, output_path)
│                          #   Isolated: imports only models + pikepdf + latex2mathml
├── encoding_fixer.py      # fix_encoding(input_path, output_path)
│                          #   Isolated: shells out to Ghostscript (gs)
├── cli.py                 # CLI: python -m altex source.tex input.pdf -o out.pdf
└── __main__.py            # Entry point for python -m altex

scripts/                   # Node.js worker scripts for math-to-speech
├── sre_worker.js          # Batch MathML→speech via SRE (stdin/stdout)
├── mathjax_worker.js      # Batch LaTeX→speech via mathjax-full+SRE
└── run-local.sh           # Start Flask dev server locally

web/                       # Flask web interface
├── app.py                 # POST /api/tag, GET /api/download/<id>, GET /
└── static/index.html      # Single-file frontend (vanilla HTML/CSS/JS)

docs/                      # Project documentation
├── design.md              # Architecture, design decisions, feature status
├── pdf-tagging-reference.md  # PDF structure tag types reference
└── math-speech-and-alt-document.md  # Phase 4 design plan

demos/                     # Demo scripts (run against theory/ test data)
├── demo_compare.sh        # Before/after comparison
├── demo_math_alttext.sh   # Math formula alt-text showcase
├── demo_math_speech.sh    # Math-to-speech engine comparison
├── demo_alt_document.sh   # Embedded alternative HTML demo
└── demo_tag_all.sh        # Batch-tag all test docs (both variants)
```

## How to Build and Run

```bash
# CLI
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m altex theory/exam/exam1.tex theory/exam/exam1.pdf -o /tmp/out.pdf

# Web (local)
pip install flask
FLASK_APP=web.app flask run --port=5001

# Docker
docker compose up --build
# → http://localhost:5000
```

## Test Data

The `theory/` directory (gitignored) contains LaTeX source + compiled PDFs
from a theory of computation course.  Key test cases:

| File | Tests |
|------|-------|
| `theory/364syllabus_fall12.tex` | Lists, tables, basic text |
| `theory/exam/exam1.tex` | Heavy inline + display math, `gather*` |
| `theory/hw/01induction.tex` | Nested lists, `align*`, `\includegraphics` |
| `theory/hw/02pumping-sol.tex` | Math proofs, many formulas (138 Formula nodes) |
| `theory/lecture/04closure.tex` | `\paragraph{}` headings, images, custom `question` env |

Run all tests: `./demos/demo_tag_all.sh`

## Known Issues and Technical Debt

### Content-stream tagging is coarse
MCIDs are assigned per BT/ET text block (one per block), not per text
operator.  The matching between structure elements and MCIDs uses word-
overlap heuristic scoring (`_match_score` in `pdf_tagger.py`).  Many
structure elements may remain unlinked.

### Preamble noise
The parser doesn't skip content before `\begin{document}`.  Preamble
macros like `\pagestyle{empty}` get their args extracted as paragraph
text.  Fix: detect `\begin{document}` in `_walk()` and only emit nodes
after that point.

### Parent tree is simplified
`_build_parent_tree` maps all MCIDs back to `StructTreeRoot` rather than
to their specific parent `StructElem`.  This is technically incorrect per
the PDF spec.  Fix: track which StructElem each MCID was assigned to
during `_link_structure_to_content`.

### Port conflict on macOS
Port 5000 is used by AirPlay Receiver on macOS.  The `run-local.sh`
script uses 5000; you may need to change to 5001 or disable AirPlay.

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

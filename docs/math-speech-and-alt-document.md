# Accessible LaTeX — Implementation Plan (v4: Math-to-Speech + Embedded Alt Document)

## Phases 1–3: Complete

Core pipeline, accessibility remediation (all 7 Adobe checker rules addressed),
web tool with Flask + Docker.

---

## Phase 4: Math-to-Speech + Embedded Alternative Document

### Feature A: Math-to-Speech

Currently, formula alt-text is raw LaTeX (e.g. `$\frac{a}{b}$`).  A screen
reader says the raw markup, which is unintelligible.  We want natural-language
speech text (e.g. "a over b").

#### Design: Pluggable engine approach

A common `math_speech.py` module exposes a single interface.  The engine
is selected via CLI flag `--math-speech <engine>` (default: `sre`).

```python
# Public interface (identical for all engines)
def latex_to_speech(formulas: list[str], engine: str = "sre") -> list[str]:
    """Convert LaTeX formulas to speech text. Returns same-length list."""
```

Engines are registered as simple functions.  Adding a new engine is a one-
function addition — no class hierarchies or plugin frameworks.

#### Engine 1: `sre` — latex2mathml (Python) + SRE (Node.js)

**Pipeline:** LaTeX → MathML (latex2mathml, pure Python) → speech (SRE)

Uses a small custom Node.js script (`scripts/sre_worker.js`) that reads
MathML lines from stdin and writes JSON speech results to stdout.  Python
launches one subprocess per `latex_to_speech()` call, writes all formulas,
reads all results, then the process exits.

This is a **short-lived batch subprocess**, not a long-running daemon.  The
Node process starts, processes all formulas for the document, and terminates.
There is no persistent IPC, no global singleton, no lifecycle management.

**Why not shell out per formula?**  Benchmarking shows SRE CLI startup
is ~1s per invocation (V8 init + SRE module load).  For the pumping-lemma
homework (138 formulas), that's 138s of pure overhead.  A single batch
subprocess pays the ~1s startup once and processes all 138 formulas in
under 2s total.

**Why not a long-running daemon (previous session's approach)?**  You're
right that IPC is overkill.  A persistent process requires lifecycle
management (startup, health checks, crash recovery, shutdown).  The batch
subprocess is simpler: start → write all → read all → exit.  No state,
no watchdog, no singleton.  This follows our isolation principles.

**References supporting batch subprocess over per-invocation:**
- Node.js process lifecycle documentation notes V8 initialization adds
  hundreds of milliseconds per spawn (thenodebook.com).
- Google's Abseil C++ Tips recommend batching subprocess work to amortize
  fork/exec overhead — same principle applies to Node.js.

**Fallback:** if Node/npx not available, returns raw LaTeX.

#### Engine 2: `mathjax` — mathjax-full + SRE (all Node.js)

**Pipeline:** LaTeX → MathML (mathjax-full) → speech (SRE), all in Node.js

Same batch subprocess pattern as Engine 1 but uses a different Node script
(`scripts/mathjax_worker.js`) that uses mathjax-full instead of receiving
MathML from Python.  This handles more LaTeX edge cases (e.g. custom macros,
`\mbox{}` inside math) because mathjax-full is a full TeX parser.

**Same architecture as Engine 1:** short-lived batch subprocess, not a
daemon.  Python sends raw LaTeX strings, Node returns speech text.

**Trade-offs vs Engine 1:**
- Better LaTeX coverage (mathjax-full is a complete TeX engine)
- Heavier dependency (mathjax-full is ~30MB vs latex2mathml at ~100KB)
- Requires `npm install` to set up dependencies

#### Engine comparison

| | `sre` (Engine 1) | `mathjax` (Engine 2) |
|---|---|---|
| LaTeX→MathML | Python (latex2mathml) | Node.js (mathjax-full) |
| MathML→Speech | Node.js (SRE) | Node.js (SRE) |
| LaTeX coverage | Common constructs | Full TeX parser |
| Python deps | latex2mathml (100KB) | none |
| Node deps | speech-rule-engine | mathjax-full + SRE (~30MB) |
| Architecture | Batch subprocess | Batch subprocess |

### Feature B: Embedded Alternative Document

For complex documents where structure tagging is imperfect, embed a
complete HTML version of the document as a PDF attachment.  Users or
assistive tech can extract this as a fully accessible fallback.

**Implementation:**
- New file: `altex/alt_document.py` — isolated module.
- Interface: `generate_alt_html(tree: DocumentNode, title: str) -> str`
- Generates a self-contained HTML document from the DocumentNode tree.
  Headings, lists, paragraphs map to HTML elements.  Math formulas get
  `<math>` MathML elements (via latex2mathml) with speech text as aria-label.
  Code blocks get `<pre><code>`.
- `embed_alt_document(pdf_path, html_content, output_path)` — uses pikepdf's
  `AttachedFileSpec` to embed the HTML as a PDF attachment with
  `AFRelationship = /Alternative`.
- CLI flag: `--embed-alt` to enable.

### File structure

```
altex/
├── math_speech.py      # NEW — pluggable engine interface (isolated)
└── alt_document.py     # NEW — HTML generation + PDF embedding (isolated)
scripts/
├── sre_worker.js       # NEW — batch MathML→speech via SRE
└── mathjax_worker.js   # NEW — batch LaTeX→speech via mathjax-full+SRE
```

`math_speech.py` imports only stdlib + latex2mathml (for `sre` engine).
`alt_document.py` imports only models + pikepdf + latex2mathml.
Worker scripts are standalone Node.js — no imports from Python.

### Todos

#### 18. `math-speech` — Math-to-speech module
- `altex/math_speech.py`: pluggable engine interface
- `scripts/sre_worker.js`: batch MathML→speech Node script
- `scripts/mathjax_worker.js`: batch LaTeX→speech Node script
- `--math-speech <engine>` CLI flag (choices: sre, mathjax, none)
- Update `latex_parser.py` to accept speech converter callback

#### 19. `alt-document` — Embedded alternative HTML
- `altex/alt_document.py`: generate_alt_html + embed_alt_document
- HTML includes MathML for formulas, proper heading hierarchy, lists
- Embedded as PDF attachment with AFRelationship=/Alternative

#### 20. `cli-web-update` — Wire into CLI + web
- CLI: `--embed-alt` flag, `--math-speech` flag
- Web: checkboxes in frontend, summary shows results

#### 21. `update-docker` — Update Dockerfile for Node.js
- Add nodejs + npm to Docker image for SRE
- Add latex2mathml to requirements.txt
- npm install for mathjax engine dependencies

#### 22. `update-demos` — Update demos + docs
- Demo script showing speech text vs raw LaTeX
- Update AGENTS.md, design.md, README.md

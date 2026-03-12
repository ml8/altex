# Testing Strategy for altex

## Overview

This document outlines the testing strategy for the altex project, explaining what we test, why we test it, and why we exclude certain components from unit testing.

---

## What We Test

### 1. **Models (`tests/test_models.py`)**

We thoroughly test the `DocumentNode` and `Tag` classes because they form the **stable contract** between the parser and the tagging pipeline.

**Why test models?**
- `DocumentNode` is the central data structure passed between pipeline stages
- Changes to serialization (`to_json`, `from_json`) break API contracts
- Tree traversal methods (`collect_by_tag`) are used by downstream systems
- The structure is deterministic and has no heuristics

**What we cover:**
- Tag enum values (ensure PDF/UA-1 compliance)
- DocumentNode initialization and properties
- Serialization/deserialization (JSON round-trips)
- Tree queries (collect_by_tag with various filters)
- Edge cases (empty text, missing children, nested structures)

---

### 2. **Parser (`tests/test_latex_parser.py`)**

We test the parser's ability to handle **standard LaTeX constructs**. The parser's contract is simple: given valid LaTeX input → produce a valid `DocumentNode` tree.

**Why test the parser?**
- Parsing is a deterministic transformation from source to tree
- Standard LaTeX commands have well-defined semantics
- Regressions (e.g., breaking section parsing) are critical to catch early
- The parser doesn't have heuristics—it either handles a construct or it doesn't

**What we cover:**
- Sectioning (`\section`, `\subsection`, etc.)
- Lists (itemize, enumerate, description)
- Math environments (equation, align, inline math)
- Code blocks (verbatim, lstlisting, minted)
- Text content and nested structures
- Unknown macros and edge cases (comments, special characters)

**What we DON'T test:**
- Heuristics for detecting structure from poorly-formatted LaTeX
- Fuzzy matching of intent
- Recovery from malformed input (out of scope for unit tests)

---

### 3. **Web App (`tests/test_web_app.py`)**

We test HTTP endpoints at the **contract level**: request validation, response format, and status codes.

**Why test the API?**
- The HTTP contract must be stable for client integration
- Request validation prevents malformed input from reaching the pipeline
- Security (filename sanitization) is critical
- Status codes communicate failure vs. success to clients

**What we cover:**
- `/healthz` endpoint (health check response)
- `/api/tag` endpoint:
  - Required parameters (tex and pdf files)
  - Optional parameters (lang, fix_encoding, math_speech, embed_alt)
  - Request validation (missing files, unsafe filenames)
  - HTTP methods (POST required, GET/PUT/DELETE rejected)
  - Response format (JSON)

**What we DON'T test:**
- Full pipeline execution (that's integration testing)
- PDF tagging correctness (that requires valid PDFs)
- Math-to-speech conversion (external library, tested separately)
- PDF/UA validation details (delegated to verapdf)

---

## What We DON'T Unit Test (and Why)

### 1. **Tagger Heuristics (`altex/pdf_tagger.py`)**

The tagger uses heuristics to map document nodes to PDF structure. These heuristics are:
- **Unstable**: evolve as we improve detection
- **Context-dependent**: behavior depends on document type, formatting
- **Hard to assert**: no single "correct" answer (e.g., is this a title or heading?)
- **Best tested in integration**: with real PDFs and manual inspection

**Solution:** Use **benchmarks** (not unit tests) with real PDFs to track quality over time.

### 2. **Fuzzy Matching & Heuristics in Parser**

Some parsing decisions are heuristic-based (e.g., detecting structure from whitespace). Unit tests are fragile for heuristics.

**Solution:** Focus unit tests on the **stable contract** (sections, lists, math), not on edge cases that depend on heuristics.

### 3. **External Pipeline (Ghostscript, verapdf)**

PDF encoding fixes and validation are delegated to external tools.

**Solution:** Trust the tools' own test suites. Our unit tests verify we call them correctly; integration tests verify end-to-end behavior.

### 4. **Math-to-Speech Conversion (`altex/math_speech.py`)**

Speech synthesis uses external libraries (MathType, MathJax).

**Solution:** Integration tests with real math expressions; unit tests only for API contracts.

---

## Test Organization

```
tests/
├── conftest.py              # Fixtures: temp dirs, sample LaTeX, trees
├── test_models.py           # DocumentNode and Tag enum
├── test_latex_parser.py     # LaTeX parsing (standard constructs)
└── test_web_app.py          # HTTP API (contracts and validation)
```

### Running Tests

```bash
# Run all tests
pytest tests/

# Run with verbose output
pytest tests/ -v

# Run specific test class
pytest tests/test_models.py::TestDocumentNode -v

# Run with coverage
pytest tests/ --cov=altex --cov=web
```

---

## Benchmarks vs. Unit Tests

**Unit Tests** (in `tests/`)
- Test deterministic transformations
- Verify stable contracts between modules
- Fast (~1-5 seconds)
- Part of CI/CD

**Benchmarks** (in `benchmarks/`)
- Test heuristic quality with real documents
- Track performance and accuracy over time
- May take minutes (use real PDFs)
- Run manually before releases

Example benchmark:
```python
# benchmarks/test_tagger_accuracy.py
def test_tagging_accuracy(real_pdf_dir):
    """Verify tagging accuracy on a corpus of PDFs."""
    for pdf_path in real_pdf_dir.glob("*.pdf"):
        tree = parse_document(pdf_path)
        tagged = tag(pdf_path, tree)
        assert tagged.validation_before.errors > tagged.validation_after.errors
```

---

## Coverage Goals

- **Models**: 100% (stable, deterministic)
- **Parser core**: 90%+ (standard LaTeX constructs)
- **Web app API**: 100% (critical contracts)
- **Tagger heuristics**: 0% unit tests (use benchmarks instead)

---

## Future: Integration Tests

Once unit tests are solid, we'll add integration tests:

```python
# tests/integration/test_pipeline.py
def test_pipeline_with_real_pdf(sample_pdf, sample_tex):
    """Full pipeline: parse TeX, tag PDF, validate result."""
    tree = parse(sample_tex)
    tagged_pdf = tag(sample_pdf, tree)
    validation = validate_pdfua(tagged_pdf)
    assert validation.passed
```

Integration tests will verify the full pipeline, but won't replace unit tests.

---

## Summary

| Component | Unit Test | Benchmark | Integration |
|-----------|-----------|-----------|-------------|
| Models (DocumentNode, Tag) | ✅ Yes | — | — |
| Parser (standard LaTeX) | ✅ Yes | — | ✅ Later |
| Tagger (heuristics) | ❌ No | ✅ Yes | ✅ Later |
| Web API (contracts) | ✅ Yes | — | ✅ Later |
| External tools | ❌ No | — | ✅ Later |

This strategy ensures we catch regressions in stable components while leaving room for heuristic improvements without brittle tests.

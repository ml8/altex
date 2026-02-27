# Tool Audit: altex vs. verapdf, PAVE, and the PDF/UA Landscape

## 1. verapdf: Role, Reputation, and Relevance

### What verapdf is

verapdf is an open-source **validator** (not a remediator) for PDF/A and
PDF/UA standards.  It is developed by the Open Preservation Foundation,
funded by the EU PREFORMA project, and maintained with support from the
PDF Association.  It checks a PDF against the ISO 14289-1 (PDF/UA-1)
specification and reports every rule violation with clause references,
error counts, and context paths.

### Reputation in the literature

verapdf is an open-source PDF/UA validator.  Key points from the accessibility literature:

- The PDF Association's own comparative study of validators (verapdf,
  PAC, Acrobat Preflight, CommonLook) found verapdf provides the most
  **strict, standards-conformant** parsing and reporting.
- Government institutions, libraries, and accessibility platforms
  (Streamline, PDFix) integrate verapdf as their preferred validator.
- Academic reviews of digital preservation (Bitsgalore/JHOVE comparisons)
  cite verapdf as essential for systematic risk identification.
- A 2025 benchmark paper (arXiv:2509.18965) recommends hybrid
  approaches—automated rule checking (verapdf) plus human review—as
  no tool can fully assess semantic appropriateness alone.

### How altex should use verapdf

verapdf is a **validation oracle**, not a competitor.  We should:

1. **Integrate it as our CI/regression benchmark** (done: `scripts/benchmark.sh`)
2. **Parse its structured output to prioritize fixes** (done: `scripts/benchmark_report.py`)
3. **Not attempt to replicate its validation logic**—it already does this
   better than we ever would

verapdf does *not* remediate PDFs.  It tells you what's wrong.  altex
remediates.  They are complementary.


## 2. PAVE PDF: ML-based Heuristic Approach

### What PAVE does

PAVE (PDF Accessibility Validation Engine) is a web application from
ZHAW (Zurich) that uses **machine learning and visual heuristics** to
detect document structure (headings, paragraphs, tables, lists, reading
order) from the PDF's rendered appearance.  It then guides users through
8 semi-automatic remediation steps.

### Why altex's approach is fundamentally better for our use case

PAVE operates on PDFs **without access to source documents**.  It must
reverse-engineer structure from visual layout—an inherently lossy
process.  This is the right approach when source documents are
unavailable (e.g., scanned documents, legacy PDFs).

altex has access to the **LaTeX source**, which is a fully structured,
machine-readable document.  This gives us:

| Capability | PAVE (visual/ML) | altex (source-informed) |
|------------|-------------------|------------------------|
| Heading detection | Heuristic (font size/weight) | Exact (`\section`, `\subsection`) |
| List structure | Visual pattern matching | Exact (`\begin{enumerate}`, `\begin{itemize}`) |
| Math formulas | Flag for manual alt-text | Extract exact LaTeX, convert to speech |
| Reading order | ML inference | Implicit in source document order |
| Table structure | Visual cell detection | Exact (`\begin{tabular}` column specs) |
| Figure captions | OCR/ML | Exact (`\caption{...}`) |
| Code blocks | Not supported | Exact (`\begin{verbatim}`, `\begin{lstlisting}`) |

**Bottom line:** When source is available, heuristic matching is
unnecessary and introduces errors.  We should use the source document as
the authoritative reference for structure, not try to infer it from the
rendered PDF.

### What we can learn from PAVE

Despite the different approach, PAVE's **8-step remediation workflow**
highlights areas we may be under-serving:

1. **Reading order** — we don't currently emit `/StructTreeRoot` children
   in source-document order; we should verify this is correct
2. **Table structure** — PAVE handles table headers (`/TH`) and row
   spans; our parser extracts tables but the tagger may not emit full
   table structure tags (`/Table`, `/TR`, `/TD`, `/TH`)
3. **Math formula alt-text** — PAVE flags this for manual input; we can
   auto-generate it from LaTeX source, which is a significant advantage


## 3. Benchmark Results Analysis

### What altex fixes (5 rules, all documents)

| Rule | Clause | What it fixes |
|------|--------|---------------|
| MarkInfo/Marked | 6.2:1 | Catalog → MarkInfo → Marked = true |
| DisplayDocTitle | 7.1:10 | ViewerPreferences → DisplayDocTitle = true |
| StructTreeRoot | 7.1:11 | Structure hierarchy rooted in StructTreeRoot |
| Metadata stream | 7.1:8 | XMP metadata with dc:title |
| Natural language | 7.2:34 | /Lang attribute on document catalog |

These are **metadata and structural scaffolding** fixes.  altex handles
them correctly across all 8 test documents.

### What remains broken (5 rules, prioritized by impact)

#### Priority 1: §7.1:3 — Content not marked as Artifact or tagged (1,964 failures)

**This is the dominant failure**, accounting for 96% of all remaining
check failures.  Every `BT/ET` text block in the content stream must
either be:
- Wrapped in a `BDC /Tag <</MCID N>> ... EMC` sequence linked to a
  structure element, OR
- Wrapped in a `BDC /Artifact ... EMC` sequence

Currently, altex wraps all `BT/ET` blocks with MCIDs but the structure
tree doesn't successfully link to all of them.  The root cause is the
**text-matching heuristic** in `_link_structure_to_content()`:

- Content items within MCID-tagged regions that don't match any structure
  element remain "orphaned"—they have MCIDs but no parent StructElem
  actually references them via `/K` MCR entries
- The parent tree maps all MCIDs to StructTreeRoot (known tech debt),
  which verapdf correctly flags as invalid structure

**Fix direction:**
- Every content item must either be linked to a StructElem or marked as
  `/Artifact` (page numbers, headers/footers, decorative rules, etc.)
- The LaTeX source tells us exactly which content is structural
  (sections, paragraphs, formulas) and which is decorative (page
  numbers via `\thepage`, horizontal rules via `\hrule`)
- We should use source-document knowledge to classify content items
  rather than relying solely on fuzzy text matching

#### Priority 2: §7.2:20 — LI elements contain invalid children (55 failures)

PDF/UA requires that `/LI` (List Item) elements contain only `/Lbl`
(label/bullet) and `/LBody` (body) children.  Our tagger emits `/LI`
with text content directly, without the required `/Lbl` + `/LBody`
wrapper structure.

**Fix direction:** In `_build_element()`, when building a LIST_ITEM
node, wrap children in `/LBody` and optionally emit `/Lbl` for the
bullet/number character.

#### Priority 3: §5:1 — Missing PDF/UA Identification (8 failures, 1 per doc)

The XMP metadata must contain a `pdfuaid:part` value declaring PDF/UA-1
conformance.  This is a **trivial metadata fix**—add the PDF/UA
identification schema to the XMP packet.

**Fix direction:** In `pdf_tagger.py`, when setting XMP metadata, add:
```xml
<rdf:Description rdf:about=""
    xmlns:pdfuaid="http://www.aiim.org/pdfua/ns/id/">
  <pdfuaid:part>1</pdfuaid:part>
</rdf:Description>
```

#### Priority 4: §7.21.7:1 — Font ToUnicode mapping (9 failures)

Some fonts lack `ToUnicode` CMap entries.  Ghostscript (`--fix-encoding`)
fixes most but not all.  The remaining failures are typically in symbol
or math fonts that use custom encodings.

**Fix direction:** This is largely a LaTeX/font issue.  We can:
- Detect affected glyphs and add `/ActualText` spans as a workaround
- Or accept this as a limitation of source PDF quality

#### Priority 5: §7.4.2:1 — Heading sequence (1 failure, 04closure only)

A heading level is skipped (e.g., H1 → H3 without H2).  This comes from
the LaTeX source using `\paragraph{}` which our parser maps to H4
without ensuring H2/H3 exist first.

**Fix direction:** Validate heading hierarchy in the parser or tagger
and either renumber or warn.

### Overall progress metric

**Internal corpus (8 documents):**

| Metric | Original | Tagged | Tagged+Encoded |
|--------|----------|--------|----------------|
| Total failed checks | 3,774 | 27 | 16 |
| Failure rate | 41.7% | 0.05% | 0.03% |

**Full corpus (15 documents, including external .edu sources):**

| Metric | Original | Tagged | Tagged+Encoded |
|--------|----------|--------|----------------|
| Total failed checks | 15,430 | 1,733 | 1,589 |
| Failure rate | 54.3% | 0.7% | 0.7% |

altex now fixes **12 of the original rule categories** across all test
documents.  The internal corpus achieves high PDF/UA-1 compliance
(0.03% failure rate with encoding fix).  The external corpus reveals
additional failure categories specific to certain document types.

### New failure categories from external corpus

The external .edu benchmark corpus (7 documents) revealed failure
categories not present in the internal corpus:

1. **§7.18.x — Link annotations** (tufts-beamer: 978 failures)
   Beamer slides with hyperlinks require link annotations to be tagged
   as `/Link` elements with alt descriptions.  altex doesn't currently
   handle PDF annotations.

2. **§7.3:1 — Figure alt text** (wm-thesis: 2, bu-cs237-hw: 1)
   Figures without `\caption{}` still need `/Alt` text on their
   `/Figure` StructElem.  Our parser falls back to empty alt text.

3. **§7.21.7:1 — Font ToUnicode** (duke-cv: 280, duke-exam: 154)
   PostScript-based PDFs (dvips→ps2pdf) have far more ToUnicode
   failures than pdflatex-generated PDFs.

4. **§7.4.2:1 — Heading hierarchy** (bu-cs237-hw: 1)
   The heading normalization fix resolved this for our internal corpus
   but the external homework uses `\section*{}` (unnumbered) mixed
   with custom heading macros that the parser doesn't detect.


## 4. Recommendations

### Immediate wins (informed by benchmarks)

1. **Add PDF/UA Identification to XMP metadata** (§5:1)
   - Effort: ~5 lines of code in `pdf_tagger.py`
   - Impact: Eliminates 8 failures, signals PDF/UA conformance intent

2. **Wrap LI children in LBody** (§7.2:20)
   - Effort: Small change to `_build_element()` in `pdf_tagger.py`
   - Impact: Eliminates 55 failures

3. **Validate heading hierarchy** (§7.4.2:1)
   - Effort: Small validation pass in parser or tagger
   - Impact: Eliminates 1 failure, improves semantic correctness

### Medium-term improvements

4. **Artifact marking for decorative content** (§7.1:3 partial fix)
   - Use LaTeX source to identify page numbers, headers, footers, rules
   - Mark corresponding PDF content items as `/Artifact` instead of
     trying to link them to structure elements
   - This alone could eliminate hundreds of §7.1:3 failures

5. **Fix parent tree to map MCIDs to actual parent StructElems**
   - Currently all MCIDs → StructTreeRoot (known tech debt)
   - Correct mapping would fix many §7.1:3 failures where content IS
     tagged but verapdf can't trace the parentage

### Strategic direction

6. **Use verapdf as the regression oracle**
   - Run `scripts/benchmark.sh` before/after every change
   - Track failure counts over time
   - The benchmark report already provides the data; we need to
     compare runs

7. **Maximize source-document information usage**
   - Unlike PAVE (which must guess), we know exactly what each piece of
     content is from the LaTeX source
   - Every heuristic match in `_link_structure_to_content()` represents
     information loss—we have the ground truth in the `.tex` file
   - Future work should focus on positional/structural matching (e.g.,
     "the 3rd paragraph on page 2 corresponds to the 3rd P node in the
     tree") rather than text-content matching


## 5. Tools We Should and Should Not Use

### Should use
- **verapdf** — as validation oracle (already integrated)
- **pikepdf** — PDF structure manipulation (already using)
- **pymupdf** — PDF text extraction (already using)
- **pylatexenc** — LaTeX parsing (already using)

### Should NOT use
- **PAVE** — designed for source-less remediation; we have source
- **ML-based structure detection** — unnecessary when structure is
  explicit in LaTeX source
- **PAC (PDF Accessibility Checker)** — Windows-only, proprietary;
  verapdf covers the same checks cross-platform
- **Adobe Acrobat Preflight** — proprietary; verapdf is more strict and
  more automatable

### Could explore later
- **tagpdf (LaTeX package)** — produces tagged PDFs directly from LaTeX;
  could be used as a comparison baseline or even as an alternative
  approach to post-processing
- **axessibility (LaTeX package)** — adds alt-text to math in LaTeX;
  could inform our math-speech approach
- **latex2pdf/pdflatex with -dPDFSETTINGS** — some LaTeX engines can
  produce partially-tagged PDFs; comparing their output to ours would
  be informative

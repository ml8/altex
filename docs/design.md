# altex Design Document

## Architecture

altex is a two-stage pipeline that makes LaTeX-generated PDFs accessible:

```
LaTeX source (.tex)     Compiled PDF (.pdf)
        |                       |
        v                       |
+----------------+              |
|  latex_parser  |              |
|  pylatexenc    |              |
+-------+--------+              |
        |  DocumentNode tree    |
        v                       v
+----------------------------------+
|  pdf_tagger                      |
|  pikepdf + pymupdf               |
+---------------+------------------+
                |
                v
         Tagged PDF (.pdf)
```

An optional pre-processing step (`encoding_fixer`) runs Ghostscript to
normalize font encodings before tagging.

### Module responsibilities

| Module           | Responsibility                          | Dependencies       |
|------------------|----------------------------------------|---------------------|
| `models.py`      | `Tag` enum + `DocumentNode` dataclass  | stdlib only         |
| `latex_parser`   | LaTeX source → `DocumentNode` tree     | pylatexenc, models  |
| `pdf_tagger`     | Embed structure tree + MCIDs into PDF  | pikepdf, pymupdf, models |
| `encoding_fixer` | Ghostscript font re-encoding           | stdlib only (subprocess) |
| `cli.py`         | Argument parsing, orchestration        | latex_parser, pdf_tagger |
| `web/app.py`     | Flask HTTP API + static serving        | flask, latex_parser, pdf_tagger |

### Interface contract

The **only** shared data structure is `DocumentNode` (defined in `models.py`).
The parser produces one; the tagger consumes one.  They share no other state.

`encoding_fixer` is fully isolated — it imports nothing from altex and
communicates only through file paths.

## Design decisions

1. **Standard LaTeX only.**  The parser handles core LaTeX commands
   (`\section`, `\begin{itemize}`, `$...$`, etc.).  Class-specific macros
   (e.g. `awesome-cv`'s `\cventry`) are handled generically by extracting
   text from their arguments.

2. **Raw LaTeX as math alt-text.**  Formula nodes store the original LaTeX
   source (e.g. `$E = mc^2$`) as alt-text.  A production tool could convert
   this to natural-language descriptions or MathML.

3. **Content-stream tagging.**  Each BT/ET text block in the PDF is wrapped
   in BDC/EMC marked-content operators with MCIDs.  Structure elements
   reference these MCIDs.  Text matching between the LaTeX parse tree and
   PDF content is heuristic (word-overlap scoring).

4. **pylatexenc 2.x.**  We use the stable v2 API (`LatexWalker`,
   `LatexNodes2Text`).  v3 has a different API and is less widely deployed.

5. **pikepdf for PDF manipulation.**  pikepdf wraps QPDF and gives full
   access to PDF objects, which is needed for building structure trees and
   modifying content streams.  pymupdf is used for text extraction to
   support content-stream matching.

6. **Isolated encoding fixer.**  The Ghostscript wrapper has zero altex
   imports and communicates only through file paths.  This keeps it
   independently testable and swappable.

7. **Single-container web deployment.**  Flask serves both the API and
   the static frontend.  No build step for the frontend (one HTML file
   with inline CSS/JS).

## Accessibility features implemented

| Feature                      | PDF/UA Requirement        | Status   |
|------------------------------|--------------------------|----------|
| Structure tree               | Tagged PDF               | ✅       |
| Document language (`/Lang`)  | Primary language set     | ✅       |
| Document title               | Title in metadata        | ✅       |
| Display title in title bar   | ViewerPreferences        | ✅       |
| Tab order                    | `/Tabs /S` on pages      | ✅       |
| Marked content (BDC/EMC)     | Content-stream MCIDs     | ✅       |
| Alt-text for math            | `/Alt` on Formula elems  | ✅       |
| Alt-text for code            | `/Alt` on Code elems     | ✅       |
| Alt-text for figures         | `/Alt` on Figure elems   | ✅       |
| Font encoding fix            | ToUnicode / glyph names  | ✅ (via Ghostscript) |
| Parent tree                  | MCID → StructElem map    | ✅       |

## Known limitations (PoC)

- **Heuristic text matching.**  Content-stream MCIDs are assigned per
  BT/ET block and matched to structure elements via word overlap.  This
  can mis-match or leave elements unlinked.

- **Preamble noise.**  Unknown macros in the preamble (e.g.
  `\pagestyle{empty}`, `\geometry{...}`) produce spurious paragraph text.
  A production tool should skip content before `\begin{document}`.

- **Single-variable inline math.**  Expressions like `$f$` or `$n$`
  generate their own Formula nodes.  A production tool might merge these
  into surrounding paragraph text.

- **Custom environments.**  `\newenvironment` definitions are not
  interpreted; their bodies are parsed generically.

- **No artifact marking.**  Decorative elements (rules, page numbers,
  headers/footers) are not marked as artifacts.

## Future work

1. **Math-to-speech** — convert LaTeX math to natural-language alt-text
   (e.g. using speech-rule-engine or a custom converter).

2. **Preamble filtering** — skip everything before `\begin{document}`.

3. **PDF/UA validation** — integrate a validator (e.g. PAC, veraPDF).

4. **Artifact marking** — mark decorative elements as artifacts.

5. **Finer-grained MCIDs** — match individual text operators (Tj/TJ)
   to structure elements rather than whole BT/ET blocks.

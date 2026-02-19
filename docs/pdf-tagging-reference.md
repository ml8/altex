# PDF Structure Tagging Reference

Quick reference for the PDF structure tags used by altex.

## Tag types

| PDF Tag     | altex `Tag` enum | Meaning                             |
|-------------|------------------|--------------------------------------|
| `/Document` | `DOCUMENT`       | Root of the document tree            |
| `/Sect`     | `SECTION`        | A logical section                    |
| `/H1`       | `HEADING1`       | Top-level heading (`\section`)       |
| `/H2`       | `HEADING2`       | Second-level (`\subsection`)         |
| `/H3`       | `HEADING3`       | Third-level (`\subsubsection`)      |
| `/H4`       | `HEADING4`       | Fourth-level (`\paragraph`)          |
| `/P`        | `PARAGRAPH`      | Paragraph of text                    |
| `/L`        | `LIST`           | List container                       |
| `/LI`       | `LIST_ITEM`      | Individual list item                 |
| `/Formula`  | `FORMULA`        | Mathematical expression              |
| `/Code`     | `CODE`           | Code block                           |
| `/Figure`   | `FIGURE`         | Figure or image                      |

## Key PDF objects

### MarkInfo (document catalog)

```
/MarkInfo << /Marked true >>
```

Signals that the document contains marked content.

### StructTreeRoot (document catalog)

```
/StructTreeRoot <<
  /Type /StructTreeRoot
  /K <reference to root StructElem>
>>
```

### StructElem

```
<<
  /Type /StructElem
  /S /H1                          % structure type
  /P <parent StructElem>          % parent reference
  /K [ <children or MCIDs> ]      % content
  /ActualText (Heading Text)      % literal text content
  /Alt (alt-text description)     % alternative description
>>
```

- `/ActualText` — the literal text this element represents.  Used for
  headings, paragraphs, list items.
- `/Alt` — an alternative description.  Used for formulas (raw LaTeX),
  code blocks (source code), and figures (caption).

## Content-stream marking (future)

To link structure elements to specific content in the PDF page:

```
% In the page content stream:
/H1 << /MCID 0 >> BDC
  ... text-drawing operators ...
EMC
```

The MCID (Marked Content ID) connects the content region to its
StructElem via the parent tree.  This is not yet implemented in the PoC.

## References

- [PDF 2.0 specification (ISO 32000-2)](https://www.iso.org/standard/75839.html) — §14.7 (Logical Structure)
- [PDF/UA (ISO 14289-1)](https://www.iso.org/standard/64599.html) — accessibility requirements
- [Matterhorn Protocol](https://www.pdfa.org/resource/the-matterhorn-protocol/) — PDF/UA conformance testing

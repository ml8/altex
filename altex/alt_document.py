"""Generate and embed an alternative HTML document in a PDF.

Public API
----------
    generate_alt_html(tree, title) -> str
    embed_alt_document(pdf_path, html, output_path) -> None

The HTML serves as a fully accessible fallback for complex documents
where PDF structure tagging is imperfect.  It is embedded as a PDF
attachment with AFRelationship = /Alternative.
"""

from __future__ import annotations

from html import escape
from pathlib import Path

import pikepdf

from altex.models import DocumentNode, Tag

# Map Tag → HTML element (or handler name).
_HTML_MAP: dict[Tag, str] = {
    Tag.HEADING1: "h1",
    Tag.HEADING2: "h2",
    Tag.HEADING3: "h3",
    Tag.HEADING4: "h4",
    Tag.PARAGRAPH: "p",
    Tag.LIST: "ul",
    Tag.LIST_ITEM: "li",
    Tag.CODE: "pre",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_alt_html(tree: DocumentNode, title: str) -> str:
    """Render *tree* as a self-contained HTML document."""
    body = _render(tree)
    return (
        "<!DOCTYPE html>\n"
        f'<html lang="en">\n<head>\n'
        f'<meta charset="utf-8">\n'
        f"<title>{escape(title)}</title>\n"
        f"<style>body{{font-family:system-ui,sans-serif;max-width:50em;"
        f"margin:2em auto;padding:0 1em}}pre{{background:#f5f5f5;"
        f"padding:1em;overflow-x:auto}}math{{font-size:1.1em}}</style>\n"
        f"</head>\n<body>\n{body}</body>\n</html>\n"
    )


def embed_alt_document(
    pdf_path: Path,
    html: str,
    output_path: Path,
) -> None:
    """Embed *html* as an alternative document attachment in the PDF."""
    pdf = pikepdf.open(pdf_path, allow_overwriting_input=True)

    filespec = pikepdf.AttachedFileSpec(
        pdf,
        data=html.encode("utf-8"),
        description="Accessible HTML alternative of this document",
        filename="accessible_alt.html",
        mime_type="text/html",
        relationship=pikepdf.Name("/Alternative"),
    )
    pdf.attachments["accessible_alt.html"] = filespec

    pdf.save(output_path)


# ---------------------------------------------------------------------------
# HTML rendering
# ---------------------------------------------------------------------------


def _render(node: DocumentNode) -> str:
    """Recursively render a DocumentNode to HTML."""
    if node.tag == Tag.DOCUMENT:
        return "\n".join(_render(c) for c in node.children)

    if node.tag == Tag.SECTION:
        return "\n".join(_render(c) for c in node.children) + "\n"

    if node.tag == Tag.FORMULA:
        return _render_formula(node)

    if node.tag == Tag.FIGURE:
        caption = escape(node.text) if node.text else "Figure"
        return f'<figure><figcaption>{caption}</figcaption></figure>\n'

    if node.tag == Tag.CODE:
        return f"<pre><code>{escape(node.text)}</code></pre>\n"

    if node.tag == Tag.LIST:
        items = "\n".join(_render(c) for c in node.children)
        return f"<ul>\n{items}\n</ul>\n"

    if node.tag == Tag.LIST_ITEM:
        inner = " ".join(_render(c) for c in node.children) if node.children else escape(node.text)
        return f"<li>{inner}</li>"

    html_tag = _HTML_MAP.get(node.tag, "span")
    text = escape(node.text) if node.text else ""
    if node.children:
        text += " ".join(_render(c) for c in node.children)
    return f"<{html_tag}>{text}</{html_tag}>\n"


def _render_formula(node: DocumentNode) -> str:
    """Render a formula as MathML with aria-label fallback."""
    text = node.text or ""
    try:
        import latex2mathml.converter as l2m
        from altex.math_speech import _strip_delimiters
        clean = _strip_delimiters(text)
        mathml = l2m.convert(clean)
        return f'<span role="math" aria-label="{escape(text)}">{mathml}</span>'
    except Exception:
        return f'<span role="math" aria-label="{escape(text)}">{escape(text)}</span>'

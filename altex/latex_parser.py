"""Parse LaTeX source into a semantic DocumentNode tree.

Public API
----------
    parse(tex_path) -> DocumentNode

The parser handles standard LaTeX commands:
  - Sectioning:  \\section .. \\paragraph
  - Lists:       itemize, enumerate, description
  - Math:        $...$, \\[...\\], equation, align, gather (and starred)
  - Code:        verbatim, lstlisting, minted
  - Figures:     figure environment, \\includegraphics, \\caption
  - Includes:    \\input, \\include

Unknown macros are handled generically by extracting readable text from
their arguments.
"""

from __future__ import annotations

from pathlib import Path

from pylatexenc.latex2text import LatexNodes2Text
from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexWalker,
    get_default_latex_context_db,
)
from pylatexenc.macrospec import MacroSpec

from altex.models import HEADING_TAGS, DocumentNode, Tag

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_SECTION_MACROS: dict[str, int] = {
    "chapter": 0,
    "section": 0,
    "subsection": 1,
    "subsubsection": 2,
    "paragraph": 3,
}

_MATH_ENVIRONMENTS = frozenset({
    "equation", "equation*",
    "align", "align*",
    "gather", "gather*",
    "multline", "multline*",
    "flalign", "flalign*",
    "displaymath",
})

_CODE_ENVIRONMENTS = frozenset({
    "verbatim", "lstlisting", "minted",
})

_LIST_ENVIRONMENTS = frozenset({
    "itemize", "enumerate", "description",
})

_l2t = LatexNodes2Text()


def _make_latex_context():
    """Extend the default pylatexenc context with missing macro specs."""
    db = get_default_latex_context_db()
    db.add_context_category(
        "altex-extras",
        macros=[
            # \paragraph has the same arg pattern as \section: *[{
            MacroSpec("paragraph", "*[{"),
            # \href{url}{text} — hyperlink (hyperref package).
            MacroSpec("href", "{{"),
            # \url{url} — verbatim URL (url/hyperref packages).
            MacroSpec("url", "{"),
        ],
    )
    return db


_latex_context = _make_latex_context()


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse(tex_path: Path) -> DocumentNode:
    """Parse *tex_path* and return a semantic document tree."""
    root = DocumentNode(Tag.DOCUMENT)
    _parse_file(tex_path, root)
    _normalize_headings(root)
    return root


def extract_title(tex_path: Path) -> str:
    """Extract the document title from ``\\title{...}``, or return ``""``."""
    source = tex_path.read_text(errors="replace")
    walker = LatexWalker(source, latex_context=_latex_context)
    nodes, _, _ = walker.get_latex_nodes()
    for node in nodes:
        if isinstance(node, LatexMacroNode) and node.macroname == "title":
            return _macro_arg_text(node).strip()
    return ""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _parse_file(tex_path: Path, parent: DocumentNode) -> None:
    """Parse a single .tex file and append nodes to *parent*."""
    source = tex_path.read_text(errors="replace")
    walker = LatexWalker(source, latex_context=_latex_context)
    nodes, _, _ = walker.get_latex_nodes()
    _walk(nodes, parent, tex_path.parent)


def _walk(
    nodes: list,
    parent: DocumentNode,
    base_dir: Path,
) -> None:
    """Walk pylatexenc nodes and build the DocumentNode tree under *parent*."""
    for node in nodes:
        if node is None:
            continue

        if isinstance(node, LatexMacroNode):
            _handle_macro(node, parent, base_dir)

        elif isinstance(node, LatexMathNode):
            _handle_math(node, parent)

        elif isinstance(node, LatexEnvironmentNode):
            _handle_environment(node, parent, base_dir)

        elif isinstance(node, LatexCharsNode):
            _handle_text(node, parent)

        elif isinstance(node, LatexGroupNode):
            _walk(node.nodelist or [], parent, base_dir)


def _handle_macro(
    node: LatexMacroNode,
    parent: DocumentNode,
    base_dir: Path,
) -> None:
    name = node.macroname

    # -- Sectioning --------------------------------------------------------
    if name in _SECTION_MACROS:
        depth = _SECTION_MACROS[name]
        # For starred sections (\section*{...}), the argspec is "*[{".
        # argnlist[0] is the star, argnlist[2] is the brace group.
        # Use _macro_brace_text to skip the star and optional bracket.
        heading_text = _macro_brace_text(node).strip()
        section = DocumentNode(Tag.SECTION)
        section.children.append(
            DocumentNode(HEADING_TAGS.get(depth, Tag.HEADING4), heading_text)
        )
        parent.children.append(section)
        return

    # -- Includes ----------------------------------------------------------
    if name in ("input", "include"):
        filename = _macro_arg_text(node)
        if filename:
            path = base_dir / filename
            if not path.suffix:
                path = path.with_suffix(".tex")
            if path.is_file():
                _parse_file(path, parent)
        return

    # -- Hyperlinks --------------------------------------------------------
    # \href{url}{text} → LINK node with display text and url as alt-text.
    # \url{url} → LINK node with url as both text and alt-text.
    # PDF/UA §7.18.5 requires links to be tagged as /Link StructElems.
    if name == "href":
        args = node.nodeargd.argnlist if node.nodeargd else []
        url = _node_to_text(args[0]).strip() if len(args) > 0 and args[0] else ""
        text = _node_to_text(args[1]).strip() if len(args) > 1 and args[1] else url
        if text or url:
            parent.children.append(DocumentNode(Tag.LINK, text or url))
        return

    if name == "url":
        url = _macro_arg_text(node).strip()
        if url:
            parent.children.append(DocumentNode(Tag.LINK, url))
        return

    # -- Everything else: extract plain text -------------------------------
    text = _node_to_text(node)
    if text.strip():
        _append_text(parent, text)


def _handle_math(node: LatexMathNode, parent: DocumentNode) -> None:
    """Inline or display math → FORMULA node with raw LaTeX as alt-text."""
    # Reconstruct the LaTeX source for use as alt-text.
    raw = node.latex_verbatim()
    parent.children.append(DocumentNode(Tag.FORMULA, raw.strip()))


def _handle_environment(
    node: LatexEnvironmentNode,
    parent: DocumentNode,
    base_dir: Path,
) -> None:
    name = node.environmentname

    # -- Math environments -------------------------------------------------
    if name in _MATH_ENVIRONMENTS:
        raw = node.latex_verbatim()
        parent.children.append(DocumentNode(Tag.FORMULA, raw.strip()))
        return

    # -- Code environments -------------------------------------------------
    if name in _CODE_ENVIRONMENTS:
        raw = node.latex_verbatim()
        parent.children.append(DocumentNode(Tag.CODE, raw.strip()))
        return

    # -- Lists -------------------------------------------------------------
    if name in _LIST_ENVIRONMENTS:
        list_node = DocumentNode(Tag.LIST)
        _walk_list_items(node.nodelist or [], list_node, base_dir)
        parent.children.append(list_node)
        return

    # -- Figures -----------------------------------------------------------
    if name == "figure":
        caption = _find_macro_text("caption", node.nodelist or [])
        # PDF/UA §7.3:1 — Figure elements must have non-empty /Alt text.
        # If no \caption{} is found, fall back to the image filename.
        if not caption:
            img = _find_macro_text("includegraphics", node.nodelist or [])
            caption = f"Figure: {img}" if img else "Figure"
        parent.children.append(DocumentNode(Tag.FIGURE, caption))
        return

    # -- Generic: recurse into environment body ----------------------------
    _walk(node.nodelist or [], parent, base_dir)


def _handle_text(node: LatexCharsNode, parent: DocumentNode) -> None:
    text = node.chars.strip()
    if text:
        _append_text(parent, text)


# ---------------------------------------------------------------------------
# List processing
# ---------------------------------------------------------------------------


def _walk_list_items(
    nodes: list,
    list_node: DocumentNode,
    base_dir: Path,
) -> None:
    """Group nodes between \\item macros into LIST_ITEM children."""
    current_item: DocumentNode | None = None
    for node in nodes:
        if node is None:
            continue
        if isinstance(node, LatexMacroNode) and node.macroname == "item":
            current_item = DocumentNode(Tag.LIST_ITEM)
            list_node.children.append(current_item)
            # \item may have optional [...] argument (description lists)
            label = _macro_arg_text(node)
            if label:
                _append_text(current_item, label)
        elif current_item is not None:
            _walk([node], current_item, base_dir)
        # text before the first \item is ignored (whitespace)


# ---------------------------------------------------------------------------
# Text extraction helpers
# ---------------------------------------------------------------------------


def _node_to_text(node) -> str:
    """Best-effort plain-text extraction from a single node."""
    try:
        raw = node.latex_verbatim()
        return _l2t.latex_to_text(raw)
    except Exception:
        return ""


def _macro_arg_text(node: LatexMacroNode) -> str:
    """Return plain text of the first non-None argument of *node*."""
    if not node.nodeargd:
        return ""
    for arg in node.nodeargd.argnlist:
        if arg is not None:
            return _node_to_text(arg)
    return ""


def _macro_brace_text(node: LatexMacroNode) -> str:
    """Return plain text of the first brace-group argument of *node*.

    Unlike ``_macro_arg_text``, this skips star (``*``) and bracket
    (``[...]``) arguments.  Used for sectioning commands where the
    argspec is ``*[{`` and we want only the ``{...}`` content, not
    the optional star modifier.
    """
    if not node.nodeargd:
        return ""
    for arg in node.nodeargd.argnlist:
        if arg is None:
            continue
        if isinstance(arg, LatexGroupNode):
            return _node_to_text(arg)
    # Fallback: return first non-None arg.
    return _macro_arg_text(node)


def _find_macro_text(macro_name: str, nodes: list) -> str:
    """Recursively find ``\\macro_name{...}`` in *nodes* and return its text.

    Used to extract ``\\caption{...}`` and ``\\includegraphics{...}`` from
    figure environments.
    """
    for node in nodes:
        if isinstance(node, LatexMacroNode) and node.macroname == macro_name:
            return _macro_arg_text(node)
        if isinstance(node, LatexGroupNode):
            result = _find_macro_text(macro_name, node.nodelist or [])
            if result:
                return result
    return ""


def _append_text(parent: DocumentNode, text: str) -> None:
    """Append text to the last PARAGRAPH child, or create one."""
    if parent.children and parent.children[-1].tag == Tag.PARAGRAPH:
        parent.children[-1].text += " " + text
    else:
        parent.children.append(DocumentNode(Tag.PARAGRAPH, text))


# ---------------------------------------------------------------------------
# Heading hierarchy normalization
# ---------------------------------------------------------------------------

# Ordered list of heading tags from highest (H1) to lowest (H4).
_HEADING_TAGS_ORDERED = [Tag.HEADING1, Tag.HEADING2, Tag.HEADING3, Tag.HEADING4]


def _normalize_headings(root: DocumentNode) -> None:
    """Renumber headings so the sequence starts at H1 with no gaps.

    PDF/UA-1 §7.4.2 (verapdf rule §7.4.2:1) requires that if heading
    tags are used, H1 must be the first, and heading levels must not
    skip intervening levels.  LaTeX documents that use only
    ``\\paragraph{}`` (H4) or ``\\subsection{}`` (H2) without higher-
    level headings would violate this rule.

    This function first removes empty headings (preamble noise from
    macros like ``\\titleformat{\\subsection}``), then collects all
    heading levels used in the tree and maps them to a compact
    sequence starting at H1.
    """
    # Remove headings with empty text (preamble noise).
    _prune_empty_headings(root)

    used: set[Tag] = set()
    _collect_heading_tags(root, used)
    if not used:
        return

    # Build remap: used levels → compact H1..Hn sequence.
    sorted_used = sorted(used, key=lambda t: _HEADING_TAGS_ORDERED.index(t))
    remap = {
        old: _HEADING_TAGS_ORDERED[i]
        for i, old in enumerate(sorted_used)
    }

    # Only apply if there's actually a change needed.
    if any(k != v for k, v in remap.items()):
        _apply_heading_remap(root, remap)


def _collect_heading_tags(node: DocumentNode, out: set[Tag]) -> None:
    """Recursively collect all heading tags used in the tree."""
    if node.tag in _HEADING_TAGS_ORDERED:
        out.add(node.tag)
    for child in node.children:
        _collect_heading_tags(child, out)


def _apply_heading_remap(node: DocumentNode, remap: dict[Tag, Tag]) -> None:
    """Recursively apply a heading tag remap to the tree."""
    if node.tag in remap:
        node.tag = remap[node.tag]
    for child in node.children:
        _apply_heading_remap(child, remap)


def _prune_empty_headings(node: DocumentNode) -> None:
    """Remove heading nodes with empty text and their empty parent sections.

    Preamble noise (e.g., ``\\titleformat{\\subsection}``) can produce
    section/heading nodes with no text.  These confuse the heading
    hierarchy normalization and should be removed.
    """
    heading_tags = set(_HEADING_TAGS_ORDERED)
    node.children = [
        child for child in node.children
        if not (
            child.tag == Tag.SECTION
            and len(child.children) == 1
            and child.children[0].tag in heading_tags
            and not child.children[0].text.strip()
        )
    ]
    for child in node.children:
        _prune_empty_headings(child)

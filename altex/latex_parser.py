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
        heading_text = _macro_arg_text(node).strip()
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
        caption = _extract_caption(node.nodelist or [])
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


def _extract_caption(nodes: list) -> str:
    """Find \\caption{...} in *nodes* and return its text."""
    for node in nodes:
        if isinstance(node, LatexMacroNode) and node.macroname == "caption":
            return _macro_arg_text(node)
        if isinstance(node, LatexGroupNode):
            result = _extract_caption(node.nodelist or [])
            if result:
                return result
    return ""


def _append_text(parent: DocumentNode, text: str) -> None:
    """Append text to the last PARAGRAPH child, or create one."""
    if parent.children and parent.children[-1].tag == Tag.PARAGRAPH:
        parent.children[-1].text += " " + text
    else:
        parent.children.append(DocumentNode(Tag.PARAGRAPH, text))

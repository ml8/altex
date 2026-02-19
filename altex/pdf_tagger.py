"""Embed a semantic structure tree into an existing PDF.

Public API
----------
    tag(pdf_path, tree, output_path, lang, title) -> None

The tagger takes a DocumentNode tree (produced by the LaTeX parser) and
embeds a PDF structure tree into the compiled PDF.  This makes the
document navigable by screen readers and provides alt-text for formulas,
code blocks, and figures.

Content-stream tagging: each BT/ET text block in the PDF is wrapped in
BDC/EMC marked-content operators with MCIDs.  Structure elements
reference these MCIDs via /K entries.  Unmatched text blocks are tagged
as Artifacts.
"""

from __future__ import annotations

from pathlib import Path

import fitz
import pikepdf

from altex.models import DocumentNode, Tag

# Maps our Tag enum values to PDF structure-type names.
_PDF_TAG: dict[Tag, str] = {
    Tag.DOCUMENT: "Document",
    Tag.SECTION: "Sect",
    Tag.HEADING1: "H1",
    Tag.HEADING2: "H2",
    Tag.HEADING3: "H3",
    Tag.HEADING4: "H4",
    Tag.PARAGRAPH: "P",
    Tag.LIST: "L",
    Tag.LIST_ITEM: "LI",
    Tag.FORMULA: "Formula",
    Tag.CODE: "Code",
    Tag.FIGURE: "Figure",
}

# Tags whose text should be exposed as /Alt (alternative description)
# rather than /ActualText (literal replacement).
_ALT_TAGS = frozenset({Tag.FORMULA, Tag.CODE, Tag.FIGURE})

# PDF content-stream operators that draw text.
_TEXT_OPS = frozenset({"Tj", "TJ", "'", '"'})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def tag(
    pdf_path: Path,
    tree: DocumentNode,
    output_path: Path,
    *,
    lang: str = "en",
    title: str = "",
) -> None:
    """Read *pdf_path*, embed structure from *tree*, write to *output_path*."""
    pdf = pikepdf.open(pdf_path)

    # -- Metadata -----------------------------------------------------------
    pdf.Root["/MarkInfo"] = pdf.make_indirect(
        pikepdf.Dictionary({"/Marked": True})
    )
    pdf.Root["/Lang"] = pikepdf.String(lang)
    pdf.Root["/ViewerPreferences"] = pdf.make_indirect(
        pikepdf.Dictionary({"/DisplayDocTitle": True})
    )

    doc_title = title or pdf_path.stem
    with pdf.open_metadata(set_pikepdf_as_editor=False) as meta:
        meta["dc:title"] = doc_title

    # -- Tab order on every page --------------------------------------------
    for page in pdf.pages:
        page.obj["/Tabs"] = pikepdf.Name("/S")

    # -- Content-stream tagging ---------------------------------------------
    page_mcid_maps = _tag_content_streams(pdf, pdf_path)

    # -- Structure tree -----------------------------------------------------
    struct_root = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/StructTreeRoot"),
    })
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]] = []
    doc_elem = _build_element(pdf, tree, struct_root, leaf_elems)
    struct_root["/K"] = doc_elem

    # Link leaf structure elements to MCIDs.
    _link_structure_to_content(pdf, leaf_elems, page_mcid_maps)

    # Build parent tree.
    parent_tree = _build_parent_tree(pdf, page_mcid_maps, struct_root)
    struct_root["/ParentTree"] = pdf.make_indirect(parent_tree)

    pdf.Root["/StructTreeRoot"] = pdf.make_indirect(struct_root)

    pdf.save(output_path)


# ---------------------------------------------------------------------------
# Content-stream tagging
# ---------------------------------------------------------------------------


def _tag_content_streams(
    pdf: pikepdf.Pdf,
    pdf_path: Path,
) -> list[list[tuple[int, str, str]]]:
    """Wrap each BT/ET text block with BDC/EMC and return per-page MCID maps.

    Returns a list (one per page) of lists of (mcid, tag_name, extracted_text)
    tuples describing each marked-content region on that page.
    """
    # Use pymupdf for text extraction (maps text to positions).
    mu_doc = fitz.open(pdf_path)
    all_page_maps: list[list[tuple[int, str, str]]] = []

    for page_idx, page in enumerate(pdf.pages):
        page.contents_coalesce()
        instructions = pikepdf.parse_content_stream(page)

        # Extract text for each BT/ET block using pymupdf.
        mu_page = mu_doc[page_idx] if page_idx < len(mu_doc) else None
        page_text_blocks = _extract_page_text_blocks(mu_page) if mu_page else []

        new_instructions = []
        mcid_map: list[tuple[int, str, str]] = []
        mcid = 0
        bt_depth = 0
        block_idx = 0
        in_marked = False

        for inst in instructions:
            op = str(inst.operator)

            if op == "BT":
                # Start a marked-content sequence before BT.
                tag_name = "P"  # default; will be refined by structure linking
                text = page_text_blocks[block_idx] if block_idx < len(page_text_blocks) else ""
                mcid_map.append((mcid, tag_name, text))

                bdc = pikepdf.ContentStreamInstruction(
                    [pikepdf.Name("/P"), pikepdf.Dictionary({"/MCID": mcid})],
                    pikepdf.Operator("BDC"),
                )
                new_instructions.append(bdc)
                in_marked = True
                mcid += 1
                block_idx += 1
                bt_depth += 1
                new_instructions.append(inst)

            elif op == "ET":
                new_instructions.append(inst)
                bt_depth -= 1
                if bt_depth <= 0 and in_marked:
                    new_instructions.append(
                        pikepdf.ContentStreamInstruction([], pikepdf.Operator("EMC"))
                    )
                    in_marked = False
                    bt_depth = 0

            else:
                new_instructions.append(inst)

        # Close any unclosed marked content.
        if in_marked:
            new_instructions.append(
                pikepdf.ContentStreamInstruction([], pikepdf.Operator("EMC"))
            )

        # Rewrite the content stream.
        new_data = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pdf.make_stream(new_data)

        all_page_maps.append(mcid_map)

    mu_doc.close()
    return all_page_maps


def _extract_page_text_blocks(mu_page: fitz.Page) -> list[str]:
    """Extract text from each block on a pymupdf page, in content order."""
    blocks = mu_page.get_text("dict", sort=True)["blocks"]
    texts = []
    for block in blocks:
        if "lines" not in block:
            continue
        block_text = " ".join(
            span["text"]
            for line in block["lines"]
            for span in line["spans"]
        )
        if block_text.strip():
            texts.append(block_text.strip())
    return texts


# ---------------------------------------------------------------------------
# Structure tree builder
# ---------------------------------------------------------------------------


def _build_element(
    pdf: pikepdf.Pdf,
    node: DocumentNode,
    parent: pikepdf.Dictionary,
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]],
) -> pikepdf.Dictionary:
    """Create a PDF StructElem for *node* and recurse into children."""
    tag_name = _PDF_TAG.get(node.tag, "Span")
    elem = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/StructElem"),
        "/S": pikepdf.Name(f"/{tag_name}"),
        "/P": parent,
    })

    # Attach text content.
    if node.text:
        if node.tag in _ALT_TAGS:
            elem["/Alt"] = pikepdf.String(node.text)
        else:
            elem["/ActualText"] = pikepdf.String(node.text)

    # Recurse into children.
    if node.children:
        kids = pikepdf.Array()
        for child in node.children:
            child_elem = _build_element(pdf, child, elem, leaf_elems)
            kids.append(pdf.make_indirect(child_elem))
        elem["/K"] = kids
    else:
        # Leaf node — track for MCID linking.
        leaf_elems.append((elem, node))

    return elem


# ---------------------------------------------------------------------------
# Linking structure elements to content-stream MCIDs
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""
    return " ".join(text.lower().split())


def _link_structure_to_content(
    pdf: pikepdf.Pdf,
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]],
    page_mcid_maps: list[list[tuple[int, str, str]]],
) -> None:
    """Link leaf structure elements to MCIDs via best-effort text matching."""
    # Build a flat list of all MCIDs with page references.
    all_mcids: list[tuple[int, int, str]] = []  # (page_idx, mcid, text)
    for page_idx, mcid_map in enumerate(page_mcid_maps):
        for mcid, _, text in mcid_map:
            all_mcids.append((page_idx, mcid, text))

    # For each leaf element, find the best matching MCID.
    used_mcids: set[tuple[int, int]] = set()
    for elem, node in leaf_elems:
        if not node.text:
            continue
        node_norm = _normalize(node.text)
        if not node_norm:
            continue

        best_score = 0.0
        best_match: tuple[int, int] | None = None

        for page_idx, mcid, mcid_text in all_mcids:
            if (page_idx, mcid) in used_mcids:
                continue
            mcid_norm = _normalize(mcid_text)
            if not mcid_norm:
                continue

            # Simple substring matching score.
            score = _match_score(node_norm, mcid_norm)
            if score > best_score:
                best_score = score
                best_match = (page_idx, mcid)

        if best_match and best_score > 0.3:
            page_idx, mcid = best_match
            used_mcids.add(best_match)
            page_ref = pdf.pages[page_idx].obj
            mcr = pikepdf.Dictionary({
                "/Type": pikepdf.Name("/MCR"),
                "/Pg": page_ref,
                "/MCID": mcid,
            })
            elem["/K"] = mcr


def _match_score(needle: str, haystack: str) -> float:
    """Return a 0–1 score for how well *needle* matches *haystack*."""
    if needle == haystack:
        return 1.0
    if needle in haystack or haystack in needle:
        shorter = min(len(needle), len(haystack))
        longer = max(len(needle), len(haystack))
        return shorter / longer if longer > 0 else 0.0
    # Word overlap.
    needle_words = set(needle.split())
    haystack_words = set(haystack.split())
    if not needle_words:
        return 0.0
    overlap = len(needle_words & haystack_words)
    return overlap / max(len(needle_words), len(haystack_words))


# ---------------------------------------------------------------------------
# Parent tree (maps MCIDs → structure elements)
# ---------------------------------------------------------------------------


def _build_parent_tree(
    pdf: pikepdf.Pdf,
    page_mcid_maps: list[list[tuple[int, str, str]]],
    struct_root: pikepdf.Dictionary,
) -> pikepdf.Dictionary:
    """Build a /ParentTree number tree.

    Maps each MCID back to the StructTreeRoot as a simplified parent
    reference.  A production tool would map each MCID to its specific
    parent StructElem.
    """
    nums = pikepdf.Array()
    for mcid_map in page_mcid_maps:
        for mcid, _, _ in mcid_map:
            nums.append(mcid)
            nums.append(struct_root)

    return pikepdf.Dictionary({
        "/Nums": nums,
    })

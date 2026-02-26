"""Embed a semantic structure tree into an existing PDF.

Public API
----------
    tag(pdf_path, tree, output_path, lang, title) -> None

The tagger takes a DocumentNode tree (produced by the LaTeX parser) and
embeds a PDF structure tree into the compiled PDF.  This makes the
document navigable by screen readers and provides alt-text for formulas,
code blocks, and figures.

PDF/UA-1 compliance (ISO 14289-1)
----------------------------------
The tagger addresses these PDF/UA requirements:

- §5:1   — PDF/UA identification via ``pdfuaid:part`` in XMP metadata
- §6.2:1 — ``/MarkInfo`` dictionary with ``/Marked = true``
- §7.1:3 — All content marked as Artifact or tagged with MCIDs
- §7.1:8 — XMP metadata stream with ``dc:title``
- §7.1:10 — ``/DisplayDocTitle`` in viewer preferences
- §7.1:11 — Structure tree rooted in ``/StructTreeRoot``
- §7.2:20 — ``/LI`` elements contain only ``/Lbl`` and ``/LBody``
- §7.2:34 — ``/Lang`` attribute on document catalog
- §7.21.7 — Unicode mapping via ``/ActualText`` on marked content

Content-stream tagging wraps each text operator (Tj/TJ) inside a BT/ET
block in its own BDC/EMC marked-content sequence with a unique MCID.
Non-text content (graphics, paths) is wrapped as ``/Artifact``.
Structure elements reference MCIDs via ``/K`` entries, and the parent
tree maps each MCID back to its owning StructElem.

References
----------
- ISO 32000-1:2008 §14.6 — Marked content
- ISO 32000-1:2008 §14.7 — Logical structure
- ISO 32000-1:2008 §14.8 — Tagged PDF
- ISO 14289-1:2014      — PDF/UA-1
- verapdf rules: https://docs.verapdf.org/validation/pdfa-part1/
"""

from __future__ import annotations

from pathlib import Path

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
    Tag.LINK: "Link",
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
        # PDF/UA-1 identification (ISO 14289-1 §5, verapdf rule §5:1).
        # Declares that this PDF intends to conform to PDF/UA-1.
        meta["pdfuaid:part"] = "1"

    # -- Tab order on every page --------------------------------------------
    for page in pdf.pages:
        page.obj["/Tabs"] = pikepdf.Name("/S")

    # -- Content-stream tagging ---------------------------------------------
    page_mcid_maps = _tag_content_streams(pdf, pdf_path)

    # -- Set /StructParents on each page ------------------------------------
    # Each page with marked content must declare its key into the parent
    # tree's number tree (ISO 32000-1:2008 §14.7.4.4).  We use the page
    # index as the key.
    for page_idx, page in enumerate(pdf.pages):
        page.obj["/StructParents"] = page_idx

    # -- Structure tree -----------------------------------------------------
    struct_root = pikepdf.Dictionary({
        "/Type": pikepdf.Name("/StructTreeRoot"),
    })
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]] = []
    doc_elem = _build_element(pdf, tree, struct_root, leaf_elems)
    struct_root["/K"] = doc_elem

    # Link leaf structure elements to MCIDs.
    ownership = _link_structure_to_content(pdf, leaf_elems, page_mcid_maps)

    # Link PDF annotations to /Link StructElems (PDF/UA §7.18.5).
    annot_parent_entries = _link_annotations_to_structure(
        pdf, leaf_elems, struct_root,
    )

    # Build parent tree (reverse mapping: MCID → owning StructElem).
    # The parent tree also includes annotation parent entries.
    parent_tree = _build_parent_tree(
        pdf, page_mcid_maps, struct_root, ownership, annot_parent_entries,
    )
    struct_root["/ParentTree"] = pdf.make_indirect(parent_tree)
    # /ParentTreeNextKey: pages use keys 0..N-1, annotations start at N.
    struct_root["/ParentTreeNextKey"] = (
        len(pdf.pages) + len(annot_parent_entries)
    )

    pdf.Root["/StructTreeRoot"] = pdf.make_indirect(struct_root)

    pdf.save(output_path)


# ---------------------------------------------------------------------------
# Content-stream tagging
# ---------------------------------------------------------------------------


def _tag_content_streams(
    pdf: pikepdf.Pdf,
    pdf_path: Path,
) -> list[list[tuple[int, str]]]:
    """Wrap each text operator in its own BDC/EMC and non-text as Artifact.

    PDF/UA-1 §7.1:3 requires every content item to be either tagged
    (linked to a structure element via MCID) or marked as Artifact.

    This function places BDC/EMC *inside* BT/ET blocks, wrapping each
    individual text-drawing operator (Tj, TJ, ', ") with a unique MCID.
    Content outside BT/ET blocks (graphics, paths, transforms) is wrapped
    as ``/Artifact`` (ISO 32000-1:2008 §14.8.2.2).

    Text is extracted directly from the TJ/Tj operands, avoiding the
    need for a separate pymupdf text-extraction pass.

    Returns a list (one per page) of ``(mcid, extracted_text)`` tuples.
    """
    all_page_maps: list[list[tuple[int, str]]] = []

    for page_idx, page in enumerate(pdf.pages):
        page.contents_coalesce()
        instructions = pikepdf.parse_content_stream(page)

        new_instructions: list[pikepdf.ContentStreamInstruction] = []
        mcid_map: list[tuple[int, str]] = []
        mcid = 0
        in_bt = False
        # Accumulate non-BT instructions for artifact wrapping.
        pending_non_bt: list[pikepdf.ContentStreamInstruction] = []

        for inst in instructions:
            op = str(inst.operator)

            if op == "BT":
                # Flush pending non-BT content as Artifact.
                _flush_artifact(new_instructions, pending_non_bt)
                pending_non_bt = []
                new_instructions.append(inst)
                in_bt = True

            elif op == "ET":
                new_instructions.append(inst)
                in_bt = False

            elif in_bt and op in _TEXT_OPS:
                # Wrap this text operator in its own BDC/EMC with a
                # unique MCID (ISO 32000-1 §14.6, "marked-content
                # sequence").  Using /Span as the structure type for
                # individual text runs; the actual semantic type comes
                # from the StructElem that links to this MCID.
                #
                # /ActualText provides a Unicode fallback for fonts
                # without ToUnicode CMaps (ISO 14289-1 §7.21.7,
                # verapdf rule §7.21.7:1).
                text = _extract_tj_text(inst)
                mcid_map.append((mcid, text))

                props = pikepdf.Dictionary({"/MCID": mcid})
                if text:
                    props["/ActualText"] = pikepdf.String(text)

                bdc = pikepdf.ContentStreamInstruction(
                    [pikepdf.Name("/Span"), props],
                    pikepdf.Operator("BDC"),
                )
                emc = pikepdf.ContentStreamInstruction(
                    [], pikepdf.Operator("EMC"),
                )
                new_instructions.append(bdc)
                new_instructions.append(inst)
                new_instructions.append(emc)
                mcid += 1

            elif in_bt:
                # Non-text instructions inside BT/ET (Tf, Td, Tm, etc.)
                # stay as-is — they set graphics state, not content.
                new_instructions.append(inst)

            else:
                # Outside BT/ET — accumulate for artifact wrapping.
                pending_non_bt.append(inst)

        # Flush any remaining non-BT content at end of stream.
        _flush_artifact(new_instructions, pending_non_bt)

        # Rewrite the content stream.
        new_data = pikepdf.unparse_content_stream(new_instructions)
        page.Contents = pdf.make_stream(new_data)
        all_page_maps.append(mcid_map)

    return all_page_maps


def _flush_artifact(
    out: list[pikepdf.ContentStreamInstruction],
    pending: list[pikepdf.ContentStreamInstruction],
) -> None:
    """Wrap accumulated non-text instructions in an Artifact BDC/EMC.

    PDF/UA-1 §7.1:3 — decorative content (rules, backgrounds, page
    furniture) must be marked as Artifact so assistive technology can
    skip it.  See ISO 32000-1:2008 §14.8.2.2.
    """
    if not pending:
        return
    bdc = pikepdf.ContentStreamInstruction(
        [pikepdf.Name("/Artifact"), pikepdf.Dictionary()],
        pikepdf.Operator("BDC"),
    )
    emc = pikepdf.ContentStreamInstruction(
        [], pikepdf.Operator("EMC"),
    )
    out.append(bdc)
    out.extend(pending)
    out.append(emc)


def _extract_tj_text(inst: pikepdf.ContentStreamInstruction) -> str:
    """Extract readable text from a Tj/TJ content-stream instruction.

    TJ arrays contain alternating strings and numeric kerning values.
    We concatenate the string parts.  The result is in font encoding
    (often Latin-1 for standard LaTeX fonts), not guaranteed Unicode,
    but sufficient for fuzzy text matching against the LaTeX source.
    """
    operand = inst.operands[0]
    if isinstance(operand, pikepdf.Array):
        parts: list[str] = []
        for item in operand:
            if isinstance(item, (pikepdf.String, bytes)):
                parts.append(bytes(item).decode("latin-1", errors="replace"))
        return "".join(parts)
    if isinstance(operand, pikepdf.String):
        return bytes(operand).decode("latin-1", errors="replace")
    return ""


# ---------------------------------------------------------------------------
# Structure tree builder
# ---------------------------------------------------------------------------


def _build_element(
    pdf: pikepdf.Pdf,
    node: DocumentNode,
    parent: pikepdf.Dictionary,
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]],
) -> pikepdf.Dictionary:
    """Create a PDF StructElem for *node* and recurse into children.

    For LIST_ITEM nodes, children are wrapped in an ``/LBody`` container
    to satisfy PDF/UA-1 §7.2 (verapdf rule §7.2:20), which requires
    ``/LI`` elements to contain only ``/Lbl`` and ``/LBody`` children.

    See ISO 32000-1:2008 §14.8.4.3.3 (list elements).
    """
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
        if node.tag == Tag.LIST_ITEM:
            # PDF/UA §7.2:20 — LI must contain only Lbl and LBody.
            # Wrap all children in an /LBody container element.
            lbody = pikepdf.Dictionary({
                "/Type": pikepdf.Name("/StructElem"),
                "/S": pikepdf.Name("/LBody"),
                "/P": elem,
            })
            lbody_kids = pikepdf.Array()
            for child in node.children:
                child_elem = _build_element(pdf, child, lbody, leaf_elems)
                lbody_kids.append(pdf.make_indirect(child_elem))
            lbody["/K"] = lbody_kids
            elem["/K"] = pikepdf.Array([pdf.make_indirect(lbody)])
        else:
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
    page_mcid_maps: list[list[tuple[int, str]]],
) -> dict[tuple[int, int], pikepdf.Dictionary]:
    """Link leaf structure elements to MCIDs via text matching.

    With per-TJ MCIDs, each MCID contains a short text fragment.  A
    single StructElem (e.g., a paragraph) typically spans multiple TJ
    operators, so one StructElem may link to many MCIDs.  The ``/K``
    entry on the StructElem becomes an Array of MCR (marked-content
    reference) dictionaries.

    Returns a mapping from ``(page_idx, mcid)`` to the StructElem that
    owns it — this is used by ``_build_parent_tree`` to create correct
    reverse mappings (ISO 32000-1:2008 §14.7.4.4).
    """
    # Build a flat list of all MCIDs with page references.
    all_mcids: list[tuple[int, int, str]] = []  # (page_idx, mcid, text)
    for page_idx, mcid_map in enumerate(page_mcid_maps):
        for mcid, text in mcid_map:
            all_mcids.append((page_idx, mcid, text))

    if not all_mcids:
        return {}

    # Ownership map: (page_idx, mcid) → StructElem that claims it.
    ownership: dict[tuple[int, int], pikepdf.Dictionary] = {}

    # For each leaf element, find all MCIDs whose text is a substring
    # of the node's text (or vice versa).  This allows one StructElem
    # to claim multiple TJ fragments.
    used_mcids: set[tuple[int, int]] = set()

    for elem, node in leaf_elems:
        if not node.text:
            continue
        node_norm = _normalize(node.text)
        if not node_norm:
            continue

        matched_mcrs: list[pikepdf.Dictionary] = []

        for page_idx, mcid, mcid_text in all_mcids:
            if (page_idx, mcid) in used_mcids:
                continue
            mcid_norm = _normalize(mcid_text)
            if not mcid_norm:
                continue

            score = _match_score(node_norm, mcid_norm)
            if score > 0.3:
                page_ref = pdf.pages[page_idx].obj
                mcr = pikepdf.Dictionary({
                    "/Type": pikepdf.Name("/MCR"),
                    "/Pg": page_ref,
                    "/MCID": mcid,
                })
                matched_mcrs.append(mcr)
                used_mcids.add((page_idx, mcid))
                ownership[(page_idx, mcid)] = elem

        if matched_mcrs:
            if len(matched_mcrs) == 1:
                elem["/K"] = matched_mcrs[0]
            else:
                elem["/K"] = pikepdf.Array(matched_mcrs)

    return ownership


def _match_score(needle: str, haystack: str) -> float:
    """Return a 0–1 score for how well *needle* matches *haystack*.

    Used for fuzzy matching between LaTeX source text (from the
    DocumentNode) and PDF content-stream text (from TJ operands).
    Supports exact match, substring containment, and word overlap.
    """
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
# Annotation → structure linking (PDF/UA §7.18)
# ---------------------------------------------------------------------------


def _link_annotations_to_structure(
    pdf: pikepdf.Pdf,
    leaf_elems: list[tuple[pikepdf.Dictionary, DocumentNode]],
    struct_root: pikepdf.Dictionary,
) -> list[tuple[int, pikepdf.Dictionary]]:
    """Link PDF link annotations to ``/Link`` StructElems.

    PDF/UA-1 §7.18.5 (verapdf rules §7.18.5:1, §7.18.5:2) requires
    that link annotations be tagged as ``/Link`` structure elements.
    §7.18.1:2 requires annotations to have ``/Contents`` or ``/Alt``.

    For each link annotation found in the PDF, this function:

    1. Sets ``/Contents`` on the annotation (alt description).
    2. Assigns ``/StructParent`` to the annotation (key into parent tree).
    3. Creates an OBJR (object reference) in the matching ``/Link``
       StructElem's ``/K`` entry (ISO 32000-1:2008 §14.7.4.3).

    Returns a list of ``(parent_tree_key, struct_elem)`` pairs for
    annotation entries in the parent tree.
    """
    # Collect /Link StructElems from leaf_elems.
    link_elems: list[tuple[pikepdf.Dictionary, DocumentNode]] = [
        (elem, node) for elem, node in leaf_elems
        if node.tag == Tag.LINK
    ]

    annot_parent_entries: list[tuple[int, pikepdf.Dictionary]] = []
    # Annotation parent tree keys start after page keys.
    next_key = len(pdf.pages)
    link_idx = 0

    for page_idx, page in enumerate(pdf.pages):
        annots = page.obj.get("/Annots")
        if not annots:
            continue

        for annot_ref in annots:
            annot = annot_ref
            if not isinstance(annot, pikepdf.Dictionary):
                continue

            # Only process /Link annotations.
            if str(annot.get("/Subtype", "")) != "/Link":
                continue

            # Extract URL for alt description.
            action = annot.get("/A")
            uri = ""
            if isinstance(action, pikepdf.Dictionary):
                uri_obj = action.get("/URI")
                if uri_obj is not None:
                    uri = str(uri_obj)

            dest = annot.get("/Dest")
            alt_text = uri or (str(dest) if dest else "Link")

            # §7.18.1:2 — Set /Contents on annotation.
            if "/Contents" not in annot:
                annot["/Contents"] = pikepdf.String(alt_text)

            # §7.18.5:1 — Assign /StructParent for parent tree.
            annot["/StructParent"] = next_key

            # Find a matching /Link StructElem.
            matched_elem = None
            if link_idx < len(link_elems):
                matched_elem = link_elems[link_idx][0]
                link_idx += 1
            else:
                # No parser-produced /Link node; create one.
                matched_elem = pikepdf.Dictionary({
                    "/Type": pikepdf.Name("/StructElem"),
                    "/S": pikepdf.Name("/Link"),
                    "/P": struct_root,
                    "/Alt": pikepdf.String(alt_text),
                })
                # Append to the document element's children.
                doc_elem = struct_root["/K"]
                if "/K" in doc_elem:
                    k = doc_elem["/K"]
                    if isinstance(k, pikepdf.Array):
                        k.append(pdf.make_indirect(matched_elem))
                    else:
                        doc_elem["/K"] = pikepdf.Array(
                            [k, pdf.make_indirect(matched_elem)]
                        )
                else:
                    doc_elem["/K"] = pdf.make_indirect(matched_elem)

            # Create OBJR (object reference) linking StructElem → annotation.
            objr = pikepdf.Dictionary({
                "/Type": pikepdf.Name("/OBJR"),
                "/Pg": page.obj,
                "/Obj": annot_ref,
            })

            # Add OBJR to the StructElem's /K.
            existing_k = matched_elem.get("/K")
            if existing_k is None:
                matched_elem["/K"] = objr
            elif isinstance(existing_k, pikepdf.Array):
                existing_k.append(objr)
            else:
                matched_elem["/K"] = pikepdf.Array([existing_k, objr])

            annot_parent_entries.append((next_key, matched_elem))
            next_key += 1

    return annot_parent_entries


# ---------------------------------------------------------------------------
# Parent tree (maps MCIDs → structure elements)
# ---------------------------------------------------------------------------


def _build_parent_tree(
    pdf: pikepdf.Pdf,
    page_mcid_maps: list[list[tuple[int, str]]],
    struct_root: pikepdf.Dictionary,
    ownership: dict[tuple[int, int], pikepdf.Dictionary],
    annot_parent_entries: list[tuple[int, pikepdf.Dictionary]] | None = None,
) -> pikepdf.Dictionary:
    """Build a ``/ParentTree`` number tree (ISO 32000-1:2008 §14.7.4.4).

    The parent tree maps each page's MCIDs back to their owning
    StructElem.  verapdf rule §7.1:3 checks both directions: StructElem
    → MCID (via ``/K``) and MCID → StructElem (via ``/ParentTree``).

    Each entry in ``/Nums`` is: ``page_index, [elem_for_mcid_0,
    elem_for_mcid_1, ...]``.  MCIDs not linked to any StructElem are
    mapped to ``struct_root`` as a fallback.

    Annotation parent entries (from ``_link_annotations_to_structure``)
    are appended with keys starting after the page keys.
    """
    nums = pikepdf.Array()

    for page_idx, mcid_map in enumerate(page_mcid_maps):
        if not mcid_map:
            continue
        # Build an array of parent refs, one per MCID on this page.
        parents = pikepdf.Array()
        for mcid, _ in mcid_map:
            parent_elem = ownership.get((page_idx, mcid), struct_root)
            parents.append(parent_elem)
        nums.append(page_idx)
        nums.append(pdf.make_indirect(parents))

    # Append annotation parent entries (§7.18.5).
    if annot_parent_entries:
        for key, elem in annot_parent_entries:
            nums.append(key)
            nums.append(elem)

    return pikepdf.Dictionary({
        "/Nums": nums,
    })

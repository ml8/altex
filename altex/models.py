"""Semantic document tree used as the interface between parser and tagger.

The parser produces a tree of DocumentNode values.  The tagger reads that
tree and embeds the corresponding structure into a PDF.  This module is
the *only* shared data structure between the two stages.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Self


class Tag(Enum):
    """PDF structure-tag types produced by the LaTeX parser."""

    DOCUMENT = "Document"
    SECTION = "Sect"
    HEADING1 = "H1"
    HEADING2 = "H2"
    HEADING3 = "H3"
    HEADING4 = "H4"
    PARAGRAPH = "P"
    LIST = "L"
    LIST_ITEM = "LI"
    FORMULA = "Formula"
    CODE = "Code"
    FIGURE = "Figure"
    LINK = "Link"


# Map LaTeX sectioning depth to heading tag.
HEADING_TAGS = {
    0: Tag.HEADING1,   # \section  or \chapter in report/book
    1: Tag.HEADING2,   # \subsection
    2: Tag.HEADING3,   # \subsubsection
    3: Tag.HEADING4,   # \paragraph
}


@dataclass
class DocumentNode:
    """A single node in the semantic document tree.

    *tag*  — the PDF structure role (see ``Tag``).
    *text* — plain-text content of the node.  For leaf nodes this is the
             readable text; for FORMULA / CODE / FIGURE it is the alt-text
             (raw LaTeX source, source code, or caption respectively).
    *children* — ordered child nodes.
    """

    tag: Tag
    text: str = ""
    children: list[DocumentNode] = field(default_factory=list)

    # -- Serialisation (for --dump-tree) -----------------------------------

    def to_dict(self) -> dict:
        d: dict = {"tag": self.tag.value}
        if self.text:
            d["text"] = self.text
        if self.children:
            d["children"] = [c.to_dict() for c in self.children]
        return d

    @classmethod
    def from_dict(cls, d: dict) -> Self:
        return cls(
            tag=Tag(d["tag"]),
            text=d.get("text", ""),
            children=[cls.from_dict(c) for c in d.get("children", [])],
        )

    def to_json(self, **kwargs) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_json(cls, s: str) -> Self:
        return cls.from_dict(json.loads(s))

    # -- Tree queries ------------------------------------------------------

    def collect_by_tag(self, tag: Tag) -> list[DocumentNode]:
        """Return all descendants (including self) with the given tag."""
        result: list[DocumentNode] = []
        if self.tag == tag and self.text:
            result.append(self)
        for child in self.children:
            result.extend(child.collect_by_tag(tag))
        return result

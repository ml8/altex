"""Tests for altex.models module.

Tests the DocumentNode data structure and Tag enum.
"""

from __future__ import annotations

import json

from altex.models import HEADING_TAGS, DocumentNode, Tag


class TestTag:
    """Test the Tag enum."""

    def test_all_tags_defined(self):
        """Verify all expected PDF structure tags are defined."""
        expected = {
            "DOCUMENT",
            "SECTION",
            "HEADING1",
            "HEADING2",
            "HEADING3",
            "HEADING4",
            "PARAGRAPH",
            "LIST",
            "LIST_ITEM",
            "FORMULA",
            "CODE",
            "FIGURE",
            "LINK",
        }
        actual = {member.name for member in Tag}
        assert actual == expected

    def test_tag_values(self):
        """Verify tag enum values match PDF/UA-1 conventions."""
        assert Tag.DOCUMENT.value == "Document"
        assert Tag.SECTION.value == "Sect"
        assert Tag.HEADING1.value == "H1"
        assert Tag.HEADING2.value == "H2"
        assert Tag.HEADING3.value == "H3"
        assert Tag.HEADING4.value == "H4"
        assert Tag.PARAGRAPH.value == "P"
        assert Tag.LIST.value == "L"
        assert Tag.LIST_ITEM.value == "LI"
        assert Tag.FORMULA.value == "Formula"
        assert Tag.CODE.value == "Code"
        assert Tag.FIGURE.value == "Figure"
        assert Tag.LINK.value == "Link"

    def test_heading_tags_mapping(self):
        """Verify heading depth-to-tag mapping."""
        assert HEADING_TAGS[0] == Tag.HEADING1
        assert HEADING_TAGS[1] == Tag.HEADING2
        assert HEADING_TAGS[2] == Tag.HEADING3
        assert HEADING_TAGS[3] == Tag.HEADING4


class TestDocumentNode:
    """Test DocumentNode data structure and methods."""

    def test_initialization_defaults(self):
        """Test DocumentNode creation with defaults."""
        node = DocumentNode(Tag.PARAGRAPH)
        assert node.tag == Tag.PARAGRAPH
        assert node.text == ""
        assert node.children == []

    def test_initialization_with_text(self):
        """Test DocumentNode creation with text."""
        node = DocumentNode(Tag.PARAGRAPH, text="Hello world")
        assert node.tag == Tag.PARAGRAPH
        assert node.text == "Hello world"
        assert node.children == []

    def test_initialization_with_children(self):
        """Test DocumentNode creation with children."""
        child1 = DocumentNode(Tag.LIST_ITEM, text="Item 1")
        child2 = DocumentNode(Tag.LIST_ITEM, text="Item 2")
        parent = DocumentNode(Tag.LIST, children=[child1, child2])

        assert parent.tag == Tag.LIST
        assert len(parent.children) == 2
        assert parent.children[0].text == "Item 1"
        assert parent.children[1].text == "Item 2"

    def test_to_dict_leaf(self):
        """Test to_dict on a leaf node."""
        node = DocumentNode(Tag.PARAGRAPH, text="Hello")
        d = node.to_dict()

        assert d["tag"] == "P"
        assert d["text"] == "Hello"
        assert "children" not in d

    def test_to_dict_with_children(self):
        """Test to_dict on a tree node."""
        child1 = DocumentNode(Tag.LIST_ITEM, text="Item 1")
        child2 = DocumentNode(Tag.LIST_ITEM, text="Item 2")
        parent = DocumentNode(Tag.LIST, children=[child1, child2])

        d = parent.to_dict()
        assert d["tag"] == "L"
        assert "text" not in d  # No text, so not included
        assert len(d["children"]) == 2
        assert d["children"][0]["tag"] == "LI"
        assert d["children"][0]["text"] == "Item 1"

    def test_to_json(self):
        """Test to_json serialization."""
        node = DocumentNode(Tag.PARAGRAPH, text="Test")
        json_str = node.to_json()

        # Parse it back to verify it's valid JSON
        d = json.loads(json_str)
        assert d["tag"] == "P"
        assert d["text"] == "Test"

    def test_from_dict(self):
        """Test from_dict deserialization."""
        d = {
            "tag": "Document",
            "children": [
                {"tag": "H1", "text": "Title"},
                {"tag": "P", "text": "Paragraph"},
            ],
        }
        node = DocumentNode.from_dict(d)

        assert node.tag == Tag.DOCUMENT
        assert len(node.children) == 2
        assert node.children[0].tag == Tag.HEADING1
        assert node.children[0].text == "Title"
        assert node.children[1].tag == Tag.PARAGRAPH
        assert node.children[1].text == "Paragraph"

    def test_from_json(self):
        """Test from_json deserialization."""
        json_str = '{"tag": "P", "text": "Hello"}'
        node = DocumentNode.from_json(json_str)

        assert node.tag == Tag.PARAGRAPH
        assert node.text == "Hello"
        assert node.children == []

    def test_round_trip_json(self):
        """Test that to_json and from_json are inverses."""
        original = DocumentNode(Tag.DOCUMENT)
        original.children.append(DocumentNode(Tag.HEADING1, text="Title"))
        original.children.append(DocumentNode(Tag.PARAGRAPH, text="Content"))

        json_str = original.to_json()
        restored = DocumentNode.from_json(json_str)

        assert restored.tag == original.tag
        assert len(restored.children) == len(original.children)
        assert restored.children[0].text == original.children[0].text
        assert restored.children[1].text == original.children[1].text

    def test_collect_by_tag_single_match(self):
        """Test collect_by_tag with one matching node."""
        doc = DocumentNode(Tag.DOCUMENT)
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text="Para 1"))
        doc.children.append(DocumentNode(Tag.HEADING1, text="Title"))

        results = doc.collect_by_tag(Tag.HEADING1)
        assert len(results) == 1
        assert results[0].text == "Title"

    def test_collect_by_tag_multiple_matches(self):
        """Test collect_by_tag with multiple matching nodes."""
        doc = DocumentNode(Tag.DOCUMENT)
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text="Para 1"))
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text="Para 2"))
        doc.children.append(DocumentNode(Tag.HEADING1, text="Title"))

        results = doc.collect_by_tag(Tag.PARAGRAPH)
        assert len(results) == 2
        assert results[0].text == "Para 1"
        assert results[1].text == "Para 2"

    def test_collect_by_tag_nested(self, sample_document_tree):
        """Test collect_by_tag on a nested tree structure."""
        results = sample_document_tree.collect_by_tag(Tag.HEADING1)

        # Should find both H1 nodes from the two sections
        assert len(results) == 2
        texts = [r.text for r in results]
        assert "Introduction" in texts
        assert "Methods" in texts

    def test_collect_by_tag_no_matches(self):
        """Test collect_by_tag with no matches."""
        doc = DocumentNode(Tag.DOCUMENT)
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text="Para"))

        results = doc.collect_by_tag(Tag.FIGURE)
        assert results == []

    def test_collect_by_tag_ignores_nodes_without_text(self):
        """Test that collect_by_tag ignores nodes without text."""
        doc = DocumentNode(Tag.DOCUMENT)
        # Node with no text (text="")
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text=""))
        # Node with text
        doc.children.append(DocumentNode(Tag.PARAGRAPH, text="Content"))

        results = doc.collect_by_tag(Tag.PARAGRAPH)
        # Should only find the one with text
        assert len(results) == 1
        assert results[0].text == "Content"

    def test_collect_by_tag_list_items(self, sample_document_tree):
        """Test collect_by_tag on list items."""
        results = sample_document_tree.collect_by_tag(Tag.LIST_ITEM)

        assert len(results) == 2
        texts = [r.text for r in results]
        assert "Item 1" in texts
        assert "Item 2" in texts

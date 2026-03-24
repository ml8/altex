"""Pytest configuration and fixtures.

Provides common fixtures for LaTeX parsing, DocumentNode creation, and sample content.
"""

from __future__ import annotations

import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest

from altex.models import DocumentNode, Tag


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_simple_latex(temp_dir: Path) -> Path:
    """Simple LaTeX document with basic sections and lists."""
    content = r"""
\documentclass{article}
\usepackage[utf-8]{inputenc}
\title{Test Document}
\author{Test Author}

\begin{document}
\maketitle

\section{Introduction}
This is an introduction paragraph.

\subsection{Background}
Some background information.

\begin{itemize}
\item First item
\item Second item
\end{itemize}

\section{Methods}
We used the following approach.

\end{document}
"""
    tex_file = temp_dir / "simple.tex"
    tex_file.write_text(content)
    return tex_file


@pytest.fixture
def sample_math_latex(temp_dir: Path) -> Path:
    """LaTeX document with math formulas."""
    content = r"""
\documentclass{article}
\usepackage{amsmath}

\begin{document}

\section{Mathematics}

The Pythagorean theorem is $a^2 + b^2 = c^2$.

\begin{equation}
E = mc^2
\end{equation}

Inline math: $\int_0^\infty e^{-x} dx = 1$.

\begin{align*}
y &= mx + b \\
\text{slope} &= m
\end{align*}

\end{document}
"""
    tex_file = temp_dir / "math.tex"
    tex_file.write_text(content)
    return tex_file


@pytest.fixture
def sample_code_latex(temp_dir: Path) -> Path:
    """LaTeX document with code blocks."""
    content = r"""
\documentclass{article}

\begin{document}

\section{Code Examples}

\begin{verbatim}
def hello():
    print("Hello, World!")
\end{verbatim}

Some text here.

\end{document}
"""
    tex_file = temp_dir / "code.tex"
    tex_file.write_text(content)
    return tex_file


@pytest.fixture
def sample_nested_lists_latex(temp_dir: Path) -> Path:
    """LaTeX document with nested lists."""
    content = r"""
\documentclass{article}

\begin{document}

\section{Nested Lists}

\begin{enumerate}
\item First item
  \begin{itemize}
  \item Nested item 1
  \item Nested item 2
  \end{itemize}
\item Second item
\end{enumerate}

\end{document}
"""
    tex_file = temp_dir / "nested_lists.tex"
    tex_file.write_text(content)
    return tex_file


@pytest.fixture
def sample_document_tree() -> DocumentNode:
    """Create a sample DocumentNode tree for testing."""
    doc = DocumentNode(Tag.DOCUMENT)

    section1 = DocumentNode(Tag.SECTION, text="Section 1")
    h1 = DocumentNode(Tag.HEADING1, text="Introduction")
    section1.children.append(h1)

    para1 = DocumentNode(Tag.PARAGRAPH, text="This is a paragraph.")
    section1.children.append(para1)

    doc.children.append(section1)

    section2 = DocumentNode(Tag.SECTION, text="Section 2")
    h2 = DocumentNode(Tag.HEADING1, text="Methods")
    section2.children.append(h2)

    lst = DocumentNode(Tag.LIST)
    li1 = DocumentNode(Tag.LIST_ITEM, text="Item 1")
    li2 = DocumentNode(Tag.LIST_ITEM, text="Item 2")
    lst.children.extend([li1, li2])
    section2.children.append(lst)

    doc.children.append(section2)

    return doc

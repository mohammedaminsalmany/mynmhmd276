"""Doca — a modern, lightweight docs-as-code engine and static site generator.

Doca turns a folder of Markdown files into a fast, clean documentation site
with a sidebar, full-text search, auto-generated tables of contents and a
dark/light theme. It is built on the Python standard library alone: no
third-party packages are required for base usage.

Basic usage::

    from doca import render_markdown

    document = render_markdown("# Hello\\n\\nSome **bold** text.")
    print(document.html)
"""

from __future__ import annotations

__title__ = "doca"
__version__ = "0.1.0"
__description__ = "Modern, lightweight docs-as-code engine and static documentation generator"
__author__ = "Mohammed Amin Salmany"
__author_email__ = "mohammedaminsalmany@gmail.com"
__license__ = "MIT"
__url__ = "https://github.com/mohammedaminsalmany/doca"

from .builder import (  # noqa: E402  (after version metadata to avoid a cycle)
    BuildResult,
    DocaError,
    Heading,
    RenderedDocument,
    build_site,
    build_toc,
    load_config,
    parse_frontmatter,
    render_markdown,
    slugify,
)

__all__ = [
    "BuildResult",
    "DocaError",
    "Heading",
    "RenderedDocument",
    "__author__",
    "__version__",
    "build_site",
    "build_toc",
    "load_config",
    "parse_frontmatter",
    "render_markdown",
    "slugify",
]

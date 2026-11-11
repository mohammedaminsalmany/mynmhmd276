"""Tests for the Doca Markdown engine and site builder."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from doca import __version__
from doca.builder import (
    DocaError,
    build_site,
    build_toc,
    load_config,
    parse_frontmatter,
    plain_text,
    render_markdown,
    slugify,
)
from doca.builder import Heading


class FrontMatterTests(unittest.TestCase):
    def test_parses_scalars_and_lists(self) -> None:
        source = (
            "---\n"
            "title: Hello world\n"
            "description: A short page\n"
            "order: 2\n"
            "draft: true\n"
            "tags: [docs, python]\n"
            "authors:\n"
            "  - Ada\n"
            "  - Grace\n"
            "---\n\n"
            "# Body\n"
        )
        meta, body = parse_frontmatter(source)
        self.assertEqual(meta["title"], "Hello world")
        self.assertEqual(meta["description"], "A short page")
        self.assertEqual(meta["order"], 2)
        self.assertIs(meta["draft"], True)
        self.assertEqual(meta["tags"], ["docs", "python"])
        self.assertEqual(meta["authors"], ["Ada", "Grace"])
        self.assertIn("# Body", body)

    def test_document_without_front_matter(self) -> None:
        meta, body = parse_frontmatter("# Just a heading\n")
        self.assertEqual(meta, {})
        self.assertEqual(body, "# Just a heading\n")

    def test_front_matter_must_close(self) -> None:
        meta, body = parse_frontmatter("---\ntitle: broken\n")
        self.assertEqual(meta, {})
        self.assertIn("title: broken", body)


class HeadingAndTocTests(unittest.TestCase):
    def test_heading_ids_and_titles(self) -> None:
        document = render_markdown("# Title\n\n## First section\n\nText\n\n### Deep Dive\n")
        self.assertEqual(
            [heading.slug for heading in document.headings],
            ["title", "first-section", "deep-dive"],
        )
        self.assertEqual([heading.level for heading in document.headings], [1, 2, 3])
        self.assertIn('<h2 id="first-section">', document.html)
        self.assertIn('href="#deep-dive"', document.toc)
        self.assertEqual(document.title, "Title")

    def test_duplicate_headings_get_unique_ids(self) -> None:
        document = render_markdown("## Setup\n\n## Setup\n")
        self.assertEqual([heading.slug for heading in document.headings], ["setup", "setup-1"])

    def test_toc_is_nested(self) -> None:
        document = render_markdown("## A\n\n### B\n\n## C\n")
        toc = document.toc
        self.assertEqual(toc.count("<ul"), 2)
        self.assertLess(toc.index('href="#a"'), toc.index('href="#b"'))
        self.assertLess(toc.index('href="#b"'), toc.index('href="#c"'))

    def test_toc_skips_h1(self) -> None:
        document = render_markdown("# Title\n\n## Section\n")
        self.assertNotIn('href="#title"', document.toc)
        self.assertIn('href="#section"', document.toc)

    def test_build_toc_empty(self) -> None:
        self.assertEqual(build_toc([Heading(level=1, text="Only", slug="only")]), "")

    def test_slugify(self) -> None:
        self.assertEqual(slugify("Hello, World!"), "hello-world")
        self.assertEqual(slugify("  Multiple   spaces  "), "multiple-spaces")
        self.assertEqual(slugify("***"), "section")


class InlineRenderingTests(unittest.TestCase):
    def render(self, source: str) -> str:
        return render_markdown(source).html

    def test_emphasis_and_code(self) -> None:
        html = self.render("**bold** *italic* _also_ ~~gone~~ `x = 1`")
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<em>also</em>", html)
        self.assertIn("<del>gone</del>", html)
        self.assertIn("<code>x = 1</code>", html)

    def test_links_and_images(self) -> None:
        html = self.render("See [the guide](guide.md) and ![logo](logo.png)")
        self.assertIn('<a href="guide.md">the guide</a>', html)
        self.assertIn('<img src="logo.png" alt="logo" loading="lazy">', html)

    def test_external_links_open_safely(self) -> None:
        html = self.render("[Doca](https://example.com)")
        self.assertIn('target="_blank"', html)
        self.assertIn('rel="noopener noreferrer"', html)

    def test_link_resolver_rewrites_markdown_links(self) -> None:
        html = render_markdown(
            "Read [Setup](setup.md#install).",
            link_resolver=lambda href: href.replace(".md", ".html"),
        ).html
        self.assertIn('<a href="setup.html#install">Setup</a>', html)

    def test_html_is_escaped(self) -> None:
        html = self.render('<script>alert("x")</script>')
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)

    def test_backslash_escapes(self) -> None:
        html = self.render(r"Literal \*stars\* here")
        self.assertIn("*stars*", html)
        self.assertNotIn("<em>", html)

    def test_line_break(self) -> None:
        html = self.render("first line  \nsecond line")
        self.assertIn("<br>", html)


class BlockRenderingTests(unittest.TestCase):
    def render(self, source: str) -> str:
        return render_markdown(source).html

    def test_unordered_list(self) -> None:
        html = self.render("- one\n- two\n- three\n")
        self.assertIn("<ul>", html)
        self.assertEqual(html.count("<li>"), 3)
        self.assertIn("<li>one", html)

    def test_ordered_list(self) -> None:
        html = self.render("1. first\n2. second\n")
        self.assertIn("<ol>", html)
        self.assertIn("<li>first", html)

    def test_nested_list(self) -> None:
        html = self.render("- one\n- two\n  - child a\n  - child b\n- three\n")
        self.assertEqual(html.count("<ul>"), 2)
        self.assertIn("<li>child a", html)
        self.assertIn("</ul></li>", html)

    def test_task_list(self) -> None:
        html = self.render("- [x] done\n- [ ] todo\n")
        self.assertIn('type="checkbox"', html)
        self.assertIn("checked", html)
        self.assertEqual(html.count('class="task-item"'), 2)

    def test_fenced_code_block(self) -> None:
        html = self.render('```python\nprint("<hi>")\n```\n')
        self.assertIn('class="language-python"', html)
        self.assertIn('data-lang="python"', html)
        self.assertIn("&lt;hi&gt;", html)
        self.assertIn("<pre><code", html)

    def test_unlabelled_code_block(self) -> None:
        html = self.render("```\nplain text\n```\n")
        self.assertIn("<pre><code>plain text</code></pre>", html)

    def test_table_with_alignment(self) -> None:
        html = self.render(
            "| Name | Score | Notes |\n"
            "| :--- | ---: | :---: |\n"
            "| Ada | 36 | first |\n"
        )
        self.assertIn("<table>", html)
        self.assertIn('<th style="text-align:left">Name</th>', html)
        self.assertIn('<th style="text-align:right">Score</th>', html)
        self.assertIn('<th style="text-align:center">Notes</th>', html)
        self.assertIn('<td style="text-align:right">36</td>', html)

    def test_blockquote(self) -> None:
        html = self.render("> quoted **text**\n")
        self.assertIn("<blockquote><p>quoted <strong>text</strong></p></blockquote>", html)

    def test_horizontal_rule(self) -> None:
        html = self.render("above\n\n---\n\nbelow")
        self.assertIn("<hr>", html)

    def test_paragraphs(self) -> None:
        html = self.render("First paragraph.\n\nSecond paragraph.\n")
        self.assertEqual(html.count("<p>"), 2)


class PlainTextTests(unittest.TestCase):
    def test_strips_markdown(self) -> None:
        text = plain_text("# Title\n\nSome **bold** and [a link](x.md).\n\n```\ncode\n```\n")
        self.assertIn("Title", text)
        self.assertIn("bold", text)
        self.assertIn("a link", text)
        self.assertNotIn("**", text)
        self.assertNotIn("```", text)


class BuildSiteTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        (root / "docs").mkdir(parents=True)
        (root / "docs" / "index.md").write_text(
            "---\ntitle: Home\n---\n\n# Home\n\nSee [Setup](setup.md).\n", encoding="utf-8"
        )
        (root / "docs" / "setup.md").write_text(
            "# Setup\n\n## Install\n\nRun `pip install doca`.\n", encoding="utf-8"
        )
        config = {
            "title": "Test Docs",
            "description": "Testing Doca",
            "author": "Tester",
            "docs_dir": "docs",
            "out_dir": "site",
            "nav": [
                {"title": "Home", "path": "index.md"},
                {"title": "Guides", "items": [{"title": "Setup", "path": "setup.md"}]},
            ],
        }
        (root / "doca.json").write_text(json.dumps(config), encoding="utf-8")

    def test_builds_pages_navigation_and_search_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            result = build_site(root)

            self.assertEqual(result.pages, 2)
            self.assertTrue((root / "site" / "index.html").exists())
            self.assertTrue((root / "site" / "setup.html").exists())
            self.assertTrue((root / "site" / "search-index.json").exists())

            index_html = (root / "site" / "index.html").read_text(encoding="utf-8")
            self.assertIn("Test Docs", index_html)
            self.assertIn('href="setup.html"', index_html)
            self.assertIn("Search docs", index_html)
            self.assertIn("Guides", index_html)

            setup_html = (root / "site" / "setup.html").read_text(encoding="utf-8")
            self.assertIn('id="install"', setup_html)
            self.assertIn("On this page", setup_html)
            self.assertIn("pip install doca", setup_html)

            search = json.loads((root / "site" / "search-index.json").read_text())
            self.assertEqual({record["url"] for record in search}, {"index.html", "setup.html"})

    def test_rebuild_replaces_previous_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            build_site(root)
            (root / "docs" / "extra.md").write_text("# Extra\n", encoding="utf-8")
            result = build_site(root)
            self.assertEqual(result.pages, 3)
            self.assertTrue((root / "site" / "extra.html").exists())

    def test_missing_config_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(DocaError):
                build_site(Path(tmp))

    def test_invalid_config_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doca.json").write_text("{ not json", encoding="utf-8")
            with self.assertRaises(DocaError):
                load_config(root)

    def test_missing_docs_directory_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "doca.json").write_text('{"docs_dir": "docs"}', encoding="utf-8")
            with self.assertRaises(DocaError):
                build_site(root)

    def test_output_inside_docs_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.make_project(root)
            with self.assertRaises(DocaError):
                build_site(root, out_dir=root / "docs" / "site")

    def test_version_is_exposed(self) -> None:
        self.assertEqual(__version__, "0.1.0")


if __name__ == "__main__":
    unittest.main()

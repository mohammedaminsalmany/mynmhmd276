"""Markdown rendering and static site building for Doca.

Doca ships a small, dependency-free Markdown engine covering the subset of
CommonMark and GitHub Flavored Markdown that documentation sites need:
front matter, headings with anchor links, paragraphs, emphasis, inline code,
fenced code blocks, block quotes, nested ordered/unordered/task lists, tables,
images, links, horizontal rules and an automatically generated table of
contents.

The same module turns a folder of Markdown files plus a ``doca.json`` file
into a ready-to-publish static site (HTML pages, navigation, search index).
"""

from __future__ import annotations

import html
import json
import posixpath
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from . import __version__
from .templates import render_page

__all__ = [
    "BuildResult",
    "DocaError",
    "Heading",
    "RenderedDocument",
    "build_site",
    "build_toc",
    "load_config",
    "parse_frontmatter",
    "plain_text",
    "render_markdown",
    "slugify",
]

CONFIG_FILE = "doca.json"
MARKDOWN_SUFFIXES = (".md", ".markdown")
BUILD_MARKER = ".doca-build"

DEFAULT_CONFIG: dict[str, Any] = {
    "title": "Doca Docs",
    "description": "Documentation built with Doca.",
    "author": "",
    "docs_dir": "docs",
    "out_dir": "site",
    "theme": {"accent": "#6366f1", "default": "auto"},
    "footer": {"text": "", "links": []},
    "nav": [],
    "edit_url": "",
}


class DocaError(Exception):
    """Raised when a Doca project cannot be loaded or built."""


# ---------------------------------------------------------------------------
# Front matter
# ---------------------------------------------------------------------------

_FRONTMATTER_RE = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.DOTALL)


def _scalar(value: str) -> Any:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    lowered = value.lower()
    if lowered in ("true", "yes"):
        return True
    if lowered in ("false", "no"):
        return False
    if lowered in ("null", "~"):
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    return value


def parse_frontmatter(source: str) -> tuple[dict[str, Any], str]:
    """Split a Markdown document into its YAML-ish front matter and body.

    Only the flat subset Doca needs is supported: ``key: value`` pairs,
    inline lists (``[a, b]``) and indented ``- item`` lists. Values are
    converted to bool/int/float when they look like one.
    """

    source = source.replace("\r\n", "\n").replace("\r", "\n")
    match = _FRONTMATTER_RE.match(source)
    if not match:
        return {}, source

    meta: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in match.group(1).split("\n"):
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        stripped = raw_line.strip()
        if stripped.startswith("- ") and current_key:
            if not isinstance(meta.get(current_key), list):
                meta[current_key] = []
            meta[current_key].append(_scalar(stripped[2:]))
            continue
        if ":" in raw_line and not raw_line.startswith((" ", "\t")):
            key, _, value = raw_line.partition(":")
            current_key = key.strip()
            meta[current_key] = _scalar(value) if value.strip() else []
        elif current_key and isinstance(meta.get(current_key), str):
            meta[current_key] = f"{meta[current_key]} {stripped}"

    body = source[match.end():]
    return meta, body


# ---------------------------------------------------------------------------
# Inline rendering
# ---------------------------------------------------------------------------

_PLACEHOLDER = "\x00{}\x00"
_ESCAPE_RE = re.compile(r"\\([\\`*_{}\[\]()#+\-.!|>~&])")
_CODE_SPAN_RE = re.compile(r"(`+)(.+?)\1", re.DOTALL)
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(\s*([^)\s]+)(?:\s+[\"']([^\"']*)[\"'])?\s*\)")
_LINK_RE = re.compile(r"\[([^\]]+)\]\(\s*([^)\s]+)(?:\s+[\"']([^\"']*)[\"'])?\s*\)")
_AUTOLINK_RE = re.compile(r"<((?:https?://|mailto:)[^>\s]+)>")
_TASK_RE = re.compile(r"^\[([ xX])\]\s+")


def _emphasis(text: str) -> str:
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.DOTALL)
    text = re.sub(r"__(?=\S)(.+?)(?<=\S)__", r"<strong>\1</strong>", text, flags=re.DOTALL)
    text = re.sub(r"~~(?=\S)(.+?)(?<=\S)~~", r"<del>\1</del>", text, flags=re.DOTALL)
    text = re.sub(r"(?<![\w*])\*(?=\S)(.+?)(?<=\S)\*(?![\w*])", r"<em>\1</em>", text, flags=re.DOTALL)
    text = re.sub(r"(?<![\w_])_(?=\S)(.+?)(?<=\S)_(?![\w_])", r"<em>\1</em>", text, flags=re.DOTALL)
    return text


def render_inline(
    text: str,
    *,
    link_resolver: Callable[[str], str] | None = None,
    allow_links: bool = True,
) -> str:
    """Render inline Markdown (emphasis, code, links, images) to HTML."""

    stashed: list[str] = []

    def stash(fragment: str) -> str:
        stashed.append(fragment)
        return _PLACEHOLDER.format(len(stashed) - 1)

    def resolve(href: str) -> str:
        return link_resolver(href) if link_resolver else href

    text = _ESCAPE_RE.sub(lambda m: stash(html.escape(m.group(1), quote=False)), text)

    text = _CODE_SPAN_RE.sub(
        lambda m: stash(f"<code>{html.escape(m.group(2), quote=False)}</code>"), text
    )

    if allow_links:
        def image_repl(match: re.Match[str]) -> str:
            alt = html.escape(match.group(1), quote=True)
            src = html.escape(resolve(match.group(2)), quote=True)
            title = match.group(3)
            title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
            return stash(
                f'<img src="{src}" alt="{alt}"{title_attr} loading="lazy">'
            )

        def link_repl(match: re.Match[str]) -> str:
            label = render_inline(match.group(1), allow_links=False)
            href = resolve(match.group(2))
            title = match.group(3)
            title_attr = f' title="{html.escape(title, quote=True)}"' if title else ""
            external = ""
            if re.match(r"^(?:https?:)?//", href):
                external = ' target="_blank" rel="noopener noreferrer"'
            return stash(
                f'<a href="{html.escape(href, quote=True)}"{title_attr}{external}>{label}</a>'
            )

        text = _IMAGE_RE.sub(image_repl, text)
        text = _LINK_RE.sub(link_repl, text)
        text = _AUTOLINK_RE.sub(
            lambda m: stash(
                f'<a href="{html.escape(m.group(1), quote=True)}" '
                f'target="_blank" rel="noopener noreferrer">{html.escape(m.group(1))}</a>'
            ),
            text,
        )

    text = html.escape(text, quote=False)
    text = _emphasis(text)
    text = re.sub(r" {2,}\n", "<br>\n", text)

    for index, fragment in enumerate(stashed):
        text = text.replace(_PLACEHOLDER.format(index), fragment)
    return text


def plain_text(markdown_source: str) -> str:
    """Reduce Markdown to plain text (used for search indexing)."""

    _, body = parse_frontmatter(markdown_source)
    body = re.sub(r"```.*?```", " ", body, flags=re.DOTALL)
    body = re.sub(r"`[^`]+`", " ", body)
    body = re.sub(r"!\[[^\]]*\]\([^)]*\)", " ", body)
    body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", body)
    body = re.sub(r"<[^>]+>", " ", body)
    body = re.sub(r"^[ \t]{0,3}(?:#{1,6}|>|[-*+]|\d+[.)])[ \t]+", "", body, flags=re.MULTILINE)
    body = re.sub(r"[*_~]|`", "", body)
    body = re.sub(r"\s+", " ", body)
    return body.strip()


# ---------------------------------------------------------------------------
# Block rendering
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})[ \t]*([\w#+.\-]*)[^`]*$")
_HR_RE = re.compile(r"^ {0,3}(?:(?:\*[ \t]*){3,}|(?:-[ \t]*){3,}|(?:_[ \t]*){3,})$")
_QUOTE_RE = re.compile(r"^ {0,3}>[ \t]?(.*)$")
_LIST_RE = re.compile(r"^([ \t]*)([-*+]|\d{1,9}[.)])[ \t]+(.*)$")
_TABLE_DELIM_RE = re.compile(
    r"^[ \t]*\|?[ \t]*:?-{2,}:?[ \t]*(?:\|[ \t]*:?-{2,}:?[ \t]*)+\|?[ \t]*$"
)


def slugify(text: str) -> str:
    """Turn heading text into a URL-friendly anchor id."""

    slug = re.sub(r"[^\w\s-]", "", text.strip().lower(), flags=re.UNICODE)
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug or "section"


@dataclass
class Heading:
    level: int
    text: str
    slug: str


@dataclass
class RenderedDocument:
    html: str
    headings: list[Heading] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)
    title: str | None = None

    @property
    def toc(self) -> str:
        return build_toc(self.headings)


def build_toc(headings: Iterable[Heading], min_level: int = 2, max_level: int = 3) -> str:
    """Render headings as a nested table of contents."""

    items = [h for h in headings if min_level <= h.level <= max_level]
    if not items:
        return ""

    parts: list[str] = []
    levels: list[int] = []
    for heading in items:
        while levels and heading.level < levels[-1]:
            parts.append("</li></ul>")
            levels.pop()
        if not levels:
            parts.append('<ul class="toc-list">')
            levels.append(heading.level)
        elif heading.level > levels[-1]:
            parts.append('<ul class="toc-list">')
            levels.append(heading.level)
        else:
            parts.append("</li>")
        parts.append(
            f'<li><a href="#{heading.slug}">{html.escape(heading.text)}</a>'
        )
    while levels:
        parts.append("</li></ul>")
        levels.pop()
    return "".join(parts)


def _is_block_start(lines: list[str], index: int) -> bool:
    line = lines[index]
    if not line.strip():
        return True
    if _FENCE_RE.match(line) or _HEADING_RE.match(line) or _HR_RE.match(line):
        return True
    if _QUOTE_RE.match(line) or _LIST_RE.match(line):
        return True
    if "|" in line and index + 1 < len(lines) and _TABLE_DELIM_RE.match(lines[index + 1]):
        return True
    return False


def _split_table_row(line: str) -> list[str]:
    line = line.strip()
    if line.startswith("|"):
        line = line[1:]
    if line.endswith("|") and not line.endswith("\\|"):
        line = line[:-1]
    cells = re.split(r"(?<!\\)\|", line)
    return [cell.strip().replace("\\|", "|") for cell in cells]


def _render_table(header: list[str], aligns: list[str], rows: list[list[str]]) -> str:
    def cell(tag: str, content: str, index: int) -> str:
        align = aligns[index] if index < len(aligns) else ""
        style = f' style="text-align:{align}"' if align else ""
        return f"<{tag}{style}>{render_inline(content)}</{tag}>"

    head = "".join(cell("th", value, i) for i, value in enumerate(header))
    body_rows = []
    for row in rows:
        cells = "".join(
            cell("td", row[i] if i < len(row) else "", i) for i in range(len(header))
        )
        body_rows.append(f"<tr>{cells}</tr>")
    body = "".join(body_rows)
    return (
        '<div class="table-wrap"><table><thead><tr>'
        f"{head}</tr></thead><tbody>{body}</tbody></table></div>"
    )


def _render_list(items: list[dict[str, Any]]) -> str:
    """Render a flat list of parsed list items into nested ``ul``/``ol``."""

    parts: list[str] = []
    stack: list[dict[str, Any]] = []

    for item in items:
        indent = item["indent"]
        tag = "ol" if item["ordered"] else "ul"

        if not stack:
            parts.append(f"<{tag}>")
            stack.append({"indent": indent, "tag": tag, "open": False})
        else:
            while len(stack) > 1 and indent < stack[-1]["indent"]:
                if stack[-1]["open"]:
                    parts.append("</li>")
                parts.append(f"</{stack[-1]['tag']}>")
                stack.pop()
            top = stack[-1]
            if indent > top["indent"]:
                parts.append(f"<{tag}>")
                stack.append({"indent": indent, "tag": tag, "open": False})
            elif tag != top["tag"]:
                if top["open"]:
                    parts.append("</li>")
                parts.append(f"</{top['tag']}>")
                parts.append(f"<{tag}>")
                stack[-1] = {"indent": indent, "tag": tag, "open": False}
            elif top["open"]:
                parts.append("</li>")

        text = item["text"]
        classes = ""
        task = _TASK_RE.match(text)
        if task:
            checked = task.group(1).lower() == "x"
            box = (
                '<input type="checkbox" disabled'
                + (" checked" if checked else "")
                + "> "
            )
            text = box + text[task.end():]
            classes = ' class="task-item"'
        parts.append(f"<li{classes}>{render_inline(text)}")
        stack[-1]["open"] = True

    while stack:
        entry = stack.pop()
        if entry["open"]:
            parts.append("</li>")
        parts.append(f"</{entry['tag']}>")

    return "".join(parts)


def render_markdown(
    source: str,
    *,
    link_resolver: Callable[[str], str] | None = None,
    meta: dict[str, Any] | None = None,
) -> RenderedDocument:
    """Render a Markdown document, including front matter and heading ids."""

    front, body = parse_frontmatter(source)
    document_meta: dict[str, Any] = dict(front)
    if meta:
        document_meta.update(meta)

    lines = body.split("\n")
    blocks: list[str] = []
    headings: list[Heading] = []
    used_slugs: dict[str, int] = {}
    index = 0
    total = len(lines)

    while index < total:
        line = lines[index]

        if not line.strip():
            index += 1
            continue

        fence = _FENCE_RE.match(line)
        if fence:
            marker = fence.group(1)
            language = (fence.group(2) or "").strip()
            index += 1
            code_lines: list[str] = []
            closing = re.compile(r"^ {0,3}" + re.escape(marker[0]) + "{" + str(len(marker)) + r",}[ \t]*$")
            while index < total and not closing.match(lines[index]):
                code_lines.append(lines[index])
                index += 1
            index += 1  # skip closing fence (or run past the end)
            code = html.escape("\n".join(code_lines), quote=False)
            lang_class = f' class="language-{html.escape(language)}"' if language else ""
            label = f' data-lang="{html.escape(language)}"' if language else ""
            blocks.append(f'<div class="code-block"{label}><pre><code{lang_class}>{code}</code></pre></div>')
            continue

        heading = _HEADING_RE.match(line)
        if heading:
            level = len(heading.group(1))
            raw_text = heading.group(2).strip()
            text = re.sub(r"[*_`~]", "", raw_text)
            text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
            slug = slugify(text)
            if slug in used_slugs:
                used_slugs[slug] += 1
                slug = f"{slug}-{used_slugs[slug]}"
            else:
                used_slugs[slug] = 0
            headings.append(Heading(level=level, text=text, slug=slug))
            blocks.append(
                f'<h{level} id="{slug}">{render_inline(raw_text)}'
                f'<a class="header-anchor" href="#{slug}" aria-label="Link to this section">#</a>'
                f"</h{level}>"
            )
            index += 1
            continue

        if _HR_RE.match(line):
            blocks.append("<hr>")
            index += 1
            continue

        if _QUOTE_RE.match(line):
            quote_lines: list[str] = []
            while index < total and (_QUOTE_RE.match(lines[index]) or not lines[index].strip()):
                if not lines[index].strip():
                    if index + 1 < total and _QUOTE_RE.match(lines[index + 1]):
                        quote_lines.append("")
                        index += 1
                        continue
                    break
                match = _QUOTE_RE.match(lines[index])
                quote_lines.append(match.group(1) if match else "")
                index += 1
            inner = render_markdown("\n".join(quote_lines), link_resolver=link_resolver)
            blocks.append(f"<blockquote>{inner.html}</blockquote>")
            continue

        if "|" in line and index + 1 < total and _TABLE_DELIM_RE.match(lines[index + 1]):
            header = _split_table_row(line)
            delimiters = _split_table_row(lines[index + 1])
            aligns: list[str] = []
            for delimiter in delimiters:
                left = delimiter.startswith(":")
                right = delimiter.endswith(":")
                if left and right:
                    aligns.append("center")
                elif right:
                    aligns.append("right")
                elif left:
                    aligns.append("left")
                else:
                    aligns.append("")
            index += 2
            rows: list[list[str]] = []
            while index < total and lines[index].strip() and "|" in lines[index]:
                rows.append(_split_table_row(lines[index]))
                index += 1
            blocks.append(_render_table(header, aligns, rows))
            continue

        if _LIST_RE.match(line):
            block_lines: list[str] = []
            while index < total:
                current = lines[index]
                if _LIST_RE.match(current):
                    block_lines.append(current)
                    index += 1
                    continue
                if not current.strip():
                    look = index + 1
                    while look < total and not lines[look].strip():
                        look += 1
                    if look < total and (
                        _LIST_RE.match(lines[look]) or lines[look].startswith((" ", "\t"))
                    ):
                        block_lines.append("")
                        index += 1
                        continue
                    break
                if current.startswith((" ", "\t")):
                    block_lines.append(current)
                    index += 1
                    continue
                break

            items: list[dict[str, Any]] = []
            for raw in block_lines:
                if not raw.strip():
                    continue
                match = _LIST_RE.match(raw)
                if match:
                    items.append(
                        {
                            "indent": len(match.group(1).expandtabs(4)),
                            "ordered": match.group(2)[0].isdigit(),
                            "text": match.group(3).strip(),
                        }
                    )
                elif items:
                    items[-1]["text"] += " " + raw.strip()
            if items:
                blocks.append(_render_list(items))
            continue

        # Paragraph (leading indentation is dropped, trailing spaces are kept
        # because two of them mean a hard line break)
        paragraph: list[str] = []
        while index < total and lines[index].strip() and not _is_block_start(lines, index):
            paragraph.append(lines[index].lstrip())
            index += 1
        if paragraph:
            blocks.append(f"<p>{render_inline(chr(10).join(paragraph), link_resolver=link_resolver)}</p>")
        else:
            index += 1

    rendered_title = document_meta.get("title")
    if not rendered_title:
        first_h1 = next((h.text for h in headings if h.level == 1), None)
        rendered_title = first_h1

    return RenderedDocument(
        html="\n".join(blocks),
        headings=headings,
        meta=document_meta,
        title=str(rendered_title) if rendered_title else None,
    )


# ---------------------------------------------------------------------------
# Site building
# ---------------------------------------------------------------------------

@dataclass
class BuildResult:
    pages: int
    out_dir: Path
    urls: list[str] = field(default_factory=list)


def load_config(root: Path) -> dict[str, Any]:
    """Load and validate ``doca.json`` from a project root."""

    path = root / CONFIG_FILE
    if not path.exists():
        raise DocaError(
            f"No {CONFIG_FILE} found in {root}. Run 'doca init' first."
        )
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DocaError(f"{CONFIG_FILE} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise DocaError(f"{CONFIG_FILE} must contain a JSON object.")

    config = dict(DEFAULT_CONFIG)
    config.update(data)
    theme = dict(DEFAULT_CONFIG["theme"])
    theme.update(data.get("theme") or {})
    config["theme"] = theme
    footer = dict(DEFAULT_CONFIG["footer"])
    footer.update(data.get("footer") or {})
    config["footer"] = footer
    return config


def _humanize(stem: str) -> str:
    words = re.split(r"[-_]+", stem)
    return " ".join(word.capitalize() for word in words if word) or stem


def _collect_markdown(docs_dir: Path) -> list[Path]:
    files = [
        path
        for path in docs_dir.rglob("*")
        if path.is_file()
        and path.suffix.lower() in MARKDOWN_SUFFIXES
        and not any(part.startswith(("_", ".")) for part in path.relative_to(docs_dir).parts)
    ]
    return sorted(files, key=lambda p: p.relative_to(docs_dir).as_posix())


def _page_url(relative: Path) -> str:
    return relative.with_suffix(".html").as_posix()


def _relative_url(current: str, target: str) -> str:
    if not target:
        return target
    if re.match(r"^(?:[a-z]+:|//|#)", target):
        return target
    current_dir = posixpath.dirname(current)
    return posixpath.relpath(target, current_dir or ".")


def _resolve_nav(
    nav_config: Any, pages: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_path = {page["rel"].as_posix(): page for page in pages}

    def resolve_item(entry: Any) -> dict[str, Any] | None:
        if isinstance(entry, str):
            entry = {"path": entry}
        if not isinstance(entry, dict):
            return None
        path = str(entry.get("path", "")).strip().lstrip("./")
        page = by_path.get(path)
        if page is None:
            return None
        return {
            "title": str(entry.get("title") or page["title"]),
            "url": page["url"],
        }

    if not nav_config:
        return [
            {"title": page["title"], "url": page["url"], "items": []}
            for page in pages
        ]

    resolved: list[dict[str, Any]] = []
    for entry in nav_config:
        if isinstance(entry, dict) and entry.get("items"):
            children = [child for child in (resolve_item(item) for item in entry["items"]) if child]
            if children:
                resolved.append({"title": str(entry.get("title", "")), "items": children})
        else:
            item = resolve_item(entry)
            if item:
                resolved.append({**item, "items": []})
    return resolved or [
        {"title": page["title"], "url": page["url"], "items": []} for page in pages
    ]


def _nav_for_page(
    nav: list[dict[str, Any]], current_url: str, resolver: Callable[[str], str]
) -> list[dict[str, Any]]:
    def convert(item: dict[str, Any]) -> dict[str, Any]:
        converted: dict[str, Any] = {"title": item.get("title", ""), "items": []}
        url = item.get("url")
        if url:
            converted["url"] = resolver(url)
            converted["active"] = url == current_url
        converted["items"] = [convert(child) for child in item.get("items", [])]
        return converted

    return [convert(item) for item in nav]


def build_site(
    root: str | Path,
    *,
    out_dir: str | Path | None = None,
    config: dict[str, Any] | None = None,
) -> BuildResult:
    """Build the static site for the project at ``root``."""

    root = Path(root).resolve()
    if config is None:
        config = load_config(root)

    docs_dir = root / str(config.get("docs_dir") or "docs")
    if not docs_dir.is_dir():
        raise DocaError(f"Documentation directory not found: {docs_dir}")

    output = Path(out_dir).resolve() if out_dir else (root / str(config.get("out_dir") or "site"))
    if output == root or output == docs_dir or docs_dir in output.parents:
        raise DocaError("The output directory must be outside the documentation directory.")

    if output.exists():
        if (output / BUILD_MARKER).exists():
            shutil.rmtree(output)
        elif any(output.iterdir()):
            raise DocaError(
                f"Output directory {output} is not empty and was not created by Doca. "
                "Remove it or choose another one with --out."
            )
    output.mkdir(parents=True, exist_ok=True)
    (output / BUILD_MARKER).write_text(f"doca {__version__}\n", encoding="utf-8")

    sources = _collect_markdown(docs_dir)
    if not sources:
        raise DocaError(f"No Markdown files found in {docs_dir}.")

    # Render every Markdown file first so the navigation knows all titles.
    pages: list[dict[str, Any]] = []
    for source_path in sources:
        relative = source_path.relative_to(docs_dir)
        raw = source_path.read_text(encoding="utf-8")
        rendered = render_markdown(
            raw,
            link_resolver=lambda href: _relative_url(_page_url(relative), href)
            if href.split("#", 1)[0].endswith(MARKDOWN_SUFFIXES)
            else href,
        )
        title = rendered.title or str(rendered.meta.get("title") or "") or _humanize(relative.stem)
        pages.append(
            {
                "title": title,
                "description": str(rendered.meta.get("description") or ""),
                "order": rendered.meta.get("order", 0) or 0,
                "url": _page_url(relative),
                "rel": relative,
                "source": source_path,
                "html": rendered.html,
                "toc": rendered.toc,
                "headings": rendered.headings,
                "meta": rendered.meta,
            }
        )

    pages.sort(
        key=lambda page: (
            page["rel"].as_posix() != "index.md",
            page["order"] if isinstance(page["order"], (int, float)) else 0,
            page["rel"].as_posix(),
        )
    )

    nav = _resolve_nav(config.get("nav"), pages)
    search_records = []
    for page in pages:
        text = plain_text(page["source"].read_text(encoding="utf-8"))
        search_records.append(
            {
                "title": page["title"],
                "url": page["url"],
                "description": page["description"],
                "headings": [heading.text for heading in page["headings"]],
                "text": text[:1200],
            }
        )

    for position, page in enumerate(pages):
        current = page["url"]

        def resolver(href: str, _current: str = current) -> str:
            return _relative_url(_current, href)

        previous = pages[position - 1] if position > 0 else None
        following = pages[position + 1] if position + 1 < len(pages) else None

        page_html = render_page(
            config=config,
            page={
                "title": page["title"],
                "description": page["description"],
                "html": page["html"],
                "toc": page["toc"],
                "source": page["rel"].as_posix(),
            },
            nav=_nav_for_page(nav, current, resolver),
            search=[
                {
                    "title": record["title"],
                    "url": _relative_url(current, record["url"]),
                    "description": record["description"],
                    "headings": record["headings"],
                    "text": record["text"],
                }
                for record in search_records
            ],
            prev=(
                {"title": previous["title"], "url": _relative_url(current, previous["url"])}
                if previous
                else None
            ),
            next=(
                {"title": following["title"], "url": _relative_url(current, following["url"])}
                if following
                else None
            ),
            current_url=current,
            version=__version__,
        )

        target = output / current
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(page_html, encoding="utf-8")

    # Copy static assets (images, fonts, PDFs, ...) next to the pages.
    for asset in docs_dir.rglob("*"):
        if not asset.is_file() or asset.suffix.lower() in MARKDOWN_SUFFIXES:
            continue
        if any(part.startswith(("_", ".")) for part in asset.relative_to(docs_dir).parts):
            continue
        destination = output / asset.relative_to(docs_dir)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, destination)

    # Search index for external tools (e.g. a hosted search service).
    (output / "search-index.json").write_text(
        json.dumps(search_records, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # A friendly 404 page.
    if pages:
        home = _relative_url("404.html", pages[0]["url"])
        (output / "404.html").write_text(
            render_page(
                config={**config, "title": "Page not found"},
                page={
                    "title": "Page not found",
                    "description": "The page you are looking for does not exist.",
                    "html": f'<p>This page could not be found. <a href="{home}">Go to the documentation home</a>.</p>',
                    "toc": "",
                    "source": "",
                },
                nav=_nav_for_page(nav, "404.html", lambda href: _relative_url("404.html", href)),
                search=[
                    {
                        "title": record["title"],
                        "url": _relative_url("404.html", record["url"]),
                        "description": record["description"],
                        "headings": record["headings"],
                        "text": record["text"],
                    }
                    for record in search_records
                ],
                prev=None,
                next=None,
                current_url="404.html",
                version=__version__,
            ),
            encoding="utf-8",
        )

    return BuildResult(pages=len(pages), out_dir=output, urls=[page["url"] for page in pages])

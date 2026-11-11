---
title: Configuration
description: Customise your Doca site with doca.json and page front matter.
order: 3
---

# Configuration

Every project has a `doca.json` file at its root. All keys are optional; the
defaults in the table below apply when a key is missing.

## Full reference

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `title` | string | `"Doca Docs"` | Site title in the header and page titles. |
| `description` | string | `"Documentation built with Doca."` | Default meta description. |
| `author` | string | `""` | Used in the footer copyright line. |
| `docs_dir` | string | `"docs"` | Folder containing Markdown sources. |
| `out_dir` | string | `"site"` | Folder for generated HTML. |
| `lang` | string | `"en"` | Value of the HTML `lang` attribute. |
| `repo` | string | `""` | `owner/name` of the GitHub repository, linked in the sidebar. |
| `edit_url` | string | `""` | Prefix for the "Edit this page" link. |
| `theme.accent` | string | `"#6366f1"` | Accent colour for links and highlights. |
| `theme.default` | string | `"auto"` | `auto`, `light` or `dark`. |
| `nav` | array | `[]` | Sidebar navigation; generated from files when empty. |
| `footer.text` | string | `""` | Custom footer text. |
| `footer.links` | array | `[]` | Extra footer links (`label`, `url`). |

## Navigation

Navigation is generated from your files when `nav` is empty. To control the
order and grouping, list pages explicitly:

```json
{
  "nav": [
    { "title": "Introduction", "path": "index.md" },
    {
      "title": "Guides",
      "items": [
        { "title": "Getting started", "path": "getting-started.md" },
        { "title": "Configuration", "path": "configuration.md" }
      ]
    }
  ]
}
```

Paths are relative to `docs_dir`. Entries that point at a missing file are
skipped, so you can write navigation before the page exists.

## Front matter

Each page can override site-wide values with front matter:

```markdown
---
title: Deployment
description: Ship a Doca site to production.
order: 3
---

# Deployment
```

- `title` — used in the sidebar, the browser tab and search results.
- `description` — becomes the page's meta description and search snippet.
- `order` — sorts pages when navigation is auto-generated.

## Theme

Set `theme.accent` to any CSS colour to re-brand the site:

```json
{ "theme": { "accent": "#10b981", "default": "dark" } }
```

`theme.default` accepts:

- `auto` — follow the reader's system preference (default).
- `light` — always start in light mode.
- `dark` — always start in dark mode.

Readers can always switch with the toggle in the header; the choice is stored
in their browser and wins over the default.

## Hiding files

Files and folders whose names start with `_` or `.` are ignored by the build,
which is handy for drafts:

```text
docs/
├── index.md
└── _drafts/
    └── unfinished.md   # never rendered
```

## Custom output directory

```bash
doca build --out public
```

The directory must sit outside `docs_dir`. Doca marks its own output with a
`.doca-build` file and will only delete folders it created.

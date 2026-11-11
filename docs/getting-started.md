---
title: Getting started
description: Install Doca and build your first documentation site.
order: 2
---

# Getting started

This guide takes you from an empty folder to a published documentation site in
about two minutes.

## Requirements

Doca needs **Python 3.10 or newer**. There are no third-party packages to
install for base usage, and nothing to compile.

```bash
python3 --version
```

## Install

Install Doca from source with pip:

```bash
git clone https://github.com/mohammedaminsalmany/mynmhmd276.git
cd doca
pip install -e .
```

Verify the installation:

```bash
doca --version
# doca 0.1.0
```

You can also run Doca without installing it, straight from the repository:

```bash
python3 -m doca --version
```

## Create a workspace

Scaffold a new project with sample pages and a configuration file:

```bash
doca init my-docs
cd my-docs
```

The generated structure looks like this:

```text
my-docs/
├── doca.json
├── .gitignore
├── docs/
│   ├── index.md
│   ├── getting-started.md
│   └── configuration.md
└── site/            # created by `doca build`
```

## Build the site

```bash
doca build
```

The rendered site is written to `site/`. Open `site/index.html` in a browser,
or start the development server:

```bash
doca serve --port 8000
```

`doca serve` watches `docs/` and `doca.json` and rebuilds automatically
whenever a file changes. Pass `--no-watch` to disable that, or `--open` to
launch your browser.

## Add a page

```bash
doca new guides/deployment --title "Deployment"
```

This creates `docs/guides/deployment.md` with front matter and a starter
heading. If `doca.json` defines an explicit `nav` array, add the new page
there so it appears in the sidebar.

## Write a page

A page is a Markdown file with optional front matter:

```markdown
---
title: Deployment
description: Ship a Doca site to production.
order: 3
---

# Deployment

Doca output is static, so any host will do.
```

### Code blocks

Fenced code blocks are labelled with their language:

````markdown
```python
from doca import render_markdown

document = render_markdown("# Hello")
print(document.html)
```
````

### Tables

| Shell | Command |
| --- | --- |
| bash | `doca build` |
| PowerShell | `doca build` |

## Deploy

Because the output is static, any static host works:

- **GitHub Pages** — publish the `site/` folder from a workflow.
- **Netlify or Cloudflare Pages** — build command `doca build`, publish directory `site`.
- **S3 or a plain server** — upload the contents of `site/` and you are done.

Remember to add `site/` to `.gitignore` if you commit the sources only.

## Troubleshooting

- `doca: error: No doca.json found` — run the command from the project root, or pass `-C path/to/project`.
- Nothing changes in the browser — hard-refresh the page; the preview server does not inject a reload script.
- Broken links — link to Markdown files (`guide.md`); Doca rewrites them to `.html` automatically.

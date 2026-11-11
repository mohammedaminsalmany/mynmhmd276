"""Embedded HTML, CSS and JavaScript templates for Doca pages.

Deliberately dependency free: every page ships with its own styles and a tiny
amount of vanilla JavaScript, so the built site works from a local folder, a
static host or a CDN without a build step of its own.
"""

from __future__ import annotations

import html
import json
import posixpath
from datetime import date
from string import Template
from typing import Any, Iterable

__all__ = ["render_page", "escape"]

escape = html.escape


def _nav_link(item: dict[str, Any]) -> str:
    classes = "nav-link" + (" active" if item.get("active") else "")
    current = ' aria-current="page"' if item.get("active") else ""
    return (
        f'<li><a class="{classes}" href="{escape(item.get("url", "#"), quote=True)}"{current}>'
        f'{escape(item.get("title", ""))}</a></li>'
    )


def _nav_html(nav: Iterable[dict[str, Any]]) -> str:
    parts: list[str] = []
    in_list = False
    for item in nav:
        children = item.get("items") or []
        if children:
            if in_list:
                parts.append("</ul>")
                in_list = False
            parts.append(
                '<div class="nav-group">'
                f'<div class="nav-group-title">{escape(item.get("title", ""))}</div>'
                '<ul class="nav-links">'
            )
            parts.extend(_nav_link(child) for child in children)
            parts.append("</ul></div>")
        else:
            if not in_list:
                parts.append('<ul class="nav-links">')
                in_list = True
            parts.append(_nav_link(item))
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


def _pager_html(prev: dict[str, Any] | None, next_page: dict[str, Any] | None) -> str:
    if not prev and not next_page:
        return ""
    parts = ['<nav class="pager" aria-label="Page navigation">']
    if prev:
        parts.append(
            f'<a class="pager-link pager-prev" href="{escape(prev["url"], quote=True)}">'
            '<span class="pager-label">Previous</span>'
            f'<span class="pager-title">{escape(prev["title"])}</span></a>'
        )
    else:
        parts.append('<span class="pager-spacer"></span>')
    if next_page:
        parts.append(
            f'<a class="pager-link pager-next" href="{escape(next_page["url"], quote=True)}">'
            '<span class="pager-label">Next</span>'
            f'<span class="pager-title">{escape(next_page["title"])}</span></a>'
        )
    parts.append("</nav>")
    return "".join(parts)


def _footer_html(config: dict[str, Any]) -> str:
    footer = config.get("footer") or {}
    text = str(footer.get("text") or "").strip()
    if not text:
        author = str(config.get("author") or "").strip()
        year = date.today().year
        text = f"© {year} {author}" if author else f"© {year} {config.get('title', 'Doca')}"
    links = []
    for link in footer.get("links") or []:
        if isinstance(link, dict) and link.get("url"):
            links.append(
                f'<a href="{escape(str(link["url"]), quote=True)}">{escape(str(link.get("label") or link["url"]))}</a>'
            )
    built = '<span class="footer-built">Built with <a href="https://github.com/mohammedaminsalmany/doca">Doca</a></span>'
    return f"<span>{escape(text)}</span><span class=\"footer-links\">{' '.join(links)}{built}</span>"


_CSS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;scroll-behavior:smooth;scroll-padding-top:calc(var(--header-h) + 16px)}
:root{
  --bg:#ffffff;--bg-soft:#f7f7f9;--bg-elev:#ffffff;--bg-inline:rgba(15,15,20,.05);
  --text:#16161a;--text-soft:#4b4b55;--muted:#77777f;
  --border:#e7e7ec;--border-soft:#f0f0f4;
  --accent:#6366f1;--accent-hover:#4f46e5;--accent-soft:rgba(99,102,241,.09);
  --code-bg:#0f1117;--code-text:#e7e7ef;
  --radius:10px;--radius-lg:16px;
  --shadow-sm:0 1px 2px rgba(16,16,24,.05);--shadow:0 12px 32px rgba(16,16,24,.10);
  --sidebar-w:264px;--toc-w:216px;--header-h:60px;
  --sans:-apple-system,BlinkMacSystemFont,"Segoe UI","Inter",Roboto,"Helvetica Neue",Arial,"Noto Sans",sans-serif;
  --mono:ui-monospace,SFMono-Regular,"SF Mono",Menlo,Consolas,"Liberation Mono",monospace;
  color-scheme:light;
}
html[data-theme="dark"]{
  --bg:#0b0b0f;--bg-soft:#111118;--bg-elev:#14141b;--bg-inline:rgba(255,255,255,.08);
  --text:#e8e8ee;--text-soft:#b3b3bd;--muted:#8a8a95;
  --border:#25252f;--border-soft:#1b1b23;
  --accent:#8b93ff;--accent-hover:#a5abff;--accent-soft:rgba(139,147,255,.14);
  --code-bg:#08080c;--code-text:#e7e7ef;
  --shadow-sm:0 1px 2px rgba(0,0,0,.6);--shadow:0 16px 40px rgba(0,0,0,.55);
  color-scheme:dark;
}
@media (prefers-color-scheme:dark){
  html[data-theme="auto"]{
    --bg:#0b0b0f;--bg-soft:#111118;--bg-elev:#14141b;--bg-inline:rgba(255,255,255,.08);
    --text:#e8e8ee;--text-soft:#b3b3bd;--muted:#8a8a95;
    --border:#25252f;--border-soft:#1b1b23;
    --accent:#8b93ff;--accent-hover:#a5abff;--accent-soft:rgba(139,147,255,.14);
    --code-bg:#08080c;--code-text:#e7e7ef;
    --shadow-sm:0 1px 2px rgba(0,0,0,.6);--shadow:0 16px 40px rgba(0,0,0,.55);
    color-scheme:dark;
  }
}
body{margin:0;font-family:var(--sans);font-size:16px;line-height:1.7;color:var(--text);background:var(--bg);-webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
a{color:var(--accent);text-decoration:none}
a:hover{color:var(--accent-hover)}
.skip-link{position:absolute;left:-999px;top:8px;z-index:100;background:var(--bg-elev);padding:8px 14px;border-radius:8px;border:1px solid var(--border)}
.skip-link:focus{left:8px}
.topbar{position:sticky;top:0;z-index:50;height:var(--header-h);display:flex;align-items:center;gap:12px;padding:0 20px;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:saturate(180%) blur(12px);border-bottom:1px solid var(--border)}
@supports not (background:color-mix(in srgb,red 50%,blue)){.topbar{background:var(--bg)}}
.brand{display:inline-flex;align-items:center;gap:9px;color:var(--text);font-weight:650;letter-spacing:-.01em;font-size:15px;white-space:nowrap}
.brand:hover{color:var(--text)}
.brand-mark{display:grid;place-items:center;width:27px;height:27px;border-radius:8px;background:linear-gradient(135deg,var(--accent),#a855f7);color:#fff;font-size:14px;font-weight:800;font-family:var(--mono)}
.topbar-spacer{flex:1}
.icon-btn{display:inline-grid;place-items:center;width:36px;height:36px;padding:0;border:1px solid transparent;border-radius:9px;background:transparent;color:var(--text-soft);cursor:pointer;transition:background .15s,color .15s,border-color .15s}
.icon-btn:hover{background:var(--bg-soft);color:var(--text);border-color:var(--border)}
.icon-btn svg{width:18px;height:18px}
.menu-toggle{display:none}
.search-trigger{display:inline-flex;align-items:center;gap:9px;height:36px;padding:0 10px 0 11px;min-width:230px;border:1px solid var(--border);border-radius:9px;background:var(--bg-soft);color:var(--muted);font-family:inherit;font-size:13.5px;cursor:pointer;transition:border-color .15s,color .15s}
.search-trigger:hover{border-color:var(--accent);color:var(--text-soft)}
.search-trigger svg{width:15px;height:15px;flex:none}
.search-trigger span{flex:1;text-align:left}
kbd{font-family:var(--mono);font-size:10.5px;line-height:1;padding:4px 5px;border:1px solid var(--border);border-bottom-width:2px;border-radius:5px;color:var(--muted);background:var(--bg)}
.shell{display:flex;min-height:calc(100vh - var(--header-h))}
.sidebar{position:fixed;top:var(--header-h);bottom:0;left:0;width:var(--sidebar-w);padding:22px 14px 26px;overflow-y:auto;border-right:1px solid var(--border);background:var(--bg);z-index:45;scrollbar-width:thin}
.sidebar-nav{display:flex;flex-direction:column;gap:18px}
.nav-group-title{font-size:11px;font-weight:700;letter-spacing:.075em;text-transform:uppercase;color:var(--muted);padding:0 10px;margin-bottom:6px}
.nav-links{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:1px}
.nav-link{display:block;padding:6.5px 10px;border-radius:7px;color:var(--text-soft);font-size:14px;line-height:1.45;transition:background .12s,color .12s}
.nav-link:hover{background:var(--bg-soft);color:var(--text)}
.nav-link.active{background:var(--accent-soft);color:var(--accent);font-weight:600}
.sidebar-footer{margin-top:auto;padding:18px 10px 0;font-size:12px;color:var(--muted);display:flex;flex-direction:column;gap:6px}
.sidebar-footer a{color:var(--muted)}
.sidebar-footer a:hover{color:var(--accent)}
.sidebar-backdrop{display:none}
.main{flex:1;min-width:0;margin-left:var(--sidebar-w);display:flex;flex-direction:column}
.content-grid{display:grid;grid-template-columns:minmax(0,1fr) var(--toc-w);gap:48px;width:100%;max-width:1180px;margin:0 auto;padding:40px 48px 64px}
.prose{max-width:780px;min-width:0;font-size:15.5px;line-height:1.75;color:var(--text-soft)}
.prose>*:first-child{margin-top:0}
.prose h1,.prose h2,.prose h3,.prose h4,.prose h5,.prose h6{color:var(--text);font-weight:680;letter-spacing:-.018em;line-height:1.25;scroll-margin-top:calc(var(--header-h) + 20px);position:relative}
.prose h1{font-size:2.05rem;margin:0 0 .5em}
.prose h2{font-size:1.42rem;margin:2.3em 0 .7em;padding-top:.9em;border-top:1px solid var(--border-soft)}
.prose h3{font-size:1.14rem;margin:1.9em 0 .55em}
.prose h4{font-size:1rem;margin:1.6em 0 .45em}
.prose h5,.prose h6{font-size:.94rem;margin:1.4em 0 .4em;color:var(--text-soft)}
.header-anchor{opacity:0;margin-left:8px;color:var(--muted);font-weight:500;text-decoration:none;transition:opacity .15s}
.prose h1:hover .header-anchor,.prose h2:hover .header-anchor,.prose h3:hover .header-anchor,.prose h4:hover .header-anchor{opacity:1}
.prose p{margin:0 0 1.15em}
.prose a{font-weight:500;text-decoration:underline;text-decoration-color:color-mix(in srgb,var(--accent) 35%,transparent);text-underline-offset:2.5px}
.prose a:hover{text-decoration-color:var(--accent)}
.prose strong{color:var(--text);font-weight:650}
.prose ul,.prose ol{margin:0 0 1.15em;padding-left:1.5em}
.prose li{margin:.28em 0}
.prose li>ul,.prose li>ol{margin:.28em 0}
.prose li::marker{color:var(--muted)}
.prose .task-item{list-style:none;margin-left:-1.4em}
.prose .task-item input{margin-right:7px;accent-color:var(--accent);transform:translateY(1px)}
.prose blockquote{margin:1.4em 0;padding:.5em 1.2em;border-left:3px solid var(--accent);background:var(--bg-soft);border-radius:0 8px 8px 0;color:var(--text-soft)}
.prose blockquote p:last-child{margin-bottom:0}
.prose hr{border:0;border-top:1px solid var(--border);margin:2.2em 0}
.prose img{max-width:100%;height:auto;border-radius:var(--radius);border:1px solid var(--border)}
code{font-family:var(--mono);font-size:.875em}
:not(pre)>code{padding:2px 5px;border-radius:5px;background:var(--bg-inline);color:var(--text);border:1px solid var(--border-soft);white-space:nowrap}
.code-block{position:relative;margin:1.4em 0;background:var(--code-bg);border:1px solid rgba(255,255,255,.07);border-radius:var(--radius);box-shadow:var(--shadow-sm)}
.code-block pre{margin:0;padding:18px 20px;overflow-x:auto;font-size:13.5px;line-height:1.65;color:var(--code-text);tab-size:4}
.code-block code{font-family:var(--mono);font-size:inherit;color:inherit;background:none;border:0;padding:0;white-space:pre}
.code-block::after{content:attr(data-lang);position:absolute;top:9px;right:78px;font-family:var(--mono);font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:rgba(255,255,255,.32);pointer-events:none}
.copy-btn{position:absolute;top:7px;right:8px;height:26px;padding:0 8px;font-family:inherit;font-size:11px;color:rgba(255,255,255,.62);background:rgba(255,255,255,.07);border:1px solid rgba(255,255,255,.1);border-radius:6px;cursor:pointer;opacity:0;transition:opacity .15s,color .15s}
.code-block:hover .copy-btn,.copy-btn:focus{opacity:1}
.copy-btn:hover{color:#fff;background:rgba(255,255,255,.13)}
.table-wrap{margin:1.5em 0;overflow-x:auto;border:1px solid var(--border);border-radius:var(--radius)}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{padding:10px 14px;border-bottom:1px solid var(--border-soft);text-align:left;vertical-align:top}
thead th{background:var(--bg-soft);color:var(--text);font-weight:650;font-size:12.5px;letter-spacing:.03em;text-transform:uppercase;border-bottom:1px solid var(--border)}
tbody tr:last-child td{border-bottom:0}
tbody tr:hover{background:var(--bg-soft)}
.page-toc{position:sticky;top:calc(var(--header-h) + 40px);align-self:start;max-height:calc(100vh - var(--header-h) - 80px);overflow-y:auto;font-size:13px;border-left:1px solid var(--border-soft);padding-left:18px}
.toc-title{font-size:11px;font-weight:700;letter-spacing:.075em;text-transform:uppercase;color:var(--muted);margin-bottom:9px;padding-left:8px}
.toc-list{list-style:none;margin:0;padding:0}
.toc-list .toc-list{padding-left:12px}
.toc-list a{display:block;padding:3.5px 8px;color:var(--muted);border-radius:6px;line-height:1.45;border-left:2px solid transparent;margin-left:-2px;font-size:13px}
.toc-list a:hover{color:var(--text)}
.toc-list a.active{color:var(--accent);border-left-color:var(--accent);background:var(--accent-soft)}
.pager{display:flex;gap:14px;margin-top:64px;padding-top:28px;border-top:1px solid var(--border)}
.pager-spacer{flex:1}
.pager-link{flex:1;display:flex;flex-direction:column;gap:3px;padding:13px 17px;border:1px solid var(--border);border-radius:var(--radius);color:var(--text);transition:border-color .15s,background .15s;min-width:0}
.pager-link:hover{border-color:var(--accent);background:var(--bg-soft);color:var(--text)}
.pager-next{text-align:right}
.pager-label{font-size:11.5px;letter-spacing:.05em;text-transform:uppercase;color:var(--muted)}
.pager-title{font-weight:600;font-size:14.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.footer{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;padding:22px 48px;border-top:1px solid var(--border);font-size:12.5px;color:var(--muted);max-width:1180px;width:100%;margin:0 auto}
.footer a{color:var(--muted);text-decoration:underline;text-underline-offset:2px}
.footer a:hover{color:var(--accent)}
.footer-links{display:inline-flex;gap:14px;flex-wrap:wrap}
.footer-built a{font-weight:600}
.edit-link{display:inline-block;margin-top:26px;font-size:13px;color:var(--muted)}
.edit-link:hover{color:var(--accent)}
/* Search */
.search-overlay{position:fixed;inset:0;z-index:100;display:flex;justify-content:center;padding:11vh 18px 18px;background:rgba(12,12,18,.5);backdrop-filter:blur(3px)}
.search-overlay[hidden]{display:none}
.search-panel{width:100%;max-width:600px;max-height:72vh;display:flex;flex-direction:column;background:var(--bg-elev);border:1px solid var(--border);border-radius:var(--radius-lg);box-shadow:var(--shadow);overflow:hidden;animation:pop .14s ease-out}
@keyframes pop{from{opacity:0;transform:translateY(-6px) scale(.99)}}
.search-box{display:flex;align-items:center;gap:10px;padding:14px 16px;border-bottom:1px solid var(--border)}
.search-box svg{width:17px;height:17px;color:var(--muted);flex:none}
.search-box input{flex:1;border:0;outline:0;background:transparent;color:var(--text);font-family:inherit;font-size:15.5px}
.search-box input::placeholder{color:var(--muted)}
.search-close{font-family:var(--mono);font-size:10.5px}
.search-results{overflow-y:auto;padding:8px}
.search-item{display:block;padding:10px 12px;border-radius:9px;color:var(--text)}
.search-item:hover,.search-item.selected{background:var(--accent-soft);color:var(--text)}
.search-item-title{font-weight:600;font-size:14px;display:flex;gap:8px;align-items:baseline}
.search-item-title mark{background:transparent;color:var(--accent);font-weight:700}
.search-item-desc{font-size:12.5px;color:var(--muted);margin-top:2px;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
.search-empty{padding:26px 16px;text-align:center;color:var(--muted);font-size:13.5px}
.search-hint{padding:9px 14px;border-top:1px solid var(--border);font-size:11.5px;color:var(--muted);display:flex;gap:14px}
@media (max-width:1100px){.content-grid{grid-template-columns:minmax(0,1fr);gap:0}.page-toc{display:none}}
@media (max-width:900px){
  .menu-toggle{display:inline-grid}
  .sidebar{transform:translateX(-100%);transition:transform .2s ease;width:290px;box-shadow:var(--shadow)}
  .nav-open .sidebar{transform:translateX(0)}
  .nav-open .sidebar-backdrop{display:block;position:fixed;inset:var(--header-h) 0 0;background:rgba(10,10,16,.42);z-index:44}
  .main{margin-left:0}
  .content-grid{padding:28px 22px 48px}
  .footer{padding:20px 22px}
  .search-trigger{min-width:0;padding:0 9px}
  .search-trigger span{display:none}
  .search-trigger kbd{display:none}
  .brand-name{max-width:150px;overflow:hidden;text-overflow:ellipsis}
}
@media (max-width:520px){
  body{font-size:15px}
  .prose h1{font-size:1.7rem}
  .prose h2{font-size:1.28rem}
  .topbar{padding:0 12px;gap:6px}
  .pager{flex-direction:column}
  .search-overlay{padding:0}
  .search-panel{max-width:none;max-height:100vh;height:100vh;border-radius:0;border:0}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important;scroll-behavior:auto!important}}
"""

_JS = """
(function () {
  var root = document.documentElement;
  var KEY = 'doca-theme';
  var fallback = '$theme_default';

  function current() {
    var stored = null;
    try { stored = localStorage.getItem(KEY); } catch (e) {}
    return stored || fallback || 'auto';
  }
  function effective() {
    var mode = current();
    if (mode === 'auto') {
      return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
    }
    return mode;
  }
  function apply(mode) {
    root.setAttribute('data-theme', mode);
    var btn = document.getElementById('theme-toggle');
    if (btn) {
      btn.setAttribute('aria-label', mode === 'dark' ? 'Switch to light theme' : 'Switch to dark theme');
    }
  }
  apply(current());

  var toggle = document.getElementById('theme-toggle');
  if (toggle) {
    toggle.addEventListener('click', function () {
      var next = effective() === 'dark' ? 'light' : 'dark';
      try { localStorage.setItem(KEY, next); } catch (e) {}
      apply(next);
    });
  }

  // Mobile navigation
  var menuBtn = document.getElementById('menu-toggle');
  var backdrop = document.getElementById('sidebar-backdrop');
  function closeNav() {
    document.body.classList.remove('nav-open');
    if (menuBtn) { menuBtn.setAttribute('aria-expanded', 'false'); }
  }
  if (menuBtn) {
    menuBtn.addEventListener('click', function () {
      var open = document.body.classList.toggle('nav-open');
      menuBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
    });
  }
  if (backdrop) { backdrop.addEventListener('click', closeNav); }

  // Copy buttons on code blocks
  document.querySelectorAll('.code-block').forEach(function (block) {
    var pre = block.querySelector('pre');
    if (!pre) { return; }
    var btn = document.createElement('button');
    btn.className = 'copy-btn';
    btn.type = 'button';
    btn.textContent = 'Copy';
    btn.addEventListener('click', function () {
      var text = pre.innerText;
      var done = function () {
        btn.textContent = 'Copied';
        setTimeout(function () { btn.textContent = 'Copy'; }, 1400);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () {});
      } else {
        var area = document.createElement('textarea');
        area.value = text;
        document.body.appendChild(area);
        area.select();
        try { document.execCommand('copy'); done(); } catch (e) {}
        document.body.removeChild(area);
      }
    });
    block.appendChild(btn);
  });

  // Table of contents scroll spy
  var tocLinks = Array.prototype.slice.call(document.querySelectorAll('.toc-list a'));
  if (tocLinks.length && 'IntersectionObserver' in window) {
    var map = {};
    tocLinks.forEach(function (link) {
      map[decodeURIComponent(link.getAttribute('href').slice(1))] = link;
    });
    var visible = {};
    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        visible[entry.target.id] = entry.isIntersecting;
        var link = map[entry.target.id];
        if (!link) { return; }
        if (entry.isIntersecting) {
          tocLinks.forEach(function (item) { item.classList.remove('active'); });
          link.classList.add('active');
        }
      });
    }, { rootMargin: '-72px 0px -70% 0px', threshold: 0 });
    document.querySelectorAll('.prose h2[id], .prose h3[id]').forEach(function (heading) {
      observer.observe(heading);
    });
  }

  // Search
  var overlay = document.getElementById('search-overlay');
  var input = document.getElementById('search-input');
  var results = document.getElementById('search-results');
  var trigger = document.getElementById('search-trigger');
  var closeBtn = document.getElementById('search-close');
  var index = window.__DOCA_SEARCH__ || [];
  var selected = 0;
  var matches = [];

  function esc(text) {
    return String(text).replace(/[&<>"']/g, function (ch) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[ch];
    });
  }
  function highlight(text, query) {
    var safe = esc(text);
    if (!query) { return safe; }
    var escapedQuery = query.replace(/[.*+?^${}()|[\\]\\\\]/g, '\\\\$&');
    try {
      return safe.replace(new RegExp('(' + escapedQuery + ')', 'ig'), '<mark>$1</mark>');
    } catch (e) { return safe; }
  }
  function score(record, query) {
    var title = record.title.toLowerCase();
    var haystack = (record.description + ' ' + (record.headings || []).join(' ') + ' ' + record.text).toLowerCase();
    var value = 0;
    if (title.indexOf(query) === 0) { value += 120; }
    else if (title.indexOf(query) > -1) { value += 70; }
    if ((record.headings || []).join(' ').toLowerCase().indexOf(query) > -1) { value += 25; }
    if (haystack.indexOf(query) > -1) { value += 12; }
    return value;
  }
  function snippet(record, query) {
    var text = record.description || record.text || '';
    var position = text.toLowerCase().indexOf(query);
    if (position > 60) {
      text = '…' + text.slice(position - 40);
    }
    return text.length > 150 ? text.slice(0, 150) + '…' : text;
  }
  function search(query) {
    query = query.trim().toLowerCase();
    if (!query) {
      matches = index.slice(0, 6);
    } else {
      matches = index
        .map(function (record) { return { record: record, score: score(record, query) }; })
        .filter(function (entry) { return entry.score > 0; })
        .sort(function (a, b) { return b.score - a.score; })
        .slice(0, 10)
        .map(function (entry) { return entry.record; });
    }
    selected = 0;
    render(query);
  }
  function render(query) {
    if (!matches.length) {
      results.innerHTML = '<div class="search-empty">No results for “' + esc(query) + '”.</div>';
      return;
    }
    var html = '';
    matches.forEach(function (record, position) {
      html += '<a class="search-item' + (position === selected ? ' selected' : '') + '" href="' + esc(record.url) + '">'
        + '<div class="search-item-title">' + highlight(record.title, query) + '</div>'
        + '<div class="search-item-desc">' + highlight(snippet(record, query), query) + '</div></a>';
    });
    results.innerHTML = html;
  }
  function openSearch() {
    if (!overlay) { return; }
    overlay.hidden = false;
    document.body.style.overflow = 'hidden';
    if (input) { input.value = ''; input.focus(); }
    search('');
  }
  function closeSearch() {
    if (!overlay) { return; }
    overlay.hidden = true;
    document.body.style.overflow = '';
    if (trigger) { trigger.focus(); }
  }
  if (trigger) { trigger.addEventListener('click', openSearch); }
  if (closeBtn) { closeBtn.addEventListener('click', closeSearch); }
  if (overlay) {
    overlay.addEventListener('click', function (event) {
      if (event.target === overlay) { closeSearch(); }
    });
  }
  if (input) {
    input.addEventListener('input', function () { search(input.value); });
    input.addEventListener('keydown', function (event) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault();
        if (!matches.length) { return; }
        selected = (selected + (event.key === 'ArrowDown' ? 1 : matches.length - 1)) % matches.length;
        render(input.value.trim().toLowerCase());
        var current = results.querySelector('.search-item.selected');
        if (current) { current.scrollIntoView({ block: 'nearest' }); }
      } else if (event.key === 'Enter') {
        var target = matches[selected];
        if (target) { window.location.href = target.url; }
      }
    });
  }
  document.addEventListener('keydown', function (event) {
    var typing = /^(INPUT|TEXTAREA|SELECT)$/.test(document.activeElement.tagName) || document.activeElement.isContentEditable;
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'k') {
      event.preventDefault();
      openSearch();
    } else if (event.key === '/' && !typing) {
      event.preventDefault();
      openSearch();
    } else if (event.key === 'Escape') {
      closeSearch();
      closeNav();
    }
  });
})();
"""

_PAGE = Template(
    """<!DOCTYPE html>
<html lang="$lang" data-theme="$theme_default">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>$title</title>
<meta name="description" content="$description">
<meta name="generator" content="Doca $version">
<meta property="og:type" content="website">
<meta property="og:title" content="$title">
<meta property="og:description" content="$description">
<meta name="twitter:card" content="summary">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%236366f1'/%3E%3Cpath d='M10 9h6a7 7 0 0 1 0 14h-6z' fill='white'/%3E%3C/svg%3E">
<style>$css</style>
</head>
<body>
<a class="skip-link" href="#main">Skip to content</a>
<header class="topbar">
  <button class="icon-btn menu-toggle" id="menu-toggle" type="button" aria-label="Toggle navigation" aria-expanded="false" aria-controls="sidebar">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M4 6h16M4 12h16M4 18h16"/></svg>
  </button>
  <a class="brand" href="$home_url"><span class="brand-mark">D</span><span class="brand-name">$site_title</span></a>
  <div class="topbar-spacer"></div>
  <button class="search-trigger" id="search-trigger" type="button" aria-label="Search documentation">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
    <span>Search docs</span><kbd>Ctrl K</kbd>
  </button>
  <button class="icon-btn theme-toggle" id="theme-toggle" type="button" aria-label="Toggle theme">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
  </button>
</header>
<div class="shell">
  <aside class="sidebar" id="sidebar" aria-label="Documentation navigation">
    <nav class="sidebar-nav">$sidebar</nav>
    <div class="sidebar-footer">
      <span>Doca v$version</span>
      $repo_link
    </div>
  </aside>
  <div class="sidebar-backdrop" id="sidebar-backdrop"></div>
  <main class="main" id="main">
    <div class="content-grid">
      <article class="prose">$content
        $edit_link
        $pager
      </article>
      <aside class="page-toc" aria-label="On this page">$toc_block</aside>
    </div>
    <footer class="footer">$footer</footer>
  </main>
</div>
<div class="search-overlay" id="search-overlay" hidden>
  <div class="search-panel" role="dialog" aria-modal="true" aria-label="Search documentation">
    <div class="search-box">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><circle cx="11" cy="11" r="7"/><path d="m20 20-3.5-3.5"/></svg>
      <input id="search-input" type="search" placeholder="Search documentation…" autocomplete="off" spellcheck="false" aria-label="Search documentation">
      <button class="icon-btn search-close" id="search-close" type="button" aria-label="Close search">Esc</button>
    </div>
    <div class="search-results" id="search-results"></div>
    <div class="search-hint"><span>↑↓ to navigate</span><span>↵ to open</span><span>Esc to close</span></div>
  </div>
</div>
<script>window.__DOCA_SEARCH__ = $search_json;</script>
<script>$js</script>
</body>
</html>
"""
)


def render_page(
    *,
    config: dict[str, Any],
    page: dict[str, Any],
    nav: list[dict[str, Any]],
    search: list[dict[str, Any]],
    prev: dict[str, Any] | None = None,
    next: dict[str, Any] | None = None,
    current_url: str = "",
    version: str = "0.1.0",
) -> str:
    """Render a complete HTML page."""

    site_title = str(config.get("title") or "Doca Docs")
    page_title = str(page.get("title") or site_title)
    description = str(page.get("description") or config.get("description") or "")
    theme = config.get("theme") or {}
    theme_default = str(theme.get("default") or "auto")
    accent = str(theme.get("accent") or "#6366f1")

    title = page_title if page_title == site_title else f"{page_title} · {site_title}"

    home_url = posixpath.relpath("index.html", posixpath.dirname(current_url) or ".")
    toc = str(page.get("toc") or "")
    toc_block = (
        f'<div class="toc-title">On this page</div>{toc}' if toc else ""
    )

    repo = str(config.get("repo") or "").strip()
    repo_link = (
        f'<a href="https://github.com/{escape(repo, quote=True)}">GitHub ↗</a>' if repo else ""
    )

    edit_url = str(config.get("edit_url") or "").strip()
    source = str(page.get("source") or "")
    edit_link = ""
    if edit_url and source:
        edit_link = (
            f'<a class="edit-link" href="{escape(edit_url.rstrip("/") + "/" + source, quote=True)}" '
            'target="_blank" rel="noopener noreferrer">Edit this page ↗</a>'
        )

    search_json = json.dumps(search, ensure_ascii=False, separators=(",", ":"))
    search_json = search_json.replace("</", "<\\/")

    css = _CSS.replace("--accent:#6366f1;", f"--accent:{accent};")
    js = Template(_JS).safe_substitute(theme_default=theme_default)

    html_page = _PAGE.safe_substitute(
        lang=escape(str(config.get("lang") or "en"), quote=True),
        title=escape(title),
        description=escape(description, quote=True),
        site_title=escape(site_title),
        theme_default=escape(theme_default, quote=True),
        version=escape(version),
        home_url=escape(home_url, quote=True),
        css=css,
        js=js,
        sidebar=_nav_html(nav),
        content=page.get("html", ""),
        toc_block=toc_block,
        pager=_pager_html(prev, next),
        footer=_footer_html(config),
        repo_link=repo_link,
        edit_link=edit_link,
        search_json=search_json,
    )
    return html_page

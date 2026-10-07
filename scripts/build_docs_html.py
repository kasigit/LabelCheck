#!/usr/bin/env python3
"""Render the project's Markdown docs to polished, self-contained HTML.

Produces, in docs/:
  README.html  (the main page)  · DOCUMENTATION.html · HOW_TO_VERIFY.html · assumptions.html

README.html is the landing page; every page shares a sidebar linking all four. Each file
is standalone (CSS embedded), readable on phone or desktop, light/dark aware, with styled
tables and code blocks. The Mermaid architecture diagram is rendered via mermaid.js from a
CDN (the ASCII diagram in the source is the offline fallback).

Run:  python scripts/build_docs_html.py
Requires:  pip install markdown   (included in the backend's "dev" extra)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"


@dataclass
class Page:
    src: Path  # Markdown source
    out: str  # output filename in docs/
    title: str  # sidebar label
    is_readme: bool = False


# Nav order. README first (the main page).
PAGES: list[Page] = [
    Page(ROOT / "README.md", "README.html", "Overview", is_readme=True),
    Page(DOCS / "DOCUMENTATION.md", "DOCUMENTATION.html", "Full Documentation"),
    Page(DOCS / "HOW_TO_VERIFY.md", "HOW_TO_VERIFY.html", "How to Verify"),
    Page(DOCS / "assumptions.md", "assumptions.html", "Assumptions"),
]

# Filenames every page links to locally (so the link rewriter leaves them alone).
_LOCAL_HTML = {p.out for p in PAGES}
# Map a doc's Markdown name to its HTML output, for cross-link rewriting.
_MD_TO_HTML = {p.src.name: p.out for p in PAGES}

CSS = """
:root {
  --bg: #ffffff; --fg: #1f2328; --muted: #656d76; --border: #d0d7de;
  --accent: #0969da; --code-bg: #f6f8fa; --table-head: #f6f8fa;
  --match: #15803d; --review: #b45309; --mismatch: #b91c1c;
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1117; --fg: #e6edf3; --muted: #9198a1; --border: #30363d;
    --accent: #4493f8; --code-bg: #161b22; --table-head: #161b22;
    --match: #3fb950; --review: #d29922; --mismatch: #f85149;
  }
}
* { box-sizing: border-box; }
body {
  margin: 0; background: var(--bg); color: var(--fg);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  font-size: 17px; line-height: 1.7;
}
.layout { display: flex; gap: 0; max-width: 1100px; margin: 0 auto; }
nav.side {
  flex: 0 0 240px; padding: 28px 16px; border-right: 1px solid var(--border);
  position: sticky; top: 0; align-self: flex-start; height: 100vh; overflow-y: auto;
}
nav.side .brand { font-size: 20px; font-weight: 800; margin: 0 0 4px; }
nav.side .tagline { font-size: 13px; color: var(--muted); margin: 0 0 18px; }
nav.side a {
  display: block; padding: 8px 12px; border-radius: 6px; color: var(--fg);
  text-decoration: none; font-size: 15px; margin-bottom: 2px;
}
nav.side a:hover { background: var(--code-bg); }
nav.side a.active { background: var(--accent); color: #fff; font-weight: 600; }
main { flex: 1 1 auto; padding: 32px 40px 80px; min-width: 0; }
.content { max-width: 820px; }
h1 { font-size: 2em; border-bottom: 2px solid var(--border); padding-bottom: .3em; margin-top: 0; }
h2 { font-size: 1.5em; border-bottom: 1px solid var(--border); padding-bottom: .3em; margin-top: 2em; }
h3 { font-size: 1.2em; margin-top: 1.8em; }
a { color: var(--accent); }
p, li { font-size: 1rem; }
blockquote {
  margin: 1em 0; padding: .6em 1em; border-left: 4px solid var(--accent);
  background: var(--code-bg); border-radius: 0 6px 6px 0; color: var(--fg);
}
blockquote p { margin: .3em 0; }
code {
  background: var(--code-bg); padding: .15em .4em; border-radius: 5px;
  font-family: "SF Mono", ui-monospace, "Cascadia Code", Menlo, Consolas, monospace; font-size: .88em;
}
pre {
  background: var(--code-bg); border: 1px solid var(--border); border-radius: 8px;
  padding: 14px 16px; overflow-x: auto; line-height: 1.5;
}
pre code { background: none; padding: 0; font-size: .85em; }
table { border-collapse: collapse; width: 100%; margin: 1.2em 0; font-size: .95rem; }
th, td { border: 1px solid var(--border); padding: 8px 12px; text-align: left; vertical-align: top; }
th { background: var(--table-head); font-weight: 600; }
tr:nth-child(even) td { background: color-mix(in srgb, var(--code-bg) 55%, transparent); }
hr { border: none; border-top: 1px solid var(--border); margin: 2.5em 0; }
.badge { display: inline-block; padding: .05em .5em; border-radius: 999px; font-weight: 700; font-size: .95em; }
.mermaid { background: var(--bg); border: 1px solid var(--border); border-radius: 8px; padding: 16px; text-align: center; }
.footer { margin-top: 48px; padding-top: 16px; border-top: 1px solid var(--border); color: var(--muted); font-size: .9em; }
@media (max-width: 800px) {
  .layout { flex-direction: column; }
  nav.side { position: static; height: auto; width: 100%; border-right: none; border-bottom: 1px solid var(--border); flex-basis: auto; }
  main { padding: 20px 16px 60px; }
}
"""

_STATUS_SPANS = [
    (r"✓\s*Match", '<span class="badge" style="color:var(--match)">✓ Match</span>'),
    (r"⚠\s*Needs review", '<span class="badge" style="color:var(--review)">⚠ Needs review</span>'),
    (r"✗\s*Mismatch", '<span class="badge" style="color:var(--mismatch)">✗ Mismatch</span>'),
]


def _nav_html(active_out: str) -> str:
    links = []
    for p in PAGES:
        cls = ' class="active"' if p.out == active_out else ""
        links.append(f'<a href="{p.out}"{cls}>{p.title}</a>')
    return (
        '<nav class="side"><p class="brand">LabelCheck</p>'
        '<p class="tagline">Alcohol-label verification</p>' + "".join(links) + "</nav>"
    )


def _rewrite_links(html: str, is_readme: bool) -> str:
    """Make relative links work from docs/, where all the HTML lives.

    - Cross-doc Markdown links (docs/foo.md or foo.md) become the sibling .html.
    - For the README (whose source lives at the repo root) other relative links — into
      .claude/, etc. — are prefixed with ../ so they still resolve from docs/.
    - The other docs already sit in docs/, so only ../README.md needs fixing.
    """
    # Cross-doc links to the *.md sources -> their *.html outputs (keep any #anchor).
    for md_name, out in _MD_TO_HTML.items():
        html = html.replace(f'href="docs/{md_name}', f'href="{out}')
        html = html.replace(f'href="{md_name}', f'href="{out}')
    html = html.replace('href="../README.md', 'href="README.html')
    html = html.replace('href="docs/index.html"', 'href="README.html"')
    # The README points at docs/README.html; from inside docs/ that's just README.html.
    html = html.replace('href="docs/README.html', 'href="README.html')

    if is_readme:
        # Prefix ../ to any remaining relative link (root-relative in the source).
        def prefix(m: re.Match) -> str:
            url = m.group(1)
            base = url.split("#")[0]
            if url.startswith(("http://", "https://", "#", "../", "mailto:")) or base in _LOCAL_HTML:
                return m.group(0)
            return f'href="../{url}"'

        html = re.sub(r'href="([^"]+)"', prefix, html)
    return html


def _render_body(md_text: str, is_readme: bool) -> str:
    html = markdown.markdown(
        md_text,
        extensions=["extra", "sane_lists", "toc", "nl2br", "admonition"],
        output_format="html5",
    )
    html = _rewrite_links(html, is_readme)
    # ```mermaid fenced blocks -> <pre class="mermaid"> so mermaid.js renders them.
    html = re.sub(
        r'<pre><code class="language-mermaid">(.*?)</code></pre>',
        r'<pre class="mermaid">\1</pre>',
        html,
        flags=re.DOTALL,
    )
    for pattern, repl in _STATUS_SPANS:
        html = re.sub(pattern, repl, html)
    return html


def _page_html(title: str, active_out: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — LabelCheck</title>
<style>{CSS}</style>
</head>
<body>
<div class="layout">
{_nav_html(active_out)}
<main><div class="content">
{body}
<div class="footer">LabelCheck documentation · <a href="README.html">Home</a></div>
</div></main>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script>
  if (window.mermaid) {{
    const dark = window.matchMedia('(prefers-color-scheme: dark)').matches;
    mermaid.initialize({{ startOnLoad: true, theme: dark ? 'dark' : 'default' }});
  }}
</script>
</body>
</html>
"""


def main() -> None:
    # Remove the old landing page if present.
    old_index = DOCS / "index.html"
    if old_index.exists():
        old_index.unlink()
        print("removed docs/index.html")

    for p in PAGES:
        if not p.src.exists():
            print(f"skip (missing): {p.src}")
            continue
        body = _render_body(p.src.read_text(encoding="utf-8"), p.is_readme)
        (DOCS / p.out).write_text(_page_html(p.title, p.out, body), encoding="utf-8")
        print(f"wrote docs/{p.out}")


if __name__ == "__main__":
    main()

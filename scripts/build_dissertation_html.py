#!/usr/bin/env python3
"""Render DISSERTATION_FULL.md as a self-contained reading edition.

Figures are inlined as data URIs so the page is one portable file, and the
palette is taken from the figures themselves so charts and page read as one
object. Editorial blockquotes are dropped, as in the .docx build.

    .venv/bin/python scripts/build_dissertation_html.py
"""
from __future__ import annotations

import base64
import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/dissertation/DISSERTATION_FULL.md"
BASE = SRC.parent
OUT = ROOT / "build" / "dissertation_reading_edition.html"

BANNED = ["delete before submission", "End of dissertation draft",
          "Editorial status", "REGISTRY CHECK"]


def data_uri(path: Path, max_px: int = 1500) -> str:
    """Inline a figure, downsampled to keep the single-file page portable.

    The page carries every figure in its own bytes, so full-resolution PNGs put
    it past what the publishing endpoint will accept in one request. At 1500 px
    across a 70ch column these are still sharp on a retina display.
    """
    import io

    from PIL import Image

    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.width > max_px:
            im = im.resize((max_px, round(im.height * max_px / im.width)),
                           Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=86, optimize=True, progressive=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


INLINE = re.compile(r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`|\[[^\]]+?\]\([^)]+?\))", re.S)


def inline(t: str) -> str:
    out = []
    for piece in INLINE.split(t):
        if not piece:
            continue
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            out.append(f"<strong>{html.escape(piece[2:-2])}</strong>")
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            out.append(f"<em>{html.escape(piece[1:-1])}</em>")
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            out.append(f"<code>{html.escape(piece[1:-1])}</code>")
        else:
            m = re.fullmatch(r"\[([^\]]+?)\]\(([^)]+?)\)", piece)
            out.append(html.escape(m.group(1)) if m else html.escape(piece))
    return "".join(out)


def slug(t: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", t.lower()).strip("-")


NUMERIC = re.compile(r"^[−\-]?[\d.,]+\s*%?$")


def convert(md: str) -> tuple[str, list[tuple[int, str, str]]]:
    lines = md.splitlines()
    out, toc = [], []
    i, n = 0, len(lines)
    fignum = 0
    while i < n:
        line = lines[i]
        if line.startswith(">") or line.strip() == "---" or not line.strip():
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            lvl, txt = len(m.group(1)), m.group(2).strip()
            sid = slug(txt)
            if lvl <= 2:
                toc.append((lvl, txt, sid))
            num = re.match(r"^(\d+\.\d+|Chapter \d+)", txt)
            eyebrow = ""
            if num and lvl == 2:
                rest = txt[len(num.group(1)):].lstrip(" —-")
                eyebrow = (f'<span class="num">{html.escape(num.group(1))}</span>'
                           f'<span class="ttl">{inline(rest)}</span>')
            cls = "chapter" if lvl == 1 and txt.startswith("Chapter") else ""
            body = eyebrow or inline(txt)
            out.append(f'<h{lvl} id="{sid}" class="{cls}">{body}</h{lvl}>')
            i += 1
            continue

        fm = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$", line)
        if fm:
            p = (BASE / fm.group(2)).resolve()
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            cap = ""
            if j < n and re.match(r"^\*\*Figure ", lines[j]):
                buf = []
                while j < n and lines[j].strip():
                    buf.append(lines[j].strip())
                    j += 1
                cap = " ".join(buf)
                i = j
            else:
                i += 1
            if p.exists():
                fignum += 1
                out.append(
                    f'<figure><img src="{data_uri(p)}" alt="{html.escape(fm.group(1))}" '
                    f'loading="lazy">'
                    + (f"<figcaption>{inline(cap)}</figcaption>" if cap else "")
                    + "</figure>")
            continue

        if re.match(r"^\*\*Table ", line):
            buf = [line.strip()]
            i += 1
            while i < n and lines[i].strip() and not lines[i].lstrip().startswith("|"):
                buf.append(lines[i].strip())
                i += 1
            out.append(f'<p class="tcap">{inline(" ".join(buf))}</p>')
            continue

        if line.lstrip().startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not re.fullmatch(r"[\s:\-]*", "".join(cells)):
                    rows.append(cells)
                i += 1
            if rows:
                head, body = rows[0], rows[1:]
                th = "".join(f"<th>{inline(c)}</th>" for c in head)
                trs = []
                for r in body:
                    tds = []
                    for k, c in enumerate(r[:len(head)]):
                        cls = ' class="n"' if k and NUMERIC.match(re.sub(r"[*`]", "", c)) else ""
                        tds.append(f"<td{cls}>{inline(c)}</td>")
                    trs.append("<tr>" + "".join(tds) + "</tr>")
                out.append('<div class="tw"><table><thead><tr>' + th
                           + "</tr></thead><tbody>" + "".join(trs)
                           + "</tbody></table></div>")
            continue

        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if lm:
            ordered = bool(re.match(r"\d+\.", lm.group(2)))
            items = []
            while i < n:
                mm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", lines[i])
                if not mm:
                    break
                buf = [mm.group(3)]
                i += 1
                while i < n and lines[i].strip() and not re.match(
                        r"^(\s*)([-*]|\d+\.)\s+", lines[i]) and not lines[i].startswith("#"):
                    buf.append(lines[i].strip())
                    i += 1
                items.append(f"<li>{inline(' '.join(buf))}</li>")
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>{''.join(items)}</{tag}>")
            continue

        buf = []
        while i < n and lines[i].strip() and not lines[i].startswith(("#", "|", ">", "!")) \
                and not re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]) \
                and not re.match(r"^\*\*(Figure|Table) ", lines[i]) \
                and lines[i].strip() != "---":
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f"<p>{inline(' '.join(buf))}</p>")
        else:
            i += 1
    return "\n".join(out), toc


CSS = """
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:ital,wght@0,400;0,600;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>
:root{
  --paper:#FAFBFA; --card:#FFFFFF; --ink:#1A1F1D; --body:#2A302D;
  --muted:#6B7671; --rule:#DDE3E0; --rule-soft:#EAEEEC;
  --teal:#0F5C55; --teal-soft:#E4EFED; --amber:#8A6220; --clay:#8F3A30;
  --serif:"IBM Plex Serif",Georgia,"Times New Roman",serif;
  --sans:"IBM Plex Sans",-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#121614; --card:#191E1C; --ink:#E9EEEB; --body:#C9D2CE;
  --muted:#8C9994; --rule:#2C3532; --rule-soft:#222A27;
  --teal:#6FC3B4; --teal-soft:#1B2A27; --amber:#D3A45E; --clay:#E08D7F;
}}
:root[data-theme="dark"]{
  --paper:#121614; --card:#191E1C; --ink:#E9EEEB; --body:#C9D2CE;
  --muted:#8C9994; --rule:#2C3532; --rule-soft:#222A27;
  --teal:#6FC3B4; --teal-soft:#1B2A27; --amber:#D3A45E; --clay:#E08D7F;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--body);margin:0;
  font:400 17px/1.68 var(--serif);
  -webkit-font-smoothing:antialiased;text-rendering:optimizeLegibility}
.shell{display:grid;grid-template-columns:236px minmax(0,1fr);gap:56px;
  max-width:1140px;margin:0 auto;padding:0 28px}
nav{position:sticky;top:0;align-self:start;max-height:100vh;overflow-y:auto;
  padding:40px 0 40px;font-family:var(--sans);font-size:12.6px;line-height:1.45}
nav .navlabel{font-size:10.5px;letter-spacing:.13em;text-transform:uppercase;
  color:var(--muted);margin:0 0 14px;font-weight:600}
nav a{display:block;color:var(--muted);text-decoration:none;padding:3.5px 0;
  border-left:2px solid transparent;padding-left:11px;margin-left:-11px}
nav a:hover{color:var(--teal);border-left-color:var(--rule)}
nav a.l1{color:var(--ink);font-weight:600;margin-top:15px}
nav a.l1:first-child{margin-top:0}
main{padding:0 0 120px;max-width:70ch}
header.title{padding:104px 0 60px;border-bottom:1px solid var(--rule);
  margin-bottom:52px}
header.title .kicker{font-family:var(--sans);font-size:11px;font-weight:600;
  letter-spacing:.16em;text-transform:uppercase;color:var(--teal);margin:0 0 22px}
header.title h1{font-size:38px;line-height:1.16;font-weight:600;color:var(--ink);
  margin:0 0 26px;text-wrap:balance;letter-spacing:-.014em}
header.title .sub{font-family:var(--sans);font-size:14.5px;color:var(--muted);
  line-height:1.62;margin:0}
header.title .sub b{color:var(--ink);font-weight:600}
.facts{display:flex;flex-wrap:wrap;gap:0;margin:34px 0 0;
  border-top:1px solid var(--rule-soft)}
.facts div{flex:1 1 128px;padding:15px 18px 15px 0;border-right:1px solid var(--rule-soft)}
.facts div:last-child{border-right:0}
.facts dt{font-family:var(--sans);font-size:10px;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);margin:0 0 5px;font-weight:600}
.facts dd{margin:0;font-family:var(--sans);font-size:19px;font-weight:600;
  color:var(--teal);font-variant-numeric:tabular-nums}
.facts dd small{display:block;font-size:11px;font-weight:400;color:var(--muted);
  margin-top:2px;letter-spacing:0}
h1,h2,h3{color:var(--ink);text-wrap:balance}
h1.chapter{font-size:13px;font-family:var(--sans);font-weight:600;
  letter-spacing:.15em;text-transform:uppercase;color:var(--teal);
  margin:82px 0 4px;padding-top:30px;border-top:2px solid var(--teal)}
h2{font-size:23px;font-weight:600;line-height:1.28;margin:52px 0 14px;
  letter-spacing:-.008em;display:flex;gap:13px;align-items:baseline}
h2 .num{font-family:var(--sans);font-size:12.5px;font-weight:600;color:var(--muted);
  flex:none;padding-top:2px;font-variant-numeric:tabular-nums}
h3{font-size:16.5px;font-weight:600;margin:34px 0 10px;font-style:italic}
p{margin:0 0 17px}
main>p:first-of-type{font-size:17.6px}
strong{font-weight:600;color:var(--ink)}
code{font-family:var(--mono);font-size:.855em;background:var(--rule-soft);
  padding:1.5px 5px;border-radius:3px;color:var(--ink);
  word-break:break-word}
ul,ol{margin:0 0 19px;padding-left:22px}
li{margin:0 0 8px;padding-left:4px}
li::marker{color:var(--muted);font-family:var(--sans);font-size:.85em}
figure{margin:38px 0 34px;width:min(100%,calc(70ch + 88px));
  margin-left:calc(-1 * min(44px, 4vw))}
figure img{width:100%;display:block;border:1px solid var(--rule);
  border-radius:3px;background:var(--card)}
figcaption{font-family:var(--sans);font-size:12.9px;line-height:1.56;
  color:var(--muted);margin-top:11px;padding-left:2px}
figcaption strong{color:var(--teal);font-weight:600}
.tcap{font-family:var(--sans);font-size:12.9px;line-height:1.56;color:var(--muted);
  margin:34px 0 9px}
.tcap strong{color:var(--teal);font-weight:600}
.tw{overflow-x:auto;margin:0 0 30px;border:1px solid var(--rule);border-radius:3px;
  background:var(--card)}
table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:13.2px}
th{background:var(--teal);color:#fff;font-weight:600;text-align:left;
  padding:9px 13px;white-space:nowrap;font-size:12.3px;letter-spacing:.01em}
td{padding:8px 13px;border-top:1px solid var(--rule-soft);color:var(--body)}
td.n{text-align:right;font-variant-numeric:tabular-nums}
tbody tr:nth-child(even){background:var(--rule-soft)}
td code{background:transparent;padding:0}
@media (max-width:900px){
  .shell{grid-template-columns:1fr;gap:0}
  nav{position:static;max-height:none;padding:26px 0 0;
    border-bottom:1px solid var(--rule);margin-bottom:8px;
    columns:2;column-gap:24px}
  nav a.l1{break-after:avoid}
  header.title{padding:44px 0 34px}
  header.title h1{font-size:29px}
  figure{margin-left:0;width:100%}
  main{max-width:none}
}
@media print{
  nav{display:none} .shell{grid-template-columns:1fr;max-width:none}
  h1.chapter{page-break-before:always} figure,.tw{page-break-inside:avoid}
  body{font-size:11pt;background:#fff}
}
@media (prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
"""


def main() -> None:
    md = SRC.read_text()
    body, toc = convert(md)

    for b in BANNED:
        assert b.lower() not in re.sub(r"<[^>]+>", "", body).lower(), \
            f"editorial text leaked: {b}"

    nav = "".join(
        f'<a class="l{lvl}" href="#{sid}">{html.escape(t)}</a>'
        for lvl, t, sid in toc
        if not t.startswith(("List of", "Table of Contents")))

    title = re.match(r"^#\s+(.*)$", md.splitlines()[0]).group(1)
    short, sub = title.split(":", 1)

    # Counted from the source, never typed in. A hardcoded figure here drifted
    # to 11,569 while the chapters grew to 11,942, and the page went on
    # announcing the stale number on its own front matter.
    _lines = md.splitlines()
    _cut = next(i for i, l in enumerate(_lines)
                if re.match(r"^#+\s*References", l, re.I))
    _body = [l for l in _lines[:_cut] if not l.startswith(">")]
    _ch1 = next(i for i, l in enumerate(_body) if l.startswith("## 1.1"))
    _keep, _skip = [], False
    for l in _body[_ch1:]:
        if l.startswith("**Figure "):
            _skip = True
        elif _skip and not l.strip():
            _skip = False
        if not _skip and not l.startswith("!["):
            _keep.append(l)
    words = len(re.findall(r"\S+", "\n".join(_keep)))
    head = f"""<header class="title">
<p class="kicker">MSc Artificial Intelligence and Business Strategy · Aston University</p>
<h1>{html.escape(short)}<br><span style="color:var(--muted);font-weight:400">{html.escape(sub.strip())}</span></h1>
<p class="sub"><b>Uririe, Orume Dominic</b> &nbsp;·&nbsp; Project JBKS1 &nbsp;·&nbsp;
September 2026<br>Supervisors: Julien Barney and Kate Sugden</p>
<dl class="facts">
<div><dt>Conditions</dt><dd>5<small>4 agentic + human</small></dd></div>
<div><dt>Observations</dt><dd>600<small>across 3 specifications</small></dd></div>
<div><dt>Cohen's κ</dt><dd>0.87<small>two independent raters</small></dd></div>
<div><dt>Main text</dt><dd>{words:,}<small>words</small></dd></div>
</dl>
</header>"""

    # drop the markdown front-matter lists; the sidebar is the contents
    body = re.sub(r'<h2 id="table-of-contents".*?(?=<h1|<h2 id="declaration")', "",
                  body, flags=re.S)

    page = (f"<title>Measuring the Unmeasured</title>\n{CSS}\n"
            f'<div class="shell">\n<nav><p class="navlabel">Contents</p>{nav}</nav>\n'
            f"<main>{head}\n{body}</main>\n</div>\n")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  sections in nav: {len(toc)}   figures: {body.count('<figure>')}   "
          f"tables: {body.count('<table>')}")


if __name__ == "__main__":
    main()

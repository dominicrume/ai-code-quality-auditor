#!/usr/bin/env python3
"""Build a browsable gallery of the study's supporting evidence.

Captions live in evidence/captions.tsv so they can be edited without touching
this script; anything not described there is listed with its date and left for
the author to caption.

    .venv/bin/python scripts/build_evidence_gallery.py
"""
from __future__ import annotations

import base64
import csv
import html
import io
from datetime import datetime
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"
PREPARED = EV / "prepared"
OUT = ROOT / "build" / "evidence_gallery.html"
MAX_PX = 1500
GROUP_ORDER = ["Validation", "Instrument", "Adoption", "Superseded",
               "Process", "Uncaptioned"]


def thumb(p: Path) -> str:
    with Image.open(p) as im:
        im = im.convert("RGB")
        if im.width > MAX_PX:
            im = im.resize((MAX_PX, round(im.height * MAX_PX / im.width)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=82, optimize=True)
    return "data:image/jpeg;base64," + base64.b64encode(buf.getvalue()).decode()


def load_captions() -> dict[str, dict]:
    out = {}
    f = EV / "captions.tsv"
    if not f.exists():
        return out
    for row in csv.DictReader(
            (l for l in f.read_text().splitlines() if not l.startswith("#")),
            delimiter="\t",
            fieldnames=["filename", "group", "title", "caption", "verified"]):
        if row["filename"]:
            out[row["filename"].strip()] = row
    return out


def main() -> None:
    caps = load_captions()
    items = []
    src = PREPARED if PREPARED.exists() else EV
    for p in sorted(src.iterdir()):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        c = caps.get(p.name, {})
        with Image.open(p) as im:
            w, h = im.size
        items.append({
            "src": thumb(p),
            "group": (c.get("group") or "Uncaptioned").strip(),
            "title": (c.get("title") or p.stem.replace("_", " ")).strip(),
            "caption": (c.get("caption") or "").strip(),
            "verified": (c.get("verified") or "").strip(),
            "date": datetime.fromtimestamp(p.stat().st_mtime).strftime("%-d %B %Y"),
            "dims": f"{w}×{h}",
            "name": p.name,
        })

    cards = []
    for g in GROUP_ORDER:
        rows = [i for i in items if i["group"] == g]
        if not rows:
            continue
        blurb = {
            "Validation": "Evidence bearing on the inter-rater reliability study "
                          "reported in §4.7. Both raters' totals were checked "
                          "against the sheets used to compute Cohen's κ.",
            "Instrument": "The auditor running against real codebases, including "
                          "one it did not produce and one run by someone else.",
            "Adoption": "Public installation statistics from PyPI, showing use "
                        "outside this study.",
            "Superseded": "Kept as a record of what the analysis produced before "
                          "it was corrected. Not the reported figures.",
            "Process": "How the work was actually carried out, including what it "
                       "corrected about itself.",
            "Uncaptioned": "Held in the evidence folder and not yet described. "
                           "Add a row to evidence/captions.tsv to caption one.",
        }[g]
        cards.append(f'<section><h2>{g}</h2><p class="blurb">{blurb}</p><div class="grid">')
        for i in rows:
            v = (f'<p class="ver"><span>Verified</span>{html.escape(i["verified"])}</p>'
                 if i["verified"] else "")
            cap = f'<p class="cap">{html.escape(i["caption"])}</p>' if i["caption"] else ""
            cards.append(
                f'<figure><a href="{i["src"]}" target="_blank" rel="noopener">'
                f'<img src="{i["src"]}" alt="{html.escape(i["title"])}" loading="lazy"></a>'
                f'<figcaption><h3>{html.escape(i["title"])}</h3>{cap}{v}'
                f'<p class="meta">{i["date"]} · {i["dims"]} · '
                f'<code>{html.escape(i["name"])}</code></p></figcaption></figure>')
        cards.append("</div></section>")

    n_cap = sum(1 for i in items if i["caption"])
    page = TEMPLATE.replace("__CARDS__", "\n".join(cards)) \
                   .replace("__N__", str(len(items))) \
                   .replace("__NCAP__", str(n_cap))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"  {len(items)} items, {n_cap} captioned")


TEMPLATE = """<title>Study Evidence</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Serif:wght@400;600&family=IBM+Plex+Mono:wght@400&display=swap">
<style>
:root{
  --paper:#FAFBFA;--card:#FFFFFF;--ink:#1A1F1D;--body:#2A302D;--muted:#6B7671;
  --rule:#DDE3E0;--rule-soft:#EAEEEC;--teal:#0F5C55;--teal-soft:#E4EFED;
  --serif:"IBM Plex Serif",Georgia,serif;
  --sans:"IBM Plex Sans",-apple-system,"Segoe UI",sans-serif;
  --mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --paper:#121614;--card:#191E1C;--ink:#E9EEEB;--body:#C9D2CE;--muted:#8C9994;
  --rule:#2C3532;--rule-soft:#222A27;--teal:#6FC3B4;--teal-soft:#1B2A27;
}}
:root[data-theme="dark"]{
  --paper:#121614;--card:#191E1C;--ink:#E9EEEB;--body:#C9D2CE;--muted:#8C9994;
  --rule:#2C3532;--rule-soft:#222A27;--teal:#6FC3B4;--teal-soft:#1B2A27;
}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--body);margin:0;
  font:400 15px/1.6 var(--sans);-webkit-font-smoothing:antialiased}
.wrap{max-width:1180px;margin:0 auto;padding:0 26px 96px}
header.top{padding:70px 0 34px;border-bottom:1px solid var(--rule);margin-bottom:12px}
.kicker{font-size:11px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;
  color:var(--teal);margin:0 0 16px}
h1{font-family:var(--serif);font-size:35px;font-weight:600;color:var(--ink);
  margin:0 0 14px;letter-spacing:-.014em;text-wrap:balance}
.lede{font-family:var(--serif);font-size:17px;line-height:1.62;color:var(--body);
  max-width:66ch;margin:0}
.count{margin-top:22px;font-size:12.5px;color:var(--muted);
  font-variant-numeric:tabular-nums}
section{margin-top:52px}
h2{font-family:var(--serif);font-size:22px;font-weight:600;color:var(--ink);
  margin:0 0 5px;letter-spacing:-.008em}
.blurb{font-size:13.6px;color:var(--muted);margin:0 0 22px;max-width:62ch}
.grid{display:grid;gap:26px;grid-template-columns:repeat(auto-fill,minmax(320px,1fr))}
figure{margin:0;background:var(--card);border:1px solid var(--rule);border-radius:4px;
  overflow:hidden;display:flex;flex-direction:column}
figure a{display:block;background:var(--rule-soft);line-height:0}
figure img{width:100%;height:206px;object-fit:cover;object-position:top center;
  display:block;transition:opacity .16s}
figure a:hover img{opacity:.9}
figure a:focus-visible{outline:2px solid var(--teal);outline-offset:-2px}
figcaption{padding:15px 17px 16px;display:flex;flex-direction:column;gap:8px;flex:1}
figcaption h3{font-size:14.6px;font-weight:600;color:var(--ink);margin:0;line-height:1.35}
.cap{font-size:13.2px;line-height:1.56;color:var(--body);margin:0}
.ver{font-size:12.2px;line-height:1.5;color:var(--muted);margin:0;
  background:var(--teal-soft);border-radius:3px;padding:8px 10px}
.ver span{display:block;font-size:9.6px;font-weight:600;letter-spacing:.11em;
  text-transform:uppercase;color:var(--teal);margin-bottom:3px}
.meta{font-family:var(--mono);font-size:10.9px;color:var(--muted);margin:auto 0 0;
  padding-top:9px;border-top:1px solid var(--rule-soft);word-break:break-all}
.meta code{font-family:inherit;background:none;padding:0}
@media (max-width:640px){
  header.top{padding:40px 0 26px} h1{font-size:26px}
  .grid{grid-template-columns:1fr}
}
@media (prefers-reduced-motion:reduce){*{transition:none!important}}
</style>
<div class="wrap">
<header class="top">
<p class="kicker">Aston University · Project JBKS1 · Uririe, Orume Dominic</p>
<h1>Study evidence</h1>
<p class="lede">Supporting material for <em>Measuring the Unmeasured</em>. Two of
these are cross-checked against the data files behind Chapter 4: each rater's
completion screen is compared value by value with the sheet used to compute
Cohen's&nbsp;κ, and both match on all nineteen items.</p>
<p class="count">__NCAP__ of __N__ items described · click any image to open it full size</p>
</header>
__CARDS__
</div>
"""

if __name__ == "__main__":
    main()

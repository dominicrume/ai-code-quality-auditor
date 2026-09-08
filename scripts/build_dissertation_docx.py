#!/usr/bin/env python3
"""Render DISSERTATION_FULL.md as a submission-ready .docx.

The .docx is the transport format: uploaded to Google Drive it converts to a
native Google Doc with headings, tables and figures intact, so the outline
pane works and the author can export to PDF unaltered.

Editorial blockquotes -- the ones marked "delete before submission" -- are
dropped, because the whole point of this artefact is that it is the thing
handed to a marker.

    .venv/bin/python scripts/build_dissertation_docx.py
"""
from __future__ import annotations

import re
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "docs/dissertation/DISSERTATION_FULL.md"
BASE = SRC.parent
OUT = ROOT / "build" / "Dissertation_Uririe_Orume_Dominic.docx"

INK = RGBColor(0x1A, 0x1F, 0x1D)
ACCENT = RGBColor(0x0F, 0x51, 0x4B)
MUTED = RGBColor(0x5A, 0x60, 0x5C)

BODY_FONT = "Georgia"
HEAD_FONT = "Georgia"
MONO_FONT = "Consolas"
TEXT_WIDTH_IN = 6.0


# ------------------------------------------------------------------ utilities
def set_cell_bg(cell, hexcolor):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hexcolor)
    tcPr.append(shd)


def add_page_numbers(section):
    """Footer with a live PAGE field, centred."""
    p = section.footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = p.add_run()
    for instr, kind in (("begin", "w:fldChar"), (" PAGE ", "w:instrText"),
                        ("end", "w:fldChar")):
        el = OxmlElement(kind)
        if kind == "w:fldChar":
            el.set(qn("w:fldCharType"), instr)
        else:
            el.set(qn("xml:space"), "preserve")
            el.text = instr
        run._r.append(el)
    run.font.name = BODY_FONT
    run.font.size = Pt(9.5)
    run.font.color.rgb = MUTED


INLINE = re.compile(
    r"(\*\*.+?\*\*|\*[^*\n]+?\*|`[^`\n]+?`|\[[^\]]+?\]\([^)]+?\))", re.S)


def add_runs(par, text, size=11, color=INK, italic_all=False):
    """Render markdown inline emphasis into runs."""
    text = text.replace(" ", " ")
    for piece in INLINE.split(text):
        if not piece:
            continue
        bold = italic = mono = False
        if piece.startswith("**") and piece.endswith("**") and len(piece) > 4:
            piece, bold = piece[2:-2], True
        elif piece.startswith("*") and piece.endswith("*") and len(piece) > 2:
            piece, italic = piece[1:-1], True
        elif piece.startswith("`") and piece.endswith("`") and len(piece) > 2:
            piece, mono = piece[1:-1], True
        else:
            m = re.fullmatch(r"\[([^\]]+?)\]\(([^)]+?)\)", piece)
            if m:
                piece = m.group(1)
        run = par.add_run(piece)
        run.bold = bold
        run.italic = italic or italic_all
        run.font.size = Pt(size - (0.6 if mono else 0))
        run.font.name = MONO_FONT if mono else BODY_FONT
        run.font.color.rgb = color


def body_par(doc, text, size=11, space_after=8, first_line_indent=None,
             justify=True):
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_after = Pt(space_after)
    pf.line_spacing = 1.42
    if justify:
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if first_line_indent:
        pf.first_line_indent = Inches(first_line_indent)
    add_runs(p, text, size=size)
    return p


def heading(doc, text, level):
    sizes = {1: 17, 2: 13, 3: 11.5}
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(20 if level == 1 else 14)
    p.paragraph_format.space_after = Pt(7)
    p.paragraph_format.keep_with_next = True
    run = p.add_run(text)
    run.bold = True
    run.font.size = Pt(sizes.get(level, 11))
    run.font.name = HEAD_FONT
    run.font.color.rgb = ACCENT if level <= 2 else INK
    p.style = doc.styles[f"Heading {min(level, 3)}"]
    for r in p.runs:
        r.font.color.rgb = ACCENT if level <= 2 else INK
        r.font.name = HEAD_FONT
        r.font.size = Pt(sizes.get(level, 11))
        r.bold = True
    return p


# Figures are generated at 300 dpi for print. Embedding them at full size
# makes the .docx too large to transport; 1600 px across a 6-inch column is
# still 267 dpi, which survives PDF export without visible loss.
MAX_PX = 900
_TMP = ROOT / "build" / "_figures_optimised"


def optimised(path: Path) -> Path:
    _TMP.mkdir(parents=True, exist_ok=True)
    out = _TMP / path.name
    if out.exists() and out.stat().st_mtime >= path.stat().st_mtime:
        return out
    with Image.open(path) as im:
        im = im.convert("RGB")
        if im.width > MAX_PX:
            h = round(im.height * MAX_PX / im.width)
            im = im.resize((MAX_PX, h), Image.LANCZOS)
        # These are charts and line diagrams: a 256-colour palette is visually
        # lossless here and roughly a third the size of truecolour PNG.
        im.quantize(colors=256, method=Image.MEDIANCUT).save(
            out, "PNG", optimize=True)
    return out


def add_figure(doc, path: Path, caption: str):
    path = optimised(path)
    with Image.open(path) as im:
        w, h = im.size
    width = min(TEXT_WIDTH_IN, TEXT_WIDTH_IN)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    p.add_run().add_picture(str(path), width=Inches(width))
    if caption:
        cp = doc.add_paragraph()
        cp.alignment = WD_ALIGN_PARAGRAPH.LEFT
        cp.paragraph_format.space_after = Pt(14)
        cp.paragraph_format.left_indent = Inches(0.25)
        cp.paragraph_format.right_indent = Inches(0.25)
        cp.paragraph_format.line_spacing = 1.15
        add_runs(cp, caption, size=9.5, color=MUTED)


def add_table(doc, rows):
    header, body = rows[0], rows[1:]
    t = doc.add_table(rows=1, cols=len(header))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = True
    for i, cell in enumerate(t.rows[0].cells):
        cell.text = ""
        set_cell_bg(cell, "EDEFEC")
        par = cell.paragraphs[0]
        par.paragraph_format.space_after = Pt(2)
        add_runs(par, header[i].strip(), size=9.5)
        for r in par.runs:
            r.bold = True
    for row in body:
        cells = t.add_row().cells
        for i, val in enumerate(row[:len(header)]):
            cells[i].text = ""
            par = cells[i].paragraphs[0]
            par.paragraph_format.space_after = Pt(2)
            add_runs(par, val.strip(), size=9.5)
    doc.add_paragraph().paragraph_format.space_after = Pt(6)


# --------------------------------------------------------------- title page
def title_page(doc, meta):
    for _ in range(3):
        doc.add_paragraph()
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = p.add_run(meta["title"])
    r.bold = True
    r.font.size = Pt(20)
    r.font.name = HEAD_FONT
    r.font.color.rgb = INK
    p.paragraph_format.space_after = Pt(26)
    p.paragraph_format.line_spacing = 1.25

    rule = doc.add_paragraph()
    rule.alignment = WD_ALIGN_PARAGRAPH.CENTER
    rr = rule.add_run("— " * 12)
    rr.font.color.rgb = ACCENT
    rr.font.size = Pt(10)
    rule.paragraph_format.space_after = Pt(26)

    for text, size, bold, colour, gap in [
        (meta["degree"], 13, True, ACCENT, 6),
        (meta["institution"], 12, False, INK, 3),
        (meta["project"], 11, False, MUTED, 26),
        (meta["author_label"], 10.5, False, MUTED, 2),
        (meta["author"], 15, True, INK, 22),
        (meta["supervisors"], 11, False, INK, 26),
        (meta["date"], 11, False, MUTED, 4),
        (meta["wordcount"], 10, False, MUTED, 0),
    ]:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = p.add_run(text)
        r.bold = bold
        r.font.size = Pt(size)
        r.font.name = BODY_FONT
        r.font.color.rgb = colour
        p.paragraph_format.space_after = Pt(gap)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


# ------------------------------------------------------------------- parsing
FIG_RE = re.compile(r"^!\[([^\]]*)\]\(([^)]+)\)\s*$")
CAP_RE = re.compile(r"^\*\*(Figure|Table) ([0-9.]+)\*\*")


def render(doc, lines):
    i, n = 0, len(lines)
    pending_fig = None
    while i < n:
        line = lines[i]

        # editorial notes -- never reach the marker
        if line.startswith(">"):
            i += 1
            continue

        if not line.strip() or line.strip() == "---":
            i += 1
            continue

        m = re.match(r"^(#{1,3})\s+(.*)$", line)
        if m:
            level, text = len(m.group(1)), m.group(2).strip()
            if level == 1 and text.startswith("Chapter"):
                doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)
            heading(doc, text, level)
            i += 1
            continue

        fm = FIG_RE.match(line)
        if fm:
            path = (BASE / fm.group(2)).resolve()
            j = i + 1
            while j < n and not lines[j].strip():
                j += 1
            caption = ""
            if j < n and CAP_RE.match(lines[j]):
                cap_lines = []
                while j < n and lines[j].strip():
                    cap_lines.append(lines[j].strip())
                    j += 1
                caption = " ".join(cap_lines)
                i = j
            else:
                i += 1
            if path.exists():
                add_figure(doc, path, caption)
            continue

        # standalone caption (table captions precede their table)
        if CAP_RE.match(line):
            cap = [line.strip()]
            i += 1
            while i < n and lines[i].strip() and not lines[i].lstrip().startswith("|"):
                cap.append(lines[i].strip())
                i += 1
            cp = doc.add_paragraph()
            cp.paragraph_format.space_before = Pt(10)
            cp.paragraph_format.space_after = Pt(4)
            cp.paragraph_format.keep_with_next = True
            cp.paragraph_format.line_spacing = 1.15
            add_runs(cp, " ".join(cap), size=9.5, color=MUTED)
            continue

        if line.lstrip().startswith("|"):
            rows = []
            while i < n and lines[i].lstrip().startswith("|"):
                cells = [c for c in lines[i].strip().strip("|").split("|")]
                if not re.fullmatch(r"[\s:\-]+", "".join(cells)):
                    rows.append(cells)
                i += 1
            if rows:
                add_table(doc, rows)
            continue

        lm = re.match(r"^(\s*)([-*]|\d+\.)\s+(.*)$", line)
        if lm:
            indent = len(lm.group(1)) // 2
            ordered = bool(re.match(r"\d+\.", lm.group(2)))
            text = [lm.group(3)]
            i += 1
            while i < n and lines[i].strip() and not re.match(
                    r"^(\s*)([-*]|\d+\.)\s+", lines[i]) and not lines[i].startswith("#"):
                text.append(lines[i].strip())
                i += 1
            p = doc.add_paragraph(
                style="List Number" if ordered else "List Bullet")
            p.paragraph_format.left_indent = Inches(0.3 + 0.25 * indent)
            p.paragraph_format.space_after = Pt(5)
            p.paragraph_format.line_spacing = 1.3
            add_runs(p, " ".join(text), size=10.6)
            continue

        # ordinary paragraph
        buf = []
        while i < n and lines[i].strip() and not lines[i].startswith(("#", "|", ">", "!")) \
                and not re.match(r"^(\s*)([-*]|\d+\.)\s+", lines[i]) \
                and not CAP_RE.match(lines[i]) and lines[i].strip() != "---":
            buf.append(lines[i].strip())
            i += 1
        if buf:
            body_par(doc, " ".join(buf))
        else:
            i += 1


def main():
    text = SRC.read_text()
    lines = text.splitlines()

    # word count for the title page (chapters, excluding figure captions)
    cut = next(k for k, l in enumerate(lines) if re.match(r"^#+\s*References", l, re.I))
    body = [l for l in lines[:cut] if not l.startswith(">")]
    ch1 = next(k for k, l in enumerate(body) if l.startswith("## 1.1"))
    keep, skip = [], False
    for l in body[ch1:]:
        if l.startswith("**Figure "):
            skip = True
        elif skip and not l.strip():
            skip = False
        if not skip and not l.startswith("!["):
            keep.append(l)
    words = len(re.findall(r"\S+", "\n".join(keep)))

    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = sec.bottom_margin = Inches(1.0)
    sec.left_margin = sec.right_margin = Inches(1.25)
    add_page_numbers(sec)

    normal = doc.styles["Normal"]
    normal.font.name = BODY_FONT
    normal.font.size = Pt(11)
    normal.font.color.rgb = INK

    title = lines[0].lstrip("# ").strip()
    title_page(doc, {
        "title": title,
        "degree": "MSc Artificial Intelligence and Business Strategy",
        "institution": "Aston University",
        "project": "Project JBKS1",
        "author_label": "Submitted by",
        "author": "Uririe, Orume Dominic",
        "supervisors": "Supervisors: Julien Barney and Kate Sugden",
        "date": "September 2026",
        "wordcount": f"{words:,} words (main text, excluding figure captions, "
                     f"references and appendices)",
    })

    render(doc, lines[1:])

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc.save(OUT)
    print(f"wrote {OUT}  ({OUT.stat().st_size/1024:.0f} KB)")
    print(f"title-page word count: {words:,}")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Crop the evidence screenshots down to their content.

Raw screen captures carry browser chrome, a bookmarks bar, the macOS menu bar
and the dock. None of that is evidence, and the bookmarks bar in particular
puts personal browsing into an academic submission. Each capture is cropped to
the region that actually shows something, then trimmed of any residual flat
border.

Originals are left untouched; output goes to evidence/prepared/.

    .venv/bin/python scripts/prepare_evidence.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageChops

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "evidence"
OUT = EV / "prepared"

# filename -> (left, top, right, bottom) in source pixels; None means full extent
CROPS = {
    # Chrome on macOS at 2940x1912: tab strip, omnibox and bookmarks bar occupy
    # the first ~310 px; a black letterbox closes the last ~30.
    "Screenshot 2026-08-10 at 03.04.16.png":      (0, 310, 2940, 1855),
    "Screenshot 2026-09-05 at 08.18.14.png":      (0, 310, 2940, 1855),
    "Screenshot 2026-09-05 at 08.29.53.png":      (0, 310, 2940, 1855),
    "Screenshot 2026-09-05 at 08.30.02.png":      (0, 310, 2940, 1855),
    "Screenshot 2026-09-08 at 12.20.40.png":      (0, 310, 2940, 1855),
    "Screenshot 2026-09-08 at 13.17.17.png":      (0, 310, 2940, 1855),
    # VS Code: menu bar off the top, dock and media widget off the bottom.
    "Screenshot 2026-08-31 at 19.39.54.png":      (0, 70, 2940, 1840),
    "Screenshot 2026-09-08 at 12.13.23.png":      (0, 70, 2940, 1780),
    "Screenshot 2026-09-08 at 13.48.17.png":      (0, 70, 2940, 1780),
    # Windows Edge: omnibox and bookmarks off the top, sidebar off the right.
    "GOV_SIGNAL_REALRUN.jpg":                      (0, 84, 1545, 448),
    # Artifact viewer: title strip off the top, sidebar off the right.
    "PHOTO-2026-09-08-13-15-30.jpg":               (0, 32, 1548, 407),
    # Already a bare table.
    "PHOTO-2026-09-07-19-53-41.jpg":               None,
    # The scope-drift pair: same project four minutes apart.
    "Screenshot 2026-09-08 at 18.41.59.png":      (0, 310, 2940, 1420),
    "Screenshot 2026-09-08 at 18.45.24.png":      (0, 310, 2940, 880),
    # The hosted report view: browser chrome off the top, dock off the bottom.
    "Screenshot 2026-09-09 at 00.45.06.png":      (0, 440, 2940, 1720),
    # Windows VS Code: title bar off the top, taskbar and status bar off the
    # bottom, activity rail off the left.
    "1fbed596-aa52-4d30-b890-3503b7d5b470 2.JPG": (60, 45, 1600, 915),
}

# Not evidence for this study.
EXCLUDE = {
    "Screenshot 2026-09-09 at 00.32.47.png": "Laravel Herd setup for an unrelated project",
    "Screenshot 2026-09-09 at 00.44.31.png": "superseded by the 00.46 capture",
    "Screenshot 2026-09-09 at 00.44.44.png": "superseded by the 00.46 capture",
    "Screenshot 2026-09-09 at 00.46.01.png": "superseded by the 00.46.29 capture",
    "MORE_Cover_Front_HiRes.png": "a book cover; unrelated to the study",
    "Screenshot 2026-08-31 at 19.39.54 copy.png": "byte-identical duplicate",
    "a162b5b3-daa6-405e-98ac-5b29d39c64ac 2.JPG": "duplicate of GOV_SIGNAL_REALRUN",
    # A private message thread. It carries a third party's photograph, contact
    # details and unrelated conversation, none of which belongs in a submitted
    # document. Kept on disk as provenance for the second rater's identity.
    "IMG_7746 2.PNG": "private correspondence containing a third party's personal data",
}


def content_box(im: Image.Image, tol: int = 14, pad: int = 26):
    """Bounding box of everything that is not flat background.

    A screenshot of a dashboard is mostly empty space below the content. Border
    trimming alone will not remove it, because the empty region is the same
    colour as the background and is contiguous with it. This measures each row
    and column against the modal background colour and keeps only the span that
    carries something.
    """
    import numpy as np

    a = np.asarray(im.convert("L"), dtype=np.int16)
    # modal background: the most common value in the outer frame
    frame = np.concatenate([a[0], a[-1], a[:, 0], a[:, -1]])
    bg = int(np.bincount(frame.clip(0, 255)).argmax())
    mask = np.abs(a - bg) > tol

    rows = np.flatnonzero(mask.any(axis=1))
    cols = np.flatnonzero(mask.any(axis=0))
    if rows.size == 0 or cols.size == 0:
        return None
    top, bottom = rows[0], rows[-1]
    left, right = cols[0], cols[-1]
    return (max(0, left - pad), max(0, top - pad),
            min(im.width, right + pad + 1), min(im.height, bottom + pad + 1))


def trim_to_content(im: Image.Image) -> Image.Image:
    box = content_box(im)
    return im.crop(box) if box else im


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.iterdir():
        old.unlink()

    done, skipped = 0, 0
    for p in sorted(EV.iterdir()):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        if p.name in EXCLUDE:
            print(f"  skip  {p.name}  ({EXCLUDE[p.name]})")
            skipped += 1
            continue
        with Image.open(p) as im:
            im = im.convert("RGB")
            before = im.size
            box = CROPS.get(p.name)
            if box:
                im = im.crop(box)
            im = trim_to_content(im)
            out = OUT / (p.stem + ".jpg")
            im.save(out, "JPEG", quality=90, optimize=True)
        pct = 100 * (1 - (im.size[0] * im.size[1]) / (before[0] * before[1]))
        print(f"  ok    {out.name:<44} {before[0]}x{before[1]} -> "
              f"{im.size[0]}x{im.size[1]}  ({pct:.0f}% removed)")
        done += 1
    print(f"\n{done} prepared, {skipped} excluded -> {OUT}")


if __name__ == "__main__":
    main()

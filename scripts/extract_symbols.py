#!/usr/bin/env python3
"""Extract the 21 election symbols from ELECTION LOGO.pdf into candidates/symbols/.

Each PDF page is a ballot card laid out as three horizontal bands:

    +--------------------------------+
    |        [ POST NAME pill ]      |  <- band 1  (black rounded rect)
    |                                |
    |            SYMBOL              |  <- band 2  (what we want)
    |                                |
    |        CANDIDATE NAME          |  <- band 3  (text)
    +--------------------------------+

The PDF's embedded images are sliced into horizontal JPEG strips by Word, so
pdfimages yields fragments rather than whole symbols. We render each page and
locate the bands from a row-darkness profile instead.

Usage:
    python3 scripts/extract_symbols.py            # extract all, write ballot.json
    python3 scripts/extract_symbols.py --debug    # also dump full page renders
"""

import argparse
import io
import json
import re
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
PDF = Path.home() / "Downloads" / "ELECTION LOGO.pdf"
OUT_DIR = ROOT / "candidates" / "symbols"
DEBUG_DIR = ROOT / "candidates" / "_debug"
BALLOT_JSON = ROOT / "ballot.json"

DPI = 300
# A row/column counts as "content" if this fraction of its pixels are dark.
# Low enough to catch thin line art (the pen, the scales), high enough to
# ignore the page's thin double border and JPEG speckle.
ROW_INK_THRESHOLD = 0.010
COL_INK_THRESHOLD = 0.004
DARK_CUTOFF = 200          # 0-255 grayscale; below this is "ink"
MIN_BAND_HEIGHT_FRAC = 0.02  # discard bands thinner than 2% of page height
PAD_FRAC = 0.04            # breathing room around the tight crop
# Tiles render around 300px, so 800px stays crisp on a hi-DPI touch screen while
# keeping all 21 symbols near 1MB total - it ships inside the .exe.
MAX_PX = 800

# The ballot. Candidate spelling follows LIST.pdf - the serial-numbered official
# nomination register - not ELECTION LOGO.pdf's decorative ballot card art, where
# three names differ (Harshavardhan has no initial there; Suharsha reads
# "Susharsha"; Kushi Patel reads "Kuyshi Patel"). Page numbers below still refer
# to ELECTION LOGO.pdf, which is what's rendered for symbol extraction.
# `symbol` is descriptive only - it documents what a human sees on that page so
# a mismatched crop is obvious during review.
BALLOT = [
    # page, post code,      post title,               candidate,          symbol
    (1,  "HEAD_BOY",  "HEAD BOY",               "Harshavardhan. A",  "light bulb"),
    (2,  "HEAD_BOY",  "HEAD BOY",               "Pruthvi Teja. S",   "torch"),
    (3,  "HEAD_BOY",  "HEAD BOY",               "Srivardhan. S",     "fountain pen"),
    (4,  "HEAD_BOY",  "HEAD BOY",               "Yashwanth. Ch",     "star"),
    (5,  "HEAD_GIRL", "HEAD GIRL",              "Akshara. K",        "candle"),
    (6,  "HEAD_GIRL", "HEAD GIRL",              "Nakshitha R.P",     "diya"),
    (7,  "HEAD_GIRL", "HEAD GIRL",              "Nirali. Ch",        "lantern"),
    (8,  "HEAD_GIRL", "HEAD GIRL",              "Suharsha. G",       "lighthouse"),
    (9,  "HEAD_GIRL", "HEAD GIRL",              "Thanmaie. B",       "table lamp and book"),
    (10, "SPORT",     "SPORT CAPTAIN",          "Kushi Patel. Ch",   "cricket bat"),
    (11, "SPORT",     "SPORT CAPTAIN",          "Satwik. K",         "carrom board"),
    (12, "SPORT",     "SPORT CAPTAIN",          "Vignesh. M",        "gold medal"),
    (13, "DISCIPLINE", "DISCIPLINE RIDER",      "Anmisha. S",        "wall clock"),
    (14, "DISCIPLINE", "DISCIPLINE RIDER",      "Karthik. S",        "weighing scales"),
    (15, "DISCIPLINE", "DISCIPLINE RIDER",      "Lasya. G",          "microphone"),
    (16, "DISCIPLINE", "DISCIPLINE RIDER",      "Lokesh. P",         "megaphone"),
    (17, "DISCIPLINE", "DISCIPLINE RIDER",      "Thanmai. S",        "whistle"),
    (18, "ART",       "ART & CULTURAL CAPTAIN", "Ananda Rupa. B",    "drum"),
    (19, "ART",       "ART & CULTURAL CAPTAIN", "Pooja. Ch",         "nadaswaram and dholak"),
    (20, "ART",       "ART & CULTURAL CAPTAIN", "Rishika Reddy. N",  "cymbals"),
    (21, "ART",       "ART & CULTURAL CAPTAIN", "Vaishali. A",       "veena"),
]

POST_ORDER = ["HEAD_BOY", "HEAD_GIRL", "SPORT", "DISCIPLINE", "ART"]


def slug(name):
    """AKSHARA. K -> akshara-k"""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower())
    return s.strip("-")


def render_page(page):
    """Render one PDF page to a full-colour PIL Image via poppler.

    Colour matters here: students recognise these symbols partly by colour (the
    yellow bulb, the gold medal, the red drum), so the ballot tiles must be in
    colour. Band analysis runs on a grayscale copy - see `ink_mask`.
    """
    proc = subprocess.run(
        ["pdftoppm", "-r", str(DPI), "-f", str(page), "-l", str(page),
         "-singlefile", "-png", "-"],
        input=PDF.read_bytes(), capture_output=True,
    )
    if proc.returncode != 0 or not proc.stdout:
        raise RuntimeError("pdftoppm failed on page %d: %s"
                           % (page, proc.stderr.decode()[:300]))
    return Image.open(io.BytesIO(proc.stdout)).convert("RGB")


def ink_mask(img):
    """Grayscale copy where ink is 255 and paper is 0, for band analysis."""
    return img.convert("L").point(lambda v: 255 if v < DARK_CUTOFF else 0)


def ink_bands(values, threshold, min_run):
    """Given per-row (or per-column) ink fractions, return [(start, end), ...]."""
    bands, start = [], None
    for i, frac in enumerate(values):
        if frac > threshold and start is None:
            start = i
        elif frac <= threshold and start is not None:
            if i - start >= min_run:
                bands.append((start, i))
            start = None
    if start is not None and len(values) - start >= min_run:
        bands.append((start, len(values)))
    return bands


def row_profile(mask):
    """Ink fraction per row. Box-averaging the mask down to 1px wide gives the
    per-row mean directly, which is far faster than a Python pixel loop."""
    w, h = mask.size
    return [v / 255.0 for v in mask.resize((1, h), Image.BOX).getdata()]


def col_profile(mask, y0, y1):
    """Ink fraction per column, restricted to rows y0..y1."""
    w, _ = mask.size
    band = mask.crop((0, y0, w, y1))
    return [v / 255.0 for v in band.resize((w, 1), Image.BOX).getdata()]


def find_symbol_box(mask):
    """Locate the symbol's bounding box in an ink mask. Returns (box, note)."""
    w, h = mask.size
    rows = row_profile(mask)
    bands = ink_bands(rows, ROW_INK_THRESHOLD, int(h * MIN_BAND_HEIGHT_FRAC))
    note = ""

    if len(bands) >= 3:
        # Normal case: pill, symbol, name. The symbol is the tallest band that
        # is not the first (pill) or last (name).
        middle = bands[1:-1]
        y0, y1 = max(middle, key=lambda b: b[1] - b[0])
    elif len(bands) == 2:
        # The name text touched the symbol and they merged into one band, or the
        # pill merged into the symbol. Take the tallest band and trim the bottom
        # sliver where the name sits.
        y0, y1 = max(bands, key=lambda b: b[1] - b[0])
        if y0 < h * 0.25:          # merged with the pill -> drop the pill
            y0 = bands[0][1] if bands[0][1] > y0 else y0
        y1 = int(y1 - (y1 - y0) * 0.16)
        note = "2 bands: trimmed name overlap"
    else:
        # Nothing usable - fall back to the layout's nominal symbol region.
        y0, y1 = int(h * 0.21), int(h * 0.76)
        note = "FALLBACK fractional crop - CHECK THIS ONE"

    cols = col_profile(mask, y0, y1)
    cbands = ink_bands(cols, COL_INK_THRESHOLD, int(w * 0.005))
    if cbands:
        x0, x1 = cbands[0][0], cbands[-1][1]
    else:
        x0, x1 = int(w * 0.1), int(w * 0.9)
        note = (note + "; no column ink").strip("; ")

    return (x0, y0, x1, y1), note


def to_square(img, pad_frac=PAD_FRAC):
    """Center the crop on a padded white square canvas, capped at MAX_PX.

    A square canvas means every ballot tile has identical geometry, so no
    candidate's symbol appears larger or better placed than another's.
    """
    w, h = img.size
    side = int(max(w, h) * (1 + pad_frac * 2))
    canvas = Image.new("RGB", (side, side), "white")
    canvas.paste(img, ((side - w) // 2, (side - h) // 2))
    if side > MAX_PX:
        canvas = canvas.resize((MAX_PX, MAX_PX), Image.LANCZOS)
    return canvas


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true",
                    help="also write full page renders with the crop box drawn")
    args = ap.parse_args()

    if not PDF.exists():
        sys.exit("Ballot PDF not found at %s" % PDF)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if args.debug:
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)

    posts = {code: {"code": code, "title": title, "candidates": []}
             for _, code, title, _, _ in BALLOT}

    print("Extracting %d symbols at %d DPI\n" % (len(BALLOT), DPI))
    warnings = []

    for page, code, title, candidate, symbol_desc in BALLOT:
        img = render_page(page)
        box, note = find_symbol_box(ink_mask(img))
        crop = img.crop(box)
        out_name = "%s.png" % slug(candidate)
        to_square(crop).save(OUT_DIR / out_name, optimize=True)

        posts[code]["candidates"].append({
            "name": candidate,
            "symbol": symbol_desc,
            "symbol_file": out_name,
            "ballot_order": len(posts[code]["candidates"]) + 1,
        })

        flag = "  <-- %s" % note if note else ""
        if note:
            warnings.append((page, candidate, note))
        print("  p%-2d  %-18s %-22s %4dx%-4d  %s%s"
              % (page, candidate, symbol_desc,
                 box[2] - box[0], box[3] - box[1], out_name, flag))

        if args.debug:
            dbg = img.copy()
            ImageDraw.Draw(dbg).rectangle(box, outline=(255, 0, 0), width=6)
            dbg.save(DEBUG_DIR / ("page%02d.png" % page))

    ballot = {
        "election": {
            "title": "Bhashyam High School Elections",
            "product": "C-LABS DIGITAL EVM",
            "marquee": "<<<< C-LABS DIGITAL EVM >>>>   <<<< Bhashyam High School Elections >>>>",
        },
        "posts": [posts[c] for c in POST_ORDER],
    }
    BALLOT_JSON.write_text(json.dumps(ballot, indent=2) + "\n")

    total = sum(len(p["candidates"]) for p in ballot["posts"])
    print("\nWrote %d symbols to %s" % (total, OUT_DIR.relative_to(ROOT)))
    print("Wrote roster to %s" % BALLOT_JSON.relative_to(ROOT))
    for code in POST_ORDER:
        print("   %-24s %d candidates" % (posts[code]["title"], len(posts[code]["candidates"])))

    if warnings:
        print("\n%d page(s) need a visual check:" % len(warnings))
        for page, candidate, note in warnings:
            print("   p%-2d %-18s %s" % (page, candidate, note))


if __name__ == "__main__":
    main()

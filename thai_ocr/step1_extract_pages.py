"""Step 1: turn a scanned PDF into one image per page, plus a cropped image of
just the handwriting.

Usage:
    python step1_extract_pages.py path/to/file.pdf

Why crop? Each scan is a whole A4 page, but the slip with the writing only
fills part of it. Sending Claude only the writing, enlarged, gives it more
detail per letter and improves accuracy.
"""

import argparse
from pathlib import Path

import numpy as np
import pypdfium2 as pdfium
from PIL import Image

from common import page_name, work_dir_for

RENDER_DPI = 200      # the scans were made at 200 dpi, so rendering higher adds nothing
INK_DARKNESS = 150    # 0 = black, 255 = white; pen strokes are darker than this
EDGE_TOP_BOTTOM = 0.02  # skip the top/bottom 2% of the page (some slips start very near the top)
EDGE_SIDES = 0.04       # skip the left/right 4% (scanner edge lines, staple marks)
CROP_PADDING = 50     # pixels of white space to keep around the writing
MAX_CROP_SIDE = 2000  # enlarge small crops up to this many pixels on the long side


def crop_to_handwriting(page: Image.Image) -> Image.Image:
    """Find the box that contains the dark pen strokes and cut it out."""
    gray = np.asarray(page.convert("L"))
    height, width = gray.shape
    ink = gray < INK_DARKNESS

    # Blank out the borders so scanner edges are not mistaken for writing.
    ey, ex = int(height * EDGE_TOP_BOTTOM), int(width * EDGE_SIDES)
    ink[:ey, :] = ink[-ey:, :] = False
    ink[:, :ex] = ink[:, -ex:] = False

    # Scanner edges and paper shadows show up as long straight lines. Handwriting
    # never fills a quarter of a whole column or row, so anything that does is a line.
    ink[:, ink.mean(axis=0) > 0.25] = False
    ink[ink.mean(axis=1) > 0.25, :] = False

    # A row/column only counts as "writing" if it has a few ink pixels,
    # so single specks of dust are ignored.
    rows = np.where(ink.sum(axis=1) > 3)[0]
    cols = np.where(ink.sum(axis=0) > 3)[0]
    if len(rows) == 0 or len(cols) == 0:
        return page  # blank page - keep it whole

    top = max(rows[0] - CROP_PADDING, 0)
    bottom = min(rows[-1] + CROP_PADDING, height)
    left = max(cols[0] - CROP_PADDING, 0)
    right = min(cols[-1] + CROP_PADDING, width)
    crop = page.crop((left, top, right, bottom))

    scale = MAX_CROP_SIDE / max(crop.size)
    if scale > 1:
        crop = crop.resize((round(crop.width * scale), round(crop.height * scale)), Image.LANCZOS)
    return crop


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("pdf", type=Path)
    args = parser.parse_args()

    doc_dir = work_dir_for(args.pdf.stem)
    (doc_dir / "pages").mkdir(parents=True, exist_ok=True)
    (doc_dir / "crops").mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(args.pdf))
    for index in range(len(pdf)):
        name = page_name(index + 1)
        page = pdf[index].render(scale=RENDER_DPI / 72).to_pil().convert("RGB")
        page.save(doc_dir / "pages" / f"{name}.jpg", quality=90)
        crop_to_handwriting(page).save(doc_dir / "crops" / f"{name}.jpg", quality=92)
        print(f"  {name}  done")

    print(f"\n{len(pdf)} pages saved in {doc_dir}")
    print("Next: open a few images in crops/ to check the cropping looks right,")
    print(f'then run:  python step2_transcribe.py "{args.pdf.stem}"')


if __name__ == "__main__":
    main()

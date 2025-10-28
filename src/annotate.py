"""
annotate.py
-----------
Build an annotated PDF from page PNG bytes:
  - red rectangles = blocks
  - optional thin gray rectangles = words (debug)
"""

from pathlib import Path
from typing import List, Dict, Any
from PIL import Image, ImageDraw
import io

def annotate_pages_to_pdf_from_bytes(
    page_png_bytes: List[bytes],      # list of page images as PNG-encoded bytes
    pages_words: List[Dict[str, Any]],# per-page dicts: {"page_num", "width", "height", "texts":[{text,bbox,...}]}
    pages_blocks: List[Dict[str, Any]],# per-page dicts: {"page_num", "blocks":[[text, bbox], ...]}
    out_pdf: Path,                    # where to write the final multi-page annotated PDF
    draw_words: bool = False,         # if True, draw light boxes for every word (debug)
):
    images = []                       # will collect PIL.Image objects for each page to later save as a PDF

    # Iterate pages in lockstep: same index across PNG bytes, words, and blocks
    for png, pw, pb in zip(page_png_bytes, pages_words, pages_blocks):
        # Decode PNG bytes -> RGB image (keeps everything in memory; no disk I/O)
        im = Image.open(io.BytesIO(png)).convert("RGB")

        # Create a drawing context to draw rectangles on top of the image
        dr = ImageDraw.Draw(im)

        # Draw larger merged "blocks" in red (thicker outline so they’re easy to see)
        for b in pb.get("blocks", []):
            # --- THIS IS THE FIX ---
            # BEFORE: x0, y0, x1, y1 = b["bbox"]
            # AFTER:  The bbox is now at index 1 of the list 'b'
            x0, y0, x1, y1 = b[1]      # b is a list like [text, [x0, y0, x1, y1]]
            dr.rectangle([x0, y0, x1, y1], outline="red", width=3)

        # Optionally draw individual word boxes (thin gray) for debugging granularity
        # This part does not need to change because the 'pages_words' data structure
        # still uses the original dictionary format.
        if draw_words:
            for w in pw.get("texts", []):
                x0, y0, x1, y1 = w["bbox"]
                dr.rectangle([x0, y0, x1, y1], outline=(180, 180, 180), width=1)

        # Keep the annotated page image for PDF assembly at the end
        images.append(im)

    # Ensure the output directory exists before saving the PDF
    out_pdf.parent.mkdir(parents=True, exist_ok=True)

    # Save a multi-page PDF: PIL requires saving the first page, then appending the rest
    if images:
        first, rest = images[0], images[1:]
        # resolution=300 hints a good default DPI for viewing/printing
        first.save(out_pdf.as_posix(), save_all=True, append_images=rest, resolution=300)
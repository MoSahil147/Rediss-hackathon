"""
pdf_utils.py
------------
Render PDF pages to **in-memory PNG bytes** (no disk I/O).
This allows us to pass images directly to OCR engines without
saving temporary files on disk (faster + cleaner).
"""

from pathlib import Path
from typing import List, Dict
import io
import fitz  # PyMuPDF
from PIL import Image


def pdf_to_png_bytes(pdf_path: Path, dpi: int = 200) -> List[Dict]:
    """
    Render a PDF into a list of pages, each page stored as a dict:
      [
        {"png": bytes, "width": int, "height": int},
        ...
      ]

    Parameters
    ----------
    pdf_path : Path
        Path to the PDF file.
    dpi : int, default=200
        Rendering resolution. Higher DPI → sharper text but larger images.

    Returns
    -------
    List[Dict]
        Each dict contains:
          - "png": PNG-encoded bytes of the rendered page
          - "width": pixel width of the page image
          - "height": pixel height of the page image
    """
    out: List[Dict] = []

    # Open the PDF document
    with fitz.open(pdf_path) as doc:
        # Scale factor: PyMuPDF works with 72 DPI base → adjust to requested DPI
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)

        # Iterate through each page in the PDF
        for page in doc:
            # Render page to a pixmap (raw pixel data, RGB)
            pix = page.get_pixmap(matrix=mat, alpha=False)

            # Convert pixmap to a PIL Image (RGB mode)
            im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)

            # Save PIL image into a BytesIO buffer as PNG (no disk I/O)
            bio = io.BytesIO()
            im.save(bio, format="PNG", optimize=True)

            # Append structured result
            out.append({
                "png": bio.getvalue(),   # raw PNG bytes
                "width": pix.width,      # pixel width
                "height": pix.height     # pixel height
            })

    return out
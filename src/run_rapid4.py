"""
run_rapid4.py
-------------
Refactored to be used as both a command-line script and an importable library.

The main function `run_ocr_pipeline` returns the path(s) to the output _blocks.json file(s).
"""

import json
import os
import time
from pathlib import Path
from typing import List, Dict, Any, Tuple, Union, Optional
from concurrent.futures import ProcessPoolExecutor, as_completed

from tqdm import tqdm
from src.pdf_utils import pdf_to_png_bytes
from src.ocr_rapid import init_rapidocr_once, decode_png_bytes_to_rgb, extract_words_from_rgb
from src.blocks import words_to_blocks, merge_key_value_blocks
from src.annotate import annotate_pages_to_pdf_from_bytes
from src.layout import words_to_paragraphs


# MODIFIED: Now returns a tuple (elapsed_time, blocks_json_path)
def process_pdf(
    pdf_path: Path,
    output_dir: Path,
    dpi: int,
    gap_x: float,
    gap_y: float,
    kv_gap_x: float,
    kv_gap_y: float,
    min_conf: Optional[float],
    draw_words: bool,
    annotate: bool,
) -> Tuple[float, Path]:
    """
    Processes a single PDF file and returns its processing time and output JSON path.
    """
    t0 = time.time()
    stem = pdf_path.stem
    out_root = output_dir / stem
    out_root.mkdir(parents=True, exist_ok=True)

    # 1) Render all pages
    pages = pdf_to_png_bytes(pdf_path, dpi=dpi)
    num_pages = len(pages)
    if num_pages == 0:
        # Return a dummy path if the PDF is empty
        return 0.0, out_root / f"{stem}_blocks.json"

    # 2) Set up and run parallel OCR
    TOTAL_ENGINES = 4
    engines_used = min(TOTAL_ENGINES, num_pages)
    engines_idle = TOTAL_ENGINES - engines_used
    engines = [ProcessPoolExecutor(max_workers=1, initializer=_engine_initializer) for _ in range(TOTAL_ENGINES)]
    futures = {}
    for i, p in enumerate(pages):
        eng_id = i % TOTAL_ENGINES
        fut = engines[eng_id].submit(_ocr_page_task, i, p["png"], min_conf)
        futures[fut] = (eng_id, i)

    results: Dict[int, Dict[str, Any]] = {}
    for fut in tqdm(as_completed(list(futures.keys())), total=len(futures), desc=f"OCR {stem} ({TOTAL_ENGINES} engines)"):
        _, page_idx = futures[fut]
        page_idx_ret, words = fut.result()
        w, h = pages[page_idx]["width"], pages[page_idx]["height"]
        results[page_idx_ret] = {"texts": words, "width": w, "height": h}
    
    for ex in engines:
        ex.shutdown(wait=True)

    # 3) Build ordered list of pages
    pages_json: List[Dict[str, Any]] = []
    for i in range(num_pages):
        pj = results.get(i, {"texts": [], "width": pages[i]["width"], "height": pages[i]["height"]})
        pages_json.append({"page_num": i + 1, "width": pj["width"], "height": pj["height"], "texts": pj["texts"]})

    # 4) Merge words to blocks (two-pass)
    pages_blocks: List[Dict[str, Any]] = []
    for p in pages_json:
        primitive_blocks = words_to_blocks(p["texts"], gap_x=gap_x, gap_y=gap_y)
        final_blocks = merge_key_value_blocks(primitive_blocks, kv_gap_x=kv_gap_x, kv_gap_y=kv_gap_y)
        pages_blocks.append({"page_num": p["page_num"], "blocks": final_blocks})

    # 5) Write outputs
    words_json = {"document": pdf_path.name, "dpi": dpi, "pages": pages_json}
    (out_root / f"{stem}_words.json").write_text(json.dumps(words_json, ensure_ascii=False, indent=2), encoding="utf-8")
    
    # Define the path for the blocks json
    blocks_json_path = out_root / f"{stem}_blocks.json"
    blocks_json = {"document": pdf_path.name, "dpi": dpi, "pages": pages_blocks}
    blocks_json_path.write_text(json.dumps(blocks_json, ensure_ascii=False, indent=2), encoding="utf-8")
    
    all_words = [w for p in pages_json for w in p["texts"]]
    paras = words_to_paragraphs(all_words)
    (out_root / f"{stem}_paragraphs.txt").write_text("\n\n".join(paras), encoding="utf-8")

    if annotate:
        page_png_bytes = [p["png"] for p in pages]
        annotate_pages_to_pdf_from_bytes(
            page_png_bytes, pages_json, pages_blocks, out_root / f"{stem}_annotated.pdf", draw_words=draw_words
        )

    # 6) Log timing
    elapsed = time.time() - t0
    msg = f"{stem}: {elapsed:.2f}s | pages={num_pages} | engines_total={TOTAL_ENGINES} used={engines_used} idle={engines_idle}"
    print("DONE", msg)
    (output_dir / "times.txt").parent.mkdir(parents=True, exist_ok=True)
    with open(output_dir / "times.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    
    # Return both the time and the path
    return elapsed, blocks_json_path

# Helper functions for the OCR workers (no changes here)
def _engine_initializer():
    os.environ["OMP_NUM_THREADS"] = "1"; os.environ["OPENBLAS_NUM_THREADS"] = "1"; os.environ["MKL_NUM_THREADS"] = "1"
    os.environ["VECLIB_MAXIMUM_THREADS"] = "1"; os.environ["NUMEXPR_NUM_THREADS"] = "1"
    init_rapidocr_once()

def _ocr_page_task(page_idx: int, png_bytes: bytes, min_conf: Optional[float]) -> Tuple[int, List[Dict[str, Any]]]:
    rgb = decode_png_bytes_to_rgb(png_bytes)
    words = extract_words_from_rgb(rgb)
    if min_conf is not None:
        words = [w for w in words if (w.get("confidence") is None or w["confidence"] >= min_conf)]
    return page_idx, words


# --- MODIFIED IMPORTABLE FUNCTION ---
# Now returns a Path for a single file, or a List[Path] for a folder.
def run_ocr_pipeline(
    input_path: Union[str, Path],
    output_dir: Union[str, Path],
    dpi: int = 200,
    gap_x: float = 30.0,
    gap_y: float = 20.0,
    kv_gap_x: float = 150.0,
    kv_gap_y: float = 40.0,
    min_conf: Optional[float] = None,
    draw_words: bool = False,
    annotate: bool = True,
) -> Optional[Union[Path, List[Path]]]:
    """
    High-level function to run the OCR pipeline.
    Returns the Path to the created _blocks.json file.
    If input is a directory, returns a List of Paths.
    """
    input_path = Path(input_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    total_time = 0.0
    return_value: Optional[Union[Path, List[Path]]] = None

    if input_path.is_file() and input_path.suffix.lower() == ".pdf":
        elapsed, json_path = process_pdf(
            input_path, output_dir, dpi, gap_x, gap_y, kv_gap_x, kv_gap_y, min_conf, draw_words, annotate
        )
        total_time += elapsed
        return_value = json_path
    elif input_path.is_dir():
        pdfs = sorted(input_path.glob("*.pdf"))
        if not pdfs:
            print(f"No PDFs found in {input_path}")
            return []  # Return empty list for an empty directory
        
        json_paths = []
        for pdf in pdfs:
            elapsed, json_path = process_pdf(
                pdf, output_dir, dpi, gap_x, gap_y, kv_gap_x, kv_gap_y, min_conf, draw_words, annotate
            )
            total_time += elapsed
            json_paths.append(json_path)
        return_value = json_paths
    else:
        raise ValueError("Input must be a PDF file or a folder containing PDFs")

    print(f"\nTotal processing time: {total_time:.2f}s")
    print(f"Timings log: {output_dir / 'times.txt'}")
    
    return return_value


# --- Main function for command-line use (no changes needed) ---
def main():
    import argparse
    ap = argparse.ArgumentParser(description="RapidOCR-only with exactly 4 engines (parallel, page_index%4 assignment)")
    ap.add_argument("--input", type=str, required=True, help="PDF file or folder")
    ap.add_argument("--output", type=str, required=True, help="Output directory")
    ap.add_argument("--dpi", type=int, default=200, help="Render DPI (higher = sharper but slower)")
    ap.add_argument("--gap-x", type=float, default=30.0, help="Horizontal merge gap (px) for words")
    ap.add_argument("--gap-y", type=float, default=20.0, help="Vertical merge gap (px) for lines")
    ap.add_argument("--kv-gap-x", type=float, default=150.0, help="Max horizontal gap for key-value merging")
    ap.add_argument("--kv-gap-y", type=float, default=40.0, help="Max vertical gap for label-value merging")
    ap.add_argument("--min-conf", type=float, default=None, help="Drop words below this confidence (None = keep all)")
    ap.add_argument("--draw-words", action="store_true", help="Draw thin gray word boxes on annotated PDF")
    ap.add_argument("--no-annotate", action="store_true", help="Skip annotated PDF for maximum speed")
    args = ap.parse_args()

    run_ocr_pipeline(
        input_path=args.input,
        output_dir=args.output,
        dpi=args.dpi,
        gap_x=args.gap_x,
        gap_y=args.gap_y,
        kv_gap_x=args.kv_gap_x,
        kv_gap_y=args.kv_gap_y,
        min_conf=args.min_conf,
        draw_words=args.draw_words,
        annotate=(not args.no_annotate),
    )


if __name__ == "__main__":
    main()
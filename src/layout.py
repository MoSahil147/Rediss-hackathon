"""
layout.py
---------
Fast paragraphing from word boxes (heuristics).
"""

from typing import List, Dict, Any
import statistics

# --- geometry helpers ---
def _y_mid(b): return (b[1] + b[3]) / 2.0    # vertical center of a box
def _h(b): return max(0.0, b[3] - b[1])      # height of a box

def _sort_words(words: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    # Sort primarily by vertical position (top-to-bottom), secondarily by x (left-to-right)
    return sorted(words, key=lambda t: (_y_mid(t["bbox"]), t["bbox"][0]))

def words_to_paragraphs(words: List[Dict[str, Any]]) -> List[str]:
    """
    Turn word-level OCR into paragraph strings.

    Input  items: {"text": str, "bbox": [x0,y0,x1,y1], ...}
    Output items: ["paragraph text 1", "paragraph text 2", ...]
    """
    if not words:
        return []

    # 1) Sort words top→bottom, left→right for stable grouping
    words = _sort_words(words)

    # 2) Derive tolerances from median word height (robust to outliers)
    heights = [_h(w["bbox"]) for w in words if w.get("bbox")]
    med_h = statistics.median(heights) if heights else 12.0
    line_tol = max(6.0, med_h * 0.6)   # y-gap threshold to consider words on the same line
    para_gap = max(12.0, med_h * 1.4)  # gap between line centers to start a new paragraph

    # 3) Group words into "lines" by vertical proximity
    lines = []
    cur = []
    last = None
    for w in words:
        y = _y_mid(w["bbox"])
        if last is None or abs(y - last) <= line_tol:
            cur.append(w)              # same line
        else:
            # y-jump → finalize previous line (sorted left→right), start a new one
            lines.append(sorted(cur, key=lambda t: t["bbox"][0]))
            cur = [w]
        last = y
    if cur:
        lines.append(sorted(cur, key=lambda t: t["bbox"][0]))

    # 4) Convert each line into a single string and keep its vertical center
    ls = []
    for ln in lines:
        if not ln:
            continue
        txt = " ".join(w["text"].strip() for w in ln if w.get("text"))
        ymid = sum(_y_mid(w["bbox"]) for w in ln) / len(ln)
        ls.append({"y_mid": ymid, "text": txt})

    # 5) Stitch lines into paragraphs using vertical gaps
    paras = []
    cp = []     # current paragraph lines
    last = None
    for l in ls:
        if last is None:
            cp.append(l["text"])       # start first paragraph
        else:
            # Big vertical gap → new paragraph; else keep appending
            if (l["y_mid"] - last) > para_gap:
                paras.append(" ".join(cp).strip())
                cp = [l["text"]]
            else:
                cp.append(l["text"])
        last = l["y_mid"]

    # flush last paragraph
    if cp:
        paras.append(" ".join(cp).strip())

    # return only non-empty paragraphs
    return [p for p in paras if p]
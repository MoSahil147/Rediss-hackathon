"""
blocks.py
---------
(Token-optimized version 3: list structure [text, bbox])
"""
from typing import List, Dict, Any, Union

Block = List[Union[str, List[int]]] # Define a type hint for our new structure [text, bbox]

# --- tiny geometry helpers ---
def _y_mid(b): return (b[1] + b[3]) / 2.0
def _h(b): return max(0, b[3] - b[1])
def _w(b): return max(0, b[2] - b[0])
def _ov1(a0,a1,b0,b1): return max(0, min(a1,b1) - max(a0,b0))
def _merge(b1,b2):
    return [int(min(b1[0],b2[0])), int(min(b1[1],b2[1])), int(max(b1[2],b2[2])), int(max(b1[3],b2[3]))]

def words_to_blocks(words: List[Dict[str, Any]], gap_x: float = 25.0, gap_y: float = 15.0) -> List[Block]:
    if not words: return []
    ws = sorted(words, key=lambda w: (_y_mid(w["bbox"]), w["bbox"][0]))
    heights = [_h(w["bbox"]) for w in ws if w.get("bbox")]
    avg_h = (sum(heights) / len(heights)) if heights else 12.0
    line_tol = max(6.0, avg_h * 0.6)
    lines, cur, last = [], [], None
    for w in ws:
        y = _y_mid(w["bbox"])
        if last is None or abs(y - last) <= line_tol: cur.append(w)
        else:
            lines.append(sorted(cur, key=lambda t: t["bbox"][0])); cur = [w]
        last = y
    if cur: lines.append(sorted(cur, key=lambda t: t["bbox"][0]))
    segs = []
    for ln in lines:
        if not ln: continue
        s: List[Block] = [[ln[0]["text"], [int(v) for v in ln[0]["bbox"]]]]
        for w in ln[1:]:
            p = s[-1]; hgap = w["bbox"][0] - p[1][2]; vov = _ov1(p[1][1], p[1][3], w["bbox"][1], w["bbox"][3])
            vmin = min(_h(p[1]), _h(w["bbox"])); vrat = (vov / vmin) if vmin > 0 else 0.0
            if hgap <= gap_x and vrat >= 0.5:
                p[0] = (p[0] + " " + w["text"]).strip(); p[1] = _merge(p[1], w["bbox"])
            else: s.append([w["text"], [int(v) for v in w["bbox"]]])
        segs.append(s)
    blocks: List[Block] = []
    for s in segs: blocks.extend(s)
    blocks.sort(key=lambda b: (_y_mid(b[1]), b[1][0]))
    merged: List[Block] = []
    for b in blocks:
        if not merged: merged.append(b); continue
        p = merged[-1]; vgap = b[1][1] - p[1][3]; xov = _ov1(p[1][0], p[1][2], b[1][0], b[1][2])
        minw = min(_w(p[1]), _w(b[1])); xrat = (xov / minw) if minw > 0 else 0.0
        if vgap <= gap_y and xrat >= 0.3:
            p[0] = (p[0] + " " + b[0]).strip(); p[1] = _merge(p[1], b[1])
        else: merged.append(b)
    return merged

def merge_key_value_blocks(blocks: List[Block], kv_gap_x: float = 150.0, kv_gap_y: float = 40.0) -> List[Block]:
    if not blocks: return []
    blocks.sort(key=lambda b: (b[1][1], b[1][0]))
    vert_merged: List[Block] = []
    skip_indices = set()
    for i in range(len(blocks)):
        if i in skip_indices: continue
        current_block = blocks[i]
        if i + 1 < len(blocks):
            next_block = blocks[i+1]; vgap = next_block[1][1] - current_block[1][3]; xov = _ov1(current_block[1][0], current_block[1][2], next_block[1][0], next_block[1][2])
            if vgap >= 0 and vgap < kv_gap_y and xov > 20 and len(current_block[0].split()) < 5:
                merged_text = (current_block[0] + ": " + next_block[0]).strip(); merged_bbox = _merge(current_block[1], next_block[1])
                vert_merged.append([merged_text, merged_bbox]); skip_indices.add(i + 1); continue
        vert_merged.append(current_block)
    vert_merged.sort(key=lambda b: (_y_mid(b[1]), b[1][0]))
    final_merged: List[Block] = []
    if not vert_merged: return []
    final_merged.append(vert_merged[0])
    for current_block in vert_merged[1:]:
        prev_block = final_merged[-1]; line_tol = max(10.0, _h(prev_block[1]) * 0.7)
        y_mid_prev = _y_mid(prev_block[1]); y_mid_curr = _y_mid(current_block[1]); hgap = current_block[1][0] - prev_block[1][2]
        if abs(y_mid_prev - y_mid_curr) < line_tol and hgap >= 0 and hgap < kv_gap_x:
            prev_block[0] = (prev_block[0] + " " + current_block[0]).strip(); prev_block[1] = _merge(prev_block[1], current_block[1])
        else: final_merged.append(current_block)
    return final_merged
"""Offline OCR engine.

* Bengali + English text  -> Tesseract (bundled, ben+eng)
* Math equations          -> pix2tex (LaTeX-OCR, optional, bundled weights)
* Graphs / charts / figs  -> detected with OpenCV and cropped to PNG
"""
from __future__ import annotations

import os
import re
import sys
from dataclasses import dataclass

import cv2
import numpy as np

BN_START, BN_END = 0x0980, 0x09FF
STRONG_MATH = set("=+×÷±∑∫√∞≤≥≠≈∂∆∈∉⊂⊃∪∩→⇒∀∃^_αβγδεθλμπσφωΩΔΣΠ−")


# --------------------------------------------------------------------------
# Paths / Tesseract setup
# --------------------------------------------------------------------------
def resource_path(*parts: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, *parts)


def setup_tesseract():
    import pytesseract

    exe_name = "tesseract.exe" if os.name == "nt" else "tesseract"
    bundled = resource_path("tesseract", exe_name)
    if os.path.exists(bundled):
        pytesseract.pytesseract.tesseract_cmd = bundled
        os.environ["TESSDATA_PREFIX"] = resource_path("tesseract", "tessdata")
    else:  # development mode: use an installed Tesseract
        default = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
        if os.name == "nt" and os.path.exists(default):
            pytesseract.pytesseract.tesseract_cmd = default
    return pytesseract


# --------------------------------------------------------------------------
# Data classes
# --------------------------------------------------------------------------
@dataclass
class Options:
    lang: str = "ben+eng"
    math_mode: str = "auto"      # off | auto | whole
    graphs: bool = True
    table_cover: float = 0.18    # regions with more text coverage = table/text, not a graph


@dataclass
class Line:
    key: tuple
    box: tuple          # x, y, w, h
    text: str
    conf: float


@dataclass
class Block:
    kind: str           # text | math | figure
    y: int
    text: str = ""
    latex: str = ""
    image_path: str = ""
    key: tuple = ()


# --------------------------------------------------------------------------
# Image helpers (unicode-safe paths for Bengali file names on Windows)
# --------------------------------------------------------------------------
def read_image(path: str) -> np.ndarray:
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("Cannot read image")
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    if img.shape[2] == 4:  # composite transparency on white
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        rgb = img[:, :, :3].astype(np.float32)
        return (rgb * alpha + 255 * (1 - alpha)).astype(np.uint8)
    return img


def save_png(path: str, img: np.ndarray) -> None:
    ok, buf = cv2.imencode(".png", img)
    if not ok:
        raise IOError("PNG encode failed")
    buf.tofile(path)


def _inside(cx, cy, box) -> bool:
    x, y, w, h = box
    return x <= cx <= x + w and y <= cy <= y + h


def _union(a, b):
    x1, y1 = min(a[0], b[0]), min(a[1], b[1])
    x2 = max(a[0] + a[2], b[0] + b[2])
    y2 = max(a[1] + a[3], b[1] + b[3])
    return (x1, y1, x2 - x1, y2 - y1)


def _intersects(a, b) -> bool:
    return not (a[0] + a[2] < b[0] or b[0] + b[2] < a[0] or
                a[1] + a[3] < b[1] or b[1] + b[3] < a[1])


def _merge_overlapping(boxes):
    boxes = list(boxes)
    changed = True
    while changed:
        changed = False
        out = []
        for b in boxes:
            for i, o in enumerate(out):
                if _intersects(b, o):
                    out[i] = _union(b, o)
                    changed = True
                    break
            else:
                out.append(b)
        boxes = out
    return boxes


# --------------------------------------------------------------------------
# Graph / figure detection
# --------------------------------------------------------------------------
def detect_figures(gray: np.ndarray, word_boxes, table_cover: float):
    """Find chart/graph/diagram regions: big structural ink (axes, bars,
    curves, wedges, borders) that is NOT text. Text labels near the structure
    (axis labels, legends, titles) are pulled into the region."""
    H, W = gray.shape
    dim = max(H, W)
    bw = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                               cv2.THRESH_BINARY_INV, 35, 12)
    mask = bw.copy()
    for x, y, w, h in word_boxes:
        cv2.rectangle(mask, (x, y), (x + w, y + h), 0, -1)

    n, labels, stats, _ = cv2.connectedComponentsWithStats(mask, connectivity=8)
    big = np.zeros_like(mask)
    min_side = 0.06 * dim
    for i in range(1, n):
        x, y, w, h, area = stats[i]
        if max(w, h) >= min_side and area >= 12:
            big[labels == i] = 255
    if not big.any():
        return []

    k = max(9, int(0.025 * dim))
    merged = cv2.dilate(big, cv2.getStructuringElement(cv2.MORPH_RECT, (k, k)))
    contours, _ = cv2.findContours(merged, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    regions = [cv2.boundingRect(c) for c in contours]

    margin = int(0.03 * dim)
    for _ in range(2):  # pull in nearby labels / legends / captions
        new = []
        for r in regions:
            ex = (r[0] - margin, r[1] - margin, r[2] + 2 * margin, r[3] + 2 * margin)
            u = r
            for wb in word_boxes:
                if _inside(wb[0] + wb[2] / 2, wb[1] + wb[3] / 2, ex):
                    u = _union(u, wb)
            new.append(u)
        regions = _merge_overlapping(new)

    figures = []
    for (x, y, w, h) in regions:
        if w < 0.08 * W or h < 0.06 * H or w * h < 0.012 * W * H:
            continue
        cover = sum(ww * hh for (wx, wy, ww, hh) in word_boxes
                    if _inside(wx + ww / 2, wy + hh / 2, (x, y, w, h))) / float(w * h)
        if cover > table_cover:      # text-heavy: a table or paragraph frame
            continue
        pad = 10
        x0, y0 = max(0, x - pad), max(0, y - pad)
        x1, y1 = min(W, x + w + pad), min(H, y + h + pad)
        figures.append((x0, y0, x1 - x0, y1 - y0))
    figures.sort(key=lambda b: (b[1], b[0]))
    return figures


# --------------------------------------------------------------------------
# Math-line heuristics
# --------------------------------------------------------------------------
def bengali_ratio(t: str) -> float:
    letters = [c for c in t if c.isalpha()]
    if not letters:
        return 0.0
    return sum(BN_START <= ord(c) <= BN_END for c in letters) / len(letters)


def is_math_line(text: str, conf: float) -> bool:
    t = text.strip()
    if len(t) < 3 or bengali_ratio(t) > 0.25:
        return False
    words = t.split()
    prose = [w for w in words if re.fullmatch(r"[A-Za-z]{4,}[.,:;]?", w)]
    if len(prose) >= 2:
        return False
    strong = sum(c in STRONG_MATH for c in t)
    if strong >= 2:
        return True
    if strong == 1 and not prose and len(words) <= 10:
        return True
    if conf < 50 and len(words) <= 8 and not prose and any(c.isdigit() for c in t):
        return True
    return False


def expand_math_boxes(math_lines, other_lines):
    """Grow each equation box to include small neighbouring fragments
    (fraction numerators/denominators, limits, super/subscripts)."""
    boxes = [tuple(l.box) for l in math_lines]
    consumed = {id(l) for l in math_lines}
    for _ in range(2):
        for i, b in enumerate(boxes):
            for l in other_lines:
                if id(l) in consumed or len(l.text) > 15 or bengali_ratio(l.text) > 0.25:
                    continue
                lx, ly, lw, lh = l.box
                x, y, w, h = b
                xo = min(x + w, lx + lw) - max(x, lx)
                gap = max(ly - (y + h), y - (ly + lh))
                if xo > 0.3 * min(w, lw) and gap < 0.6 * max(h, lh):
                    boxes[i] = _union(b, l.box)
                    consumed.add(id(l))
    boxes = _merge_overlapping(boxes)
    return boxes, consumed


# --------------------------------------------------------------------------
# Math OCR (pix2tex), loaded lazily
# --------------------------------------------------------------------------
class MathOCR:
    def __init__(self):
        self._model = None
        self._tried = False
        self.error = ""

    def available(self) -> bool:
        if not self._tried:
            self._tried = True
            try:
                from pix2tex.cli import LatexOCR
                self._model = LatexOCR()
            except Exception as e:  # not installed (lite build) or weights missing
                self.error = str(e)
        return self._model is not None

    def to_latex(self, bgr: np.ndarray) -> str:
        from PIL import Image
        bgr = cv2.copyMakeBorder(bgr, 12, 12, 12, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        pil = Image.fromarray(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        return self._model(pil).strip()


# --------------------------------------------------------------------------
# Main per-image pipeline
# --------------------------------------------------------------------------
def process_image(path: str, index: int, opts: Options, graph_dir: str,
                  math: MathOCR, log=lambda m: None):
    import pytesseract
    from pytesseract import Output

    img = read_image(path)
    h0, w0 = img.shape[:2]
    scale = 2.0 if max(h0, w0) < 1600 else 1.0
    if scale != 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    stem = re.sub(r'[\\/:*?"<>|]', "_", os.path.splitext(os.path.basename(path))[0])[:40]

    # ---- whole-image equation mode
    if opts.math_mode == "whole":
        if not math.available():
            raise RuntimeError("Math engine not available in this build: " + math.error)
        return [Block("math", 0, latex=math.to_latex(img))]

    # ---- text recognition
    d = pytesseract.image_to_data(gray, lang=opts.lang, config="--oem 1 --psm 3",
                                  output_type=Output.DICT)
    words, lines = [], {}
    for i in range(len(d["text"])):
        t = d["text"][i].strip()
        try:
            conf = float(d["conf"][i])
        except ValueError:
            conf = -1
        if not t or conf < 0:
            continue
        box = (d["left"][i], d["top"][i], d["width"][i], d["height"][i])
        words.append(box)
        key = (d["block_num"][i], d["par_num"][i], d["line_num"][i])
        if key in lines:
            ln = lines[key]
            ln.box = _union(ln.box, box)
            ln.text += " " + t
            ln.conf = (ln.conf + conf) / 2
        else:
            lines[key] = Line(key, box, t, conf)
    line_list = list(lines.values())

    blocks: list[Block] = []

    # ---- graphs / figures
    figs = []
    if opts.graphs:
        figs = detect_figures(gray, words, opts.table_cover)
        for n, (x, y, w, h) in enumerate(figs, 1):
            out = os.path.join(graph_dir, f"{index:03d}_{stem}_graph{n}.png")
            save_png(out, img[y:y + h, x:x + w])
            blocks.append(Block("figure", y, image_path=out))
        if figs:
            log(f"   {len(figs)} graph/figure region(s) saved")
        line_list = [l for l in line_list
                     if not any(_inside(l.box[0] + l.box[2] / 2, l.box[1] + l.box[3] / 2, f)
                                for f in figs)]

    # ---- equations
    consumed = set()
    if opts.math_mode == "auto" and math.available():
        cand = [l for l in line_list if is_math_line(l.text, l.conf)]
        if cand:
            boxes, consumed = expand_math_boxes(cand, line_list)
            for (x, y, w, h) in boxes:
                latex = ""
                try:
                    latex = math.to_latex(img[y:y + h, x:x + w])
                except Exception as e:
                    log(f"   math OCR failed on a region: {e}")
                if latex:
                    blocks.append(Block("math", y, latex=latex))
                else:  # fall back to plain OCR text of those lines
                    consumed -= {id(l) for l in line_list if _inside(
                        l.box[0] + l.box[2] / 2, l.box[1] + l.box[3] / 2, (x, y, w, h))}
            if blocks:
                log(f"   {sum(b.kind == 'math' for b in blocks)} equation(s) recognised")
    elif opts.math_mode == "auto" and not math.available():
        log("   (math engine not installed - equations stay as plain text)")

    # ---- assemble reading order
    text_lines = [l for l in line_list if id(l) not in consumed]
    items = [Block("text", l.box[1], text=l.text, key=l.key[:2]) for l in text_lines]
    if blocks:   # figures/equations present: order by vertical position
        items = sorted(items + blocks, key=lambda b: b.y)

    result: list[Block] = []
    for b in items:
        if (b.kind == "text" and result and result[-1].kind == "text"
                and result[-1].key == b.key):
            result[-1].text += " " + b.text
        else:
            result.append(b)
    return result

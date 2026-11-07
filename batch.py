"""Batch runner: up to 100 images -> .docx / .txt / .tex + graphs/*.png"""
from __future__ import annotations

import os
import time

from docwriter import DocBuilder
from ocr_engine import MathOCR, Options, process_image, setup_tesseract

MAX_IMAGES = 100


def run_batch(paths, out_root, opts: Options, want_docx=True, want_txt=True,
              progress=lambda i, n: None, log=lambda m: None, cancel=None):
    if len(paths) > MAX_IMAGES:
        raise ValueError(f"Maximum {MAX_IMAGES} images per batch")
    setup_tesseract()

    out_dir = os.path.join(out_root, "OCR_Output_" + time.strftime("%Y%m%d_%H%M%S"))
    graph_dir = os.path.join(out_dir, "graphs")
    os.makedirs(graph_dir, exist_ok=True)

    math = MathOCR()
    if opts.math_mode != "off":
        log("Loading math engine (first time can take ~10-30 s)...")
        if not math.available():
            log("Math engine unavailable: " + (math.error or "unknown reason"))

    doc = DocBuilder() if want_docx else None
    txt, tex = [], []
    failed = 0

    for i, path in enumerate(paths, 1):
        if cancel is not None and cancel.is_set():
            log("Cancelled.")
            break
        name = os.path.basename(path)
        log(f"[{i}/{len(paths)}] {name}")
        progress(i - 1, len(paths))
        try:
            blocks = process_image(path, i, opts, graph_dir, math, log)
        except Exception as e:
            failed += 1
            log(f"   ERROR: {e}")
            if doc:
                doc.start_image(i, name)
                doc.add_note(f"[Could not process this image: {e}]")
            continue

        if doc:
            doc.start_image(i, name)
        txt.append(f"===== Image {i}: {name} =====")
        for b in blocks:
            if b.kind == "text":
                txt.append(b.text)
                if doc:
                    doc.add_text(b.text)
            elif b.kind == "math":
                txt.append(f"$$ {b.latex} $$")
                tex.append(f"% image {i}\n\\[ {b.latex} \\]\n")
                if doc:
                    doc.add_equation(b.latex)
            elif b.kind == "figure":
                txt.append(f"[graph: graphs/{os.path.basename(b.image_path)}]")
                if doc:
                    doc.add_figure(b.image_path)
        txt.append("")
        progress(i, len(paths))

    if doc:
        doc.save(os.path.join(out_dir, "document.docx"))
    if want_txt:
        with open(os.path.join(out_dir, "text.txt"), "w", encoding="utf-8") as f:
            f.write("\n".join(txt))
    if tex:
        with open(os.path.join(out_dir, "equations.tex"), "w", encoding="utf-8") as f:
            f.write("\n".join(tex))
    log(f"Done. {len(paths) - failed} OK, {failed} failed.")
    return out_dir

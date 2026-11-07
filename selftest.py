"""Smoke test run by the build: OfflineOCR.exe --selftest  -> writes selftest.txt"""
import os
import sys
import traceback


def run():
    base = os.path.dirname(sys.executable) if getattr(sys, "frozen", False) else "."
    out = os.path.join(base, "selftest.txt")
    lines, ok = [], True
    try:
        from ocr_engine import MathOCR, setup_tesseract
        pt = setup_tesseract()
        langs = pt.get_languages(config="")
        lines.append("tesseract languages: " + ",".join(langs))
        if "ben" not in langs or "eng" not in langs:
            ok = False
            lines.append("MISSING ben/eng language data")
        import cv2
        import numpy as np
        m = MathOCR()
        if not m.available():
            ok = False
            lines.append("MATH ENGINE FAILED: " + m.error)
        else:
            img = np.full((80, 300, 3), 255, np.uint8)
            cv2.putText(img, "x^2+y^2=z^2", (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (0, 0, 0), 2)
            lines.append("math test result: " + m.to_latex(img))
    except Exception:
        ok = False
        lines.append(traceback.format_exc())
    lines.append("SELFTEST_OK" if ok else "SELFTEST_FAILED")
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    sys.exit(0 if ok else 1)

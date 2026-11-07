# Offline OCR (Bengali + English, equations, graphs)

Fully offline Windows desktop app. Add up to **100 images** → get:

| Output | What it contains |
|---|---|
| `document.docx` | Bengali/English text, **editable Word equations**, graphs embedded |
| `text.txt` | Plain text (equations as `$$ LaTeX $$`) |
| `equations.tex` | All equations as LaTeX |
| `graphs/*.png` | Every detected graph / chart / diagram, cropped as PNG |

## Get the .exe (two ways)

**A. Local Windows build**
1. Install Python 3.10 or 3.11 and Tesseract (UB Mannheim installer).
2. Double-click `build_exe.bat`.
3. Result: `dist\OfflineOCR\OfflineOCR.exe` (copy the whole `OfflineOCR` folder anywhere; no install, no internet).

**B. GitHub Actions (no setup on your PC)**
Push this folder to a GitHub repo → *Actions → Build Windows exe → Run workflow* → download `OfflineOCR-windows.zip`.

**Lite build** (small, ~150 MB, no equation support): delete the `pix2tex` line in `requirements.txt` and skip the torch install. The full build is ~1.5–2.5 GB because it bundles PyTorch and the math model.

## Run from source
```
pip install -r requirements.txt
python app.py
```
(needs Tesseract installed with `ben` and `eng` language data)

## How it works
- **Text**: Tesseract 5 (`ben+eng`, best-accuracy models, LSTM engine), bundled inside the exe.
- **Equations**: pix2tex (LaTeX-OCR) on lines/regions that look like math, converted to native Word equations (OMML).
- **Graphs**: OpenCV finds large non-text structure (axes, bars, curves, pie wedges, diagrams), pulls in nearby labels/legends, and saves the crop as PNG.

## Honest limitations
- Bengali OCR is good on clean printed text; handwriting, low-resolution photos and decorative fonts will have errors. Use sharp, well-lit images (≥150 DPI).
- Equation recognition is excellent on printed math but not 100% "exact"; it does **not** read handwritten math. Check the LaTeX in `equations.tex`. Use *"Whole image is ONE equation"* for cropped equation screenshots – that is the most accurate mode.
- Graphs are **cropped as images**, not converted into data. Tables are kept as text, not as graphs.
- Multi-column pages containing graphs/equations may come out in slightly wrong order.
- Auto-detection of equations is heuristic; stray text may occasionally be treated as math (or vice-versa).
- The Windows build could not be run in the environment where this code was written; the engine, figure detection and Word/equation export were tested on Linux. If PyInstaller reports a missing module on your first build, add it to `hiddenimports` in `OfflineOCR.spec`.
- `python tools/selftest.py` runs a quick sanity test of the graph detector and document builder.

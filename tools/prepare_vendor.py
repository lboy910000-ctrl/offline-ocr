import os, shutil, sys, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEST = os.path.join(ROOT, "vendor", "tesseract")
TESSDATA = os.path.join(DEST, "tessdata")
BASE = "https://github.com/tesseract-ocr/tessdata_best/raw/main/"


def find_tesseract_dir():
    env = os.environ.get("TESSERACT_DIR")
    cands = [env] if env else []
    cands += [r"C:\Program Files\Tesseract-OCR", r"C:\Program Files (x86)\Tesseract-OCR"]
    exe = shutil.which("tesseract")
    if exe:
        cands.append(os.path.dirname(exe))
    for c in cands:
        if c and os.path.exists(os.path.join(c, "tesseract.exe")):
            return c
    sys.exit("Tesseract not found.")


src = find_tesseract_dir()
print("Copying Tesseract from", src)
if os.path.exists(DEST):
    shutil.rmtree(DEST)
shutil.copytree(src, DEST, ignore=shutil.ignore_patterns("tessdata", "doc", "unins*"))
os.makedirs(TESSDATA, exist_ok=True)
for lang in ("eng", "ben", "osd"):
    print("Downloading", lang)
    urllib.request.urlretrieve(BASE + lang + ".traineddata",
                               os.path.join(TESSDATA, lang + ".traineddata"))

try:
    print("Fetching math model weights (pix2tex)...")
    from pix2tex.cli import LatexOCR
    LatexOCR()
    print("Math model ready.")
except Exception as e:
    print("Math engine not prepared:", e)

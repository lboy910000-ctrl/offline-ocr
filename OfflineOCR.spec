# PyInstaller spec - builds dist/OfflineOCR/OfflineOCR.exe (folder build, fast start-up)
import importlib.util
from PyInstaller.utils.hooks import collect_all

datas = [("vendor/tesseract", "tesseract")]
binaries, hiddenimports = [], []

for pkg in ("torchvision", "pix2tex", "x_transformers", "timm", "latex2mathml",
            "mathml2omml", "albumentations", "pytesseract"):
    if importlib.util.find_spec(pkg):
        d, b, h = collect_all(pkg)
        datas += d; binaries += b; hiddenimports += h

a = Analysis(["app.py"], pathex=["."], binaries=binaries, datas=datas,
             hiddenimports=hiddenimports, excludes=["matplotlib", "IPython"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="OfflineOCR",
          console=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, name="OfflineOCR")

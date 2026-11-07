"""Build the Word document (.docx) with Bengali/English text, native Word
equations (OMML) and embedded graph PNGs."""
from __future__ import annotations

from docx import Document
from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

M_NS = "http://schemas.openxmlformats.org/officeDocument/2006/math"
W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
LATIN_FONT = "Calibri"
BENGALI_FONT = "Nirmala UI"   # ships with Windows 8+


def _set_fonts(run, size=11):
    run.font.size = Pt(size)
    rPr = run._element.get_or_add_rPr()
    rf = rPr.find(qn("w:rFonts"))
    if rf is None:
        rf = OxmlElement("w:rFonts")
        rPr.insert(0, rf)
    rf.set(qn("w:ascii"), LATIN_FONT)
    rf.set(qn("w:hAnsi"), LATIN_FONT)
    rf.set(qn("w:cs"), BENGALI_FONT)       # complex-script font = Bengali
    rf.set(qn("w:eastAsia"), LATIN_FONT)
    sz = OxmlElement("w:szCs")
    sz.set(qn("w:val"), str(size * 2))
    rPr.append(sz)


def latex_to_omml(latex: str) -> str:
    import latex2mathml.converter
    import mathml2omml
    return mathml2omml.convert(latex2mathml.converter.convert(latex))


class DocBuilder:
    def __init__(self):
        self.doc = Document()
        sec = self.doc.sections[0]
        sec.left_margin = sec.right_margin = Inches(0.9)
        self.first = True

    def start_image(self, number: int, filename: str):
        if not self.first:
            self.doc.add_page_break()
        self.first = False
        p = self.doc.add_paragraph()
        r = p.add_run(f"Image {number}: {filename}")
        _set_fonts(r, 9)
        r.italic = True

    def add_text(self, text: str):
        p = self.doc.add_paragraph()
        _set_fonts(p.add_run(text), 11)

    def add_equation(self, latex: str):
        p = self.doc.add_paragraph()
        try:
            omml = latex_to_omml(latex)
            xml = (f'<m:oMathPara xmlns:m="{M_NS}" xmlns:w="{W_NS}">{omml}</m:oMathPara>')
            p._p.append(parse_xml(xml))
        except Exception:
            r = p.add_run(latex)          # fallback: raw LaTeX
            r.font.name = "Consolas"
            r.font.size = Pt(10)

    def add_figure(self, png_path: str):
        self.doc.add_picture(png_path, width=Inches(5.8))

    def add_note(self, text: str):
        r = self.doc.add_paragraph().add_run(text)
        _set_fonts(r, 9)

    def save(self, path: str):
        self.doc.save(path)

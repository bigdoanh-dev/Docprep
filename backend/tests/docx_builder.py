"""Build small .docx fixtures that mimic the structures found in the MOH guidelines."""

import io
import random

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH
from PIL import Image


def png_bytes(size: int) -> bytes:
    """Noise PNG; size=64 gives ~12 KB (a real figure), size=1 gives <100 B (a glyph)."""
    rnd = random.Random(size)
    img = Image.new("RGB", (size, size))
    img.putdata([(rnd.randrange(256), rnd.randrange(256), rnd.randrange(256))
                 for _ in range(size * size)])
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class DocBuilder:
    def __init__(self):
        self.doc = Document()

    def p(self, text: str = "", bold: bool = False, center: bool = False,
          style: str | None = None, bold_prefix: str | None = None):
        para = self.doc.add_paragraph(style=style)
        if bold_prefix:
            para.add_run(bold_prefix).bold = True
        if text:
            para.add_run(text).bold = bold or None
        if center:
            para.alignment = WD_ALIGN_PARAGRAPH.CENTER
        return self

    def caps(self, text: str):
        return self.p(text, bold=True, center=True)

    def h(self, text: str):
        return self.p(text, bold=True)

    def image(self, size: int = 64):
        self.doc.add_picture(io.BytesIO(png_bytes(size)))
        return self

    def picture(self, data: bytes):
        self.doc.add_picture(io.BytesIO(data))
        return self

    def table(self, rows: list[list[str]], hmerge: tuple[int, int, int] | None = None,
              vmerge: tuple[int, int, int] | None = None):
        """hmerge=(row, col_from, col_to); vmerge=(col, row_from, row_to)."""
        t = self.doc.add_table(rows=len(rows), cols=len(rows[0]))
        for r, row in enumerate(rows):
            for c, val in enumerate(row):
                t.cell(r, c).text = val
        if hmerge:
            r, a, b = hmerge
            t.cell(r, a).merge(t.cell(r, b)).text = rows[r][a]
        if vmerge:
            c, a, b = vmerge
            t.cell(a, c).merge(t.cell(b, c)).text = rows[a][c]
        return self

    def add_style(self, name: str):
        self.doc.styles.add_style(name, WD_STYLE_TYPE.PARAGRAPH)
        return self

    def save(self, path):
        self.doc.save(path)
        return path

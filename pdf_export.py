from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import cm

def markdown_to_pdf_bytes(md_text: str) -> bytes:
    """Minimal markdown-to-PDF: monospaced text with simple wrapping (MVP)."""
    from io import BytesIO
    import textwrap
    bio = BytesIO()
    c = canvas.Canvas(bio, pagesize=A4)
    width, height = A4
    left = 2*cm
    right = width - 2*cm
    top = height - 2*cm
    line_height = 12
    x = left
    y = top

    for raw_line in md_text.splitlines():
        line = raw_line.replace("\t", "    ")
        for wline in textwrap.wrap(line, width=95) or [""]:
            if y <= 2*cm:
                c.showPage()
                y = top
            c.setFont("Courier", 9)
            c.drawString(x, y, wline)
            y -= line_height
    c.showPage()
    c.save()
    bio.seek(0)
    return bio.read()

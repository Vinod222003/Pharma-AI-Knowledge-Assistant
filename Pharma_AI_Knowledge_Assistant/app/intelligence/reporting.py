"""In-memory, source-referenced PDF summary; avoids writing sensitive reports to disk."""
from io import BytesIO
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import simpleSplit
from reportlab.pdfgen import canvas


def build_report(title: str, question: str, answer: str, sources: list[dict]) -> bytes:
    stream = BytesIO()
    pdf = canvas.Canvas(stream, pagesize=A4)
    width, height = A4
    y = height - 55
    def write(text: str, size: int = 10):
        nonlocal y
        pdf.setFont('Helvetica', size)
        for line in str(text).splitlines() or ['']:
            for part in simpleSplit(line, 'Helvetica', size, width - 100) or ['']:
                if y < 65:
                    pdf.showPage()
                    y = height - 55
                    pdf.setFont('Helvetica', size)
                pdf.drawString(50, y, part)
                y -= size + 6
    write(title, 14)
    write('EDUCATIONAL PROTOTYPE — NOT VALIDATED FOR GMP OR REGULATORY DECISIONS', 8)
    y -= 12
    write('Question: ' + question)
    y -= 8
    write('Response:')
    write(answer)
    y -= 10
    write('Source references:')
    for src in sources:
        write(f"[{src.get('label','?')}] {src.get('filename','Unknown')} — page {src.get('page','?')}")
    if not sources:
        write('No supporting source supplied')
    pdf.save()
    return stream.getvalue()

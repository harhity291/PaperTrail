"""Build small real PDFs for tests, without any extra library."""


def _escape(text):
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def make_pdf(pages):
    """Return the bytes of a PDF with one page per string in `pages`.

    An empty string makes a page with no text (like a scanned page).
    Long text is wrapped onto several lines.
    """
    objects = []  # PDF objects, numbered from 1

    def add(body):
        objects.append(body)
        return len(objects)

    catalog = add(None)   # filled in once we know the pages object number
    pages_obj = add(None)
    font = add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    page_ids = []
    for text in pages:
        words, lines, line = text.split(), [], ""
        for word in words:
            if len(line) + len(word) + 1 > 90:
                lines.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            lines.append(line)

        ops = ["BT", "/F1 10 Tf", "12 TL", "40 800 Td"]
        for ln in lines:
            ops.append(f"({_escape(ln)}) Tj T*")
        ops.append("ET")
        stream = "\n".join(ops).encode("latin-1")
        content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
        page_ids.append(add(
            b"<< /Type /Page /Parent %d 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 %d 0 R >> >> /Contents %d 0 R >>" % (pages_obj, font, content)
        ))

    kids = " ".join(f"{p} 0 R" for p in page_ids).encode()
    objects[pages_obj - 1] = b"<< /Type /Pages /Kids [" + kids + b"] /Count %d >>" % len(page_ids)
    objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    for off in offsets:
        out += b"%010d 00000 n \n" % off
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, catalog, xref)
    return bytes(out)

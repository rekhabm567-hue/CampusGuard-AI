import pytest

from app.documents.chunker import DocumentChunker
from app.documents.extractor import extract_pdf_pages
from app.documents.loader import load_document


def make_pdf(path, page_texts):
    """Write a minimal valid PDF, one text line per page."""

    count = len(page_texts)
    kids = " ".join(f"{4 + 2 * i} 0 R" for i in range(count))

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {count} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    for i, text in enumerate(page_texts):
        content = f"BT /F1 12 Tf 72 720 Td ({text}) Tj ET".encode()
        objects.append(
            (
                "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {5 + 2 * i} 0 R "
                "/Resources << /Font << /F1 3 0 R >> >> >>"
            ).encode()
        )
        objects.append(
            b"<< /Length %d >>\nstream\n" % len(content)
            + content
            + b"\nendstream"
        )

    out = bytearray(b"%PDF-1.4\n")
    offsets = []

    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"

    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n".encode()
    out += b"0000000000 65535 f \n"

    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()

    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()

    path.write_bytes(bytes(out))


PAGE_ONE = "Attendance needs seventy five percent presence."
PAGE_THREE = "Library opens at nine in the morning daily."


def test_pdf_pages_keep_real_page_numbers(tmp_path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, [PAGE_ONE, "", PAGE_THREE])

    pages = extract_pdf_pages(pdf)

    assert [p["page"] for p in pages] == [1, 3]
    assert "seventy five" in pages[0]["text"]
    assert "Library" in pages[1]["text"]


def test_loader_returns_text_and_pages(tmp_path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, [PAGE_ONE, PAGE_THREE])

    document = load_document(pdf)

    assert document["file_type"] == ".pdf"
    assert len(document["pages"]) == 2
    assert "Library" in document["text"]


def test_scanned_pdf_gives_clear_error(tmp_path):
    pdf = tmp_path / "scan.pdf"
    make_pdf(pdf, ["", ""])

    with pytest.raises(ValueError, match="scanned"):
        load_document(pdf)


def test_chunks_get_page_numbers(tmp_path):
    pdf = tmp_path / "sample.pdf"
    make_pdf(pdf, [PAGE_ONE, "", PAGE_THREE])

    chunks = DocumentChunker(max_chunk_size=60, overlap=10).chunk_document(
        load_document(pdf)
    )

    assert [c["page"] for c in chunks] == [1, 3]
    assert "pages" not in chunks[0]


def test_ambiguous_page_is_none_not_guessed():
    sentence = "Same sentence repeated here for test."
    document = {
        "text": f"{sentence}\n\n{sentence}",
        "pages": [
            {"page": 1, "text": sentence},
            {"page": 2, "text": sentence},
        ],
    }

    chunks = DocumentChunker(max_chunk_size=40, overlap=5).chunk_document(
        document
    )

    assert len(chunks) == 2
    assert all(chunk["page"] is None for chunk in chunks)


def test_long_paragraph_is_split_with_overlap():
    text = " ".join(f"w{i:03d}" for i in range(100))

    chunks = DocumentChunker(max_chunk_size=100, overlap=20).chunk_document(
        text
    )

    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 100 for chunk in chunks)
    assert chunks[1]["text"].split()[0] in chunks[0]["text"].split()[-5:]


def test_invalid_overlap_rejected():
    with pytest.raises(ValueError):
        DocumentChunker(max_chunk_size=100, overlap=100)
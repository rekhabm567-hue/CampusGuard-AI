from pathlib import Path

from app.documents.extractor import extract_pdf_pages, extract_text


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


def validate_document(file_path):
    """Check that the file exists and uses a supported format."""

    path = Path(file_path)

    if not path.exists():
        raise FileNotFoundError(
            f"Document not found: {file_path}"
        )

    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Unsupported document type: {path.suffix}"
        )

    return True


def load_document(file_path):
    """Load a document and return its text.

    PDFs also return "pages": [{"page": n, "text": ...}]. Other
    formats have no reliable page numbers, so "pages" is empty.
    """

    validate_document(file_path)

    path = Path(file_path)

    if path.suffix.lower() == ".pdf":
        pages = extract_pdf_pages(path)
        text = "\n\n".join(page["text"] for page in pages)
    else:
        pages = []
        text = extract_text(path)

    if not text or not text.strip():
        if path.suffix.lower() == ".pdf":
            raise ValueError(
                f"No extractable text in {file_path}. It may be a "
                "scanned PDF; OCR is not enabled."
            )

        raise ValueError(
            f"No readable text found in: {file_path}"
        )

    return {
        "file_name": path.name,
        "file_path": str(path),
        "file_type": path.suffix.lower(),
        "text": text.strip(),
        "pages": pages,
    }
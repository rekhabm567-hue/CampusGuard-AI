from pathlib import Path

from pypdf import PdfReader
from pypdf.errors import PdfReadError
from docx import Document


def extract_pdf_pages(file_path):
    """Return [{"page": n, "text": ...}] with real 1-based page numbers.

    Pages without extractable text are skipped, but numbering is kept.
    Raises ValueError for encrypted or malformed PDFs.
    """

    try:
        reader = PdfReader(str(file_path))
    except PdfReadError as error:
        raise ValueError(f"Malformed PDF: {error}") from error

    if reader.is_encrypted:
        try:
            unlocked = reader.decrypt("")
        except Exception as error:
            raise ValueError(
                "PDF is encrypted and cannot be read."
            ) from error

        if not unlocked:
            raise ValueError("PDF is encrypted and cannot be read.")

    pages = []

    try:
        for number, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()

            if text:
                pages.append({"page": number, "text": text})
    except PdfReadError as error:
        raise ValueError(f"Malformed PDF: {error}") from error

    return pages


def extract_pdf_text(file_path):
    """Extract text from a PDF document (pages joined)."""

    return "\n\n".join(
        page["text"] for page in extract_pdf_pages(file_path)
    )


def extract_docx_text(file_path):
    """Extract text from a DOCX document."""

    document = Document(str(file_path))

    paragraphs = []

    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_txt_text(file_path):
    """Extract text from a plain text document."""

    return Path(file_path).read_text(
        encoding="utf-8"
    )


def extract_text(file_path):
    """Select the correct extractor based on file extension."""

    extension = Path(file_path).suffix.lower()

    if extension == ".pdf":
        return extract_pdf_text(file_path)

    if extension == ".docx":
        return extract_docx_text(file_path)

    if extension == ".txt":
        return extract_txt_text(file_path)

    raise ValueError(
        f"Unsupported document type: {extension}"
    )
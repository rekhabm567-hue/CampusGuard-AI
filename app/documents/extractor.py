from pathlib import Path

from pypdf import PdfReader
from docx import Document


def extract_pdf_text(file_path):
    """
    Extract text from a PDF document.
    """

    reader = PdfReader(str(file_path))

    pages = []

    for page in reader.pages:

        text = page.extract_text()

        if text:
            pages.append(text)

    return "\n\n".join(pages)


def extract_docx_text(file_path):
    """
    Extract text from a DOCX document.
    """

    document = Document(str(file_path))

    paragraphs = []

    for paragraph in document.paragraphs:

        text = paragraph.text.strip()

        if text:
            paragraphs.append(text)

    return "\n\n".join(paragraphs)


def extract_txt_text(file_path):
    """
    Extract text from a plain text document.
    """

    return Path(file_path).read_text(
        encoding="utf-8"
    )


def extract_text(file_path):
    """
    Automatically select the correct
    extractor based on file extension.
    """

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
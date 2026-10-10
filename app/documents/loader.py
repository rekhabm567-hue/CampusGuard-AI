from pathlib import Path

from app.documents.extractor import extract_text


SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".txt",
}


def validate_document(file_path):
    """
    Check whether the supplied file exists
    and uses a supported document format.
    """

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
    """
    Load a document and return its extracted text.
    """

    validate_document(file_path)

    path = Path(file_path)

    text = extract_text(path)

    if not text or not text.strip():
        raise ValueError(
            f"No readable text found in: {file_path}"
        )

    return {
        "file_name": path.name,
        "file_path": str(path),
        "file_type": path.suffix.lower(),
        "text": text.strip(),
    }
# ============================================================
# DOCUMENT REGISTRY
# LLM HALLUCINATION FIREWALL
# ============================================================

import json
from pathlib import Path


DOCUMENTS_DIRECTORY = Path("data") / "documents"
REGISTRY_FILE = DOCUMENTS_DIRECTORY / "document_registry.json"


def initialize_registry():

    DOCUMENTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True
    )

    if not REGISTRY_FILE.exists():

        REGISTRY_FILE.write_text(
            "[]",
            encoding="utf-8"
        )


def load_registry():

    initialize_registry()

    try:

        data = json.loads(
            REGISTRY_FILE.read_text(
                encoding="utf-8"
            )
        )

        if isinstance(data, list):
            return data

        return []

    except Exception:

        return []


def save_registry(documents):

    initialize_registry()

    REGISTRY_FILE.write_text(
        json.dumps(
            documents,
            indent=4
        ),
        encoding="utf-8"
    )


def add_document_metadata(metadata):

    documents = load_registry()

    file_path = metadata.get(
        "file_path"
    )

    documents = [
        document
        for document in documents
        if document.get("file_path") != file_path
    ]

    documents.append(metadata)

    save_registry(documents)


def get_document_metadata(file_path):

    documents = load_registry()

    for document in documents:

        if document.get("file_path") == file_path:

            return document

    return None


def get_all_documents():

    return load_registry()


def remove_document_metadata(file_path):

    documents = load_registry()

    documents = [
        document
        for document in documents
        if document.get("file_path") != file_path
    ]

    save_registry(documents)


def document_exists(file_path):

    return get_document_metadata(
        file_path
    ) is not None
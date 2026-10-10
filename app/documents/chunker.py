# ============================================================
# DOCUMENT CHUNKER
# LLM HALLUCINATION FIREWALL
# ============================================================

import re
from typing import Any, Dict, List, Optional


class DocumentChunker:

    def __init__(
        self,
        max_chunk_size: int = 1200,
        overlap: int = 100,
    ):
        if max_chunk_size <= 0:
            raise ValueError("max_chunk_size must be positive.")

        if overlap < 0 or overlap >= max_chunk_size:
            raise ValueError(
                "overlap must be >= 0 and smaller than max_chunk_size."
            )

        self.max_chunk_size = max_chunk_size
        self.overlap = overlap

    # ========================================================
    # NORMALIZE TEXT
    # ========================================================

    def _normalize_text(self, text: str) -> str:

        if not text:
            return ""

        text = str(text)

        text = text.replace("\r\n", "\n")
        text = text.replace("\r", "\n")

        text = re.sub(r"[ \t]+", " ", text)

        text = re.sub(r"\n{3,}", "\n\n", text)

        return text.strip()

    # ========================================================
    # HELPERS
    # ========================================================

    def _safe_file_name(self, metadata: Dict[str, Any]) -> str:

        file_name = str(metadata.get("file_name", "document"))

        return re.sub(r"[^a-zA-Z0-9_.-]+", "_", file_name)

    def _create_chunk(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_id: Optional[str] = None,
    ) -> Dict[str, Any]:

        clean_text = str(text).strip()

        chunk_metadata = dict(metadata or {})

        return {
            "chunk_id": chunk_id,
            "text": clean_text,
            "metadata": chunk_metadata,
            **chunk_metadata,
        }

    # ========================================================
    # SPLIT AN OVERSIZED PARAGRAPH (WITH OVERLAP)
    # ========================================================

    def _split_long_text(self, text: str) -> List[str]:
        """Split text into pieces of at most max_chunk_size characters,
        breaking at whitespace, each piece overlapping the previous
        one by about `overlap` characters."""

        size = self.max_chunk_size

        if len(text) <= size:
            return [text]

        pieces = []
        start = 0
        length = len(text)

        while start < length:

            end = min(start + size, length)

            if end < length:

                cut = max(
                    text.rfind(" ", start, end),
                    text.rfind("\n", start, end),
                )

                if cut > start:
                    end = cut

            piece = text[start:end].strip()

            if piece:
                pieces.append(piece)

            if end >= length:
                break

            next_start = end - self.overlap

            if self.overlap > 0:

                boundary = text.find(" ", next_start, end)

                if boundary != -1:
                    next_start = boundary + 1

            if next_start <= start:
                next_start = end

            start = next_start

        return pieces

    # ========================================================
    # NUMBER LINE CHECK
    # ========================================================

    def _is_number_line(self, line: str) -> bool:

        return bool(
            re.fullmatch(
                r"\d+",
                str(line).strip(),
            )
        )

    # ========================================================
    # FIND RULE POSITIONS
    # ========================================================

    def _find_rule_positions(self, lines: List[str]) -> List[int]:

        positions = []

        for index, line in enumerate(lines):

            if self._is_number_line(line):

                number = int(line.strip())

                if 1 <= number <= 999:
                    positions.append(index)

        return positions

    # ========================================================
    # PARSE NUMBERED RULES
    # ========================================================

    def _chunk_numbered_rules(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        normalized_text = self._normalize_text(text)

        if not normalized_text:
            return []

        lines = [
            line.strip()
            for line in normalized_text.split("\n")
            if line.strip()
        ]

        rule_positions = self._find_rule_positions(lines)

        if not rule_positions:
            return []

        chunks = []

        for position_index, start_index in enumerate(rule_positions):

            rule_number = lines[start_index].strip()

            if position_index + 1 < len(rule_positions):
                end_index = rule_positions[position_index + 1]
            else:
                end_index = len(lines)

            # Need at least: number, title, description.
            if start_index + 1 >= end_index:
                continue

            rule_title = lines[start_index + 1].strip()

            description_lines = []

            for line_index in range(start_index + 2, end_index):

                line = lines[line_index].strip()

                if line:
                    description_lines.append(line)

            description = " ".join(description_lines).strip()

            if not rule_title or not description:
                continue

            description = re.sub(
                r"\s*Testing Note:.*$",
                "",
                description,
                flags=re.IGNORECASE,
            ).strip()

            if not description:
                continue

            rule_text = f"{rule_title} — {description}"

            chunk_metadata = dict(metadata or {})

            chunk_metadata.update(
                {
                    "rule_number": rule_number,
                    "section": rule_title,
                    "chunk_type": "rule",
                }
            )

            chunk_id = (
                f"{self._safe_file_name(chunk_metadata)}"
                f"_rule_{rule_number}"
            )

            chunks.append(
                self._create_chunk(
                    rule_text,
                    chunk_metadata,
                    chunk_id,
                )
            )

        return chunks

    # ========================================================
    # NORMAL DOCUMENT CHUNKING
    # ========================================================

    def _chunk_normal_document(
        self,
        text: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        normalized_text = self._normalize_text(text)

        if not normalized_text:
            return []

        paragraphs = []

        for paragraph in re.split(r"\n\s*\n", normalized_text):

            paragraph = paragraph.strip()

            if paragraph:
                paragraphs.extend(self._split_long_text(paragraph))

        chunks = []
        current_text = ""
        chunk_number = 1

        def flush():
            nonlocal chunk_number

            chunk_metadata = dict(metadata or {})

            chunk_metadata.update(
                {
                    "chunk_type": "section",
                    "chunk_number": chunk_number,
                }
            )

            chunk_id = (
                f"{self._safe_file_name(chunk_metadata)}"
                f"_chunk_{chunk_number}"
            )

            chunks.append(
                self._create_chunk(
                    current_text,
                    chunk_metadata,
                    chunk_id,
                )
            )

            chunk_number += 1

        for paragraph in paragraphs:

            proposed_text = (
                f"{current_text}\n\n{paragraph}"
                if current_text
                else paragraph
            )

            if len(proposed_text) <= self.max_chunk_size:
                current_text = proposed_text
            else:
                if current_text:
                    flush()

                current_text = paragraph

        if current_text:
            flush()

        return chunks

    # ========================================================
    # PAGE ASSIGNMENT
    # ========================================================

    @staticmethod
    def _squash(text: str) -> str:

        return re.sub(r"\s+", " ", str(text)).strip().lower()

    def _page_snippet(self, chunk: Dict[str, Any]) -> str:

        text = chunk.get("text", "")

        if chunk.get("chunk_type") == "rule":
            text = text.split(" — ", 1)[-1]
            return self._squash(text)[:60]

        return self._squash(text)[:80]

    def _assign_pages(
        self,
        chunks: List[Dict[str, Any]],
        pages: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        """Set chunk["page"] to the page where the chunk starts.

        The page is set only if the chunk's opening text appears on
        exactly one page. Otherwise it is None (never guessed).
        """

        if not pages:
            return chunks

        squashed_pages = [
            (page.get("page"), self._squash(page.get("text", "")))
            for page in pages
        ]

        for chunk in chunks:

            snippet = self._page_snippet(chunk)

            matches = [
                number
                for number, page_text in squashed_pages
                if snippet and snippet in page_text
            ]

            page = matches[0] if len(matches) == 1 else None

            chunk["page"] = page
            chunk.setdefault("metadata", {})["page"] = page

        return chunks

    # ========================================================
    # MAIN CHUNKING METHOD
    # ========================================================

    def chunk_document(
        self,
        document,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        pages = []

        if isinstance(document, dict):

            text = document.get("text", "")

            document_metadata = dict(document)

            document_metadata.pop("text", None)

            pages = document_metadata.pop("pages", None) or []

            if metadata:
                document_metadata.update(metadata)

            metadata = document_metadata

        else:

            text = str(document or "")

            metadata = dict(metadata or {})

        normalized_text = self._normalize_text(text)

        if not normalized_text:
            return []

        lines = [
            line.strip()
            for line in normalized_text.split("\n")
            if line.strip()
        ]

        chunks = None

        # Numbered-rule documents need at least two numbered sections.
        if len(self._find_rule_positions(lines)) >= 2:

            rule_chunks = self._chunk_numbered_rules(
                normalized_text,
                metadata,
            )

            if rule_chunks:
                chunks = rule_chunks

        if chunks is None:
            chunks = self._chunk_normal_document(
                normalized_text,
                metadata,
            )

        return self._assign_pages(chunks, pages)


# ============================================================
# COMPATIBILITY FUNCTIONS
# ============================================================

def chunk_text(
    text: str,
    chunk_size: int = 1200,
    overlap: int = 100,
) -> List[str]:

    chunker = DocumentChunker(
        max_chunk_size=chunk_size,
        overlap=overlap,
    )

    return [
        chunk["text"]
        for chunk in chunker.chunk_document(text)
    ]


def create_document_chunks(
    document,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:

    return DocumentChunker().chunk_document(
        document,
        metadata,
    )
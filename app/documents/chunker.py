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

        text = re.sub(
            r"[ \t]+",
            " ",
            text,
        )

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text,
        )

        return text.strip()

    # ========================================================
    # CREATE CHUNK
    # ========================================================

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
    # NUMBER LINE CHECK
    # ========================================================

    def _is_number_line(
        self,
        line: str,
    ) -> bool:

        return bool(
            re.fullmatch(
                r"\d+",
                str(line).strip(),
            )
        )

    # ========================================================
    # FIND RULE POSITIONS
    # ========================================================

    def _find_rule_positions(
        self,
        lines: List[str],
    ) -> List[int]:

        positions = []

        for index, line in enumerate(lines):

            if self._is_number_line(line):

                number = int(line.strip())

                # Employee/sample rule documents normally
                # contain sequential numbers.
                #
                # We accept 1..10 and similar numbered rules.
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

            # ------------------------------------------------
            # Rule number
            # ------------------------------------------------

            rule_number = lines[start_index].strip()

            # ------------------------------------------------
            # End of current rule
            # ------------------------------------------------

            if position_index + 1 < len(rule_positions):

                end_index = rule_positions[position_index + 1]

            else:

                end_index = len(lines)

            # ------------------------------------------------
            # Need at least:
            #
            # number
            # title
            # description
            # ------------------------------------------------

            if start_index + 1 >= end_index:

                continue

            rule_title = lines[start_index + 1].strip()

            description_lines = []

            for line_index in range(
                start_index + 2,
                end_index,
            ):

                line = lines[line_index].strip()

                if not line:
                    continue

                description_lines.append(line)

            description = " ".join(
                description_lines
            ).strip()

            if not rule_title:
                continue

            if not description:
                continue

            # ------------------------------------------------
            # Remove testing note from final rule if present
            # ------------------------------------------------

            description = re.sub(
                r"\s*Testing Note:.*$",
                "",
                description,
                flags=re.IGNORECASE,
            ).strip()

            if not description:
                continue

            # ------------------------------------------------
            # Create clean rule text
            # ------------------------------------------------

            rule_text = (
                f"{rule_title} — {description}"
            )

            chunk_metadata = dict(
                metadata or {}
            )

            chunk_metadata.update(
                {
                    "rule_number": rule_number,
                    "section": rule_title,
                    "chunk_type": "rule",
                }
            )

            file_name = str(
                chunk_metadata.get(
                    "file_name",
                    "document",
                )
            )

            safe_file_name = re.sub(
                r"[^a-zA-Z0-9_.-]+",
                "_",
                file_name,
            )

            chunk_id = (
                f"{safe_file_name}"
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

        paragraphs = [
            paragraph.strip()
            for paragraph in re.split(
                r"\n\s*\n",
                normalized_text,
            )
            if paragraph.strip()
        ]

        chunks = []

        current_text = ""

        chunk_number = 1

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

                    chunk_metadata = dict(
                        metadata or {}
                    )

                    chunk_metadata.update(
                        {
                            "chunk_type": "section",
                            "chunk_number": chunk_number,
                        }
                    )

                    file_name = str(
                        chunk_metadata.get(
                            "file_name",
                            "document",
                        )
                    )

                    safe_file_name = re.sub(
                        r"[^a-zA-Z0-9_.-]+",
                        "_",
                        file_name,
                    )

                    chunk_id = (
                        f"{safe_file_name}"
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

                current_text = paragraph

        if current_text:

            chunk_metadata = dict(
                metadata or {}
            )

            chunk_metadata.update(
                {
                    "chunk_type": "section",
                    "chunk_number": chunk_number,
                }
            )

            file_name = str(
                chunk_metadata.get(
                    "file_name",
                    "document",
                )
            )

            safe_file_name = re.sub(
                r"[^a-zA-Z0-9_.-]+",
                "_",
                file_name,
            )

            chunk_id = (
                f"{safe_file_name}"
                f"_chunk_{chunk_number}"
            )

            chunks.append(
                self._create_chunk(
                    current_text,
                    chunk_metadata,
                    chunk_id,
                )
            )

        return chunks

    # ========================================================
    # MAIN CHUNKING METHOD
    # ========================================================

    def chunk_document(
        self,
        document,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:

        # ----------------------------------------------------
        # Dictionary document
        # ----------------------------------------------------

        if isinstance(document, dict):

            text = document.get(
                "text",
                "",
            )

            document_metadata = dict(
                document
            )

            document_metadata.pop(
                "text",
                None,
            )

            if metadata:

                document_metadata.update(
                    metadata
                )

            metadata = document_metadata

        # ----------------------------------------------------
        # Plain text document
        # ----------------------------------------------------

        else:

            text = str(
                document or ""
            )

            metadata = dict(
                metadata or {}
            )

        normalized_text = self._normalize_text(
            text
        )

        if not normalized_text:
            return []

        lines = [
            line.strip()
            for line in normalized_text.split("\n")
            if line.strip()
        ]

        # ----------------------------------------------------
        # Detect numbered-rule document
        # ----------------------------------------------------

        rule_positions = self._find_rule_positions(
            lines
        )

        # Require at least two numbered sections.
        # This prevents ordinary documents containing
        # one number from being treated as rule documents.
        if len(rule_positions) >= 2:

            rule_chunks = (
                self._chunk_numbered_rules(
                    normalized_text,
                    metadata,
                )
            )

            if rule_chunks:

                return rule_chunks

        # ----------------------------------------------------
        # Normal document
        # ----------------------------------------------------

        return self._chunk_normal_document(
            normalized_text,
            metadata,
        )


# ============================================================
# COMPATIBILITY FUNCTION
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

    chunks = chunker.chunk_document(
        text
    )

    return [
        chunk["text"]
        for chunk in chunks
    ]


# ============================================================
# PROJECT COMPATIBILITY FUNCTION
# ============================================================

def create_document_chunks(
    document,
    metadata: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:

    chunker = DocumentChunker()

    return chunker.chunk_document(
        document,
        metadata,
    )
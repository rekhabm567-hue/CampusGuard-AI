# ============================================================
# CITATION VALIDATOR
# LLM HALLUCINATION FIREWALL
#
# Checks that every [n] in an answer refers to evidence that was
# actually supplied (1-based, in usable_evidence() order).
# It never creates or repairs citations.
# ============================================================

import re

_BRACKET = re.compile(r"\[([^\[\]]{1,40})\]")
_PART = re.compile(r"^\s*(\d+)\s*(?:[-\u2013]\s*(\d+))?\s*$")

_NO_CITATION_NEEDED = re.compile(
    r"^(?:i\s+could\s+not|i\s+cannot|i\s+can\s*not|i\s+can[\u2019']t|"
    r"the\s+(?:available\s+)?documents?\s+do(?:es)?\s+not|"
    r"conflicting\s+information)",
    re.IGNORECASE,
)


def _numbers_in(bracket_text):
    """Numbers in '1', '1, 3', '1-3'. Returns None if not a citation."""

    numbers = []

    for part in bracket_text.split(","):
        match = _PART.match(part)

        if not match:
            return None

        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else start

        if end < start or end - start > 20:
            return None

        numbers.extend(range(start, end + 1))

    return numbers


def extract_citations(text):
    """All citation numbers in order of appearance (with repeats)."""

    found = []

    for match in _BRACKET.finditer(str(text or "")):
        numbers = _numbers_in(match.group(1))

        if numbers:
            found.extend(numbers)

    return found


def _sentences(text):
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
        if s.strip()
    ]


def validate_citations(answer, evidence_documents):
    """Validate [n] citations against the evidence list.

    evidence_documents must be the same ordered list the prompt used
    (PromptBuilder.usable_evidence).
    """

    evidence = list(evidence_documents or [])
    count = len(evidence)

    cited = extract_citations(answer)

    valid = sorted({n for n in cited if 1 <= n <= count})
    invalid = sorted({n for n in cited if n < 1 or n > count})

    uncited = []

    for sentence in _sentences(answer):
        if extract_citations(sentence):
            continue

        if _NO_CITATION_NEEDED.match(sentence):
            continue

        # Ignore fragments with no real words (bullets, headings).
        if len(re.findall(r"[A-Za-z]{3,}", sentence)) < 3:
            continue

        uncited.append(sentence)

    cited_documents = []

    for number in valid:
        document = evidence[number - 1]
        cited_documents.append(
            {
                "citation": number,
                "chunk_id": document.get("chunk_id"),
                "title": document.get("title") or document.get("file_name"),
                "file_path": document.get("file_path"),
                "page": document.get("page"),
                "version": document.get("version"),
            }
        )

    return {
        "citation_count": len(cited),
        "valid": valid,
        "invalid": invalid,
        "uncited_sentences": uncited,
        "cited_documents": cited_documents,
        "ok": bool(valid) and not invalid and not uncited,
    }
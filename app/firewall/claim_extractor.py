# ============================================================
# CLAIM EXTRACTOR
# LLM HALLUCINATION FIREWALL
#
# Splits an answer into verifiable claims. Header lines (ending
# with a colon), bare bullet markers and fragments are not claims.
# No split after common abbreviations or numbering such as "4.1".
# Meta lead-ins such as "According to the evidence," are removed
# because they are not part of the claim itself.
# ============================================================

import re

_BULLET = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s*")

_LEAD_IN = re.compile(
    r"^\s*(?:"
    r"according\s+to\s+(?:the\s+)?(?:authorized\s+|provided\s+)?"
    r"(?:evidence|documents?|sources?|context|policy|text)"
    r"(?:\s*\[\d+\])?"
    r"|based\s+on\s+(?:the\s+)?(?:authorized\s+|provided\s+)?"
    r"(?:evidence|documents?|sources?|context|text)"
    r"|the\s+(?:evidence|documents?|sources?)\s+"
    r"(?:states?|says?|indicates?|shows?)\s+that"
    r")\s*[,:]?\s*",
    re.IGNORECASE,
)

_ABBREVIATIONS = (
    "ch", "e.g", "i.e", "etc", "vs", "no", "fig", "eq", "dr", "mr",
    "mrs", "ms", "prof", "sec", "approx", "cf", "al",
)

_PROTECT = "\u0001"


def _split_sentences(line):
    """Split on . ! ? followed by space, except after abbreviations
    or a bare number."""

    protected = line

    for abbr in _ABBREVIATIONS:
        protected = re.sub(
            rf"(?i)\b({re.escape(abbr)})\.(\s)",
            rf"\1{_PROTECT}\2",
            protected,
        )

    protected = re.sub(r"(\d)\.(\s)", rf"\1{_PROTECT}\2", protected)

    parts = re.split(r"(?<=[.!?])\s+", protected)

    return [part.replace(_PROTECT, ".") for part in parts]


def strip_lead_in(sentence):
    """Remove a meta lead-in and re-capitalise the first letter."""

    stripped = _LEAD_IN.sub("", sentence, count=1).strip()

    if stripped and stripped != sentence.strip():
        return stripped[0].upper() + stripped[1:]

    return sentence.strip()


class ClaimExtractor:

    def __init__(self):
        pass

    def extract(self, answer):

        if not answer or not answer.strip():
            return []

        text = re.sub(
            r"\b(No|Yes)\.\s+",
            r"\1 ",
            answer.strip(),
            flags=re.IGNORECASE,
        )

        claims = []

        for line in re.split(r"\n+", text):

            line = _BULLET.sub("", line).strip()

            if not line:
                continue

            for sentence in _split_sentences(line):

                sentence = _BULLET.sub("", sentence).strip()

                if not sentence:
                    continue

                if sentence.endswith(":"):
                    continue

                sentence = strip_lead_in(sentence)

                if len(re.findall(r"[A-Za-z]{2,}", sentence)) < 2:
                    continue

                claims.append(sentence)

        return claims


def create_claim_extractor():

    return ClaimExtractor()
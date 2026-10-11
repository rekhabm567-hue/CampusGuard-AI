# ============================================================
# CLAIM EXTRACTOR
# LLM HALLUCINATION FIREWALL
#
# Splits an answer into verifiable claims. Header lines (ending
# with a colon) and bare bullet markers are not claims.
# ============================================================

import re

_BULLET = re.compile(r"^\s*(?:[-*\u2022]|\d+[.)])\s*")


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

            for sentence in re.split(r"(?<=[.!?])\s+", line):

                sentence = _BULLET.sub("", sentence).strip()

                if not sentence:
                    continue

                if sentence.endswith(":"):
                    continue

                if len(re.findall(r"[A-Za-z]{2,}", sentence)) < 2:
                    continue

                claims.append(sentence)

        return claims


def create_claim_extractor():

    return ClaimExtractor()
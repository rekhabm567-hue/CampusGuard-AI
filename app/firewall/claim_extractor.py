# ============================================================
# CLAIM EXTRACTOR
# LLM HALLUCINATION FIREWALL
# ============================================================

import re


class ClaimExtractor:

    def __init__(self):
        pass


    def extract(self, answer):

        if not answer or not answer.strip():
            return []

        cleaned_answer = answer.strip()

        # Remove bullet symbols
        cleaned_answer = re.sub(
            r"^[\-\*\•]\s*",
            "",
            cleaned_answer
        )

        # ----------------------------------------------------
        # Protect short standalone answer words such as:
        # "No." / "Yes."
        #
        # These are part of the following sentence and should
        # not become separate claims.
        # ----------------------------------------------------

        cleaned_answer = re.sub(
            r"\b(No|Yes)\.\s+",
            r"\1 ",
            cleaned_answer,
            flags=re.IGNORECASE
        )

        # ----------------------------------------------------
        # Split normal sentences
        # ----------------------------------------------------

        sentences = re.split(
            r"(?<=[.!?])\s+",
            cleaned_answer
        )

        claims = []

        for sentence in sentences:

            sentence = sentence.strip()

            if not sentence:
                continue

            sentence = re.sub(
                r"^[\-\*\•]\s*",
                "",
                sentence
            )

            if sentence:
                claims.append(sentence)

        return claims


# ============================================================
# FACTORY
# ============================================================

def create_claim_extractor():

    return ClaimExtractor()
# ============================================================
# EVIDENCE MATCHER
# LLM HALLUCINATION FIREWALL
# ============================================================

import re


class EvidenceMatcher:

    def __init__(self):
        pass

    def _tokenize(self, text):
        if not text:
            return set()

        return set(
            re.findall(
                r"\b[a-zA-Z0-9]+\b",
                text.lower()
            )
        )

    def calculate_overlap(
        self,
        claim,
        evidence
    ):
        claim_tokens = self._tokenize(
            claim
        )

        evidence_tokens = self._tokenize(
            evidence
        )

        if not claim_tokens:
            return 0.0

        common_tokens = (
            claim_tokens.intersection(
                evidence_tokens
            )
        )

        return (
            len(common_tokens)
            / len(claim_tokens)
        )

    def match_claim(
        self,
        claim,
        evidence_documents,
        threshold=0.30
    ):
        if not claim:
            return {
                "claim": claim,
                "supported": False,
                "score": 0.0,
                "evidence": []
            }

        matches = []

        for document in evidence_documents:

            evidence_text = document.get(
                "text",
                ""
            )

            score = self.calculate_overlap(
                claim,
                evidence_text
            )

            if score >= threshold:

                match = document.copy()

                match["evidence_score"] = (
                    score
                )

                matches.append(match)

        matches.sort(
            key=lambda item:
            item["evidence_score"],
            reverse=True
        )

        return {
            "claim": claim,
            "supported": len(matches) > 0,
            "score": (
                matches[0]["evidence_score"]
                if matches
                else 0.0
            ),
            "evidence": matches
        }

    def match_all_claims(
        self,
        claims,
        evidence_documents,
        threshold=0.30
    ):
        results = []

        for claim in claims:
            results.append(
                self.match_claim(
                    claim,
                    evidence_documents,
                    threshold
                )
            )

        return results


def create_evidence_matcher():
    return EvidenceMatcher()
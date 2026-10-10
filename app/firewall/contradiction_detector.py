# ============================================================
# CONTRADICTION DETECTOR
# LLM HALLUCINATION FIREWALL
# ============================================================

import re


class ContradictionDetector:

    def __init__(self):
        pass

    def _extract_percentages(self, text):
        if not text:
            return []

        matches = re.findall(
            r"\b(\d+(?:\.\d+)?)\s*%",
            text
        )

        return [
            float(value)
            for value in matches
        ]

    def detect(self, documents):
        if not documents:
            return {
                "has_conflict": False,
                "values": [],
                "message": None
            }

        extracted_values = []

        for document in documents:
            percentages = self._extract_percentages(
                document.get("text", "")
            )

            for percentage in percentages:
                extracted_values.append(
                    {
                        "value": percentage,
                        "title": document.get(
                            "title",
                            "Unknown document"
                        ),
                        "text": document.get(
                            "text",
                            ""
                        )
                    }
                )

        unique_values = sorted(
            {
                item["value"]
                for item in extracted_values
            }
        )

        has_conflict = len(unique_values) > 1

        message = None

        if has_conflict:
            message = (
                "Multiple documents contain "
                "different percentage requirements."
            )

        return {
            "has_conflict": has_conflict,
            "values": extracted_values,
            "message": message
        }


def create_contradiction_detector():
    return ContradictionDetector()
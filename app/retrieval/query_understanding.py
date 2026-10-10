# ============================================================
# QUERY UNDERSTANDING
# LLM HALLUCINATION FIREWALL
# ============================================================

import re


class QueryUnderstanding:

    def __init__(self):
        pass

    def extract_year(self, query):
        if not query:
            return None

        match = re.search(
            r"\b(1st|2nd|3rd|4th)\s+year\b",
            query,
            re.IGNORECASE
        )

        if match:
            return match.group(1).lower()

        return None

    def extract_department(self, query):
        if not query:
            return None

        departments = {
            "cse": "CSE",
            "computer science": "CSE",
            "ise": "ISE",
            "information science": "ISE",
            "ece": "ECE",
            "electronics": "ECE",
            "eee": "EEE",
            "mechanical": "ME",
            "civil": "CE",
        }

        query_lower = query.lower()

        for keyword, department in departments.items():
            if keyword in query_lower:
                return department

        return None

    def extract_attendance(self, query):
        if not query:
            return None

        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*%\s*attendance\b",
            query,
            re.IGNORECASE
        )

        if match:
            return float(match.group(1))

        return None

    def extract_academic_year(self, query):
        if not query:
            return None

        matches = re.findall(
            r"\b20\d{2}\b",
            query
        )

        if matches:
            return int(matches[0])

        return None

    def understand(self, query):
        if not query or not query.strip():
            return {
                "year": None,
                "department": None,
                "attendance": None,
                "academic_year": None,
            }

        return {
            "year": self.extract_year(query),
            "department": self.extract_department(query),
            "attendance": self.extract_attendance(query),
            "academic_year": self.extract_academic_year(query),
        }


def create_query_understanding():
    return QueryUnderstanding()

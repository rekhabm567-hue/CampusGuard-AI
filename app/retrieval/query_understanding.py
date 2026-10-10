# ============================================================
# QUERY UNDERSTANDING
# LLM HALLUCINATION FIREWALL
#
# Extracts structured constraints from a question using
# deterministic rules. Department names are matched on word
# boundaries. Missing or conflicting fields are reported in
# "ambiguous" so the caller can ask a clarifying question.
# ============================================================

import re

DEPARTMENT_PATTERNS = [
    (r"\bcse\b|\bcomputer\s+science\b", "CSE"),
    (r"\bise\b|\binformation\s+science\b", "ISE"),
    (r"\bece\b|\belectronics\b", "ECE"),
    (r"\beee\b|\belectrical\b", "EEE"),
    (r"\bmechanical\b", "ME"),
    (r"\bcivil\b", "CE"),
]

YEAR_WORDS = {
    "1st": 1, "first": 1,
    "2nd": 2, "second": 2,
    "3rd": 3, "third": 3,
    "4th": 4, "fourth": 4,
}


class QueryUnderstanding:

    def __init__(self):
        pass

    def extract_year(self, query):
        """Year of study as a string like '2nd' (kept for compatibility)."""

        if not query:
            return None

        match = re.search(
            r"\b(1st|2nd|3rd|4th|first|second|third|fourth)"
            r"[\s-]+year\b",
            query,
            re.IGNORECASE,
        )

        if not match:
            return None

        number = YEAR_WORDS[match.group(1).lower()]
        suffix = {1: "1st", 2: "2nd", 3: "3rd", 4: "4th"}[number]

        return suffix

    def extract_departments(self, query):
        """All departments mentioned, in a stable order, without repeats."""

        if not query:
            return []

        found = []

        for pattern, department in DEPARTMENT_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                if department not in found:
                    found.append(department)

        return found

    def extract_department(self, query):
        """Single department, or None if none or several are mentioned."""

        found = self.extract_departments(query)

        if len(found) == 1:
            return found[0]

        return None

    def extract_attendance(self, query):
        """Attendance percentage, only if it is between 0 and 100."""

        if not query:
            return None

        match = re.search(
            r"\b(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?attendance\b"
            r"|\battendance\s+(?:of\s+)?(\d+(?:\.\d+)?)\s*%",
            query,
            re.IGNORECASE,
        )

        if not match:
            return None

        value = float(match.group(1) or match.group(2))

        if 0 <= value <= 100:
            return value

        return None

    def extract_academic_year(self, query):
        """Four-digit year between 2000 and 2099, first one found."""

        if not query:
            return None

        matches = re.findall(r"\b20\d{2}\b", query)

        if matches:
            return int(matches[0])

        return None

    def understand(self, query):
        empty = {
            "year": None,
            "department": None,
            "attendance": None,
            "academic_year": None,
            "ambiguous": [],
        }

        if not query or not query.strip():
            return empty

        departments = self.extract_departments(query)
        years = {
            m for m in re.findall(r"\b20\d{2}\b", query)
        }

        ambiguous = []

        if len(departments) > 1:
            ambiguous.append(
                "department: more than one department mentioned "
                f"({', '.join(departments)})"
            )

        if len(years) > 1:
            ambiguous.append(
                "academic_year: more than one year mentioned "
                f"({', '.join(sorted(years))})"
            )

        raw_attendance = re.search(
            r"(\d+(?:\.\d+)?)\s*%\s*(?:of\s+)?attendance",
            query,
            re.IGNORECASE,
        )

        if raw_attendance and self.extract_attendance(query) is None:
            ambiguous.append(
                "attendance: percentage is outside 0-100"
            )

        return {
            "year": self.extract_year(query),
            "department": self.extract_department(query),
            "attendance": self.extract_attendance(query),
            "academic_year": self.extract_academic_year(query),
            "ambiguous": ambiguous,
        }


def create_query_understanding():
    return QueryUnderstanding()
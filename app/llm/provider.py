# ============================================================
# LLM PROVIDER
# LLM HALLUCINATION FIREWALL
# ============================================================

import re
from abc import ABC, abstractmethod

# Words that appear in almost every policy document. A line that shares
# only these with the question is not relevant.
GENERIC_WORDS = {
    "policy", "policies", "employee", "employees", "rule", "rules",
    "regulation", "regulations", "document", "documents", "college",
    "section", "version",
}

MAX_SENTENCES = 3
MAX_SENTENCE_CHARS = 300


class LLMProvider(ABC):

    name = "unknown"
    evidence_only = False

    @abstractmethod
    def generate(self, prompt):
        raise NotImplementedError

    def describe(self):
        return {
            "name": self.name,
            "evidence_only": self.evidence_only,
        }


class MockLLMProvider(LLMProvider):
    """
    Evidence-based local answer generator (not a language model).

    It copies the most relevant short sentences from the evidence.
    """

    name = "mock-evidence-extractor"
    evidence_only = True

    def generate(self, prompt):

        if not prompt or not prompt.strip():
            return (
                "I could not find sufficient evidence "
                "to answer this question."
            )

        query = self._extract_query(prompt)
        evidence = self._extract_evidence(prompt)

        if not evidence:
            return (
                "I could not find sufficient evidence "
                "in the authorized enterprise documents "
                "to answer this question."
            )

        evidence = self._clean_evidence(evidence)

        # Special handling for employee rules.
        if self._is_employee_rules_question(query):
            rules = self._extract_employee_rules(evidence)

            if rules:
                return self._format_employee_rules(rules)

        relevant_content = self._find_relevant_content(
            query,
            evidence
        )

        if not relevant_content:
            return (
                "I could not find sufficient evidence "
                "in the authorized enterprise documents "
                "to answer this question."
            )

        return self._build_answer(
            query,
            relevant_content
        )

    # ========================================================
    # QUERY EXTRACTION
    # ========================================================

    def _extract_query(self, prompt):

        match = re.search(
            r"USER QUESTION:\s*(.*?)"
            r"\s*AUTHORIZED EVIDENCE:",
            prompt,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            return match.group(1).strip()

        return ""

    # ========================================================
    # EVIDENCE EXTRACTION
    # ========================================================

    def _extract_evidence(self, prompt):

        match = re.search(
            r"AUTHORIZED EVIDENCE:\s*(.*?)"
            r"\s*INSTRUCTIONS:",
            prompt,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            return match.group(1).strip()

        # Fallback if instructions section is absent.
        match = re.search(
            r"AUTHORIZED EVIDENCE:\s*(.*)$",
            prompt,
            re.IGNORECASE | re.DOTALL
        )

        if match:
            return match.group(1).strip()

        return ""

    # ========================================================
    # CLEAN EVIDENCE
    # ========================================================

    def _clean_evidence(self, evidence):

        lines = evidence.splitlines()

        cleaned = []

        for line in lines:

            line = line.strip()

            if not line:
                continue

            lower = line.lower()

            # Retrieval metadata.
            if re.match(
                r"^evidence\s+\d+",
                line,
                re.IGNORECASE
            ):
                continue

            if lower.startswith("source:"):
                continue

            if lower.startswith("section:"):
                continue

            if lower.startswith("page:"):
                continue

            if "evidence match score" in lower:
                continue

            if lower.startswith("score:"):
                continue

            if lower.startswith("testing note"):
                continue

            cleaned.append(line)

        return "\n".join(cleaned)

    # ========================================================
    # TOKENIZER
    # ========================================================

    def _tokenize(self, text):

        if not text:
            return set()

        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text.lower()
        )

        stop_words = {
            "what", "is", "are", "the", "a", "an", "of", "to", "for",
            "in", "on", "and", "or", "can", "could", "would", "should",
            "does", "do", "this", "that", "with", "be", "about", "how",
            "who", "which", "tell", "me", "please",
        }

        return {
            word
            for word in words
            if word not in stop_words
        }

    # ========================================================
    # EMPLOYEE RULE QUESTION
    # ========================================================

    def _is_employee_rules_question(self, query):

        query_lower = query.lower()

        employee = (
            "employee" in query_lower
            or "employees" in query_lower
        )

        rules = (
            "rule" in query_lower
            or "rules" in query_lower
            or "regulation" in query_lower
            or "regulations" in query_lower
        )

        return employee and rules

    # ========================================================
    # EXTRACT EMPLOYEE RULES
    # ========================================================

    def _extract_employee_rules(self, evidence):

        lines = [
            line.strip()
            for line in evidence.splitlines()
            if line.strip()
        ]

        rules = []

        current_number = None
        current_title = None
        current_description = []

        for line in lines:

            number_match = re.fullmatch(
                r"(\d{1,2})",
                line
            )

            if number_match:

                if (
                    current_number is not None
                    and current_title
                    and current_description
                ):

                    rules.append(
                        (
                            current_number,
                            current_title,
                            " ".join(current_description),
                        )
                    )

                current_number = number_match.group(1)
                current_title = None
                current_description = []

                continue

            if line.lower() in {
                "no.",
                "rule / regulation",
                "description",
                "rule",
                "regulation",
            }:
                continue

            if (
                current_number is not None
                and current_title is None
            ):

                if line.lower() in {
                    "employee rules and regulations",
                    "10 sample workplace rules arranged in serial order for testing",
                }:
                    continue

                current_title = line
                continue

            if (
                current_number is not None
                and current_title is not None
            ):

                if line.lower().startswith("testing note"):
                    break

                current_description.append(line)

        if (
            current_number is not None
            and current_title
            and current_description
        ):

            rules.append(
                (
                    current_number,
                    current_title,
                    " ".join(current_description),
                )
            )

        valid_rules = []

        for number, title, description in rules:

            if not description:
                continue

            if len(description) < 10:
                continue

            valid_rules.append((number, title, description))

        return valid_rules[:10]

    # ========================================================
    # FORMAT EMPLOYEE RULES
    # ========================================================

    def _format_employee_rules(self, rules):

        answer_lines = [
            "According to the authorized "
            "Employee Rules and Regulations:"
        ]

        for number, title, description in rules:

            answer_lines.append(
                f"{number}. {title} — {description}"
            )

        return "\n\n".join(answer_lines)

    # ========================================================
    # SENTENCE SPLITTING
    # ========================================================

    def _sentences(self, text):
        """Split on sentence ends, not after abbreviations or numbers."""

        protected = re.sub(
            r"(?i)\b(ch|e\.g|i\.e|etc|vs|no|fig|eq|dr|mr|mrs|ms|prof|sec)"
            r"\.(\s)",
            "\\1\u0001\\2",
            text,
        )
        protected = re.sub(r"(\d)\.(\s)", "\\1\u0001\\2", protected)

        parts = re.split(r"(?<=[.!?])\s+", protected)

        return [p.replace("\u0001", ".").strip() for p in parts if p.strip()]

    # ========================================================
    # GENERAL RELEVANT CONTENT
    # ========================================================

    def _find_relevant_content(
        self,
        query,
        evidence
    ):
        """Up to MAX_SENTENCES short sentences, best overlap first."""

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        meaningful = query_tokens - GENERIC_WORDS

        if not meaningful:
            meaningful = query_tokens

        needed = min(2, len(meaningful))

        query_lower = query.lower()

        candidates = []
        position = 0

        for line in evidence.splitlines():

            for sentence in self._sentences(line.strip()):

                position += 1

                if (
                    len(sentence) > MAX_SENTENCE_CHARS
                    or len(re.findall(r"[A-Za-z]{2,}", sentence)) < 3
                ):
                    continue

                overlap = meaningful & self._tokenize(sentence)

                if len(overlap) < needed:
                    continue

                score = len(overlap)
                lower = sentence.lower()

                for word in ("attendance", "exam", "leave", "cgpa"):
                    if word in query_lower and word in lower:
                        score += 5

                candidates.append((score, position, sentence))

        candidates.sort(key=lambda item: (-item[0], item[1]))

        selected = []
        seen = set()

        for score, position, sentence in candidates:

            key = sentence.lower()

            if key in seen:
                continue

            seen.add(key)
            selected.append(sentence)

            if len(selected) >= MAX_SENTENCES:
                break

        return selected

    # ========================================================
    # BUILD GENERAL ANSWER
    # ========================================================

    def _build_answer(
        self,
        query,
        content
    ):

        query_lower = query.lower()

        # Attendance
        if "attendance" in query_lower:

            for item in content:

                percentage = re.search(
                    r"(\d+(?:\.\d+)?)\s*%",
                    item
                )

                if percentage:

                    return (
                        "The applicable attendance "
                        "requirement stated in the "
                        "authorized evidence is "
                        f"{percentage.group(1)}%."
                    )

        # CGPA
        if "cgpa" in query_lower:

            for item in content:

                if re.search(r"\d+(?:\.\d+)?", item):
                    return item

        if len(content) == 1:
            return content[0]

        return (
            "According to the authorized "
            "enterprise evidence:\n\n"
            + "\n".join(
                f"• {item}"
                for item in content
            )
        )


# ============================================================
# PROVIDER FACTORY
# ============================================================

def create_llm_provider():

    return MockLLMProvider()
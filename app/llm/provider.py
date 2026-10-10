# ============================================================
# LLM PROVIDER
# LLM HALLUCINATION FIREWALL
# ============================================================

import re
from abc import ABC, abstractmethod


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
    Evidence-based local answer generator.

    This version is designed to handle:
    - Normal document questions
    - Attendance questions
    - Employee rules tables
    - Numbered rules
    - Multi-line PDF extraction
    - Removal of retrieval metadata
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
            "what",
            "is",
            "are",
            "the",
            "a",
            "an",
            "of",
            "to",
            "for",
            "in",
            "on",
            "and",
            "or",
            "can",
            "could",
            "would",
            "should",
            "does",
            "do",
            "this",
            "that",
            "with",
            "be",
            "about",
            "how",
            "who",
            "which",
            "tell",
            "me",
            "please",
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

            # ------------------------------------------------
            # Detect rule number.
            #
            # Examples:
            # 1
            # 2
            # 10
            # ------------------------------------------------

            number_match = re.fullmatch(
                r"(\d{1,2})",
                line
            )

            if number_match:

                # Save previous rule.
                if (
                    current_number is not None
                    and current_title
                    and current_description
                ):

                    description = " ".join(
                        current_description
                    )

                    rules.append(
                        (
                            current_number,
                            current_title,
                            description
                        )
                    )

                current_number = (
                    number_match.group(1)
                )

                current_title = None
                current_description = []

                continue

            # ------------------------------------------------
            # Ignore table headings.
            # ------------------------------------------------

            if line.lower() in {
                "no.",
                "rule / regulation",
                "description",
                "rule",
                "regulation",
            }:
                continue

            # ------------------------------------------------
            # If we have a rule number but no title,
            # the next meaningful line is the title.
            # ------------------------------------------------

            if (
                current_number is not None
                and current_title is None
            ):

                # Avoid document title.
                if line.lower() in {
                    "employee rules and regulations",
                    "10 sample workplace rules arranged in serial order for testing",
                }:
                    continue

                current_title = line
                continue

            # ------------------------------------------------
            # Remaining lines belong to the description.
            # ------------------------------------------------

            if (
                current_number is not None
                and current_title is not None
            ):

                # Stop at testing note.
                if line.lower().startswith(
                    "testing note"
                ):
                    break

                current_description.append(
                    line
                )

        # Save final rule.
        if (
            current_number is not None
            and current_title
            and current_description
        ):

            description = " ".join(
                current_description
            )

            rules.append(
                (
                    current_number,
                    current_title,
                    description
                )
            )

        # ----------------------------------------------------
        # Validate that these really look like rules.
        # ----------------------------------------------------

        valid_rules = []

        for number, title, description in rules:

            if not description:
                continue

            if len(description) < 10:
                continue

            valid_rules.append(
                (
                    number,
                    title,
                    description
                )
            )

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

        return "\n\n".join(
            answer_lines
        )

    # ========================================================
    # GENERAL RELEVANT CONTENT
    # ========================================================

    def _find_relevant_content(
        self,
        query,
        evidence
    ):

        query_tokens = self._tokenize(
            query
        )

        if not query_tokens:
            return []

        lines = [
            line.strip()
            for line in evidence.splitlines()
            if line.strip()
        ]

        candidates = []

        for index, line in enumerate(lines):

            line_tokens = self._tokenize(
                line
            )

            overlap = (
                query_tokens.intersection(
                    line_tokens
                )
            )

            score = len(overlap)

            query_lower = query.lower()
            line_lower = line.lower()

            if (
                "attendance" in query_lower
                and "attendance" in line_lower
            ):
                score += 5

            if (
                "exam" in query_lower
                and (
                    "exam" in line_lower
                    or "examination" in line_lower
                )
            ):
                score += 5

            if (
                "leave" in query_lower
                and "leave" in line_lower
            ):
                score += 5

            if (
                "cgpa" in query_lower
                and "cgpa" in line_lower
            ):
                score += 5

            if score > 0:

                candidates.append(
                    (
                        score,
                        index,
                        line
                    )
                )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True
        )

        selected = []
        seen = set()

        for score, index, line in candidates:

            normalized = line.lower()

            if normalized in seen:
                continue

            seen.add(normalized)

            selected.append(line)

            if len(selected) >= 5:
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

        # ----------------------------------------------------
        # Attendance
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # CGPA
        # ----------------------------------------------------

        if "cgpa" in query_lower:

            for item in content:

                if re.search(
                    r"\d+(?:\.\d+)?",
                    item
                ):
                    return item

        # ----------------------------------------------------
        # Single result
        # ----------------------------------------------------

        if len(content) == 1:
            return content[0]

        # ----------------------------------------------------
        # Multiple results
        # ----------------------------------------------------

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
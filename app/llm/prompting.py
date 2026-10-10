# ============================================================
# LLM PROMPTING
# LLM HALLUCINATION FIREWALL
# ============================================================


class PromptBuilder:

    def __init__(self):
        pass

    def build_prompt(self, query, evidence_documents):
        """
        Build a grounded prompt using only authorized evidence.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        if not evidence_documents:
            return self._build_no_evidence_prompt(query)

        evidence_text = self._format_evidence(
            evidence_documents
        )

        prompt = f"""
You are an enterprise knowledge assistant.

Answer the user's question using ONLY the evidence provided below.

Do not:
- invent information
- use outside knowledge
- make unsupported assumptions
- create policy rules that are not present in the evidence
- ignore conflicts between applicable documents

If the evidence is insufficient, clearly state that the available
documents do not provide enough information.

If multiple applicable documents contain conflicting requirements,
do not choose one without evidence of which document has priority.
Instead, clearly state that conflicting information was found.

USER QUESTION:
{query.strip()}

AUTHORIZED EVIDENCE:
{evidence_text}

INSTRUCTIONS:
1. Answer the user's question directly.
2. Base every factual claim on the authorized evidence.
3. Preserve important numbers, dates, requirements, and conditions.
4. Do not expose internal retrieval or security details.
5. Keep the answer concise and natural.
"""

        return prompt.strip()

    def _format_evidence(self, evidence_documents):
        evidence_parts = []

        for index, document in enumerate(
            evidence_documents,
            start=1
        ):
            title = document.get(
                "title",
                document.get(
                    "file_name",
                    "Unknown document"
                )
            )

            section = document.get(
                "section",
                "Relevant section"
            )

            text = document.get(
                "text",
                ""
            ).strip()

            if not text:
                continue

            evidence_parts.append(
                f"""
Evidence {index}
Source: {title}
Section: {section}

{text}
""".strip()
            )

        if not evidence_parts:
            return "No usable evidence was found."

        return "\n\n".join(evidence_parts)

    def _build_no_evidence_prompt(self, query):
        return f"""
You are an enterprise knowledge assistant.

The user asked:

{query.strip()}

No authorized evidence is available for this question.

Do not invent an answer.

Respond clearly that the available enterprise documents
do not contain enough information to answer the question.
""".strip()


def create_prompt_builder():
    return PromptBuilder()
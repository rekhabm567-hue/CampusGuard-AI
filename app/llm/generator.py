# ============================================================
# LLM GENERATOR
# LLM HALLUCINATION FIREWALL
# ============================================================

from app.llm.provider import create_llm_provider
from app.llm.prompting import create_prompt_builder


class AnswerGenerator:

    def __init__(self, provider=None, prompt_builder=None):
        self.provider = (
            provider
            if provider is not None
            else create_llm_provider()
        )

        self.prompt_builder = (
            prompt_builder
            if prompt_builder is not None
            else create_prompt_builder()
        )

    def generate(self, query, evidence_documents):
        """
        Generate an answer using only the supplied evidence.
        """

        if not query or not query.strip():
            raise ValueError("Query cannot be empty.")

        prompt = self.prompt_builder.build_prompt(
            query,
            evidence_documents
        )

        answer = self.provider.generate(prompt)

        if not answer or not answer.strip():
            raise ValueError(
                "The LLM provider returned an empty answer."
            )

        return {
            "query": query.strip(),
            "answer": answer.strip(),
            "prompt": prompt,
            "evidence_count": len(evidence_documents),
        }


def create_answer_generator():
    return AnswerGenerator()
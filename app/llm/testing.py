"""Test-only providers. Never used by the production factory."""
from app.llm.provider import LLMProvider


class FaultyLLMProvider(LLMProvider):
    """Returns a fixed answer, whatever the prompt says.

    Used to prove the firewall catches wrong answers.
    """

    name = "test-faulty"
    evidence_only = False

    def __init__(self, answer):
        self._answer = answer

    def generate(self, prompt):
        return self._answer
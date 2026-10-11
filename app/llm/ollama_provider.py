"""Local LLM provider using an Ollama server.

Falls back to the evidence-only mock if the server is unreachable or
returns nothing, and says so through describe().
"""
import os

import requests

from app.llm.provider import LLMProvider, MockLLMProvider

DEFAULT_URL = "http://127.0.0.1:11434"
DEFAULT_MODEL = "qwen2.5:7b"


class OllamaProvider(LLMProvider):

    evidence_only = False

    def __init__(
        self,
        model=None,
        base_url=None,
        timeout=300,
        fallback=None,
        http_post=None,
    ):
        self.model = model or os.getenv("OLLAMA_MODEL", DEFAULT_MODEL)
        self.base_url = (
            base_url or os.getenv("OLLAMA_URL", DEFAULT_URL)
        ).rstrip("/")
        self.timeout = timeout
        self.fallback = fallback or MockLLMProvider()
        self._post = http_post or requests.post
        self.last_error = None
        self.used_fallback = False
        self.name = f"ollama:{self.model}"

    def generate(self, prompt):

        self.last_error = None
        self.used_fallback = False

        try:
            response = self._post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0, "num_ctx": 4096},
                },
                timeout=self.timeout,
            )
            response.raise_for_status()
            text = (response.json().get("response") or "").strip()

            if text:
                return text

            self.last_error = "Empty response from the model."

        except Exception as error:
            self.last_error = f"{type(error).__name__}: {error}"

        self.used_fallback = True
        self.name = f"{self.fallback.name} (fallback; {self.model} unavailable)"
        self.evidence_only = True

        return self.fallback.generate(prompt)
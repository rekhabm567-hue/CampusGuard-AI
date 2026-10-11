from app.llm.ollama_provider import OllamaProvider


class FakeResponse:
    def __init__(self, data):
        self._data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self._data


PROMPT = (
    "USER QUESTION:\nWhat is the leave rule?\n\nAUTHORIZED EVIDENCE:\n"
    "Evidence 1\nLeave must be approved by the manager.\n\nINSTRUCTIONS:\n1."
)


def test_returns_model_text():
    provider = OllamaProvider(
        http_post=lambda *a, **k: FakeResponse({"response": " Answer [1]. "})
    )
    assert provider.generate(PROMPT) == "Answer [1]."
    assert provider.used_fallback is False
    assert provider.describe()["evidence_only"] is False


def test_falls_back_when_server_down():
    def boom(*a, **k):
        raise ConnectionError("refused")

    provider = OllamaProvider(http_post=boom)
    answer = provider.generate(PROMPT)
    assert answer
    assert provider.used_fallback is True
    assert "fallback" in provider.name
    assert provider.describe()["evidence_only"] is True
    assert "ConnectionError" in provider.last_error


def test_empty_response_falls_back():
    provider = OllamaProvider(
        http_post=lambda *a, **k: FakeResponse({"response": "  "})
    )
    provider.generate(PROMPT)
    assert provider.used_fallback is True
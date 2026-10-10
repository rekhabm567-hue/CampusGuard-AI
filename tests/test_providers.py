from app.llm.generator import AnswerGenerator
from app.llm.provider import MockLLMProvider, create_llm_provider
from app.llm.testing import FaultyLLMProvider


def test_mock_provider_is_labelled_evidence_only():
    info = MockLLMProvider().describe()
    assert info["evidence_only"] is True
    assert "mock" in info["name"]


def test_factory_still_returns_the_mock():
    assert isinstance(create_llm_provider(), MockLLMProvider)


def test_faulty_provider_returns_its_fixed_answer():
    provider = FaultyLLMProvider("Students need 90% attendance.")
    assert provider.generate("any prompt") == "Students need 90% attendance."
    assert provider.describe()["evidence_only"] is False


def test_generator_accepts_an_injected_provider():
    generator = AnswerGenerator(
        provider=FaultyLLMProvider("Students need 90% attendance.")
    )
    result = generator.generate(
        "What is the attendance rule?",
        [{"title": "Policy", "text": "The minimum is 75%."}],
    )
    assert result["answer"] == "Students need 90% attendance."
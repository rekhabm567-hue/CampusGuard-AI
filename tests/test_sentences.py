from app.firewall.claim_extractor import ClaimExtractor
from app.llm.prompting import PromptBuilder
from app.llm.provider import MockLLMProvider

ex = ClaimExtractor()


def test_no_split_after_abbreviation_or_number():
    claims = ex.extract(
        "Textbook 1: Ch. 9, Ch. 12 covers retrieval models. "
        "Section 4.1 introduces the topic."
    )
    assert len(claims) == 2
    assert claims[0].startswith("Textbook 1: Ch. 9")
    assert claims[1].startswith("Section 4.1 introduces")


def test_normal_sentences_still_split():
    assert ex.extract("First rule applies. Second rule applies.") == [
        "First rule applies.",
        "Second rule applies.",
    ]


def test_mock_output_is_short_for_a_long_chunk():
    long_text = " ".join(
        f"Information retrieval models describe method number {i} "
        f"for ranking documents." for i in range(60)
    )
    doc = {"title": "Module 4", "text": long_text}
    prompt = PromptBuilder().build_prompt(
        "information retrieval models", [doc]
    )
    answer = MockLLMProvider().generate(prompt)
    assert answer.count("•") <= 3
    assert len(answer) < 1200
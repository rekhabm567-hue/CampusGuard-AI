from app.core.pipeline import HallucinationFirewallPipeline
from app.llm.prompting import PromptBuilder
from app.llm.provider import MockLLMProvider
from app.retrieval.reranker import EvidenceReranker

LEAVE = {
    "title": "Employee Rules",
    "text": "Leave Policy — Planned leave must be requested in advance "
            "and approved by the appropriate manager.",
}

ATTENDANCE = {
    "title": "2026 Academic Attendance Policy",
    "text": "This policy applies to undergraduate students enrolled in "
            "the college.\n\nSection 6: Policy Version\n\nPolicy Version: 2.0",
}

QUESTION = "what is the employee leave policy"


def make_pipeline():
    return HallucinationFirewallPipeline(
        reranker=EvidenceReranker(),
        entailment_fn=None,
        audit_fn=lambda *args: None,
    )


def test_generic_word_policy_does_not_make_a_document_relevant():
    kept = make_pipeline()._filter_relevant_evidence(
        QUESTION, [LEAVE, ATTENDANCE]
    )
    assert kept == [LEAVE]


def test_single_meaningful_word_is_enough_for_the_matching_document():
    assert make_pipeline()._is_relevant_document(QUESTION, LEAVE)


def test_provider_ignores_lines_sharing_only_generic_words():
    prompt = PromptBuilder().build_prompt(QUESTION, [LEAVE, ATTENDANCE])
    answer = MockLLMProvider().generate(prompt)
    assert "Planned leave" in answer
    assert "Policy Version" not in answer
    assert "undergraduate" not in answer
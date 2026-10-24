from app.llm.prompting import PromptBuilder
from app.llm.provider import MockLLMProvider

POLICY = {
    "title": "Attendance Policy",
    "text": (
        "The minimum attendance requirement for semester examinations "
        "is 75%.\n\nA student whose attendance is below the required 75% "
        "minimum does not meet the requirement."
    ),
}


def test_attendance_answer_is_the_rule_sentence_itself():
    prompt = PromptBuilder().build_prompt(
        "Can a student with 76% attendance write the semester exam?",
        [POLICY],
    )
    answer = MockLLMProvider().generate(prompt)
    assert answer == (
        "The minimum attendance requirement for semester examinations "
        "is 75%."
    )
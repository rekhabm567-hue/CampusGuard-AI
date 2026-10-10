import pytest

from app.retrieval.query_understanding import QueryUnderstanding

qu = QueryUnderstanding()


def test_attendance_example_from_project_brief():
    result = qu.understand(
        "Can a 2nd year CSE student with 72% attendance "
        "write the 2026 semester exam?"
    )
    assert result["year"] == "2nd"
    assert result["department"] == "CSE"
    assert result["attendance"] == 72.0
    assert result["academic_year"] == 2026
    assert result["ambiguous"] == []


@pytest.mark.parametrize(
    "text",
    [
        "How do I raise a concern?",
        "Where is the piece of equipment kept?",
        "What is the policy otherwise?",
        "I promise to attend.",
    ],
)
def test_departments_not_matched_inside_other_words(text):
    assert qu.extract_departments(text) == []
    assert qu.understand(text)["department"] is None


def test_real_departments_still_match():
    assert qu.extract_department("ECE lab timings") == "ECE"
    assert qu.extract_department("ise syllabus") == "ISE"
    assert qu.extract_department("Computer Science rules") == "CSE"


def test_two_departments_is_ambiguous():
    result = qu.understand("Compare CSE and ECE attendance rules")
    assert result["department"] is None
    assert any("department" in item for item in result["ambiguous"])


def test_two_academic_years_is_ambiguous():
    result = qu.understand("Difference between 2025 and 2026 policy?")
    assert any("academic_year" in item for item in result["ambiguous"])


def test_attendance_over_100_is_flagged():
    result = qu.understand("A student with 150% attendance")
    assert result["attendance"] is None
    assert any("attendance" in item for item in result["ambiguous"])


def test_attendance_phrase_variants():
    assert qu.extract_attendance("attendance of 72%") == 72.0
    assert qu.extract_attendance("72.5% attendance") == 72.5
    assert qu.extract_attendance("no number here") is None


def test_year_of_study_words():
    assert qu.extract_year("a third year student") == "3rd"
    assert qu.extract_year("1st year") == "1st"
    assert qu.extract_year("hello") is None


def test_empty_query():
    result = qu.understand("   ")
    assert result["department"] is None
    assert result["ambiguous"] == []
from app.firewall.citations import extract_citations, validate_citations

EVIDENCE = [
    {"chunk_id": "a_1", "title": "Attendance Policy", "page": None,
     "version": "2.0", "text": "Minimum is 75%."},
    {"chunk_id": "b_1", "title": "Exam Rules", "page": 3,
     "version": "1.0", "text": "Hall tickets are issued online."},
]


def test_extract_simple_list_and_range():
    assert extract_citations("A [1]. B [2, 3]. C [1-2].") == [1, 2, 3, 1, 2]


def test_non_citation_brackets_ignored():
    assert extract_citations("See [Note] and [a, b] and [].") == []


def test_valid_citation_maps_to_evidence():
    result = validate_citations(
        "The minimum attendance is 75% [1].", EVIDENCE
    )
    assert result["ok"] is True
    assert result["valid"] == [1]
    assert result["cited_documents"][0]["chunk_id"] == "a_1"
    assert result["cited_documents"][0]["page"] is None


def test_page_comes_only_from_evidence():
    result = validate_citations("Hall tickets are online [2].", EVIDENCE)
    assert result["cited_documents"][0]["page"] == 3


def test_citation_beyond_evidence_is_invalid():
    result = validate_citations("The minimum is 75% [7].", EVIDENCE)
    assert result["invalid"] == [7]
    assert result["ok"] is False
    assert result["cited_documents"] == []


def test_zero_citation_is_invalid():
    result = validate_citations("The minimum is 75% [0].", EVIDENCE)
    assert result["invalid"] == [0]
    assert result["ok"] is False


def test_uncited_factual_sentence_is_reported():
    result = validate_citations(
        "The minimum is 75% [1]. Students may also repeat the course.",
        EVIDENCE,
    )
    assert result["uncited_sentences"] == [
        "Students may also repeat the course."
    ]
    assert result["ok"] is False


def test_abstention_sentence_needs_no_citation():
    result = validate_citations(
        "I could not find sufficient evidence to answer this question.",
        EVIDENCE,
    )
    assert result["uncited_sentences"] == []
    assert result["ok"] is False  # nothing was cited


def test_no_evidence_means_every_citation_invalid():
    result = validate_citations("The minimum is 75% [1].", [])
    assert result["invalid"] == [1]
    assert result["ok"] is False


def test_empty_answer():
    result = validate_citations("", EVIDENCE)
    assert result["citation_count"] == 0
    assert result["ok"] is False
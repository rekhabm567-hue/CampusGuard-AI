from app.firewall.claim_extractor import ClaimExtractor

ex = ClaimExtractor()


def test_header_line_is_not_a_claim():
    answer = (
        "According to the authorized enterprise evidence:\n\n"
        "• Leave Policy — Planned leave must be requested in advance."
    )
    claims = ex.extract(answer)
    assert len(claims) == 1
    assert claims[0].startswith("Leave Policy")


def test_sentences_split_and_bullets_stripped():
    assert ex.extract("- First rule applies. Second rule applies.") == [
        "First rule applies.",
        "Second rule applies.",
    ]


def test_empty_answer():
    assert ex.extract("  ") == []
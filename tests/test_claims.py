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
    

def test_meta_lead_in_is_removed():
    claims = ex.extract(
        "According to the evidence, the employee leave policy requires "
        "that planned leave be requested in advance."
    )
    assert claims == [
        "The employee leave policy requires that planned leave be "
        "requested in advance."
    ]


def test_lead_in_variants():
    assert ex.extract("Based on the evidence, leave needs approval.") == [
        "Leave needs approval."
    ]
    assert ex.extract("The documents state that leave needs approval.") == [
        "Leave needs approval."
    ]


def test_plain_sentence_is_unchanged():
    assert ex.extract("Leave needs approval from the manager.") == [
        "Leave needs approval from the manager."
    ]


def test_lead_in_with_trailing_provided():
    claims = ex.extract(
        "Based on the evidence provided, a student with 72% attendance "
        "does not meet the minimum."
    )
    assert claims == [
        "A student with 72% attendance does not meet the minimum."
    ]
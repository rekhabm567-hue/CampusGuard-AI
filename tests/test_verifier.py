from app.firewall.verifier import (
    CONTRADICTED,
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNVERIFIED,
    ClaimVerifier,
    extract_thresholds,
    overall_status,
)

POLICY_TEXT = (
    "Section 2: Attendance Requirement\n\n"
    "Students are required to maintain the minimum attendance percentage "
    "specified by the college for eligibility to appear for semester "
    "examinations.\n\n"
    "Section 3: General Requirement\n\n"
    "The minimum attendance requirement for semester examinations is 75%.\n\n"
    "Section 4: Examination Eligibility\n\n"
    "A student whose attendance is below the required 75% minimum does not\n"
    "meet the standard attendance eligibility requirement for the semester\n"
    "examination."
)

POLICY = {
    "chunk_id": "attendance_policy_2026.txt_chunk_1",
    "title": "2026 Academic Attendance Policy",
    "file_path": "data/documents/attendance_policy_2026.txt",
    "page": None,
    "version": "2.0",
    "text": POLICY_TEXT,
}


def fake_entailment(entail=0.0, contradiction=0.0):
    return lambda claim, text: {
        "entailment": entail,
        "contradiction": contradiction,
    }


def test_threshold_extraction_from_policy():
    assert extract_thresholds(POLICY_TEXT) == {75.0}


def test_student_value_is_not_a_rule():
    assert extract_thresholds(
        "A student with 72% attendance is below the 75% minimum."
    ) == {75.0}
    assert extract_thresholds("The student has 72% attendance.") == set()


def test_wrong_percentage_is_contradicted():
    result = ClaimVerifier().verify_claim(
        "Students need 90% attendance for semester examinations.",
        [POLICY],
    )
    assert result["status"] == CONTRADICTED
    assert result["method"] == "numeric"
    assert result["numeric_check"] == "conflict"
    assert "75%" in result["contradicting"][0]["excerpt"]
    assert result["contradicting"][0]["version"] == "2.0"


def test_matching_percentage_is_partial_without_entailment_model():
    result = ClaimVerifier().verify_claim(
        "The minimum attendance for semester examinations is 75%.",
        [POLICY],
    )
    assert result["status"] == PARTIALLY_SUPPORTED
    assert result["numeric_check"] == "consistent"
    assert result["supporting"]


def test_matching_percentage_is_supported_with_entailment_model():
    verifier = ClaimVerifier(entailment_fn=fake_entailment(entail=0.95))
    result = verifier.verify_claim(
        "The minimum attendance for semester examinations is 75%.",
        [POLICY],
    )
    assert result["status"] == SUPPORTED
    assert result["method"] == "entailment"


def test_entailment_model_can_contradict():
    verifier = ClaimVerifier(entailment_fn=fake_entailment(contradiction=0.9))
    result = verifier.verify_claim(
        "Students do not need attendance for semester examinations.",
        [POLICY],
    )
    assert result["status"] == CONTRADICTED
    assert result["method"] == "entailment"


def test_unrelated_claim_is_unverified():
    result = ClaimVerifier().verify_claim(
        "The canteen serves lunch at noon.", [POLICY]
    )
    assert result["status"] == UNVERIFIED
    assert result["related"] == []


def test_relevant_but_unconfirmed_claim_is_unverified():
    result = ClaimVerifier().verify_claim(
        "Students must attend semester examinations.", [POLICY]
    )
    assert result["status"] == UNVERIFIED
    assert result["related"]


def test_student_percentage_does_not_cause_contradiction():
    result = ClaimVerifier().verify_claim(
        "A student with 72% attendance does not meet the requirement "
        "for semester examinations.",
        [POLICY],
    )
    assert result["numeric_check"] == "not_applicable"
    assert result["status"] != CONTRADICTED


def test_page_is_never_invented():
    claim = "Students need 90% attendance for semester examinations."

    no_page = ClaimVerifier().verify_claim(claim, [POLICY])
    assert no_page["contradicting"][0]["page"] is None

    with_page = ClaimVerifier().verify_claim(
        claim, [dict(POLICY, page=3)]
    )
    assert with_page["contradicting"][0]["page"] == 3


def test_empty_claim_and_no_evidence():
    verifier = ClaimVerifier()
    assert verifier.verify_claim("", [POLICY])["status"] == UNVERIFIED
    assert verifier.verify_claim("anything", [])["status"] == UNVERIFIED
    assert verifier.verify_claim("anything", None)["status"] == UNVERIFIED


def test_overall_status():
    def make(*statuses):
        return [{"status": s} for s in statuses]

    assert overall_status([]) == "unverified"
    assert overall_status(make(SUPPORTED, SUPPORTED)) == "verified"
    assert overall_status(make(SUPPORTED, CONTRADICTED)) == "contradicted"
    assert overall_status(make(SUPPORTED, UNVERIFIED)) == "partially_verified"
    assert overall_status(make(PARTIALLY_SUPPORTED)) == "partially_verified"
    assert overall_status(make(UNVERIFIED, UNVERIFIED)) == "unverified"
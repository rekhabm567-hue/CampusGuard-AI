# ============================================================
# CLAIM VERIFIER
# LLM HALLUCINATION FIREWALL
#
# Statuses: supported, partially_supported, contradicted,
# unverified. "supported" needs either an entailment function
# (NLI model) or the claim being quoted from the evidence.
#
# Deterministic checks:
#   1. Percentage rules stated in a claim must match rules in
#      the relevant evidence.
#   2. A student's own value (e.g. 72%) compared with a single
#      minimum rule must agree with the claim's eligibility
#      verdict (value >= minimum means eligible).
#   3. A claim whose words appear contiguously in one evidence
#      chunk is supported by quotation.
# ============================================================

import re

SUPPORTED = "supported"
PARTIALLY_SUPPORTED = "partially_supported"
CONTRADICTED = "contradicted"
UNVERIFIED = "unverified"

RELEVANCE_MIN = 0.25

STOPWORDS = {
    "the", "and", "for", "are", "was", "were", "that", "this", "with",
    "from", "have", "has", "had", "can", "will", "shall", "may", "not",
    "all", "any", "its", "their", "than", "then", "who", "whose", "what",
    "when", "which", "does", "did", "into", "such", "per", "must", "should",
}

_NUM = r"(\d+(?:\.\d+)?)\s*(?:%|percent\b|per\s+cent\b)"

_CUE = (
    r"(?:minimum|at\s+least|requirements|requirement|required|requires|"
    r"require|needs|need|threshold|not\s+less\s+than|no\s+less\s+than|"
    r"below|under|above|exceeds|more\s+than|less\s+than)"
)

# Up to 6 plain words between the cue and the number. Words that
# describe a person's own value ("has 72%") break the match.
_GAP = (
    r"(?:\s+(?!(?:with|has|have|had|having|attended|scored|got|"
    r"obtained|secured|achieved)\b)[A-Za-z]+){0,6}?"
)

_BEFORE = re.compile(rf"\b{_CUE}{_GAP}\s+{_NUM}", re.IGNORECASE)

_AFTER = re.compile(
    rf"(?<![\d.]){_NUM}\s+(?:[A-Za-z]+\s+)?"
    r"(?:minimum|required|threshold)\b",
    re.IGNORECASE,
)

# A percentage that describes a person's own value.
_STUDENT = re.compile(
    r"\b(?:with|has|have|having|had|attended|"
    rf"attendance\s+(?:of|at|is|was))\s+{_NUM}",
    re.IGNORECASE,
)

_NEGATIVE_VERDICT = re.compile(
    r"\b(?:not\s+(?:be\s+)?(?:eligible|allowed|permitted|able|qualified)"
    r"|not\s+(?:meet|qualify|satisfy)"
    r"|fails?\s+to\s+meet"
    r"|ineligible|unable\s+to|barred|disqualified"
    r"|cannot|can[\u2019']?t|can\s+not|may\s+not|must\s+not)\b",
    re.IGNORECASE,
)

_POSITIVE_VERDICT = re.compile(
    r"\b(?:eligible|allowed|permitted|able\s+to"
    r"|can\s+(?:write|appear|sit|take|attend)"
    r"|may\s+(?:write|appear|sit|take)"
    r"|meets?\s+the|satisf(?:y|ies)\s+the|qualif(?:y|ies))\b",
    re.IGNORECASE,
)

_MINIMUM_WORDS = re.compile(
    r"\b(?:minimum|at\s+least|not\s+less\s+than|no\s+less\s+than|required)\b",
    re.IGNORECASE,
)


def _rule_matches(text):
    """Return (collapsed_text, [(start, end, value)]) for rule numbers."""

    collapsed = re.sub(r"\s+", " ", str(text or ""))

    spans = []

    for pattern in (_BEFORE, _AFTER):
        for match in pattern.finditer(collapsed):
            spans.append(
                (match.start(1), match.end(1), float(match.group(1)))
            )

    return collapsed, spans


def extract_thresholds(text):
    """Percentages stated as a rule (minimum, required, at least...)."""

    _, spans = _rule_matches(text)

    return {value for _, _, value in spans}


def extract_student_values(text):
    """Percentages that describe a person's own value (e.g. 'with 72%').

    Numbers already matched as rules are excluded.
    """

    collapsed, rule_spans = _rule_matches(text)

    values = []

    for match in _STUDENT.finditer(collapsed):
        start, end = match.span(1)

        if any(start < r_end and r_start < end for r_start, r_end, _ in rule_spans):
            continue

        value = float(match.group(1))

        if 0 <= value <= 100 and value not in values:
            values.append(value)

    return values


def eligibility_verdict(text):
    """'eligible', 'ineligible', or None if absent or mixed."""

    text = str(text or "")

    negative = bool(_NEGATIVE_VERDICT.search(text))
    positive = bool(_POSITIVE_VERDICT.search(_NEGATIVE_VERDICT.sub(" ", text)))

    if negative and not positive:
        return "ineligible"

    if positive and not negative:
        return "eligible"

    return None


def content_tokens(text):
    return {
        token
        for token in re.findall(r"[a-z]{3,}", str(text or "").lower())
        if token not in STOPWORDS
    }


def relevance(claim, chunk_text):
    claim_tokens = content_tokens(claim)

    if not claim_tokens:
        return 0.0

    return len(claim_tokens & content_tokens(chunk_text)) / len(claim_tokens)


def _norm(text):
    return re.sub(r"[^a-z0-9% ]+", " ", str(text or "").lower()).split()


def quoted_in(claim, document):
    """True if the claim's words appear contiguously in the document."""

    words = _norm(claim)

    if len(words) < 4:
        return False

    haystack = " " + " ".join(_norm(document.get("text", ""))) + " "

    return " " + " ".join(words) + " " in haystack


def _sentences(text):
    return [
        s.strip()
        for s in re.split(r"(?<=[.!?])\s+|\n+", str(text or ""))
        if s.strip()
    ]


def _excerpt(text, value=None):
    if value is not None:
        for sentence in _sentences(text):
            if value in extract_thresholds(sentence):
                return sentence[:300]

    return re.sub(r"\s+", " ", str(text or "")).strip()[:200]


def _is_minimum_rule(document, value):
    """True if a sentence stating `value` also uses minimum wording."""

    for sentence in _sentences(document.get("text", "")):
        if value in extract_thresholds(sentence) and _MINIMUM_WORDS.search(
            sentence
        ):
            return True

    return False


def _ref(document, excerpt, **extra):
    reference = {
        "chunk_id": document.get("chunk_id"),
        "title": document.get("title") or document.get("file_name"),
        "file_path": document.get("file_path"),
        "page": document.get("page"),
        "version": document.get("version"),
        "excerpt": excerpt,
    }
    reference.update(extra)
    return reference


def _fmt(values):
    return ", ".join(f"{value:g}" for value in values)


class ClaimVerifier:

    def __init__(
        self,
        entailment_fn=None,
        entail_threshold=0.7,
        contradict_threshold=0.7,
        relevance_min=RELEVANCE_MIN,
    ):
        """entailment_fn(claim, evidence_text) -> {"entailment": p,
        "contradiction": p}. Optional; enables the supported status."""

        self.entailment_fn = entailment_fn
        self.entail_threshold = entail_threshold
        self.contradict_threshold = contradict_threshold
        self.relevance_min = relevance_min

    # --------------------------------------------------------
    # eligibility: student's value vs a single minimum rule
    # --------------------------------------------------------

    def _check_eligibility(
        self, student_values, verdict, evidence_values, result
    ):
        """Updates result. Returns True if it set a CONTRADICTED status."""

        if not evidence_values:
            result["eligibility_check"] = "no_evidence"
            return False

        if len(evidence_values) > 1:
            result["eligibility_check"] = "ambiguous"
            result["reasons"].append(
                "The evidence states several percentage rules "
                f"({_fmt(sorted(evidence_values))}%), so eligibility "
                "was not decided automatically."
            )
            return False

        threshold = next(iter(evidence_values))

        documents = [
            d
            for d in evidence_values[threshold]
            if _is_minimum_rule(d, threshold)
        ]

        if not documents:
            result["eligibility_check"] = "not_a_minimum_rule"
            return False

        claim_says_eligible = verdict == "eligible"

        for value in student_values:

            meets = value >= threshold

            if meets != claim_says_eligible:
                result["status"] = CONTRADICTED
                result["method"] = "numeric"
                result["eligibility_check"] = "conflict"
                result["reasons"].append(
                    f"The claim says a student with {value:g}% is "
                    f"{'eligible' if claim_says_eligible else 'not eligible'}"
                    f", but the minimum is {threshold:g}%, which "
                    f"{value:g}% {'meets' if meets else 'does not meet'}."
                )

                for document in documents:
                    result["contradicting"].append(
                        _ref(
                            document,
                            _excerpt(document.get("text", ""), threshold),
                            value=threshold,
                        )
                    )

                return True

        result["eligibility_check"] = "consistent"
        result["reasons"].append(
            "The eligibility verdict follows from comparing "
            f"{_fmt(student_values)}% with the {threshold:g}% minimum."
        )

        for document in documents:
            result["supporting"].append(
                _ref(
                    document,
                    _excerpt(document.get("text", ""), threshold),
                    value=threshold,
                )
            )

        if result["numeric_check"] == "not_applicable":
            result["numeric_check"] = "consistent"

        return False

    # --------------------------------------------------------
    # main entry point
    # --------------------------------------------------------

    def verify_claim(self, claim, evidence_documents):

        result = {
            "claim": claim,
            "status": UNVERIFIED,
            "method": "none",
            "numeric_check": "not_applicable",
            "eligibility_check": "not_applicable",
            "reasons": [],
            "supporting": [],
            "contradicting": [],
            "related": [],
        }

        if not claim or not str(claim).strip():
            result["reasons"].append("Empty claim.")
            return result

        documents = [
            d for d in (evidence_documents or []) if isinstance(d, dict)
        ]

        scored = [
            (d, relevance(claim, d.get("text", ""))) for d in documents
        ]

        relevant = sorted(
            [(d, s) for d, s in scored if s >= self.relevance_min],
            key=lambda pair: pair[1],
            reverse=True,
        )

        if not relevant:
            result["reasons"].append(
                "No relevant evidence among the authorized documents."
            )
            return result

        result["related"] = [
            _ref(d, _excerpt(d.get("text", "")), relevance=round(s, 3))
            for d, s in relevant[:2]
        ]

        # ---------------- deterministic numeric checks ----------------

        claim_values = extract_thresholds(claim)
        student_values = extract_student_values(claim)
        verdict = eligibility_verdict(claim)

        evidence_values = {}

        if claim_values or student_values:
            for document, _ in relevant:
                for value in extract_thresholds(document.get("text", "")):
                    evidence_values.setdefault(value, []).append(document)

        if claim_values:

            if not evidence_values:
                result["numeric_check"] = "no_evidence"
                result["reasons"].append(
                    "The claim states a percentage rule, but the relevant "
                    "evidence states none."
                )

            else:
                missing = sorted(
                    v for v in claim_values if v not in evidence_values
                )

                if missing:
                    result["numeric_check"] = "conflict"
                    result["status"] = CONTRADICTED
                    result["method"] = "numeric"
                    result["reasons"].append(
                        f"The claim states {_fmt(missing)}% but the "
                        f"evidence states {_fmt(sorted(evidence_values))}%."
                    )

                    for value in sorted(evidence_values):
                        for document in evidence_values[value]:
                            result["contradicting"].append(
                                _ref(
                                    document,
                                    _excerpt(document.get("text", ""), value),
                                    value=value,
                                )
                            )

                    return result

                result["numeric_check"] = "consistent"

                for value in sorted(claim_values):
                    for document in evidence_values[value]:
                        result["supporting"].append(
                            _ref(
                                document,
                                _excerpt(document.get("text", ""), value),
                                value=value,
                            )
                        )

        if student_values and verdict:
            if self._check_eligibility(
                student_values, verdict, evidence_values, result
            ):
                return result

        # ---------------- quotation from the evidence ----------------

        if result["numeric_check"] in ("not_applicable", "consistent"):
            for document, _ in relevant:
                if quoted_in(claim, document):
                    result["status"] = SUPPORTED
                    result["method"] = "quotation"
                    result["supporting"].append(
                        _ref(document, _excerpt(document.get("text", "")))
                    )
                    result["reasons"].append(
                        "The claim is stated in the evidence."
                    )
                    return result

        # ---------------- optional entailment model ----------------

        if self.entailment_fn:

            best_entail = (0.0, None)
            best_contra = (0.0, None)

            for document, _ in relevant:
                scores = self.entailment_fn(claim, document.get("text", ""))

                entail = float(scores.get("entailment", 0.0))
                contra = float(scores.get("contradiction", 0.0))

                if entail > best_entail[0]:
                    best_entail = (entail, document)

                if contra > best_contra[0]:
                    best_contra = (contra, document)

            if (
                best_contra[0] >= self.contradict_threshold
                and best_contra[0] > best_entail[0]
            ):
                document = best_contra[1]
                result["status"] = CONTRADICTED
                result["method"] = "entailment"
                result["contradicting"].append(
                    _ref(
                        document,
                        _excerpt(document.get("text", "")),
                        score=round(best_contra[0], 3),
                    )
                )
                result["reasons"].append(
                    "The entailment model found the evidence contradicts "
                    "the claim."
                )
                return result

            if (
                best_entail[0] >= self.entail_threshold
                and result["numeric_check"] in ("not_applicable", "consistent")
            ):
                document = best_entail[1]
                result["status"] = SUPPORTED
                result["method"] = "entailment"
                result["supporting"].append(
                    _ref(
                        document,
                        _excerpt(document.get("text", "")),
                        score=round(best_entail[0], 3),
                    )
                )
                result["reasons"].append(
                    "The entailment model found the evidence supports "
                    "the claim."
                )
                return result

        # ---------------- no decisive verdict ----------------

        if result["numeric_check"] == "consistent":
            result["status"] = PARTIALLY_SUPPORTED
            result["method"] = "numeric"
            result["reasons"].append(
                "The numbers match the evidence, but the claim's "
                "full meaning was not verified."
            )
            return result

        result["reasons"].append(
            "Relevant passages were found, but nothing verified that they "
            "support the claim."
        )

        return result

    def verify_claims(self, claims, evidence_documents):
        return [
            self.verify_claim(claim, evidence_documents)
            for claim in (claims or [])
        ]


def overall_status(claim_results):
    """Collapse per-claim statuses into one answer-level status."""

    if not claim_results:
        return "unverified"

    statuses = [result["status"] for result in claim_results]

    if CONTRADICTED in statuses:
        return "contradicted"

    if all(status == SUPPORTED for status in statuses):
        return "verified"

    if any(status in (SUPPORTED, PARTIALLY_SUPPORTED) for status in statuses):
        return "partially_verified"

    return "unverified"


def create_claim_verifier(entailment_fn=None):
    return ClaimVerifier(entailment_fn=entailment_fn)
# ============================================================
# CLAIM VERIFIER
# LLM HALLUCINATION FIREWALL
#
# Statuses: supported, partially_supported, contradicted,
# unverified. "supported" needs an entailment function (NLI
# model); without one, word overlap alone never yields it.
# Deterministic check: percentage rules stated in a claim must
# match percentage rules in the relevant evidence.
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


def extract_thresholds(text):
    """Percentages stated as a rule (minimum, required, at least...)."""

    collapsed = re.sub(r"\s+", " ", str(text or ""))

    values = set()

    for pattern in (_BEFORE, _AFTER):
        for match in pattern.finditer(collapsed):
            values.add(float(match.group(1)))

    return values


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

    def verify_claim(self, claim, evidence_documents):

        result = {
            "claim": claim,
            "status": UNVERIFIED,
            "method": "none",
            "numeric_check": "not_applicable",
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

        # ---------------- deterministic numeric check ----------------

        claim_values = extract_thresholds(claim)

        if claim_values:

            evidence_values = {}

            for document, _ in relevant:
                for value in extract_thresholds(document.get("text", "")):
                    evidence_values.setdefault(value, []).append(document)

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
                "The percentage matches a stated rule, but the claim's "
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
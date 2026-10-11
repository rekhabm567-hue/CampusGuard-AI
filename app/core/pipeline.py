# ============================================================
# LLM HALLUCINATION FIREWALL
# CENTRAL END-TO-END PIPELINE
#
# question -> authorization -> query understanding ->
# authorized-only retrieval -> rerank -> relevance filter ->
# rule-conflict check -> generation -> claim verification ->
# citation validation -> final answer or abstention -> audit
# ============================================================

import json
import re
import time

from app.database.audit_log import log_event
from app.firewall.citations import extract_citations, validate_citations
from app.firewall.claim_extractor import ClaimExtractor
from app.firewall.nli import create_entailment_fn
from app.firewall.verifier import (
    PARTIALLY_SUPPORTED,
    SUPPORTED,
    UNVERIFIED,
    ClaimVerifier,
    _is_minimum_rule,
    extract_thresholds,
    overall_status,
)
from app.llm.generator import AnswerGenerator
from app.llm.prompting import PromptBuilder
from app.retrieval.authorized_retrieval import AuthorizedRetrieval
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.query_understanding import QueryUnderstanding
from app.retrieval.reranker import CrossEncoderReranker

ABSTAIN_MESSAGE = (
    "I could not verify this answer from the authorized college "
    "documents currently available."
)

_AUTO = object()

_ABSTENTION_START = re.compile(
    r"^\s*(?:i\s+could\s+not\s+find|i\s+cannot\s+(?:answer|find)|"
    r"the\s+(?:available\s+)?documents?\s+do(?:es)?\s+not)",
    re.IGNORECASE,
)

STOP_WORDS = {
    "what", "is", "are", "the", "a", "an", "of", "to", "for", "in", "on",
    "and", "or", "can", "does", "do", "this", "that", "with", "be",
    "about", "how", "who", "which", "tell", "me", "please",
}


def find_rule_conflicts(documents):
    """Stopgap conflict check.

    Different source files stating rule-style percentages with no value
    in common are reported as a conflict needing administrator review.
    """

    by_source = {}

    for document in documents:
        source = (
            document.get("file_path")
            or document.get("title")
            or document.get("chunk_id")
        )

        for value in extract_thresholds(document.get("text", "")):
            by_source.setdefault(source, {}).setdefault(value, document)

    if len(by_source) < 2:
        return {"has_conflict": False, "values": [], "message": None}

    common = set.intersection(*(set(v) for v in by_source.values()))

    if common:
        return {"has_conflict": False, "values": [], "message": None}

    values = []

    for source_values in by_source.values():
        for value, document in sorted(source_values.items()):
            values.append(
                {
                    "value": value,
                    "title": document.get("title")
                    or document.get("file_name"),
                    "version": document.get("version"),
                    "effective_date": document.get("effective_date"),
                    "chunk_id": document.get("chunk_id"),
                }
            )

    return {
        "has_conflict": True,
        "values": values,
        "message": (
            "Different authorized documents state different percentage "
            "rules for this topic."
        ),
    }


class HallucinationFirewallPipeline:

    def __init__(
        self,
        generator=None,
        reranker=None,
        entailment_fn=_AUTO,
        embedding_engine=None,
        audit_fn=None,
        top_k_retrieve=8,
        top_k_evidence=5,
    ):
        self.query_understanding = QueryUnderstanding()
        self.authorized_retrieval = AuthorizedRetrieval()
        self.claim_extractor = ClaimExtractor()
        self.prompt_builder = PromptBuilder()

        self.generator = generator or AnswerGenerator()
        self.reranker = reranker or CrossEncoderReranker()
        self.embedding_engine = embedding_engine
        self.audit_fn = audit_fn or log_event

        self.top_k_retrieve = top_k_retrieve
        self.top_k_evidence = top_k_evidence

        self._entailment_fn = entailment_fn
        self._verifier = None

    # ========================================================
    # HELPERS
    # ========================================================

    def _get_verifier(self):

        if self._verifier is None:
            entailment_fn = self._entailment_fn

            if entailment_fn is _AUTO:
                entailment_fn = create_entailment_fn()

            self._verifier = ClaimVerifier(entailment_fn=entailment_fn)

        return self._verifier

    def _tokenize(self, text):

        if not text:
            return set()

        return {
            word
            for word in re.findall(r"\b[a-zA-Z0-9]+\b", text.lower())
            if word not in STOP_WORDS
        }

    def _is_relevant_document(self, query, document):

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return False

        title = str(
            document.get("title", document.get("file_name", ""))
        )
        text = str(document.get("text", ""))

        if query_tokens & self._tokenize(title):
            return True

        return len(query_tokens & self._tokenize(text)) >= 2

    def _filter_relevant_evidence(self, query, documents):

        return [
            document
            for document in (documents or [])
            if self._is_relevant_document(query, document)
        ]

    def _result(self, status, answer, reason, **extra):

        result = {
            "status": status,
            "answer": answer,
            "evidence": [],
            "claims": [],
            "reason": reason,
        }
        result.update(extra)

        return result

    def _eligibility_check(self, query_context, evidence):
        """Deterministic: the student's % in the question vs one minimum."""

        value = query_context.get("attendance")

        if value is None:
            return None

        rules = {}

        for document in evidence:
            for threshold in extract_thresholds(document.get("text", "")):
                if _is_minimum_rule(document, threshold):
                    rules.setdefault(threshold, []).append(document)

        if len(rules) != 1:
            return None

        threshold, documents = next(iter(rules.items()))
        document = documents[0]

        return {
            "student_value": value,
            "minimum": threshold,
            "meets_minimum": value >= threshold,
            "title": document.get("title") or document.get("file_name"),
            "chunk_id": document.get("chunk_id"),
            "version": document.get("version"),
            "page": document.get("page"),
        }

    def _attached_citations(self, claim_results):

        seen = set()
        citations = []

        for claim in claim_results:
            for ref in claim.get("supporting", []):
                key = ref.get("chunk_id") or ref.get("title")

                if key in seen:
                    continue

                seen.add(key)
                citations.append(
                    {
                        "chunk_id": ref.get("chunk_id"),
                        "title": ref.get("title"),
                        "file_path": ref.get("file_path"),
                        "page": ref.get("page"),
                        "version": ref.get("version"),
                        "attached_by": "system",
                    }
                )

        return citations

    # ========================================================
    # PROCESS QUERY
    # ========================================================

    def process_query(self, user, query, documents):

        started = time.perf_counter()

        result = self._run(user, query, documents)

        result["latency_ms"] = round(
            (time.perf_counter() - started) * 1000
        )

        self._audit(user, result)

        return result

    def _audit(self, user, result):

        try:
            details = json.dumps(
                {
                    "status": result.get("status"),
                    "evidence": len(result.get("evidence", [])),
                    "claims": len(result.get("claims", [])),
                    "overall": result.get("overall"),
                    "provider": result.get("provider"),
                    "reranker": result.get("reranker"),
                    "latency_ms": result.get("latency_ms"),
                }
            )

            self.audit_fn(
                "query",
                (user or {}).get("username"),
                details,
            )
        except Exception:
            pass

    def _run(self, user, query, documents):

        if not user:
            return self._result(
                "ACCESS DENIED",
                "Authentication is required.",
                "No authenticated user was provided.",
            )

        if not query or not query.strip():
            return self._result(
                "BLOCKED", "Please enter a question.", "Empty query."
            )

        query_context = self.query_understanding.understand(query)

        # ---------------- clarifying question ----------------

        if query_context.get("ambiguous"):
            return self._result(
                "AMBIGUOUS",
                "I need a clarification before answering. "
                + "; ".join(query_context["ambiguous"])
                + ". Please rephrase the question so it covers only one.",
                "The question is ambiguous.",
                query_context=query_context,
            )

        # ---------------- authorization (before retrieval) ----------------

        documents = [d for d in (documents or []) if isinstance(d, dict)]

        authorized = self.authorized_retrieval.filter_documents(
            user,
            documents,
            academic_year=query_context.get("academic_year"),
            department=query_context.get("department"),
        )

        if not authorized:
            return self._result(
                "ACCESS DENIED",
                "The required information is not available to your "
                "account.",
                "No authorized documents matched the request.",
                query_context=query_context,
            )

        # ---------------- retrieval: authorized documents only ----------------

        search = HybridSearch(embedding_engine=self.embedding_engine)
        search.add_documents(authorized)

        retrieved = search.search(query, top_k=self.top_k_retrieve)

        if not retrieved:
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                "No relevant evidence was retrieved.",
                query_context=query_context,
            )

        reranked = self.reranker.rerank(
            query, retrieved, top_k=self.top_k_retrieve
        )

        reranker_name = (
            reranked[0].get("reranker") if reranked else None
        )

        relevant = self._filter_relevant_evidence(query, reranked)[
            : self.top_k_evidence
        ]

        if not relevant:
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                "The retrieved evidence does not contain the concepts "
                "the question asks about.",
                query_context=query_context,
                reranker=reranker_name,
            )

        # ---------------- rule conflicts between documents ----------------

        conflict = find_rule_conflicts(relevant)

        if conflict["has_conflict"]:

            lines = [
                f"- {item['value']:g}% in {item['title']}"
                f" (version {item.get('version') or 'unknown'}, "
                f"effective {item.get('effective_date') or 'unknown'})"
                for item in conflict["values"]
            ]

            return self._result(
                "AMBIGUOUS",
                "I cannot give a definitive answer because the "
                "authorized documents state different rules:\n"
                + "\n".join(lines)
                + "\nAn administrator needs to review which rule "
                "governs.",
                conflict["message"],
                evidence=relevant,
                conflicts=conflict["values"],
                query_context=query_context,
                reranker=reranker_name,
            )

        # ---------------- generation ----------------

        usable = self.prompt_builder.usable_evidence(relevant)

        provider = getattr(self.generator, "provider", None)
        provider_info = (
            provider.describe()["name"]
            if hasattr(provider, "describe")
            else None
        )

        try:
            answer = self.generator.generate(query, usable)["answer"]
        except Exception:
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                "The answer generator did not return a usable answer.",
                evidence=relevant,
                query_context=query_context,
                provider=provider_info,
                reranker=reranker_name,
            )

        common = {
            "evidence": relevant,
            "query_context": query_context,
            "provider": provider_info,
            "reranker": reranker_name,
        }

        eligibility = self._eligibility_check(query_context, relevant)

        if _ABSTENTION_START.match(answer):
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                "The answer generator reported insufficient evidence.",
                eligibility_check=eligibility,
                **common,
            )

        # ---------------- claim verification ----------------

        claims = self.claim_extractor.extract(answer)

        verifier = self._get_verifier()

        claim_results = verifier.verify_claims(claims, usable)

        for claim in claim_results:
            claim["supported"] = claim["status"] in (
                SUPPORTED,
                PARTIALLY_SUPPORTED,
            )
            claim["score"] = max(
                (r.get("relevance", 0.0) for r in claim["related"]),
                default=0.0,
            )

        common["claims"] = claim_results
        common["nli_used"] = verifier.entailment_fn is not None

        if not claim_results:
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                "No verifiable claims were found in the generated answer.",
                rejected_answer=answer,
                eligibility_check=eligibility,
                **common,
            )

        overall = overall_status(claim_results)
        common["overall"] = overall

        # ---------------- citations ----------------

        citation_check = None

        if extract_citations(answer):
            citation_check = validate_citations(answer, usable)

            if citation_check["invalid"]:
                return self._result(
                    "BLOCKED",
                    ABSTAIN_MESSAGE,
                    "The answer cites sources that were not supplied "
                    f"(invalid citation(s): {citation_check['invalid']}).",
                    rejected_answer=answer,
                    citation_check=citation_check,
                    eligibility_check=eligibility,
                    **common,
                )

            citations = citation_check["cited_documents"]
        else:
            citations = self._attached_citations(claim_results)

        common["citations"] = citations
        common["citation_check"] = citation_check
        common["eligibility_check"] = eligibility

        # ---------------- final decision ----------------

        statuses = [c["status"] for c in claim_results]

        summary = (
            f"{statuses.count(SUPPORTED)} supported, "
            f"{statuses.count(PARTIALLY_SUPPORTED)} partially supported, "
            f"{statuses.count(UNVERIFIED)} unverified, "
            f"{statuses.count('contradicted')} contradicted "
            f"of {len(statuses)} claim(s)."
        )

        if overall == "contradicted":
            reasons = [
                reason
                for claim in claim_results
                if claim["status"] == "contradicted"
                for reason in claim["reasons"]
            ]
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE
                + " The draft answer contradicted the source documents "
                "and was withheld.",
                " ".join(reasons) or summary,
                rejected_answer=answer,
                **common,
            )

        if overall == "unverified":
            return self._result(
                "BLOCKED",
                ABSTAIN_MESSAGE,
                summary,
                rejected_answer=answer,
                **common,
            )

        status = "VERIFIED" if overall == "verified" else "PARTIALLY VERIFIED"

        if (
            status == "VERIFIED"
            and citation_check is not None
            and citation_check["uncited_sentences"]
        ):
            status = "PARTIALLY VERIFIED"
            summary += " Some sentences carry no citation."

        final_answer = answer

        if eligibility:
            if eligibility["meets_minimum"]:
                final_answer += (
                    f"\n\nCheck: {eligibility['student_value']:g}% meets "
                    f"the {eligibility['minimum']:g}% minimum stated in "
                    f"{eligibility['title']}. Other eligibility "
                    "conditions are not covered by this check."
                )
            else:
                final_answer += (
                    f"\n\nCheck: {eligibility['student_value']:g}% is "
                    f"below the {eligibility['minimum']:g}% minimum "
                    f"stated in {eligibility['title']}, so this student "
                    "does not meet the standard attendance requirement."
                )

        return self._result(status, final_answer, summary, **common)


def create_firewall_pipeline():

    return HallucinationFirewallPipeline()
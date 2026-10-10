# ============================================================
# LLM HALLUCINATION FIREWALL
# CENTRAL END-TO-END PIPELINE
# ============================================================

import re

from app.retrieval.query_understanding import QueryUnderstanding
from app.retrieval.authorized_retrieval import AuthorizedRetrieval
from app.retrieval.hybrid_search import HybridSearch
from app.retrieval.reranker import EvidenceReranker

from app.firewall.contradiction_detector import ContradictionDetector
from app.firewall.claim_extractor import ClaimExtractor
from app.firewall.evidence_matcher import EvidenceMatcher
from app.firewall.decision import FirewallDecision

from app.llm.generator import AnswerGenerator


class HallucinationFirewallPipeline:

    def __init__(self):

        self.query_understanding = QueryUnderstanding()

        self.authorized_retrieval = (
            AuthorizedRetrieval()
        )

        self.hybrid_search = HybridSearch()

        self.reranker = EvidenceReranker()

        self.contradiction_detector = (
            ContradictionDetector()
        )

        self.claim_extractor = ClaimExtractor()

        self.evidence_matcher = EvidenceMatcher()

        self.firewall_decision = FirewallDecision()

        self.answer_generator = AnswerGenerator()

    # ========================================================
    # TOKENIZE QUERY FOR RELEVANCE CHECKING
    # ========================================================

    def _tokenize(self, text):

        if not text:
            return set()

        words = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text.lower()
        )

        stop_words = {
            "what",
            "is",
            "are",
            "the",
            "a",
            "an",
            "of",
            "to",
            "for",
            "in",
            "on",
            "and",
            "or",
            "can",
            "does",
            "do",
            "this",
            "that",
            "with",
            "be",
            "about",
            "how",
            "who",
            "which",
            "tell",
            "me",
            "please",
        }

        return {
            word
            for word in words
            if word not in stop_words
        }

    # ========================================================
    # CHECK WHETHER DOCUMENT IS ACTUALLY RELEVANT
    # ========================================================

    def _is_relevant_document(
        self,
        query,
        document
    ):

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return False

        title = str(
            document.get(
                "title",
                document.get(
                    "file_name",
                    ""
                )
            )
        )

        text = str(
            document.get(
                "text",
                ""
            )
        )

        title_tokens = self._tokenize(title)

        text_tokens = self._tokenize(text)

        title_overlap = (
            query_tokens.intersection(
                title_tokens
            )
        )

        text_overlap = (
            query_tokens.intersection(
                text_tokens
            )
        )

        # ----------------------------------------------------
        # Strong title match
        #
        # Example:
        # Query: "employee rules"
        # Title: "Employee Rules and Regulations"
        # ----------------------------------------------------

        if len(title_overlap) >= 1:
            return True

        # ----------------------------------------------------
        # Strong content match
        #
        # Require at least two meaningful query concepts
        # to avoid unrelated documents being included.
        # ----------------------------------------------------

        if len(text_overlap) >= 2:
            return True

        return False

    # ========================================================
    # FILTER RETRIEVED DOCUMENTS
    # ========================================================

    def _filter_relevant_evidence(
        self,
        query,
        documents
    ):

        if not documents:
            return []

        relevant_documents = []

        for document in documents:

            if self._is_relevant_document(
                query,
                document
            ):
                relevant_documents.append(
                    document
                )

        return relevant_documents

    # ========================================================
    # PROCESS QUERY
    # ========================================================

    def process_query(
        self,
        user,
        query,
        documents
    ):

        # ----------------------------------------------------
        # Authentication check
        # ----------------------------------------------------

        if not user:

            return {
                "status": "ACCESS DENIED",
                "answer": "Authentication is required.",
                "evidence": [],
                "claims": [],
                "reason": (
                    "No authenticated user was provided."
                )
            }

        # ----------------------------------------------------
        # Empty query check
        # ----------------------------------------------------

        if not query or not query.strip():

            return {
                "status": "BLOCKED",
                "answer": "Please enter a question.",
                "evidence": [],
                "claims": [],
                "reason": "Empty query."
            }

        # ----------------------------------------------------
        # Understand query
        # ----------------------------------------------------

        query_context = (
            self.query_understanding.understand(
                query
            )
        )

        # ----------------------------------------------------
        # Authorization + metadata filtering
        # ----------------------------------------------------

        authorized_documents = (
            self.authorized_retrieval.filter_documents(
                user,
                documents,
                academic_year=query_context.get(
                    "academic_year"
                ),
                department=query_context.get(
                    "department"
                )
            )
        )

        if not authorized_documents:

            return {
                "status": "ACCESS DENIED",
                "answer": (
                    "The required information is not "
                    "available to your account."
                ),
                "evidence": [],
                "claims": [],
                "reason": (
                    "No authorized documents matched "
                    "the request."
                ),
                "query_context": query_context,
            }

        # ----------------------------------------------------
        # Build search index only from authorized documents
        # ----------------------------------------------------

        self.hybrid_search = HybridSearch()

        self.hybrid_search.add_documents(
            authorized_documents
        )

        # ----------------------------------------------------
        # Hybrid search
        # ----------------------------------------------------

        retrieved_documents = (
            self.hybrid_search.search(
                query,
                top_k=8
            )
        )

        if not retrieved_documents:

            return {
                "status": "BLOCKED",
                "answer": (
                    "I could not find sufficient evidence "
                    "to answer this question."
                ),
                "evidence": [],
                "claims": [],
                "reason": (
                    "No relevant evidence was retrieved."
                ),
                "query_context": query_context,
            }

        # ----------------------------------------------------
        # Re-ranking
        # ----------------------------------------------------

        reranked_documents = (
            self.reranker.rerank(
                query,
                retrieved_documents,
                top_k=8
            )
        )

        # ----------------------------------------------------
        # IMPORTANT:
        # Remove semantically similar but actually unrelated
        # documents.
        # ----------------------------------------------------

        relevant_documents = (
            self._filter_relevant_evidence(
                query,
                reranked_documents
            )
        )

        # ----------------------------------------------------
        # No sufficiently relevant evidence
        # ----------------------------------------------------

        if not relevant_documents:

            return {
                "status": "BLOCKED",
                "answer": (
                    "I could not find sufficient evidence "
                    "in the authorized enterprise documents "
                    "to answer this question."
                ),
                "evidence": [],
                "claims": [],
                "reason": (
                    "The retrieved evidence does not contain "
                    "a specific concept required by the question."
                ),
                "query_context": query_context,
            }

        # ----------------------------------------------------
        # Keep only the strongest relevant evidence
        # ----------------------------------------------------

        relevant_documents = relevant_documents[:5]

        # ----------------------------------------------------
        # Detect contradictions
        # ----------------------------------------------------

        contradiction_result = (
            self.contradiction_detector.detect(
                relevant_documents
            )
        )

        if contradiction_result.get(
            "has_conflict"
        ):

            decision = (
                self.firewall_decision.decide(
                    [],
                    contradiction_result=(
                        contradiction_result
                    )
                )
            )

            return {
                "status": decision["status"],
                "answer": (
                    "I cannot provide a definitive answer "
                    "because conflicting requirements were "
                    "found in the applicable documents."
                ),
                "evidence": relevant_documents,
                "claims": [],
                "reason": decision["reason"],
                "query_context": query_context,
            }

        # ----------------------------------------------------
        # Generate answer using ONLY relevant evidence
        # ----------------------------------------------------

        generation_result = (
            self.answer_generator.generate(
                query,
                relevant_documents
            )
        )

        answer = generation_result["answer"]

        # ----------------------------------------------------
        # Extract claims
        # ----------------------------------------------------

        claims = (
            self.claim_extractor.extract(
                answer
            )
        )

        # ----------------------------------------------------
        # Verify every claim against evidence
        # ----------------------------------------------------

        claim_results = (
            self.evidence_matcher.match_all_claims(
                claims,
                relevant_documents
            )
        )

        # ----------------------------------------------------
        # Final firewall decision
        # ----------------------------------------------------

        decision = (
            self.firewall_decision.decide(
                claim_results,
                contradiction_result=None
            )
        )

        # ----------------------------------------------------
        # Return complete result
        # ----------------------------------------------------

        return {
            "status": decision["status"],
            "answer": answer,
            "evidence": relevant_documents,
            "claims": claim_results,
            "reason": decision["reason"],
            "query_context": query_context,
        }


def create_firewall_pipeline():

    return HallucinationFirewallPipeline()
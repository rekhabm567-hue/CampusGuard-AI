# ============================================================
# EVIDENCE RE-RANKER
# LLM HALLUCINATION FIREWALL
# ============================================================

import re


class EvidenceReranker:

    def __init__(self):
        pass

    def _tokenize(self, text):
        if not text:
            return set()

        return set(
            re.findall(
                r"\b[a-zA-Z0-9]+\b",
                text.lower()
            )
        )

    def _keyword_overlap(self, query, document_text):
        query_tokens = self._tokenize(query)
        document_tokens = self._tokenize(
            document_text
        )

        if not query_tokens:
            return 0.0

        overlap = query_tokens.intersection(
            document_tokens
        )

        return len(overlap) / len(query_tokens)

    def rerank(self, query, results, top_k=5):

        if not results:
            return []

        reranked_results = []

        for result in results:

            hybrid_score = float(
                result.get(
                    "hybrid_score",
                    0.0
                )
            )

            overlap_score = (
                self._keyword_overlap(
                    query,
                    result.get("text", "")
                )
            )

            final_score = (
                0.7 * hybrid_score
                +
                0.3 * overlap_score
            )

            updated_result = result.copy()

            updated_result[
                "keyword_overlap"
            ] = overlap_score

            updated_result[
                "rerank_score"
            ] = final_score

            reranked_results.append(
                updated_result
            )

        reranked_results.sort(
            key=lambda result:
            result["rerank_score"],
            reverse=True
        )

        return reranked_results[:top_k]


def create_reranker():
    return EvidenceReranker()
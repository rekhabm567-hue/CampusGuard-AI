# ============================================================
# HYBRID SEARCH ENGINE
# LLM HALLUCINATION FIREWALL
# ============================================================

from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.vector_store import VectorStore
from app.retrieval.keyword_search import KeywordSearch


class HybridSearch:

    def __init__(self):
        self.embedding_engine = EmbeddingEngine()

        self.vector_store = VectorStore(
            self.embedding_engine.get_embedding_dimension()
        )

        self.keyword_search = KeywordSearch()

    def add_documents(self, documents):
        if not documents:
            return

        texts = [
            document.get("text", "")
            for document in documents
        ]

        embeddings = (
            self.embedding_engine.encode_documents(
                texts
            )
        )

        self.vector_store.add_documents(
            embeddings,
            documents
        )

        self.keyword_search.add_documents(
            documents
        )

    def search(
        self,
        query,
        top_k=5,
        semantic_weight=0.6,
        keyword_weight=0.4
    ):
        if not query or not query.strip():
            return []

        semantic_results = self.vector_store.search(
            self.embedding_engine.encode_text(query),
            top_k=top_k
        )

        keyword_results = self.keyword_search.search(
            query,
            top_k=top_k
        )

        combined = {}

        for result in semantic_results:
            key = result.get("text", "")

            combined[key] = {
                **result,
                "semantic_score": result.get(
                    "score",
                    0.0
                ),
                "keyword_score": 0.0,
            }

        for result in keyword_results:
            key = result.get("text", "")

            if key not in combined:
                combined[key] = {
                    **result,
                    "semantic_score": 0.0,
                    "keyword_score": 0.0,
                }

            combined[key]["keyword_score"] = (
                result.get(
                    "keyword_score",
                    0.0
                )
            )

        results = list(combined.values())

        if not results:
            return []

        max_semantic = max(
            result["semantic_score"]
            for result in results
        )

        max_keyword = max(
            result["keyword_score"]
            for result in results
        )

        for result in results:

            if max_semantic > 0:
                normalized_semantic = (
                    result["semantic_score"]
                    / max_semantic
                )
            else:
                normalized_semantic = 0.0

            if max_keyword > 0:
                normalized_keyword = (
                    result["keyword_score"]
                    / max_keyword
                )
            else:
                normalized_keyword = 0.0

            result["hybrid_score"] = (
                semantic_weight
                * normalized_semantic
                +
                keyword_weight
                * normalized_keyword
            )

        results.sort(
            key=lambda result:
            result["hybrid_score"],
            reverse=True
        )

        return results[:top_k]


def create_hybrid_search():
    return HybridSearch()
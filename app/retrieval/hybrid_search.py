# ============================================================
# HYBRID SEARCH ENGINE
# LLM HALLUCINATION FIREWALL
#
# Dense (FAISS) + lexical (BM25) retrieval, fused with
# Reciprocal Rank Fusion (RRF). Chunks are identified by
# source file + content hash, so identical text from two
# different documents is never merged.
# ============================================================

import hashlib

from app.retrieval.embeddings import EmbeddingEngine
from app.retrieval.vector_store import VectorStore
from app.retrieval.keyword_search import KeywordSearch

RRF_K = 60

_ENGINE_CACHE = {}


def get_embedding_engine(model_name="all-MiniLM-L6-v2"):
    """Load the embedding model once per process."""

    if model_name not in _ENGINE_CACHE:
        _ENGINE_CACHE[model_name] = EmbeddingEngine(model_name)

    return _ENGINE_CACHE[model_name]


def chunk_key(document):
    """Stable identity: source file + chunk id/index + text hash."""

    source = str(
        document.get("file_path")
        or document.get("title")
        or ""
    )

    chunk_part = str(
        document.get("chunk_id")
        if document.get("chunk_id") is not None
        else document.get("chunk_index", "")
    )

    text_hash = hashlib.sha256(
        str(document.get("text", "")).encode("utf-8")
    ).hexdigest()[:16]

    return f"{source}|{chunk_part}|{text_hash}"


class HybridSearch:

    def __init__(
        self,
        embedding_engine=None,
        rrf_k=RRF_K,
        candidate_multiplier=3,
    ):
        self.embedding_engine = (
            embedding_engine or get_embedding_engine()
        )

        self.vector_store = VectorStore(
            self.embedding_engine.get_embedding_dimension()
        )

        self.keyword_search = KeywordSearch()

        self.rrf_k = rrf_k
        self.candidate_multiplier = candidate_multiplier

    def add_documents(self, documents):
        if not documents:
            return

        documents = list(documents)

        texts = [
            document.get("text", "")
            for document in documents
        ]

        embeddings = self.embedding_engine.encode_documents(
            texts
        )

        self.vector_store.add_documents(
            documents,
            embeddings,
        )

        self.keyword_search.add_documents(
            documents
        )

    def search(
        self,
        query,
        top_k=5,
        semantic_weight=1.0,
        keyword_weight=1.0,
    ):
        """Return the top_k chunks ranked by weighted RRF."""

        if not query or not query.strip():
            return []

        candidates = max(
            int(top_k) * self.candidate_multiplier,
            int(top_k),
        )

        semantic_results = self.vector_store.search(
            self.embedding_engine.encode_text(query),
            top_k=candidates,
        )

        keyword_results = [
            result
            for result in self.keyword_search.search(
                query,
                top_k=candidates,
            )
            # Zero BM25 score means no lexical match at all.
            if result.get("keyword_score", 0.0) > 0
        ]

        combined = {}

        def merge(results, rank_field, weight):
            for rank, result in enumerate(results, start=1):
                key = chunk_key(result)

                entry = combined.setdefault(
                    key,
                    {
                        **result,
                        "chunk_key": key,
                        "semantic_score": 0.0,
                        "keyword_score": 0.0,
                        "semantic_rank": None,
                        "keyword_rank": None,
                        "rrf_score": 0.0,
                    },
                )

                if "semantic_score" in result:
                    entry["semantic_score"] = result["semantic_score"]

                if "keyword_score" in result:
                    entry["keyword_score"] = result["keyword_score"]

                entry[rank_field] = rank
                entry["rrf_score"] += weight / (self.rrf_k + rank)

        merge(semantic_results, "semantic_rank", semantic_weight)
        merge(keyword_results, "keyword_rank", keyword_weight)

        results = list(combined.values())

        if not results:
            return []

        results.sort(
            key=lambda result: result["rrf_score"],
            reverse=True,
        )

        # Scale to 0-1 so the existing reranker weights still make
        # sense. Kept under the old field name for compatibility.
        top_score = results[0]["rrf_score"] or 1.0

        for result in results:
            result["hybrid_score"] = result["rrf_score"] / top_score

        return results[:top_k]


def create_hybrid_search():
    return HybridSearch()
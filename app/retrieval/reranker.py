# ============================================================
# EVIDENCE RE-RANKERS
# LLM HALLUCINATION FIREWALL
#
# EvidenceReranker      : fast word-overlap reranker (baseline)
# CrossEncoderReranker  : cross-encoder model, falls back to
#                         EvidenceReranker if the model can't load.
# Both expose rerank(query, results, top_k).
# ============================================================

import logging
import math
import re

logger = logging.getLogger(__name__)

DEFAULT_CROSS_ENCODER = "cross-encoder/ms-marco-MiniLM-L-6-v2"


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

            updated_result["keyword_overlap"] = overlap_score
            updated_result["rerank_score"] = final_score
            updated_result["reranker"] = "overlap"

            reranked_results.append(
                updated_result
            )

        reranked_results.sort(
            key=lambda result:
            result["rerank_score"],
            reverse=True
        )

        return reranked_results[:top_k]


_MODEL_CACHE = {}


def _load_cross_encoder(model_name):
    """Load once per process. Returns None if loading fails."""

    if model_name not in _MODEL_CACHE:
        try:
            from sentence_transformers import CrossEncoder

            _MODEL_CACHE[model_name] = CrossEncoder(model_name)
        except Exception as error:
            logger.warning(
                "Cross-encoder %s could not be loaded (%s). "
                "Using the overlap reranker instead.",
                model_name,
                error,
            )
            _MODEL_CACHE[model_name] = None

    return _MODEL_CACHE[model_name]


def _sigmoid(value):
    return 1.0 / (1.0 + math.exp(-float(value)))


class CrossEncoderReranker:

    def __init__(self, model_name=DEFAULT_CROSS_ENCODER, model=None):
        self.model_name = model_name
        self._model = model
        self._fallback = EvidenceReranker()

    @property
    def model(self):
        if self._model is None:
            self._model = _load_cross_encoder(self.model_name)
        return self._model

    def rerank(self, query, results, top_k=5):

        if not results:
            return []

        model = self.model

        if model is None:
            return self._fallback.rerank(query, results, top_k=top_k)

        pairs = [
            (query, result.get("text", ""))
            for result in results
        ]

        scores = model.predict(pairs)

        reranked_results = []

        for result, score in zip(results, scores):
            updated = result.copy()
            updated["cross_encoder_score"] = float(score)
            updated["rerank_score"] = _sigmoid(score)
            updated["reranker"] = "cross_encoder"
            reranked_results.append(updated)

        reranked_results.sort(
            key=lambda result: result["rerank_score"],
            reverse=True,
        )

        return reranked_results[:top_k]


def create_reranker():
    return EvidenceReranker()


def create_cross_encoder_reranker():
    return CrossEncoderReranker()
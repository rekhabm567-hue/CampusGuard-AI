import app.retrieval.reranker as reranker_module
from app.retrieval.reranker import (
    CrossEncoderReranker,
    EvidenceReranker,
)


class FakeModel:
    """Scores a pair by how many query words the text contains."""

    def predict(self, pairs):
        scores = []
        for query, text in pairs:
            words = set(query.lower().split())
            scores.append(float(len(words & set(text.lower().split()))))
        return scores


RESULTS = [
    {"text": "library opens at nine", "hybrid_score": 0.9},
    {"text": "attendance requirement is seventy five", "hybrid_score": 0.5},
]


def test_cross_encoder_reorders_by_model_score():
    reranker = CrossEncoderReranker(model=FakeModel())
    out = reranker.rerank("attendance requirement", RESULTS, top_k=2)
    assert out[0]["text"].startswith("attendance")
    assert out[0]["reranker"] == "cross_encoder"
    assert "cross_encoder_score" in out[0]
    assert 0.0 < out[0]["rerank_score"] < 1.0


def test_top_k_and_empty_input():
    reranker = CrossEncoderReranker(model=FakeModel())
    assert len(reranker.rerank("attendance", RESULTS, top_k=1)) == 1
    assert reranker.rerank("attendance", []) == []


def test_fallback_when_model_cannot_load(monkeypatch):
    monkeypatch.setattr(
        reranker_module, "_load_cross_encoder", lambda name: None
    )
    reranker = CrossEncoderReranker(model_name="does-not-exist")
    out = reranker.rerank("attendance requirement", RESULTS, top_k=2)
    assert out
    assert out[0]["reranker"] == "overlap"


def test_overlap_reranker_unchanged_interface():
    out = EvidenceReranker().rerank("attendance", RESULTS, top_k=2)
    assert "rerank_score" in out[0] and "keyword_overlap" in out[0]
    assert out[0]["reranker"] == "overlap"
import numpy as np

from app.retrieval.hybrid_search import HybridSearch, chunk_key


class FakeEngine:
    """Deterministic 4-dim embeddings based on a few keywords."""

    KEYWORDS = ["attendance", "library", "fees", "exam"]

    def get_embedding_dimension(self):
        return 4

    def _vector(self, text):
        text = str(text).lower()
        vector = np.array(
            [1.0 if word in text else 0.0 for word in self.KEYWORDS],
            dtype="float32",
        )
        norm = np.linalg.norm(vector)
        if norm == 0:
            vector[0] = 0.01
            norm = np.linalg.norm(vector)
        return vector / norm

    def encode_documents(self, texts):
        return np.array([self._vector(t) for t in texts])

    def encode_text(self, text):
        return self._vector(text).reshape(1, -1)


def make_search(docs):
    search = HybridSearch(embedding_engine=FakeEngine())
    search.add_documents(docs)
    return search


DOCS = [
    {"text": "Students need 75 percent attendance to write exams.",
     "file_path": "a.txt", "chunk_id": 0},
    {"text": "Library hours are 9 to 5.",
     "file_path": "b.txt", "chunk_id": 0},
    {"text": "Hostel fees are due in July.",
     "file_path": "c.txt", "chunk_id": 0},
]


def test_relevant_chunk_ranks_first():
    results = make_search(DOCS).search("attendance requirement", top_k=2)
    assert results[0]["file_path"] == "a.txt"


def test_identical_text_from_two_documents_is_not_merged():
    docs = [
        {"text": "Attendance must be 75 percent.",
         "file_path": "policy_v1.txt", "chunk_id": 0},
        {"text": "Attendance must be 75 percent.",
         "file_path": "policy_v2.txt", "chunk_id": 0},
    ]
    results = make_search(docs).search("attendance", top_k=5)
    assert {r["file_path"] for r in results} == {
        "policy_v1.txt", "policy_v2.txt"
    }


def test_chunk_key_differs_by_source():
    a = {"text": "same", "file_path": "x.txt", "chunk_id": 0}
    b = {"text": "same", "file_path": "y.txt", "chunk_id": 0}
    assert chunk_key(a) != chunk_key(b)


def test_results_carry_scores_and_ranks():
    result = make_search(DOCS).search("attendance", top_k=1)[0]
    for field in ("rrf_score", "hybrid_score", "semantic_score",
                  "keyword_score", "chunk_key"):
        assert field in result
    assert 0.0 < result["hybrid_score"] <= 1.0


def test_empty_and_blank_queries():
    search = make_search(DOCS)
    assert search.search("") == []
    assert search.search("   ") == []


def test_no_documents():
    search = HybridSearch(embedding_engine=FakeEngine())
    assert search.search("attendance") == []


def test_top_k_is_respected():
    assert len(make_search(DOCS).search("attendance", top_k=2)) <= 2


def test_keyword_only_match_still_found():
    docs = [
        {"text": "Form 17B must be filed.", "file_path": "f.txt",
         "chunk_id": 0},
        {"text": "Library hours are 9 to 5.", "file_path": "l.txt",
         "chunk_id": 0},
    ]
    results = make_search(docs).search("17B", top_k=2)
    assert results[0]["file_path"] == "f.txt"
# ============================================================
# VECTOR STORE
# LLM HALLUCINATION FIREWALL
# ============================================================

from pathlib import Path

import faiss
import numpy as np


class VectorStore:

    def __init__(self, dimension=384):

        self.dimension = dimension

        self.index = faiss.IndexFlatIP(
            self.dimension
        )

        self.documents = []

    # ========================================================
    # CLEAR
    # ========================================================

    def clear(self):

        self.index = faiss.IndexFlatIP(
            self.dimension
        )

        self.documents = []

    # ========================================================
    # ADD DOCUMENTS
    #
    # documents  : list of dicts (one per chunk)
    # embeddings : array-like, shape (n_documents, dimension)
    # ========================================================

    def add_documents(
        self,
        documents,
        embeddings,
    ):

        if documents is None or embeddings is None:
            return

        documents = list(documents)

        if len(documents) == 0:
            return

        embeddings = np.asarray(
            embeddings,
            dtype="float32",
        )

        if embeddings.ndim == 1:

            embeddings = embeddings.reshape(
                1,
                -1,
            )

        if embeddings.ndim != 2:

            raise ValueError(
                "Embeddings must be a 2D array."
            )

        if embeddings.shape[1] != self.dimension:

            raise ValueError(
                "Embedding dimension mismatch: "
                f"expected {self.dimension}, "
                f"received {embeddings.shape[1]}"
            )

        if embeddings.shape[0] != len(documents):

            raise ValueError(
                "Number of embeddings does not match "
                "number of documents: "
                f"{embeddings.shape[0]} embeddings, "
                f"{len(documents)} documents."
            )

        self.index.add(
            embeddings
        )

        self.documents.extend(
            documents
        )

    # ========================================================
    # SEARCH
    # ========================================================

    def search(
        self,
        query_embedding,
        top_k=5,
    ):

        if len(self.documents) == 0:
            return []

        if query_embedding is None:
            return []

        query_embedding = np.asarray(
            query_embedding,
            dtype="float32",
        )

        query_embedding = np.squeeze(
            query_embedding
        )

        if query_embedding.ndim == 1:

            query_embedding = query_embedding.reshape(
                1,
                -1,
            )

        if query_embedding.ndim != 2:

            raise ValueError(
                "Query embedding must be a 2D array."
            )

        if query_embedding.shape[1] != self.dimension:

            raise ValueError(
                "Query embedding dimension mismatch: "
                f"expected {self.dimension}, "
                f"received {query_embedding.shape[1]}"
            )

        top_k = min(
            int(top_k),
            len(self.documents),
        )

        if top_k <= 0:
            return []

        scores, indexes = self.index.search(
            query_embedding,
            top_k,
        )

        results = []

        for score, index in zip(
            scores[0],
            indexes[0],
        ):

            if index < 0:
                continue

            if index >= len(self.documents):
                continue

            document = dict(
                self.documents[index]
            )

            document["semantic_score"] = float(
                score
            )

            results.append(
                document
            )

        return results

    # ========================================================
    # SAVE
    # ========================================================

    def save(
        self,
        index_path,
    ):

        index_path = Path(
            index_path
        )

        index_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        faiss.write_index(
            self.index,
            str(index_path),
        )

    # ========================================================
    # LOAD
    # ========================================================

    def load(
        self,
        index_path,
    ):

        index_path = Path(
            index_path
        )

        if not index_path.exists():
            return False

        self.index = faiss.read_index(
            str(index_path)
        )

        return True


# ============================================================
# FACTORY
# ============================================================

def create_vector_store(
    dimension=384,
):

    return VectorStore(
        dimension=dimension
    )
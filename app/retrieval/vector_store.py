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
    # Supports:
    #
    # add_documents(documents, embeddings)
    # add_documents(embeddings, documents)
    # ========================================================

    def add_documents(
        self,
        first,
        second,
    ):

        if first is None or second is None:
            return

        # ----------------------------------------------------
        # Identify which argument is embeddings
        # ----------------------------------------------------

        first_array = np.asarray(
            first,
            dtype="float32",
        )

        second_array = np.asarray(
            second,
            dtype="float32",
        )

        if (
            first_array.ndim >= 1
            and first_array.size > 0
            and first_array.shape[-1] == self.dimension
        ):

            embeddings = first_array
            documents = second

        else:

            documents = first
            embeddings = second_array

        # ----------------------------------------------------
        # Validate documents
        # ----------------------------------------------------

        if documents is None:
            return

        documents = list(documents)

        if len(documents) == 0:
            return

        # ----------------------------------------------------
        # Normalize embedding shape
        # ----------------------------------------------------

        embeddings = np.asarray(
            embeddings,
            dtype="float32",
        )

        embeddings = np.squeeze(
            embeddings
        )

        if embeddings.ndim == 1:

            embeddings = embeddings.reshape(
                1,
                -1,
            )

        # ----------------------------------------------------
        # Validate dimension
        # ----------------------------------------------------

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

        # ----------------------------------------------------
        # Validate count
        # ----------------------------------------------------

        if embeddings.shape[0] != len(documents):

            raise ValueError(
                "Number of embeddings does not match "
                "number of documents: "
                f"{embeddings.shape[0]} embeddings, "
                f"{len(documents)} documents."
            )

        # ----------------------------------------------------
        # Add to FAISS
        # ----------------------------------------------------

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
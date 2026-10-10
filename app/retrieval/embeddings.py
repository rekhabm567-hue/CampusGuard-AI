# ============================================================
# EMBEDDING ENGINE
# LLM HALLUCINATION FIREWALL
# ============================================================

from sentence_transformers import SentenceTransformer


class EmbeddingEngine:

    def __init__(
        self,
        model_name="all-MiniLM-L6-v2",
    ):
        self.model_name = model_name

        self.model = SentenceTransformer(
            self.model_name
        )

    # ========================================================
    # ENCODE TEXT
    # ========================================================

    def encode(self, texts):

        if isinstance(texts, str):
            texts = [texts]

        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
        )

    # ========================================================
    # ENCODE TEXT - COMPATIBILITY METHOD
    # ========================================================

    def encode_text(self, text):

        return self.encode(text)

    # ========================================================
    # ENCODE DOCUMENTS
    # ========================================================

    def encode_documents(self, documents):

        if not documents:
            return []

        texts = []

        for document in documents:

            if isinstance(document, dict):

                text = document.get(
                    "text",
                    "",
                )

            else:

                text = str(document)

            texts.append(
                str(text)
            )

        return self.encode(texts)

    # ========================================================
    # ENCODE QUERY
    # ========================================================

    def encode_query(self, query):

        return self.encode(query)

    # ========================================================
    # GET EMBEDDING DIMENSION
    # ========================================================

    def get_embedding_dimension(self):

        return self.model.get_embedding_dimension()

    # ========================================================
    # COMPATIBILITY METHOD
    # ========================================================

    def dimension(self):

        return self.get_embedding_dimension()


# ============================================================
# COMPATIBILITY CLASS
# ============================================================

class EmbeddingModel(EmbeddingEngine):
    pass


# ============================================================
# FACTORY
# ============================================================

def create_embedding_model():

    return EmbeddingModel()
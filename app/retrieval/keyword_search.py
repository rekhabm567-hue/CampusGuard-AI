# ============================================================
# KEYWORD SEARCH ENGINE
# LLM HALLUCINATION FIREWALL
# ============================================================

import re

from rank_bm25 import BM25Okapi


class KeywordSearch:

    def __init__(self):
        self.documents = []
        self.bm25 = None

    def _tokenize(self, text):
        if not text:
            return []

        text = text.lower()

        # Keep words and numbers as separate searchable tokens
        tokens = re.findall(
            r"\b[a-zA-Z0-9]+\b",
            text
        )

        return tokens

    def add_documents(self, documents):
        self.documents = list(documents)

        if not self.documents:
            self.bm25 = None
            return

        tokenized_documents = [
            self._tokenize(
                document.get("text", "")
            )
            for document in self.documents
        ]

        self.bm25 = BM25Okapi(
            tokenized_documents
        )

    def search(self, query, top_k=5):

        if not self.documents or self.bm25 is None:
            return []

        query_tokens = self._tokenize(query)

        if not query_tokens:
            return []

        scores = self.bm25.get_scores(
            query_tokens
        )

        ranked_indexes = sorted(
            range(len(scores)),
            key=lambda index: scores[index],
            reverse=True
        )

        results = []

        for index in ranked_indexes[:top_k]:

            document = self.documents[index].copy()

            document["keyword_score"] = float(
                scores[index]
            )

            results.append(document)

        return results

    def count(self):
        return len(self.documents)


def create_keyword_search():
    return KeywordSearch()
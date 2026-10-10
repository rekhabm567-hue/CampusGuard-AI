# ============================================================
# AUTHORIZATION-AWARE RETRIEVAL
# LLM HALLUCINATION FIREWALL
# ============================================================

from app.auth.authorization import (
    filter_authorized_documents,
)

from app.retrieval.metadata_filter import (
    MetadataFilter,
)


class AuthorizedRetrieval:

    def __init__(self):
        self.metadata_filter = MetadataFilter()

    def filter_documents(
        self,
        user,
        documents,
        academic_year=None,
        department=None,
    ):
        """
        Apply security filtering before retrieval.

        Flow:

            User
              ↓
            Authorization
              ↓
            Department / Academic-Year filtering
              ↓
            Authorized documents
        """

        if not user:
            return []

        if not documents:
            return []

        # ====================================================
        # STEP 1 — AUTHORIZATION FIREWALL
        # ====================================================

        authorized_documents = filter_authorized_documents(
            user,
            documents,
        )

        if not authorized_documents:
            return []

        # ====================================================
        # STEP 2 — METADATA FILTER
        # ====================================================

        filtered_documents = self.metadata_filter.apply(
            authorized_documents,
            academic_year=academic_year,
            department=department,
            role=user.get("role"),
        )

        # ====================================================
        # STEP 3 — SAFETY FALLBACK
        # ====================================================
        #
        # If the query did not actually specify a year or
        # department, metadata filtering should not remove
        # already-authorized documents because of missing
        # query metadata.
        #
        # We therefore only enforce filters when the query
        # understanding layer actually supplied them.
        # ====================================================

        if not academic_year and not department:
            return authorized_documents

        return filtered_documents


def create_authorized_retrieval():
    return AuthorizedRetrieval()
from app.auth.authorization import (
    filter_authorized_documents,
)

from app.retrieval.metadata_filter import MetadataFilter


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
        Filter documents using the authenticated user's
        permissions before searching.
        """

        if not isinstance(user, dict):
            return []

        if not documents:
            return []

        # Step 1: Apply authorization and document lifecycle checks.
        authorized_documents = filter_authorized_documents(
            user,
            documents,
        )

        if not authorized_documents:
            return []

        # Step 2: Apply optional query-specific filters.
        filtered_documents = self.metadata_filter.apply(
            authorized_documents,
            academic_year=academic_year,
            department=department,
            role=user.get("role"),
        )

        return filtered_documents


def create_authorized_retrieval():
    return AuthorizedRetrieval()
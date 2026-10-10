# ============================================================
# METADATA FILTER
# LLM HALLUCINATION FIREWALL
# ============================================================

GLOBAL_DEPARTMENTS = {
    "academic affairs",
    "administration",
    "college",
    "general",
    "all",
    "academic",
    "common",
}


class MetadataFilter:

    def __init__(self):
        pass

    # ========================================================
    # NORMALIZATION
    # ========================================================

    def _normalize(self, value):

        if value is None:
            return ""

        return str(value).strip().lower()

    # ========================================================
    # ACADEMIC YEAR FILTER
    # ========================================================

    def filter_by_academic_year(
        self,
        documents,
        academic_year,
    ):

        # No year in the question means do not filter.
        if academic_year is None:
            return list(documents)

        results = []

        try:
            requested_year = int(academic_year)
        except (TypeError, ValueError):
            return list(documents)

        for document in documents:

            document_year = document.get(
                "academic_year"
            )

            # If a document has no academic year,
            # don't discard it when it has already passed
            # authorization.
            if document_year is None:
                results.append(document)
                continue

            try:
                document_year = int(
                    document_year
                )
            except (TypeError, ValueError):

                # Keep documents with malformed metadata
                # rather than silently removing authorized
                # evidence.
                results.append(document)
                continue

            if document_year == requested_year:
                results.append(document)

        return results

    # ========================================================
    # DEPARTMENT FILTER
    # ========================================================

    def filter_by_department(
        self,
        documents,
        department,
    ):

        # No department in the question means no department
        # filtering.
        if not department:
            return list(documents)

        requested_department = self._normalize(
            department
        )

        results = []

        for document in documents:

            document_department = self._normalize(
                document.get("department")
            )

            # Missing department metadata should not destroy
            # an already-authorized document.
            if not document_department:
                results.append(document)
                continue

            # College-wide / global documents.
            if document_department in GLOBAL_DEPARTMENTS:
                results.append(document)
                continue

            # Exact department match.
            if (
                document_department
                == requested_department
            ):
                results.append(document)

        return results

    # ========================================================
    # ROLE FILTER
    # ========================================================

    def filter_by_role(
        self,
        documents,
        role,
    ):

        # No role means no additional filtering.
        if not role:
            return list(documents)

        requested_role = self._normalize(
            role
        )

        results = []

        for document in documents:

            # Admin can access documents that already passed
            # the authorization firewall.
            if requested_role == "admin":
                results.append(document)
                continue

            allowed_roles = document.get(
                "allowed_roles"
            )

            # ------------------------------------------------
            # IMPORTANT:
            #
            # Older documents may not contain allowed_roles.
            # They have already passed the authorization
            # firewall, so don't reject them here.
            # ------------------------------------------------

            if not allowed_roles:
                results.append(document)
                continue

            if isinstance(
                allowed_roles,
                str,
            ):

                allowed_roles = [
                    item.strip().lower()
                    for item in allowed_roles.split(",")
                    if item.strip()
                ]

            elif isinstance(
                allowed_roles,
                (list, tuple, set),
            ):

                allowed_roles = [
                    str(item).strip().lower()
                    for item in allowed_roles
                    if str(item).strip()
                ]

            else:

                # Unknown metadata format.
                # Don't destroy an already-authorized document.
                results.append(document)
                continue

            # Explicit wildcard access.
            if "all" in allowed_roles:
                results.append(document)
                continue

            if "*" in allowed_roles:
                results.append(document)
                continue

            # Explicit role authorization.
            if requested_role in allowed_roles:
                results.append(document)

        return results

    # ========================================================
    # APPLY ALL FILTERS
    # ========================================================

    def apply(
        self,
        documents,
        academic_year=None,
        department=None,
        role=None,
    ):

        if not documents:
            return []

        filtered_documents = list(
            documents
        )

        # ----------------------------------------------------
        # 1. Academic year
        # ----------------------------------------------------

        filtered_documents = (
            self.filter_by_academic_year(
                filtered_documents,
                academic_year,
            )
        )

        if not filtered_documents:
            return []

        # ----------------------------------------------------
        # 2. Department
        # ----------------------------------------------------

        filtered_documents = (
            self.filter_by_department(
                filtered_documents,
                department,
            )
        )

        if not filtered_documents:
            return []

        # ----------------------------------------------------
        # 3. Role
        # ----------------------------------------------------

        filtered_documents = (
            self.filter_by_role(
                filtered_documents,
                role,
            )
        )

        return filtered_documents


# ============================================================
# FACTORY
# ============================================================

def create_metadata_filter():

    return MetadataFilter()
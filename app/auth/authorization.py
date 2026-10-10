# ============================================================
# AUTHORIZATION
# LLM HALLUCINATION FIREWALL
# ============================================================

ROLE_PERMISSIONS = {
    "admin": {
        "documents.read",
        "documents.upload",
        "documents.manage",
        "users.manage",
        "audit.view",
    },

    "faculty": {
        "documents.read",
        "documents.upload",
    },

    "student": {
        "documents.read",
    },

    "staff": {
        "documents.read",
    },
}


ROLE_LEVELS = {
    "student": 1,
    "staff": 2,
    "faculty": 3,
    "admin": 4,
}


GLOBAL_DEPARTMENTS = {
    "academic affairs",
    "administration",
    "college",
    "general",
    "all",
    "academic",
    "common",
}


def _normalize(value):
    """
    Normalize a value for reliable authorization comparison.
    """

    if value is None:
        return ""

    return str(value).strip().lower()


def _normalize_roles(allowed_roles):
    """
    Convert allowed_roles into a clean list of role names.
    """

    if not allowed_roles:
        return []

    if isinstance(allowed_roles, str):

        # Support:
        # "student,faculty"
        # "student, faculty"
        # "student"
        roles = allowed_roles.split(",")

    elif isinstance(allowed_roles, (list, tuple, set)):

        roles = list(allowed_roles)

    else:
        return []

    return [
        _normalize(role)
        for role in roles
        if _normalize(role)
    ]


def has_permission(role, permission):
    """
    Check whether a role has a particular permission.
    """

    role = _normalize(role)
    permission = _normalize(permission)

    if not role or not permission:
        return False

    permissions = ROLE_PERMISSIONS.get(
        role,
        set()
    )

    return permission in permissions


def get_permissions(role):
    """
    Return all permissions assigned to a role.
    """

    role = _normalize(role)

    if not role:
        return set()

    return ROLE_PERMISSIONS.get(
        role,
        set()
    )


def is_valid_role(role):
    """
    Check whether the supplied role exists.
    """

    role = _normalize(role)

    return role in ROLE_PERMISSIONS


def has_role_level(role, required_role):
    """
    Compare role hierarchy.
    """

    role = _normalize(role)
    required_role = _normalize(required_role)

    if not role or not required_role:
        return False

    user_level = ROLE_LEVELS.get(
        role,
        0
    )

    required_level = ROLE_LEVELS.get(
        required_role,
        0
    )

    return user_level >= required_level


def _department_matches(user_department, document_department):
    """
    Check whether the user's department can access the
    document's department.
    """

    user_department = _normalize(
        user_department
    )

    document_department = _normalize(
        document_department
    )

    # A document without department information is treated
    # as a general document.
    if not document_department:
        return True

    # Global / college-wide documents.
    if document_department in GLOBAL_DEPARTMENTS:
        return True

    # Department-specific document.
    if not user_department:
        return False

    return (
        user_department
        == document_department
    )


def can_access_document(user, document):
    """
    Determine whether the authenticated user can access
    a particular document.

    Authorization order:

        User
          ↓
        Role
          ↓
        Department
          ↓
        Document role restrictions
    """

    if not user or not document:
        return False

    role = _normalize(
        user.get("role")
    )

    if not role:
        return False

    # --------------------------------------------------------
    # Validate user role
    # --------------------------------------------------------

    if not is_valid_role(role):
        return False

    # --------------------------------------------------------
    # Admin bypass
    # --------------------------------------------------------

    # Administrators are allowed to access all enterprise
    # documents.
    if role == "admin":
        return True

    # --------------------------------------------------------
    # Department authorization
    # --------------------------------------------------------

    user_department = _normalize(
        user.get("department")
    )

    document_department = _normalize(
        document.get("department")
    )

    if not _department_matches(
        user_department,
        document_department
    ):
        return False

    # --------------------------------------------------------
    # Role authorization
    # --------------------------------------------------------

    allowed_roles = _normalize_roles(
        document.get("allowed_roles")
    )

    # --------------------------------------------------------
    # Important compatibility rule
    # --------------------------------------------------------
    #
    # Older uploaded documents may not have allowed_roles
    # stored in their metadata.
    #
    # In that case:
    #
    #   - Same department -> allowed
    #   - Global document -> allowed
    #
    # Explicit role restrictions are still enforced when
    # allowed_roles is actually present.
    #
    # This allows older/demo documents to continue working
    # without removing RBAC from documents that define it.
    # --------------------------------------------------------

    if not allowed_roles:

        # If there is no explicit role restriction and the
        # department already passed authorization, allow access.
        return True

    # Explicit role restriction.
    if role in allowed_roles:
        return True

    # Support wildcard access.
    if "all" in allowed_roles:
        return True

    if "*" in allowed_roles:
        return True

    return False


def filter_authorized_documents(
    user,
    documents
):
    """
    Return only documents the current user is authorized
    to access.
    """

    if not user:
        return []

    if not documents:
        return []

    authorized_documents = []

    for document in documents:

        if not isinstance(document, dict):
            continue

        if can_access_document(
            user,
            document
        ):
            authorized_documents.append(
                document
            )

    return authorized_documents


def get_authorized_document_count(
    user,
    documents
):
    """
    Return the number of documents accessible
    to the current user.
    """

    return len(
        filter_authorized_documents(
            user,
            documents
        )
    )


def can_upload_document(user):
    """
    Check whether the current user can upload documents.
    """

    if not user:
        return False

    role = _normalize(
        user.get("role")
    )

    return has_permission(
        role,
        "documents.upload"
    )


def can_manage_documents(user):
    """
    Check whether the current user can manage documents.
    """

    if not user:
        return False

    role = _normalize(
        user.get("role")
    )

    return has_permission(
        role,
        "documents.manage"
    )


def can_manage_users(user):
    """
    Check whether the current user can manage users.
    """

    if not user:
        return False

    role = _normalize(
        user.get("role")
    )

    return has_permission(
        role,
        "users.manage"
    )


def can_view_audit_logs(user):
    """
    Check whether the current user can view audit logs.
    """

    if not user:
        return False

    role = _normalize(
        user.get("role")
    )

    return has_permission(
        role,
        "audit.view"
    )
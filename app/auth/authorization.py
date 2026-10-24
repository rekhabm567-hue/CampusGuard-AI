from datetime import date, datetime


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

VISIBLE_STATUSES = {"official"}

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
    if value is None:
        return ""

    return str(value).strip().lower()


def _normalize_roles(allowed_roles):
    if isinstance(allowed_roles, str):
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


def _parse_date(value):
    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    if not value:
        return None

    try:
        return date.fromisoformat(str(value).strip())
    except (ValueError, TypeError):
        return None


def has_permission(role, permission):
    role = _normalize(role)
    permission = _normalize(permission)

    return permission in ROLE_PERMISSIONS.get(role, set())


def get_permissions(role):
    return ROLE_PERMISSIONS.get(_normalize(role), set())


def is_valid_role(role):
    return _normalize(role) in ROLE_PERMISSIONS


def has_role_level(role, required_role):
    levels = {
        "student": 1,
        "staff": 2,
        "faculty": 3,
        "admin": 4,
    }

    role = _normalize(role)
    required_role = _normalize(required_role)

    if role not in levels or required_role not in levels:
        return False

    return levels[role] >= levels[required_role]


def is_document_active(document, today=None):
    if not isinstance(document, dict):
        return False

    today = today or date.today()

    if _normalize(document.get("status")) not in VISIBLE_STATUSES:
        return False

    if _normalize(document.get("superseded_by")):
        return False

    effective_date = _parse_date(
        document.get("effective_date")
    )

    # Missing or invalid effective date: deny access.
    if effective_date is None or effective_date > today:
        return False

    expiration_value = document.get("expiration_date")

    if expiration_value:
        expiration_date = _parse_date(expiration_value)

        if expiration_date is None or expiration_date < today:
            return False

    return True


def _department_matches(user_department, document_department):
    user_department = _normalize(user_department)
    document_department = _normalize(document_department)

    if not document_department:
        return False

    if document_department in GLOBAL_DEPARTMENTS:
        return True

    if not user_department:
        return False

    return user_department == document_department


def can_access_document(user, document):
    """
    Determine whether the authenticated user can access a document.
    """

    if not isinstance(user, dict):
        return False

    if not isinstance(document, dict):
        return False

    role = _normalize(user.get("role"))

    if role not in ROLE_PERMISSIONS:
        return False

    # Admin has access to documents, subject to document lifecycle checks.
    if role == "admin":
        return True

    # A document must explicitly specify its permitted roles.
    allowed_roles = _normalize_roles(
        document.get("allowed_roles")
    )

    if not allowed_roles:
        return False

    # Check the authenticated user's role.
    if role not in allowed_roles and "all" not in allowed_roles and "*" not in allowed_roles:
        return False

    # Enforce department restrictions.
    if not _department_matches(
        user.get("department"),
        document.get("department"),
    ):
        return False

    return True


def filter_authorized_documents(user, documents, today=None):
    """
    Return only documents that the user can access
    and that are currently official and active.
    """

    if not isinstance(user, dict):
        return []

    if not documents:
        return []

    return [
        document
        for document in documents
        if isinstance(document, dict)
        and can_access_document(user, document)
        and is_document_active(document, today=today)
    ]


def get_authorized_document_count(user, documents):
    return len(filter_authorized_documents(user, documents))


def _role_has(user, permission):
    if not isinstance(user, dict):
        return False

    return has_permission(user.get("role"), permission)


def can_upload_document(user):
    return _role_has(user, "documents.upload")


def can_manage_documents(user):
    return _role_has(user, "documents.manage")


def can_manage_users(user):
    return _role_has(user, "users.manage")


def can_view_audit_logs(user):
    return _role_has(user, "audit.view")
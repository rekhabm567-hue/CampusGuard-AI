# ============================================================
# AUTHORIZATION (fail closed)
# LLM HALLUCINATION FIREWALL
#
# Two separate questions:
#   can_access_document : may this USER see this document?
#   is_document_active  : is the DOCUMENT currently authoritative?
# filter_authorized_documents requires both, for every role.
# Missing or malformed metadata means DENY.
# ============================================================

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

# Only these statuses may be used as evidence.
VISIBLE_STATUSES = {"official"}


def _normalize(value):
    if value is None:
        return ""
    return str(value).strip().lower()


def _normalize_roles(allowed_roles):
    """Return a clean list of role names, or [] if unusable."""

    if not allowed_roles:
        return []

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
    """Return a date, or None if missing or malformed."""

    if value is None or value == "":
        return None

    if isinstance(value, datetime):
        return value.date()

    if isinstance(value, date):
        return value

    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


# ============================================================
# PERMISSIONS
# ============================================================

def has_permission(role, permission):
    role = _normalize(role)
    permission = _normalize(permission)

    if not role or not permission:
        return False

    return permission in ROLE_PERMISSIONS.get(role, set())


def get_permissions(role):
    role = _normalize(role)

    if not role:
        return set()

    return ROLE_PERMISSIONS.get(role, set())


def is_valid_role(role):
    return _normalize(role) in ROLE_PERMISSIONS


def has_role_level(role, required_role):
    role = _normalize(role)
    required_role = _normalize(required_role)

    if not role or not required_role:
        return False

    return (
        ROLE_LEVELS.get(role, 0)
        >= ROLE_LEVELS.get(required_role, 0)
    )


# ============================================================
# DOCUMENT LIFECYCLE
# ============================================================

def is_document_active(document, today=None):
    """True only for official, in-date, non-superseded documents."""

    if not isinstance(document, dict):
        return False

    today = today or date.today()

    if _normalize(document.get("status")) not in VISIBLE_STATUSES:
        return False

    if _normalize(document.get("superseded_by")):
        return False

    effective = _parse_date(document.get("effective_date"))

    if effective is None or effective > today:
        return False

    raw_expiration = document.get("expiration_date")

    if raw_expiration not in (None, ""):
        expiration = _parse_date(raw_expiration)

        # Malformed expiration date: deny.
        if expiration is None or expiration < today:
            return False

    return True


# ============================================================
# USER ACCESS
# ============================================================

def _department_matches(user_department, document_department):
    user_department = _normalize(user_department)
    document_department = _normalize(document_department)

    # Missing document department: deny.
    if not document_department:
        return False

    if document_department in GLOBAL_DEPARTMENTS:
        return True

    if not user_department:
        return False

    return user_department == document_department


def can_access_document(user, document):
    """May this user see this document? (Not a lifecycle check.)"""

    if not user or not isinstance(document, dict):
        return False

    role = _normalize(user.get("role"))

    if not is_valid_role(role):
        return False

    # Administrators may see every document.
    if role == "admin":
        return True

    if not _department_matches(
        user.get("department"),
        document.get("department"),
    ):
        return False

    allowed_roles = _normalize_roles(
        document.get("allowed_roles")
    )

    # Missing or unreadable role list: deny.
    if not allowed_roles:
        return False

    return (
        role in allowed_roles
        or "all" in allowed_roles
        or "*" in allowed_roles
    )


def filter_authorized_documents(user, documents, today=None):
    """Documents this user may see AND that are currently active."""

    if not user or not documents:
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


# ============================================================
# ACTION CHECKS
# ============================================================

def _role_has(user, permission):
    if not user:
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
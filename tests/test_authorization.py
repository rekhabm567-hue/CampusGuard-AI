from datetime import date

import pytest

from app.auth.authorization import (
    can_access_document,
    filter_authorized_documents,
    has_permission,
    is_document_active,
)

TODAY = date(2026, 10, 10)

STUDENT_CSE = {"role": "student", "department": "CSE"}
STUDENT_ECE = {"role": "student", "department": "ECE"}
FACULTY_CSE = {"role": "faculty", "department": "CSE"}
STAFF_CSE = {"role": "staff", "department": "CSE"}
ADMIN = {"role": "admin", "department": None}


def make_doc(**overrides):
    doc = {
        "title": "Doc",
        "department": "CSE",
        "allowed_roles": ["student", "faculty", "staff"],
        "status": "official",
        "effective_date": "2026-06-01",
    }
    doc.update(overrides)
    return doc


def test_permissions():
    assert has_permission("admin", "documents.manage")
    assert has_permission("faculty", "documents.upload")
    assert has_permission("student", "documents.read")
    assert not has_permission("student", "documents.manage")
    assert not has_permission("staff", "documents.upload")
    assert not has_permission("unknown", "documents.read")


# ---------------- user access ----------------

def test_same_department_allowed():
    assert can_access_document(STUDENT_CSE, make_doc())


def test_other_department_denied():
    assert not can_access_document(STUDENT_ECE, make_doc())
    assert not can_access_document(
        STUDENT_CSE, make_doc(department="Finance")
    )


def test_department_match_is_case_insensitive():
    assert can_access_document(STUDENT_CSE, make_doc(department="cse"))


def test_global_department_allowed_for_any_department():
    doc = make_doc(department="Academic Affairs")
    assert can_access_document(STUDENT_ECE, doc)
    assert can_access_document(STUDENT_CSE, doc)


def test_missing_department_denied():
    assert not can_access_document(
        STUDENT_CSE, make_doc(department=None)
    )
    assert not can_access_document(
        STUDENT_CSE, make_doc(department="")
    )


@pytest.mark.parametrize("roles", [None, [], "", 5, {"a": 1}])
def test_missing_or_unreadable_allowed_roles_denied(roles):
    assert not can_access_document(
        STUDENT_CSE, make_doc(allowed_roles=roles)
    )


def test_role_restriction():
    doc = make_doc(allowed_roles=["faculty"])
    assert not can_access_document(STUDENT_CSE, doc)
    assert not can_access_document(STAFF_CSE, doc)
    assert can_access_document(FACULTY_CSE, doc)


def test_allowed_roles_as_comma_string():
    doc = make_doc(allowed_roles="student, faculty")
    assert can_access_document(STUDENT_CSE, doc)
    assert not can_access_document(STAFF_CSE, doc)


def test_wildcard_roles():
    assert can_access_document(
        STAFF_CSE, make_doc(allowed_roles=["all"])
    )


def test_admin_can_access_regardless_of_metadata():
    assert can_access_document(
        ADMIN, make_doc(department=None, allowed_roles=None)
    )


def test_invalid_users_denied():
    assert not can_access_document(None, make_doc())
    assert not can_access_document({}, make_doc())
    assert not can_access_document(
        {"role": "hacker", "department": "CSE"}, make_doc()
    )
    assert not can_access_document(STUDENT_CSE, None)


# ---------------- document lifecycle ----------------

def test_official_in_date_document_is_active():
    assert is_document_active(make_doc(), today=TODAY)


@pytest.mark.parametrize("status", ["draft", "archived", "", None, "weird"])
def test_non_official_status_inactive(status):
    assert not is_document_active(make_doc(status=status), today=TODAY)


def test_missing_status_key_inactive():
    doc = make_doc()
    del doc["status"]
    assert not is_document_active(doc, today=TODAY)


def test_expired_document_inactive():
    doc = make_doc(expiration_date="2026-09-30")
    assert not is_document_active(doc, today=TODAY)


def test_document_expiring_today_still_active():
    doc = make_doc(expiration_date="2026-10-10")
    assert is_document_active(doc, today=TODAY)


def test_superseded_document_inactive():
    doc = make_doc(superseded_by="Attendance Policy v3")
    assert not is_document_active(doc, today=TODAY)


def test_future_effective_date_inactive():
    doc = make_doc(effective_date="2026-12-01")
    assert not is_document_active(doc, today=TODAY)


def test_missing_effective_date_inactive():
    doc = make_doc(effective_date=None)
    assert not is_document_active(doc, today=TODAY)


@pytest.mark.parametrize("bad", ["not-a-date", "01/06/2026", "2026-13-45"])
def test_malformed_dates_inactive(bad):
    assert not is_document_active(
        make_doc(effective_date=bad), today=TODAY
    )
    assert not is_document_active(
        make_doc(expiration_date=bad), today=TODAY
    )


# ---------------- combined filter ----------------

def test_filter_applies_access_and_lifecycle():
    docs = [
        make_doc(title="ok"),
        make_doc(title="faculty only", allowed_roles=["faculty"]),
        make_doc(title="other dept", department="Finance"),
        make_doc(title="draft", status="draft"),
        make_doc(title="expired", expiration_date="2026-01-01"),
        make_doc(title="superseded", superseded_by="v2"),
        make_doc(title="no roles", allowed_roles=None),
    ]
    result = filter_authorized_documents(STUDENT_CSE, docs, today=TODAY)
    assert [d["title"] for d in result] == ["ok"]


def test_filter_excludes_inactive_documents_even_for_admin():
    docs = [
        make_doc(title="ok"),
        make_doc(title="draft", status="draft"),
        make_doc(title="superseded", superseded_by="v2"),
    ]
    result = filter_authorized_documents(ADMIN, docs, today=TODAY)
    assert [d["title"] for d in result] == ["ok"]


def test_filter_cross_role_matrix():
    docs = [
        make_doc(title="all roles"),
        make_doc(title="faculty only", allowed_roles=["faculty"]),
        make_doc(title="staff only", allowed_roles=["staff"]),
    ]

    def titles(user):
        return sorted(
            d["title"]
            for d in filter_authorized_documents(user, docs, today=TODAY)
        )

    assert titles(STUDENT_CSE) == ["all roles"]
    assert titles(FACULTY_CSE) == ["all roles", "faculty only"]
    assert titles(STAFF_CSE) == ["all roles", "staff only"]
    assert titles(STUDENT_ECE) == []
    assert titles(ADMIN) == ["all roles", "faculty only", "staff only"]


def test_filter_handles_bad_input():
    assert filter_authorized_documents(None, [make_doc()]) == []
    assert filter_authorized_documents(STUDENT_CSE, None) == []
    assert filter_authorized_documents(
        STUDENT_CSE, ["not a dict", None], today=TODAY
    ) == []
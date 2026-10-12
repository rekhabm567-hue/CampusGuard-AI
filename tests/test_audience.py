from datetime import date

from app.auth.authorization import filter_authorized_documents

TODAY = date(2026, 10, 12)

EMPLOYEE = {
    "title": "Employee Leave Policy",
    "department": "Administration",
    "allowed_roles": ["faculty", "staff"],
    "status": "official",
    "effective_date": "2026-01-01",
}

STUDENT_LEAVE = {
    "title": "Student Leave Policy",
    "department": "Academic Affairs",
    "allowed_roles": ["student"],
    "status": "official",
    "effective_date": "2026-01-01",
}

DOCS = [EMPLOYEE, STUDENT_LEAVE]


def titles(user):
    return [
        d["title"]
        for d in filter_authorized_documents(user, DOCS, today=TODAY)
    ]


def test_student_sees_only_student_leave():
    assert titles({"role": "student", "department": "CSE"}) == [
        "Student Leave Policy"
    ]


def test_faculty_and_staff_see_only_employee_leave():
    assert titles({"role": "faculty", "department": "ECE"}) == [
        "Employee Leave Policy"
    ]
    assert titles({"role": "staff", "department": "CSE"}) == [
        "Employee Leave Policy"
    ]


def test_admin_sees_both():
    assert sorted(titles({"role": "admin", "department": None})) == [
        "Employee Leave Policy",
        "Student Leave Policy",
    ]
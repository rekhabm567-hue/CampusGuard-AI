from app.auth.authorization import (
    has_permission,
    can_access_document,
    filter_authorized_documents,
)


def test_permissions():

    assert has_permission(
        "admin",
        "documents.manage"
    )

    assert has_permission(
        "faculty",
        "documents.upload"
    )

    assert has_permission(
        "student",
        "documents.read"
    )

    assert not has_permission(
        "student",
        "documents.manage"
    )


def test_document_access():

    student = {
        "username": "student",
        "role": "student",
        "department": "CSE",
    }

    cse_document = {
        "title": "CSE Attendance Policy",
        "allowed_roles": [
            "student",
            "faculty"
        ],
        "department": "CSE",
    }

    finance_document = {
        "title": "Finance Department Policy",
        "allowed_roles": [
            "student",
            "faculty"
        ],
        "department": "Finance",
    }

    assert can_access_document(
        student,
        cse_document
    )

    assert not can_access_document(
        student,
        finance_document
    )


def test_document_filter():

    student = {
        "username": "student",
        "role": "student",
        "department": "CSE",
    }

    documents = [

        {
            "title": "CSE Attendance Policy",
            "allowed_roles": [
                "student",
                "faculty"
            ],
            "department": "CSE",
        },

        {
            "title": "CSE Faculty Guidelines",
            "allowed_roles": [
                "faculty"
            ],
            "department": "CSE",
        },

        {
            "title": "Finance Policy",
            "allowed_roles": [
                "student"
            ],
            "department": "Finance",
        },
    ]

    authorized = filter_authorized_documents(
        student,
        documents
    )

    assert len(authorized) == 1

    assert authorized[0]["title"] == (
        "CSE Attendance Policy"
    )


if __name__ == "__main__":

    test_permissions()
    test_document_access()
    test_document_filter()

    print(
        "Authorization tests passed successfully."
    )
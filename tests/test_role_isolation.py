import json

import numpy as np

from app.auth.authorization import filter_authorized_documents
from app.core.pipeline import HallucinationFirewallPipeline
from app.llm.generator import AnswerGenerator
from app.llm.provider import LLMProvider
from app.retrieval.reranker import EvidenceReranker


def make_doc(title, roles, secret, department="Administration"):
    return {
        "title": title,
        "department": department,
        "allowed_roles": roles,
        "status": "official",
        "effective_date": "2020-01-01",
        "file_path": f"data/{title}.txt",
        "chunk_id": f"{title}_1",
        "text": f"{secret} marks submission workload rules for members.",
    }


STUDENT_DOC = make_doc("Student Rules", ["student"], "SECRET-STUDENT")
FACULTY_DOC = make_doc("Faculty Rules", ["faculty"], "SECRET-FACULTY")
STAFF_DOC = make_doc("Staff Rules", ["staff"], "SECRET-STAFF")
SHARED_DOC = make_doc(
    "Shared Notice", ["student", "faculty", "staff"], "SECRET-SHARED"
)
DOCS = [STUDENT_DOC, FACULTY_DOC, STAFF_DOC, SHARED_DOC]

USERS = {
    "student": {"username": "s", "role": "student", "department": "CSE"},
    "faculty": {"username": "f", "role": "faculty", "department": "CSE"},
    "staff": {"username": "t", "role": "staff", "department": "CSE"},
    "admin": {"username": "a", "role": "admin", "department": None},
}


def titles(role):
    return sorted(
        d["title"] for d in filter_authorized_documents(USERS[role], DOCS)
    )


def test_each_role_sees_only_its_own_and_shared_documents():
    assert titles("student") == ["Shared Notice", "Student Rules"]
    assert titles("faculty") == ["Faculty Rules", "Shared Notice"]
    assert titles("staff") == ["Shared Notice", "Staff Rules"]


def test_admin_sees_every_active_document():
    assert titles("admin") == [
        "Faculty Rules", "Shared Notice", "Staff Rules", "Student Rules",
    ]


def test_inactive_documents_are_never_used_even_for_admin():
    draft = dict(FACULTY_DOC, title="Draft", status="draft")
    result = filter_authorized_documents(USERS["admin"], [draft])
    assert result == []


class FakeEngine:
    KEYWORDS = ["marks", "submission", "workload", "members"]

    def get_embedding_dimension(self):
        return 4

    def _vector(self, text):
        text = str(text).lower()
        vector = np.array(
            [1.0 if w in text else 0.0 for w in self.KEYWORDS],
            dtype="float32",
        )
        if not vector.any():
            vector[0] = 0.01
        return vector / np.linalg.norm(vector)

    def encode_documents(self, texts):
        return np.array([self._vector(t) for t in texts])

    def encode_text(self, text):
        return self._vector(text).reshape(1, -1)


class Recorder(LLMProvider):
    name = "test-recorder"

    def __init__(self):
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        return "Marks submission workload rules apply to members."


def ask(role):
    provider = Recorder()
    pipeline = HallucinationFirewallPipeline(
        generator=AnswerGenerator(provider=provider),
        reranker=EvidenceReranker(),
        entailment_fn=None,
        embedding_engine=FakeEngine(),
        audit_fn=lambda *args: None,
    )
    result = pipeline.process_query(
        USERS[role], "What are the marks submission workload rules?", DOCS
    )
    return " ".join(provider.prompts) + json.dumps(result, default=str)


def test_other_roles_text_never_reaches_the_model_or_the_result():
    forbidden = {
        "student": ["SECRET-FACULTY", "SECRET-STAFF"],
        "faculty": ["SECRET-STUDENT", "SECRET-STAFF"],
        "staff": ["SECRET-STUDENT", "SECRET-FACULTY"],
    }

    for role, secrets in forbidden.items():
        seen = ask(role)
        for secret in secrets:
            assert secret not in seen, f"{role} leaked {secret}"
import pytest

from app.database import database
from app.database import feedback as fb


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.db")
    database.initialize_database()
    fb.init_tables()
    yield


def test_history_is_private_to_each_user():
    fb.save_query("alice", "Q1?", "A1", "VERIFIED")
    fb.save_query("bob", "Q2?", "A2", "BLOCKED")

    alice = fb.get_history("alice")
    assert [h["question"] for h in alice] == ["Q1?"]
    assert fb.get_history("nobody") == []


def test_history_newest_first_and_limited():
    for i in range(5):
        fb.save_query("alice", f"Q{i}", "A", "VERIFIED")

    history = fb.get_history("alice", limit=3)
    assert [h["question"] for h in history] == ["Q4", "Q3", "Q2"]


def test_feedback_saved_and_counted():
    hid = fb.save_query("alice", "Q?", "A", "VERIFIED")

    assert fb.save_feedback(hid, "alice", 1, "good") is True

    summary = fb.get_feedback_summary()
    assert summary == {"up": 1, "down": 0, "total": 1}
    assert fb.get_recent_feedback()[0]["comment"] == "good"


def test_cannot_rate_someone_elses_answer():
    hid = fb.save_query("alice", "Q?", "A", "VERIFIED")

    assert fb.save_feedback(hid, "bob", -1) is False
    assert fb.get_feedback_summary()["total"] == 0


def test_only_one_feedback_per_answer():
    hid = fb.save_query("alice", "Q?", "A", "VERIFIED")

    assert fb.save_feedback(hid, "alice", 1) is True
    assert fb.save_feedback(hid, "alice", -1) is False


def test_invalid_rating_rejected():
    hid = fb.save_query("alice", "Q?", "A", "VERIFIED")

    with pytest.raises(ValueError):
        fb.save_feedback(hid, "alice", 5)


def test_unknown_history_id_rejected():
    assert fb.save_feedback(999, "alice", 1) is False


def test_long_comment_is_truncated():
    hid = fb.save_query("alice", "Q?", "A", "VERIFIED")
    fb.save_feedback(hid, "alice", 1, "x" * 2000)

    assert len(fb.get_recent_feedback()[0]["comment"]) == fb.MAX_COMMENT
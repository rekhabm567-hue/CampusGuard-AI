import pytest

from app.database import database
from app.auth import authentication
from app.auth.authentication import (
    MAX_FAILED_ATTEMPTS,
    authenticate_user,
    is_locked_out,
)
from app.auth.users import create_user, get_user


@pytest.fixture(autouse=True)
def temp_database(tmp_path, monkeypatch):
    monkeypatch.setattr(
        database, "DATABASE_PATH", tmp_path / "test.db"
    )
    database.initialize_database()
    yield


def _make_user(username="alice", password="correct-horse-1", role="student"):
    assert create_user(username, password, "Alice", role, "CSE")


def test_login_success_hides_password_hash():
    _make_user()
    user = authenticate_user("alice", "correct-horse-1")
    assert user is not None
    assert user["username"] == "alice"
    assert "password_hash" not in user


def test_wrong_password_rejected():
    _make_user()
    assert authenticate_user("alice", "wrong") is None


def test_unknown_user_rejected():
    assert authenticate_user("nobody", "whatever") is None


def test_empty_credentials_rejected():
    assert authenticate_user("", "") is None
    assert authenticate_user("alice", "") is None


def test_inactive_user_rejected():
    _make_user()
    connection = database.get_connection()
    connection.execute(
        "UPDATE users SET is_active = 0 WHERE username = 'alice'"
    )
    connection.commit()
    connection.close()
    assert authenticate_user("alice", "correct-horse-1") is None


def test_lockout_after_repeated_failures():
    _make_user()
    for _ in range(MAX_FAILED_ATTEMPTS):
        assert authenticate_user("alice", "wrong") is None
    assert is_locked_out("alice")
    # Even the correct password is refused while locked out.
    assert authenticate_user("alice", "correct-horse-1") is None


def test_lockout_does_not_affect_other_users():
    _make_user("alice")
    _make_user("bob")
    for _ in range(MAX_FAILED_ATTEMPTS):
        authenticate_user("alice", "wrong")
    assert authenticate_user("bob", "correct-horse-1") is not None


def test_duplicate_username_returns_false():
    _make_user()
    assert create_user("alice", "another-pass-1", "A2", "student") is False


def test_invalid_role_raises():
    with pytest.raises(ValueError):
        create_user("eve", "some-password-1", "Eve", "superuser")


def test_password_is_stored_hashed():
    _make_user()
    stored = get_user("alice")["password_hash"]
    assert stored != "correct-horse-1"
    assert stored.startswith("$2")
from datetime import datetime, timedelta, timezone

from app.auth.users import get_user
from app.core.security import verify_password
from app.database.audit_log import log_event
from app.database.database import get_connection, initialize_database

MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _window_start():
    start = datetime.now(timezone.utc) - timedelta(minutes=LOCKOUT_MINUTES)
    return start.strftime("%Y-%m-%d %H:%M:%S")


def _recent_failures(username):
    connection = get_connection()
    try:
        row = connection.execute(
            "SELECT COUNT(*) AS n FROM login_attempts "
            "WHERE username = ? AND success = 0 AND attempted_at >= ?",
            (username, _window_start()),
        ).fetchone()
        return row["n"]
    finally:
        connection.close()


def _record_attempt(username, success):
    connection = get_connection()
    try:
        connection.execute(
            "INSERT INTO login_attempts (username, success) VALUES (?, ?)",
            (username, 1 if success else 0),
        )
        connection.commit()
    finally:
        connection.close()


def is_locked_out(username):
    initialize_database()
    return _recent_failures(username) >= MAX_FAILED_ATTEMPTS


def authenticate_user(username, password):
    """Return the user (without password hash) or None."""

    initialize_database()

    username = (username or "").strip()

    if not username or not password:
        return None

    if is_locked_out(username):
        log_event("login_blocked_lockout", username)
        return None

    user = get_user(username)

    if user is None or not verify_password(
        password,
        user["password_hash"],
    ):
        _record_attempt(username, False)
        log_event("login_failed", username)
        return None

    if not user.get("is_active"):
        _record_attempt(username, False)
        log_event("login_blocked_inactive", username)
        return None

    _record_attempt(username, True)
    log_event("login_success", username)

    safe_user = dict(user)
    safe_user.pop("password_hash", None)

    return safe_user
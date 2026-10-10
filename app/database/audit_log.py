"""Audit log: append-only record of security-relevant events."""
from app.database.database import get_connection, initialize_database


def log_event(event_type, username=None, details=None):
    """Record an event. Never raises, so logging can't break a login."""
    try:
        initialize_database()
        connection = get_connection()
        try:
            connection.execute(
                "INSERT INTO audit_logs (event_type, username, details) "
                "VALUES (?, ?, ?)",
                (event_type, username, details),
            )
            connection.commit()
        finally:
            connection.close()
    except Exception:
        pass


def get_recent_events(limit=50):
    initialize_database()
    connection = get_connection()
    try:
        rows = connection.execute(
            "SELECT id, event_type, username, details, created_at "
            "FROM audit_logs ORDER BY id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        connection.close()
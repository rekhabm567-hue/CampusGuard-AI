"""Query history and answer feedback (SQLite)."""
from app.database.database import get_connection

MAX_QUESTION = 2000
MAX_ANSWER = 4000
MAX_COMMENT = 500


def init_tables():
    connection = get_connection()

    try:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS query_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT NOT NULL,
                question TEXT NOT NULL,
                answer TEXT,
                status TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS idx_history_user
            ON query_history (username, id)
        """)

        connection.execute("""
            CREATE TABLE IF NOT EXISTS feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                history_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                rating INTEGER NOT NULL CHECK (rating IN (-1, 1)),
                comment TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (history_id) REFERENCES query_history(id)
            )
        """)

        connection.commit()

    finally:
        connection.close()


def save_query(username, question, answer, status):
    """Store one question and its result. Returns the history id."""

    init_tables()
    connection = get_connection()

    try:
        cursor = connection.execute(
            "INSERT INTO query_history (username, question, answer, status) "
            "VALUES (?, ?, ?, ?)",
            (
                username,
                str(question)[:MAX_QUESTION],
                str(answer or "")[:MAX_ANSWER],
                status,
            ),
        )
        connection.commit()
        return cursor.lastrowid

    finally:
        connection.close()


def get_history(username, limit=50):
    """A user's own past questions, newest first."""

    init_tables()
    connection = get_connection()

    try:
        rows = connection.execute(
            "SELECT id, question, answer, status, created_at "
            "FROM query_history WHERE username = ? "
            "ORDER BY id DESC LIMIT ?",
            (username, int(limit)),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def save_feedback(history_id, username, rating, comment=""):
    """Record feedback. Returns False if it is not allowed.

    A user can only rate their own answers, and only once.
    """

    if rating not in (-1, 1):
        raise ValueError("rating must be 1 or -1")

    init_tables()
    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT username FROM query_history WHERE id = ?",
            (history_id,),
        ).fetchone()

        if row is None or row["username"] != username:
            return False

        existing = connection.execute(
            "SELECT 1 FROM feedback WHERE history_id = ?",
            (history_id,),
        ).fetchone()

        if existing:
            return False

        connection.execute(
            "INSERT INTO feedback (history_id, username, rating, comment) "
            "VALUES (?, ?, ?, ?)",
            (history_id, username, rating, str(comment or "")[:MAX_COMMENT]),
        )
        connection.commit()
        return True

    finally:
        connection.close()


def get_feedback_summary():
    init_tables()
    connection = get_connection()

    try:
        row = connection.execute(
            "SELECT "
            "COALESCE(SUM(CASE WHEN rating = 1 THEN 1 ELSE 0 END), 0) AS up, "
            "COALESCE(SUM(CASE WHEN rating = -1 THEN 1 ELSE 0 END), 0) AS down, "
            "COUNT(*) AS total FROM feedback"
        ).fetchone()

        return {"up": row["up"], "down": row["down"], "total": row["total"]}

    finally:
        connection.close()


def get_recent_feedback(limit=100):
    """For administrators."""

    init_tables()
    connection = get_connection()

    try:
        rows = connection.execute(
            "SELECT f.id, f.username, f.rating, f.comment, f.created_at, "
            "h.question, h.status "
            "FROM feedback f JOIN query_history h ON h.id = f.history_id "
            "ORDER BY f.id DESC LIMIT ?",
            (int(limit),),
        ).fetchall()

        return [dict(row) for row in rows]

    finally:
        connection.close()


def count_queries():
    init_tables()
    connection = get_connection()

    try:
        return connection.execute(
            "SELECT COUNT(*) AS n FROM query_history"
        ).fetchone()["n"]

    finally:
        connection.close()
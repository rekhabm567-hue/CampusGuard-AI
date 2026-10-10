# ============================================================
# USER MANAGEMENT
# LLM HALLUCINATION FIREWALL
# ============================================================

import sqlite3

from app.database.database import get_connection
from app.core.security import hash_password


VALID_ROLES = {"admin", "faculty", "student", "staff"}


# ============================================================
# CREATE USER
# ============================================================

def create_user(
    username,
    password,
    full_name,
    role,
    department=None,
):
    """Create a user.

    Returns True if created, False if the username already exists.
    Raises ValueError for invalid input and re-raises unexpected
    database errors.
    """

    username = (username or "").strip()

    if not username:
        raise ValueError("Username is required.")

    if not password:
        raise ValueError("Password is required.")

    if role not in VALID_ROLES:
        raise ValueError(f"Invalid role: {role}")

    connection = get_connection()

    try:

        connection.execute(
            """
            INSERT INTO users (
                username,
                password_hash,
                full_name,
                role,
                department
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username,
                hash_password(password),
                full_name,
                role,
                department,
            ),
        )

        connection.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        connection.close()


# ============================================================
# GET USER
# ============================================================

def get_user(username):

    connection = get_connection()

    try:

        row = connection.execute(
            """
            SELECT
                id,
                username,
                password_hash,
                full_name,
                role,
                department,
                is_active
            FROM users
            WHERE username = ?
            """,
            (username,),
        ).fetchone()

        if row is None:
            return None

        return {
            "id": row["id"],
            "username": row["username"],
            "password_hash": row["password_hash"],
            "full_name": row["full_name"],
            "role": row["role"],
            "department": row["department"],
            "is_active": row["is_active"],
        }

    finally:

        connection.close()


# ============================================================
# GET ALL USERS
# ============================================================

def get_all_users():

    connection = get_connection()

    try:

        rows = connection.execute(
            """
            SELECT
                id,
                username,
                full_name,
                role,
                department,
                is_active
            FROM users
            ORDER BY username
            """
        ).fetchall()

        users = []

        for row in rows:

            users.append(
                {
                    "id": row["id"],
                    "username": row["username"],
                    "full_name": row["full_name"],
                    "role": row["role"],
                    "department": row["department"],
                    "is_active": row["is_active"],
                }
            )

        return users

    finally:

        connection.close()
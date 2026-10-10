# ============================================================
# USER MANAGEMENT
# LLM HALLUCINATION FIREWALL
# ============================================================

from app.database.database import get_connection
from app.core.security import hash_password


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
    connection = get_connection()

    password_hash = hash_password(password)

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
                password_hash,
                full_name,
                role,
                department,
            ),
        )

        connection.commit()

        return True

    except Exception:

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
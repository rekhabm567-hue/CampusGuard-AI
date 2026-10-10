"""Seed demo users.

Passwords are never stored in source code. Each password is read from an
environment variable (see .env.example). If a variable is not set, a random
password is generated and printed once, only when the user is newly created.
"""
import os
import secrets

from dotenv import load_dotenv

from app.auth.users import create_user
from app.database.database import initialize_database

load_dotenv()

MIN_PASSWORD_LENGTH = 8

SEED_USERS = [
    {
        "username": "admin",
        "env_var": "SEED_ADMIN_PASSWORD",
        "full_name": "System Administrator",
        "role": "admin",
        "department": None,
    },
    {
        "username": "faculty",
        "env_var": "SEED_FACULTY_PASSWORD",
        "full_name": "Academic Faculty",
        "role": "faculty",
        "department": "CSE",
    },
    {
        "username": "student",
        "env_var": "SEED_STUDENT_PASSWORD",
        "full_name": "Aira Student",
        "role": "student",
        "department": "CSE",
    },
    {
        "username": "staff",
        "env_var": "SEED_STAFF_PASSWORD",
        "full_name": "Department Staff",
        "role": "staff",
        "department": "CSE",
    },
]


def seed_users():
    initialize_database()

    for user in SEED_USERS:
        password = os.getenv(user["env_var"])
        generated = False

        if not password:
            password = secrets.token_urlsafe(12)
            generated = True
        elif len(password) < MIN_PASSWORD_LENGTH:
            raise ValueError(
                f"{user['env_var']} must be at least "
                f"{MIN_PASSWORD_LENGTH} characters long."
            )

        created = create_user(
            username=user["username"],
            password=password,
            full_name=user["full_name"],
            role=user["role"],
            department=user["department"],
        )

        if created:
            print(f"Created: {user['username']} ({user['role']})")
            if generated:
                print(
                    f"  Generated password for {user['username']}: "
                    f"{password}  (shown once, save it now)"
                )
        else:
            print(f"Already exists: {user['username']}")


if __name__ == "__main__":
    seed_users()
    print("\nUser seeding completed.")
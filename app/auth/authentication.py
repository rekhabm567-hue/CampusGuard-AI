from app.auth.users import get_user
from app.core.security import verify_password


def authenticate_user(username, password):
    user = get_user(username)

    if user is None:
        return None

    if not verify_password(
        password,
        user["password_hash"]
    ):
        return None

    return user
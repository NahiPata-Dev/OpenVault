from collections.abc import Callable
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.database import get_session
from app.errors import raise_api_error
from app.models import AccountProfile, User


def get_current_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str):
        raise_api_error("forbidden", "Authentication is required.", 401)
    try:
        user_id = str(UUID(user_id))
    except ValueError:
        request.session.clear()
        raise_api_error("forbidden", "Authentication is required.", 401)
    user = session.get(User, user_id)
    profile = session.get(AccountProfile, user_id)
    if user is None or (not user.is_demo and profile is None):
        request.session.clear()
        raise_api_error("forbidden", "Authentication is required.", 401)
    if profile is not None and not profile.is_active:
        request.session.clear()
        raise_api_error("forbidden", "Authentication is required.", 401)
    if request.session.get("auth_version", 0) != (
        profile.auth_version if profile is not None else 0
    ):
        request.session.clear()
        raise_api_error("forbidden", "Authentication is required.", 401)
    return user


def get_optional_user(
    request: Request,
    session: Session = Depends(get_session),
) -> User | None:
    user_id = request.session.get("user_id")
    if not isinstance(user_id, str):
        return None
    try:
        user_id = str(UUID(user_id))
    except ValueError:
        request.session.clear()
        return None
    user = session.get(User, user_id)
    profile = session.get(AccountProfile, user_id)
    if user is None or (not user.is_demo and profile is None):
        request.session.clear()
        return None
    if profile is not None and not profile.is_active:
        request.session.clear()
        return None
    if request.session.get("auth_version", 0) != (
        profile.auth_version if profile is not None else 0
    ):
        request.session.clear()
        return None
    return user


def require_roles(*roles: str) -> Callable:
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise_api_error(
                "forbidden",
                "You are not authorized to perform this action.",
                403,
            )
        return user

    return dependency

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.errors import raise_api_error
from app.models import User
from app.schemas import (
    DemoAccountRead,
    DemoAccountsRead,
    DemoLoginRequest,
    DemoLoginResponse,
    UserRead,
)
from app.services.auth import verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/demo-accounts", response_model=DemoAccountsRead)
def demo_accounts(session: Session = Depends(get_session)) -> DemoAccountsRead:
    users = session.scalars(
        select(User)
        .where(User.is_demo.is_(True))
        .order_by(User.display_name)
    ).all()
    return DemoAccountsRead(
        accounts=[DemoAccountRead.model_validate(user) for user in users]
    )


@router.post("/demo-login", response_model=DemoLoginResponse)
def demo_login(
    payload: DemoLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> DemoLoginResponse:
    user = session.get(User, str(payload.account_id))
    if (
        user is None
        or not user.is_demo
        or not verify_password(payload.password, user.password_hash)
    ):
        raise_api_error("forbidden", "Invalid demo account or password.", 401)
    request.session.clear()
    request.session["user_id"] = user.id
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.get("/session", response_model=DemoLoginResponse)
def current_session(user: User = Depends(get_current_user)) -> DemoLoginResponse:
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.post("/logout")
def logout(
    request: Request,
    _user: User = Depends(get_current_user),
) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}

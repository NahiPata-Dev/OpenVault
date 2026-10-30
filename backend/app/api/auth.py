import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user
from app.errors import raise_api_error
from app.models import AccountProfile, LoginAttempt, User
from app.schemas import (
    AccountLogin,
    AccountRegister,
    DemoAccountRead,
    DemoAccountsRead,
    DemoLoginRequest,
    DemoLoginResponse,
    UserRead,
)
from app.services.accounts import organization_scope, unique_display_name
from app.services.auth import hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_FAILURE_LIMIT = 5
NEW_PASSWORD_ROUNDS = 600_000
DUMMY_PASSWORD_HASH = hash_password(
    "invalid-login-timing-placeholder", NEW_PASSWORD_ROUNDS
)


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
    profile = session.get(AccountProfile, user.id)
    request.session["auth_version"] = profile.auth_version if profile else 0
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.post("/register", response_model=DemoLoginResponse, status_code=201)
def register(
    payload: AccountRegister,
    session: Session = Depends(get_session),
) -> DemoLoginResponse:
    if session.scalar(
        select(AccountProfile.user_id).where(
            func.lower(AccountProfile.email) == payload.email
        )
    ):
        raise_api_error("conflict", "An account with this email already exists.", 409)

    user_id = str(uuid4())
    organization_id = organization_scope(payload.organization_name, user_id)
    user = User(
        id=user_id,
        display_name=unique_display_name(
            session, payload.full_name, organization_id, user_id
        ),
        role="requester",
        organization_id=organization_id,
        is_demo=False,
        password_hash=hash_password(payload.password, NEW_PASSWORD_ROUNDS),
    )
    profile = AccountProfile(
        user_id=user_id,
        email=payload.email,
        full_name=payload.full_name,
        organization_name=payload.organization_name,
        intended_use=payload.intended_use,
        email_verified=False,
        is_active=True,
        auth_version=0,
    )
    try:
        session.add(user)
        session.flush()
        session.add(profile)
        session.commit()
    except IntegrityError:
        session.rollback()
        raise_api_error("conflict", "An account with this email already exists.", 409)
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.post("/login", response_model=DemoLoginResponse)
def login(
    payload: AccountLogin,
    request: Request,
    session: Session = Depends(get_session),
) -> DemoLoginResponse:
    now = datetime.now(timezone.utc)
    account_key = _rate_key(request.app.state.secret_key, payload.email)
    client_ip = request.client.host if request.client else "unknown"
    ip_key = _rate_key(request.app.state.secret_key, client_ip)
    cutoff = now - LOGIN_WINDOW
    account_failures = session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.account_key == account_key,
            LoginAttempt.failed_at >= cutoff,
        )
    ) or 0
    ip_failures = session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(LoginAttempt.ip_key == ip_key, LoginAttempt.failed_at >= cutoff)
    ) or 0
    if account_failures >= LOGIN_FAILURE_LIMIT or ip_failures >= LOGIN_FAILURE_LIMIT:
        raise_api_error(
            "rate_limited",
            "Too many failed sign-in attempts. Try again in 15 minutes.",
            429,
        )

    profile = session.scalar(
        select(AccountProfile).where(AccountProfile.email == payload.email)
    )
    user = session.get(User, profile.user_id) if profile is not None else None
    valid_password = verify_password(
        payload.password,
        user.password_hash if user is not None else DUMMY_PASSWORD_HASH,
    )
    if (
        user is None
        or profile is None
        or not profile.is_active
        or not valid_password
    ):
        session.execute(delete(LoginAttempt).where(LoginAttempt.failed_at < cutoff))
        session.add(
            LoginAttempt(
                id=str(uuid4()),
                account_key=account_key,
                ip_key=ip_key,
                failed_at=now,
            )
        )
        session.commit()
        raise_api_error("invalid_credentials", "Invalid email or password.", 401)

    request.session.clear()
    request.session["user_id"] = user.id
    request.session["auth_version"] = profile.auth_version
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.get("/session", response_model=DemoLoginResponse)
def current_session(user: User = Depends(get_current_user)) -> DemoLoginResponse:
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.post("/logout")
def logout(
    request: Request,
) -> dict[str, bool]:
    request.session.clear()
    return {"ok": True}


def _rate_key(secret_key: str, value: str) -> str:
    return hmac.new(
        secret_key.encode("utf-8"), value.encode("utf-8"), hashlib.sha256
    ).hexdigest()

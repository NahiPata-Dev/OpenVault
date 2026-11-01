import hashlib
import hmac
from datetime import datetime, timedelta, timezone
from typing import Literal
from urllib.parse import urlencode
from uuid import uuid4

from authlib.integrations.base_client.errors import OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi import Query
from fastapi.responses import RedirectResponse
from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_session
from app.dependencies import get_current_user, get_optional_user
from app.errors import raise_api_error
from app.models import AccountProfile, LoginAttempt, User
from app.schemas import (
    AccountLogin,
    AccountRegister,
    AuthSessionRead,
    DemoAccountRead,
    DemoAccountsRead,
    DemoLoginRequest,
    DemoLoginResponse,
    JudgeLoginRequest,
    JudgeRole,
    UserRead,
)
from app.services.accounts import organization_scope, unique_display_name
from app.services.auth import hash_password, verify_password
from app.services.audit_service import record_event
from app.seed import DEMO_USER_IDS

router = APIRouter(prefix="/api/auth", tags=["auth"])
OAuthProvider = Literal["google", "linkedin"]
LOGIN_WINDOW = timedelta(minutes=15)
LOGIN_FAILURE_LIMIT = 5
JUDGE_LOGIN_WINDOW = timedelta(minutes=10)
JUDGE_LOGIN_LIMIT = 30
JUDGE_LOGIN_ACCOUNT_KEY = "judge-login"
JUDGE_USER_KEYS: dict[JudgeRole, str] = {
    "requester": "requester_a",
    "manager": "lab_manager",
    "auditor": "judge_auditor",
}
JUDGE_ROLES: tuple[JudgeRole, ...] = ("requester", "manager", "auditor")
NEW_PASSWORD_ROUNDS = 600_000
DUMMY_PASSWORD_HASH = hash_password(
    "invalid-login-timing-placeholder", NEW_PASSWORD_ROUNDS
)


def _safe_next_path(value: str | None) -> str:
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return "/resources"
    return value


def _oauth_client(request: Request, provider: OAuthProvider):
    if not request.app.state.oauth_redirect_base_url:
        return None
    return request.app.state.oauth.create_client(provider)


def _oauth_failure_redirect(
    request: Request, provider: OAuthProvider, error_code: str
) -> RedirectResponse:
    next_path = _safe_next_path(request.session.pop(f"oauth_next_{provider}", None))
    query = urlencode({"oauth_error": error_code, "next": next_path})
    return RedirectResponse(
        f"{request.app.state.frontend_base_url}/login?{query}", status_code=303
    )


@router.get("/providers")
def oauth_providers(request: Request) -> dict[str, dict[str, bool]]:
    return {
        "providers": {
            name: _oauth_client(request, name) is not None
            for name in ("google", "linkedin")
        }
    }


@router.get("/{provider}/start")
async def start_oauth(
    provider: OAuthProvider,
    request: Request,
    next_path: str = Query(default="/resources", alias="next", max_length=2048),
):
    client = _oauth_client(request, provider)
    if client is None:
        raise_api_error("oauth_unavailable", "This sign-in provider is not configured.", 503)
    request.session[f"oauth_next_{provider}"] = _safe_next_path(next_path)
    redirect_uri = (
        f"{request.app.state.oauth_redirect_base_url}"
        f"/api/auth/{provider}/callback"
    )
    return await client.authorize_redirect(request, redirect_uri)


@router.get("/{provider}/callback")
async def finish_oauth(provider: OAuthProvider, request: Request, session: Session = Depends(get_session)):
    client = _oauth_client(request, provider)
    if client is None:
        return _oauth_failure_redirect(request, provider, "provider_unavailable")
    try:
        token = await client.authorize_access_token(request)
    except OAuthError:
        return _oauth_failure_redirect(request, provider, "provider_error")

    claims = token.get("userinfo")
    if not isinstance(claims, dict) or claims.get("email_verified") is not True:
        return _oauth_failure_redirect(request, provider, "unverified_email")
    email = claims.get("email")
    if not isinstance(email, str) or not email.strip():
        return _oauth_failure_redirect(request, provider, "unverified_email")

    profile = session.scalar(
        select(AccountProfile).where(
            func.lower(AccountProfile.email) == email.strip().casefold()
        )
    )
    if profile is None:
        return _oauth_failure_redirect(request, provider, "account_not_found")
    user = session.get(User, profile.user_id)
    if user is None or not profile.is_active:
        return _oauth_failure_redirect(request, provider, "account_inactive")

    if not profile.email_verified:
        profile.email_verified = True
        session.commit()
    next_path = _safe_next_path(request.session.pop(f"oauth_next_{provider}", None))
    request.session.clear()
    request.session["user_id"] = user.id
    request.session["auth_version"] = profile.auth_version
    return RedirectResponse(
        f"{request.app.state.frontend_base_url}{next_path}", status_code=303
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


@router.post("/judge-login", response_model=DemoLoginResponse)
def judge_login(
    payload: JudgeLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> DemoLoginResponse:
    if not request.app.state.judge_login_enabled:
        raise_api_error("not_found", "Not Found", 404)
    user = _judge_user(session, payload.role)
    _record_judge_call(request, session)
    request.session.clear()
    request.session["user_id"] = user.id
    profile = session.get(AccountProfile, user.id)
    request.session["auth_version"] = profile.auth_version if profile else 0
    request.session["judge_mode"] = True
    record_event(
        session,
        user,
        "auth",
        user.id,
        "auth.judge_login",
        request.state.request_id,
        after={"judge_role": payload.role},
    )
    session.commit()
    return DemoLoginResponse(user=UserRead.model_validate(user))


@router.post("/judge-switch", response_model=DemoLoginResponse)
def judge_switch(
    payload: JudgeLoginRequest,
    request: Request,
    session: Session = Depends(get_session),
) -> DemoLoginResponse:
    if not request.app.state.judge_login_enabled:
        raise_api_error("not_found", "Not Found", 404)
    if request.session.get("judge_mode") is not True:
        raise_api_error("forbidden", "Role switching is available only in judge mode.", 403)
    user = _judge_user(session, payload.role)
    _record_judge_call(request, session)
    request.session.clear()
    request.session["user_id"] = user.id
    profile = session.get(AccountProfile, user.id)
    request.session["auth_version"] = profile.auth_version if profile else 0
    request.session["judge_mode"] = True
    record_event(
        session,
        user,
        "auth",
        user.id,
        "auth.judge_switch",
        request.state.request_id,
        after={"judge_role": payload.role},
    )
    session.commit()
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


@router.get("/session", response_model=AuthSessionRead)
def current_session(
    request: Request,
    user: User | None = Depends(get_optional_user),
) -> AuthSessionRead:
    enabled = request.app.state.judge_login_enabled
    if user is None and not enabled:
        raise_api_error("forbidden", "Authentication is required.", 401)
    return AuthSessionRead(
        user=UserRead.model_validate(user) if user else None,
        judge_mode=request.session.get("judge_mode") is True,
        judge_login_available=enabled,
        available_judge_roles=list(JUDGE_ROLES) if enabled else [],
    )


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


def _judge_user(session: Session, role: JudgeRole) -> User:
    user = session.get(User, DEMO_USER_IDS[JUDGE_USER_KEYS[role]])
    if (
        user is None
        or not user.is_demo
        or user.role
        != {"requester": "requester", "manager": "lab_manager", "auditor": "auditor"}[
            role
        ]
    ):
        raise_api_error("invalid_state", "The seeded judge account is unavailable.", 503)
    return user


def _record_judge_call(request: Request, session: Session) -> None:
    now = datetime.now(timezone.utc)
    client_ip = request.client.host if request.client else "unknown"
    ip_key = _rate_key(request.app.state.secret_key, client_ip)
    attempt = LoginAttempt(
        id=str(uuid4()),
        account_key=_rate_key(
            request.app.state.secret_key, JUDGE_LOGIN_ACCOUNT_KEY
        ),
        ip_key=ip_key,
        failed_at=now,
    )
    session.add(attempt)
    session.flush()
    cutoff = now - JUDGE_LOGIN_WINDOW
    session.execute(delete(LoginAttempt).where(LoginAttempt.failed_at < cutoff))
    call_count = session.scalar(
        select(func.count())
        .select_from(LoginAttempt)
        .where(
            LoginAttempt.account_key == attempt.account_key,
            LoginAttempt.ip_key == ip_key,
            LoginAttempt.failed_at >= cutoff,
        )
    ) or 0
    if call_count > JUDGE_LOGIN_LIMIT:
        session.commit()
        raise_api_error(
            "rate_limited",
            "Too many judge sign-in requests. Try again in 10 minutes.",
            429,
        )

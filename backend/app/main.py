import logging
import os
from threading import Lock
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from itsdangerous import BadSignature
from sqlalchemy import select
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.audit import router as audit_router
from app.api.admin import router as admin_router
from app.api.account import router as account_router
from app.api.ai import router as ai_router
from app.api.analytics import router as analytics_router
from app.api.bookings import router as bookings_router
from app.api.dashboard import router as dashboard_router
from app.api.incidents import router as incidents_router
from app.api.notifications import router as notifications_router
from app.api.policies import router as policies_router
from app.api.public import router as public_router
from app.api.requests import router as requests_router
from app.api.resources import router as resources_router
from app.database import (
    Base,
    build_engine,
    build_session_factory,
    migrate_legacy_resource_schema,
)
from app.errors import APIError
from app.models import (
    AccessContract,
    AllocationDecision,
    AuditEvent,
    Booking,
    HandoverReport,
    Incident,
    Notification,
    Resource,
    ResourcePolicy,
    ResourceRequest,
    TrainingRecord,
    User,
)
from app.seed import seed_database

logger = logging.getLogger(__name__)
MAX_REQUEST_BODY_BYTES = 1_048_576
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
}
API_CONTENT_SECURITY_POLICY = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
DOCS_CONTENT_SECURITY_POLICY = (
    "default-src 'self'; "
    "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "img-src 'self' data: https://fastapi.tiangolo.com; "
    "font-src 'self' https://cdn.jsdelivr.net; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
)


def create_app(
    database_url: str | None = None,
    secret_key: str | None = None,
    initialize_database: bool = True,
    demo_mode: bool | None = None,
) -> FastAPI:
    database_url = database_url or os.environ.get(
        "DATABASE_URL", "sqlite:///./openvault.db"
    )
    secret_key = secret_key or os.environ.get("SECRET_KEY")
    if not secret_key:
        raise RuntimeError("SECRET_KEY must be configured in the environment.")

    engine = build_engine(database_url)
    app = FastAPI(title="OpenVault API", version="0.1.0")
    app.state.engine = engine
    app.state.session_factory = build_session_factory(engine)
    app.state.secret_key = secret_key
    app.state.demo_password = os.environ.get("DEMO_PASSWORD", "northstar-demo")
    app.state.demo_mode = (
        demo_mode
        if demo_mode is not None
        else os.environ.get("DEMO_MODE", "false").casefold() == "true"
    )
    app.state.public_summary_buckets = {}
    app.state.public_summary_lock = Lock()
    app.state.public_summary_cleanup_at = 0.0

    app.add_middleware(
        SessionMiddleware,
        secret_key=secret_key,
        session_cookie="openvault_session",
        max_age=12 * 60 * 60,
        same_site="lax",
        https_only=os.environ.get("COOKIE_SECURE", "false").casefold() == "true",
    )
    allowed_origins = [
        origin.strip()
        for origin in os.environ.get("ALLOWED_ORIGINS", "").split(",")
        if origin.strip()
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    )

    @app.middleware("http")
    async def attach_request_id(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid4())
        request.state.request_id = request_id
        declared_length = request.headers.get("content-length")
        if declared_length is not None:
            try:
                body_length = int(declared_length)
            except ValueError:
                body_length = MAX_REQUEST_BODY_BYTES + 1
            if body_length < 0 or body_length > MAX_REQUEST_BODY_BYTES:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "request_too_large",
                            "message": "Request body exceeds the 1 MiB limit.",
                            "details": [],
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["X-Request-ID"] = request_id
                _apply_security_headers(response, request.url.path)
                return response

        body = bytearray()
        async for chunk in request.stream():
            if len(body) + len(chunk) > MAX_REQUEST_BODY_BYTES:
                response = JSONResponse(
                    status_code=413,
                    content={
                        "error": {
                            "code": "request_too_large",
                            "message": "Request body exceeds the 1 MiB limit.",
                            "details": [],
                            "request_id": request_id,
                        }
                    },
                )
                response.headers["X-Request-ID"] = request_id
                _apply_security_headers(response, request.url.path)
                return response
            body.extend(chunk)
        request._body = bytes(body)
        body_sent = False

        async def replay_body():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return {"type": "http.disconnect"}

        request._receive = replay_body
        try:
            response = await call_next(request)
        except BadSignature:
            request_id = request.state.request_id
            response = JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "forbidden",
                        "message": "Authentication is required.",
                        "details": [],
                        "request_id": request_id,
                    }
                },
                headers={"X-Request-ID": request_id},
            )
            _apply_security_headers(response, request.url.path)
            return response
        response.headers["X-Request-ID"] = request_id
        _apply_security_headers(response, request.url.path)
        return response

    @app.exception_handler(APIError)
    async def api_error_handler(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details or [],
                    "request_id": getattr(request.state, "request_id", str(uuid4())),
                }
            },
            headers={"X-Request-ID": getattr(request.state, "request_id", "")},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        details = [
            {
                "code": "validation_error",
                "message": ".".join(str(item) for item in error["loc"])
                + ": "
                + error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "validation_error",
                    "message": "Request validation failed.",
                    "details": details,
                    "request_id": request.state.request_id,
                }
            },
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        code = {
            401: "forbidden",
            403: "forbidden",
            404: "not_found",
            409: "conflict",
            422: "validation_error",
            429: "rate_limited",
            413: "request_too_large",
        }.get(exc.status_code, "validation_error")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": code,
                    "message": str(exc.detail),
                    "details": [],
                    "request_id": request.state.request_id,
                }
            },
            headers={"X-Request-ID": request.state.request_id},
        )

    @app.exception_handler(Exception)
    async def internal_error_handler(request: Request, _exc: Exception):
        logger.exception("Unhandled API error request_id=%s", request.state.request_id)
        response = JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "An internal server error occurred.",
                    "details": [],
                    "request_id": request.state.request_id,
                }
            },
            headers={"X-Request-ID": request.state.request_id},
        )
        _apply_security_headers(response, request.url.path)
        return response

    app.include_router(account_router)
    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(ai_router)
    app.include_router(analytics_router)
    app.include_router(audit_router)
    app.include_router(bookings_router)
    app.include_router(dashboard_router)
    app.include_router(incidents_router)
    app.include_router(notifications_router)
    app.include_router(policies_router)
    app.include_router(public_router)
    app.include_router(requests_router)
    app.include_router(resources_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    def initialize_schema() -> None:
        if initialize_database:
            Base.metadata.create_all(bind=engine)
            migrate_legacy_resource_schema(engine)
            with app.state.session_factory() as session:
                has_users = session.scalar(select(User.id).limit(1)) is not None
            if not has_users:
                seed_database(app.state.session_factory, app.state.demo_password)

    @app.on_event("shutdown")
    def dispose_engine() -> None:
        engine.dispose()

    return app


def _apply_security_headers(response: Response, request_path: str) -> None:
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    response.headers["Content-Security-Policy"] = (
        DOCS_CONTENT_SECURITY_POLICY
        if request_path in {"/docs", "/redoc"}
        else API_CONTENT_SECURITY_POLICY
    )


app = create_app()

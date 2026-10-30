import os
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from itsdangerous import BadSignature
from sqlalchemy import select
from starlette.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.sessions import SessionMiddleware

from app.api.auth import router as auth_router
from app.api.audit import router as audit_router
from app.api.admin import router as admin_router
from app.api.ai import router as ai_router
from app.api.analytics import router as analytics_router
from app.api.bookings import router as bookings_router
from app.api.incidents import router as incidents_router
from app.api.notifications import router as notifications_router
from app.api.policies import router as policies_router
from app.api.requests import router as requests_router
from app.api.resources import router as resources_router
from app.database import Base, build_engine, build_session_factory
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
    app.state.demo_password = os.environ.get("DEMO_PASSWORD", "northstar-demo")
    app.state.demo_mode = (
        demo_mode
        if demo_mode is not None
        else os.environ.get("DEMO_MODE", "false").casefold() == "true"
    )

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
        try:
            response = await call_next(request)
        except BadSignature:
            request_id = request.state.request_id
            return JSONResponse(
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
        response.headers["X-Request-ID"] = request_id
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

    app.include_router(auth_router)
    app.include_router(admin_router)
    app.include_router(ai_router)
    app.include_router(analytics_router)
    app.include_router(audit_router)
    app.include_router(bookings_router)
    app.include_router(incidents_router)
    app.include_router(notifications_router)
    app.include_router(policies_router)
    app.include_router(requests_router)
    app.include_router(resources_router)

    @app.get("/api/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.on_event("startup")
    def initialize_schema() -> None:
        if initialize_database:
            Base.metadata.create_all(bind=engine)
            with app.state.session_factory() as session:
                has_users = session.scalar(select(User.id).limit(1)) is not None
            if not has_users:
                seed_database(app.state.session_factory, app.state.demo_password)

    @app.on_event("shutdown")
    def dispose_engine() -> None:
        engine.dispose()

    return app


app = create_app()

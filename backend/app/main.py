import os
from contextlib import asynccontextmanager
from datetime import datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import HTTPException as FastAPIHTTPException, RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.config import settings
from app.logging_config import configure_logging
from app.middleware.audit_middleware import AuditMiddleware
from app.middleware.request_id import RequestIdMiddleware, get_request_id

configure_logging(settings.app_env)

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.db import AsyncSessionLocal
    from app.repositories import auth_repo

    async with AsyncSessionLocal() as db:
        await auth_repo.create_admin_account_if_not_exists(db)
    yield


app = FastAPI(title="회의 및 회의실 관리", version="1.0.0", lifespan=lifespan)

# 미들웨어 등록 순서: RequestIdMiddleware → AuditMiddleware (LIFO: 나중에 add한 게 먼저 실행)
app.add_middleware(AuditMiddleware)
app.add_middleware(RequestIdMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_origin],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    return response


@app.exception_handler(FastAPIHTTPException)
async def http_exception_handler(request: Request, exc: FastAPIHTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        content = exc.detail
    else:
        content = {
            "error": {
                "code": "HTTP_ERROR",
                "message": str(exc.detail) if exc.detail else "요청 처리 중 오류가 발생했습니다",
            }
        }
    headers = dict(exc.headers) if exc.headers else {}
    return JSONResponse(status_code=exc.status_code, content=content, headers=headers)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "INVALID_REQUEST",
                "message": "요청 형식이 올바르지 않습니다",
                "detail": exc.errors(),
            }
        },
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", exc_info=exc, request_id=get_request_id())
    return JSONResponse(
        status_code=500,
        content={"error": {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다"}},
    )


# ── Routers ────────────────────────────────────────────────────────────────────

from app.routers import auth  # noqa: E402
from app.routers import employees, departments  # noqa: E402

app.include_router(auth.router)
app.include_router(employees.router)
app.include_router(departments.router)


@app.get("/api/health")
async def health_check():
    from app.db import AsyncSessionLocal

    db_status = "error"
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
            db_status = "ok"
    except Exception:
        pass

    status = "ok" if db_status == "ok" else "degraded"
    return JSONResponse(
        status_code=200 if status == "ok" else 503,
        content={
            "status": status,
            "db": db_status,
            "timestamp": datetime.now().isoformat(),
        },
    )


# 정적 파일 서빙 (Svelte 빌드) — frontend/dist가 없으면 조건부 마운트
_static_dir = os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "dist")
if os.path.exists(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="static")

"""
ARIA / SAKHI — Application Entry Point
========================================
FastAPI application factory with:
  - Lifespan context (DB + startup validation)
  - Router registration
  - CORS
  - Rate limiting
  - Exception handlers
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.config import get_settings
from app.database import engine
from app.models import Base  # ensures all models are registered before create_all

# ─── Routers (BE3 owns) ────────────────────────────────────────────────────────
from app.routers import emergency

settings = get_settings()

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan — startup and shutdown hooks."""
    # Startup
    # NOTE: In production use Alembic migrations, not create_all.
    # create_all is here only for test/local convenience.
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    # Shutdown
    await engine.dispose()


# ─── FastAPI App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="ARIA — Autonomous Real-Time Intelligence for Assistance",
    description=(
        "AI-powered, consent-driven real-time women safety alert system. "
        "Backend Engineer 3: Emergency & Real-Time Systems."
    ),
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# ─── Middleware ───────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)  # type: ignore[arg-type]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if settings.DEBUG else [],  # BE1 should lock down origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(emergency.router, prefix="/emergency", tags=["Emergency"])
app.include_router(emergency.ws_router, tags=["Emergency WebSocket"])

# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["Health"], summary="Health check")
async def health_check() -> dict[str, str]:
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# ─── Generic Exception Handler ────────────────────────────────────────────────
@app.exception_handler(Exception)
async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    if settings.DEBUG:
        raise exc
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "An internal error occurred."},
    )

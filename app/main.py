from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from app.config import settings
from app.database import engine, Base
import app.models  # Ensure all SQLAlchemy models are imported
from app.api.v1.api import api_router
from app.core.exceptions import AppException


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables on startup
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="SAKHI — Core Backend & Data Layer",
    description="""
### SAKHI: AI-Powered Real-Time Safety Sentinel
**Detect. Verify. Respond.**

Core Backend & Data Layer (Backend 2) responsible for:
- Identity & Authentication (JWT, Bcrypt)
- User Management
- Trusted Contacts Management
- Consent-First Permissions Engine
- Emergency Response Policy Configuration
- Safe Journey Lifecycle Management
- Context & Integration contracts for Backend 1 (AI Risk Engine) & Backend 3 (Emergency & Realtime)
    """,
    version="1.0.0",
    lifespan=lifespan
)

# CORS Middleware
origins = settings.ALLOWED_ORIGINS
if isinstance(origins, str):
    origins = [origins]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if origins != ["*"] else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom domain exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.detail
            }
        }
    )

# Request validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        loc = " -> ".join([str(l) for l in err.get("loc", []) if l != "body"])
        errors.append({
            "field": loc,
            "message": err.get("msg")
        })
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": errors
            }
        }
    )


@app.get("/health", tags=["System"])
def health_check():
    return {
        "status": "healthy",
        "service": "SAKHI Core Backend",
        "environment": settings.ENVIRONMENT,
        "version": "1.0.0"
    }


@app.get("/", tags=["System"])
def root():
    return {
        "message": "Welcome to SAKHI Core Backend API",
        "tagline": "Detect. Verify. Respond.",
        "docs": "/docs",
        "health": "/health"
    }


# Mount API routers
app.include_router(api_router, prefix=settings.API_V1_STR)

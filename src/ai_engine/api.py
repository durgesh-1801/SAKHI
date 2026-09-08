"""FastAPI Application and Endpoints for SAKHI AI / Risk Engine.

Provides the primary `/ai/analyze` REST endpoint consumed by downstream SAKHI backend services.
Adheres strictly to the analysis boundary: returns risk severity without triggering emergency actions.
"""

import logging
from typing import Any, Dict
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from .config import settings
from .engine import RiskEngine
from .schemas import AIAnalyzeRequest, AIAnalyzeResponse

# Configure structured logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)
logger = logging.getLogger("sakhi.ai_engine.api")

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description=(
        "AI / Risk Engine microservice for SAKHI. "
        "Evaluates multimodal safety signals, generates explainable risk scores and levels. "
        "Strictly an analysis engine; downstream consent/policy handles emergency escalations."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
)

# Initialize engine instance
engine = RiskEngine()


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Custom handler for request validation errors with clear, actionable diagnostics."""
    errors = []
    for err in exc.errors():
        field_path = " -> ".join(str(loc) for loc in err.get("loc", []))
        errors.append({
            "field": field_path,
            "message": err.get("msg", "Validation error"),
            "type": err.get("type", "invalid_value"),
        })

    logger.warning(
        "Request validation error on %s %s: %s",
        request.method,
        request.url.path,
        errors,
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "error": "Validation Error",
            "message": "Incoming signal payload contains invalid types, out-of-range values, or unknown fields.",
            "details": errors,
        },
    )


@app.get("/health", tags=["System"])
async def health_check() -> Dict[str, Any]:
    """Health and readiness check for the AI Risk Engine service."""
    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": settings.app_version,
    }


@app.get("/ai/config", tags=["AI Engine"])
async def get_engine_config() -> Dict[str, Any]:
    """Inspect active weights and classification thresholds."""
    return {
        "weights": engine.config.weights.to_dict(),
        "thresholds": engine.config.thresholds.model_dump(),
        "score_bounds": {
            "min": engine.config.min_score,
            "max": engine.config.max_score,
        },
    }


@app.post(
    "/ai/analyze",
    response_model=AIAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Engine"],
    summary="Analyze multimodal safety signals",
)
@app.post(
    "/api/v1/ai/analyze",
    response_model=AIAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    tags=["AI Engine"],
    include_in_schema=False,
)
async def analyze_signals(request: AIAnalyzeRequest) -> AIAnalyzeResponse:
    """Analyze incoming safety signals and return explainable risk severity.

    - **user_id**: Non-PII identifier for audit tracking.
    - **signals**: Dictionary of safety flags and/or processed feature scores.

    Returns:
    - **risk_score**: Normalized clamped risk score (0-100).
    - **risk_level**: SAFE | SUSPICIOUS | HIGH | CRITICAL.
    - **reasons**: Specific explainable factors contributing to danger assessment.
    - **signals_detected**: Contributing signal identifiers.
    """
    try:
        response = engine.analyze(request.signals)

        # Structured privacy-safe logging: log only non-sensitive metadata and results
        logger.info(
            "Analyzed signals for user=%s -> score=%.1f level=%s signals_count=%d",
            request.user_id,
            response.risk_score,
            response.risk_level.value,
            len(response.signals_detected),
        )

        return response
    except Exception as exc:
        logger.error(
            "Unexpected error during signal analysis for user=%s: %s",
            request.user_id,
            str(exc),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI Risk Engine encountered an unexpected error during signal evaluation.",
        )

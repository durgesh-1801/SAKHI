"""AI & Risk Engine Endpoints for SAKHI (Backend 1).

Exposes:
- POST /api/v1/ai/analyze: Multimodal safety signal analysis with Backend 2 consent enforcement.
- POST /api/v1/ai/analyze-audio: Audio upload, validation, and acoustic distress analysis.
- GET /api/v1/ai/config: Inspection of risk weights and classification thresholds.

Strictly adheres to Backend 1 boundary:
DETECT → ANALYZE → ASSESS RISK → RETURN RISK ASSESSMENT.
Never dispatches emergency alerts, calls 112, or sends SMS.
"""

from typing import Any

from fastapi import APIRouter, Depends, File, Form, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from src.ai_engine.audio_pipeline import audio_pipeline
from src.ai_engine.context_client import ConsentEnforcer, context_client
from src.ai_engine.engine import RiskEngine
from src.ai_engine.schemas import AIAnalyzeRequest, AIAnalyzeResponse, SignalsPayload

router = APIRouter(prefix="/ai", tags=["AI & Risk Engine (Backend 1)"])

# Shared engine instance
engine = RiskEngine()


@router.get("/config", status_code=status.HTTP_200_OK, summary="Inspect AI Engine configuration")
def get_ai_config() -> dict[str, Any]:
    """Returns the active signal weights, risk thresholds, and score bounds."""
    return {
        "weights": engine.config.weights.to_dict(),
        "thresholds": engine.config.thresholds.model_dump(),
        "score_bounds": {
            "min": engine.config.min_score,
            "max": engine.config.max_score,
        },
    }


@router.post(
    "/analyze",
    response_model=AIAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze multimodal safety signals with consent enforcement",
)
def analyze_safety_signals(
    request: AIAnalyzeRequest,
    db: Session = Depends(get_db),  # noqa: B008
) -> AIAnalyzeResponse:
    """
    **Primary AI & Risk Engine Analysis Endpoint**.

    1. Retrieves user consent & active journey context from Backend 2 (`ContextService`).
    2. Enforces Consent Rules:
       - If `ai_detection_permitted == False` → Aborts with HTTP 403.
       - If `audio_analysis_permitted == False` → Filters out audio distress signals.
       - If `location_monitoring_permitted == False` → Filters out route deviation signals.
    3. Evaluates active safety signals via modular detectors.
    4. Computes normalized, clamped risk score (0–100).
    5. Categorizes risk level: SAFE, SUSPICIOUS, HIGH, CRITICAL.
    6. Returns explainable reasons for downstream Backend 3 consumption.
    """
    # 1. Resolve context & consent from Backend 2
    user_context = context_client.get_context(request.user_id, db_session=db)

    # 2. Enforce consent rules
    sanitized_signals, _ = ConsentEnforcer.enforce(user_context, request.signals)

    # 3. If active journey exists, correlate route deviation
    if user_context.active_journey and sanitized_signals.route_deviation:
        journey_info = user_context.active_journey
        origin = journey_info.get("origin", "Origin")
        dest = journey_info.get("destination", "Destination")
        logger_note = f"Route deviation occurred during Safe Journey: {origin} -> {dest}"
    else:
        logger_note = None

    # 4. Perform risk analysis
    response = engine.analyze(sanitized_signals)

    # Augment response with consent and journey audit notes
    if logger_note and "Route deviation detected" in response.reasons:
        response.reasons.remove("Route deviation detected")
        response.reasons.append("Significant route deviation during active Safe Journey")

    return response


@router.post(
    "/analyze-audio",
    response_model=AIAnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Upload audio file for acoustic distress analysis",
)
async def analyze_audio_file(
    user_id: str = Form(..., description="User ID for consent lookup"),
    file: UploadFile = File(..., description="Audio recording (.wav, .mp3, .m4a, .ogg, .flac)"),  # noqa: B008
    sudden_fall: bool | None = Form(False, description="Correlating fall flag if detected simultaneously"),
    abnormal_motion: bool | None = Form(False, description="Correlating motion anomaly flag"),
    db: Session = Depends(get_db),  # noqa: B008
) -> AIAnalyzeResponse:
    """
    **Audio Stream / File Analysis Endpoint**.

    1. Resolves user consent from Backend 2.
    2. Validates `audio_analysis_permitted` (aborts with 403 if disabled).
    3. Validates audio format, size, and integrity.
    4. Extracts acoustic features / distress signatures.
    5. Evaluates distress score and correlates with simultaneous physical signals.
    6. Returns explainable risk assessment.
    """
    # 1. Resolve context & consent from Backend 2
    user_context = context_client.get_context(user_id, db_session=db)

    # Check AI detection consent
    if not user_context.ai_detection_permitted:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "AI_CONSENT_REVOKED",
                "message": "AI safety detection is disabled by user consent policy.",
                "user_id": user_id,
            },
        )

    # Check audio analysis consent
    if not user_context.audio_analysis_permitted:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "AUDIO_ANALYSIS_NOT_PERMITTED",
                "message": "Audio stream analysis is disabled by user consent policy.",
                "user_id": user_id,
            },
        )

    # 2. Process audio upload
    _, audio_result = await audio_pipeline.process_upload(file)

    # 3. Formulate signals payload
    signals = SignalsPayload(
        distress_audio=audio_result.distress_detected,
        audio_confidence=audio_result.confidence,
        sudden_fall=sudden_fall or False,
        abnormal_motion=abnormal_motion or False,
    )

    # 4. Perform risk analysis
    response = engine.analyze(signals)
    return response

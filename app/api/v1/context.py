from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.context import AIRiskContext, EmergencyDispatchContext
from app.services.context_service import context_service

router = APIRouter(prefix="/context", tags=["Shared System Context"])


@router.get(
    "/ai-risk/{user_id}",
    response_model=AIRiskContext,
    status_code=status.HTTP_200_OK,
    summary="Get user context for AI & Risk Engine (Backend 1 Integration)"
)
def get_ai_risk_context(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    **Integration Contract for Backend 1 (AI & Risk Engine)**.
    
    Provides the risk engine with:
    - Opt-in status for AI detection (`ai_detection_permitted`)
    - Opt-in status for audio stream analysis (`audio_analysis_permitted`)
    - Opt-in status for location monitoring (`location_monitoring_permitted`)
    - Currently active Safe Journey details (origin, destination, duration) if any
    
    *Backend 1 MUST inspect these flags and abort audio/location analysis if permitted is false.*
    """
    return context_service.get_ai_risk_context(db, user_id)


@router.get(
    "/emergency-dispatch/{user_id}",
    response_model=EmergencyDispatchContext,
    status_code=status.HTTP_200_OK,
    summary="Get emergency dispatch policy & contacts (Backend 3 Integration)"
)
def get_emergency_dispatch_context(
    user_id: str,
    db: Session = Depends(get_db)
):
    """
    **Integration Contract for Backend 3 (Emergency & Realtime)**.
    
    Provides the emergency response and dispatch pipeline with:
    - User identification & contact details
    - Emergency verification timeout window
    - Auto-escalation permission check
    - Location sharing permission check
    - Primary & Secondary contact details
    - Full list of trusted contacts ordered by priority
    - Active Safe Journey details (if incident occurs during a journey)
    
    *Backend 3 uses this payload to execute the verification countdown and notify contacts.*
    """
    return context_service.get_emergency_dispatch_context(db, user_id)


@router.get(
    "/my-safety-profile",
    response_model=EmergencyDispatchContext,
    status_code=status.HTTP_200_OK,
    summary="Get current user's aggregated safety configuration"
)
def get_my_safety_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Returns the authenticated user's aggregated safety profile (consent, policy, contacts, journey).
    """
    return context_service.get_emergency_dispatch_context(db, current_user.id)

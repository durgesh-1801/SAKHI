from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.schemas.consent import ConsentResponse
from app.schemas.policy import PolicyResponse
from app.schemas.journey import JourneyResponse
from app.schemas.contact import ContactResponse


# ============================================================================
# SHARED CONTRACT FOR BACKEND 1 (AI & RISK ENGINE)
# ============================================================================

class AIRiskContext(BaseModel):
    """
    Context provided by Backend 2 to Backend 1 (AI & Risk Engine)
    before running distress, motion, or route anomaly inference.
    AI detection will only proceed if permitted by user consent.
    """
    user_id: str
    ai_detection_permitted: bool
    audio_analysis_permitted: bool
    location_monitoring_permitted: bool
    active_journey: Optional[JourneyResponse] = None
    consent: ConsentResponse

    model_config = ConfigDict(from_attributes=True)


class RiskAssessment(BaseModel):
    """
    Contract schema representing Backend 1's output.
    Used across SAKHI to represent an explainable risk evaluation.
    """
    risk_score: int  # 0 - 100
    risk_level: str  # SAFE, SUSPICIOUS, HIGH, CRITICAL
    reasons: List[str]
    evaluated_at: Optional[datetime] = None


# ============================================================================
# SHARED CONTRACT FOR BACKEND 3 (EMERGENCY & REALTIME)
# ============================================================================

class EmergencyDispatchContext(BaseModel):
    """
    Context provided by Backend 2 to Backend 3 (Emergency & Realtime)
    to execute safety verification windows, alert escalation, and notifications.
    """
    user_id: str
    user_name: str
    user_phone: str
    auto_escalation_permitted: bool
    evidence_collection_permitted: bool
    verification_timeout: int
    location_sharing_enabled: bool
    policy: PolicyResponse
    consent: ConsentResponse
    active_journey: Optional[JourneyResponse] = None
    recipients: List[ContactResponse] = []

    model_config = ConfigDict(from_attributes=True)

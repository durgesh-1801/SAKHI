from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ConsentBase(BaseModel):
    location_monitoring: bool = Field(default=False, description="Allow location monitoring during safe journeys or emergency")
    ai_detection: bool = Field(default=False, description="Enable AI-based distress/anomaly signal detection")
    audio_analysis: bool = Field(default=False, description="Allow audio stream analysis for distress sound detection")
    automatic_escalation: bool = Field(default=False, description="Allow automated alert escalation if user does not verify safety")
    evidence_collection: bool = Field(default=False, description="Allow emergency audio/sensor snapshot logging upon verified incident")


class ConsentUpdate(BaseModel):
    location_monitoring: Optional[bool] = None
    ai_detection: Optional[bool] = None
    audio_analysis: Optional[bool] = None
    automatic_escalation: Optional[bool] = None
    evidence_collection: Optional[bool] = None


class ConsentResponse(ConsentBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

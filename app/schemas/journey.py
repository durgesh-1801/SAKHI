from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.models.journey import JourneyStatus


class JourneyBase(BaseModel):
    origin: str = Field(..., min_length=2, max_length=255, description="Starting location name or address")
    destination: str = Field(..., min_length=2, max_length=255, description="Target destination name or address")
    expected_duration: int = Field(..., ge=1, le=1440, description="Expected duration in minutes (max 24 hours)")


class JourneyCreate(JourneyBase):
    auto_start: bool = Field(default=False, description="Immediately transition journey to ACTIVE state upon creation")


class JourneyUpdate(BaseModel):
    origin: Optional[str] = Field(None, min_length=2, max_length=255)
    destination: Optional[str] = Field(None, min_length=2, max_length=255)
    expected_duration: Optional[int] = Field(None, ge=1, le=1440)


class JourneyResponse(JourneyBase):
    id: str
    user_id: str
    status: JourneyStatus
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

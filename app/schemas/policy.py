from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict
from app.schemas.contact import ContactResponse


class PolicyBase(BaseModel):
    verification_timeout: int = Field(
        default=30,
        ge=10,
        le=300,
        description="Verification window in seconds before escalation kicks in (10 - 300s)"
    )
    auto_alert_enabled: bool = Field(
        default=True,
        description="Whether to automatically escalate when verification window lapses"
    )
    location_sharing_enabled: bool = Field(
        default=True,
        description="Include live location in emergency alerts sent to trusted contacts"
    )
    primary_contact_id: Optional[str] = Field(
        None,
        description="ID of primary trusted contact"
    )
    secondary_contact_id: Optional[str] = Field(
        None,
        description="ID of secondary trusted contact"
    )
    escalation_level: int = Field(
        default=1,
        ge=1,
        le=3,
        description="Escalation level: 1=Primary contact, 2=All contacts, 3=All contacts + Emergency Services"
    )


class PolicyUpdate(BaseModel):
    verification_timeout: Optional[int] = Field(None, ge=10, le=300)
    auto_alert_enabled: Optional[bool] = None
    location_sharing_enabled: Optional[bool] = None
    primary_contact_id: Optional[str] = None
    secondary_contact_id: Optional[str] = None
    escalation_level: Optional[int] = Field(None, ge=1, le=3)


class PolicyResponse(PolicyBase):
    id: str
    user_id: str
    primary_contact: Optional[ContactResponse] = None
    secondary_contact: Optional[ContactResponse] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

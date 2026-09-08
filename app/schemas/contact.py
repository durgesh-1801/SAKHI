import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator, ConfigDict
from app.schemas.user import validate_phone_number


class ContactBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="Trusted contact's name")
    phone: str = Field(..., description="Contact's phone number")
    relationship_type: Optional[str] = Field(None, max_length=60, description="e.g. Parent, Partner, Friend, Colleague")
    priority: int = Field(default=1, ge=1, le=10, description="Escalation priority (1 is highest)")
    verified: bool = Field(default=False, description="Whether contact's phone has been verified")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_phone_number(v)


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = None
    relationship_type: Optional[str] = Field(None, max_length=60)
    priority: Optional[int] = Field(None, ge=1, le=10)
    verified: Optional[bool] = None

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_phone_number(v)
        return v


class ContactResponse(ContactBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

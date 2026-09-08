import re
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, ConfigDict


def validate_phone_number(v: str) -> str:
    cleaned = re.sub(r"[\s\-\(\)]", "", v)
    if not re.match(r"^\+?[0-9]{7,15}$", cleaned):
        raise ValueError("Invalid phone number format. Must contain 7 to 15 digits, optional '+' prefix.")
    return cleaned


class UserBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120, description="User full name")
    email: EmailStr = Field(..., description="User unique email address")
    phone: str = Field(..., description="Phone number with country code")

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        cleaned = v.strip()
        if len(cleaned) < 2:
            raise ValueError("Name must contain at least 2 non-whitespace characters.")
        return cleaned

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        return validate_phone_number(v)


class UserCreate(UserBase):
    password: str = Field(..., min_length=8, max_length=100, description="Plain text password (min 8 characters)")


class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=120)
    phone: Optional[str] = None
    password: Optional[str] = Field(None, min_length=8, max_length=100)

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            cleaned = v.strip()
            if len(cleaned) < 2:
                raise ValueError("Name must contain at least 2 non-whitespace characters.")
            return cleaned
        return v

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            return validate_phone_number(v)
        return v


class UserResponse(UserBase):
    id: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

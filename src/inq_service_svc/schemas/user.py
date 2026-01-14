from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, EmailStr, Field, ConfigDict

from inq_service_svc.models.enums import UserRole


class UserCreate(BaseModel):
    email: EmailStr
    # enforce minimum length per action item
    password: str = Field(..., min_length=8)
    name: str
    role: UserRole


class UserUpdate(BaseModel):
    email: Optional[EmailStr] = None
    password: Optional[str] = Field(default=None, min_length=8)
    name: Optional[str] = None
    role: Optional[UserRole] = None


class UserResponse(BaseModel):
    id: int
    email: EmailStr
    name: str
    role: UserRole

    model_config = ConfigDict(from_attributes=True)

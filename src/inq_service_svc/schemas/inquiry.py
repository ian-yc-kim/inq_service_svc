from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, ConfigDict

from inq_service_svc.models.enums import InquiryStatus


class InquiryCreate(BaseModel):
    title: str
    content: str
    customer_email: EmailStr
    customer_name: str


class InquiryResponse(BaseModel):
    id: int
    title: str
    content: str
    customer_email: EmailStr
    customer_name: Optional[str]
    status: InquiryStatus
    category: Optional[str]
    urgency: Optional[str]
    assigned_user_id: Optional[int]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class InquiryUpdate(BaseModel):
    """Payload for partial update of Inquiry.

    Fields are optional; exclude_unset will be used by handlers to apply updates.
    Use InquiryStatus for status to leverage pydantic enum validation.
    """

    status: Optional[InquiryStatus] = None
    assigned_user_id: Optional[int] = None

    model_config = ConfigDict()

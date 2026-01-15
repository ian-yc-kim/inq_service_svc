from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel, EmailStr, ConfigDict

from inq_service_svc.models.enums import InquiryStatus, MessageSenderType


class InquiryCreate(BaseModel):
    title: str
    content: str
    customer_email: EmailStr
    customer_name: Optional[str] = None


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


class MessageResponse(BaseModel):
    id: int
    content: str
    sender_type: MessageSenderType
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)


class InquiryDetailResponse(InquiryResponse):
    messages: List[MessageResponse]

    model_config = ConfigDict(from_attributes=True)


# New request schema for reply endpoint
class ReplyRequest(BaseModel):
    content: str

    model_config = ConfigDict()

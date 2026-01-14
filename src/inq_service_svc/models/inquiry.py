from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from sqlalchemy import Enum as SAEnum

from .base import Base
from .enums import InquiryStatus, MessageSenderType


class Inquiry(Base):
    __tablename__ = "inquiries"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    customer_email = Column(String, nullable=False)
    status = Column(SAEnum(InquiryStatus, native_enum=False), nullable=False, default=InquiryStatus.New)
    category = Column(String, nullable=True)
    urgency = Column(String, nullable=True)
    assigned_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=func.now())

    assigned_user = relationship("User", back_populates="inquiries")
    messages = relationship("Message", back_populates="inquiry", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Inquiry(id={self.id}, title='{self.title}', status='{self.status}')>"


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    inquiry_id = Column(Integer, ForeignKey("inquiries.id"), nullable=False)
    content = Column(Text, nullable=False)
    sender_type = Column(SAEnum(MessageSenderType, native_enum=False), nullable=False)
    timestamp = Column(DateTime, default=func.now())

    inquiry = relationship("Inquiry", back_populates="messages")

    def __repr__(self) -> str:
        return f"<Message(id={self.id}, inquiry_id={self.inquiry_id}, sender_type='{self.sender_type}')>"

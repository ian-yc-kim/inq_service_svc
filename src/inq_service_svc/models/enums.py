from enum import Enum


class UserRole(str, Enum):
    Admin = "Admin"
    Staff = "Staff"


class InquiryStatus(str, Enum):
    New = "New"
    InProgress = "InProgress"
    On_Hold = "On-Hold"
    Completed = "Completed"


class MessageSenderType(str, Enum):
    Customer = "Customer"
    Staff = "Staff"

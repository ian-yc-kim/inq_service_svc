from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from inq_service_svc.models import User, Inquiry
from inq_service_svc.models.enums import UserRole, InquiryStatus

logger = logging.getLogger(__name__)


def assign_staff(db: Session) -> Optional[int]:
    """Return the staff user id with the minimum active workload or None.

    Workload counts inquiries assigned to the user with status New or On-Hold.
    Only users with role == UserRole.Staff are considered. Ties broken by user.id.
    Returns None when no staff users exist or on error.
    """
    try:
        # Active statuses to count
        active_statuses = [InquiryStatus.New, InquiryStatus.On_Hold]

        # Subquery: count active inquiries per assigned_user_id
        subq = (
            select(
                Inquiry.assigned_user_id.label("user_id"),
                func.count(Inquiry.id).label("workload"),
            )
            .where(
                Inquiry.status.in_(active_statuses),
                Inquiry.assigned_user_id != None,
            )
            .group_by(Inquiry.assigned_user_id)
            .subquery()
        )

        # Outer select users (only Staff) and coalesce workload to 0 for users with no active inquiries
        workload_col = func.coalesce(subq.c.workload, 0)

        stmt = (
            select(User.id, workload_col.label("workload"))
            .outerjoin(subq, User.id == subq.c.user_id)
            .where(User.role == UserRole.Staff)
            .order_by(workload_col.asc(), User.id.asc())
            .limit(1)
        )

        row = db.execute(stmt).first()
        if not row:
            return None

        user_id = row[0]
        return int(user_id)
    except Exception as e:
        logger.error(e, exc_info=True)
        # Fail-safe: return None on unexpected errors
        return None

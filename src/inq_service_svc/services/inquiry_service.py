from typing import Optional
import logging

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from inq_service_svc.models import User, Inquiry
from inq_service_svc.models.enums import UserRole, InquiryStatus

from inq_service_svc.schemas.inquiry import InquiryCreate
from inq_service_svc.services.classifier import (
    classify_inquiry,
    DEFAULT_CLASSIFICATION,
    ClassificationResult,
)

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


def create_inquiry(db: Session, inquiry_data: InquiryCreate) -> Inquiry:
    """Create and persist a new Inquiry, including classification and staff assignment.

    This function encapsulates the business logic of creating an inquiry. It does not
    perform side-effects like websocket broadcasting or sending emails.
    """
    try:
        # classification may fail but returns default result
        try:
            classification: ClassificationResult = classify_inquiry(inquiry_data.title, inquiry_data.content)
        except Exception as e:
            logger.error(e, exc_info=True)
            classification = DEFAULT_CLASSIFICATION

        # assignment may fail and return None
        try:
            assigned_user_id: Optional[int] = assign_staff(db)
        except Exception as e:
            logger.error(e, exc_info=True)
            assigned_user_id = None

        inquiry = Inquiry(
            title=inquiry_data.title,
            content=inquiry_data.content,
            customer_email=str(inquiry_data.customer_email),
            customer_name=inquiry_data.customer_name,
            status=InquiryStatus.New,
            category=classification.category,
            urgency=classification.urgency,
            assigned_user_id=assigned_user_id,
        )

        try:
            db.add(inquiry)
            db.commit()
            db.refresh(inquiry)
        except Exception as e:
            logger.error(e, exc_info=True)
            try:
                db.rollback()
            except Exception as ex:
                logger.error(ex, exc_info=True)
            # re-raise to let callers translate to HTTP responses
            raise

        return inquiry
    except Exception as e:
        logger.error(e, exc_info=True)
        raise

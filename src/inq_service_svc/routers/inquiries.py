from __future__ import annotations

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from inq_service_svc.models import Inquiry, get_db, User
from inq_service_svc.models.enums import InquiryStatus
from inq_service_svc.schemas.inquiry import InquiryCreate, InquiryResponse
from inq_service_svc.services.classifier import classify_inquiry, ClassificationResult
from inq_service_svc.services.inquiry_service import assign_staff
from inq_service_svc.utils.websocket_manager import manager
from inq_service_svc.routers.auth import get_current_user

logger = logging.getLogger(__name__)

inquiries_router = APIRouter()


@inquiries_router.get("/", response_model=List[InquiryResponse])
def list_inquiries(
    status: Optional[InquiryStatus] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[Inquiry]:
    """List inquiries. Optionally filter by status. Requires authentication."""
    try:
        stmt = select(Inquiry)
        if status is not None:
            stmt = stmt.where(Inquiry.status == status)

        inquiries = db.execute(stmt).scalars().all()
        return inquiries
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@inquiries_router.post("/", response_model=InquiryResponse, status_code=status.HTTP_201_CREATED)
def create_inquiry(
    payload: InquiryCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Inquiry:
    """Create a new inquiry, classify it, assign staff, persist, and broadcast event."""
    try:
        # classification may fail but returns default result
        try:
            classification: ClassificationResult = classify_inquiry(payload.title, payload.content)
        except Exception as e:
            logger.error(e, exc_info=True)
            classification = ClassificationResult(category="General", urgency="Medium")

        # assignment may fail and return None
        try:
            assigned_user_id: Optional[int] = assign_staff(db)
        except Exception as e:
            logger.error(e, exc_info=True)
            assigned_user_id = None

        inquiry = Inquiry(
            title=payload.title,
            content=payload.content,
            customer_email=str(payload.customer_email),
            customer_name=payload.customer_name,
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
            except Exception:
                pass
            raise HTTPException(status_code=500, detail="Internal server error")

        # schedule broadcast of new inquiry event
        try:
            message = json.dumps({"event": "new_inquiry", "inquiry_id": inquiry.id})
            # manager.broadcast is async; BackgroundTasks can accept callables including coroutines
            background_tasks.add_task(manager.broadcast, message)
        except Exception as e:
            logger.error(e, exc_info=True)

        return inquiry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

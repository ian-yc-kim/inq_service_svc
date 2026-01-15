from __future__ import annotations

import json
import logging
from typing import Optional, List

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select, update as sa_update
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from inq_service_svc.models import Inquiry, get_db, User
from inq_service_svc.models.enums import InquiryStatus
from inq_service_svc.schemas.inquiry import InquiryCreate, InquiryResponse, InquiryUpdate
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
            except Exception as ex:
                logger.error(ex, exc_info=True)
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


@inquiries_router.patch("/{inquiry_id}", response_model=InquiryResponse)
def update_inquiry(
    inquiry_id: int,
    payload: InquiryUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Inquiry:
    """Partially update inquiry status and/or assignment and broadcast the change."""
    try:
        inquiry = db.get(Inquiry, inquiry_id)
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if inquiry is None:
        raise HTTPException(status_code=404, detail="Inquiry not found")

    try:
        update_data = payload.model_dump(exclude_unset=True)

        values: dict = {}

        # Validate assigned_user_id if present (allow explicit None to clear assignment)
        if "assigned_user_id" in update_data:
            assigned_val = update_data.get("assigned_user_id")
            if assigned_val is not None:
                try:
                    user = db.execute(select(User).where(User.id == assigned_val)).scalar_one_or_none()
                except Exception as e:
                    logger.error(e, exc_info=True)
                    raise HTTPException(status_code=500, detail="Internal server error")
                if user is None:
                    raise HTTPException(status_code=400, detail="Assigned user not found")
            values["assigned_user_id"] = assigned_val

        if "status" in update_data:
            status_val = update_data.get("status")
            if status_val is not None:
                try:
                    # status_val should already be an InquiryStatus because schema uses the enum
                    if isinstance(status_val, InquiryStatus):
                        status_enum = status_val
                    else:
                        # Try by member name first, then by value
                        try:
                            status_enum = InquiryStatus[status_val]
                        except Exception:
                            status_enum = InquiryStatus(status_val)
                except Exception as e:
                    logger.error(e, exc_info=True)
                    raise HTTPException(status_code=400, detail="Invalid status value")
                values["status"] = status_enum

        # If there is nothing to update, return current inquiry (ensure fresh state)
        if not values:
            try:
                db.refresh(inquiry)
            except Exception as e:
                logger.error(e, exc_info=True)
            return inquiry

        # Perform an UPDATE statement to ensure persistence across sessions
        try:
            stmt = sa_update(Inquiry).where(Inquiry.id == inquiry_id).values(**values)
            db.execute(stmt)
            db.commit()
        except IntegrityError as e:
            logger.error(e, exc_info=True)
            try:
                db.rollback()
            except Exception as ex:
                logger.error(ex, exc_info=True)
            raise HTTPException(status_code=400, detail="Invalid assignment or data")
        except Exception as e:
            logger.error(e, exc_info=True)
            try:
                db.rollback()
            except Exception as ex:
                logger.error(ex, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

        # refresh the in-memory inquiry instance from DB to return and broadcast
        try:
            db.refresh(inquiry)
        except Exception as e:
            logger.error(e, exc_info=True)
            raise HTTPException(status_code=500, detail="Internal server error")

        # schedule websocket broadcast; failures should not break the request
        try:
            status_str = getattr(inquiry.status, "value", str(inquiry.status))
            message = json.dumps(
                {
                    "event": "inquiry_updated",
                    "inquiry_id": inquiry.id,
                    "status": status_str,
                    "assigned_user_id": inquiry.assigned_user_id,
                }
            )
            background_tasks.add_task(manager.broadcast, message)
        except Exception as e:
            logger.error(e, exc_info=True)

        return inquiry
    except HTTPException:
        raise
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

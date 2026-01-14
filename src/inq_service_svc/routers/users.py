from __future__ import annotations

import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from inq_service_svc.models import User, get_db
from inq_service_svc.models.enums import UserRole
import inq_service_svc.utils.security as security
from inq_service_svc.schemas.user import UserCreate, UserResponse, UserUpdate
from inq_service_svc.routers.auth import get_current_user

logger = logging.getLogger(__name__)

users_router = APIRouter()


def _require_admin(current_user: User) -> None:
    if current_user.role != UserRole.Admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")


@users_router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    _require_admin(current_user)

    try:
        existing = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if existing is not None:
        raise HTTPException(status_code=400, detail="Email already exists")

    try:
        hashed = security.get_password_hash(payload.password)
        user = User(email=payload.email, hashed_password=hashed, name=payload.name, role=payload.role)
        db.add(user)
        db.commit()
        db.refresh(user)
        return user
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@users_router.get("/", response_model=List[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> List[User]:
    _require_admin(current_user)

    try:
        users = db.execute(select(User)).scalars().all()
        return users
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@users_router.patch("/{user_id}", response_model=UserResponse)
def update_user(
    user_id: int,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> User:
    _require_admin(current_user)

    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        if payload.email is not None and payload.email != user.email:
            duplicate = db.execute(select(User).where(User.email == payload.email)).scalar_one_or_none()
            if duplicate is not None and duplicate.id != user.id:
                raise HTTPException(status_code=400, detail="Email already exists")
            user.email = payload.email

        if payload.password is not None:
            user.hashed_password = security.get_password_hash(payload.password)

        if payload.name is not None:
            user.name = payload.name

        if payload.role is not None:
            user.role = payload.role

        db.commit()
        db.refresh(user)
        return user
    except HTTPException:
        raise
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")


@users_router.delete("/{user_id}")
def delete_user(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)

    try:
        user = db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        db.delete(user)
        db.commit()
        return {"detail": "User deleted"}
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

import inq_service_svc.utils.security as security
from inq_service_svc.models import User, get_db
from inq_service_svc.schemas.auth import Token, LoginRequest

logger = logging.getLogger(__name__)

auth_router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = security.decode_access_token(token)
    except Exception as e:
        logger.error(e, exc_info=True)
        payload = None

    if payload is None:
        raise credential_exception

    email = payload.get("sub")
    if not email:
        raise credential_exception

    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if user is None:
        raise credential_exception

    return user


@auth_router.post("/login", response_model=Token)
async def login(request: LoginRequest, db: Session = Depends(get_db)) -> Token:
    credential_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        user = db.execute(select(User).where(User.email == request.email)).scalar_one_or_none()
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    if user is None:
        raise credential_exception

    try:
        verified = security.verify_password(request.password, user.hashed_password)
    except Exception as e:
        logger.error(e, exc_info=True)
        # treat verification errors as credential issues
        raise credential_exception

    if not verified:
        raise credential_exception

    try:
        access_token = security.create_access_token({"sub": user.email})
    except Exception as e:
        logger.error(e, exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

    return Token(access_token=access_token, token_type="bearer")

import pytest
from datetime import timedelta

from passlib.context import CryptContext
from fastapi import HTTPException

import inq_service_svc.utils.security as security
from inq_service_svc.models import User, UserRole
from inq_service_svc.routers.auth import get_current_user


@pytest.fixture(autouse=True)
def use_test_pwd_context(monkeypatch):
    # Use a pure-python reliable scheme and deterministic signing in tests
    ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    monkeypatch.setattr(security, "pwd_context", ctx)
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")
    yield


def create_user(db_session, email: str, password: str = "pw123") -> User:
    hashed = security.get_password_hash(password)
    user = User(email=email, name="Tester", role=UserRole.Staff, hashed_password=hashed)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_login_success_returns_token(client, db_session):
    email = "success@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)

    resp = client.post("/api/auth/login", json={"email": email, "password": pw})
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data and data["access_token"]
    assert data.get("token_type") == "bearer"


def test_login_failure_returns_401(client, db_session):
    email = "fail@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)

    resp = client.post("/api/auth/login", json={"email": email, "password": "wrong"})
    assert resp.status_code == 401


def test_get_current_user_valid_token_returns_user(db_session):
    email = "dep@example.com"
    user = create_user(db_session, email, "pw123")

    token = security.create_access_token({"sub": user.email}, expires_delta=timedelta(minutes=5))
    # call dependency function directly
    result = get_current_user(token=token, db=db_session)
    assert result.email == email


def test_get_current_user_invalid_token_raises_401(db_session):
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token="not-a-token", db=db_session)
    assert excinfo.value.status_code == 401


def test_get_current_user_expired_token_raises_401(db_session):
    email = "exp@example.com"
    user = create_user(db_session, email, "pw123")

    token = security.create_access_token({"sub": user.email}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token=token, db=db_session)
    assert excinfo.value.status_code == 401


def test_get_current_user_missing_email_claim_raises_401(db_session):
    email = "no-sub@example.com"
    create_user(db_session, email, "pw123")

    token = security.create_access_token({"foo": "bar"}, expires_delta=timedelta(minutes=5))
    with pytest.raises(HTTPException) as excinfo:
        get_current_user(token=token, db=db_session)
    assert excinfo.value.status_code == 401

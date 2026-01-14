import pytest
from datetime import timedelta, datetime, timezone

import inq_service_svc.utils.security as security
from inq_service_svc import config
from passlib.context import CryptContext


@pytest.fixture(autouse=True)
def use_test_pwd_context(monkeypatch):
    # Use a pure-python, reliable scheme in tests to avoid environment bcrypt issues
    ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    monkeypatch.setattr(security, "pwd_context", ctx)
    yield


def test_get_password_hash_and_verify_password_success():
    pw = "secret-password-123"
    hashed = security.get_password_hash(pw)
    assert hashed != pw
    assert security.verify_password(pw, hashed) is True
    assert security.verify_password("wrong-password", hashed) is False


def test_verify_password_invalid_hash_returns_false():
    # malformed hash should not raise, should return False
    assert security.verify_password("pw", "not-a-real-hash") is False


def test_get_password_hash_invalid_input():
    with pytest.raises(ValueError):
        security.get_password_hash("")
    with pytest.raises(ValueError):
        # type: ignore - ensure non-str triggers validation
        security.get_password_hash(None)  # type: ignore


def test_verify_password_invalid_input():
    with pytest.raises(ValueError):
        security.verify_password("", "hash")
    with pytest.raises(ValueError):
        security.verify_password("pw", "")


def test_create_and_decode_access_token_valid(monkeypatch):
    # Ensure deterministic signing in tests
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")

    data = {"sub": "user@example.com"}
    token = security.create_access_token(data, expires_delta=timedelta(minutes=5))
    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload.get("sub") == "user@example.com"
    assert "exp" in payload


def test_decode_access_token_expired_returns_none(monkeypatch):
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")

    token = security.create_access_token({"sub": "u"}, expires_delta=timedelta(seconds=-1))
    assert security.decode_access_token(token) is None


def test_decode_access_token_invalid_returns_none():
    assert security.decode_access_token("this-is-not-a-token") is None


def test_create_access_token_uses_default_expiration(monkeypatch):
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")
    # set default minutes and create token without explicit expires_delta
    monkeypatch.setattr(security.config, "ACCESS_TOKEN_EXPIRE_MINUTES", 60)

    token = security.create_access_token({"sub": "user@example.com"})
    payload = security.decode_access_token(token)
    assert payload is not None
    assert "exp" in payload
    exp = int(payload["exp"])
    now = int(datetime.now(timezone.utc).timestamp())
    # allow small timing drift
    assert (now + 60 * 60 - 5) <= exp <= (now + 60 * 60 + 5)

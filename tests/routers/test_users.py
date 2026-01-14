import pytest
from sqlalchemy import select
from passlib.context import CryptContext

import inq_service_svc.utils.security as security
from inq_service_svc.models import User, UserRole


@pytest.fixture(autouse=True)
def use_test_pwd_context(monkeypatch):
    # Use a deterministic hashing scheme for tests and fixed JWT config
    ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    monkeypatch.setattr(security, "pwd_context", ctx)
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")
    yield


def create_user(db_session, email: str, password: str = "pw12345678", role: UserRole = UserRole.Staff) -> User:
    hashed = security.get_password_hash(password)
    user = User(email=email, name="Tester", role=role, hashed_password=hashed)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_auth_header(client, email: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_admin_crud_success(client, db_session):
    admin = create_user(db_session, "admin@example.com", "adminpass", role=UserRole.Admin)
    headers = get_auth_header(client, "admin@example.com", "adminpass")

    # Create user
    resp = client.post(
        "/api/users",
        json={"email": "u1@example.com", "password": "pw12345678", "name": "User1", "role": "Staff"},
        headers=headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["email"] == "u1@example.com"
    assert "password" not in data
    user_id = data["id"]

    # List users
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 200
    assert any(u["email"] == "u1@example.com" for u in resp.json())

    # Update user (name and password)
    resp = client.patch(
        f"/api/users/{user_id}", json={"name": "NewName", "password": "newpassword"}, headers=headers
    )
    assert resp.status_code == 200
    data2 = resp.json()
    assert data2["name"] == "NewName"

    # verify password hashed and can be verified
    stmt = select(User).where(User.id == user_id)
    fetched = db_session.execute(stmt).scalar_one()
    assert fetched.hashed_password != "newpassword"
    assert security.verify_password("newpassword", fetched.hashed_password)

    # Delete user
    resp = client.delete(f"/api/users/{user_id}", headers=headers)
    assert resp.status_code == 200

    # Ensure removed
    resp = client.get("/api/users", headers=headers)
    assert all(u["email"] != "u1@example.com" for u in resp.json())


def test_staff_forbidden_all_endpoints(client, db_session):
    staff = create_user(db_session, "staff@example.com", "staffpw", role=UserRole.Staff)
    headers = get_auth_header(client, "staff@example.com", "staffpw")

    # POST
    resp = client.post(
        "/api/users",
        json={"email": "u2@example.com", "password": "pw12345678", "name": "User2", "role": "Staff"},
        headers=headers,
    )
    assert resp.status_code == 403

    # GET
    resp = client.get("/api/users", headers=headers)
    assert resp.status_code == 403

    # PATCH
    resp = client.patch("/api/users/1", json={"name": "x"}, headers=headers)
    assert resp.status_code == 403

    # DELETE
    resp = client.delete("/api/users/1", headers=headers)
    assert resp.status_code == 403


def test_unauthenticated_access_returns_401(client):
    resp = client.get("/api/users")
    assert resp.status_code == 401

    resp = client.post(
        "/api/users",
        json={"email": "u3@example.com", "password": "pw12345678", "name": "User3", "role": "Staff"},
    )
    assert resp.status_code == 401


def test_duplicate_email_creation_returns_400(client, db_session):
    admin = create_user(db_session, "admin2@example.com", "adminpass", role=UserRole.Admin)
    headers = get_auth_header(client, "admin2@example.com", "adminpass")

    resp = client.post(
        "/api/users",
        json={"email": "dup@example.com", "password": "pw12345678", "name": "Dup", "role": "Staff"},
        headers=headers,
    )
    assert resp.status_code == 201

    resp2 = client.post(
        "/api/users",
        json={"email": "dup@example.com", "password": "pw12345678", "name": "Dup2", "role": "Staff"},
        headers=headers,
    )
    assert resp2.status_code == 400


def test_invalid_input_short_password_returns_422(client, db_session):
    admin = create_user(db_session, "admin3@example.com", "adminpass", role=UserRole.Admin)
    headers = get_auth_header(client, "admin3@example.com", "adminpass")

    resp = client.post(
        "/api/users",
        json={"email": "badpass@example.com", "password": "short", "name": "Bad", "role": "Staff"},
        headers=headers,
    )
    assert resp.status_code == 422

    # create valid user then attempt patch with short password
    resp_ok = client.post(
        "/api/users",
        json={"email": "ok@example.com", "password": "longenough", "name": "OK", "role": "Staff"},
        headers=headers,
    )
    assert resp_ok.status_code == 201
    uid = resp_ok.json()["id"]

    resp_patch = client.patch(f"/api/users/{uid}", json={"password": "short"}, headers=headers)
    assert resp_patch.status_code == 422


def test_password_hashing_on_create_and_update(client, db_session):
    admin = create_user(db_session, "admin4@example.com", "adminpass", role=UserRole.Admin)
    headers = get_auth_header(client, "admin4@example.com", "adminpass")

    # create new user
    resp = client.post(
        "/api/users",
        json={"email": "hashme@example.com", "password": "securepass", "name": "HashMe", "role": "Staff"},
        headers=headers,
    )
    assert resp.status_code == 201
    uid = resp.json()["id"]

    stmt = select(User).where(User.id == uid)
    fetched = db_session.execute(stmt).scalar_one()
    # capture old hash snapshot before update
    old_hash = fetched.hashed_password
    assert old_hash != "securepass"
    assert security.verify_password("securepass", old_hash)

    # update password
    resp_up = client.patch(f"/api/users/{uid}", json={"password": "newsecure"}, headers=headers)
    assert resp_up.status_code == 200

    # ensure the test session sees DB changes by expiring cached state
    db_session.expire_all()

    fetched2 = db_session.execute(stmt).scalar_one()
    assert fetched2.hashed_password != old_hash
    assert security.verify_password("newsecure", fetched2.hashed_password)

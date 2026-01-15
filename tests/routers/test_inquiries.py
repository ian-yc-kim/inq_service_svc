import json
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select
from passlib.context import CryptContext

import inq_service_svc.utils.security as security
from inq_service_svc.models import Inquiry
from inq_service_svc.models.enums import InquiryStatus
from inq_service_svc.services.classifier import ClassificationResult


VALID_PAYLOAD = {
    "title": "Billing question",
    "content": "I was charged twice",
    "customer_email": "cust@example.com",
    "customer_name": "Customer",
}


@pytest.fixture(autouse=True)
def use_test_pwd_context(monkeypatch):
    # Ensure deterministic hashing and JWT settings in tests
    ctx = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
    monkeypatch.setattr(security, "pwd_context", ctx)
    monkeypatch.setattr(security.config, "SECRET_KEY", "test-secret")
    monkeypatch.setattr(security.config, "ALGORITHM", "HS256")
    yield


def create_user(db_session, email: str, password: str = "pw123"):
    hashed = security.get_password_hash(password)
    # role defaults to Staff in model; supply minimal fields
    from inq_service_svc.models import User, UserRole

    user = User(email=email, name="Tester", role=UserRole.Staff, hashed_password=hashed)
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def get_auth_header(client, email: str, password: str) -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_create_inquiry_success_persists_and_returns(client, db_session):
    # Patch classifier and assign_staff used in router
    with patch("inq_service_svc.routers.inquiries.classify_inquiry") as mock_classify, \
        patch("inq_service_svc.routers.inquiries.assign_staff") as mock_assign, \
        patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_classify.return_value = ClassificationResult(category="Billing", urgency="High")
        mock_assign.return_value = 1
        # ensure broadcast is an async mock so background tasks don't error
        mock_manager.broadcast = AsyncMock()

        resp = client.post("/api/inquiries/", json=VALID_PAYLOAD)
        assert resp.status_code == 201
        data = resp.json()
        assert "id" in data
        assert data["title"] == VALID_PAYLOAD["title"]
        assert data["category"] == "Billing"
        assert data["urgency"] == "High"
        assert data["assigned_user_id"] == 1

        # verify persisted in DB
        stmt = select(Inquiry).where(Inquiry.id == data["id"])
        fetched = db_session.execute(stmt).scalar_one()
        assert fetched.title == VALID_PAYLOAD["title"]
        assert fetched.customer_email == VALID_PAYLOAD["customer_email"]
        assert fetched.category == "Billing"


def test_create_inquiry_invalid_email_returns_422(client):
    payload = VALID_PAYLOAD.copy()
    payload["customer_email"] = "not-an-email"

    resp = client.post("/api/inquiries/", json=payload)
    assert resp.status_code == 422
    body = resp.json()
    # pydantic error should mention customer_email
    assert any("customer_email" in str(err) or err.get("loc") for err in body.get("detail", []))


def test_list_inquiries_authenticated_returns_all(client, db_session):
    # create staff user and obtain auth header
    email = "staff@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiries directly in DB
    i1 = Inquiry(title="T1", content="c1", customer_email="a@example.com", customer_name="A", status=InquiryStatus.New)
    i2 = Inquiry(title="T2", content="c2", customer_email="b@example.com", customer_name="B", status=InquiryStatus.Completed)
    db_session.add_all([i1, i2])
    db_session.commit()

    resp = client.get("/api/inquiries", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    titles = {item["title"] for item in data}
    assert {"T1", "T2"} <= titles


def test_list_inquiries_filter_by_status(client, db_session):
    email = "staff2@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiries with different statuses
    new1 = Inquiry(title="New1", content="x", customer_email="x@example.com", customer_name="X", status=InquiryStatus.New)
    comp1 = Inquiry(title="Comp1", content="y", customer_email="y@example.com", customer_name="Y", status=InquiryStatus.Completed)
    comp2 = Inquiry(title="Comp2", content="z", customer_email="z@example.com", customer_name="Z", status=InquiryStatus.Completed)
    db_session.add_all([new1, comp1, comp2])
    db_session.commit()

    resp = client.get("/api/inquiries?status=Completed", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 2
    assert all(item["status"] == "Completed" for item in data)


def test_list_inquiries_unauthenticated_returns_401(client):
    resp = client.get("/api/inquiries")
    assert resp.status_code == 401


# New tests for PATCH /api/inquiries/{id}

def test_patch_inquiry_update_status_success_broadcasts(client, db_session):
    # prepare users and auth
    email = "patcher@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiry
    inq = Inquiry(title="Updatable", content="x", customer_email="u@example.com", customer_name="U", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    with patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.patch(f"/api/inquiries/{inq.id}", json={"status": "Completed"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "Completed"

        # ensure test session sees DB changes
        db_session.expire_all()

        # verify DB updated
        stmt = select(Inquiry).where(Inquiry.id == inq.id)
        fetched = db_session.execute(stmt).scalar_one()
        assert fetched.status == InquiryStatus.Completed

        # verify broadcast called with correct payload
        assert mock_manager.broadcast.call_count == 1
        called_arg = mock_manager.broadcast.call_args[0][0]
        payload = json.loads(called_arg)
        assert payload["event"] == "inquiry_updated"
        assert payload["inquiry_id"] == inq.id
        assert payload["status"] == "Completed"
        assert payload.get("assigned_user_id") == fetched.assigned_user_id


def test_patch_inquiry_update_assigned_user_id_success_broadcasts(client, db_session):
    # prepare users and auth
    author_email = "assigner@example.com"
    pw = "pw123"
    create_user(db_session, author_email, pw)
    headers = get_auth_header(client, author_email, pw)

    # create assignee user
    assignee = create_user(db_session, "assignee@example.com", "pw123")

    # create inquiry without assignment
    inq = Inquiry(title="AssignMe", content="y", customer_email="a@example.com", customer_name="A", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    with patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.patch(f"/api/inquiries/{inq.id}", json={"assigned_user_id": assignee.id}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["assigned_user_id"] == assignee.id

        # ensure test session sees DB changes
        db_session.expire_all()

        # verify DB updated
        stmt = select(Inquiry).where(Inquiry.id == inq.id)
        fetched = db_session.execute(stmt).scalar_one()
        assert fetched.assigned_user_id == assignee.id

        # verify broadcast
        assert mock_manager.broadcast.call_count == 1
        called_arg = mock_manager.broadcast.call_args[0][0]
        payload = json.loads(called_arg)
        assert payload["event"] == "inquiry_updated"
        assert payload["inquiry_id"] == inq.id
        assert payload["assigned_user_id"] == assignee.id


def test_patch_inquiry_not_found_returns_404(client, db_session):
    email = "notfoundtester@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    with patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.patch("/api/inquiries/9999", json={"status": "Completed"}, headers=headers)
        assert resp.status_code == 404
        assert mock_manager.broadcast.call_count == 0


def test_patch_inquiry_invalid_assigned_user_id_returns_400(client, db_session):
    # prepare users and auth
    email = "invalidassigner@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiry
    inq = Inquiry(title="T", content="c", customer_email="e@example.com", customer_name="N", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    with patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.patch(f"/api/inquiries/{inq.id}", json={"assigned_user_id": 99999}, headers=headers)
        assert resp.status_code == 400
        assert mock_manager.broadcast.call_count == 0


def test_patch_inquiry_unauthenticated_returns_401(client, db_session):
    # create inquiry
    inq = Inquiry(title="NoAuth", content="z", customer_email="na@example.com", customer_name="NA", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    # no auth header provided
    resp = client.patch(f"/api/inquiries/{inq.id}", json={"status": "Completed"})
    assert resp.status_code == 401


def test_patch_inquiry_update_both_fields_success_broadcasts(client, db_session):
    # prepare users and auth
    author_email = "bothfields@example.com"
    pw = "pw123"
    create_user(db_session, author_email, pw)
    headers = get_auth_header(client, author_email, pw)

    # create assignee user
    assignee = create_user(db_session, "both_assignee@example.com", "pw123")

    # create inquiry
    inq = Inquiry(title="Both", content="both", customer_email="both@example.com", customer_name="B", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    with patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.patch(
            f"/api/inquiries/{inq.id}",
            json={"status": "InProgress", "assigned_user_id": assignee.id},
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "InProgress"
        assert data["assigned_user_id"] == assignee.id

        # ensure test session sees DB changes
        db_session.expire_all()

        stmt = select(Inquiry).where(Inquiry.id == inq.id)
        fetched = db_session.execute(stmt).scalar_one()
        assert fetched.status == InquiryStatus.InProgress
        assert fetched.assigned_user_id == assignee.id

        assert mock_manager.broadcast.call_count == 1
        called_arg = mock_manager.broadcast.call_args[0][0]
        payload = json.loads(called_arg)
        assert payload["event"] == "inquiry_updated"
        assert payload["inquiry_id"] == inq.id
        assert payload["status"] == "InProgress"
        assert payload["assigned_user_id"] == assignee.id


# New tests for GET /api/inquiries/{id}

def test_get_inquiry_detail_success(client, db_session):
    # prepare user and auth
    email = "detailtester@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiry and messages
    inq = Inquiry(title="Detail", content="detail content", customer_email="d@example.com", customer_name="D", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    # import Message model and enum
    from inq_service_svc.models import Message
    from inq_service_svc.models.enums import MessageSenderType

    msg1 = Message(inquiry_id=inq.id, content="First message", sender_type=MessageSenderType.Customer)
    msg2 = Message(inquiry_id=inq.id, content="Staff reply", sender_type=MessageSenderType.Staff)
    db_session.add_all([msg1, msg2])
    db_session.commit()

    resp = client.get(f"/api/inquiries/{inq.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == inq.id
    assert data["title"] == "Detail"
    assert "messages" in data
    assert isinstance(data["messages"], list)
    assert len(data["messages"]) >= 2

    # verify messages shape
    for m in data["messages"]:
        assert "id" in m
        assert "content" in m
        assert "sender_type" in m
        assert "timestamp" in m
        assert m["sender_type"] in {"Customer", "Staff"}


def test_get_inquiry_detail_not_found(client, db_session):
    email = "notfounddetail@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    resp = client.get("/api/inquiries/999999", headers=headers)
    assert resp.status_code == 404
    assert resp.json().get("detail") == "Inquiry not found"


# New tests for POST /api/inquiries/{id}/reply

def test_reply_inquiry_success_saves_message_updates_status_and_notifies(client, db_session):
    # prepare user and auth
    email = "replier@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    # create inquiry
    inq = Inquiry(title="Replyable", content="orig", customer_email="custreply@example.com", customer_name="C", status=InquiryStatus.New)
    db_session.add(inq)
    db_session.commit()
    db_session.refresh(inq)

    from inq_service_svc.models import Message
    from inq_service_svc.models.enums import MessageSenderType

    with patch("inq_service_svc.routers.inquiries.send_email") as mock_send, patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.post(f"/api/inquiries/{inq.id}/reply", json={"content": "This is a staff reply"}, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["content"] == "This is a staff reply"
        assert data["sender_type"] == "Staff"
        assert "id" in data

        # ensure DB session sees changes
        db_session.expire_all()

        # verify message persisted
        stmt = select(Message).where(Message.inquiry_id == inq.id)
        fetched_msg = db_session.execute(stmt).scalars().all()
        # there should be at least one message (the reply)
        assert any(m.content == "This is a staff reply" for m in fetched_msg)

        # verify inquiry status updated
        stmt_inq = select(Inquiry).where(Inquiry.id == inq.id)
        fetched_inq = db_session.execute(stmt_inq).scalar_one()
        assert fetched_inq.status == InquiryStatus.Completed

        # verify send_email called with correct args
        mock_send.assert_called_once_with(inq.customer_email, f"Re: {inq.title}", "This is a staff reply")

        # verify websocket broadcast called
        assert mock_manager.broadcast.call_count == 1
        called_arg = mock_manager.broadcast.call_args[0][0]
        payload = json.loads(called_arg)
        assert payload["event"] == "inquiry_updated"
        assert payload["inquiry_id"] == inq.id
        assert payload["status"] == "Completed"


def test_reply_inquiry_not_found_returns_404_and_no_notifications(client, db_session):
    email = "replynotfound@example.com"
    pw = "pw123"
    create_user(db_session, email, pw)
    headers = get_auth_header(client, email, pw)

    with patch("inq_service_svc.routers.inquiries.send_email") as mock_send, patch("inq_service_svc.routers.inquiries.manager") as mock_manager:
        mock_manager.broadcast = AsyncMock()

        resp = client.post("/api/inquiries/999999/reply", json={"content": "No one"}, headers=headers)
        assert resp.status_code == 404
        assert mock_send.call_count == 0
        assert mock_manager.broadcast.call_count == 0

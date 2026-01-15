import json
from unittest.mock import patch, AsyncMock

import pytest
from sqlalchemy import select

from inq_service_svc.models import Inquiry
from inq_service_svc.services.classifier import ClassificationResult


VALID_PAYLOAD = {
    "title": "Billing question",
    "content": "I was charged twice",
    "customer_email": "cust@example.com",
    "customer_name": "Customer",
}


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

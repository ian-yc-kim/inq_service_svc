import types
from unittest.mock import MagicMock

import pytest

from inq_service_svc.services import email_processor
from inq_service_svc.schemas.inquiry import InquiryCreate


def make_msg(from_, subject=None, text=None, html=None):
    return types.SimpleNamespace(from_=from_, subject=subject, text=text, html=html)


def test_process_incoming_emails_creates_inquiry(monkeypatch):
    # No blacklist
    monkeypatch.setattr(email_processor.config, "EMAIL_DOMAIN_BLACKLIST", "")

    msg = make_msg("Alice <alice@example.com>", subject="Hello", text="Body", html=None)

    mock_fetch = MagicMock(return_value=[msg])
    monkeypatch.setattr(email_processor, "fetch_emails", mock_fetch)

    mock_session = MagicMock()
    mock_session.close = MagicMock()
    mock_sessionlocal = MagicMock(return_value=mock_session)
    monkeypatch.setattr(email_processor, "SessionLocal", mock_sessionlocal)

    mock_create = MagicMock()
    monkeypatch.setattr(email_processor.inquiry_service, "create_inquiry", mock_create)

    email_processor.process_incoming_emails()

    mock_create.assert_called_once()
    called_args = mock_create.call_args[0]
    # first arg is session, second is InquiryCreate
    assert called_args[0] is mock_session
    inquiry_obj = called_args[1]
    assert isinstance(inquiry_obj, InquiryCreate)
    assert inquiry_obj.title == "Hello"
    assert inquiry_obj.content == "Body"
    assert str(inquiry_obj.customer_email) == "alice@example.com"
    assert inquiry_obj.customer_name == "Alice"
    mock_session.close.assert_called_once()


def test_process_incoming_emails_skips_blacklisted(monkeypatch):
    monkeypatch.setattr(email_processor.config, "EMAIL_DOMAIN_BLACKLIST", "example.com")

    msg = make_msg("Alice <alice@example.com>", subject="Hello", text="Body")
    monkeypatch.setattr(email_processor, "fetch_emails", MagicMock(return_value=[msg]))

    mock_session = MagicMock()
    mock_session.close = MagicMock()
    monkeypatch.setattr(email_processor, "SessionLocal", MagicMock(return_value=mock_session))

    mock_create = MagicMock()
    monkeypatch.setattr(email_processor.inquiry_service, "create_inquiry", mock_create)

    mock_logger = MagicMock()
    monkeypatch.setattr(email_processor, "logger", mock_logger)

    email_processor.process_incoming_emails()

    mock_create.assert_not_called()
    mock_logger.warning.assert_called_once()
    mock_session.close.assert_called_once()


def test_process_incoming_emails_continues_on_error(monkeypatch):
    monkeypatch.setattr(email_processor.config, "EMAIL_DOMAIN_BLACKLIST", "")

    msg1 = make_msg("A <a@example.com>", subject="S1", text="T1")
    msg2 = make_msg("B <b@example.org>", subject="S2", text="T2")
    monkeypatch.setattr(email_processor, "fetch_emails", MagicMock(return_value=[msg1, msg2]))

    mock_session = MagicMock()
    mock_session.close = MagicMock()
    monkeypatch.setattr(email_processor, "SessionLocal", MagicMock(return_value=mock_session))

    def side_effect_create(session, inquiry):
        if str(inquiry.customer_email).endswith("example.com"):
            raise Exception("boom")
        return None

    mock_create = MagicMock(side_effect=side_effect_create)
    monkeypatch.setattr(email_processor.inquiry_service, "create_inquiry", mock_create)

    mock_logger = MagicMock()
    monkeypatch.setattr(email_processor, "logger", mock_logger)

    email_processor.process_incoming_emails()

    assert mock_create.call_count == 2
    # error logged for first failure
    assert mock_logger.error.call_count >= 1
    mock_session.close.assert_called_once()


def test_content_selection_prefers_text_then_html(monkeypatch):
    monkeypatch.setattr(email_processor.config, "EMAIL_DOMAIN_BLACKLIST", "")

    msg = make_msg("C <c@ex.org>", subject="S", text=None, html="<p>Hi</p>")
    monkeypatch.setattr(email_processor, "fetch_emails", MagicMock(return_value=[msg]))

    mock_session = MagicMock()
    mock_session.close = MagicMock()
    monkeypatch.setattr(email_processor, "SessionLocal", MagicMock(return_value=mock_session))

    mock_create = MagicMock()
    monkeypatch.setattr(email_processor.inquiry_service, "create_inquiry", mock_create)

    email_processor.process_incoming_emails()

    mock_create.assert_called_once()
    inquiry_obj = mock_create.call_args[0][1]
    assert inquiry_obj.content == "<p>Hi</p>"

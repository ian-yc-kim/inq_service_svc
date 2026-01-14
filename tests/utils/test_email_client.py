import logging
from unittest.mock import MagicMock, patch

import pytest

from inq_service_svc.utils import email_client


def setup_config(monkeypatch):
    # Ensure predictable configuration for tests
    monkeypatch.setattr(email_client.config, "EMAIL_IMAP_SERVER", "imap.example.com")
    monkeypatch.setattr(email_client.config, "EMAIL_IMAP_PORT", 993)
    monkeypatch.setattr(email_client.config, "EMAIL_SMTP_SERVER", "smtp.example.com")
    monkeypatch.setattr(email_client.config, "EMAIL_SMTP_PORT", 587)
    monkeypatch.setattr(email_client.config, "EMAIL_ACCOUNT", "me@example.com")
    monkeypatch.setattr(email_client.config, "EMAIL_PASSWORD", "secret")


def test_fetch_emails_happy_path(monkeypatch):
    setup_config(monkeypatch)
    mock_mailbox_cls = MagicMock()
    mailbox_cm = mock_mailbox_cls.return_value.login.return_value.__enter__.return_value
    mailbox_cm.fetch.return_value = ["msg1", "msg2"]

    with patch("inq_service_svc.utils.email_client.MailBox", mock_mailbox_cls):
        result = email_client.fetch_emails(limit=2, folder="INBOX")

    # Verify MailBox constructed with correct server and port
    mock_mailbox_cls.assert_called_with("imap.example.com", 993)
    # Verify login called with account and password and initial_folder
    mock_mailbox_cls.return_value.login.assert_called_with(
        "me@example.com", "secret", initial_folder="INBOX"
    )
    # Verify fetch called with limit
    mailbox_cm.fetch.assert_called_with(limit=2)
    assert result == ["msg1", "msg2"]


def test_fetch_emails_invalid_inputs():
    with pytest.raises(ValueError):
        email_client.fetch_emails(limit=0, folder="INBOX")
    with pytest.raises(ValueError):
        email_client.fetch_emails(limit=1, folder="")


def test_fetch_emails_failure_logs_and_raises(monkeypatch):
    setup_config(monkeypatch)
    mock_mailbox_cls = MagicMock()
    mailbox_cm = mock_mailbox_cls.return_value.login.return_value.__enter__.return_value
    mailbox_cm.fetch.side_effect = Exception("boom")

    with patch("inq_service_svc.utils.email_client.MailBox", mock_mailbox_cls):
        with patch("inq_service_svc.utils.email_client._logger.error") as mock_log_error:
            with pytest.raises(RuntimeError):
                email_client.fetch_emails(limit=1, folder="INBOX")
            # logging.error should be called once with exc_info=True
            mock_log_error.assert_called_once()
            assert mock_log_error.call_args.kwargs.get("exc_info") is True


def test_send_email_happy_path(monkeypatch):
    setup_config(monkeypatch)
    mock_smtp_cls = MagicMock()
    smtp_cm = mock_smtp_cls.return_value.__enter__.return_value

    with patch("inq_service_svc.utils.email_client.smtplib.SMTP", mock_smtp_cls):
        email_client.send_email("you@example.com", "subject", "body")

    mock_smtp_cls.assert_called_with("smtp.example.com", 587)
    smtp_cm.starttls.assert_called_once()
    smtp_cm.login.assert_called_with("me@example.com", "secret")
    smtp_cm.send_message.assert_called_once()


def test_send_email_invalid_inputs():
    with pytest.raises(ValueError):
        email_client.send_email("", "sub", "body")
    with pytest.raises(ValueError):
        email_client.send_email("a@b.com", "", "body")
    with pytest.raises(ValueError):
        email_client.send_email("a@b.com", "sub", "")


def test_send_email_failure_logs_and_raises(monkeypatch):
    setup_config(monkeypatch)
    mock_smtp_cls = MagicMock()
    smtp_cm = mock_smtp_cls.return_value.__enter__.return_value
    smtp_cm.send_message.side_effect = Exception("boom")

    with patch("inq_service_svc.utils.email_client.smtplib.SMTP", mock_smtp_cls):
        with patch("inq_service_svc.utils.email_client._logger.error") as mock_log_error:
            with pytest.raises(RuntimeError):
                email_client.send_email("you@example.com", "subject", "body")
            mock_log_error.assert_called_once()
            assert mock_log_error.call_args.kwargs.get("exc_info") is True

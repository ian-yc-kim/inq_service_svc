import logging
from typing import List

from imap_tools import MailBox, AND
import smtplib
from email.message import EmailMessage

from inq_service_svc import config

_logger = logging.getLogger(__name__)


def fetch_emails(limit: int = 10, folder: str = "INBOX", only_unread: bool = True) -> List[object]:
    """Fetch recent emails from the configured IMAP server.

    Returns a list of message objects from imap-tools.
    Raises ValueError for invalid inputs and RuntimeError on failures.
    """
    if limit <= 0:
        raise ValueError("limit must be > 0")
    if not folder:
        raise ValueError("folder must be a non-empty string")

    try:
        # MailBox(host, port).login(user, password, initial_folder=...)
        with MailBox(config.EMAIL_IMAP_SERVER, config.EMAIL_IMAP_PORT).login(
            config.EMAIL_ACCOUNT, config.EMAIL_PASSWORD, initial_folder=folder
        ) as mailbox:
            if only_unread:
                messages = list(mailbox.fetch(AND(seen=False), limit=limit))
            else:
                messages = list(mailbox.fetch(limit=limit))
            return messages
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise RuntimeError("Failed to fetch emails") from e


def send_email(to_email: str, subject: str, body: str) -> None:
    """Send an email using configured SMTP server.

    Validates inputs and raises ValueError on invalid input, RuntimeError on send failure.
    """
    if not to_email:
        raise ValueError("to_email must be provided")
    if not subject:
        raise ValueError("subject must be provided")
    if not body:
        raise ValueError("body must be provided")

    msg = EmailMessage()
    msg["From"] = config.EMAIL_ACCOUNT
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(config.EMAIL_SMTP_SERVER, config.EMAIL_SMTP_PORT) as smtp:
            smtp.starttls()
            smtp.login(config.EMAIL_ACCOUNT, config.EMAIL_PASSWORD)
            smtp.send_message(msg)
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise RuntimeError("Failed to send email") from e

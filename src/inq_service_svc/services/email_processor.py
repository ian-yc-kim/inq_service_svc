import logging
from email.utils import parseaddr
from typing import List

from inq_service_svc import config
from inq_service_svc.models.base import SessionLocal
from inq_service_svc.schemas.inquiry import InquiryCreate
from inq_service_svc.utils.email_client import fetch_emails
from inq_service_svc.services import inquiry_service

logger = logging.getLogger(__name__)


def _parse_blacklist() -> List[str]:
    raw = getattr(config, "EMAIL_DOMAIN_BLACKLIST", "") or ""
    parts = [p.strip().lower() for p in raw.split(",") if p.strip()]
    return parts


def process_incoming_emails() -> None:
    """Fetch unread emails and create inquiries for non-blacklisted senders.

    Each message is handled independently; failures for one message do not stop processing.
    Ensures DB session is closed after processing.
    """
    blacklist = _parse_blacklist()

    session = None
    try:
        session = SessionLocal()
    except Exception as e:
        logger.error(e, exc_info=True)
        return

    try:
        try:
            messages = fetch_emails(limit=10, only_unread=True)
        except Exception as e:
            logger.error(e, exc_info=True)
            return

        for msg in messages:
            try:
                # Extract name and email robustly
                raw_from = getattr(msg, "from_", "") or getattr(msg, "from", "")
                name, email_addr = parseaddr(raw_from)
                email_addr = (email_addr or "").strip()
                domain = email_addr.split("@")[-1].lower() if "@" in email_addr else ""

                if domain and domain in blacklist:
                    logger.warning("Skipping blacklisted sender domain %s for %s", domain, email_addr)
                    continue

                title = getattr(msg, "subject", None) or "(no subject)"
                # prefer plain text, fall back to html
                content = getattr(msg, "text", None) or getattr(msg, "html", None) or ""
                customer_name = name or None

                inquiry_create = InquiryCreate(
                    title=title,
                    content=content,
                    customer_email=email_addr,
                    customer_name=customer_name,
                )

                try:
                    inquiry_service.create_inquiry(session, inquiry_create)
                except Exception as e:
                    logger.error(e, exc_info=True)
                    # continue to next message
                    continue

            except Exception as e:
                logger.error(e, exc_info=True)
                continue
    finally:
        try:
            if session is not None:
                session.close()
        except Exception as e:
            logger.error(e, exc_info=True)

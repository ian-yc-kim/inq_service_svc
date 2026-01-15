import os
import logging
from dotenv import load_dotenv

load_dotenv()

# Basic configuration loaded from environment with safe defaults for development
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///:memory:")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_NAME = os.getenv("OPENAI_MODEL_NAME", "gpt-4o")

# Email configuration
EMAIL_IMAP_SERVER = os.getenv("EMAIL_IMAP_SERVER")
EMAIL_SMTP_SERVER = os.getenv("EMAIL_SMTP_SERVER")
EMAIL_ACCOUNT = os.getenv("EMAIL_ACCOUNT")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")

# Keep simple integer parsing for email ports (restore original behavior)
EMAIL_SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
EMAIL_IMAP_PORT = int(os.getenv("EMAIL_IMAP_PORT", "993"))

# Security / JWT configuration
# SECRET_KEY should be overridden in production via environment
SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
try:
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))
except Exception as e:
    logging.error(e, exc_info=True)
    ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Comma separated list of blacklisted sender domains
EMAIL_DOMAIN_BLACKLIST: str = os.getenv("EMAIL_DOMAIN_BLACKLIST", "")

# New: polling interval for background email processing in minutes
try:
    EMAIL_POLLING_INTERVAL: int = int(os.getenv("EMAIL_POLLING_INTERVAL", "5"))
except Exception as e:
    logging.error(e, exc_info=True)
    EMAIL_POLLING_INTERVAL = 5

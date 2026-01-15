# inq_service_svc

AI Customer Inquiry Auto-Classification backend service.

This FastAPI service handles inquiry ingestion, persistence, AI-driven classification, email integration, and real-time updates.

## Configuration

The application reads configuration from environment variables (for development use `.env`). The following environment variables are required for normal operation:

- `OPENAI_API_KEY` — OpenAI API key used for inquiry classification (required).
- `EMAIL_IMAP_SERVER` — IMAP server hostname used to ingest incoming emails (required).
- `EMAIL_SMTP_SERVER` — SMTP server hostname used to send outgoing emails (required).
- `EMAIL_ACCOUNT` — Email account username or address used for IMAP/SMTP authentication (required).
- `EMAIL_PASSWORD` — Password or app-specific password for the email account (required).

Optional configuration and their defaults (the application uses sensible defaults when not provided):

- `OPENAI_MODEL_NAME` — Default: `gpt-4o`.
- `EMAIL_SMTP_PORT` — Default: `587`.
- `EMAIL_IMAP_PORT` — Default: `993`.
- `EMAIL_POLLING_INTERVAL` — Default: `5` (minutes). Interval in minutes between background email polling runs.
- `EMAIL_DOMAIN_BLACKLIST` — Default: empty (no blocked domains). Comma-separated list of sender domains to ignore, e.g. `spam.com,example.org`.

Example `.env` snippet:

```
OPENAI_API_KEY=sk-xxxx
OPENAI_MODEL_NAME=gpt-4o
EMAIL_IMAP_SERVER=imap.example.com
EMAIL_IMAP_PORT=993
EMAIL_SMTP_SERVER=smtp.example.com
EMAIL_SMTP_PORT=587
EMAIL_ACCOUNT=service@example.com
EMAIL_PASSWORD=app-password
# Optional polling settings
EMAIL_POLLING_INTERVAL=5
EMAIL_DOMAIN_BLACKLIST=spam.com,example.org
```

Note: Treat credentials (OPENAI_API_KEY, EMAIL_PASSWORD) as sensitive secrets and do not commit them to source control.

## Background Email Polling

The service includes a background email polling job that periodically fetches unread emails from the configured IMAP account and converts them into inquiries in the system.

Key points:

- The polling job starts automatically when the FastAPI application starts. It is registered during the application's lifespan (APScheduler integration) and requires no manual scheduling.
- The polling interval is configured by `EMAIL_POLLING_INTERVAL` and is expressed in minutes. Default is 5 minutes.
- Senders with domains listed in `EMAIL_DOMAIN_BLACKLIST` are skipped. The blacklist is a comma-separated list of domains (no spaces required). Matching is performed against the sender's domain; blacklisted domains are ignored during ingestion.
- The job is idempotent in registration (the scheduler registers the job with replace_existing enabled) so repeated startups do not create duplicate jobs.
- The polling logic performs high-level filtering and inquiry creation; internal implementation details (IMAP fetch, parsing, classification, and persistence) are handled within service modules and are not required to be configured here.

## Project structure and utilities

Utility helpers are available under `src/inq_service_svc/utils/` to centralize integration logic:

- `openai_client.py` — OpenAI client helpers and model name configuration.
- `email_client.py` — IMAP fetch and SMTP send helpers for email ingestion and replies.
- `scheduler.py` — APScheduler lifecycle helpers for background polling jobs.
- `websocket_manager.py` — WebSocket connection manager for real-time board updates.

These modules are exposed via `src/inq_service_svc/utils/__init__.py` for easy import and testing.

## Running and testing

- See `Makefile` and `pyproject.toml` for available commands and dependencies.
- Use the provided `.env` for local development, and provide real secrets via environment variables in production.

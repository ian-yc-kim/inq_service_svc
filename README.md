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
```

Note: Treat credentials (OPENAI_API_KEY, EMAIL_PASSWORD) as sensitive secrets and do not commit them to source control.

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

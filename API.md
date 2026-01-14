# inq_service_svc API Documentation

## Overview

Service: inq_service_svc

Base URL (local): http://localhost:8000
Base URL (deployed): https://api.thesenai.com/inq_service_svc

This document describes the Authentication API and how to use access tokens for protected endpoints.


## Authentication API

### POST /api/auth/login

Description
- Validate user credentials and return a JWT access token used for authenticating protected endpoints.

Request
- URL: POST /api/auth/login
- Content-Type: application/json

Request body schema (JSON):
- email: string (email)
- password: string

Example request body:

```json
{
  "email": "user@example.com",
  "password": "secret-password"
}
```

Responses

200 OK
- Description: Credentials valid. Returns access token and token type.
- Response body schema (JSON):
  - access_token: string (JWT)
  - token_type: string (always "bearer")

Example success response:

```json
{
  "access_token": "eyJhbGciOiJI...",
  "token_type": "bearer"
}
```

401 Unauthorized
- Description: Invalid credentials or token validation failure.
- Response body (example produced by FastAPI):

```json
{
  "detail": "Could not validate credentials"
}
```

Notes
- The login endpoint returns token_type set to "bearer" (lowercase).
- On internal failures (database or token creation), the service may return 500 Internal Server Error.


## Authentication for Protected Routes

Protected endpoints require an Authorization header with a bearer access token obtained from POST /api/auth/login.

Header format:

```
Authorization: Bearer <access_token>
```

Example curl usage for a protected endpoint:

```bash
curl -X GET "http://localhost:8000/api/inquiries" \
  -H "Authorization: Bearer eyJhbGciOiJI..." \
  -H "Accept: application/json"
```

Notes
- Replace the example token with the actual access_token returned by /api/auth/login.
- Ensure the Authorization header uses the exact format: Bearer followed by a space and the token.


## Cross-checks
- Endpoint path documented as /api/auth/login to match implementation.
- Request/response schemas align with LoginRequest and Token Pydantic models.
- token_type documented as "bearer" consistent with router implementation.


## Change log
- 2025-01-14: Created Authentication documentation and token usage examples.

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


## User Management API

This section documents the User Management endpoints for creating, listing, updating, and deleting users.

Permissions
- All /api/users endpoints require an Authorization header with a valid access token obtained from /api/auth/login.
- Only users with role Admin are permitted to call these endpoints. Requests by non-Admin users return 403 Forbidden.
- If the token is missing or invalid, endpoints return 401 Unauthorized with {
  "detail": "Could not validate credentials"
}.

Common models
- UserResponse (response model):

```json
{
  "id": 1,
  "email": "user@example.com",
  "name": "Alice Example",
  "role": "Admin"
}
```

- UserCreate (request for creating a user):

```json
{
  "email": "newuser@example.com",
  "password": "strongpassword",
  "name": "New User",
  "role": "Staff"
}
```
Notes: password minimum length 8. Role must be one of "Admin" or "Staff".

- UserUpdate (request for updating a user):

```json
{
  "email": "optional@example.com",
  "password": "newpassword",
  "name": "Optional Name",
  "role": "Admin"
}
```
All fields are optional for updates. Password, if present, must be at least 8 characters.

Implementation notes
- Responses never include hashed_password. Pydantic schema UserResponse exposes id, email, name, role.
- The router enforces Admin-only access via a helper that raises 403 when current_user.role != Admin.


### POST /api/users
- Purpose: Create a new user (Admin only).
- URL: POST /api/users
- Content-Type: application/json
- Request body: UserCreate

Success responses
- 201 Created
  - Response body: UserResponse (created user)

Errors
- 400 Bad Request: { "detail": "Email already exists" } when email duplicates an existing user.
- 401 Unauthorized: token missing or invalid. { "detail": "Could not validate credentials" }
- 403 Forbidden: caller is not Admin. { "detail": "Forbidden" }
- 500 Internal Server Error: { "detail": "Internal server error" }

Example request
```json
{
  "email": "newuser@example.com",
  "password": "strongpassword",
  "name": "New User",
  "role": "Staff"
}
```

Example success response (201):
```json
{
  "id": 5,
  "email": "newuser@example.com",
  "name": "New User",
  "role": "Staff"
}
```


### GET /api/users
- Purpose: List all users (Admin only).
- URL: GET /api/users
- Response: 200 OK with an array of UserResponse

Success responses
- 200 OK: [ UserResponse, ... ]

Errors
- 401 Unauthorized, 403 Forbidden, 500 Internal Server Error as above.

Example success response (200):
```json
[
  {
    "id": 1,
    "email": "admin@example.com",
    "name": "Admin User",
    "role": "Admin"
  },
  {
    "id": 2,
    "email": "staff@example.com",
    "name": "Staff User",
    "role": "Staff"
  }
]
```


### PATCH /api/users/{id}
- Purpose: Update an existing user (Admin only).
- URL: PATCH /api/users/{user_id}
- Path parameter: user_id (integer)
- Request body: UserUpdate (all fields optional)

Success responses
- 200 OK: UserResponse (updated user)

Errors
- 400 Bad Request: { "detail": "Email already exists" } when attempting to change to an email already used by another user.
- 404 Not Found: { "detail": "User not found" } when the provided user_id does not exist.
- 401 Unauthorized, 403 Forbidden, 500 Internal Server Error as above.

Example request
```json
{
  "name": "Updated Name",
  "role": "Admin"
}
```

Example success response (200):
```json
{
  "id": 2,
  "email": "staff@example.com",
  "name": "Updated Name",
  "role": "Admin"
}
```


### DELETE /api/users/{id}
- Purpose: Delete a user (Admin only).
- URL: DELETE /api/users/{user_id}
- Path parameter: user_id (integer)

Success responses
- 200 OK: { "detail": "User deleted" }

Errors
- 404 Not Found: { "detail": "User not found" }
- 401 Unauthorized, 403 Forbidden, 500 Internal Server Error as above.

Example success response (200):
```json
{
  "detail": "User deleted"
}
```


Routing note
- The implementation mounts the users router under the application prefix /api/users. The router uses @users_router.post("/"), @users_router.get("/"), etc., so the canonical endpoints are /api/users/ and /api/users/{id}. FastAPI will typically redirect /api/users to /api/users/.


Cross-checks
- Endpoint paths documented match router prefix /api/users and route definitions in src/inq_service_svc/routers/users.py.
- Admin-only enforcement is implemented via a helper that raises HTTP 403 Forbidden when current_user.role != Admin.
- Request/response schemas align with Pydantic models in src/inq_service_svc/schemas/user.py: UserCreate, UserUpdate, UserResponse.
- Status codes and error responses documented reflect the HTTPException usage in the router implementation.


## Cross-checks (global)
- Endpoint path documented as /api/auth/login and /api/users/* to match implementation.
- Request/response schemas align with Pydantic models found in src/inq_service_svc/schemas.


## Change log
- 2025-01-14: Added User Management API documentation covering POST, GET, PATCH, DELETE endpoints and permission details.

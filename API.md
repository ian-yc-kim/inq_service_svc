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


## Inquiries API

This section documents endpoints related to customer inquiries.

### POST /api/inquiries

Description
- Create a new customer inquiry. The endpoint validates input, runs an automatic classification, optionally assigns staff, persists the inquiry, and schedules a WebSocket broadcast event announcing the new inquiry.

Notes on path
- Router is mounted under the application prefix /api/inquiries with @inquiries_router.post("/"). Canonical path is /api/inquiries/; FastAPI will accept and may redirect /api/inquiries to /api/inquiries/.

Authentication
- The current implementation of the inquiries create endpoint does not require a JWT access token. Documented as no authentication required.

Request
- URL: POST /api/inquiries
- Content-Type: application/json

Request body schema (InquiryCreate):
- title: string
- content: string
- customer_email: string (email)
- customer_name: string

Example request body:

```json
{
  "title": "Unable to access account",
  "content": "I tried to log in but I get an unexpected error code 500.",
  "customer_email": "customer@example.com",
  "customer_name": "Jane Customer"
}
```

Responses

201 Created
- Description: Inquiry created and persisted.
- Response model: InquiryResponse
- Response schema fields:
  - id: integer
  - title: string
  - content: string
  - customer_email: string (email)
  - customer_name: string | null
  - status: enum (InquiryStatus, e.g., New)
  - category: string | null (AI-generated classification, e.g., "Account Issues")
  - urgency: string | null (AI-assigned urgency, e.g., "High")
  - assigned_user_id: integer | null (id of assigned staff)
  - created_at: ISO-8601 datetime string

Example success response (201):

```json
{
  "id": 123,
  "title": "Unable to access account",
  "content": "I tried to log in but I get an unexpected error code 500.",
  "customer_email": "customer@example.com",
  "customer_name": "Jane Customer",
  "status": "New",
  "category": "Account Issues",
  "urgency": "High",
  "assigned_user_id": null,
  "created_at": "2025-01-15T12:34:56.789012"
}
```

Errors
- 422 Unprocessable Entity: Request validation failed (e.g., invalid email format for customer_email). FastAPI/Pydantic returns details about the invalid field.
- 500 Internal Server Error: Persistence or unexpected failure while handling the request. The endpoint translates internal failures to HTTP 500.

Events
- On successful creation, the service schedules a broadcast over the WebSocket manager. The event is a JSON-encoded string with shape:
  - {"event": "new_inquiry", "inquiry_id": <id>}

Cross-checks
- Implementation: src/inq_service_svc/routers/inquiries.py#create_inquiry uses InquiryCreate request model and InquiryResponse response model (src/inq_service_svc/schemas/inquiry.py).
- Broadcast call: background task adds manager.broadcast(json.dumps({"event":"new_inquiry","inquiry_id": inquiry.id})).


## WebSocket API

Realtime updates are delivered via WebSocket connections.

Endpoint
- Path: /api/ws
- Router: websocket router is mounted under the application prefix /api so endpoint becomes /api/ws

Example connection URLs
- Local (development): ws://localhost:8000/api/ws
- Deployed (example): wss://api.thesenai.com/inq_service_svc/api/ws

Transport details
- Text frames are used for all messages.
- The server accepts connections and tracks active connections in an in-memory ConnectionManager (src/inq_service_svc/utils/websocket_manager.py).

Client → Server behavior
- Send the literal text "ping" to receive the literal text "pong" from the server (keep-alive / ping/pong semantics).
- Sending any other text message will result in the server echoing the same text back to the sender.

Server → Client behavior
- Broadcasts are JSON-encoded text messages. Current broadcasted event example when a new inquiry is created:
  - {"event": "new_inquiry", "inquiry_id": 123}
- Clients should attempt to parse incoming text as JSON; non-JSON payloads (e.g., echo responses or "pong") should be handled gracefully.

Example JavaScript client usage

```javascript
const ws = new WebSocket('ws://localhost:8000/api/ws');

ws.addEventListener('open', () => {
  // Send a ping to test connection
  ws.send('ping');
});

ws.addEventListener('message', (event) => {
  const text = event.data;
  try {
    const obj = JSON.parse(text);
    if (obj.event === 'new_inquiry') {
      console.log('New inquiry id:', obj.inquiry_id);
    } else {
      console.log('Received event:', obj);
    }
  } catch (err) {
    // Not JSON: could be pong or echo
    if (text === 'pong') {
      console.log('Received pong');
    } else {
      console.log('Echo or text message:', text);
    }
  }
});

ws.addEventListener('close', () => console.log('WebSocket closed'));
ws.addEventListener('error', (e) => console.error('WebSocket error', e));
```

Cross-checks
- WebSocket router implementation: src/inq_service_svc/routers/websocket.py (websocket endpoint accepts connections, handles ping/pong, and echoes other messages).
- Connection manager: src/inq_service_svc/utils/websocket_manager.py manages active connections and broadcast(message) to all connections.


## Cross-checks (global)
- Endpoint paths documented match router prefixes and definitions in src/inq_service_svc/routers.
- POST /api/inquiries matches src/inq_service_svc/routers/inquiries.py and uses InquiryCreate/InquiryResponse from src/inq_service_svc/schemas/inquiry.py.
- WebSocket /api/ws matches src/inq_service_svc/routers/websocket.py and uses the ConnectionManager broadcast in src/inq_service_svc/utils/websocket_manager.py.
- Request/response schemas align with Pydantic models found in src/inq_service_svc/schemas.


## Change log
- 2025-01-14: Added User Management API documentation covering POST, GET, PATCH, DELETE endpoints and permission details.
- 2025-01-15: Added Inquiries API documentation for POST /api/inquiries: request/response schemas, examples, errors, and event notes.
- 2025-01-15: Added WebSocket API documentation for /api/ws: connection details, message formats, and a JavaScript client example.

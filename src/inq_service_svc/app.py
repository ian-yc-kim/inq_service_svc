from fastapi import FastAPI
import logging

# Create FastAPI app instance for the service
app = FastAPI(debug=True, title="inq_service_svc")

# Import and register routers directly. Keep app file minimal.
from inq_service_svc.routers import auth_router, users_router, inquiries_router, websocket_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
# users_router is expected to be present; include it directly.
if users_router is not None:
    app.include_router(users_router, prefix="/api/users", tags=["users"])

# inquiries router
if inquiries_router is not None:
    app.include_router(inquiries_router, prefix="/api/inquiries", tags=["inquiries"])

# websocket router mounted under /api so WS endpoint becomes /api/ws
if websocket_router is not None:
    app.include_router(websocket_router, prefix="/api", tags=["websocket"])

logger = logging.getLogger(__name__)

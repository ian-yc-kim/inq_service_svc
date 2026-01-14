from fastapi import FastAPI

# Create FastAPI app instance for the service
# Keep this file minimal to avoid import-time side effects
app = FastAPI(debug=True, title="inq_service_svc")

# Register routers
from inq_service_svc.routers import auth_router

app.include_router(auth_router, prefix="/api/auth", tags=["auth"])

from fastapi import FastAPI

# Create FastAPI app instance for the service
# Keep this file minimal to avoid import-time side effects
app = FastAPI(debug=True, title="inq_service_svc")

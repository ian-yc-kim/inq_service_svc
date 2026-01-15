from fastapi import FastAPI
import logging
from contextlib import asynccontextmanager

# scheduler and job imports
from inq_service_svc.config import EMAIL_POLLING_INTERVAL
from inq_service_svc.utils.scheduler import init_scheduler, shutdown_scheduler
from inq_service_svc.services.email_processor import process_incoming_emails

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan: start scheduler and register recurring email polling job."""
    try:
        try:
            scheduler = init_scheduler()
            # register job idempotently
            scheduler.add_job(
                process_incoming_emails,
                "interval",
                minutes=EMAIL_POLLING_INTERVAL,
                id="email_polling",
                replace_existing=True,
            )
            logger.info("Scheduler initialized and email polling job registered with interval %s minutes", EMAIL_POLLING_INTERVAL)
        except Exception as e:
            logger.error(e, exc_info=True)
            # re-raise so startup fails visibly
            raise
        yield
    finally:
        try:
            await shutdown_scheduler()
            logger.info("Scheduler shutdown complete")
        except Exception as e:
            logger.error(e, exc_info=True)


# Create FastAPI app instance for the service with lifespan handling
app = FastAPI(debug=True, title="inq_service_svc", lifespan=lifespan)

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

import pytest
from apscheduler.schedulers.base import STATE_RUNNING

from inq_service_svc.config import EMAIL_POLLING_INTERVAL
from inq_service_svc.utils.scheduler import init_scheduler
from inq_service_svc.services.email_processor import process_incoming_emails


def test_app_startup_registers_email_polling_job(client):
    """Ensure app startup initializes scheduler and registers the email polling job."""
    # The client fixture starts the app and triggers the lifespan startup
    s = init_scheduler()
    # assert scheduler is running (support different APScheduler versions)
    assert getattr(s, "running", None) == True or getattr(s, "state", None) == STATE_RUNNING

    jobs = s.get_jobs()
    job = next((j for j in jobs if getattr(j, "id", None) == "email_polling"), None)
    assert job is not None, "email_polling job was not registered"

    # function comparison: compare by name to avoid wrapper differences
    job_func_name = getattr(getattr(job, "func", None), "__name__", None)
    assert job_func_name == process_incoming_emails.__name__

    # verify trigger interval matches configured polling interval
    trigger_interval = getattr(job.trigger, "interval", None)
    assert trigger_interval is not None, "job trigger has no interval"
    assert int(trigger_interval.total_seconds()) == int(EMAIL_POLLING_INTERVAL) * 60

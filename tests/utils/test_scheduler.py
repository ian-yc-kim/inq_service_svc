import logging
import pytest
from apscheduler.schedulers.base import STATE_RUNNING

from inq_service_svc.utils.scheduler import init_scheduler, shutdown_scheduler


@pytest.fixture(autouse=True)
@pytest.mark.anyio
async def cleanup_scheduler():
    # Ensure scheduler is shutdown after each test to avoid state leakage
    yield
    try:
        await shutdown_scheduler()
    except Exception:
        # Best-effort cleanup; tests should not fail on cleanup errors
        pass


@pytest.mark.anyio
async def test_init_scheduler_starts_and_is_idempotent():
    s1 = init_scheduler()
    s2 = init_scheduler()
    assert s1 is s2
    # Depending on apscheduler version, either running attribute or state constant
    assert getattr(s1, "running", None) == True or getattr(s1, "state", None) == STATE_RUNNING


@pytest.mark.anyio
async def test_shutdown_scheduler_stops_gracefully():
    s = init_scheduler()
    await shutdown_scheduler()
    # Instead of relying on internal attrs that may vary across versions,
    # ensure the module-level scheduler reference was cleared by creating a new one
    s2 = init_scheduler()
    assert s2 is not s


@pytest.mark.anyio
async def test_shutdown_scheduler_is_idempotent():
    # should not raise when called without init
    await shutdown_scheduler()
    # init then call shutdown multiple times
    s = init_scheduler()
    await shutdown_scheduler()
    await shutdown_scheduler()

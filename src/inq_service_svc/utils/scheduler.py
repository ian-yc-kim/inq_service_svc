import asyncio
import logging
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler

_logger = logging.getLogger(__name__)

_scheduler: Optional[AsyncIOScheduler] = None


def init_scheduler() -> AsyncIOScheduler:
    """Initialize and start a module-level AsyncIOScheduler singleton.

    Idempotent: repeated calls return the same started scheduler.
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    try:
        _scheduler = AsyncIOScheduler()
        _scheduler.start()
        return _scheduler
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise


async def shutdown_scheduler(wait: bool = True) -> None:
    """Shutdown the scheduler if it exists. Idempotent.

    Runs the (synchronous) scheduler.shutdown in a thread so this
    coroutine can be awaited safely from an event loop.
    """
    global _scheduler
    if _scheduler is None:
        return

    s = _scheduler
    try:
        # scheduler.shutdown is blocking/synchronous; run it in a thread
        await asyncio.to_thread(s.shutdown, wait)
    except Exception as e:
        _logger.error(e, exc_info=True)
        raise
    finally:
        # Clear module reference so a subsequent init creates a fresh scheduler
        _scheduler = None

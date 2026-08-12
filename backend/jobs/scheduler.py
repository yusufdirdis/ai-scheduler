import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from jobs.tasks import run_scheduled_tick

logger = logging.getLogger(__name__)

_scheduler: BackgroundScheduler | None = None


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    _scheduler = BackgroundScheduler(timezone="UTC")
    # Fires on the hour — is_request_due() matches at hour granularity, so this is
    # the coarsest interval that still hits every business's configured window.
    _scheduler.add_job(run_scheduled_tick, CronTrigger(minute=0), id="availability_tick", replace_existing=True)
    _scheduler.start()
    logger.info("APScheduler started: hourly availability-request tick")
    return _scheduler


def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None

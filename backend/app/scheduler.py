from __future__ import annotations

import structlog
from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.config import settings

logger = structlog.get_logger(__name__)

scheduler = AsyncIOScheduler(timezone="Asia/Seoul")


def _parse_cron(cron_str: str) -> dict:
    """"0 2 * * *" → {"minute": "0", "hour": "2", ...}"""
    parts = cron_str.strip().split()
    if len(parts) != 5:
        raise ValueError(f"Invalid cron expression: {cron_str!r}")
    minute, hour, day, month, day_of_week = parts

    def _val(v: str) -> str | int:
        return int(v) if v.isdigit() else v

    return {
        "minute": _val(minute),
        "hour": _val(hour),
        "day": _val(day),
        "month": _val(month),
        "day_of_week": _val(day_of_week),
    }


def setup_scheduler(app) -> None:  # noqa: ANN001
    """FastAPI startup 이벤트에서 호출."""
    from app.db import AsyncSessionLocal
    from app.services import sync_service
    from app.services import notification_service
    from app.repositories import notification_repo

    cron_kwargs = _parse_cron(settings.sync_cron)

    @scheduler.scheduled_job("cron", **cron_kwargs)
    async def sync_job() -> None:
        logger.info("sync_job_started", trigger="scheduler")
        async with AsyncSessionLocal() as db:
            try:
                await sync_service.run(db, triggered_by="scheduler")
            except Exception:
                logger.error("sync_job_failed", exc_info=True)

    @scheduler.scheduled_job("interval", minutes=5)
    async def retry_notifications() -> None:
        """Retry FAILED or PENDING notifications (up to retry_count < 3)."""
        async with AsyncSessionLocal() as db:
            try:
                pending = await notification_repo.get_pending_logs(db)
                if pending:
                    logger.info("notification_retry_started", count=len(pending))
                for log in pending:
                    await notification_service._send_one(log.id, db)
            except Exception:
                logger.error("notification_retry_failed", exc_info=True)

    scheduler.start()
    logger.info("scheduler_started", cron=settings.sync_cron)


def shutdown_scheduler() -> None:
    """FastAPI shutdown 이벤트에서 호출."""
    if scheduler.running:
        scheduler.shutdown()
        logger.info("scheduler_stopped")

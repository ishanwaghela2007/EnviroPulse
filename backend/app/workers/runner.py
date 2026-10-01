"""Simple background scheduler (APScheduler). Jobs are modular functions, so they can later move to a
queue (Celery/RQ/Arq) without changing the API or the frontend.
  * external air ingestion       every INGEST_INTERVAL_SECONDS
  * pipeline (align/analytics/alerts/forecast) every PIPELINE_INTERVAL_SECONDS
  * demo stream tick             every DEMO_TICK_SECONDS when DEMO_STREAM_AUTO=true
Run standalone with:  python -m app.workers.runner"""
import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler

from app.core.config import get_settings
from app.core.database import session_scope
from app.core.logging import configure_logging, log
from app.services import demo_stream
from app.workers import analytics_worker, ingestion_worker

logger = logging.getLogger("enviropulse.worker")
_scheduler: BackgroundScheduler | None = None


def _safe(name, fn):
    def job():
        try:
            fn()
        except Exception as exc:  # a failing job must never kill the scheduler
            log(logger, logging.ERROR, "worker job failed", job=name, error=str(exc))
    return job


def _demo_tick():
    with session_scope() as db:
        try:
            demo_stream.tick(db)
        except demo_stream.DemoError as exc:
            log(logger, logging.INFO, "demo tick skipped", reason=str(exc))


def start() -> BackgroundScheduler:
    global _scheduler
    s = get_settings()
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone="UTC", job_defaults={"coalesce": True, "max_instances": 1})
        _scheduler.add_job(_safe("ingestion", ingestion_worker.run_external_air), "interval",
                           seconds=s.ingest_interval_seconds, id="ingestion")
        _scheduler.add_job(_safe("pipeline", analytics_worker.run_pending), "interval",
                           seconds=s.pipeline_interval_seconds, id="pipeline")
        if s.demo_stream_auto:
            _scheduler.add_job(_safe("demo_tick", _demo_tick), "interval", seconds=s.demo_tick_seconds, id="demo")
        _scheduler.start()
        log(logger, logging.INFO, "scheduler started", jobs=[j.id for j in _scheduler.get_jobs()])
    return _scheduler


def stop() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


def status() -> dict:
    if _scheduler is None:
        return {"status": "disabled" if not get_settings().enable_scheduler else "stopped", "jobs": []}
    return {"status": "running", "jobs": [{"id": j.id, "next_run": j.next_run_time} for j in _scheduler.get_jobs()]}


if __name__ == "__main__":
    configure_logging(get_settings().log_level)
    start()
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        stop()

# =============================================================================
# smart_engine/scheduler.py
#
# MAIN ENTRYPOINT — run this as a standalone background process:
#
#     python scheduler.py
#
# Wires two independent APScheduler jobs:
#
#   Job 1 — Odometer Cron (hourly by default)
#       Checks every vehicle's odometer_km against MAINTENANCE_SCHEDULE.
#       Injects "due soon" or "overdue" tickets into `tickets`.
#
#   Job 2 — Telemetry Listener (every 30s by default)
#       Polls `telemetry_events` for unprocessed P1_WARNING rows.
#       Maps event_code → ticket template, injects ticket, marks event done.
#
# Both jobs are fully independent. If one crashes, the other keeps running.
# All config (cron times, intervals) lives in engine_config.py.
# =============================================================================

import logging
import signal
import sys
import time
from datetime import datetime

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron         import CronTrigger
from apscheduler.triggers.interval     import IntervalTrigger
from apscheduler.events                import EVENT_JOB_ERROR, EVENT_JOB_EXECUTED

from engine_config      import (
    ODOMETER_CHECK_CRON,
    TELEMETRY_POLL_SECONDS,
    WEEKLY_SNAPSHOT_CRON,
)
from odometer_checker   import run_odometer_check
from telemetry_listener import run_telemetry_check

# ── Logging setup ─────────────────────────────────────────────────────────────
logging.basicConfig(
    level  = logging.INFO,
    format = "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
    datefmt= "%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("smart_engine.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("smart_engine.scheduler")


# ── Job wrappers (catch all exceptions so scheduler keeps running) ────────────

def job_odometer_check():
    logger.info("━" * 60)
    logger.info("[Job:OdometerCheck] STARTING")
    try:
        summary = run_odometer_check()
        logger.info(
            f"[Job:OdometerCheck] DONE — "
            f"{summary['tickets_created']} ticket(s) created, "
            f"{summary['skipped_duplicate']} duplicate(s) skipped, "
            f"{summary['errors']} error(s), "
            f"took {summary['duration_seconds']}s"
        )
    except Exception as exc:
        logger.error(f"[Job:OdometerCheck] UNHANDLED ERROR: {exc}", exc_info=True)


def job_telemetry_check():
    try:
        summary = run_telemetry_check()
        if summary["events_found"] > 0:
            logger.info(
                f"[Job:TelemetryListener] {summary['events_found']} event(s) — "
                f"{summary['tickets_created']} ticket(s) injected, "
                f"{summary['skipped_dup']} dup(s) skipped"
            )
    except Exception as exc:
        logger.error(f"[Job:TelemetryListener] UNHANDLED ERROR: {exc}", exc_info=True)


# ── APScheduler event listener (logs missed/failed jobs) ─────────────────────

def on_job_event(event):
    if event.exception:
        logger.error(f"[Scheduler] Job '{event.job_id}' raised an exception: {event.exception}")
    else:
        logger.debug(f"[Scheduler] Job '{event.job_id}' executed successfully.")


# ── Graceful shutdown ─────────────────────────────────────────────────────────

_scheduler: BackgroundScheduler | None = None

def _shutdown(sig, frame):
    logger.info(f"[Scheduler] Signal {sig} received — shutting down gracefully…")
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("[Scheduler] Stopped.")
    sys.exit(0)


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    global _scheduler

    logger.info("=" * 60)
    logger.info("  VehicleGuard Smart Engine — Starting Up")
    logger.info(f"  {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    logger.info("=" * 60)

    _scheduler = BackgroundScheduler(timezone="UTC")
    _scheduler.add_listener(on_job_event, EVENT_JOB_ERROR | EVENT_JOB_EXECUTED)

    # ── Job 1: Odometer Check (cron) ─────────────────────────────────
    _scheduler.add_job(
        func     = job_odometer_check,
        trigger  = CronTrigger(
            hour   = ODOMETER_CHECK_CRON["hour"],
            minute = ODOMETER_CHECK_CRON["minute"],
            timezone="UTC",
        ),
        id              = "odometer_check",
        name            = "Odometer vs Maintenance Schedule",
        replace_existing= True,
        max_instances   = 1,        # never run two at once
        coalesce        = True,     # if missed, run once not multiple times
    )
    logger.info(
        f"[Scheduler] Job registered: odometer_check "
        f"(cron hour={ODOMETER_CHECK_CRON['hour']} minute={ODOMETER_CHECK_CRON['minute']})"
    )

    # ── Job 2: Telemetry P1 Listener (interval) ───────────────────────
    _scheduler.add_job(
        func     = job_telemetry_check,
        trigger  = IntervalTrigger(seconds=TELEMETRY_POLL_SECONDS, timezone="UTC"),
        id              = "telemetry_listener",
        name            = "Telemetry P1_WARNING Listener",
        replace_existing= True,
        max_instances   = 1,
        coalesce        = True,
    )
    logger.info(
        f"[Scheduler] Job registered: telemetry_listener "
        f"(interval={TELEMETRY_POLL_SECONDS}s)"
    )

    # ── Start ──────────────────────────────────────────────────────────
    _scheduler.start()
    logger.info("[Scheduler] Both jobs started. Running… (Ctrl+C to stop)")

    # Run odometer check immediately on startup so we don't wait for first cron tick
    logger.info("[Scheduler] Running initial odometer check on startup…")
    job_odometer_check()

    # Register signal handlers for clean shutdown
    signal.signal(signal.SIGINT,  _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Keep main thread alive
    while True:
        time.sleep(5)


if __name__ == "__main__":
    main()

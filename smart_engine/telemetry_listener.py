# =============================================================================
# smart_engine/telemetry_listener.py
#
# P1_WARNING Telemetry Stream → Ticket Injector
#
# This module polls the `telemetry_events` collection for unprocessed
# P1_WARNING events (written by Round 2 / IoT gateway / OBD adapter).
#
# For each unprocessed event it:
#   1. Looks up the vehicle from the event's vehicle_id
#   2. Maps the event_code → ticket template via P1_WARNING_MAP
#   3. Applies a duplicate guard (one open ticket per vehicle+task)
#   4. Builds a fully-formatted ticket via ticket_factory
#   5. Injects the ticket into `tickets`
#   6. Marks the event as processed (with ticket_id back-reference)
#
# This runs on its own APScheduler interval (TELEMETRY_POLL_SECONDS),
# completely independently of the odometer cron job.
# =============================================================================

import logging
from datetime import datetime

from engine_config import P1_WARNING_MAP
from engine_db     import (
    get_unprocessed_p1_events, get_vehicle,
    ticket_exists_open, inject_ticket,
    mark_event_processed, log_engine_run,
)
from ticket_factory import build_p1_ticket

logger = logging.getLogger("smart_engine.telemetry")


def run_telemetry_check() -> dict:
    """
    Poll for unprocessed P1_WARNING events and inject tickets.
    Called by the APScheduler interval job every TELEMETRY_POLL_SECONDS.
    Returns a summary dict.
    """
    started_at      = datetime.utcnow()
    events          = get_unprocessed_p1_events()
    processed_count = 0
    ticket_count    = 0
    skipped_dup     = 0
    skipped_no_veh  = 0
    errors          = 0
    ticket_log      = []

    if events:
        logger.info(f"[TelemetryListener] {len(events)} unprocessed P1 event(s) found.")
    else:
        logger.debug("[TelemetryListener] No new P1 events.")

    for event in events:
        event_id   = str(event["_id"])
        vehicle_id = event.get("vehicle_id")
        event_code = event.get("event_code", "GENERIC_P1")

        try:
            # ── 1. Resolve vehicle ────────────────────────────────────
            vehicle = get_vehicle(vehicle_id) if vehicle_id else None
            if not vehicle:
                logger.warning(
                    f"[TelemetryListener] Event {event_id} — vehicle '{vehicle_id}' not found. "
                    f"Marking processed with no ticket."
                )
                mark_event_processed(event_id, ticket_id=None)
                skipped_no_veh += 1
                processed_count += 1
                continue

            vid = str(vehicle["_id"])
            reg = vehicle.get("registration_number", vid)

            # ── 2. Resolve mapping ────────────────────────────────────
            mapping  = P1_WARNING_MAP.get(event_code, P1_WARNING_MAP["GENERIC_P1"])
            task_id  = mapping["task_id"]

            if event_code not in P1_WARNING_MAP:
                logger.warning(
                    f"[TelemetryListener] Unknown event_code '{event_code}' for {reg}. "
                    f"Falling back to GENERIC_P1 mapping."
                )

            # ── 3. Duplicate guard ────────────────────────────────────
            if ticket_exists_open(vid, task_id):
                logger.info(
                    f"[TelemetryListener] {reg} / {event_code} → task '{task_id}' "
                    f"already has an open ticket. Skipping ticket creation."
                )
                mark_event_processed(event_id, ticket_id="DUPLICATE_SKIPPED")
                skipped_dup += 1
                processed_count += 1
                continue

            # ── 4. Build ticket ───────────────────────────────────────
            ticket    = build_p1_ticket(vehicle=vehicle, event=event)

            # ── 5. Inject ticket ──────────────────────────────────────
            ticket_id = inject_ticket(ticket)
            ticket_count += 1

            logger.info(
                f"[TelemetryListener] TICKET INJECTED — {reg} | {event_code} → "
                f"task='{task_id}' | ticket={ticket_id} | "
                f"SLA={mapping['sla_hours']}h"
            )
            ticket_log.append({
                "registration": reg,
                "event_code":   event_code,
                "task_id":      task_id,
                "ticket_id":    ticket_id,
                "sla_hours":    mapping["sla_hours"],
            })

            # ── 6. Mark event processed ───────────────────────────────
            mark_event_processed(event_id, ticket_id=ticket_id)
            processed_count += 1

        except Exception as exc:
            errors += 1
            logger.error(
                f"[TelemetryListener] ERROR processing event {event_id}: {exc}",
                exc_info=True,
            )
            # Don't mark as processed — will retry on next poll cycle

    duration_s = (datetime.utcnow() - started_at).total_seconds()
    summary = {
        "events_found":    len(events),
        "processed":       processed_count,
        "tickets_created": ticket_count,
        "skipped_dup":     skipped_dup,
        "skipped_no_veh":  skipped_no_veh,
        "errors":          errors,
        "duration_seconds":round(duration_s, 3),
        "ticket_log":      ticket_log,
    }

    if events:
        log_engine_run("telemetry_check", summary)

    return summary

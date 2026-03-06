# =============================================================================
# smart_engine/odometer_checker.py
#
# Round 2 → Round 3 Bridge — Odometer vs Maintenance Schedule
#
# Called by the cron scheduler on every tick.
# Reads every vehicle's odometer_km, calculates its age, shrinks each
# rule's interval_km proportionally (older vehicle → shorter interval),
# then injects a ticket when a threshold is crossed.
#
# Core formula per vehicle per rule:
#   age_years          = (today − purchase_date).days / 365.25
#   multiplier         = AGE_INTERVAL_MULTIPLIERS lookup (e.g. 0.60 for a 7yr old car)
#   effective_interval = base_interval_km × multiplier
#   warning_km         = AGE_WARNING_KM lookup
#
#   km_since_last = current_km − last_done_km
#   if km_since_last >= effective_interval              → OVERDUE
#   if km_since_last >= effective_interval − warning_km → DUE SOON
#
# Example — OIL_CHANGE base interval = 5,000 km:
#   Vehicle age 1 yr  → effective = 5,000 km  (multiplier 1.00)
#   Vehicle age 5 yrs → effective = 4,000 km  (multiplier 0.80)
#   Vehicle age 8 yrs → effective = 3,000 km  (multiplier 0.60)
#   Vehicle age 12 yrs→ effective = 2,000 km  (multiplier 0.40)
# =============================================================================

import logging
from datetime import datetime

from engine_config import (
    MAINTENANCE_SCHEDULE,
    AGE_INTERVAL_MULTIPLIERS,
    AGE_WARNING_KM,
)
from engine_db import (
    get_all_vehicles, get_schedule_entry, upsert_schedule_entry,
    ticket_exists_open, inject_ticket, log_engine_run,
)
from ticket_factory import build_odometer_ticket

logger = logging.getLogger("smart_engine.odometer")


# ── Age helpers ───────────────────────────────────────────────────────────────

def _vehicle_age_years(vehicle: dict) -> float:
    """Return the vehicle's age in fractional years from its purchase_date."""
    purchase_date = vehicle.get("purchase_date")
    if not purchase_date:
        return 0.0
    if isinstance(purchase_date, str):
        purchase_date = datetime.strptime(purchase_date, "%Y-%m-%d")
    return (datetime.utcnow() - purchase_date).days / 365.25


def _get_age_multiplier(age_years: float) -> tuple[float, str]:
    """
    Return (multiplier, label) for a given vehicle age.
    The multiplier shrinks the base km interval — older car → smaller number
    → more frequent servicing.
    """
    for max_age, multiplier, label in AGE_INTERVAL_MULTIPLIERS:
        if age_years <= max_age:
            return multiplier, label
    return AGE_INTERVAL_MULTIPLIERS[-1][1], AGE_INTERVAL_MULTIPLIERS[-1][2]


def _get_warning_km(age_years: float) -> int:
    """
    Return the km-before-boundary at which a DUE SOON ticket fires.
    Older vehicles get an earlier warning because their parts degrade faster.
    """
    for max_age, warning_km, _ in AGE_WARNING_KM:
        if age_years <= max_age:
            return warning_km
    return AGE_WARNING_KM[-1][1]


def compute_effective_interval(base_interval_km: int, age_years: float) -> dict:
    """
    Public helper (also used by ticket_factory for context fields).
    Returns a dict with all computed age-adjusted values for a single rule.
    """
    multiplier, age_label = _get_age_multiplier(age_years)
    warning_km            = _get_warning_km(age_years)
    effective_km          = max(200, int(base_interval_km * multiplier))  # floor at 200 km
    return {
        "base_interval_km":      base_interval_km,
        "effective_interval_km": effective_km,
        "multiplier":            multiplier,
        "age_label":             age_label,
        "warning_km":            warning_km,
        "age_years":             round(age_years, 2),
    }


# ── Main job ──────────────────────────────────────────────────────────────────

def run_odometer_check() -> dict:
    """
    Main entry point called by the cron scheduler.
    Iterates all vehicles × all maintenance rules, applying age-based
    interval compression before comparing against the odometer.
    Returns a summary dict stored in engine_run_log.
    """
    started_at        = datetime.utcnow()
    vehicles          = get_all_vehicles()
    total_checked     = 0
    tickets_created   = 0
    skipped_duplicate = 0
    errors            = 0
    ticket_log        = []

    logger.info(f"[OdometerCheck] Starting — {len(vehicles)} vehicle(s) to check.")

    for vehicle in vehicles:
        vid        = str(vehicle["_id"])
        current_km = int(vehicle.get("odometer_km", 0))
        reg        = vehicle.get("registration_number", vid)
        age_years  = _vehicle_age_years(vehicle)

        for rule in MAINTENANCE_SCHEDULE:
            task_id      = rule["task_id"]
            total_checked += 1

            try:
                # ── Age-adjusted interval ─────────────────────────────
                age_ctx          = compute_effective_interval(rule["interval_km"], age_years)
                effective_km     = age_ctx["effective_interval_km"]
                warning_km       = age_ctx["warning_km"]

                # ── Last completed km for this task ───────────────────
                entry        = get_schedule_entry(vid, task_id)
                last_done_km = entry["last_done_km"] if entry else 0
                km_since_last = current_km - last_done_km

                # ── Classify against EFFECTIVE (age-adjusted) interval ─
                is_overdue  = km_since_last >= effective_km
                is_due_soon = (not is_overdue and
                               km_since_last >= (effective_km - warning_km))

                if not is_overdue and not is_due_soon:
                    continue

                # ── Duplicate guard ───────────────────────────────────
                if ticket_exists_open(vid, task_id):
                    logger.debug(
                        f"[OdometerCheck] {reg}/{task_id} — open ticket exists, skipping."
                    )
                    skipped_duplicate += 1
                    continue

                # ── Build & inject ticket ─────────────────────────────
                ticket    = build_odometer_ticket(
                    vehicle      = vehicle,
                    rule         = rule,
                    current_km   = current_km,
                    last_done_km = last_done_km,
                    overdue      = is_overdue,
                    age_ctx      = age_ctx,        # ← passes age data into the ticket
                )
                ticket_id = inject_ticket(ticket)
                tickets_created += 1

                label = "OVERDUE" if is_overdue else "DUE SOON"
                logger.info(
                    f"[OdometerCheck] {reg} — {task_id} [{label}] "
                    f"| age={age_years:.1f}yrs multiplier={age_ctx['multiplier']} "
                    f"| base={rule['interval_km']:,}km effective={effective_km:,}km "
                    f"| km_since_last={km_since_last:,} | ticket={ticket_id}"
                )
                ticket_log.append({
                    "registration":      reg,
                    "task_id":           task_id,
                    "status":            label,
                    "ticket_id":         ticket_id,
                    "age_years":         round(age_years, 1),
                    "multiplier":        age_ctx["multiplier"],
                    "base_interval_km":  rule["interval_km"],
                    "effective_interval_km": effective_km,
                    "km_since_last":     km_since_last,
                })

            except Exception as exc:
                errors += 1
                logger.error(
                    f"[OdometerCheck] ERROR {reg}/{task_id}: {exc}", exc_info=True
                )

    duration_s = (datetime.utcnow() - started_at).total_seconds()
    summary = {
        "vehicles_checked":      len(vehicles),
        "rules_evaluated":       total_checked,
        "tickets_created":       tickets_created,
        "skipped_duplicate":     skipped_duplicate,
        "errors":                errors,
        "duration_seconds":      round(duration_s, 2),
        "ticket_log":            ticket_log,
    }
    logger.info(
        f"[OdometerCheck] Done in {duration_s:.1f}s — "
        f"{tickets_created} ticket(s) created, "
        f"{skipped_duplicate} skipped, {errors} error(s)."
    )
    log_engine_run("odometer_check", summary)
    return summary


def mark_task_completed(vehicle_id: str, task_id: str, completed_at_km: int):
    """
    Called by Round 3 (mechanic closes a ticket) to record that a task
    was completed. Resets the km counter for that task on this vehicle.
    """
    upsert_schedule_entry(vehicle_id, task_id, completed_at_km)
    logger.info(
        f"[OdometerCheck] Task '{task_id}' marked complete for vehicle "
        f"{vehicle_id} at {completed_at_km:,} km."
    )

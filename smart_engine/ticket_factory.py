# =============================================================================
# smart_engine/ticket_factory.py
#
# Responsible for assembling fully-formatted ticket documents before
# they are injected into MongoDB.  Nothing touches the DB here —
# this module is pure data transformation so it is trivially testable.
# =============================================================================

from datetime import datetime, timedelta
from engine_config import TICKET_STATUSES, P1_WARNING_MAP, MAINTENANCE_SCHEDULE


# ── Helpers ───────────────────────────────────────────────────────────────────

def _find_schedule_rule(task_id: str) -> dict | None:
    for rule in MAINTENANCE_SCHEDULE:
        if rule["task_id"] == task_id:
            return rule
    return None

def _sla_deadline(sla_hours: int) -> datetime:
    return datetime.utcnow() + timedelta(hours=sla_hours)

def _ticket_number() -> str:
    """Human-readable ticket number: TKT-YYYYMMDD-HHMMSS"""
    return "TKT-" + datetime.utcnow().strftime("%Y%m%d-%H%M%S")


# ── Odometer-Triggered Ticket ─────────────────────────────────────────────────

def build_odometer_ticket(
    vehicle: dict,
    rule: dict,
    current_km: int,
    last_done_km: int,
    overdue: bool,
    age_ctx: dict = None,       # ← injected by odometer_checker
) -> dict:
    """
    Build a maintenance ticket triggered by an odometer threshold breach.

    age_ctx (from compute_effective_interval) carries:
        effective_interval_km – age-adjusted interval that was actually used
        base_interval_km      – original rule value before age compression
        multiplier            – e.g. 0.60 means 40% shorter than base
        age_label             – human-readable age bracket
        age_years             – exact vehicle age at check time
        warning_km            – early-warning distance used
    """
    age_ctx       = age_ctx or {}
    km_since_last = current_km - last_done_km

    # Use the effective (age-adjusted) interval in all calculations
    effective_km  = age_ctx.get("effective_interval_km", rule["interval_km"])
    base_km       = age_ctx.get("base_interval_km",      rule["interval_km"])
    multiplier    = age_ctx.get("multiplier",             1.0)
    age_label     = age_ctx.get("age_label",              "Unknown")
    age_years     = age_ctx.get("age_years",              0.0)

    km_overdue    = max(0, km_since_last - effective_km)
    priority      = "P1" if overdue and rule["priority"] == "P1" else rule["priority"]

    # ── Age note appended to every description ────────────────────────
    age_note = (
        f" Vehicle age: {age_years:.1f} yrs ({age_label.split('—')[0].strip()}). "
        f"Base interval {base_km:,} km compressed to {effective_km:,} km "
        f"({int((1 - multiplier) * 100)}% reduction for age)."
    )

    if overdue:
        title = f"[OVERDUE] {rule['description']}"
        description = (
            f"Vehicle {vehicle['registration_number']} ({vehicle['make']} {vehicle['model']}) "
            f"is {km_overdue:,} km overdue for '{rule['description']}'. "
            f"Last completed at {last_done_km:,} km. Current odometer: {current_km:,} km. "
            f"Effective service interval: every {effective_km:,} km."
            + age_note
        )
        sla_hours = 24 if priority == "P1" else 72
    else:
        km_remaining = effective_km - km_since_last
        title = f"[DUE SOON] {rule['description']}"
        description = (
            f"Vehicle {vehicle['registration_number']} ({vehicle['make']} {vehicle['model']}) "
            f"is due for '{rule['description']}' within {km_remaining:,} km. "
            f"Last completed at {last_done_km:,} km. Current odometer: {current_km:,} km. "
            f"Effective service interval: every {effective_km:,} km."
            + age_note
        )
        sla_hours = 72 if priority == "P1" else 168

    return {
        # ── Identity ────────────────────────────────────────────────
        "ticket_number":   _ticket_number(),
        "source":          "odometer_check",

        # ── Vehicle / task linkage ──────────────────────────────────
        "vehicle_id":      str(vehicle["_id"]),
        "owner_id":        vehicle["owner_id"],
        "registration":    vehicle["registration_number"],
        "make":            vehicle["make"],
        "model":           vehicle["model"],
        "task_id":         rule["task_id"],
        "category":        "maintenance",

        # ── Content ─────────────────────────────────────────────────
        "title":           title,
        "description":     description,
        "parts_required":  rule.get("parts", []),
        "estimated_hrs":   rule.get("estimated_hrs", 1.0),

        # ── Priority & SLA ──────────────────────────────────────────
        "priority":        priority,
        "overdue":         overdue,
        "sla_deadline":    _sla_deadline(sla_hours),

        # ── Odometer + age context (visible to Round 3 dashboard) ────
        "odometer_context": {
            "current_km":            current_km,
            "last_done_km":          last_done_km,
            "km_since_last":         km_since_last,
            "km_overdue":            km_overdue,
            "base_interval_km":      base_km,
            "effective_interval_km": effective_km,
            "interval_multiplier":   multiplier,
            "vehicle_age_years":     age_years,
            "age_bracket":           age_label,
        },

        # ── Workflow ─────────────────────────────────────────────────
        "status":          "open",
        "auto_assign":     "mechanic",
        "assigned_to":     None,
        "history": [{
            "status":    "open",
            "note":      (
                f"Auto-generated by odometer check engine. "
                f"{'OVERDUE' if overdue else 'DUE SOON'}. "
                f"Age bracket: {age_label.split('—')[0].strip()} "
                f"(multiplier {multiplier})."
            ),
            "timestamp": datetime.utcnow(),
        }],

        # ── Timestamps ───────────────────────────────────────────────
        "created_at":  datetime.utcnow(),
        "updated_at":  datetime.utcnow(),
    }


# ── P1 Telemetry-Triggered Ticket ────────────────────────────────────────────

def build_p1_ticket(
    vehicle: dict,
    event: dict,
) -> dict:
    """
    Build a ticket from a P1_WARNING telemetry event.

    The event document must contain:
        vehicle_id  – str
        event_code  – str matching a key in P1_WARNING_MAP (or "GENERIC_P1")
        severity    – "P1_WARNING"
        payload     – dict of raw sensor readings (stored verbatim)
        received_at – datetime
    """
    event_code = event.get("event_code", "GENERIC_P1")
    mapping    = P1_WARNING_MAP.get(event_code, P1_WARNING_MAP["GENERIC_P1"])

    # Enrich description with raw sensor payload if available
    payload_str = ""
    if event.get("payload"):
        payload_str = "\n\nRaw sensor data: " + ", ".join(
            f"{k}={v}" for k, v in event["payload"].items()
        )

    return {
        # ── Identity ────────────────────────────────────────────────
        "ticket_number":  _ticket_number(),
        "source":         "telemetry_p1",
        "source_event_id": str(event["_id"]),

        # ── Vehicle / task linkage ──────────────────────────────────
        "vehicle_id":     str(vehicle["_id"]),
        "owner_id":       vehicle["owner_id"],
        "registration":   vehicle["registration_number"],
        "make":           vehicle["make"],
        "model":          vehicle["model"],
        "task_id":        mapping["task_id"],
        "category":       mapping["category"],

        # ── Content ─────────────────────────────────────────────────
        "title":          f"[P1] {mapping['title']}",
        "description":    mapping["description"] + payload_str,
        "parts_required": _find_schedule_rule(mapping["task_id"]).get("parts", [])
                          if _find_schedule_rule(mapping["task_id"]) else [],
        "estimated_hrs":  _find_schedule_rule(mapping["task_id"]).get("estimated_hrs", 2.0)
                          if _find_schedule_rule(mapping["task_id"]) else 2.0,

        # ── Priority & SLA ──────────────────────────────────────────
        "priority":       "P1",
        "overdue":        True,   # P1 telemetry events are always treated as overdue
        "sla_deadline":   _sla_deadline(mapping["sla_hours"]),

        # ── Telemetry context ────────────────────────────────────────
        "telemetry_context": {
            "event_code":  event_code,
            "severity":    event.get("severity"),
            "received_at": event.get("received_at"),
            "payload":     event.get("payload", {}),
        },

        # ── Workflow ─────────────────────────────────────────────────
        "status":        "open",
        "auto_assign":   mapping["auto_assign"],
        "assigned_to":   None,
        "history": [{
            "status":    "open",
            "note":      f"Auto-generated from P1_WARNING telemetry event '{event_code}'. "
                         f"SLA: {mapping['sla_hours']}h.",
            "timestamp": datetime.utcnow(),
        }],

        # ── Timestamps ───────────────────────────────────────────────
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow(),
    }

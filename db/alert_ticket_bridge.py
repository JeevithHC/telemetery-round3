"""
alert_ticket_bridge.py — Maps Round 2 alert types to Round 3 maintenance tickets.

This is the core "hackathon winning" bridge. When the Round 2 alert engine
fires any of the alerts below, call `create_ticket_from_alert()` to
automatically generate a maintenance ticket with correct priority and due date.

Usage (inside your existing alert engine, after creating the alert):
    from db.alert_ticket_bridge import create_ticket_from_alert
    create_ticket_from_alert(alert_doc, current_telemetry)
"""

from datetime import datetime, timedelta
from typing import Optional
import uuid
from db.database import db, get_org_for_vehicle, ticket_exists_for_alert, get_open_ticket


# ─────────────────────────────────────────────
# MAPPING: Alert Type → Ticket Config
# ─────────────────────────────────────────────
# Each entry defines:
#   service_type  — what kind of maintenance is needed
#   priority      — P0 (24h), P1 (7 days), P2 (next routine)
#   due_hours     — how many hours until due_by deadline
#   reason_template — human-readable trigger description

ALERT_TO_TICKET_MAP = {

    # ── From your existing 9 alert types ──────────────────────────────

    "oil_pressure_low": {
        "service_type": "Oil Change",
        "priority": "P0",
        "due_hours": 24,
        "reason_template": "Oil pressure dropped to {value:.1f} PSI (critical threshold: 20 PSI)",
    },
    "engine_temp_high": {
        "service_type": "Cooling System Check",
        "priority": "P0",
        "due_hours": 24,
        "reason_template": "Engine temperature reached {value:.1f}°C (threshold exceeded)",
    },
    "health_score_low": {
        "service_type": "Full Inspection",
        "priority": "P0",
        "due_hours": 24,
        "reason_template": "Vehicle health score fell to {value:.1f}/100 (maintenance_required flag triggered)",
    },
    "tyre_pressure_low": {
        "service_type": "Tyre Service",
        "priority": "P1",
        "due_hours": 168,   # 7 days
        "reason_template": "Tyre pressure 20%+ below normal — slow leak detected",
    },
    "harsh_braking": {
        "service_type": "Brake Inspection",
        "priority": "P1",
        "due_hours": 168,
        "reason_template": "Repeated harsh braking events detected (brake pressure > 80%)",
    },
    "overspeed": {
        "service_type": "Full Inspection",
        "priority": "P2",
        "due_hours": None,   # P2 = fold into next routine
        "reason_template": "Overspeed alert — structural stress check recommended",
    },

    # ── Gemini-recommended predictive alerts ──────────────────────────

    "air_brake_pressure_low": {
        "service_type": "Air Brake Inspection",
        "priority": "P0",
        "due_hours": 24,
        "reason_template": "Air brake pressure {value:.1f} PSI — below 90 PSI minimum",
    },
    "dpf_backpressure_high": {
        "service_type": "DPF Clean & Forced Regen",
        "priority": "P1",
        "due_hours": 168,
        "reason_template": "DPF backpressure exceeded 10 kPa — regeneration required",
    },
    "battery_voltage_dropping": {
        "service_type": "Battery Check",
        "priority": "P1",
        "due_hours": 72,    # 3 days (as per Gemini spec)
        "reason_template": "Battery voltage slope negative — replacement may be needed",
    },
    "misfire_detected": {
        "service_type": "Spark Plug & Coil Inspection",
        "priority": "P1",
        "due_hours": 168,
        "reason_template": "Engine misfire detected — spark plugs or coil pack suspected",
    },
    "chain_slip_detected": {
        "service_type": "Drivetrain Tensioning",
        "priority": "P1",
        "due_hours": 168,
        "reason_template": "Belt/chain slip detected — drivetrain tensioning required",
    },
    "tip_over": {
        "service_type": "Structural & Fluid Leak Inspection",
        "priority": "P0",
        "due_hours": 24,
        "reason_template": "Tip-over event detected — immediate structural and fluid check required",
    },
    "engine_vibration_high": {
        "service_type": "Full Inspection",
        "priority": "P1",
        "due_hours": 168,
        "reason_template": "Engine vibration above threshold — mounting or imbalance issue suspected",
    },
}


# ─────────────────────────────────────────────
# PRIORITY → STATUS MAPPING
# ─────────────────────────────────────────────

PRIORITY_TO_STATUS = {
    "P0": "grounded",   # vehicle grounded until fixed
    "P1": "pending",
    "P2": "pending",
}


# ─────────────────────────────────────────────
# MAIN BRIDGE FUNCTION
# ─────────────────────────────────────────────

def create_ticket_from_alert(
    alert_doc: dict,
    telemetry: Optional[dict] = None
) -> Optional[dict]:
    """
    Call this after creating any Round 2 alert document.

    Args:
        alert_doc: The alert document just written to telemetry_alerts.
                   Must have: alert_type, vehicle_id, vehicle_type, _id
        telemetry: Current telemetry reading (used for richer reason text).

    Returns:
        The created ticket document, or None if skipped (duplicate / no mapping).
    """

    alert_type = alert_doc.get("alert_type", "")
    vehicle_id = alert_doc.get("vehicle_id", "")
    vehicle_type = alert_doc.get("vehicle_type", "")
    alert_id = str(alert_doc.get("_id", alert_doc.get("alert_id", "")))

    # 1. No mapping for this alert type → skip
    if alert_type not in ALERT_TO_TICKET_MAP:
        return None

    config = ALERT_TO_TICKET_MAP[alert_type]

    # 2. Ticket already exists for this alert → skip (deduplication)
    if ticket_exists_for_alert(alert_id):
        return None

    # 3. Open ticket of same service type already exists → skip
    existing = get_open_ticket(vehicle_id, config["service_type"])
    if existing:
        return None

    # 4. Build reason string with telemetry values if available
    value = 0
    if telemetry:
        field_hints = {
            "oil_pressure_low":       "oil_pressure",
            "engine_temp_high":       "engine_temp",
            "health_score_low":       "health_score",
            "air_brake_pressure_low": "air_brake_pressure",
        }
        field = field_hints.get(alert_type)
        if field and field in telemetry:
            value = telemetry[field]

    try:
        reason = config["reason_template"].format(value=value)
    except (KeyError, IndexError):
        reason = config["reason_template"]

    # 5. Calculate due_by
    due_by = None
    if config["due_hours"]:
        due_by = datetime.utcnow() + timedelta(hours=config["due_hours"])

    # 6. Get org
    org_id = get_org_for_vehicle(vehicle_id) or "UNASSIGNED"

    # 7. Build ticket document
    ticket_id = f"TKT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{vehicle_id}-{str(uuid.uuid4())[:4].upper()}"

    ticket = {
        "ticket_id": ticket_id,
        "vehicle_id": vehicle_id,
        "vehicle_type": vehicle_type,
        "org_id": org_id,
        "service_type": config["service_type"],
        "source": "predictive",
        "priority": config["priority"],
        "status": PRIORITY_TO_STATUS[config["priority"]],
        "trigger_reason": reason,
        "alert_id": alert_id,
        "created_at": datetime.utcnow(),
        "due_by": due_by,
        "approved_at": None,
        "approved_by": None,
        "assigned_mechanic_id": None,
        "odometer_at_creation": telemetry.get("odometer") if telemetry else None,
        "health_score_at_creation": telemetry.get("health_score") if telemetry else None,
        "completed_at": None,
        "service_event_id": None,
        "checklist": [],
        "owner_notes": "",
        "is_delayed": False,
        "delay_reason": None,
    }

    db.maintenance_tickets.insert_one(ticket)
    return ticket

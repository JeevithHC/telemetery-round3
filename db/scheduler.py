"""
scheduler.py — The "Upcoming/Overdue" Engine.

Run this as a cron job every hour:
    */60 * * * * python scheduler.py

What it does every run:
    1. Loads all active maintenance schedule rules
    2. For every vehicle in every org, fetches current odometer from telemetry
    3. Compares against last service record (km + date)
    4. If within warning window → creates UPCOMING ticket
    5. If past due → creates OVERDUE ticket / escalates existing one
    6. Marks P0 tickets as GROUNDED if vehicle is still running
    7. Prints a full run report
"""

import os
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from db.database import db, get_vehicle_category, get_last_service, get_open_ticket, get_org_for_vehicle

load_dotenv()


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_latest_odometer(vehicle_id: str) -> float | None:
    """Pull the latest odometer reading from your existing telemetry collection."""
    doc = db.telemetry.find_one(
        {"vehicle_id": vehicle_id, "data_type": "raw"},
        sort=[("timestamp", -1)],
        projection={"odometer": 1}
    )
    return doc["odometer"] if doc else None

def get_latest_telemetry(vehicle_id: str) -> dict | None:
    """Pull the full latest telemetry doc for a vehicle."""
    return db.telemetry.find_one(
        {"vehicle_id": vehicle_id, "data_type": "raw"},
        sort=[("timestamp", -1)]
    )

def make_ticket_id(vehicle_id: str) -> str:
    suffix = str(uuid.uuid4())[:4].upper()
    return f"TKT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{vehicle_id}-{suffix}"

def build_checklist(items: list) -> list:
    return [{"item": i, "completed": False, "notes": None} for i in items]


# ─────────────────────────────────────────────
# CORE EVALUATION FUNCTION
# ─────────────────────────────────────────────

def evaluate_vehicle_for_rule(vehicle_id: str, vehicle_type: str, org_id: str, rule: dict) -> dict:
    """
    Evaluates one vehicle against one maintenance rule.

    Returns a result dict:
        status  : "ok" | "upcoming" | "overdue" | "skipped"
        reason  : human-readable explanation
        ticket  : the created ticket doc (or None)
    """

    service_type = rule["service_type"]
    km_interval  = rule.get("km_interval")
    day_interval = rule.get("days_interval")
    warn_km      = rule.get("warning_km_before", 500)
    warn_days    = rule.get("warning_days_before", 7)
    checklist    = rule.get("checklist_items", [])

    # ── Get current odometer ──────────────────
    current_odometer = get_latest_odometer(vehicle_id)
    if current_odometer is None:
        return {"status": "skipped", "reason": "No telemetry found", "ticket": None}

    # ── Get last service record ───────────────
    last_svc = get_last_service(vehicle_id, service_type)

    last_service_km   = last_svc["odometer_at_service"] if last_svc else 0.0
    last_service_date = last_svc["service_date"] if last_svc else datetime(2000, 1, 1)

    # ── Calculate km and days since last service ──
    km_since    = current_odometer - last_service_km
    days_since  = (datetime.utcnow() - last_service_date).days

    # ── Check if open ticket already exists ──
    existing = get_open_ticket(vehicle_id, service_type)
    if existing:
        # If it's now overdue, escalate status
        if existing.get("due_by") and existing["due_by"] < datetime.utcnow():
            db.maintenance_tickets.update_one(
                {"ticket_id": existing["ticket_id"]},
                {"$set": {"status": "overdue"}}
            )
            return {
                "status": "escalated_to_overdue",
                "reason": f"Existing ticket {existing['ticket_id']} escalated to OVERDUE",
                "ticket": existing
            }
        return {"status": "skipped", "reason": f"Open ticket already exists: {existing['ticket_id']}", "ticket": None}

    # ── Determine if action needed ────────────
    is_overdue_km   = km_interval  and km_since  >= km_interval
    is_overdue_days = day_interval and days_since >= day_interval
    is_upcoming_km  = km_interval  and not is_overdue_km  and (km_interval  - km_since)  <= warn_km
    is_upcoming_days= day_interval and not is_overdue_days and (day_interval - days_since) <= warn_days

    if not any([is_overdue_km, is_overdue_days, is_upcoming_km, is_upcoming_days]):
        km_left   = (km_interval - km_since)   if km_interval  else "N/A"
        days_left = (day_interval - days_since) if day_interval else "N/A"
        return {
            "status": "ok",
            "reason": f"OK — {km_left} km or {days_left} days remaining",
            "ticket": None
        }

    # ── Determine priority and due_by ─────────
    if is_overdue_km or is_overdue_days:
        priority  = "P1"
        status    = "overdue"
        due_by    = datetime.utcnow() + timedelta(days=2)  # needs fixing ASAP

        if is_overdue_km:
            reason = (f"OVERDUE: {km_since:.0f} km since last {service_type} "
                      f"(interval: {km_interval} km, overdue by {km_since - km_interval:.0f} km)")
        else:
            reason = (f"OVERDUE: {days_since} days since last {service_type} "
                      f"(interval: {day_interval} days, overdue by {days_since - day_interval} days)")

    else:  # upcoming
        priority = "P2"
        status   = "pending"

        if is_upcoming_km and is_upcoming_days:
            km_left   = km_interval  - km_since
            days_left = day_interval - days_since
            due_by    = datetime.utcnow() + timedelta(days=min(days_left, 30))
            reason    = (f"Due soon: {km_left:.0f} km or {days_left} days until {service_type}")
        elif is_upcoming_km:
            km_left = km_interval - km_since
            due_by  = datetime.utcnow() + timedelta(days=14)
            reason  = f"Due soon: {km_left:.0f} km until {service_type}"
        else:
            days_left = day_interval - days_since
            due_by    = datetime.utcnow() + timedelta(days=days_left)
            reason    = f"Due soon: {days_left} days until {service_type}"

    # ── Build and insert ticket ───────────────
    ticket = {
        "ticket_id":               make_ticket_id(vehicle_id),
        "vehicle_id":              vehicle_id,
        "vehicle_type":            vehicle_type,
        "org_id":                  org_id,
        "service_type":            service_type,
        "source":                  "routine",
        "priority":                priority,
        "status":                  status,
        "trigger_reason":          reason,
        "alert_id":                None,
        "created_at":              datetime.utcnow(),
        "due_by":                  due_by,
        "approved_at":             None,
        "approved_by":             None,
        "assigned_mechanic_id":    None,
        "odometer_at_creation":    current_odometer,
        "health_score_at_creation": get_latest_telemetry(vehicle_id).get("health_score") if get_latest_telemetry(vehicle_id) else None,
        "completed_at":            None,
        "service_event_id":        None,
        "checklist":               build_checklist(checklist),
        "owner_notes":             "",
        "is_delayed":              False,
        "delay_reason":            None,
    }

    db.maintenance_tickets.insert_one(ticket)
    return {"status": status, "reason": reason, "ticket": ticket}


# ─────────────────────────────────────────────
# MAIN SCHEDULER RUN
# ─────────────────────────────────────────────

def run_scheduler():
    started_at = datetime.utcnow()
    print(f"\n{'='*60}")
    print(f"  🔄 MAINTENANCE SCHEDULER — {started_at.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    print(f"{'='*60}\n")

    # Load all active rules
    rules = list(db.maintenance_schedule.find({"is_active": True}))
    print(f"📋 Loaded {len(rules)} active maintenance rules\n")

    # Load all orgs and their vehicles
    orgs = list(db.organizations.find({"is_active": True}))

    stats = {
        "ok":                   0,
        "upcoming_created":     0,
        "overdue_created":      0,
        "escalated_to_overdue": 0,
        "skipped":              0,
        "total_vehicles":       0,
    }

    for org in orgs:
        org_id      = org["org_id"]
        org_name    = org["name"]
        vehicle_ids = org["vehicle_ids"]

        print(f"🏢 {org_name} ({org_id}) — {len(vehicle_ids)} vehicles")

        for vehicle_id in vehicle_ids:
            stats["total_vehicles"] += 1

            # Determine vehicle type from ID prefix (e.g. "TRUCK-001" → "TRUCK")
            vehicle_type = vehicle_id.split("-")[0]
            category     = get_vehicle_category(vehicle_type)

            if not category:
                print(f"    ⚠️  Unknown vehicle type: {vehicle_type}")
                stats["skipped"] += 1
                continue

            # Filter rules relevant to this vehicle type
            applicable_rules = [
                r for r in rules
                if vehicle_type in r.get("vehicle_types", [])
            ]

            for rule in applicable_rules:
                result = evaluate_vehicle_for_rule(vehicle_id, vehicle_type, org_id, rule)
                s = result["status"]

                if s == "ok":
                    stats["ok"] += 1
                elif s == "upcoming":
                    stats["upcoming_created"] += 1
                    print(f"    🟡 {vehicle_id} — UPCOMING: {result['reason']}")
                elif s == "overdue":
                    stats["overdue_created"] += 1
                    print(f"    🔴 {vehicle_id} — OVERDUE: {result['reason']}")
                elif s == "escalated_to_overdue":
                    stats["escalated_to_overdue"] += 1
                    print(f"    🔴 {vehicle_id} — ESCALATED TO OVERDUE: {result['reason']}")
                elif s == "skipped":
                    stats["skipped"] += 1

        print()

    # ── P0 Grounding Check ───────────────────────────────────────────
    # Any vehicle with a grounded ticket that is still sending telemetry
    # gets flagged in the console (in production: send SMS to owner)
    print("🚨 Checking for grounded vehicles still in operation...")
    grounded_tickets = list(db.maintenance_tickets.find({"status": "grounded"}))
    for ticket in grounded_tickets:
        latest = get_latest_telemetry(ticket["vehicle_id"])
        if latest and latest.get("speed", 0) > 0:
            print(f"    ⛔ ALERT: {ticket['vehicle_id']} is GROUNDED but currently moving at {latest['speed']:.1f} km/h!")
            # TODO: trigger SMS/email notification to owner here

    # ── Print Summary ────────────────────────────────────────────────
    elapsed = (datetime.utcnow() - started_at).total_seconds()
    print(f"\n{'='*60}")
    print(f"  ✅ SCHEDULER RUN COMPLETE — {elapsed:.2f}s")
    print(f"{'='*60}")
    print(f"  Vehicles evaluated  : {stats['total_vehicles']}")
    print(f"  All OK              : {stats['ok']}")
    print(f"  Upcoming tickets    : {stats['upcoming_created']}")
    print(f"  Overdue tickets     : {stats['overdue_created']}")
    print(f"  Escalated to overdue: {stats['escalated_to_overdue']}")
    print(f"  Skipped             : {stats['skipped']}")
    print(f"  Grounded vehicles   : {len(grounded_tickets)}")
    print(f"{'='*60}\n")

    return stats


# ─────────────────────────────────────────────
# OVERDUE ESCALATION (run independently if needed)
# ─────────────────────────────────────────────

def escalate_overdue_tickets():
    """
    Separate pass — scans all non-completed tickets whose due_by
    has passed and marks them OVERDUE. Run every 15 minutes.
    """
    now = datetime.utcnow()
    result = db.maintenance_tickets.update_many(
        {
            "due_by": {"$lt": now},
            "status": {"$in": ["pending", "approved"]}
        },
        {"$set": {"status": "overdue"}}
    )
    if result.modified_count:
        print(f"  ⏰ Escalated {result.modified_count} tickets to OVERDUE")
    return result.modified_count


if __name__ == "__main__":
    run_scheduler()
    escalate_overdue_tickets()
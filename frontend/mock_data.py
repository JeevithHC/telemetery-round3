"""
mock_data.py — Realistic fake data for demo purposes.
Used when the API is unavailable or for presentations.
"""

from datetime import datetime, timedelta
import random

NOW = datetime.now()

def t(days=0, hours=0):
    return (NOW + timedelta(days=days, hours=hours)).isoformat()

# ─────────────────────────────────────────────
# TICKETS
# ─────────────────────────────────────────────

TICKETS = [
    # P0 Grounded
    {"ticket_id": "TKT-001", "vehicle_id": "TRUCK-004", "vehicle_type": "TRUCK",
     "org_id": "ORG-001", "service_type": "Oil Change", "source": "predictive",
     "priority": "P0", "status": "grounded",
     "trigger_reason": "Oil pressure dropped to 14.2 PSI (critical threshold: 20 PSI)",
     "due_by": t(hours=20), "created_at": t(-1), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Top up engine oil immediately", "completed": False},
         {"item": "Inspect for oil leaks under vehicle", "completed": False},
         {"item": "Check oil pressure sensor", "completed": False},
         {"item": "Perform full oil change if contaminated", "completed": False},
     ]},
    {"ticket_id": "TKT-002", "vehicle_id": "BUS-007", "vehicle_type": "BUS",
     "org_id": "ORG-002", "service_type": "Brake Inspection", "source": "predictive",
     "priority": "P0", "status": "grounded",
     "trigger_reason": "Critical brake system fault — brake pressure sensor anomaly detected",
     "due_by": t(hours=8), "created_at": t(-2), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Check brake fluid level", "completed": False},
         {"item": "Inspect brake lines for leaks", "completed": False},
         {"item": "Measure brake pad thickness", "completed": False},
         {"item": "Test ABS sensor function", "completed": False},
     ]},

    # P1 Overdue
    {"ticket_id": "TKT-003", "vehicle_id": "TRUCK-011", "vehicle_type": "TRUCK",
     "org_id": "ORG-001", "service_type": "Air Brake Inspection", "source": "routine",
     "priority": "P1", "status": "overdue",
     "trigger_reason": "OVERDUE: 21,400 km since last Air Brake Inspection (interval: 20,000 km)",
     "due_by": t(-3), "created_at": t(-10), "approved_at": t(-9),
     "assigned_mechanic_id": "USR-101", "checklist": [
         {"item": "Test air brake line pressure (must be ≥ 90 PSI)", "completed": True},
         {"item": "Inspect air compressor output", "completed": False},
         {"item": "Check brake drums and shoes", "completed": False},
         {"item": "Verify air dryer operation", "completed": False},
     ]},
    {"ticket_id": "TKT-004", "vehicle_id": "VAN-003", "vehicle_type": "VAN",
     "org_id": "ORG-001", "service_type": "Oil Change", "source": "routine",
     "priority": "P1", "status": "overdue",
     "trigger_reason": "OVERDUE: 22,100 km since last Oil Change (interval: 20,000 km, overdue by 2,100 km)",
     "due_by": t(-5), "created_at": t(-12), "approved_at": t(-11),
     "assigned_mechanic_id": "USR-101", "checklist": [
         {"item": "Drain and replace engine oil", "completed": False},
         {"item": "Replace oil filter", "completed": False},
         {"item": "Check for leaks", "completed": False},
     ]},

    # P1 Pending
    {"ticket_id": "TKT-005", "vehicle_id": "CAR-008", "vehicle_type": "CAR",
     "org_id": "ORG-003", "service_type": "Battery Check", "source": "predictive",
     "priority": "P1", "status": "pending",
     "trigger_reason": "Battery voltage slope negative — replacement may be needed",
     "due_by": t(days=3), "created_at": t(-1), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Test battery voltage (healthy: 12.4–12.7V)", "completed": False},
         {"item": "Load test battery", "completed": False},
         {"item": "Check alternator charging output", "completed": False},
         {"item": "Replace battery if failed", "completed": False},
     ]},
    {"ticket_id": "TKT-006", "vehicle_id": "TRUCK-015", "vehicle_type": "TRUCK",
     "org_id": "ORG-001", "service_type": "DPF Clean & Forced Regen", "source": "predictive",
     "priority": "P1", "status": "pending",
     "trigger_reason": "DPF backpressure exceeded 10 kPa — regeneration required",
     "due_by": t(days=5), "created_at": t(-2), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Check DPF backpressure (threshold: 10 kPa)", "completed": False},
         {"item": "Perform forced regeneration cycle", "completed": False},
         {"item": "Inspect exhaust temperature sensors", "completed": False},
     ]},
    {"ticket_id": "TKT-007", "vehicle_id": "BUS-012", "vehicle_type": "BUS",
     "org_id": "ORG-002", "service_type": "Suspension Check", "source": "routine",
     "priority": "P1", "status": "pending",
     "trigger_reason": "Due soon: 800 km until Suspension Check (interval: 20,000 km)",
     "due_by": t(days=6), "created_at": t(-1), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Inspect leaf springs for cracks", "completed": False},
         {"item": "Check shock absorber condition", "completed": False},
         {"item": "Torque all suspension bolts", "completed": False},
     ]},

    # P2 Pending
    {"ticket_id": "TKT-008", "vehicle_id": "CAR-012", "vehicle_type": "CAR",
     "org_id": "ORG-003", "service_type": "Tyre Service", "source": "routine",
     "priority": "P2", "status": "pending",
     "trigger_reason": "Due soon: 400 km until Tyre Rotation (interval: 10,000 km)",
     "due_by": t(days=10), "created_at": t(-1), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Rotate FL→RR, FR→RL", "completed": False},
         {"item": "Check all tyre pressures", "completed": False},
         {"item": "Inspect tread depth", "completed": False},
     ]},
    {"ticket_id": "TKT-009", "vehicle_id": "BIKE-004", "vehicle_type": "BIKE",
     "org_id": "ORG-003", "service_type": "Chain Lubrication & Tensioning", "source": "routine",
     "priority": "P2", "status": "pending",
     "trigger_reason": "Due soon: 180 km until Chain Lubrication (interval: 3,000 km)",
     "due_by": t(days=7), "created_at": t(), "approved_at": None,
     "assigned_mechanic_id": None, "checklist": [
         {"item": "Clean chain with degreaser", "completed": False},
         {"item": "Lubricate chain thoroughly", "completed": False},
         {"item": "Check chain slack (ideal: 20–30mm)", "completed": False},
     ]},

    # In Progress
    {"ticket_id": "TKT-010", "vehicle_id": "TRUCK-008", "vehicle_type": "TRUCK",
     "org_id": "ORG-001", "service_type": "Cooling System Check", "source": "predictive",
     "priority": "P1", "status": "in_progress",
     "trigger_reason": "Engine temperature reached 108°C (threshold exceeded)",
     "due_by": t(hours=12), "created_at": t(-1), "approved_at": t(-1),
     "assigned_mechanic_id": "USR-101", "checklist": [
         {"item": "Check coolant level and condition", "completed": True},
         {"item": "Inspect radiator for blockage", "completed": True},
         {"item": "Test thermostat operation", "completed": False},
         {"item": "Pressure test cooling system", "completed": False},
     ]},
]

# ─────────────────────────────────────────────
# SERVICE HISTORY
# ─────────────────────────────────────────────

SERVICE_HISTORY = {
    "TRUCK-004": [
        {"event_id": "SVC-001", "vehicle_id": "TRUCK-004", "service_type": "Oil Change",
         "mechanic_name": "Rajesh Kumar", "odometer_at_service": 18200,
         "service_date": t(-45), "notes": "Oil was very dark, extended interval not recommended",
         "parts_replaced": ["Engine oil 5W-30 6L", "Oil filter"],
         "cost_estimate": 1200, "next_service_due_km": 38200},
        {"event_id": "SVC-002", "vehicle_id": "TRUCK-004", "service_type": "Air Brake Inspection",
         "mechanic_name": "Rajesh Kumar", "odometer_at_service": 15000,
         "service_date": t(-90), "notes": "All brake lines OK, pressure at 94 PSI",
         "parts_replaced": [], "cost_estimate": 800, "next_service_due_km": 35000},
        {"event_id": "SVC-003", "vehicle_id": "TRUCK-004", "service_type": "Full Inspection",
         "mechanic_name": "Arjun Selvam", "odometer_at_service": 10000,
         "service_date": t(-180), "notes": "100k service completed. All systems checked.",
         "parts_replaced": ["Oil", "Air filter", "Fuel filter", "Spark plugs"],
         "cost_estimate": 8500, "next_service_due_km": 110000},
    ],
    "BUS-007": [
        {"event_id": "SVC-004", "vehicle_id": "BUS-007", "service_type": "Brake Inspection",
         "mechanic_name": "Arjun Selvam", "odometer_at_service": 32000,
         "service_date": t(-30), "notes": "Rear pads replaced, fronts OK",
         "parts_replaced": ["Rear brake pads"], "cost_estimate": 3200,
         "next_service_due_km": 72000},
    ],
}

# ─────────────────────────────────────────────
# ALERTS (for insurance portal)
# ─────────────────────────────────────────────

ALERTS = {
    "TRUCK-004": [
        {"alert_type": "oil_pressure_low", "severity": "critical",
         "message": "Oil pressure dropped to 14.2 PSI", "timestamp": t(-1),
         "resolved": False},
        {"alert_type": "engine_temp_high", "severity": "warning",
         "message": "Engine temp reached 102°C", "timestamp": t(-3),
         "resolved": True},
        {"alert_type": "oil_pressure_low", "severity": "critical",
         "message": "Oil pressure at 17.1 PSI", "timestamp": t(-7),
         "resolved": True},
        {"alert_type": "harsh_braking", "severity": "warning",
         "message": "Harsh braking detected — brake pressure 87%", "timestamp": t(-10),
         "resolved": True},
    ],
    "BUS-007": [
        {"alert_type": "harsh_braking", "severity": "critical",
         "message": "Brake system fault — pressure anomaly", "timestamp": t(-2),
         "resolved": False},
        {"alert_type": "tyre_pressure_low", "severity": "warning",
         "message": "Front-left tyre at 18 PSI", "timestamp": t(-5),
         "resolved": True},
    ],
}

# ─────────────────────────────────────────────
# PRE-COMPUTED API RESPONSES
# ─────────────────────────────────────────────

def get_owner_stats():
    grounded   = [t for t in TICKETS if t["status"] == "grounded"]
    overdue    = [t for t in TICKETS if t["status"] == "overdue"]
    this_week  = [t for t in TICKETS if t["status"] == "pending"]
    in_progress= [t for t in TICKETS if t["status"] == "in_progress"]
    return {
        "summary": {
            "grounded_count":     len(grounded),
            "overdue_count":      len(overdue),
            "due_this_week":      len(this_week),
            "total_open":         len(TICKETS),
            "estimated_cost_inr": 47200,
        },
        "grounded_vehicles": [
            {"vehicle_id": t["vehicle_id"], "reason": t["trigger_reason"], "since": t["created_at"]}
            for t in grounded
        ],
        "kanban": {
            "grounded":    grounded,
            "overdue":     overdue,
            "this_week":   this_week,
            "in_progress": in_progress,
        }
    }

def get_mechanic_stats():
    my    = [t for t in TICKETS if t.get("assigned_mechanic_id") == "USR-101"]
    unass = [t for t in TICKETS if not t.get("assigned_mechanic_id") and t["status"] not in ("completed",)]
    today = [t for t in my if t.get("due_by","") < t(days=1)]
    return {
        "mechanic": "Rajesh Kumar",
        "my_tickets":  my,
        "unassigned":  unass,
        "due_today":   today,
        "counts": {
            "assigned":   len(my),
            "unassigned": len(unass),
            "due_today":  len(today),
        }
    }

def get_tickets():
    counts = {
        "grounded":   sum(1 for t in TICKETS if t["status"] == "grounded"),
        "overdue":    sum(1 for t in TICKETS if t["status"] == "overdue"),
        "pending":    sum(1 for t in TICKETS if t["status"] == "pending"),
        "approved":   sum(1 for t in TICKETS if t["status"] == "approved"),
        "in_progress":sum(1 for t in TICKETS if t["status"] == "in_progress"),
        "completed":  0,
    }
    return {"tickets": TICKETS, "counts": counts, "total": len(TICKETS)}

def get_audit(vehicle_id: str):
    vid      = vehicle_id.upper()
    history  = SERVICE_HISTORY.get(vid, [])
    alerts   = ALERTS.get(vid, [])
    tickets  = [t for t in TICKETS if t["vehicle_id"] == vid]

    # Negligence: any unresolved critical alert older than 2 days
    flags = []
    for a in alerts:
        if not a["resolved"] and "critical" in a.get("severity",""):
            flags.append({
                "type": "NO_TICKET_CREATED",
                "severity": "HIGH",
                "alert_type": a["alert_type"],
                "alert_time": a["timestamp"],
                "days_ignored": 2,
                "description": f"Alert '{a['alert_type']}' fired 2 days ago — maintenance ticket was not approved in time.",
            })

    neg_level = "HIGH" if any(f["severity"]=="HIGH" for f in flags) else \
                "MEDIUM" if flags else "CLEAR"

    return {
        "vehicle_id":       vid,
        "negligence_level": neg_level,
        "negligence_flags": flags,
        "service_history":  history,
        "alerts_total":     len(alerts),
        "alerts":           alerts,
        "tickets":          tickets,
        "total_services":   len(history),
    }

"""
database.py — Central DB connection and reusable query helpers.
Import `db` from here everywhere else in the codebase.

Usage:
    from db.database import db, get_org_for_vehicle, get_vehicle_category
"""

from pymongo import MongoClient
from typing import Optional
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "vehicle_telemetry")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


# ─────────────────────────────────────────────
# VEHICLE CATEGORY MAPPING
# ─────────────────────────────────────────────

VEHICLE_CATEGORY_MAP = {
    "TRUCK": "HEAVY",
    "BUS":   "HEAVY",
    "VAN":   "HEAVY",
    "CAR":   "CAR",
    "PICKUP":"CAR",
    "BIKE":  "TWO_WHEELER",
    "SCOOTY":"TWO_WHEELER",
}

def get_vehicle_category(vehicle_type: str) -> Optional[str]:
    """Returns HEAVY / CAR / TWO_WHEELER for a given vehicle type."""
    return VEHICLE_CATEGORY_MAP.get(vehicle_type.upper())


# ─────────────────────────────────────────────
# ORG LOOKUP HELPERS
# ─────────────────────────────────────────────

def get_org_for_vehicle(vehicle_id: str) -> Optional[str]:
    """Returns org_id for a vehicle, or None if unassigned."""
    org = db.organizations.find_one({"vehicle_ids": vehicle_id}, {"org_id": 1})
    return org["org_id"] if org else None

def get_vehicles_for_org(org_id: str) -> list:
    """Returns list of vehicle_ids belonging to an org."""
    org = db.organizations.find_one({"org_id": org_id}, {"vehicle_ids": 1})
    return org["vehicle_ids"] if org else []

def get_vehicles_for_user(user_id: str) -> Optional[list]:
    """
    Returns vehicle list scoped to user's org.
    Super admin and insurance get None (meaning: all vehicles).
    """
    user = db.users.find_one({"user_id": user_id})
    if not user:
        return []
    if user["role"] in ("super_admin", "insurance"):
        return None  # caller should treat None as "no filter"
    return get_vehicles_for_org(user["org_id"])


# ─────────────────────────────────────────────
# TICKET HELPERS
# ─────────────────────────────────────────────

def ticket_exists_for_alert(alert_id: str) -> bool:
    """Prevents duplicate tickets from the same Round 2 alert."""
    return db.maintenance_tickets.find_one({"alert_id": alert_id}) is not None

def get_open_ticket(vehicle_id: str, service_type: str) -> Optional[dict]:
    """
    Returns an open (non-completed) ticket for this vehicle+service combo.
    Used to prevent creating duplicate routine tickets.
    """
    return db.maintenance_tickets.find_one({
        "vehicle_id": vehicle_id,
        "service_type": service_type,
        "status": {"$in": ["pending", "approved", "in_progress", "overdue", "grounded"]}
    })


# ─────────────────────────────────────────────
# SERVICE HISTORY HELPERS
# ─────────────────────────────────────────────

def get_last_service(vehicle_id: str, service_type: str) -> Optional[dict]:
    """
    Returns the most recent completed service of a given type for a vehicle.
    The scheduler uses this to calculate km/days since last service.
    """
    return db.service_history.find_one(
        {"vehicle_id": vehicle_id, "service_type": service_type},
        sort=[("service_date", -1)]
    )

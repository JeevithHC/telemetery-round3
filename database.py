"""
db/database.py — MongoDB connection + helper functions
=======================================================
Collections used:
  users                 — all user accounts (owner, mechanic, super_admin, insurance)
  organizations         — fleet orgs, each owns a list of vehicle_ids
  maintenance_tickets   — fault → ticket lifecycle
  service_history       — immutable completed service records
  maintenance_schedule  — rules for km/day intervals per service type
  telemetry_alerts      — raw alerts from Round 2 detection engine

Run seed_db.py once to populate users, orgs, and maintenance_schedule.
"""

import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME   = os.getenv("DB_NAME",   "fleetsentinel")

client = MongoClient(MONGO_URI)
db     = client[DB_NAME]

# ── Indexes (safe to call multiple times) ─────────────────────────────────────
db.users.create_index("user_id",  unique=True)
db.users.create_index("username", unique=True)
db.organizations.create_index("org_id", unique=True)
db.maintenance_tickets.create_index("ticket_id",  unique=True)
db.maintenance_tickets.create_index("vehicle_id")
db.maintenance_tickets.create_index("status")
db.service_history.create_index("event_id",   unique=True)
db.service_history.create_index("vehicle_id")
db.telemetry_alerts.create_index([("vehicle_id", ASCENDING), ("timestamp", DESCENDING)])


# ── Helper Functions ──────────────────────────────────────────────────────────

def get_vehicles_for_user(user_id: str):
    """
    Returns list of vehicle_ids the user is allowed to access.
    Returns None for super_admin / insurance (means: all vehicles).
    """
    user = db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        return []

    # Super admin and insurance see everything
    if user["role"] in ("super_admin", "insurance"):
        return None

    # Everyone else is scoped to their org
    org_id = user.get("org_id")
    if not org_id:
        return []

    org = db.organizations.find_one({"org_id": org_id}, {"_id": 0})
    if not org:
        return []

    return org.get("vehicle_ids", [])


def get_org_for_vehicle(vehicle_id: str) -> str | None:
    """Returns the org_id that owns this vehicle, or None."""
    org = db.organizations.find_one(
        {"vehicle_ids": vehicle_id},
        {"_id": 0, "org_id": 1}
    )
    return org["org_id"] if org else None


def get_last_service(vehicle_id: str, service_type: str = None) -> dict | None:
    """
    Returns the most recent service record for a vehicle.
    Optionally filter by service_type.
    """
    query = {"vehicle_id": vehicle_id}
    if service_type:
        query["service_type"] = service_type

    return db.service_history.find_one(
        query,
        {"_id": 0},
        sort=[("service_date", DESCENDING)]
    )

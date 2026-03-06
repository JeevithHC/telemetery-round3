# =============================================================================
# smart_engine/engine_db.py  (patched for Round 3 integration)
#
# KEY FIX: uses "maintenance_schedule_ledger" (not "maintenance_schedule")
# for the per-vehicle km ledger, because "maintenance_schedule" is already
# used by db_init.py to store interval rules.
# =============================================================================

from pymongo import MongoClient, ASCENDING, DESCENDING
from bson import ObjectId
from datetime import datetime
from engine_config import MONGO_URI

_client = None
_db     = None


def get_db():
    global _client, _db
    if _db is None:
        _client = MongoClient(MONGO_URI)
        _db = _client.get_default_database()
        _ensure_indexes(_db)
    return _db


def _ensure_indexes(db):
    """Idempotent index creation — safe to call every startup."""
    db.tickets.create_index([("vehicle_id", ASCENDING)])
    db.tickets.create_index([("status", ASCENDING)])
    db.tickets.create_index([("priority", ASCENDING)])
    db.tickets.create_index([("created_at", DESCENDING)])
    db.tickets.create_index([("source_event_id", ASCENDING)], sparse=True)
    db.tickets.create_index(
        [("vehicle_id", ASCENDING), ("task_id", ASCENDING), ("status", ASCENDING)],
        name="vehicle_task_status_idx",
    )
    # KEY FIX: renamed from maintenance_schedule → maintenance_schedule_ledger
    db.maintenance_schedule_ledger.create_index(
        [("vehicle_id", ASCENDING), ("task_id", ASCENDING)],
        unique=True,
        name="vehicle_task_unique",
    )
    db.telemetry_events.create_index([("vehicle_id", ASCENDING), ("processed", ASCENDING)])
    db.telemetry_events.create_index([("received_at", DESCENDING)])
    db.telemetry_events.create_index([("severity", ASCENDING), ("processed", ASCENDING)])


def get_all_vehicles():
    vehicles = list(get_db().vehicles.find())
    if vehicles:
        return vehicles
    ids = get_db().telemetry.distinct("vehicle_id")
    return [_make_stub_vehicle(vid) for vid in ids]


def get_vehicle(vehicle_id: str):
    doc = get_db().vehicles.find_one({"vehicle_id": vehicle_id})
    if doc:
        return doc
    try:
        doc = get_db().vehicles.find_one({"_id": ObjectId(vehicle_id)})
        if doc:
            return doc
    except Exception:
        pass
    latest = get_db().telemetry.find_one(
        {"vehicle_id": vehicle_id, "data_type": "raw"},
        sort=[("timestamp", -1)]
    )
    if latest:
        return _make_stub_vehicle(vehicle_id)
    return None


def _make_stub_vehicle(vehicle_id: str) -> dict:
    vehicle_type = vehicle_id.split("-")[0]
    latest = get_db().telemetry.find_one(
        {"vehicle_id": vehicle_id, "data_type": "raw"},
        sort=[("timestamp", -1)],
        projection={"odometer": 1}
    )
    odometer = latest["odometer"] if latest else 0
    org = get_db().organizations.find_one({"vehicle_ids": vehicle_id}, {"org_id": 1})
    owner_id = org["org_id"] if org else "UNASSIGNED"
    return {
        "_id":                 vehicle_id,
        "vehicle_id":          vehicle_id,
        "registration_number": vehicle_id,
        "make":                vehicle_type,
        "model":               vehicle_type,
        "vehicle_type":        vehicle_type,
        "owner_id":            owner_id,
        "odometer_km":         odometer,
        "purchase_date":       None,
    }


def get_schedule_entry(vehicle_id: str, task_id: str) -> dict | None:
    return get_db().maintenance_schedule_ledger.find_one({
        "vehicle_id": vehicle_id,
        "task_id":    task_id,
    })

def upsert_schedule_entry(vehicle_id: str, task_id: str, last_done_km: int):
    get_db().maintenance_schedule_ledger.update_one(
        {"vehicle_id": vehicle_id, "task_id": task_id},
        {"$set": {
            "vehicle_id":   vehicle_id,
            "task_id":      task_id,
            "last_done_km": last_done_km,
            "updated_at":   datetime.utcnow(),
        }},
        upsert=True,
    )

def get_all_schedule_entries(vehicle_id: str) -> list:
    return list(get_db().maintenance_schedule_ledger.find({"vehicle_id": vehicle_id}))


def ticket_exists_open(vehicle_id: str, task_id: str) -> bool:
    return get_db().tickets.find_one({
        "vehicle_id": vehicle_id,
        "task_id":    task_id,
        "status":     {"$in": ["open", "assigned", "in_progress"]},
    }) is not None

def inject_ticket(ticket: dict) -> str:
    result = get_db().tickets.insert_one(ticket)
    return str(result.inserted_id)

def get_ticket(ticket_id: str) -> dict | None:
    try:
        return get_db().tickets.find_one({"_id": ObjectId(ticket_id)})
    except Exception:
        return None

def get_open_tickets(vehicle_id: str = None) -> list:
    q = {"status": {"$in": ["open", "assigned", "in_progress"]}}
    if vehicle_id:
        q["vehicle_id"] = vehicle_id
    return list(get_db().tickets.find(q).sort("created_at", DESCENDING))

def update_ticket_status(ticket_id: str, status: str, note: str = ""):
    get_db().tickets.update_one(
        {"_id": ObjectId(ticket_id)},
        {"$set": {"status": status, "updated_at": datetime.utcnow()},
         "$push": {"history": {"status": status, "note": note, "timestamp": datetime.utcnow()}}},
    )


def get_unprocessed_p1_events() -> list:
    return list(get_db().telemetry_events.find({
        "severity":  "P1_WARNING",
        "processed": False,
    }).sort("received_at", ASCENDING))

def mark_event_processed(event_id: str, ticket_id: str = None):
    get_db().telemetry_events.update_one(
        {"_id": ObjectId(event_id)},
        {"$set": {"processed": True, "processed_at": datetime.utcnow(), "ticket_id": ticket_id}},
    )

def insert_telemetry_event(event: dict) -> str:
    event.setdefault("received_at", datetime.utcnow())
    event.setdefault("processed",   False)
    result = get_db().telemetry_events.insert_one(event)
    return str(result.inserted_id)


def log_engine_run(run_type: str, summary: dict):
    get_db().engine_run_log.insert_one({
        "run_type":  run_type,
        "summary":   summary,
        "logged_at": datetime.utcnow(),
    })
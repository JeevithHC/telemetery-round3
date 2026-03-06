"""
sync_vehicles.py — One-time setup script (and periodic sync).

PROBLEM IT SOLVES:
    The Smart Engine's ticket_factory.py expects a `vehicles` collection with
    fields like: registration_number, make, model, owner_id, odometer_km, purchase_date

    Our Round 2 system stores vehicles implicitly in the `telemetry` collection
    as vehicle_ids like "CAR-001", "TRUCK-005", etc.

    This script bridges that gap by building a proper `vehicles` collection
    from our existing telemetry + organizations data.

RUN:
    python sync_vehicles.py            # full sync
    python sync_vehicles.py --watch    # re-sync every 5 minutes (for live odometer updates)

AFTER THIS RUNS:
    The smart engine will have rich vehicle data including odometer_km,
    which it uses for the age-based interval compression feature.
"""

import os
import time
import argparse
from datetime import datetime
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv()

_client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017/vehicle_telemetry"))
_db     = _client.get_default_database()

# ── Vehicle type → make/model display names ───────────────────────────────────
VEHICLE_DISPLAY = {
    "TRUCK":  {"make": "Ashok Leyland", "model": "Dost Strong"},
    "BUS":    {"make": "TATA Motors",   "model": "Starbus Ultra"},
    "VAN":    {"make": "Force Motors",  "model": "Traveller"},
    "CAR":    {"make": "Maruti Suzuki", "model": "Swift Dzire"},
    "PICKUP": {"make": "TATA Motors",   "model": "Xenon XT"},
    "BIKE":   {"make": "Royal Enfield", "model": "Bullet 350"},
    "SCOOTY": {"make": "Honda",         "model": "Activa 6G"},
}

# ── Rough purchase_date by vehicle number (older numbers = older vehicles) ────
# We simulate this so the age-based interval multiplier actually fires.
# Higher vehicle numbers are "newer" in our fleet.
def estimate_purchase_year(vehicle_num: int, total_in_type: int) -> int:
    """Older vehicles (lower numbers) were purchased earlier."""
    current_year = datetime.utcnow().year
    max_age = 12   # oldest vehicle is 12 years old
    age = int((1 - vehicle_num / total_in_type) * max_age)
    return current_year - age


def run_sync(verbose: bool = True) -> dict:
    started = datetime.utcnow()
    stats = {"synced": 0, "updated": 0, "skipped": 0, "errors": 0}

    if verbose:
        print(f"\n[VehicleSync] Starting sync at {started.strftime('%H:%M:%S')}")

    # Get all unique vehicle IDs from telemetry
    vehicle_ids = _db.telemetry.distinct("vehicle_id")

    # Group by type to calculate relative age
    from collections import defaultdict
    type_groups = defaultdict(list)
    for vid in vehicle_ids:
        vtype = vid.split("-")[0]
        num   = int(vid.split("-")[1]) if "-" in vid else 1
        type_groups[vtype].append((num, vid))

    for vtype, entries in type_groups.items():
        entries.sort()  # sort by number
        total = len(entries)

        for idx, (num, vehicle_id) in enumerate(entries):
            try:
                # Get latest telemetry for odometer
                latest = _db.telemetry.find_one(
                    {"vehicle_id": vehicle_id, "data_type": "raw"},
                    sort=[("timestamp", -1)],
                    projection={"odometer": 1, "health_score": 1, "timestamp": 1}
                )
                odometer = float(latest["odometer"]) if latest else 0.0

                # Get org
                org = _db.organizations.find_one(
                    {"vehicle_ids": vehicle_id},
                    {"org_id": 1, "name": 1}
                )
                owner_id   = org["org_id"]   if org else "UNASSIGNED"
                owner_name = org["name"]      if org else "Unassigned"

                # Build purchase date
                purchase_year = estimate_purchase_year(idx + 1, total)
                purchase_date = datetime(purchase_year, 1, 1)

                display = VEHICLE_DISPLAY.get(vtype, {"make": vtype, "model": "Unknown"})

                vehicle_doc = {
                    "vehicle_id":          vehicle_id,
                    "registration_number": vehicle_id,        # e.g. "CAR-001"
                    "make":                display["make"],
                    "model":               display["model"],
                    "vehicle_type":        vtype,
                    "owner_id":            owner_id,
                    "owner_name":          owner_name,
                    "odometer_km":         odometer,
                    "purchase_date":       purchase_date,
                    "last_synced":         datetime.utcnow(),
                }

                result = _db.vehicles.update_one(
                    {"vehicle_id": vehicle_id},
                    {"$set": vehicle_doc},
                    upsert=True
                )

                if result.upserted_id:
                    stats["synced"] += 1
                    if verbose:
                        age_years = (datetime.utcnow() - purchase_date).days / 365.25
                        print(f"  ✅ {vehicle_id:<12} | {display['make']:<20} | "
                              f"odometer={odometer:>8.0f} km | age={age_years:.1f} yrs")
                else:
                    stats["updated"] += 1

            except Exception as e:
                stats["errors"] += 1
                if verbose:
                    print(f"  ❌ {vehicle_id}: {e}")

    # Ensure index on vehicle_id for fast lookups
    _db.vehicles.create_index("vehicle_id", unique=True)

    elapsed = (datetime.utcnow() - started).total_seconds()
    total_vehicles = _db.vehicles.count_documents({})

    if verbose:
        print(f"\n[VehicleSync] Done in {elapsed:.1f}s")
        print(f"  New:     {stats['synced']}")
        print(f"  Updated: {stats['updated']}")
        print(f"  Errors:  {stats['errors']}")
        print(f"  Total in vehicles collection: {total_vehicles}")

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sync vehicles collection from telemetry")
    parser.add_argument("--watch", action="store_true",
                        help="Keep running, re-sync every 5 minutes")
    parser.add_argument("--interval", type=int, default=300,
                        help="Sync interval in seconds when --watch is used (default: 300)")
    args = parser.parse_args()

    if args.watch:
        print(f"[VehicleSync] Watch mode — syncing every {args.interval}s. Ctrl+C to stop.")
        while True:
            run_sync(verbose=False)
            print(f"[VehicleSync] Synced at {datetime.utcnow().strftime('%H:%M:%S')}")
            time.sleep(args.interval)
    else:
        run_sync(verbose=True)

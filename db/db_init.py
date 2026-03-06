"""
db_init.py — Run this ONCE to set up all Round 3 collections and indexes.

Usage:
    python db_init.py

What it does:
    1. Creates 5 new MongoDB collections
    2. Creates all indexes on each collection
    3. Seeds maintenance_schedule with interval rules for all vehicle types
    4. Seeds 3 sample organizations
    5. Seeds sample users for each role (mechanic, owner, insurance, admin)
"""

from pymongo import MongoClient, ASCENDING, DESCENDING
from datetime import datetime
import bcrypt
import os
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "vehicle_telemetry")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]


# ─────────────────────────────────────────────
# STEP 1: CREATE COLLECTIONS
# ─────────────────────────────────────────────

COLLECTIONS = [
    "organizations",
    "users",
    "maintenance_schedule",
    "service_history",
    "maintenance_tickets",
]

existing = db.list_collection_names()
for col in COLLECTIONS:
    if col not in existing:
        db.create_collection(col)
        print(f"  ✅ Created collection: {col}")
    else:
        print(f"  ⚠️  Collection already exists (skipped): {col}")


# ─────────────────────────────────────────────
# STEP 2: CREATE INDEXES
# ─────────────────────────────────────────────

print("\n📇 Creating indexes...")

# --- organizations ---
db.organizations.create_index([("org_id", ASCENDING)], unique=True)
db.organizations.create_index([("vehicle_ids", ASCENDING)])
print("  ✅ organizations indexes")

# --- users ---
db.users.create_index([("user_id", ASCENDING)], unique=True)
db.users.create_index([("username", ASCENDING)], unique=True)
db.users.create_index([("org_id", ASCENDING)])
db.users.create_index([("role", ASCENDING)])
print("  ✅ users indexes")

# --- maintenance_schedule ---
db.maintenance_schedule.create_index([("schedule_id", ASCENDING)], unique=True)
db.maintenance_schedule.create_index([("vehicle_category", ASCENDING)])
db.maintenance_schedule.create_index([("vehicle_types", ASCENDING)])
print("  ✅ maintenance_schedule indexes")

# --- service_history ---
db.service_history.create_index([("event_id", ASCENDING)], unique=True)
db.service_history.create_index([("vehicle_id", ASCENDING), ("service_date", DESCENDING)])
db.service_history.create_index([("org_id", ASCENDING), ("service_date", DESCENDING)])
db.service_history.create_index([("mechanic_id", ASCENDING)])
db.service_history.create_index([("ticket_id", ASCENDING)])
print("  ✅ service_history indexes")

# --- maintenance_tickets ---
db.maintenance_tickets.create_index([("ticket_id", ASCENDING)], unique=True)
db.maintenance_tickets.create_index([("vehicle_id", ASCENDING), ("created_at", DESCENDING)])
db.maintenance_tickets.create_index([("org_id", ASCENDING), ("status", ASCENDING)])
db.maintenance_tickets.create_index([("status", ASCENDING), ("priority", ASCENDING)])
db.maintenance_tickets.create_index([("due_by", ASCENDING)])          # for overdue engine
db.maintenance_tickets.create_index([("alert_id", ASCENDING)])        # alert → ticket lookup
db.maintenance_tickets.create_index([("assigned_mechanic_id", ASCENDING)])
print("  ✅ maintenance_tickets indexes")


# ─────────────────────────────────────────────
# STEP 3: SEED MAINTENANCE SCHEDULE RULES
# ─────────────────────────────────────────────

print("\n🌱 Seeding maintenance schedule rules...")

schedule_rules = [

    # ── HEAVY VEHICLES (TRUCK, BUS, VAN) ──────────────────────────────

    {
        "schedule_id": "SCHED-HEAVY-OIL",
        "vehicle_category": "HEAVY",
        "vehicle_types": ["TRUCK", "BUS", "VAN"],
        "service_type": "Oil Change",
        "km_interval": 20000,
        "days_interval": 180,
        "warning_km_before": 1000,
        "warning_days_before": 14,
        "checklist_items": [
            "Drain and replace engine oil",
            "Replace oil filter",
            "Check oil pressure post-replacement",
            "Inspect for oil leaks under vehicle",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-HEAVY-AIR-BRAKE",
        "vehicle_category": "HEAVY",
        "vehicle_types": ["TRUCK", "BUS"],
        "service_type": "Air Brake Inspection",
        "km_interval": 20000,
        "days_interval": 180,
        "warning_km_before": 1000,
        "warning_days_before": 14,
        "checklist_items": [
            "Test air brake line pressure (must be ≥ 90 PSI)",
            "Inspect air compressor output",
            "Check brake drums and shoes",
            "Test slack adjusters",
            "Verify air dryer operation",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-HEAVY-DPF",
        "vehicle_category": "HEAVY",
        "vehicle_types": ["TRUCK", "BUS", "VAN"],
        "service_type": "DPF Clean & Forced Regen",
        "km_interval": 20000,
        "days_interval": 180,
        "warning_km_before": 1000,
        "warning_days_before": 14,
        "checklist_items": [
            "Check DPF backpressure (threshold: 10 kPa)",
            "Perform forced regeneration cycle",
            "Inspect exhaust temperature sensors",
            "Clean or replace DPF if backpressure > 15 kPa",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-HEAVY-SUSPENSION",
        "vehicle_category": "HEAVY",
        "vehicle_types": ["TRUCK", "BUS", "VAN"],
        "service_type": "Suspension Check",
        "km_interval": 20000,
        "days_interval": 180,
        "warning_km_before": 1000,
        "warning_days_before": 14,
        "checklist_items": [
            "Inspect leaf springs for cracks",
            "Check shock absorber condition",
            "Measure chassis height at load",
            "Torque all suspension bolts",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },

    # ── CARS & PICKUPS ─────────────────────────────────────────────────

    {
        "schedule_id": "SCHED-CAR-OIL",
        "vehicle_category": "CAR",
        "vehicle_types": ["CAR", "PICKUP"],
        "service_type": "Oil Change",
        "km_interval": 10000,
        "days_interval": 365,
        "warning_km_before": 500,
        "warning_days_before": 14,
        "checklist_items": [
            "Drain and replace synthetic engine oil",
            "Replace oil filter",
            "Top up coolant and windshield fluid",
            "Check for leaks",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-CAR-BATTERY",
        "vehicle_category": "CAR",
        "vehicle_types": ["CAR", "PICKUP"],
        "service_type": "Battery Check",
        "km_interval": 10000,
        "days_interval": 365,
        "warning_km_before": 500,
        "warning_days_before": 14,
        "checklist_items": [
            "Test battery voltage (healthy: 12.4–12.7V)",
            "Check alternator charging output",
            "Inspect terminal corrosion",
            "Load-test battery",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-CAR-TYRE",
        "vehicle_category": "CAR",
        "vehicle_types": ["CAR", "PICKUP"],
        "service_type": "Tyre Service",
        "km_interval": 10000,
        "days_interval": 365,
        "warning_km_before": 500,
        "warning_days_before": 14,
        "checklist_items": [
            "Rotate tyres (FL→RR, FR→RL)",
            "Check tyre pressure (all 4 tyres)",
            "Inspect tread depth (replace if < 2mm)",
            "Check for sidewall cracking",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-CAR-SPARK",
        "vehicle_category": "CAR",
        "vehicle_types": ["CAR", "PICKUP"],
        "service_type": "Spark Plug & Coil Inspection",
        "km_interval": 10000,
        "days_interval": 365,
        "warning_km_before": 500,
        "warning_days_before": 14,
        "checklist_items": [
            "Remove and inspect all spark plugs",
            "Replace plugs if gap > 1.1mm",
            "Test ignition coil resistance",
            "Clear any misfire fault codes",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },

    # ── TWO-WHEELERS (BIKE, SCOOTY) ────────────────────────────────────

    {
        "schedule_id": "SCHED-2W-OIL",
        "vehicle_category": "TWO_WHEELER",
        "vehicle_types": ["BIKE", "SCOOTY"],
        "service_type": "Oil Change",
        "km_interval": 3000,
        "days_interval": 120,
        "warning_km_before": 200,
        "warning_days_before": 7,
        "checklist_items": [
            "Drain and replace engine oil",
            "Replace oil filter (if applicable)",
            "Check for leaks after fill",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-2W-CHAIN",
        "vehicle_category": "TWO_WHEELER",
        "vehicle_types": ["BIKE", "SCOOTY"],
        "service_type": "Chain Lubrication & Tensioning",
        "km_interval": 3000,
        "days_interval": 120,
        "warning_km_before": 200,
        "warning_days_before": 7,
        "checklist_items": [
            "Clean chain with degreaser",
            "Lubricate chain thoroughly",
            "Check chain slack (ideal: 20–30mm)",
            "Adjust tensioner if needed",
            "Inspect sprockets for wear",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "schedule_id": "SCHED-2W-BRAKE",
        "vehicle_category": "TWO_WHEELER",
        "vehicle_types": ["BIKE", "SCOOTY"],
        "service_type": "Brake Pad Replacement",
        "km_interval": 3000,
        "days_interval": 120,
        "warning_km_before": 200,
        "warning_days_before": 7,
        "checklist_items": [
            "Inspect front brake pad thickness",
            "Inspect rear brake pad thickness",
            "Replace pads if < 2mm",
            "Bleed brake lines if spongy",
            "Test brake feel at low speed",
        ],
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
]

for rule in schedule_rules:
    db.maintenance_schedule.update_one(
        {"schedule_id": rule["schedule_id"]},
        {"$setOnInsert": rule},
        upsert=True
    )
print(f"  ✅ Inserted {len(schedule_rules)} schedule rules")


# ─────────────────────────────────────────────
# STEP 4: SEED ORGANIZATIONS
# ─────────────────────────────────────────────

print("\n🏢 Seeding organizations...")

# Map 100 vehicles to 3 orgs (matching your simulator)
# TRUCK-001 to TRUCK-020, BUS-001 to BUS-015
# CAR-001 to CAR-020, VAN-001 to VAN-015, PICKUP-001 to PICKUP-010
# BIKE-001 to BIKE-010, SCOOTY-001 to SCOOTY-010

def make_ids(prefix, count):
    return [f"{prefix}-{str(i).zfill(3)}" for i in range(1, count + 1)]

orgs = [
    {
        "org_id": "ORG-001",
        "name": "Chennai Metro Logistics",
        "contact_email": "ops@cml.in",
        "vehicle_ids": make_ids("TRUCK", 20) + make_ids("VAN", 15),
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "org_id": "ORG-002",
        "name": "TN State Transport",
        "contact_email": "fleet@tnst.gov.in",
        "vehicle_ids": make_ids("BUS", 15) + make_ids("PICKUP", 10),
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
    {
        "org_id": "ORG-003",
        "name": "Rapid Riders Pvt Ltd",
        "contact_email": "admin@rapidriders.com",
        "vehicle_ids": make_ids("CAR", 20) + make_ids("BIKE", 10) + make_ids("SCOOTY", 10),
        "created_at": datetime.utcnow(),
        "is_active": True,
    },
]

for org in orgs:
    db.organizations.update_one(
        {"org_id": org["org_id"]},
        {"$setOnInsert": org},
        upsert=True
    )
print(f"  ✅ Inserted {len(orgs)} organizations")


# ─────────────────────────────────────────────
# STEP 5: SEED USERS (one per role per org)
# ─────────────────────────────────────────────

print("\n👤 Seeding users...")

def hash_pw(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

users = [
    # Super Admin
    {
        "user_id": "USR-000",
        "username": "admin",
        "hashed_password": hash_pw("admin123"),
        "role": "super_admin",
        "org_id": None,
        "full_name": "System Administrator",
        "email": "admin@telemetry.local",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    # ORG-001 users
    {
        "user_id": "USR-101",
        "username": "mechanic_raj",
        "hashed_password": hash_pw("mech123"),
        "role": "mechanic",
        "org_id": "ORG-001",
        "full_name": "Rajesh Kumar",
        "email": "raj@cml.in",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    {
        "user_id": "USR-102",
        "username": "owner_cml",
        "hashed_password": hash_pw("owner123"),
        "role": "owner",
        "org_id": "ORG-001",
        "full_name": "Priya Venkat",
        "email": "priya@cml.in",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    # ORG-002 users
    {
        "user_id": "USR-201",
        "username": "mechanic_arjun",
        "hashed_password": hash_pw("mech123"),
        "role": "mechanic",
        "org_id": "ORG-002",
        "full_name": "Arjun Selvam",
        "email": "arjun@tnst.gov.in",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    {
        "user_id": "USR-202",
        "username": "owner_tnst",
        "hashed_password": hash_pw("owner123"),
        "role": "owner",
        "org_id": "ORG-002",
        "full_name": "Karthik Balan",
        "email": "karthik@tnst.gov.in",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    # ORG-003 users
    {
        "user_id": "USR-301",
        "username": "mechanic_dev",
        "hashed_password": hash_pw("mech123"),
        "role": "mechanic",
        "org_id": "ORG-003",
        "full_name": "Devika Nair",
        "email": "dev@rapidriders.com",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    {
        "user_id": "USR-302",
        "username": "owner_rr",
        "hashed_password": hash_pw("owner123"),
        "role": "owner",
        "org_id": "ORG-003",
        "full_name": "Suresh Pillai",
        "email": "suresh@rapidriders.com",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
    # Insurance user (no org — sees all vehicles for audit)
    {
        "user_id": "USR-401",
        "username": "auditor_lic",
        "hashed_password": hash_pw("audit123"),
        "role": "insurance",
        "org_id": None,
        "full_name": "LIC Fleet Auditor",
        "email": "audit@lic.in",
        "created_at": datetime.utcnow(),
        "is_active": True,
        "last_login": None,
    },
]

for user in users:
    db.users.update_one(
        {"user_id": user["user_id"]},
        {"$setOnInsert": user},
        upsert=True
    )
print(f"  ✅ Inserted {len(users)} users")


# ─────────────────────────────────────────────
# DONE
# ─────────────────────────────────────────────

print("\n" + "="*55)
print("✅  Database initialization complete.")
print("="*55)
print("\nCollections created:")
for col in COLLECTIONS:
    count = db[col].count_documents({})
    print(f"   {col:<30} {count} documents")

print("\nDefault login credentials:")
print("   Role         Username          Password")
print("   ──────────── ──────────────── ─────────")
print("   super_admin  admin             admin123")
print("   mechanic     mechanic_raj      mech123")
print("   owner        owner_cml         owner123")
print("   insurance    auditor_lic       audit123")
print("\n⚠️  Change all passwords before deploying to production.\n")

client.close()

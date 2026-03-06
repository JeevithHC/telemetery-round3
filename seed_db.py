"""
seed_db.py — Run once to populate MongoDB with:
  - Users (owner, mechanics, super_admin, insurance)
  - Organizations (3 Chennai fleet orgs)
  - Maintenance schedule rules (km + day intervals)

Run:
    python seed_db.py
"""

import bcrypt
from datetime import datetime
from db.database import db

def hash_pw(plain: str) -> str:
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()

# ── Clear existing seed data ──────────────────────────────────────────────────
db.users.delete_many({})
db.organizations.delete_many({})
db.maintenance_schedule.delete_many({})
print("Cleared existing seed data.")

# ── Users ─────────────────────────────────────────────────────────────────────
users = [
    # Super admin
    {
        "user_id":         "USR-ADMIN-001",
        "username":        "admin",
        "hashed_password": hash_pw("admin123"),
        "full_name":       "Super Admin",
        "role":            "super_admin",
        "org_id":          None,
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    # Fleet Owners
    {
        "user_id":         "USR-OWN-001",
        "username":        "owner1",
        "hashed_password": hash_pw("owner123"),
        "full_name":       "Rajan Subramaniam",
        "role":            "owner",
        "org_id":          "ORG-001",
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    {
        "user_id":         "USR-OWN-002",
        "username":        "owner2",
        "hashed_password": hash_pw("owner123"),
        "full_name":       "Priya Venkatesh",
        "role":            "owner",
        "org_id":          "ORG-002",
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    # Mechanics
    {
        "user_id":         "USR-MEC-001",
        "username":        "mechanic1",
        "hashed_password": hash_pw("mech123"),
        "full_name":       "Arjun Krishnan",
        "role":            "mechanic",
        "org_id":          "ORG-001",
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    {
        "user_id":         "USR-MEC-002",
        "username":        "mechanic2",
        "hashed_password": hash_pw("mech123"),
        "full_name":       "Deepak Selvam",
        "role":            "mechanic",
        "org_id":          "ORG-001",
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    {
        "user_id":         "USR-MEC-003",
        "username":        "mechanic3",
        "hashed_password": hash_pw("mech123"),
        "full_name":       "Murugan Pillai",
        "role":            "mechanic",
        "org_id":          "ORG-002",
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
    # Insurance
    {
        "user_id":         "USR-INS-001",
        "username":        "insurance1",
        "hashed_password": hash_pw("ins123"),
        "full_name":       "United India Insurance",
        "role":            "insurance",
        "org_id":          None,
        "is_active":       True,
        "created_at":      datetime.utcnow(),
        "last_login":      None,
    },
]

db.users.insert_many(users)
print(f"Inserted {len(users)} users.")

# ── Organizations ─────────────────────────────────────────────────────────────
# Split the 100-vehicle fleet across 2 orgs
org1_vehicles = (
    [f"SCOOTY-{str(i).zfill(3)}" for i in range(1, 11)] +
    [f"BIKE-{str(i).zfill(3)}"   for i in range(1, 11)] +
    [f"CAR-{str(i).zfill(3)}"    for i in range(1, 11)] +
    [f"PICKUP-{str(i).zfill(3)}" for i in range(1, 6)]  +
    [f"VAN-{str(i).zfill(3)}"    for i in range(1, 8)]  +
    [f"TRUCK-{str(i).zfill(3)}"  for i in range(1, 11)]
)

org2_vehicles = (
    [f"CAR-{str(i).zfill(3)}"    for i in range(11, 21)] +
    [f"PICKUP-{str(i).zfill(3)}" for i in range(6, 11)]  +
    [f"VAN-{str(i).zfill(3)}"    for i in range(8, 16)]  +
    [f"TRUCK-{str(i).zfill(3)}"  for i in range(11, 21)] +
    [f"BUS-{str(i).zfill(3)}"    for i in range(1, 16)]
)

organizations = [
    {
        "org_id":      "ORG-001",
        "name":        "Chennai Metro Logistics",
        "owner_id":    "USR-OWN-001",
        "vehicle_ids": org1_vehicles,
        "city":        "Chennai",
        "created_at":  datetime.utcnow(),
    },
    {
        "org_id":      "ORG-002",
        "name":        "Tamil Nadu Fleet Services",
        "owner_id":    "USR-OWN-002",
        "vehicle_ids": org2_vehicles,
        "city":        "Chennai",
        "created_at":  datetime.utcnow(),
    },
]

db.organizations.insert_many(organizations)
print(f"Inserted {len(organizations)} organizations.")

# ── Maintenance Schedule Rules ────────────────────────────────────────────────
# km_interval: trigger ticket every N km
# days_interval: trigger ticket every N days
schedule_rules = [
    {"service_type": "OIL_SYSTEM_SERVICE",      "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS"],        "km_interval": 5000,  "days_interval": 90},
    {"service_type": "OIL_SYSTEM_SERVICE",      "vehicle_types": ["SCOOTY","BIKE"],                           "km_interval": 3000,  "days_interval": 60},
    {"service_type": "TYRE_REPLACEMENT",         "vehicle_types": ["CAR","PICKUP","VAN"],                      "km_interval": 40000, "days_interval": 730},
    {"service_type": "TYRE_REPLACEMENT",         "vehicle_types": ["TRUCK","BUS"],                             "km_interval": 60000, "days_interval": 730},
    {"service_type": "TYRE_REPLACEMENT",         "vehicle_types": ["SCOOTY","BIKE"],                           "km_interval": 20000, "days_interval": 365},
    {"service_type": "BRAKE_PAD_REPLACEMENT",    "vehicle_types": ["CAR","PICKUP","VAN"],                      "km_interval": 25000, "days_interval": 365},
    {"service_type": "BRAKE_SYSTEM_OVERHAUL",    "vehicle_types": ["TRUCK","BUS"],                             "km_interval": 50000, "days_interval": 365},
    {"service_type": "ENGINE_INSPECTION",        "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS","SCOOTY","BIKE"], "km_interval": 20000, "days_interval": 180},
    {"service_type": "ELECTRICAL_INSPECTION",    "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS"],        "km_interval": 15000, "days_interval": 180},
    {"service_type": "TURBO_SERVICE",            "vehicle_types": ["PICKUP","VAN","TRUCK","BUS"],               "km_interval": 30000, "days_interval": 365},
    {"service_type": "WHEEL_ALIGNMENT",          "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS"],        "km_interval": 10000, "days_interval": 180},
    {"service_type": "DRIVETRAIN_INSPECTION",    "vehicle_types": ["SCOOTY","BIKE"],                           "km_interval": 5000,  "days_interval": 90},
    {"service_type": "FUEL_SYSTEM_INSPECTION",   "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS"],        "km_interval": 20000, "days_interval": 365},
    {"service_type": "GENERAL_INSPECTION",       "vehicle_types": ["CAR","PICKUP","VAN","TRUCK","BUS","SCOOTY","BIKE"], "km_interval": 10000, "days_interval": 90},
]

db.maintenance_schedule.insert_many(schedule_rules)
print(f"Inserted {len(schedule_rules)} maintenance schedule rules.")

# ── Summary ───────────────────────────────────────────────────────────────────
print("\n✅ Seed complete. Login credentials:")
print("  admin      / admin123   (super_admin)")
print("  owner1     / owner123   (owner — ORG-001)")
print("  owner2     / owner123   (owner — ORG-002)")
print("  mechanic1  / mech123    (mechanic — ORG-001)")
print("  mechanic2  / mech123    (mechanic — ORG-001)")
print("  mechanic3  / mech123    (mechanic — ORG-002)")
print("  insurance1 / ins123     (insurance — all orgs)")

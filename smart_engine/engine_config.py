# =============================================================================
# smart_engine/engine_config.py
#
# Central config for the Smart Engine (Member 2).
# All thresholds, cron timings, P1 mappings, and ticket templates live here.
# Change values here without touching any other file.
# =============================================================================

import os
from dotenv import load_dotenv
load_dotenv()
# Reads MONGO_URI from .env — same .env used by the Round 2 and Round 3 API
# Format must include DB name: mongodb+srv://user:pass@host/vehicle_telemetry
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/vehicle_telemetry")

# ── Cron Schedule ─────────────────────────────────────────────────────────────
# Odometer vs maintenance_schedule check (Round 2 → Round 3 bridge)
ODOMETER_CHECK_CRON = {
    "hour":   "*",     # every hour  (change to "8" for daily at 8am)
    "minute": "0",
}

# Telemetry stream poll interval (seconds) — how often we check for new P1 events
TELEMETRY_POLL_SECONDS = 30

# Weekly snapshot cron (mirrors existing weekly_check but driven by this engine)
WEEKLY_SNAPSHOT_CRON = {
    "day_of_week": "sun",
    "hour": "0",
    "minute": "5",
}

# ── Odometer-Based Maintenance Schedule ──────────────────────────────────────
# Each rule defines: every N km → trigger a specific maintenance task.
# These are checked against vehicles.odometer_km vs the last recorded service km.
#
# priority: P1 = critical / safety, P2 = important, P3 = routine
MAINTENANCE_SCHEDULE = [
    {
        "task_id":       "OIL_CHANGE",
        "description":   "Engine Oil & Filter Change",
        "interval_km":   5_000,
        "priority":      "P2",
        "estimated_hrs": 1.0,
        "parts":         ["Engine oil (4L)", "Oil filter"],
    },
    {
        "task_id":       "TYRE_ROTATION",
        "description":   "Tyre Rotation & Pressure Check",
        "interval_km":   10_000,
        "priority":      "P3",
        "estimated_hrs": 0.5,
        "parts":         [],
    },
    {
        "task_id":       "AIR_FILTER",
        "description":   "Air Filter Replacement",
        "interval_km":   15_000,
        "priority":      "P2",
        "estimated_hrs": 0.5,
        "parts":         ["Air filter"],
    },
    {
        "task_id":       "BRAKE_FLUID",
        "description":   "Brake Fluid Flush & Top-up",
        "interval_km":   20_000,
        "priority":      "P1",
        "estimated_hrs": 1.5,
        "parts":         ["Brake fluid (DOT4, 1L)"],
    },
    {
        "task_id":       "SPARK_PLUGS",
        "description":   "Spark Plug Replacement",
        "interval_km":   30_000,
        "priority":      "P2",
        "estimated_hrs": 2.0,
        "parts":         ["Spark plugs (set of 4)"],
    },
    {
        "task_id":       "COOLANT_FLUSH",
        "description":   "Coolant System Flush & Refill",
        "interval_km":   40_000,
        "priority":      "P1",
        "estimated_hrs": 2.0,
        "parts":         ["Coolant (2L)", "Distilled water"],
    },
    {
        "task_id":       "BRAKE_PADS",
        "description":   "Brake Pad Inspection & Replacement",
        "interval_km":   40_000,
        "priority":      "P1",
        "estimated_hrs": 2.5,
        "parts":         ["Front brake pads (set)", "Rear brake pads (set)"],
    },
    {
        "task_id":       "TRANSMISSION_FLUID",
        "description":   "Transmission Fluid Change",
        "interval_km":   60_000,
        "priority":      "P2",
        "estimated_hrs": 2.0,
        "parts":         ["Transmission fluid (2L)"],
    },
    {
        "task_id":       "TIMING_BELT",
        "description":   "Timing Belt / Chain Inspection",
        "interval_km":   80_000,
        "priority":      "P1",
        "estimated_hrs": 4.0,
        "parts":         ["Timing belt kit"],
    },
    {
        "task_id":       "FULL_SERVICE",
        "description":   "Full Major Service (100k Milestone)",
        "interval_km":   100_000,
        "priority":      "P1",
        "estimated_hrs": 6.0,
        "parts":         ["Oil", "Filters", "Belts", "Plugs", "Fluids"],
    },
]

# ── P1 Telemetry Event → Ticket Mapping ──────────────────────────────────────
# Maps diagnostic fault codes / telemetry event types → structured ticket fields.
# When the telemetry stream emits a P1_WARNING with a matching event_code,
# the engine autonomously injects a formatted ticket into the `tickets` collection.
#
# Each entry:
#   event_code    – the code arriving in the telemetry stream
#   task_id       – links back to a MAINTENANCE_SCHEDULE entry (or standalone)
#   title         – human-readable ticket title
#   description   – what the ticket describes
#   priority      – always P1 for this mapping (can be overridden per rule)
#   category      – used by Round 3 dashboard for grouping
#   auto_assign   – role that should receive this ticket first
#   sla_hours     – how many hours until this ticket must be resolved
P1_WARNING_MAP = {
    # ── Engine ────────────────────────────────────────────────────────
    "ENG_OVERHEAT": {
        "task_id":     "COOLANT_FLUSH",
        "title":       "Engine Overheating Detected",
        "description": "Telemetry reports engine temperature above safe threshold. "
                       "Immediate coolant system inspection required.",
        "priority":    "P1",
        "category":    "engine",
        "auto_assign": "mechanic",
        "sla_hours":   4,
    },
    "ENG_OIL_LOW": {
        "task_id":     "OIL_CHANGE",
        "title":       "Critical Engine Oil Level",
        "description": "Oil pressure sensor reports critically low oil level. "
                       "Risk of engine seizure if not addressed immediately.",
        "priority":    "P1",
        "category":    "engine",
        "auto_assign": "mechanic",
        "sla_hours":   2,
    },
    "ENG_MISFIRE": {
        "task_id":     "SPARK_PLUGS",
        "title":       "Engine Misfire Detected",
        "description": "Multiple cylinder misfire events logged. "
                       "Spark plug or ignition coil failure suspected.",
        "priority":    "P1",
        "category":    "engine",
        "auto_assign": "mechanic",
        "sla_hours":   8,
    },
    # ── Brakes ───────────────────────────────────────────────────────
    "BRAKE_FAIL": {
        "task_id":     "BRAKE_PADS",
        "title":       "Brake System Failure Warning",
        "description": "Brake pressure sensor anomaly detected. "
                       "Vehicle must not be driven until brakes are inspected.",
        "priority":    "P1",
        "category":    "brakes",
        "auto_assign": "mechanic",
        "sla_hours":   1,
    },
    "BRAKE_FLUID_LOW": {
        "task_id":     "BRAKE_FLUID",
        "title":       "Brake Fluid Level Critical",
        "description": "Brake fluid reservoir below minimum. "
                       "Possible leak or pad wear. Immediate inspection required.",
        "priority":    "P1",
        "category":    "brakes",
        "auto_assign": "mechanic",
        "sla_hours":   2,
    },
    # ── Transmission ─────────────────────────────────────────────────
    "TRANS_SLIP": {
        "task_id":     "TRANSMISSION_FLUID",
        "title":       "Transmission Slipping Detected",
        "description": "Gear slip events logged by transmission ECU. "
                       "Fluid level and clutch pack integrity must be checked.",
        "priority":    "P1",
        "category":    "transmission",
        "auto_assign": "mechanic",
        "sla_hours":   8,
    },
    # ── Battery / Electrical ─────────────────────────────────────────
    "BATT_CRITICAL": {
        "task_id":     "BATT_CHECK",
        "title":       "Battery Voltage Critical",
        "description": "Battery voltage below 11.5V under load. "
                       "Alternator or battery replacement required.",
        "priority":    "P1",
        "category":    "electrical",
        "auto_assign": "mechanic",
        "sla_hours":   6,
    },
    # ── Tyres ────────────────────────────────────────────────────────
    "TYRE_PRESSURE": {
        "task_id":     "TYRE_ROTATION",
        "title":       "Critical Tyre Pressure Loss",
        "description": "TPMS sensor reports one or more tyres below safe pressure. "
                       "Risk of blowout. Inspect immediately.",
        "priority":    "P1",
        "category":    "tyres",
        "auto_assign": "mechanic",
        "sla_hours":   1,
    },
    # ── Generic / Catch-all ──────────────────────────────────────────
    "GENERIC_P1": {
        "task_id":     "INSPECTION",
        "title":       "Unclassified P1 Warning",
        "description": "A P1-severity diagnostic event was received from the telemetry "
                       "stream that does not match a known fault code. Manual inspection required.",
        "priority":    "P1",
        "category":    "general",
        "auto_assign": "mechanic",
        "sla_hours":   12,
    },
}

# ── Ticket Status Flow ────────────────────────────────────────────────────────
TICKET_STATUSES = ["open", "assigned", "in_progress", "resolved", "closed"]

# ── Odometer Warning Thresholds ───────────────────────────────────────────────
# How many km BEFORE the interval boundary do we issue a warning ticket?
ODOMETER_WARNING_KM = 500    # warn when within 500 km of next service
ODOMETER_OVERDUE_KM = 0      # 0 = exactly at boundary triggers overdue

# ── Age-Based Interval Multiplier ─────────────────────────────────────────────
# Older vehicles wear faster, so their km-based service intervals shrink.
# The multiplier is applied to every rule's interval_km at check time:
#
#   effective_interval_km = base_interval_km × multiplier
#
# A multiplier of 0.5 means the service is due at HALF the normal km gap,
# i.e. twice as frequently. The oldest bracket (> 10 yrs) triggers at 40%
# of the base interval — 2.5× more often than a brand-new vehicle.
#
# Format: list of (max_age_years, multiplier, label) — first match wins.
AGE_INTERVAL_MULTIPLIERS = [
    (3,   1.00, "New (0–3 yrs)         — full interval"),
    (6,   0.80, "Moderate (3–6 yrs)    — 20% shorter interval"),
    (10,  0.60, "Mature (6–10 yrs)     — 40% shorter interval"),
    (999, 0.40, "Veteran (> 10 yrs)    — 60% shorter interval"),
]

# The warning window also shrinks with age so owners get earlier notice
# on older vehicles. Expressed as km before the effective interval boundary.
AGE_WARNING_KM = [
    (3,   500,  "New"),
    (6,   400,  "Moderate"),
    (10,  300,  "Mature"),
    (999, 200,  "Veteran"),
]

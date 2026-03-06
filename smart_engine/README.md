# VehicleGuard — Smart Engine (Member 2)
**Round 2 → Round 3 Bridge**

Standalone background process. Runs two independent jobs that read from the
Round 2 database (`vehicles`, `telemetry_events`) and write into the Round 3
database (`tickets`, `maintenance_schedule`, `engine_run_log`).

---

## Quick Start

```bash
pip install -r requirements.txt
python scheduler.py          # starts both jobs
```

### Simulate P1 telemetry events (for testing)
```bash
python telemetry_simulator.py --reg TN01AB1234 --code ENG_OVERHEAT
python telemetry_simulator.py --all-codes          # all 9 event codes at once
python telemetry_simulator.py --stress 20          # 20 random events
```

### Run tests
```bash
pytest tests/test_smart_engine.py -v
```

---

## File Map

```
smart_engine/
├── scheduler.py            ← ENTRYPOINT — run this
├── engine_config.py        ← All thresholds, cron settings, P1 mappings, ticket templates
├── engine_db.py            ← All MongoDB reads/writes (tickets, telemetry, schedule ledger)
├── odometer_checker.py     ← Round 2→3 bridge: odometer vs maintenance_schedule
├── telemetry_listener.py   ← P1_WARNING stream → ticket injector
├── ticket_factory.py       ← Pure data: assembles formatted ticket documents
├── telemetry_simulator.py  ← Dev tool: push fake P1 events into the DB
├── requirements.txt
└── tests/
    └── test_smart_engine.py
```

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      ROUND 2 (Streamlit)                    │
│   vehicles.odometer_km ──────────────────────────────────┐  │
│   telemetry_events  {severity:"P1_WARNING", processed:F} │  │
└─────────────────────────────────────────────────────────────┘
                              │ MongoDB (same DB)
┌─────────────────────────────▼───────────────────────────────┐
│                     SMART ENGINE                            │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Job 1 — Odometer Check  (cron, hourly)              │  │
│  │                                                      │  │
│  │  for each vehicle × MAINTENANCE_SCHEDULE rule:       │  │
│  │    km_since_last = odometer − last_done_km           │  │
│  │    if >= interval_km      → OVERDUE ticket           │  │
│  │    if >= interval − 500km → DUE SOON ticket          │  │
│  │    (duplicate guard: skip if open ticket exists)     │  │
│  └──────────────────────────────────────────────────────┘  │
│                                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Job 2 — Telemetry Listener  (interval, every 30s)   │  │
│  │                                                      │  │
│  │  poll telemetry_events WHERE processed=false:        │  │
│  │    → resolve vehicle                                 │  │
│  │    → map event_code → P1_WARNING_MAP entry           │  │
│  │    → duplicate guard                                 │  │
│  │    → build_p1_ticket()                               │  │
│  │    → inject into tickets                             │  │
│  │    → mark event processed (with ticket_id backref)   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                              │ MongoDB (same DB)
┌─────────────────────────────▼───────────────────────────────┐
│                     ROUND 3 (Dashboard)                     │
│   tickets        { priority, status, sla_deadline, … }     │
│   maintenance_schedule  { vehicle_id, task_id, last_km }   │
│   engine_run_log        { run_type, summary, logged_at }   │
└─────────────────────────────────────────────────────────────┘
```

---

## Ticket Document Schema (Round 3 consumes this)

```json
{
  "ticket_number":   "TKT-20240310-143022",
  "source":          "odometer_check | telemetry_p1",
  "vehicle_id":      "...",
  "owner_id":        "...",
  "registration":    "TN01AB1234",
  "make":            "Toyota",
  "model":           "Innova",
  "task_id":         "BRAKE_FLUID",
  "category":        "brakes | engine | tyres | electrical | transmission | maintenance",
  "title":           "[P1] Brake Fluid Level Critical",
  "description":     "...",
  "parts_required":  ["Brake fluid (DOT4, 1L)"],
  "estimated_hrs":   1.5,
  "priority":        "P1 | P2 | P3",
  "overdue":         true,
  "sla_deadline":    "2024-03-10T16:30:22Z",
  "status":          "open | assigned | in_progress | resolved | closed",
  "auto_assign":     "mechanic",
  "assigned_to":     null,
  "history":         [{ "status": "open", "note": "...", "timestamp": "..." }],
  "odometer_context": { ... },   // only for source=odometer_check
  "telemetry_context":{ ... },   // only for source=telemetry_p1
  "created_at":      "...",
  "updated_at":      "..."
}
```

---

## Maintenance Schedule Rules

| Task ID           | Description                      | Every (km) | Priority |
|-------------------|----------------------------------|-----------|----------|
| OIL_CHANGE        | Engine Oil & Filter Change       | 5,000     | P2       |
| TYRE_ROTATION     | Tyre Rotation & Pressure Check   | 10,000    | P3       |
| AIR_FILTER        | Air Filter Replacement           | 15,000    | P2       |
| BRAKE_FLUID       | Brake Fluid Flush                | 20,000    | P1       |
| SPARK_PLUGS       | Spark Plug Replacement           | 30,000    | P2       |
| COOLANT_FLUSH     | Coolant System Flush             | 40,000    | P1       |
| BRAKE_PADS        | Brake Pad Replacement            | 40,000    | P1       |
| TRANSMISSION_FLUID| Transmission Fluid Change        | 60,000    | P2       |
| TIMING_BELT       | Timing Belt Inspection           | 80,000    | P1       |
| FULL_SERVICE      | Full Major Service (100k)        | 100,000   | P1       |

All rules and intervals configurable in `engine_config.py`.

---

## P1 Event Codes

| Code            | Title                        | SLA  | Category      |
|-----------------|------------------------------|------|---------------|
| ENG_OVERHEAT    | Engine Overheating           | 4h   | engine        |
| ENG_OIL_LOW     | Critical Engine Oil Level    | 2h   | engine        |
| ENG_MISFIRE     | Engine Misfire               | 8h   | engine        |
| BRAKE_FAIL      | Brake System Failure         | 1h   | brakes        |
| BRAKE_FLUID_LOW | Brake Fluid Critical         | 2h   | brakes        |
| TRANS_SLIP      | Transmission Slipping        | 8h   | transmission  |
| BATT_CRITICAL   | Battery Voltage Critical     | 6h   | electrical    |
| TYRE_PRESSURE   | Critical Tyre Pressure Loss  | 1h   | tyres         |
| GENERIC_P1      | Unclassified P1 Warning      | 12h  | general       |

New codes → add a mapping in `engine_config.P1_WARNING_MAP`. No other file changes needed.

---

## Integration Points for Other Members

### Round 2 (Streamlit app) — what to write:
Push a telemetry event when OBD/sensor fires:
```python
db.telemetry_events.insert_one({
    "vehicle_id":  "<vehicle_id_str>",
    "event_code":  "ENG_OVERHEAT",   # must match P1_WARNING_MAP key
    "severity":    "P1_WARNING",
    "payload":     {"engine_temp_c": 118, ...},
    "received_at": datetime.utcnow(),
    "processed":   False,
})
```

### Round 3 (Dashboard) — what to read:
```python
# Open tickets
db.tickets.find({"status": {"$in": ["open","assigned","in_progress"]}})

# Mark task done (resets km counter)
from odometer_checker import mark_task_completed
mark_task_completed(vehicle_id, task_id, completed_at_km)
```

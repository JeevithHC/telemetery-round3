# FleetSentinel
### Real-Time Vehicle Fleet Fault Detection & Maintenance Governance

> 100 vehicles. 35 sensors. 16 fault types. Zero tolerance for breakdowns.

---

## What This Is

FleetSentinel is a two-round system built for a Chennai fleet of 100 vehicles.

**Round 2** detects faults in real time — engine overheats, oil pressure drops, tyre blowouts, air brake failures — using a physics-based simulator feeding live telemetry into a multi-algorithm detection engine. Every alert is scored, classified, and surfaced on a live dashboard.

**Round 3** turns those alerts into action — maintenance tickets are auto-created, assigned to mechanics, approved by owners, and logged as immutable service history. Insurance auditors get a negligence report. Nothing gets ignored.

---

## Stack

| Layer | Technology |
|---|---|
| Simulator | Pure Python — physics model, fault injection, 1s tick |
| Detection Engine | Python — Kalman filters, Z-score, linear regression, thresholds |
| Round 2 API | FastAPI + in-memory alert store |
| Round 3 API | FastAPI + MongoDB + JWT auth |
| Frontend | Vanilla HTML/CSS/JS — zero dependencies, open in browser |
| Database | MongoDB |

---

## Project Structure

```
fleetsentinel/
├── simulator.py                 # 100-vehicle telemetry generator
├── vehicle_safety_system_v3.py  # core detection algorithms
├── simulator_bridge.py          # maps telemetry → detection engine
├── server.py                    # Round 2 API (no auth, in-memory)
├── main.py                      # Round 3 API (JWT auth, MongoDB)
├── fleetsentinal.html           # live dashboard
├── seed_db.py                   # run once — creates users + orgs
├── .env                         # mongo URI + JWT secret
└── db/
    ├── database.py              # MongoDB connection + helpers
    └── alert_ticket_bridge.py   # alert → maintenance ticket
```

---

## Prerequisites

**Install once:**
```bash
brew install mongodb-community     # macOS
pip install fastapi uvicorn pymongo python-jose bcrypt python-dotenv requests
```

---

## Running Round 2 (Fault Detection)

**Terminal 1 — API server:**
```bash
python server.py
```

**Terminal 2 — Simulator:**
```bash
python simulator.py
```

**Browser — Dashboard:**
```
Open fleetsentinal.html directly in your browser. No server needed.
```

**Verify it's working:**
```bash
curl http://localhost:8000/api/alerts
curl http://localhost:8000/api/stats
```

---

## Running Round 3 (Maintenance Governance)

**Step 1 — Start MongoDB:**
```bash
brew services start mongodb-community
```

**Step 2 — Seed the database (one time only):**
```bash
python seed_db.py
```

**Step 3 — Start the API:**
```bash
python main.py
```

**Step 4 — Get a token:**
```bash
curl -X POST http://localhost:8000/auth/login \
  -d "username=admin&password=admin123"
```

> `server.py` and `main.py` both run on port 8000. Run one at a time.

---

## Login Credentials

| Username | Password | Role | Access |
|---|---|---|---|
| `admin` | `admin123` | super_admin | Everything |
| `owner1` | `owner123` | owner | ORG-001 vehicles |
| `owner2` | `owner123` | owner | ORG-002 vehicles |
| `mechanic1` | `mech123` | mechanic | ORG-001 tickets |
| `mechanic2` | `mech123` | mechanic | ORG-001 tickets |
| `mechanic3` | `mech123` | mechanic | ORG-002 tickets |
| `insurance1` | `ins123` | insurance | Full audit access |

---

## API Reference

### Round 2 — `server.py`

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/telemetry` | Receives simulator payload |
| GET | `/api/alerts` | Returns latest alerts |
| GET | `/api/stats` | Fleet summary counts |

### Round 3 — `main.py`

| Method | Endpoint | Who |
|---|---|---|
| POST | `/auth/login` | Everyone |
| GET | `/api/tickets` | Scoped by role |
| POST | `/api/tickets` | Owner / Admin |
| PATCH | `/api/tickets/{id}/approve` | Owner |
| PATCH | `/api/tickets/{id}/assign` | Owner |
| PATCH | `/api/tickets/{id}/complete` | Mechanic |
| PATCH | `/api/tickets/{id}/delay` | Owner |
| GET | `/api/history/{vehicle_id}` | Owner / Mechanic |
| GET | `/api/audit/{vehicle_id}` | Insurance / Admin |
| GET | `/api/stats/owner` | Owner |
| GET | `/api/stats/mechanic` | Mechanic |

---

## Fleet

| Type | Count | Class | Unique Faults |
|---|---|---|---|
| SCOOTY | 10 | Two-Wheeler | Chain slip |
| BIKE | 10 | Two-Wheeler | Chain slip |
| CAR | 20 | Car | Brake wear |
| PICKUP | 10 | Car | Brake wear, turbo failure, overload |
| VAN | 15 | Car | Brake wear, turbo failure, overload |
| TRUCK | 20 | Heavy | Air brake loss, overload, high-PSI blowout |
| BUS | 15 | Heavy | Air brake loss, overload, high-PSI blowout |

---

## Fault Detection Methods

| Method | Catches |
|---|---|
| Hard threshold | Tyre blowout, overspeed, air brake loss |
| Linear regression | Oil pressure drop, coolant leak (gradual ramps) |
| Kalman filter | Engine temp, vibration, battery (noise reduction) |
| Z-score anomaly | Vibration spikes, battery failure, GPS drift |
| Rate-of-change | Fuel leak (drain rate vs expected) |
| Multi-field correlation | Engine overheat (temp + coolant together) |

---

## Alert Scoring

Every alert is scored 0–100:

```
score = threshold breach   (0–60)
      + sustained event    (0–30)
      + hard limit cross   (0–10)
      + statistical z-score(0–10)
```

| Score | Severity | Action |
|---|---|---|
| 71–100 | CRITICAL | Stop vehicle immediately |
| 31–70 | WARNING | Schedule inspection within 24h |
| 0–30 | LOG | Record for maintenance history |

---

## Ticket Lifecycle

```
Alert fires
    │
    ▼
Ticket auto-created (P0 = grounded, P1 = pending)
    │
    ▼
Owner approves
    │
    ▼
Mechanic assigned → in_progress
    │
    ▼
Mechanic completes → service history record created
                   → next service due date calculated
```

P0 tickets cannot be delayed. Ever.

---

## Negligence Flag (Insurance Audit)

A vehicle is flagged as negligent if:
- A CRITICAL alert fired and no ticket was created within 48 hours
- A ticket existed but sat unapproved for 7+ days

Available at `GET /api/audit/{vehicle_id}` — insurance role only.

---

## Stopping Everything

```bash
Ctrl + C                                  # stop any running server
brew services stop mongodb-community      # stop MongoDB
```

---

## Known Gaps

- Round 2 alert store is in-memory — restarting `server.py` clears all alerts
- `fleetsentinal.html` runs its own internal simulation — not yet wired to live API alerts
- No rate limiting on API endpoints
- JWT secret defaults to a placeholder — change it in `.env` before any real deployment

---

*Built for the Vehicle Telemetry Fault Detection hackathon. Chennai fleet. Two rounds. One system.*

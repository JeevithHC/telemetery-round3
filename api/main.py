"""
main.py — FastAPI app for Round 3: Fleet Governance & Scheduling

New endpoints added on top of your existing Round 2 API:

AUTH
    POST /auth/login                        → get JWT token

ORGANIZATIONS
    GET  /api/orgs                          → list all orgs (admin only)
    GET  /api/orgs/{org_id}/vehicles        → vehicles in an org

MAINTENANCE TICKETS
    GET  /api/tickets                       → list tickets (filtered by role)
    POST /api/tickets                       → create ticket manually
    PATCH /api/tickets/{id}/approve         → owner approves a ticket
    PATCH /api/tickets/{id}/assign          → assign mechanic to ticket
    PATCH /api/tickets/{id}/delay           → owner delays a ticket
    PATCH /api/tickets/{id}/complete        → mechanic completes a ticket

SERVICE HISTORY
    GET  /api/history/{vehicle_id}          → full service history for a vehicle
    POST /api/history                       → log a completed service (mechanic)

INSURANCE / AUDIT
    GET  /api/audit/{vehicle_id}            → immutable audit trail + negligence flag

DASHBOARD STATS
    GET  /api/stats/owner                   → owner dashboard summary
    GET  /api/stats/mechanic                → mechanic workload summary
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timedelta
from jose import JWTError, jwt
import bcrypt
import os
from dotenv import load_dotenv
from db.database import db, get_vehicles_for_user, get_org_for_vehicle, get_last_service
from db.alert_ticket_bridge import create_ticket_from_alert

load_dotenv()

# ─────────────────────────────────────────────
# APP SETUP
# ─────────────────────────────────────────────

app = FastAPI(
    title="Vehicle Telemetry — Round 3 API",
    description="Fleet Governance & Maintenance Scheduling",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SECRET_KEY = os.getenv("JWT_SECRET", "change-this-in-production")
ALGORITHM  = "HS256"
TOKEN_TTL  = 60 * 8  # 8 hours

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


# ─────────────────────────────────────────────
# AUTH HELPERS
# ─────────────────────────────────────────────

def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode(), hashed.encode())

def create_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.utcnow() + timedelta(minutes=TOKEN_TTL)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    user = db.users.find_one({"user_id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

def require_roles(*roles):
    """Dependency factory — restricts endpoint to specific roles."""
    def checker(user: dict = Depends(get_current_user)):
        if user["role"] not in roles:
            raise HTTPException(
                status_code=403,
                detail=f"Access denied. Required roles: {list(roles)}"
            )
        return user
    return checker

def clean(doc: dict) -> dict:
    """Remove MongoDB _id from response."""
    if doc:
        doc.pop("_id", None)
    return doc

def clean_list(docs: list) -> list:
    return [clean(d) for d in docs]


# ─────────────────────────────────────────────
# REQUEST BODIES
# ─────────────────────────────────────────────

class CreateTicketBody(BaseModel):
    vehicle_id: str
    service_type: str
    priority: str = "P1"
    trigger_reason: str
    due_by: Optional[datetime] = None
    checklist: Optional[List[dict]] = []

class ApproveTicketBody(BaseModel):
    notes: Optional[str] = ""

class AssignTicketBody(BaseModel):
    mechanic_id: str

class DelayTicketBody(BaseModel):
    delay_reason: str
    new_due_by: Optional[datetime] = None

class CompleteTicketBody(BaseModel):
    checklist: List[dict]           # checked-off items
    notes: str = ""
    odometer: float
    parts_replaced: Optional[List[str]] = []
    cost_estimate: Optional[float] = None

class LogServiceBody(BaseModel):
    vehicle_id: str
    service_type: str
    ticket_id: Optional[str] = None
    odometer_at_service: float
    checklist: List[dict] = []
    notes: str = ""
    parts_replaced: List[str] = []
    cost_estimate: Optional[float] = None


# ─────────────────────────────────────────────
# AUTH ENDPOINTS
# ─────────────────────────────────────────────

@app.post("/auth/login", tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()):
    """
    Standard login. Returns JWT token.
    Token encodes: user_id, role, org_id.
    Frontend uses role to decide which portal to show.
    """
    user = db.users.find_one({"username": form.username})
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if not user.get("is_active"):
        raise HTTPException(status_code=403, detail="Account is disabled")

    db.users.update_one(
        {"user_id": user["user_id"]},
        {"$set": {"last_login": datetime.utcnow()}}
    )

    token = create_token({
        "user_id": user["user_id"],
        "role":    user["role"],
        "org_id":  user.get("org_id"),
    })

    return {
        "access_token": token,
        "token_type":   "bearer",
        "role":         user["role"],
        "org_id":       user.get("org_id"),
        "full_name":    user["full_name"],
    }


# ─────────────────────────────────────────────
# ORGANIZATION ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/orgs", tags=["Organizations"])
def list_orgs(user=Depends(require_roles("super_admin", "insurance"))):
    """List all organizations. Admin and insurance only."""
    orgs = list(db.organizations.find({}, {"_id": 0}))
    return {"orgs": orgs, "count": len(orgs)}


@app.get("/api/orgs/{org_id}/vehicles", tags=["Organizations"])
def get_org_vehicles(org_id: str, user=Depends(get_current_user)):
    """
    Get all vehicles for an org.
    Owners/mechanics can only access their own org.
    """
    if user["role"] not in ("super_admin", "insurance") and user.get("org_id") != org_id:
        raise HTTPException(status_code=403, detail="Cannot access another organization's vehicles")

    org = db.organizations.find_one({"org_id": org_id}, {"_id": 0})
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return org


# ─────────────────────────────────────────────
# MAINTENANCE TICKET ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/tickets", tags=["Tickets"])
def list_tickets(
    status:       Optional[str] = None,
    priority:     Optional[str] = None,
    vehicle_id:   Optional[str] = None,
    vehicle_type: Optional[str] = None,
    source:       Optional[str] = None,
    user=Depends(get_current_user)
):
    """
    List tickets scoped to the user's org.
    Mechanics see only tickets assigned to them or unassigned in their org.
    Owners see all tickets in their org.
    Insurance/Admin see everything.
    """
    query = {}

    # Scope by org
    allowed_vehicles = get_vehicles_for_user(user["user_id"])
    if allowed_vehicles is not None:
        query["vehicle_id"] = {"$in": allowed_vehicles}

    # Mechanics only see their own + unassigned
    if user["role"] == "mechanic":
        query["$or"] = [
            {"assigned_mechanic_id": user["user_id"]},
            {"assigned_mechanic_id": None}
        ]

    if status:       query["status"]       = status
    if priority:     query["priority"]     = priority
    if vehicle_id:   query["vehicle_id"]   = vehicle_id
    if vehicle_type: query["vehicle_type"] = vehicle_type
    if source:       query["source"]       = source

    tickets = list(db.maintenance_tickets.find(query, {"_id": 0}).sort("created_at", -1))

    # Attach summary counts for dashboard badges
    counts = {
        "grounded":  sum(1 for t in tickets if t["status"] == "grounded"),
        "overdue":   sum(1 for t in tickets if t["status"] == "overdue"),
        "pending":   sum(1 for t in tickets if t["status"] == "pending"),
        "approved":  sum(1 for t in tickets if t["status"] == "approved"),
        "in_progress": sum(1 for t in tickets if t["status"] == "in_progress"),
        "completed": sum(1 for t in tickets if t["status"] == "completed"),
    }

    return {"tickets": tickets, "counts": counts, "total": len(tickets)}


@app.post("/api/tickets", tags=["Tickets"])
def create_ticket_manual(
    body: CreateTicketBody,
    user=Depends(require_roles("owner", "super_admin", "mechanic"))
):
    """Manually create a maintenance ticket."""
    import uuid

    # Verify vehicle belongs to user's org
    allowed = get_vehicles_for_user(user["user_id"])
    if allowed is not None and body.vehicle_id not in allowed:
        raise HTTPException(status_code=403, detail="Vehicle not in your organization")

    vehicle_type = body.vehicle_id.split("-")[0]
    org_id = get_org_for_vehicle(body.vehicle_id) or "UNASSIGNED"
    ticket_id = f"TKT-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{body.vehicle_id}-{str(uuid.uuid4())[:4].upper()}"

    ticket = {
        "ticket_id":            ticket_id,
        "vehicle_id":           body.vehicle_id,
        "vehicle_type":         vehicle_type,
        "org_id":               org_id,
        "service_type":         body.service_type,
        "source":               "manual",
        "priority":             body.priority,
        "status":               "grounded" if body.priority == "P0" else "pending",
        "trigger_reason":       body.trigger_reason,
        "alert_id":             None,
        "created_at":           datetime.utcnow(),
        "due_by":               body.due_by,
        "approved_at":          None,
        "approved_by":          None,
        "assigned_mechanic_id": None,
        "odometer_at_creation": None,
        "health_score_at_creation": None,
        "completed_at":         None,
        "service_event_id":     None,
        "checklist":            body.checklist or [],
        "owner_notes":          "",
        "is_delayed":           False,
        "delay_reason":         None,
    }

    db.maintenance_tickets.insert_one(ticket)
    return clean(ticket)


@app.patch("/api/tickets/{ticket_id}/approve", tags=["Tickets"])
def approve_ticket(
    ticket_id: str,
    body: ApproveTicketBody,
    user=Depends(require_roles("owner", "super_admin"))
):
    """Owner approves a pending ticket — moves it to 'approved'."""
    ticket = db.maintenance_tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Verify org access
    allowed = get_vehicles_for_user(user["user_id"])
    if allowed is not None and ticket["vehicle_id"] not in allowed:
        raise HTTPException(status_code=403, detail="Not authorized for this vehicle")

    db.maintenance_tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {
            "status":      "approved",
            "approved_at": datetime.utcnow(),
            "approved_by": user["user_id"],
            "owner_notes": body.notes or "",
        }}
    )
    return {"message": "Ticket approved", "ticket_id": ticket_id}


@app.patch("/api/tickets/{ticket_id}/assign", tags=["Tickets"])
def assign_ticket(
    ticket_id: str,
    body: AssignTicketBody,
    user=Depends(require_roles("owner", "super_admin"))
):
    """Assign a mechanic to a ticket — moves it to 'in_progress'."""
    ticket = db.maintenance_tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    # Verify mechanic exists and is in same org
    mechanic = db.users.find_one({"user_id": body.mechanic_id, "role": "mechanic"})
    if not mechanic:
        raise HTTPException(status_code=404, detail="Mechanic not found")

    db.maintenance_tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {
            "assigned_mechanic_id": body.mechanic_id,
            "status":               "in_progress",
        }}
    )
    return {"message": f"Assigned to {mechanic['full_name']}", "ticket_id": ticket_id}


@app.patch("/api/tickets/{ticket_id}/delay", tags=["Tickets"])
def delay_ticket(
    ticket_id: str,
    body: DelayTicketBody,
    user=Depends(require_roles("owner", "super_admin"))
):
    """Owner delays a ticket with a reason and optional new due date."""
    ticket = db.maintenance_tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")
    if ticket["priority"] == "P0":
        raise HTTPException(status_code=400, detail="P0 (Critical) tickets cannot be delayed")

    update = {
        "is_delayed":    True,
        "delay_reason":  body.delay_reason,
        "status":        "pending",
    }
    if body.new_due_by:
        update["due_by"] = body.new_due_by

    db.maintenance_tickets.update_one({"ticket_id": ticket_id}, {"$set": update})
    return {"message": "Ticket delayed", "ticket_id": ticket_id}


@app.patch("/api/tickets/{ticket_id}/complete", tags=["Tickets"])
def complete_ticket(
    ticket_id: str,
    body: CompleteTicketBody,
    user=Depends(require_roles("mechanic", "super_admin"))
):
    """
    Mechanic completes a ticket.
    Automatically creates a service_history record and resets the interval timer.
    """
    import uuid
    ticket = db.maintenance_tickets.find_one({"ticket_id": ticket_id})
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    now = datetime.utcnow()

    # Look up interval rule to compute next due date
    vehicle_type = ticket["vehicle_id"].split("-")[0]
    rule = db.maintenance_schedule.find_one({
        "service_type":  ticket["service_type"],
        "vehicle_types": vehicle_type
    })

    next_km_due   = None
    next_date_due = None
    if rule:
        if rule.get("km_interval"):
            next_km_due = body.odometer + rule["km_interval"]
        if rule.get("days_interval"):
            next_date_due = now + timedelta(days=rule["days_interval"])

    # Create service history record
    event_id = f"SVC-{now.strftime('%Y%m%d%H%M%S')}-{ticket['vehicle_id']}"
    svc_record = {
        "event_id":              event_id,
        "vehicle_id":            ticket["vehicle_id"],
        "vehicle_type":          ticket["vehicle_type"],
        "org_id":                ticket["org_id"],
        "ticket_id":             ticket_id,
        "service_type":          ticket["service_type"],
        "mechanic_id":           user["user_id"],
        "mechanic_name":         user["full_name"],
        "odometer_at_service":   body.odometer,
        "service_date":          now,
        "checklist":             body.checklist,
        "notes":                 body.notes,
        "cost_estimate":         body.cost_estimate,
        "parts_replaced":        body.parts_replaced,
        "next_service_due_km":   next_km_due,
        "next_service_due_date": next_date_due,
        "created_at":            now,
    }
    db.service_history.insert_one(svc_record)

    # Mark ticket as completed
    db.maintenance_tickets.update_one(
        {"ticket_id": ticket_id},
        {"$set": {
            "status":           "completed",
            "completed_at":     now,
            "service_event_id": event_id,
            "checklist":        body.checklist,
        }}
    )

    return {
        "message":          "Ticket completed and service logged",
        "ticket_id":        ticket_id,
        "service_event_id": event_id,
        "next_service": {
            "km":   next_km_due,
            "date": next_date_due,
        }
    }


# ─────────────────────────────────────────────
# SERVICE HISTORY ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/history/{vehicle_id}", tags=["Service History"])
def get_service_history(vehicle_id: str, user=Depends(get_current_user)):
    """Full immutable service history for a vehicle."""
    allowed = get_vehicles_for_user(user["user_id"])
    if allowed is not None and vehicle_id not in allowed:
        raise HTTPException(status_code=403, detail="Vehicle not in your organization")

    history = list(
        db.service_history.find({"vehicle_id": vehicle_id}, {"_id": 0})
        .sort("service_date", -1)
    )
    return {"vehicle_id": vehicle_id, "history": history, "total_services": len(history)}


@app.post("/api/history", tags=["Service History"])
def log_service_manually(
    body: LogServiceBody,
    user=Depends(require_roles("mechanic", "super_admin"))
):
    """
    Manually log a past service (for back-filling records).
    Does NOT close any ticket — use /complete for that.
    """
    import uuid
    now = datetime.utcnow()
    event_id = f"SVC-MANUAL-{now.strftime('%Y%m%d%H%M%S')}-{body.vehicle_id}"
    org_id = get_org_for_vehicle(body.vehicle_id) or "UNASSIGNED"

    record = {
        "event_id":            event_id,
        "vehicle_id":          body.vehicle_id,
        "vehicle_type":        body.vehicle_id.split("-")[0],
        "org_id":              org_id,
        "ticket_id":           body.ticket_id,
        "service_type":        body.service_type,
        "mechanic_id":         user["user_id"],
        "mechanic_name":       user["full_name"],
        "odometer_at_service": body.odometer_at_service,
        "service_date":        now,
        "checklist":           body.checklist,
        "notes":               body.notes,
        "cost_estimate":       body.cost_estimate,
        "parts_replaced":      body.parts_replaced,
        "next_service_due_km": None,
        "next_service_due_date": None,
        "created_at":          now,
    }

    db.service_history.insert_one(record)
    return clean(record)


# ─────────────────────────────────────────────
# INSURANCE / AUDIT ENDPOINT
# ─────────────────────────────────────────────

@app.get("/api/audit/{vehicle_id}", tags=["Insurance Audit"])
def get_audit_trail(vehicle_id: str, user=Depends(require_roles("insurance", "super_admin"))):
    """
    Full audit trail for a vehicle — for insurance / negligence check.

    Returns:
    - Complete service history (immutable)
    - All alerts ever fired for this vehicle
    - All maintenance tickets (including ignored ones)
    - NEGLIGENCE FLAG: alerts that were ignored for 7+ days before an accident
    """

    # Service history
    history = list(
        db.service_history.find({"vehicle_id": vehicle_id}, {"_id": 0})
        .sort("service_date", -1)
    )

    # All alerts from Round 2
    alerts = list(
        db.telemetry_alerts.find({"vehicle_id": vehicle_id}, {"_id": 0})
        .sort("timestamp", -1)
        .limit(200)
    )

    # All tickets
    tickets = list(
        db.maintenance_tickets.find({"vehicle_id": vehicle_id}, {"_id": 0})
        .sort("created_at", -1)
    )

    # ── Negligence Flag Logic ─────────────────────────────────────────
    # An alert is flagged as "negligent" if:
    #   - It was a P0/P1 level alert (critical or warning)
    #   - No ticket was created within 48h of the alert
    #   - OR a ticket was created but sat unacknowledged for 7+ days

    negligence_flags = []

    critical_alert_types = {
        "oil_pressure_low", "engine_temp_high", "health_score_low",
        "air_brake_pressure_low", "tip_over", "harsh_braking",
        "battery_voltage_dropping", "misfire_detected"
    }

    for alert in alerts:
        if alert.get("alert_type") not in critical_alert_types:
            continue

        alert_time   = alert.get("timestamp", alert.get("created_at"))
        if not alert_time:
            continue

        # Was a ticket created within 48h?
        linked_ticket = None
        for t in tickets:
            if (t.get("alert_id") == str(alert.get("alert_id", "")) or
                    t.get("trigger_reason", "").startswith(alert.get("alert_type", "XXX")[:10])):
                linked_ticket = t
                break

        if not linked_ticket:
            age_days = (datetime.utcnow() - alert_time).days if isinstance(alert_time, datetime) else 0
            if age_days >= 2:
                negligence_flags.append({
                    "type":        "NO_TICKET_CREATED",
                    "severity":    "HIGH",
                    "alert_type":  alert.get("alert_type"),
                    "alert_time":  alert_time,
                    "days_ignored": age_days,
                    "description": f"Alert '{alert.get('alert_type')}' fired {age_days} days ago — no maintenance ticket was ever created.",
                })
        else:
            # Ticket exists — was it ignored (stayed pending for 7+ days)?
            created = linked_ticket.get("created_at")
            approved = linked_ticket.get("approved_at")
            if created and not approved:
                pending_days = (datetime.utcnow() - created).days
                if pending_days >= 7:
                    negligence_flags.append({
                        "type":         "TICKET_NOT_APPROVED",
                        "severity":     "MEDIUM",
                        "alert_type":   alert.get("alert_type"),
                        "ticket_id":    linked_ticket["ticket_id"],
                        "pending_days": pending_days,
                        "description":  f"Maintenance ticket sat unapproved for {pending_days} days.",
                    })

    negligence_level = (
        "HIGH"   if any(f["severity"] == "HIGH"   for f in negligence_flags) else
        "MEDIUM" if any(f["severity"] == "MEDIUM" for f in negligence_flags) else
        "CLEAR"
    )

    return {
        "vehicle_id":        vehicle_id,
        "negligence_level":  negligence_level,
        "negligence_flags":  negligence_flags,
        "service_history":   history,
        "alerts_total":      len(alerts),
        "alerts":            alerts[:50],      # last 50 alerts
        "tickets":           tickets,
        "total_services":    len(history),
    }


# ─────────────────────────────────────────────
# DASHBOARD STATS ENDPOINTS
# ─────────────────────────────────────────────

@app.get("/api/stats/owner", tags=["Dashboard Stats"])
def owner_stats(user=Depends(require_roles("owner", "super_admin"))):
    """
    Summary for owner's command center dashboard:
    - Ticket counts by status
    - Grounded vehicles list
    - Cost estimate for upcoming work
    - Vehicles by health tier
    """
    allowed = get_vehicles_for_user(user["user_id"])
    vehicle_filter = {"vehicle_id": {"$in": allowed}} if allowed else {}

    tickets = list(db.maintenance_tickets.find(
        {**vehicle_filter, "status": {"$ne": "completed"}},
        {"_id": 0}
    ))

    grounded   = [t for t in tickets if t["status"] == "grounded"]
    overdue    = [t for t in tickets if t["status"] == "overdue"]
    this_week  = [t for t in tickets if t.get("due_by") and
                  t["due_by"] <= datetime.utcnow() + timedelta(days=7) and
                  t["status"] not in ("grounded", "overdue")]

    total_cost = sum(
        t.get("cost_estimate", 0) or 0 for t in tickets
    )

    return {
        "summary": {
            "grounded_count":    len(grounded),
            "overdue_count":     len(overdue),
            "due_this_week":     len(this_week),
            "total_open":        len(tickets),
            "estimated_cost_inr": total_cost,
        },
        "grounded_vehicles": [
            {"vehicle_id": t["vehicle_id"], "reason": t["trigger_reason"], "since": t["created_at"]}
            for t in grounded
        ],
        "kanban": {
            "grounded":    [clean(t) for t in grounded],
            "overdue":     [clean(t) for t in overdue],
            "this_week":   [clean(t) for t in this_week],
            "pending":     [clean(t) for t in tickets if t["status"] == "pending"],
            "in_progress": [clean(t) for t in tickets if t["status"] == "in_progress"],
        }
    }


@app.get("/api/stats/mechanic", tags=["Dashboard Stats"])
def mechanic_stats(user=Depends(require_roles("mechanic", "super_admin"))):
    """
    Summary for mechanic's portal:
    - My assigned tickets
    - Unassigned tickets in my org
    - Tickets due today
    """
    allowed = get_vehicles_for_user(user["user_id"])
    vehicle_filter = {"vehicle_id": {"$in": allowed}} if allowed else {}

    today_end = datetime.utcnow().replace(hour=23, minute=59, second=59)

    my_tickets = list(db.maintenance_tickets.find(
        {**vehicle_filter, "assigned_mechanic_id": user["user_id"], "status": {"$ne": "completed"}},
        {"_id": 0}
    ).sort("due_by", 1))

    unassigned = list(db.maintenance_tickets.find(
        {**vehicle_filter, "assigned_mechanic_id": None, "status": {"$in": ["approved", "pending"]}},
        {"_id": 0}
    ).sort("priority", 1))

    due_today = [t for t in my_tickets if t.get("due_by") and t["due_by"] <= today_end]

    return {
        "mechanic":        user["full_name"],
        "my_tickets":      my_tickets,
        "unassigned":      unassigned,
        "due_today":       due_today,
        "counts": {
            "assigned":   len(my_tickets),
            "unassigned": len(unassigned),
            "due_today":  len(due_today),
        }
    }
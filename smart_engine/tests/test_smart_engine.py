# =============================================================================
# smart_engine/tests/test_smart_engine.py
#
# Run with:  pytest tests/test_smart_engine.py -v
# =============================================================================

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from unittest.mock import MagicMock, patch
from datetime import datetime, timedelta
from bson import ObjectId

# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

def _make_vehicle(odometer_km=50_000, reg="TN01AB1234", purchase_date=None):
    return {
        "_id":                 ObjectId(),
        "owner_id":            "owner_001",
        "registration_number": reg,
        "make":                "Toyota",
        "model":               "Innova",
        "year":                2018,
        "purchase_date":       purchase_date or datetime(2018, 1, 1),
        "odometer_km":         odometer_km,
        "fuel_type":           "Diesel",
    }

def _make_p1_event(vehicle_id, event_code="ENG_OVERHEAT"):
    return {
        "_id":        ObjectId(),
        "vehicle_id": str(vehicle_id),
        "event_code": event_code,
        "severity":   "P1_WARNING",
        "payload":    {"engine_temp_c": 120, "coolant_level": "LOW"},
        "received_at":datetime.utcnow(),
        "processed":  False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# ticket_factory tests (pure, no DB)
# ─────────────────────────────────────────────────────────────────────────────

class TestTicketFactory:

    def test_build_odometer_ticket_overdue(self):
        from ticket_factory import build_odometer_ticket
        from engine_config import MAINTENANCE_SCHEDULE

        vehicle = _make_vehicle(odometer_km=56_000)
        rule    = next(r for r in MAINTENANCE_SCHEDULE if r["task_id"] == "OIL_CHANGE")

        ticket = build_odometer_ticket(
            vehicle      = vehicle,
            rule         = rule,
            current_km   = 56_000,
            last_done_km = 50_000,
            overdue      = True,
        )

        assert ticket["priority"]   == "P1"
        assert ticket["overdue"]    == True
        assert ticket["task_id"]    == "OIL_CHANGE"
        assert ticket["vehicle_id"] == str(vehicle["_id"])
        assert "[OVERDUE]" in ticket["title"]
        assert ticket["odometer_context"]["km_since_last"] == 6_000
        assert ticket["odometer_context"]["km_overdue"]    == 1_000
        assert ticket["status"]     == "open"
        assert ticket["source"]     == "odometer_check"
        assert "history" in ticket and len(ticket["history"]) == 1

    def test_build_odometer_ticket_due_soon(self):
        from ticket_factory import build_odometer_ticket
        from engine_config import MAINTENANCE_SCHEDULE

        vehicle = _make_vehicle(odometer_km=4_600)
        rule    = next(r for r in MAINTENANCE_SCHEDULE if r["task_id"] == "OIL_CHANGE")

        ticket = build_odometer_ticket(
            vehicle      = vehicle,
            rule         = rule,
            current_km   = 4_600,
            last_done_km = 0,
            overdue      = False,
        )

        assert "[DUE SOON]" in ticket["title"]
        assert ticket["overdue"]   == False
        assert ticket["priority"]  == "P2"  # OIL_CHANGE is P2 when not overdue

    def test_build_p1_ticket_known_code(self):
        from ticket_factory import build_p1_ticket

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"], "ENG_OVERHEAT")

        ticket = build_p1_ticket(vehicle=vehicle, event=event)

        assert ticket["priority"]  == "P1"
        assert ticket["source"]    == "telemetry_p1"
        assert ticket["task_id"]   == "COOLANT_FLUSH"
        assert ticket["category"]  == "engine"
        assert "[P1]" in ticket["title"]
        assert ticket["status"]    == "open"
        assert ticket["sla_deadline"] > datetime.utcnow()
        assert ticket["telemetry_context"]["event_code"] == "ENG_OVERHEAT"

    def test_build_p1_ticket_unknown_code_falls_back(self):
        from ticket_factory import build_p1_ticket

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"], "TOTALLY_MADE_UP_CODE")

        ticket = build_p1_ticket(vehicle=vehicle, event=event)

        assert ticket["task_id"]  == "INSPECTION"   # GENERIC_P1 fallback
        assert ticket["priority"] == "P1"

    def test_sla_deadline_is_in_future(self):
        from ticket_factory import build_p1_ticket

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"], "BRAKE_FAIL")
        ticket  = build_p1_ticket(vehicle=vehicle, event=event)

        assert ticket["sla_deadline"] > datetime.utcnow()

    def test_ticket_number_format(self):
        from ticket_factory import build_p1_ticket

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"])
        ticket  = build_p1_ticket(vehicle=vehicle, event=event)

        assert ticket["ticket_number"].startswith("TKT-")
        assert len(ticket["ticket_number"]) == 18  # TKT-YYYYMMDD-HHMMSS


# ─────────────────────────────────────────────────────────────────────────────
# odometer_checker tests (DB mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestOdometerChecker:

    @patch("odometer_checker.inject_ticket",     return_value="fake_ticket_id")
    @patch("odometer_checker.ticket_exists_open", return_value=False)
    @patch("odometer_checker.get_schedule_entry", return_value={"last_done_km": 0})
    @patch("odometer_checker.get_all_vehicles")
    @patch("odometer_checker.log_engine_run")
    def test_overdue_creates_ticket(self, mock_log, mock_vehicles,
                                    mock_entry, mock_exists, mock_inject):
        from odometer_checker import run_odometer_check

        # Vehicle with 6000 km — OIL_CHANGE (5000 km interval) is overdue
        mock_vehicles.return_value = [_make_vehicle(odometer_km=6_000)]
        summary = run_odometer_check()

        assert summary["tickets_created"] > 0
        mock_inject.assert_called()

    @patch("odometer_checker.inject_ticket",      return_value="fake_ticket_id")
    @patch("odometer_checker.ticket_exists_open", return_value=True)   # ← already open
    @patch("odometer_checker.get_schedule_entry", return_value={"last_done_km": 0})
    @patch("odometer_checker.get_all_vehicles")
    @patch("odometer_checker.log_engine_run")
    def test_duplicate_guard_skips_ticket(self, mock_log, mock_vehicles,
                                           mock_entry, mock_exists, mock_inject):
        from odometer_checker import run_odometer_check

        mock_vehicles.return_value = [_make_vehicle(odometer_km=6_000)]
        summary = run_odometer_check()

        assert summary["tickets_created"]   == 0
        assert summary["skipped_duplicate"] > 0
        mock_inject.assert_not_called()

    @patch("odometer_checker.inject_ticket",      return_value="fake_ticket_id")
    @patch("odometer_checker.ticket_exists_open", return_value=False)
    @patch("odometer_checker.get_schedule_entry", return_value={"last_done_km": 0})
    @patch("odometer_checker.get_all_vehicles")
    @patch("odometer_checker.log_engine_run")
    def test_low_odometer_no_tickets(self, mock_log, mock_vehicles,
                                      mock_entry, mock_exists, mock_inject):
        from odometer_checker import run_odometer_check

        # Only 100 km — nothing should be due
        mock_vehicles.return_value = [_make_vehicle(odometer_km=100)]
        summary = run_odometer_check()

        assert summary["tickets_created"] == 0
        mock_inject.assert_not_called()


# ─────────────────────────────────────────────────────────────────────────────
# telemetry_listener tests (DB mocked)
# ─────────────────────────────────────────────────────────────────────────────

class TestTelemetryListener:

    @patch("telemetry_listener.mark_event_processed")
    @patch("telemetry_listener.inject_ticket",      return_value="tkt_001")
    @patch("telemetry_listener.ticket_exists_open", return_value=False)
    @patch("telemetry_listener.get_vehicle")
    @patch("telemetry_listener.get_unprocessed_p1_events")
    @patch("telemetry_listener.log_engine_run")
    def test_p1_event_injects_ticket(self, mock_log, mock_events,
                                      mock_get_veh, mock_exists,
                                      mock_inject, mock_mark):
        from telemetry_listener import run_telemetry_check

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"], "ENG_OVERHEAT")

        mock_events.return_value  = [event]
        mock_get_veh.return_value = vehicle

        summary = run_telemetry_check()

        assert summary["tickets_created"] == 1
        assert summary["processed"]       == 1
        mock_inject.assert_called_once()
        mock_mark.assert_called_once_with(str(event["_id"]), ticket_id="tkt_001")

    @patch("telemetry_listener.mark_event_processed")
    @patch("telemetry_listener.inject_ticket",      return_value="tkt_002")
    @patch("telemetry_listener.ticket_exists_open", return_value=True)  # ← duplicate
    @patch("telemetry_listener.get_vehicle")
    @patch("telemetry_listener.get_unprocessed_p1_events")
    @patch("telemetry_listener.log_engine_run")
    def test_duplicate_p1_skipped(self, mock_log, mock_events,
                                   mock_get_veh, mock_exists,
                                   mock_inject, mock_mark):
        from telemetry_listener import run_telemetry_check

        vehicle = _make_vehicle()
        event   = _make_p1_event(vehicle["_id"], "ENG_OVERHEAT")
        mock_events.return_value  = [event]
        mock_get_veh.return_value = vehicle

        summary = run_telemetry_check()

        assert summary["tickets_created"] == 0
        assert summary["skipped_dup"]     == 1
        mock_inject.assert_not_called()

    @patch("telemetry_listener.mark_event_processed")
    @patch("telemetry_listener.get_vehicle",        return_value=None)  # ← missing vehicle
    @patch("telemetry_listener.get_unprocessed_p1_events")
    @patch("telemetry_listener.log_engine_run")
    def test_missing_vehicle_handled(self, mock_log, mock_events,
                                      mock_get_veh, mock_mark):
        from telemetry_listener import run_telemetry_check

        event = _make_p1_event("nonexistent_vehicle_id", "BRAKE_FAIL")
        mock_events.return_value = [event]

        summary = run_telemetry_check()

        assert summary["skipped_no_veh"] == 1
        assert summary["tickets_created"] == 0

    @patch("telemetry_listener.get_unprocessed_p1_events", return_value=[])
    @patch("telemetry_listener.log_engine_run")
    def test_no_events_returns_zero(self, mock_log, mock_events):
        from telemetry_listener import run_telemetry_check

        summary = run_telemetry_check()

        assert summary["events_found"]    == 0
        assert summary["tickets_created"] == 0


# ─────────────────────────────────────────────────────────────────────────────
# Age-based interval multiplier tests
# ─────────────────────────────────────────────────────────────────────────────

class TestAgeMultiplier:

    def test_new_vehicle_uses_full_interval(self):
        from odometer_checker import compute_effective_interval
        result = compute_effective_interval(5_000, age_years=1.0)
        assert result["multiplier"] == 1.00
        assert result["effective_interval_km"] == 5_000

    def test_moderate_age_shrinks_interval(self):
        from odometer_checker import compute_effective_interval
        result = compute_effective_interval(5_000, age_years=5.0)
        assert result["multiplier"] == 0.80
        assert result["effective_interval_km"] == 4_000   # 5000 × 0.80

    def test_mature_age_shrinks_interval_more(self):
        from odometer_checker import compute_effective_interval
        result = compute_effective_interval(5_000, age_years=8.0)
        assert result["multiplier"] == 0.60
        assert result["effective_interval_km"] == 3_000   # 5000 × 0.60

    def test_veteran_vehicle_uses_shortest_interval(self):
        from odometer_checker import compute_effective_interval
        result = compute_effective_interval(5_000, age_years=12.0)
        assert result["multiplier"] == 0.40
        assert result["effective_interval_km"] == 2_000   # 5000 × 0.40

    def test_effective_interval_never_below_floor(self):
        # Very small base interval on a very old car should not go below 200 km
        from odometer_checker import compute_effective_interval
        result = compute_effective_interval(400, age_years=15.0)
        assert result["effective_interval_km"] >= 200

    def test_older_vehicle_triggers_sooner_than_newer(self):
        # An old vehicle (12 yrs) at 2100 km since last service should be OVERDUE.
        # A new vehicle at the same km should NOT be overdue (base interval 5000 km).
        from odometer_checker import compute_effective_interval
        new_ctx = compute_effective_interval(5_000, age_years=1.0)   # effective = 5000
        old_ctx = compute_effective_interval(5_000, age_years=12.0)  # effective = 2000

        km_since_last = 2_100
        assert km_since_last < new_ctx["effective_interval_km"]   # new: NOT overdue
        assert km_since_last > old_ctx["effective_interval_km"]   # old: OVERDUE ✓

    def test_warning_km_shrinks_with_age(self):
        from odometer_checker import _get_warning_km
        assert _get_warning_km(1.0)  == 500   # new
        assert _get_warning_km(5.0)  == 400   # moderate
        assert _get_warning_km(8.0)  == 300   # mature
        assert _get_warning_km(12.0) == 200   # veteran

    def test_ticket_carries_age_context(self):
        from ticket_factory import build_odometer_ticket
        from odometer_checker import compute_effective_interval
        from engine_config import MAINTENANCE_SCHEDULE

        vehicle = _make_vehicle(odometer_km=3_000,
                                purchase_date=datetime.utcnow() - timedelta(days=365 * 12))
        rule    = next(r for r in MAINTENANCE_SCHEDULE if r["task_id"] == "OIL_CHANGE")
        age_ctx = compute_effective_interval(rule["interval_km"], age_years=12.0)

        ticket = build_odometer_ticket(
            vehicle=vehicle, rule=rule,
            current_km=3_000, last_done_km=0,
            overdue=True, age_ctx=age_ctx,
        )

        ctx = ticket["odometer_context"]
        assert ctx["vehicle_age_years"]     == 12.0
        assert ctx["interval_multiplier"]   == 0.40
        assert ctx["effective_interval_km"] == 2_000
        assert ctx["base_interval_km"]      == 5_000
        assert "60% reduction" in ticket["description"]

    @patch("odometer_checker.inject_ticket",     return_value="age_tkt")
    @patch("odometer_checker.ticket_exists_open", return_value=False)
    @patch("odometer_checker.get_schedule_entry", return_value={"last_done_km": 0})
    @patch("odometer_checker.get_all_vehicles")
    @patch("odometer_checker.log_engine_run")
    def test_old_vehicle_fires_ticket_at_reduced_km(
        self, mock_log, mock_vehicles, mock_entry, mock_exists, mock_inject
    ):
        from odometer_checker import run_odometer_check

        # 12-year-old vehicle at 2,100 km — OIL_CHANGE effective threshold is 2,000 km
        # so this should be OVERDUE even though 2100 < 5000 (base interval)
        old_vehicle = _make_vehicle(
            odometer_km=2_100,
            purchase_date=datetime.utcnow() - timedelta(days=365 * 12),
        )
        mock_vehicles.return_value = [old_vehicle]
        summary = run_odometer_check()

        assert summary["tickets_created"] > 0
        # Confirm at least one ticket log entry notes the multiplier
        oil_entries = [
            t for t in summary["ticket_log"] if t["task_id"] == "OIL_CHANGE"
        ]
        assert oil_entries, "Expected OIL_CHANGE ticket for old vehicle at 2100 km"
        assert oil_entries[0]["multiplier"] == 0.40

    @patch("odometer_checker.inject_ticket",     return_value="age_tkt_new")
    @patch("odometer_checker.ticket_exists_open", return_value=False)
    @patch("odometer_checker.get_schedule_entry", return_value={"last_done_km": 0})
    @patch("odometer_checker.get_all_vehicles")
    @patch("odometer_checker.log_engine_run")
    def test_new_vehicle_does_not_fire_at_same_km(
        self, mock_log, mock_vehicles, mock_entry, mock_exists, mock_inject
    ):
        from odometer_checker import run_odometer_check

        # Brand-new vehicle (1 yr old) at 2,100 km — OIL_CHANGE threshold is 5,000 km
        # so NOT due yet (2100 < 5000 - 500 warning)
        new_vehicle = _make_vehicle(
            odometer_km=2_100,
            purchase_date=datetime.utcnow() - timedelta(days=365 * 1),
        )
        mock_vehicles.return_value = [new_vehicle]
        summary = run_odometer_check()

        oil_entries = [
            t for t in summary["ticket_log"] if t["task_id"] == "OIL_CHANGE"
        ]
        assert not oil_entries, "New vehicle at 2100 km should NOT trigger OIL_CHANGE"


# ─────────────────────────────────────────────────────────────────────────────
# engine_config sanity checks
# ─────────────────────────────────────────────────────────────────────────────

class TestEngineConfig:

    def test_all_p1_codes_have_required_fields(self):
        from engine_config import P1_WARNING_MAP

        required = {"task_id","title","description","priority","category","auto_assign","sla_hours"}
        for code, mapping in P1_WARNING_MAP.items():
            missing = required - set(mapping.keys())
            assert not missing, f"P1_WARNING_MAP['{code}'] missing: {missing}"

    def test_maintenance_schedule_has_required_fields(self):
        from engine_config import MAINTENANCE_SCHEDULE

        required = {"task_id","description","interval_km","priority"}
        for rule in MAINTENANCE_SCHEDULE:
            missing = required - set(rule.keys())
            assert not missing, f"MAINTENANCE_SCHEDULE rule missing: {missing}"

    def test_intervals_are_positive(self):
        from engine_config import MAINTENANCE_SCHEDULE

        for rule in MAINTENANCE_SCHEDULE:
            assert rule["interval_km"] > 0, f"{rule['task_id']} interval must be > 0"

    def test_sla_hours_are_positive(self):
        from engine_config import P1_WARNING_MAP

        for code, m in P1_WARNING_MAP.items():
            assert m["sla_hours"] > 0, f"{code} sla_hours must be > 0"

    def test_age_multipliers_are_descending(self):
        from engine_config import AGE_INTERVAL_MULTIPLIERS
        multipliers = [m for _, m, _ in AGE_INTERVAL_MULTIPLIERS]
        assert multipliers == sorted(multipliers, reverse=True), \
            "Multipliers must decrease as vehicle gets older"

    def test_age_multipliers_all_between_zero_and_one(self):
        from engine_config import AGE_INTERVAL_MULTIPLIERS
        for _, m, _ in AGE_INTERVAL_MULTIPLIERS:
            assert 0 < m <= 1.0, f"Multiplier {m} out of range (0, 1]"

    def test_warning_km_are_positive(self):
        from engine_config import AGE_WARNING_KM
        for _, km, _ in AGE_WARNING_KM:
            assert km > 0

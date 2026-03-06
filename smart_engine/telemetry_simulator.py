# =============================================================================
# smart_engine/telemetry_simulator.py
#
# TEST UTILITY — simulates the IoT / OBD telemetry stream.
#
# Use this during development / demos to push fake P1_WARNING events
# into `telemetry_events` so the listener has something to process.
#
# Usage:
#   python telemetry_simulator.py --reg TN01AB1234 --code ENG_OVERHEAT
#   python telemetry_simulator.py --reg TN01AB1234 --code BRAKE_FAIL
#   python telemetry_simulator.py --all-codes        # one event per code
#   python telemetry_simulator.py --stress 50        # 50 random events
# =============================================================================

import argparse
import random
import sys
from datetime import datetime

from engine_config import P1_WARNING_MAP
from engine_db     import get_db, insert_telemetry_event, get_all_vehicles

# Fake sensor payloads per event code
_FAKE_PAYLOADS = {
    "ENG_OVERHEAT":    {"engine_temp_c": 118, "coolant_level": "LOW",  "fan_status": "ON"},
    "ENG_OIL_LOW":     {"oil_pressure_bar": 0.4, "oil_level_pct": 8,    "temp_c": 95},
    "ENG_MISFIRE":     {"misfire_count": 47, "rpm": 1800, "cylinders_affected": [2, 4]},
    "BRAKE_FAIL":      {"brake_pressure_bar": 0.1, "abs_status": "FAULT","pedal_travel_mm": 95},
    "BRAKE_FLUID_LOW": {"fluid_level_pct": 12, "reservoir": "MIN_LINE"},
    "TRANS_SLIP":      {"slip_events": 8, "fluid_temp_c": 105, "gear": 3},
    "BATT_CRITICAL":   {"voltage_v": 11.2, "current_a": -15, "soc_pct": 18},
    "TYRE_PRESSURE":   {"fl_psi": 12, "fr_psi": 32, "rl_psi": 31, "rr_psi": 32},
    "GENERIC_P1":      {"raw_dtc": "U0100", "ecu": "BODY_CTRL"},
}


def _resolve_vehicle(reg: str | None):
    vehicles = get_all_vehicles()
    if not vehicles:
        print("ERROR: No vehicles found in the database.")
        sys.exit(1)
    if reg:
        match = next((v for v in vehicles
                      if v["registration_number"].upper() == reg.upper()), None)
        if not match:
            print(f"ERROR: Vehicle '{reg}' not found.")
            sys.exit(1)
        return match
    return random.choice(vehicles)


def push_event(vehicle_id: str, event_code: str, extra_payload: dict = None) -> str:
    payload = dict(_FAKE_PAYLOADS.get(event_code, {}))
    if extra_payload:
        payload.update(extra_payload)
    event = {
        "vehicle_id":  vehicle_id,
        "event_code":  event_code,
        "severity":    "P1_WARNING",
        "payload":     payload,
        "received_at": datetime.utcnow(),
        "processed":   False,
        "source":      "simulator",
    }
    eid = insert_telemetry_event(event)
    return eid


def main():
    parser = argparse.ArgumentParser(description="VehicleGuard Telemetry Simulator")
    parser.add_argument("--reg",        help="Vehicle registration number (e.g. TN01AB1234)")
    parser.add_argument("--code",       help=f"Event code. Choices: {list(P1_WARNING_MAP.keys())}")
    parser.add_argument("--all-codes",  action="store_true", help="Push one event per known code")
    parser.add_argument("--stress",     type=int, metavar="N", help="Push N random events")
    args = parser.parse_args()

    all_codes = list(P1_WARNING_MAP.keys())

    if args.all_codes:
        vehicle = _resolve_vehicle(args.reg)
        vid = str(vehicle["_id"])
        reg = vehicle["registration_number"]
        print(f"Pushing all {len(all_codes)} event codes for {reg}…")
        for code in all_codes:
            eid = push_event(vid, code)
            print(f"  ✓ {code:20s} → event_id={eid}")
        print("Done.")

    elif args.stress:
        vehicles = get_all_vehicles()
        if not vehicles:
            print("No vehicles found.")
            sys.exit(1)
        print(f"Stress test: pushing {args.stress} random events…")
        for i in range(args.stress):
            v    = random.choice(vehicles)
            code = random.choice(all_codes)
            eid  = push_event(str(v["_id"]), code)
            print(f"  [{i+1:3d}] {v['registration_number']:12s} {code:20s} → {eid}")
        print("Done.")

    elif args.code:
        if args.code not in P1_WARNING_MAP:
            print(f"Unknown code '{args.code}'. Valid codes: {all_codes}")
            sys.exit(1)
        vehicle = _resolve_vehicle(args.reg)
        vid     = str(vehicle["_id"])
        reg     = vehicle["registration_number"]
        eid     = push_event(vid, args.code)
        print(f"✓ Event pushed — vehicle={reg} code={args.code} event_id={eid}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()

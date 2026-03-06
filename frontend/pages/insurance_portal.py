"""pages/insurance_portal.py — Insurance audit portal using mock data."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mock_data as md
from datetime import datetime

NEG_COLORS = {"HIGH":"#ef4444","MEDIUM":"#f97316","CLEAR":"#4ade80"}
NEG_BG     = {"HIGH":"rgba(239,68,68,0.1)","MEDIUM":"rgba(249,115,22,0.1)","CLEAR":"rgba(74,222,128,0.1)"}

STYLES = """
<style>
.portal-title { font-family:'Space Mono',monospace; font-size:1.6rem; font-weight:700; color:#f1f5f9; }
.portal-sub   { color:#64748b; font-size:0.9rem; margin-bottom:2rem; }
.neg-banner   { border-radius:12px; padding:1.25rem 1.5rem; margin-bottom:1.5rem; }
.flag-card    { background:#1e293b; border-radius:8px; padding:0.85rem 1rem;
                margin-bottom:0.6rem; border-left:3px solid #f97316; }
.svc-row      { background:#111827; border:1px solid #1e293b; border-radius:8px;
                padding:0.75rem 1rem; margin-bottom:0.5rem; }
.divider      { border:none; border-top:1px solid #1e293b; margin:1.5rem 0; }
</style>
"""

# All available vehicle IDs for hint
ALL_VEHICLES = (
    [f"TRUCK-{i:03d}" for i in range(1,21)] +
    [f"BUS-{i:03d}" for i in range(1,16)] +
    [f"CAR-{i:03d}" for i in range(1,21)] +
    [f"VAN-{i:03d}" for i in range(1,16)] +
    [f"BIKE-{i:03d}" for i in range(1,11)] +
    [f"SCOOTY-{i:03d}" for i in range(1,11)] +
    [f"PICKUP-{i:03d}" for i in range(1,11)]
)

def render():
    st.markdown(STYLES, unsafe_allow_html=True)
    st.markdown("""
    <div class="portal-title">🔍 Insurance Audit Portal</div>
    <div class="portal-sub">Enter a Vehicle ID to view its full audit trail and negligence assessment.</div>
    """, unsafe_allow_html=True)

    sc1, sc2 = st.columns([3,1])
    with sc1:
        vehicle_id = st.text_input("Vehicle ID",
            placeholder="e.g. TRUCK-004, BUS-007, CAR-008",
            label_visibility="collapsed")
    with sc2:
        search = st.button("🔍 Audit", use_container_width=True)

    # Show hint buttons for vehicles that have rich mock data
    st.markdown("**Try these vehicles with full data:**")
    hc1,hc2,hc3 = st.columns(3)
    if hc1.button("🚛 TRUCK-004 (Negligence: HIGH)"):
        st.session_state["audit_vid"] = "TRUCK-004"
    if hc2.button("🚌 BUS-007 (Negligence: HIGH)"):
        st.session_state["audit_vid"] = "BUS-007"
    if hc3.button("🚗 CAR-008 (Negligence: CLEAR)"):
        st.session_state["audit_vid"] = "CAR-008"

    # Use button shortcut or typed value
    vid_to_use = st.session_state.get("audit_vid") or (vehicle_id.strip().upper() if search and vehicle_id else None)

    if not vid_to_use:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#475569;">
            <div style="font-size:3rem;margin-bottom:1rem">🔎</div>
            <div>Enter a Vehicle ID or click a quick-access button above.</div>
        </div>""", unsafe_allow_html=True)
        return

    # Clear shortcut after use
    if "audit_vid" in st.session_state:
        del st.session_state["audit_vid"]

    data = md.get_audit(vid_to_use)

    neg_level = data["negligence_level"]
    neg_flags = data["negligence_flags"]
    history   = data["service_history"]
    tickets   = data["tickets"]
    alerts    = data["alerts"]
    color     = NEG_COLORS[neg_level]
    bg        = NEG_BG[neg_level]
    icons     = {"HIGH":"🚨","MEDIUM":"⚠️","CLEAR":"✅"}

    st.markdown(f"""
    <div class="neg-banner" style="background:{bg};border:1px solid {color}40;">
        <div style="font-size:1.5rem;font-weight:700;color:{color}">
            {icons[neg_level]} Negligence Assessment: {neg_level}
        </div>
        <div style="font-size:0.8rem;color:{color}99;margin-top:0.2rem;">
            Vehicle ID: {vid_to_use} — {len(neg_flags)} flag(s) found
        </div>
    </div>
    """, unsafe_allow_html=True)

    c1,c2,c3,c4 = st.columns(4)
    c1.metric("Total Services",   data["total_services"])
    c2.metric("Total Alerts",     data["alerts_total"])
    c3.metric("Total Tickets",    len(tickets))
    c4.metric("Negligence Flags", len(neg_flags))

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    tab1,tab2,tab3,tab4 = st.tabs([
        f"🚨 Flags ({len(neg_flags)})",
        f"🔧 Service History ({len(history)})",
        f"🎫 Tickets ({len(tickets)})",
        f"⚠️ Alerts ({len(alerts)})",
    ])

    with tab1:
        if not neg_flags:
            st.success("✅ No negligence flags. Maintenance appears compliant.")
        else:
            for flag in neg_flags:
                sev   = flag.get("severity","MEDIUM")
                fcol  = "#ef4444" if sev=="HIGH" else "#f97316"
                st.markdown(f"""
                <div class="flag-card" style="border-left-color:{fcol}">
                    <div style="font-weight:600;color:{fcol}">
                        {'🚨' if sev=='HIGH' else '⚠️'} {flag.get('type','').replace('_',' ')} — {sev}
                    </div>
                    <div style="color:#cbd5e1;margin-top:0.4rem;font-size:0.875rem">{flag.get('description','')}</div>
                    <div style="color:#64748b;font-size:0.8rem;margin-top:0.3rem">
                        Alert: {flag.get('alert_type','')} | Days ignored: {flag.get('days_ignored','N/A')}
                    </div>
                </div>""", unsafe_allow_html=True)

    with tab2:
        if not history:
            st.info("No service records found. Try TRUCK-004 or BUS-007 for full history.")
        else:
            for svc in history:
                date = svc.get("service_date","")
                try: date = datetime.fromisoformat(date).strftime("%d %b %Y")
                except: pass
                parts = ", ".join(svc.get("parts_replaced",[])) or "None"
                st.markdown(f"""
                <div class="svc-row">
                    <div style="display:flex;justify-content:space-between;align-items:start">
                        <div>
                            <div style="font-weight:600;color:#f1f5f9">{svc.get('service_type','')}</div>
                            <div style="color:#94a3b8;font-size:0.82rem;margin-top:0.2rem">
                                Mechanic: {svc.get('mechanic_name','')} |
                                Odometer: {svc.get('odometer_at_service',0):,} km |
                                Cost: ₹{svc.get('cost_estimate',0):,}
                            </div>
                            <div style="color:#64748b;font-size:0.8rem;margin-top:0.2rem">Parts: {parts}</div>
                            {f"<div style='color:#64748b;font-size:0.8rem'>{svc.get('notes','')}</div>" if svc.get('notes') else ''}
                        </div>
                        <div style="color:#64748b;font-size:0.8rem;white-space:nowrap">{date}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

    with tab3:
        if not tickets:
            st.info("No tickets found for this vehicle.")
        else:
            for t in tickets:
                status = t.get("status","")
                p      = t.get("priority","P2")
                scol   = {"grounded":"#ef4444","overdue":"#f97316","completed":"#4ade80"}.get(status,"#94a3b8")
                created = t.get("created_at","")
                try: created = datetime.fromisoformat(created).strftime("%d %b %Y")
                except: pass
                with st.expander(f"[{p}] {t.get('service_type','')} — {status} ({created})"):
                    st.markdown(f"**Trigger:** {t.get('trigger_reason','')}")
                    st.markdown(f"**Source:** {t.get('source','')} | **Status:** <span style='color:{scol}'>{status}</span>", unsafe_allow_html=True)

    with tab4:
        if not alerts:
            st.info("No alerts found. Try TRUCK-004 or BUS-007.")
        else:
            for a in alerts:
                ts = a.get("timestamp","")
                try: ts = datetime.fromisoformat(ts).strftime("%d %b %Y %H:%M")
                except: pass
                resolved = "✅ Resolved" if a.get("resolved") else "🔴 Active"
                sev_col  = "#ef4444" if "critical" in a.get("severity","") else "#f97316"
                st.markdown(f"""
                <div class="svc-row">
                    <div style="display:flex;justify-content:space-between">
                        <div>
                            <span style="font-weight:500;color:{sev_col}">{a.get('alert_type','')}</span>
                            <span style="color:#94a3b8;font-size:0.82rem;margin-left:0.75rem">{a.get('message','')}</span>
                        </div>
                        <div style="display:flex;gap:0.75rem;align-items:center">
                            <span style="color:#64748b;font-size:0.8rem">{resolved}</span>
                            <span style="color:#64748b;font-size:0.8rem">{ts}</span>
                        </div>
                    </div>
                </div>""", unsafe_allow_html=True)

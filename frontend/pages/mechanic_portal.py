"""pages/mechanic_portal.py — Mechanic portal using mock data."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mock_data as md
from datetime import datetime

PRIORITY_COLORS = {"P0":"#ef4444","P1":"#f97316","P2":"#38bdf8","P3":"#94a3b8"}

STYLES = """
<style>
.portal-title { font-family:'Space Mono',monospace; font-size:1.6rem; font-weight:700; color:#f1f5f9; }
.portal-sub   { color:#64748b; font-size:0.9rem; margin-bottom:2rem; }
.stat-card    { background:#111827; border:1px solid #1e293b; border-radius:12px; padding:1.25rem; text-align:center; }
.stat-value   { font-size:2rem; font-weight:700; }
.stat-label   { color:#64748b; font-size:0.75rem; text-transform:uppercase; letter-spacing:0.08em; margin-top:0.25rem; }
.divider      { border:none; border-top:1px solid #1e293b; margin:1.5rem 0; }
</style>
"""

def render():
    st.markdown(STYLES, unsafe_allow_html=True)
    stats = md.get_mechanic_stats()

    st.markdown(f"""
    <div class="portal-title">🔧 Mechanic Portal</div>
    <div class="portal-sub">Welcome, {stats['mechanic']} — {datetime.now().strftime('%A, %d %b %Y')}</div>
    """, unsafe_allow_html=True)

    counts = stats["counts"]
    c1,c2,c3 = st.columns(3)
    for col,val,label,color in [
        (c1, counts["assigned"],   "My Tickets",  "#38bdf8"),
        (c2, counts["due_today"],  "Due Today",   "#ef4444"),
        (c3, counts["unassigned"], "Unassigned",  "#fbbf24"),
    ]:
        col.markdown(f'<div class="stat-card"><div class="stat-value" style="color:{color}">{val}</div><div class="stat-label">{label}</div></div>', unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    tab1, tab2 = st.tabs(["📋 My Tickets", "🆕 Unassigned Tickets"])

    with tab1:
        tickets = stats["my_tickets"]
        if not tickets:
            st.info("No tickets assigned to you yet.")
        else:
            for t in tickets:
                _ticket_card(t, show_complete=True)

    with tab2:
        tickets = stats["unassigned"]
        if not tickets:
            st.info("No unassigned tickets.")
        else:
            for t in tickets:
                _ticket_card(t, show_complete=False)


def _ticket_card(t, show_complete):
    p      = t.get("priority","P2")
    p_col  = PRIORITY_COLORS.get(p,"#94a3b8")
    status = t.get("status","")
    due    = t.get("due_by","")
    try: due = datetime.fromisoformat(due).strftime("%d %b %H:%M")
    except: due = ""

    emoji = "🚨" if p=="P0" else "⚠️" if p=="P1" else "🔵"
    with st.expander(f"{emoji} {t['vehicle_id']} — {t['service_type']}  [{p}]  |  {status}"):
        c1,c2 = st.columns(2)
        c1.markdown(f"**Vehicle:** {t['vehicle_id']} ({t.get('vehicle_type','')})")
        c2.markdown(f"**Due:** {due or 'Not set'}")
        c1.markdown(f"**Priority:** <span style='color:{p_col}'>{p}</span>", unsafe_allow_html=True)
        c2.markdown(f"**Source:** {t.get('source','')}")
        st.markdown(f"**Reason:** {t.get('trigger_reason','')}")

        checklist = t.get("checklist",[])
        if checklist:
            st.markdown("**Checklist:**")
            for i, item in enumerate(checklist):
                st.checkbox(item["item"], value=item.get("completed",False),
                            key=f"chk_{t['ticket_id']}_{i}")

        if show_complete and status in ("approved","in_progress","grounded","open","overdue","pending"):
            st.markdown("---")
            st.markdown("**Complete this ticket:**")
            fc1,fc2 = st.columns(2)
            odometer = fc1.number_input("Current Odometer (km)", min_value=0.0, step=100.0, key=f"odo_{t['ticket_id']}")
            cost     = fc2.number_input("Cost Estimate (₹)",     min_value=0.0, step=100.0, key=f"cost_{t['ticket_id']}")
            notes    = st.text_area("Notes / Parts replaced", key=f"notes_{t['ticket_id']}", height=80)
            if st.button("✅ Mark Complete (Demo)", key=f"complete_{t['ticket_id']}"):
                if odometer == 0:
                    st.warning("Please enter the current odometer reading.")
                else:
                    st.success(f"✅ Ticket marked complete! (Demo mode — no DB write)")
                    st.balloons()

        elif not show_complete:
            if st.button("📥 Assign to me (Demo)", key=f"assign_{t['ticket_id']}"):
                st.success("Assigned! (Demo mode — no DB write)")

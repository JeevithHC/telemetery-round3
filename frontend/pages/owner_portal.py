"""pages/owner_portal.py — Owner portal using mock data."""
import streamlit as st
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
import mock_data as md
from datetime import datetime

PRIORITY_COLORS = {"P0":"#ef4444","P1":"#f97316","P2":"#38bdf8","P3":"#94a3b8"}
STATUS_COLORS   = {"grounded":"#ef4444","overdue":"#f97316","pending":"#fbbf24",
                   "approved":"#38bdf8","in_progress":"#a78bfa","completed":"#4ade80"}

STYLES = """
<style>
.portal-title { font-family:'Space Mono',monospace; font-size:1.6rem; font-weight:700;
    color:#f1f5f9; margin-bottom:0.25rem; }
.portal-sub { color:#64748b; font-size:0.9rem; margin-bottom:2rem; }
.stat-card { background:#111827; border:1px solid #1e293b; border-radius:12px; padding:1.25rem 1.5rem; }
.stat-value { font-size:2.2rem; font-weight:700; line-height:1; }
.stat-label { color:#64748b; font-size:0.8rem; text-transform:uppercase; letter-spacing:0.08em; margin-top:0.3rem; }
.kanban-col { background:#111827; border:1px solid #1e293b; border-radius:12px; padding:1rem; }
.kanban-header { font-size:0.78rem; font-weight:600; text-transform:uppercase; letter-spacing:0.1em;
    margin-bottom:0.75rem; padding-bottom:0.5rem; border-bottom:1px solid #1e293b; }
.ticket-card { background:#1e293b; border-radius:8px; padding:0.85rem; margin-bottom:0.6rem; border-left:3px solid #334155; }
.ticket-vehicle { font-weight:600; font-size:0.9rem; color:#f1f5f9; }
.ticket-service { font-size:0.8rem; color:#94a3b8; margin-top:0.15rem; }
.ticket-meta { display:flex; gap:0.5rem; margin-top:0.5rem; flex-wrap:wrap; }
.badge { padding:0.15rem 0.5rem; border-radius:4px; font-size:0.7rem; font-weight:600; }
.divider { border:none; border-top:1px solid #1e293b; margin:1.5rem 0; }
</style>
"""

def render():
    st.markdown(STYLES, unsafe_allow_html=True)
    stats   = md.get_owner_stats()
    t_data  = md.get_tickets()
    summary = stats["summary"]
    kanban  = stats["kanban"]

    st.markdown(f"""
    <div class="portal-title">🏢 Owner Command Center</div>
    <div class="portal-sub">Chennai Metro Logistics — {datetime.now().strftime('%A, %d %b %Y')}</div>
    """, unsafe_allow_html=True)

    # ── Stat Cards ──────────────────────────────────────────────────
    c1,c2,c3,c4,c5 = st.columns(5)
    def stat(col, val, label, color):
        col.markdown(f'<div class="stat-card"><div class="stat-value" style="color:{color}">{val}</div><div class="stat-label">{label}</div></div>', unsafe_allow_html=True)

    stat(c1, summary["grounded_count"],                     "Grounded",      "#ef4444")
    stat(c2, summary["overdue_count"],                      "Overdue",       "#f97316")
    stat(c3, summary["due_this_week"],                      "Due This Week", "#fbbf24")
    stat(c4, summary["total_open"],                         "Total Open",    "#38bdf8")
    stat(c5, f"₹{summary['estimated_cost_inr']:,.0f}",      "Est. Cost",     "#4ade80")

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Grounded Alert ───────────────────────────────────────────────
    grounded = stats["grounded_vehicles"]
    if grounded:
        st.markdown("### 🚨 Grounded Vehicles — Immediate Action Required")
        for g in grounded:
            st.markdown(f"""
            <div class="ticket-card" style="border-left-color:#ef4444;background:#1f0f0f;">
                <div class="ticket-vehicle">⛔ {g['vehicle_id']}</div>
                <div class="ticket-service">{g['reason']}</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Kanban ───────────────────────────────────────────────────────
    st.markdown("### 📋 Maintenance Kanban Board")
    cols = st.columns(4)
    kanban_defs = [
        ("🔴 Grounded",    "#ef4444", kanban["grounded"]),
        ("🟠 Overdue",     "#f97316", kanban["overdue"]),
        ("🟡 Pending",     "#fbbf24", kanban["this_week"]),
        ("🟣 In Progress", "#a78bfa", kanban["in_progress"]),
    ]
    for col, (title, color, tickets) in zip(cols, kanban_defs):
        with col:
            st.markdown(f'<div class="kanban-col"><div class="kanban-header" style="color:{color}">{title} ({len(tickets)})</div>', unsafe_allow_html=True)
            if not tickets:
                st.markdown('<p style="color:#475569;font-size:0.8rem;text-align:center;padding:1rem 0">All clear ✓</p>', unsafe_allow_html=True)
            else:
                for t in tickets[:6]:
                    p      = t.get("priority","P2")
                    p_col  = PRIORITY_COLORS.get(p,"#94a3b8")
                    due    = t.get("due_by","")
                    try: due = datetime.fromisoformat(due).strftime("%d %b")
                    except: due = ""
                    st.markdown(f"""
                    <div class="ticket-card" style="border-left-color:{p_col}">
                        <div class="ticket-vehicle">{t['vehicle_id']}</div>
                        <div class="ticket-service">{t['service_type']}</div>
                        <div class="ticket-meta">
                            <span class="badge" style="background:{p_col}22;color:{p_col}">{p}</span>
                            <span class="badge" style="background:#1e293b;color:#94a3b8">{t.get('source','')}</span>
                            {f'<span style="color:#64748b;font-size:0.7rem">due {due}</span>' if due else ''}
                        </div>
                    </div>""", unsafe_allow_html=True)
            st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("<hr class='divider'>", unsafe_allow_html=True)

    # ── Full Ticket Table ────────────────────────────────────────────
    st.markdown("### 📄 All Tickets")
    all_tickets = t_data["tickets"]

    fc1, fc2 = st.columns(2)
    f_priority = fc1.selectbox("Priority", ["All","P0","P1","P2"], key="f_pri")
    f_status   = fc2.selectbox("Status",   ["All","grounded","overdue","pending","in_progress"], key="f_sta")

    filtered = [t for t in all_tickets if
                (f_priority=="All" or t.get("priority")==f_priority) and
                (f_status=="All"   or t.get("status")==f_status)]

    for t in filtered:
        p     = t.get("priority","P2")
        p_col = PRIORITY_COLORS.get(p,"#94a3b8")
        s     = t.get("status","")
        s_col = STATUS_COLORS.get(s,"#94a3b8")
        with st.expander(f"🚗 {t['vehicle_id']} — {t['service_type']}  [{p}]  |  {s}"):
            a,b,c = st.columns(3)
            a.markdown(f"**Status:** <span style='color:{s_col}'>{s}</span>", unsafe_allow_html=True)
            b.markdown(f"**Source:** {t.get('source','')}")
            c.markdown(f"**Type:** {t.get('vehicle_type','')}")
            st.markdown(f"**Reason:** {t.get('trigger_reason','')}")
            checklist = t.get("checklist",[])
            if checklist:
                st.markdown("**Checklist:**")
                for item in checklist:
                    icon = "✅" if item.get("completed") else "⬜"
                    st.markdown(f"&nbsp;&nbsp;{icon} {item['item']}")
            if s in ("pending","overdue","grounded"):
                if st.button("✅ Approve (Demo)", key=f"approve_{t['ticket_id']}"):
                    st.success("Approved! (Demo mode — no DB write)")

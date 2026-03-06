"""
app.py — Main entrypoint. Uses mock data (no API required).
Run: streamlit run app.py
"""

import streamlit as st

st.set_page_config(
    page_title="VehicleGuard — Fleet Governance",
    page_icon="🚗",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@300;400;500;600&display=swap');
*, *::before, *::after { box-sizing: border-box; }
html, body, [data-testid="stAppViewContainer"] {
    background: #0a0e1a !important; color: #e2e8f0 !important;
    font-family: 'DM Sans', sans-serif !important;
}
[data-testid="stAppViewContainer"] > .main { background: #0a0e1a !important; }
#MainMenu, footer, header { visibility: hidden; }
[data-testid="stSidebar"] { display: none; }
[data-testid="stDecoration"] { display: none; }
.login-logo { font-family:'Space Mono',monospace; font-size:1.1rem; font-weight:700;
    color:#38bdf8; letter-spacing:0.15em; text-transform:uppercase; margin-bottom:0.25rem; }
.login-title { font-size:2rem; font-weight:600; color:#f1f5f9; margin-bottom:0.5rem; line-height:1.2; }
.login-sub { color:#64748b; font-size:0.9rem; margin-bottom:2rem; }
.stTextInput > div > div > input {
    background:#1e293b !important; border:1px solid #334155 !important;
    border-radius:8px !important; color:#f1f5f9 !important;
    font-size:0.95rem !important; padding:0.75rem 1rem !important;
}
.stTextInput > div > div > input:focus { border-color:#38bdf8 !important; }
.stTextInput label { color:#94a3b8 !important; font-size:0.85rem !important; }
.stButton > button {
    width:100% !important; background:#38bdf8 !important; color:#0a0e1a !important;
    border:none !important; border-radius:8px !important; font-weight:600 !important;
    padding:0.75rem 1.5rem !important;
}
.role-grid { display:grid; grid-template-columns:1fr 1fr; gap:0.75rem; margin-bottom:2rem; }
.role-card { background:#1e293b; border:1px solid #334155; border-radius:10px;
             padding:0.85rem 1rem; text-align:center; }
.role-card .icon { font-size:1.5rem; margin-bottom:0.25rem; }
.role-card .label { font-size:0.78rem; color:#94a3b8; font-weight:500;
                    text-transform:uppercase; letter-spacing:0.05em; }
.role-card .user { font-size:0.82rem; color:#cbd5e1; margin-top:0.1rem; }
.login-error { background:rgba(239,68,68,0.1); border:1px solid rgba(239,68,68,0.3);
    border-radius:8px; color:#fca5a5; padding:0.75rem 1rem; font-size:0.875rem; margin-top:1rem; }
.nav-bar { background:#111827; border-bottom:1px solid #1e293b; padding:0.75rem 2rem;
    display:flex; align-items:center; justify-content:space-between; margin-bottom:2rem; }
.nav-brand { font-family:'Space Mono',monospace; font-size:0.9rem; font-weight:700;
    color:#38bdf8; letter-spacing:0.12em; text-transform:uppercase; }
.nav-role-badge { padding:0.25rem 0.75rem; border-radius:999px;
    font-size:0.75rem; font-weight:600; text-transform:uppercase; }
.role-mechanic    { background:rgba(34,197,94,0.15);  color:#4ade80; border:1px solid rgba(34,197,94,0.3); }
.role-owner       { background:rgba(56,189,248,0.15); color:#38bdf8; border:1px solid rgba(56,189,248,0.3); }
.role-insurance   { background:rgba(251,191,36,0.15); color:#fbbf24; border:1px solid rgba(251,191,36,0.3); }
.role-super_admin { background:rgba(168,85,247,0.15); color:#c084fc; border:1px solid rgba(168,85,247,0.3); }
.nav-username { color:#94a3b8; font-size:0.875rem; }
.demo-banner { background:rgba(251,191,36,0.08); border:1px solid rgba(251,191,36,0.25);
    border-radius:8px; padding:0.5rem 1rem; margin-bottom:1.5rem;
    color:#fbbf24; font-size:0.82rem; text-align:center; }
</style>
""", unsafe_allow_html=True)

MOCK_USERS = {
    "admin":        {"password": "admin123",  "role": "super_admin", "full_name": "Super Admin",        "org_id": None},
    "mechanic_raj": {"password": "mech123",   "role": "mechanic",    "full_name": "Rajesh Kumar",        "org_id": "ORG-001"},
    "owner_cml":    {"password": "owner123",  "role": "owner",       "full_name": "Chennai Metro Fleet", "org_id": "ORG-001"},
    "auditor_lic":  {"password": "audit123",  "role": "insurance",   "full_name": "LIC Auditor",         "org_id": None},
}

def init_session():
    for k, v in {"role":None,"org_id":None,"full_name":None,"username":None,"logged_in":False}.items():
        if k not in st.session_state:
            st.session_state[k] = v

init_session()

def logout():
    for k in ["role","org_id","full_name","username","logged_in"]:
        st.session_state[k] = None
    st.session_state.logged_in = False
    st.rerun()

def render_nav():
    role = st.session_state.role or ""
    name = st.session_state.full_name or ""
    icon = {"mechanic":"🔧","owner":"🏢","insurance":"🔍","super_admin":"⚡"}.get(role,"👤")
    st.markdown(f"""
    <div class="nav-bar">
        <div class="nav-brand">⬡ VehicleGuard</div>
        <div style="display:flex;align-items:center;gap:1rem;">
            <span class="nav-username">{icon} {name}</span>
            <span class="nav-role-badge role-{role}">{role.replace('_',' ')}</span>
        </div>
    </div>""", unsafe_allow_html=True)
    _, _, col3 = st.columns([8, 1, 1])
    with col3:
        if st.button("Logout", key="nav_logout"):
            logout()
    st.markdown('<div class="demo-banner">⚡ Demo Mode — showing realistic mock data</div>',
                unsafe_allow_html=True)

def render_login():
    st.markdown("""
    <div style="max-width:440px; margin:4rem auto 0 auto;">
        <div class="login-logo">⬡ VehicleGuard</div>
        <div class="login-title">Fleet Governance<br>& Scheduling</div>
        <div class="login-sub">Round 3 — Maintenance Management System</div>
    </div>
    <div style="max-width:440px; margin:0 auto 1.5rem auto;">
        <p style="color:#64748b;font-size:0.8rem;margin-bottom:0.75rem;text-transform:uppercase;letter-spacing:0.08em;">Quick fill credentials</p>
        <div class="role-grid">
            <div class="role-card"><div class="icon">🔧</div><div class="label">Mechanic</div><div class="user">mechanic_raj / mech123</div></div>
            <div class="role-card"><div class="icon">🏢</div><div class="label">Owner</div><div class="user">owner_cml / owner123</div></div>
            <div class="role-card"><div class="icon">🔍</div><div class="label">Insurance</div><div class="user">auditor_lic / audit123</div></div>
            <div class="role-card"><div class="icon">⚡</div><div class="label">Super Admin</div><div class="user">admin / admin123</div></div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    _, col_form, _ = st.columns([1, 2, 1])
    with col_form:
        username = st.text_input("Username", placeholder="Enter your username", key="login_user")
        password = st.text_input("Password", placeholder="Enter your password", type="password", key="login_pass")
        st.markdown("<div style='height:0.5rem'></div>", unsafe_allow_html=True)
        if st.button("Sign In →", key="login_btn"):
            if not username or not password:
                st.markdown('<div class="login-error">⚠️ Please enter both username and password.</div>', unsafe_allow_html=True)
            elif username in MOCK_USERS and MOCK_USERS[username]["password"] == password:
                u = MOCK_USERS[username]
                st.session_state.role      = u["role"]
                st.session_state.org_id    = u["org_id"]
                st.session_state.full_name = u["full_name"]
                st.session_state.username  = username
                st.session_state.logged_in = True
                st.rerun()
            else:
                st.markdown('<div class="login-error">❌ Invalid username or password.</div>', unsafe_allow_html=True)

def route_to_portal():
    render_nav()
    role = st.session_state.role
    if role == "mechanic":
        from pages import mechanic_portal; mechanic_portal.render()
    elif role in ("owner", "super_admin"):
        from pages import owner_portal; owner_portal.render()
    elif role == "insurance":
        from pages import insurance_portal; insurance_portal.render()
    else:
        st.error(f"Unknown role: {role}")

if not st.session_state.logged_in:
    render_login()
else:
    route_to_portal()

import streamlit as st


def apply_global_theme():
    st.markdown(
        """
<style>
:root {
    --mp-bg-1: #020617;
    --mp-bg-2: #0b1220;
    --mp-bg-3: #0f172a;
    --mp-text: #f8fafc;
    --mp-text-soft: #cbd5e1;
    --mp-placeholder: #94a3b8;
    --mp-blue: #3b82f6;
    --mp-blue-soft: #93c5fd;
    --mp-gold: #d4af37;
}

html, body, [class*="css"] {
    font-family: "Inter", "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    letter-spacing: 0.005em;
}

.stApp {
    background: radial-gradient(980px 420px at 14% -8%, rgba(59,130,246,0.22) 0%, rgba(2,6,23,0) 60%),
                linear-gradient(180deg, var(--mp-bg-1) 0%, var(--mp-bg-2) 56%, var(--mp-bg-3) 100%);
    color: var(--mp-text);
}

h1, h2, h3 {
    color: #ffffff !important;
    font-weight: 700 !important;
    line-height: 1.2 !important;
}

h4, h5 {
    color: #ffffff !important;
    font-weight: 700 !important;
}

p, li, label, .stMarkdown {
    line-height: 1.55;
    color: var(--mp-text) !important;
}

p, li, .stCaption, small {
    color: var(--mp-text-soft) !important;
}

label, .stTextInput label, .stTextArea label, .stSelectbox label {
    color: var(--mp-text) !important;
    font-weight: 600 !important;
}

[data-testid="stSidebar"] {
    background: linear-gradient(180deg, rgba(15,23,42,0.95), rgba(2,6,23,0.98));
    border-right: 1px solid rgba(148,163,184,0.18);
}

[data-testid="stSidebar"] * {
    color: var(--mp-text);
}

[data-testid="stMetric"] {
    background: rgba(30,41,59,0.82);
    border: 1px solid rgba(147,197,253,0.30);
    border-radius: 14px;
    padding: 0.65rem 0.75rem;
    transition: transform 0.18s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

[data-testid="stMetricLabel"] {
    color: #cbd5e1 !important;
}

[data-testid="stMetricValue"] {
    color: #f8fafc !important;
    font-weight: 800 !important;
}

[data-testid="stMetric"]:hover {
    transform: translateY(-2px);
    border-color: rgba(147,197,253,0.50);
    box-shadow: 0 10px 24px rgba(2,6,23,0.35), 0 0 24px rgba(59,130,246,0.14);
}

.stTextInput > div > div > input,
.stTextArea textarea,
.stSelectbox > div > div,
.stDateInput > div > div,
.stNumberInput input {
    background: #0f172a !important;
    color: #ffffff !important;
    border: 1px solid #334155 !important;
    border-radius: 12px !important;
    transition: border-color 0.2s ease, box-shadow 0.2s ease;
}

.stTextInput > div > div > input::placeholder,
.stTextArea textarea::placeholder,
.stNumberInput input::placeholder {
    color: var(--mp-placeholder) !important;
    opacity: 1;
}

.stTextInput > div > div > input:focus,
.stTextArea textarea:focus,
.stNumberInput input:focus {
    border-color: #60a5fa !important;
    box-shadow: 0 0 0 1px rgba(59,130,246,0.25), 0 0 18px rgba(59,130,246,0.14);
}

.stSelectbox > div > div:hover,
.stDateInput > div > div:hover {
    border-color: #60a5fa !important;
}

/* BaseWeb select/dropdown consistency for dark theme */
div[data-baseweb="select"] > div {
    background: #0f172a !important;
    color: #ffffff !important;
    border: 1px solid #334155 !important;
}

div[data-baseweb="popover"] ul,
div[data-baseweb="popover"] li,
div[data-baseweb="select"] * {
    color: #ffffff !important;
}

div[data-baseweb="menu"] {
    background: #0f172a !important;
    border: 1px solid #334155 !important;
}

.stButton > button,
.stDownloadButton > button {
    border-radius: 12px !important;
    border: 1px solid rgba(147,197,253,0.45) !important;
    background: linear-gradient(135deg, #2563eb, #1d4ed8) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    transition: transform 0.16s ease, box-shadow 0.2s ease, filter 0.2s ease !important;
}

.stButton > button:hover,
.stDownloadButton > button:hover {
    transform: translateY(-1px);
    box-shadow: 0 12px 24px rgba(29,78,216,0.35), 0 0 18px rgba(96,165,250,0.24);
    filter: brightness(1.04);
    border-color: #60a5fa !important;
}

.stButton > button:active,
.stDownloadButton > button:active {
    transform: translateY(1px) scale(0.99);
}

.stButton > button[kind="secondary"] {
    background: rgba(30,41,59,0.65) !important;
}

.dpia-report-card {
    border: 1px solid rgba(147,197,253,0.30);
    border-radius: 14px;
    background: rgba(15,23,42,0.88);
    padding: 1rem 1.05rem;
    margin-bottom: 0.85rem;
    box-shadow: 0 0 0 1px rgba(59,130,246,0.08), 0 10px 26px rgba(2,6,23,0.35);
    color: var(--mp-text);
    transition: transform 0.2s ease, box-shadow 0.2s ease, border-color 0.2s ease;
}

.dpia-report-card:hover,
.mp-empty-state:hover {
    transform: translateY(-2px);
    border-color: rgba(96,165,250,0.4);
    box-shadow: 0 0 0 1px rgba(59,130,246,0.14), 0 12px 28px rgba(2,6,23,0.36), 0 0 24px rgba(59,130,246,0.16);
}

.mp-empty-state {
    border: 1px solid rgba(147,197,253,0.30);
    border-radius: 14px;
    background: rgba(15,23,42,0.88);
    padding: 0.85rem 1rem;
    margin: 0.55rem 0;
    color: var(--mp-text);
}

[data-testid="stAlert"] {
    border-radius: 12px;
    border: 1px solid rgba(148,163,184,0.25);
    background: rgba(15,23,42,0.82);
    color: var(--mp-text);
}

[data-testid="stSpinner"] {
    border-radius: 12px;
    border: 1px solid rgba(59,130,246,0.24);
    background: rgba(15,23,42,0.78);
    padding: 0.45rem 0.65rem;
    animation: mpFadeIn 0.24s ease;
}

.stApp * {
    animation-duration: 0.001s;
}

.mp-gold-accent {
    color: var(--mp-gold);
}

.mp-cred-strip {
    margin-top: 0.55rem;
    padding: 0.45rem 0.65rem;
    border-radius: 999px;
    border: 1px solid rgba(212,175,55,0.34);
    background: rgba(30,41,59,0.62);
    color: #e2e8f0;
    font-size: 0.78rem;
    font-weight: 700;
    display: inline-block;
}

@keyframes mpFadeIn {
    from { opacity: 0.5; transform: translateY(2px); }
    to { opacity: 1; transform: translateY(0px); }
}
</style>
""",
        unsafe_allow_html=True,
    )

    try:
        from ui import admin_views

        uid = st.session_state.get("user_id")
        email = None
        if uid is not None:
            from banco import obter_email_usuario

            email = obter_email_usuario(uid)
        admin_views.apply_sidebar_admin_visibility(email, uid)
    except Exception:
        pass

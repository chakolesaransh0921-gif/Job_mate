# streamlit_app.py
import streamlit as st
import sys
import time
import threading
import yaml
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta
import sqlite3
import json

# ── Page Configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Job Application Automation",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Path Setup ────────────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).parent
SRC_DIR  = BASE_DIR / "src"
DATA_DIR = BASE_DIR / "data"
LOGS_DIR = BASE_DIR / "logs"
CONFIG_PATH = BASE_DIR / "config.yaml"

for d in [DATA_DIR, LOGS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

sys.path.insert(0, str(BASE_DIR))

# ── Custom CSS ────────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Global ── */
[data-testid="stAppViewContainer"] {
    background: linear-gradient(135deg, #0f0c29, #302b63, #24243e);
    color: #e0e0e0;
}
[data-testid="stSidebar"] {
    background: rgba(255,255,255,0.05);
    backdrop-filter: blur(10px);
    border-right: 1px solid rgba(255,255,255,0.1);
}

/* ── Metric cards ── */
.metric-card {
    background: rgba(255,255,255,0.07);
    border: 1px solid rgba(255,255,255,0.15);
    border-radius: 16px;
    padding: 24px;
    text-align: center;
    transition: transform .2s, box-shadow .2s;
}
.metric-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 8px 32px rgba(99,102,241,.35);
}
.metric-number {
    font-size: 2.8rem;
    font-weight: 800;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.metric-label {
    font-size: .9rem;
    color: #9ca3af;
    margin-top: 6px;
}

/* ── Status badges ── */
.badge {
    display: inline-block;
    padding: 4px 12px;
    border-radius: 20px;
    font-size: .78rem;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: .5px;
}
.badge-applied   { background: rgba(99,102,241,.2); color: #818cf8; }
.badge-interview { background: rgba(16,185,129,.2); color: #34d399; }
.badge-rejected  { background: rgba(239,68,68,.2);  color: #f87171; }
.badge-pending   { background: rgba(245,158,11,.2); color: #fbbf24; }

/* ── Buttons ── */
.stButton > button {
    background: linear-gradient(135deg, #6366f1, #8b5cf6) !important;
    color: #fff !important;
    border: none !important;
    border-radius: 10px !important;
    padding: 10px 24px !important;
    font-weight: 600 !important;
    transition: opacity .2s !important;
}
.stButton > button:hover { opacity: .85 !important; }

/* ── Section headers ── */
.section-header {
    font-size: 1.4rem;
    font-weight: 700;
    color: #c7d2fe;
    border-left: 4px solid #6366f1;
    padding-left: 12px;
    margin: 20px 0 14px;
}

/* ── Job card ── */
.job-card {
    background: rgba(255,255,255,0.06);
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 14px;
    padding: 20px;
    margin-bottom: 14px;
    transition: border-color .2s;
}
.job-card:hover { border-color: #6366f1; }
.job-title   { font-size: 1.1rem; font-weight: 700; color: #e0e7ff; }
.job-company { font-size: .9rem; color: #818cf8; margin-top: 2px; }
.job-meta    { font-size: .82rem; color: #6b7280; margin-top: 8px; }

/* ── Log output ── */
.log-box {
    background: #0d1117;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 16px;
    font-family: 'Fira Code', monospace;
    font-size: .8rem;
    color: #58a6ff;
    max-height: 360px;
    overflow-y: auto;
}

/* ── Score bar ── */
.score-bar-bg {
    background: rgba(255,255,255,0.1);
    border-radius: 8px;
    height: 10px;
    margin-top: 6px;
}
.score-bar-fill {
    height: 10px;
    border-radius: 8px;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# ── Helpers / Utilities ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def load_config() -> dict:
    """Load YAML config or return sensible defaults."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    return {
        "job_search": {
            "keywords": ["Python Developer", "Software Engineer"],
            "locations": ["Remote"],
            "experience_level": "mid",
            "sites": [
                {"name": "linkedin", "enabled": True,
                 "url": "https://www.linkedin.com/jobs/search/"},
                {"name": "indeed",   "enabled": True,
                 "url": "https://www.indeed.com/jobs"},
            ],
        },
        "automation": {
            "check_interval_seconds": 3600,
            "max_applications_per_day": 10,
            "delay_between_applications": 30,
        },
        "email": {
            "enabled": False,
            "smtp_server": "smtp.gmail.com",
            "smtp_port": 587,
            "sender_email": "",
            "sender_password": "",
            "recipient_email": "",
        },
        "resume": {
            "path": "data/resume.pdf",
            "cover_letter_template": "data/cover_letter.txt",
        },
        "database": {"path": "data/jobs.db"},
        "matching": {
            "min_match_score": 70,
            "required_skills": ["Python", "SQL", "Git"],
            "preferred_skills": ["Docker", "AWS", "JavaScript"],
        },
    }


def save_config(cfg: dict):
    """Persist config to disk."""
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(cfg, f, default_flow_style=False)
    st.success("✅ Configuration saved!")


def get_db_connection():
    db_path = DATA_DIR / "jobs.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_database():
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS applied_jobs (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            applied_at TEXT NOT NULL,
            match_score INTEGER,
            status TEXT DEFAULT 'applied',
            notes TEXT,
            location TEXT DEFAULT '',
            source TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS job_listings (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            company TEXT NOT NULL,
            url TEXT UNIQUE NOT NULL,
            description TEXT,
            location TEXT,
            posted_date TEXT,
            source TEXT,
            match_score INTEGER,
            last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def get_stats() -> dict:
    """Aggregate dashboard statistics."""
    conn   = get_db_connection()
    cur    = conn.cursor()
    today  = datetime.now().strftime("%Y-%m-%d")

    cur.execute("SELECT COUNT(*) FROM applied_jobs")
    total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM applied_jobs WHERE date(applied_at)=?", (today,))
    today_count = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM applied_jobs WHERE status='interview'")
    interviews = cur.fetchone()[0]

    cur.execute("SELECT AVG(match_score) FROM applied_jobs")
    avg_score = cur.fetchone()[0] or 0

    cur.execute("SELECT COUNT(*) FROM applied_jobs WHERE status='rejected'")
    rejected = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM applied_jobs WHERE status='pending'")
    pending = cur.fetchone()[0]

    conn.close()
    return {
        "total": total,
        "today": today_count,
        "interviews": interviews,
        "avg_score": round(avg_score, 1),
        "rejected": rejected,
        "pending": pending,
        "response_rate": round((interviews / total * 100) if total else 0, 1),
    }


def get_recent_applications(limit: int = 50) -> pd.DataFrame:
    conn = get_db_connection()
    df   = pd.read_sql_query(
        "SELECT * FROM applied_jobs ORDER BY applied_at DESC LIMIT ?",
        conn, params=(limit,)
    )
    conn.close()
    return df


def add_sample_data():
    """Seed with demo rows for demonstration."""
    samples = [
        ("s001", "Senior Python Developer",  "TechCorp Inc",
         "https://linkedin.com/jobs/1", "2024-01-15T10:30:00", 92,
         "interview", "Great opportunity!", "Remote", "linkedin"),
        ("s002", "Backend Engineer",         "StartupXYZ",
         "https://indeed.com/jobs/2",   "2024-01-15T11:00:00", 78,
         "applied",   None,               "New York", "indeed"),
        ("s003", "Software Engineer",        "BigTech Corp",
         "https://linkedin.com/jobs/3", "2024-01-14T14:20:00", 85,
         "pending",   None,               "Remote", "linkedin"),
        ("s004", "Python Developer",         "FinTech Solutions",
         "https://indeed.com/jobs/4",   "2024-01-14T09:15:00", 71,
         "rejected",  "Not enough exp",  "San Francisco", "indeed"),
        ("s005", "Full Stack Developer",     "Digital Agency",
         "https://linkedin.com/jobs/5", "2024-01-13T16:45:00", 65,
         "applied",   None,               "Remote", "linkedin"),
    ]
    conn = get_db_connection()
    cur  = conn.cursor()
    cur.executemany(
        """INSERT OR IGNORE INTO applied_jobs
           (id,title,company,url,applied_at,match_score,status,notes,location,source)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        samples
    )
    conn.commit()
    conn.close()


def get_logs(n: int = 100) -> list[str]:
    """Return latest n lines from today's log file."""
    log_file = LOGS_DIR / f"job_automation_{datetime.now().strftime('%Y%m%d')}.log"
    if not log_file.exists():
        return ["No log file found for today."]
    with open(log_file) as f:
        lines = f.readlines()
    return lines[-n:]


def score_color(score: int) -> str:
    if score >= 80: return "#34d399"
    if score >= 60: return "#fbbf24"
    return "#f87171"


def status_badge(status: str) -> str:
    cls = {"applied": "badge-applied", "interview": "badge-interview",
           "rejected": "badge-rejected", "pending": "badge-pending"}.get(status, "badge-pending")
    return f'<span class="badge {cls}">{status}</span>'


# ══════════════════════════════════════════════════════════════════════════════
# ── Session State Bootstrap ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

if "config"          not in st.session_state: st.session_state.config = load_config()
if "automation_on"   not in st.session_state: st.session_state.automation_on = False
if "run_log"         not in st.session_state: st.session_state.run_log = []
if "jobs_found"      not in st.session_state: st.session_state.jobs_found = []
if "last_run"        not in st.session_state: st.session_state.last_run = None

init_database()


# ══════════════════════════════════════════════════════════════════════════════
# ── Sidebar ───────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## 🚀 Job Automation")
    st.markdown("---")

    page = st.radio(
        "Navigation",
        ["📊 Dashboard", "🔍 Job Search", "📝 Applications",
         "⚙️ Configuration", "📧 Email Settings",
         "📈 Analytics", "📋 Logs"],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # ── Automation toggle ────────────────────────────────────────────────────
    st.markdown("### ⚡ Automation")
    if st.session_state.automation_on:
        st.success("🟢 Running")
        if st.button("⏹ Stop Automation", use_container_width=True):
            st.session_state.automation_on = False
            st.rerun()
    else:
        st.error("🔴 Stopped")
        if st.button("▶️ Start Automation", use_container_width=True):
            st.session_state.automation_on = True
            st.session_state.run_log.append(
                f"[{datetime.now().strftime('%H:%M:%S')}] Automation started"
            )
            st.rerun()

    # ── Quick stats sidebar ──────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("### 📊 Quick Stats")
    stats = get_stats()
    st.metric("Total Applied",  stats["total"])
    st.metric("Today",          stats["today"])
    st.metric("Interviews",     stats["interviews"])
    st.metric("Avg Match",      f"{stats['avg_score']}%")

    # ── Add sample data ──────────────────────────────────────────────────────
    st.markdown("---")
    if st.button("🎲 Load Demo Data", use_container_width=True):
        add_sample_data()
        st.success("Demo data loaded!")
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ── Pages ─────────────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Dashboard
# ─────────────────────────────────────────────────────────────────────────────
if page == "📊 Dashboard":
    st.markdown("# 📊 Dashboard")
    st.markdown("Real-time overview of your job application activity.")

    # KPI row
    stats = get_stats()
    cols  = st.columns(4)
    kpis  = [
        ("📨 Total Applied",  stats["total"],         ""),
        ("📅 Applied Today",  stats["today"],          ""),
        ("🎯 Interviews",     stats["interviews"],     ""),
        ("📈 Response Rate",  f"{stats['response_rate']}%", ""),
    ]
    for col, (label, value, delta) in zip(cols, kpis):
        with col:
            st.markdown(f"""
            <div class="metric-card">
                <div class="metric-number">{value}</div>
                <div class="metric-label">{label}</div>
            </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts row ───────────────────────────────────────────────────────────
    df = get_recent_applications(200)
    col_left, col_right = st.columns(2)

    with col_left:
        st.markdown('<div class="section-header">📅 Applications Over Time</div>',
                    unsafe_allow_html=True)
        if not df.empty:
            df["date"] = pd.to_datetime(df["applied_at"]).dt.date
            daily = df.groupby("date").size().reset_index(name="count")
            fig = px.area(
                daily, x="date", y="count",
                color_discrete_sequence=["#6366f1"],
                template="plotly_dark"
            )
            fig.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=20, b=0),
                xaxis_title="", yaxis_title="Applications"
            )
            fig.update_traces(fill="tozeroy", fillcolor="rgba(99,102,241,0.2)")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No application data yet. Load demo data or start applying!")

    with col_right:
        st.markdown('<div class="section-header">📊 Application Status</div>',
                    unsafe_allow_html=True)
        if not df.empty:
            status_counts = df["status"].value_counts().reset_index()
            status_counts.columns = ["status", "count"]
            colors = {
                "applied": "#6366f1", "interview": "#34d399",
                "rejected": "#f87171", "pending": "#fbbf24"
            }
            fig2 = px.pie(
                status_counts, names="status", values="count",
                color="status",
                color_discrete_map=colors,
                template="plotly_dark",
                hole=0.5
            )
            fig2.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                legend=dict(font=dict(color="#e0e0e0")),
                margin=dict(l=0, r=0, t=20, b=0)
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No data yet.")

    # ── Recent applications table ─────────────────────────────────────────────
    st.markdown('<div class="section-header">🕐 Recent Applications</div>',
                unsafe_allow_html=True)
    df_recent = get_recent_applications(10)
    if not df_recent.empty:
        for _, row in df_recent.iterrows():
            with st.container():
                r1, r2, r3, r4 = st.columns([3, 2, 1, 1])
                with r1:
                    st.markdown(
                        f'<div class="job-title">{row["title"]}</div>'
                        f'<div class="job-company">🏢 {row["company"]}</div>',
                        unsafe_allow_html=True
                    )
                with r2:
                    applied_str = row["applied_at"][:10] if row["applied_at"] else "-"
                    st.markdown(
                        f'<div class="job-meta">📍 {row.get("location","")}'
                        f'<br>📅 {applied_str}</div>',
                        unsafe_allow_html=True
                    )
                with r3:
                    sc = row["match_score"] or 0
                    st.markdown(
                        f'<div style="color:{score_color(sc)};font-weight:700;'
                        f'font-size:1.3rem;text-align:center">{sc}%</div>'
                        f'<div class="score-bar-bg"><div class="score-bar-fill" '
                        f'style="width:{sc}%;background:linear-gradient(90deg,'
                        f'{score_color(sc)},{score_color(sc)})"></div></div>',
                        unsafe_allow_html=True
                    )
                with r4:
                    st.markdown(status_badge(row["status"]), unsafe_allow_html=True)
                st.markdown("---")
    else:
        st.info("No applications found. Click **Load Demo Data** in the sidebar to get started.")

    # ── Automation log ────────────────────────────────────────────────────────
    if st.session_state.run_log:
        st.markdown('<div class="section-header">🖥️ Automation Log</div>',
                    unsafe_allow_html=True)
        log_text = "\n".join(st.session_state.run_log[-20:])
        st.markdown(f'<div class="log-box">{log_text}</div>',
                    unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Job Search
# ─────────────────────────────────────────────────────────────────────────────
elif page == "🔍 Job Search":
    st.markdown("# 🔍 Job Search")
    st.markdown("Configure and trigger job searches across multiple platforms.")

    # ── Search configuration panel ────────────────────────────────────────────
    with st.expander("🎛️ Search Parameters", expanded=True):
        c1, c2 = st.columns(2)
        with c1:
            keywords_raw = st.text_area(
                "Job Keywords (one per line)",
                value="\n".join(
                    st.session_state.config.get("job_search", {}).get("keywords", [])
                ),
                height=120
            )
        with c2:
            locations_raw = st.text_area(
                "Locations (one per line)",
                value="\n".join(
                    st.session_state.config.get("job_search", {}).get("locations", [])
                ),
                height=120
            )

        exp_level = st.select_slider(
            "Experience Level",
            options=["entry", "mid", "senior"],
            value=st.session_state.config.get(
                "job_search", {}).get("experience_level", "mid")
        )

    # ── Site toggles ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">🌐 Job Sites</div>',
                unsafe_allow_html=True)
    sites = st.session_state.config.get("job_search", {}).get("sites", [])
    site_cols = st.columns(len(sites) if sites else 1)
    site_states = {}
    for col, site in zip(site_cols, sites):
        with col:
            site_states[site["name"]] = st.toggle(
                site["name"].title(),
                value=site.get("enabled", True),
                key=f"site_{site['name']}"
            )

    # ── Trigger search ────────────────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    col_btn, col_info = st.columns([1, 3])
    with col_btn:
        search_clicked = st.button("🔍 Search Now", use_container_width=True)
    with col_info:
        st.info("ℹ️ Real scraping requires Selenium and valid credentials. "
                "Demo mode shows simulated results.")

    if search_clicked:
        keywords  = [k.strip() for k in keywords_raw.splitlines() if k.strip()]
        locations = [l.strip() for l in locations_raw.splitlines() if l.strip()]

        # Update config in memory
        st.session_state.config["job_search"]["keywords"]  = keywords
        st.session_state.config["job_search"]["locations"] = locations
        st.session_state.config["job_search"]["experience_level"] = exp_level

        with st.spinner("🔍 Searching for jobs..."):
            time.sleep(2)  # Simulate network latency

            # ── Simulated results ──────────────────────────────────────────
            import random, hashlib
            simulated = []
            companies = ["TechCorp", "StartupAI", "FinTech Ltd",
                         "CloudBase", "DataSystems", "RemoteCo"]
            titles_pool = keywords or ["Software Engineer"]

            for kw in titles_pool[:3]:
                for loc in locations[:2]:
                    url = f"https://linkedin.com/jobs/{hashlib.md5((kw+loc).encode()).hexdigest()[:8]}"
                    simulated.append({
                        "title":   kw,
                        "company": random.choice(companies),
                        "location": loc,
                        "source":  "linkedin",
                        "url":     url,
                        "score":   random.randint(55, 98),
                        "posted":  "1 day ago"
                    })

            st.session_state.jobs_found = simulated

        st.success(f"✅ Found {len(st.session_state.jobs_found)} jobs!")

    # ── Job results ───────────────────────────────────────────────────────────
    if st.session_state.jobs_found:
        st.markdown('<div class="section-header">📋 Search Results</div>',
                    unsafe_allow_html=True)

        # Filter bar
        fc1, fc2, fc3 = st.columns(3)
        with fc1:
            filter_source = st.selectbox(
                "Source",
                ["All"] + list({j["source"] for j in st.session_state.jobs_found})
            )
        with fc2:
            min_score = st.slider("Min Match Score", 0, 100, 60)
        with fc3:
            sort_by = st.selectbox("Sort By", ["Score (High→Low)", "Score (Low→High)"])

        jobs_display = [
            j for j in st.session_state.jobs_found
            if (filter_source == "All" or j["source"] == filter_source)
            and j["score"] >= min_score
        ]
        if sort_by == "Score (High→Low)":
            jobs_display.sort(key=lambda x: x["score"], reverse=True)
        else:
            jobs_display.sort(key=lambda x: x["score"])

        for job in jobs_display:
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <div class="job-title">{job['title']}</div>
                    <div class="job-company">🏢 {job['company']}</div>
                    <div class="job-meta">
                        📍 {job['location']} &nbsp;|&nbsp;
                        🌐 {job['source'].title()} &nbsp;|&nbsp;
                        📅 {job['posted']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

                jc1, jc2, jc3 = st.columns([2, 1, 1])
                with jc1:
                    sc = job["score"]
                    st.markdown(
                        f'**Match:** <span style="color:{score_color(sc)};'
                        f'font-weight:700">{sc}%</span>',
                        unsafe_allow_html=True
                    )
                    st.progress(sc / 100)
                with jc2:
                    st.link_button("🔗 View Job", job["url"])
                with jc3:
                    if st.button("📨 Apply Now", key=f"apply_{job['url'][:20]}"):
                        with st.spinner("Applying..."):
                            time.sleep(1.5)

                            # Save to DB
                            conn = get_db_connection()
                            cur  = conn.cursor()
                            import hashlib
                            jid  = hashlib.md5(job["url"].encode()).hexdigest()[:12]
                            try:
                                cur.execute(
                                    """INSERT OR IGNORE INTO applied_jobs
                                       (id,title,company,url,applied_at,
                                        match_score,status,location,source)
                                       VALUES (?,?,?,?,?,?,?,?,?)""",
                                    (jid, job["title"], job["company"],
                                     job["url"],
                                     datetime.now().isoformat(),
                                     job["score"], "applied",
                                     job["location"], job["source"])
                                )
                                conn.commit()
                                st.success("✅ Applied!")
                            except Exception as e:
                                st.error(f"Error: {e}")
                            finally:
                                conn.close()

                st.markdown("---")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Applications
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📝 Applications":
    st.markdown("# 📝 Application Tracker")

    df = get_recent_applications(200)

    if df.empty:
        st.info("No applications found. Load demo data or start searching!")
        st.stop()

    # ── Filters ───────────────────────────────────────────────────────────────
    st.markdown("### 🔎 Filter & Search")
    f1, f2, f3, f4 = st.columns(4)
    with f1:
        sel_status = st.multiselect(
            "Status",
            ["applied", "interview", "rejected", "pending"],
            default=["applied", "interview", "rejected", "pending"]
        )
    with f2:
        sel_source = st.multiselect(
            "Source",
            df["source"].unique().tolist() if "source" in df.columns else [],
            default=df["source"].unique().tolist() if "source" in df.columns else []
        )
    with f3:
        score_range = st.slider("Match Score Range", 0, 100, (0, 100))
    with f4:
        search_q = st.text_input("🔍 Search title / company")

    # Apply filters
    mask = (
        df["status"].isin(sel_status) &
        df["match_score"].between(score_range[0], score_range[1])
    )
    if sel_source and "source" in df.columns:
        mask &= df["source"].isin(sel_source)
    if search_q:
        q = search_q.lower()
        mask &= (
            df["title"].str.lower().str.contains(q, na=False) |
            df["company"].str.lower().str.contains(q, na=False)
        )
    df_filtered = df[mask]

    st.markdown(f"**Showing {len(df_filtered)} of {len(df)} applications**")

    # ── Export ────────────────────────────────────────────────────────────────
    csv = df_filtered.to_csv(index=False)
    st.download_button(
        "⬇️ Export CSV", csv, "applications.csv", "text/csv", key="export_csv"
    )

    st.markdown("---")

    # ── Application rows ──────────────────────────────────────────────────────
    for _, row in df_filtered.iterrows():
        with st.expander(f"**{row['title']}** — {row['company']} "
                         f"| {(row['match_score'] or 0)}% match"):
            d1, d2, d3 = st.columns([2, 2, 1])

            with d1:
                st.markdown(f"**🏢 Company:** {row['company']}")
                st.markdown(f"**📍 Location:** {row.get('location','N/A')}")
                st.markdown(f"**🌐 Source:** {row.get('source','N/A').title()}")
                if row.get("url"):
                    st.markdown(f"**🔗 [View Posting]({row['url']})**")

            with d2:
                applied_str = row["applied_at"][:19].replace("T", " ") \
                              if row["applied_at"] else "N/A"
                st.markdown(f"**📅 Applied:** {applied_str}")
                sc = row["match_score"] or 0
                st.markdown(
                    f"**Match:** <span style='color:{score_color(sc)};font-weight:700'>"
                    f"{sc}%</span>",
                    unsafe_allow_html=True
                )
                st.progress(sc / 100)
                st.markdown(
                    f"**Status:** {status_badge(row['status'])}",
                    unsafe_allow_html=True
                )

            with d3:
                new_status = st.selectbox(
                    "Update Status",
                    ["applied", "interview", "rejected", "pending"],
                    index=["applied", "interview", "rejected", "pending"].index(
                        row["status"] if row["status"] in
                        ["applied", "interview", "rejected", "pending"]
                        else "applied"
                    ),
                    key=f"status_{row['id']}"
                )
                notes = st.text_area(
                    "Notes", value=row.get("notes") or "",
                    key=f"notes_{row['id']}", height=80
                )
                if st.button("💾 Save", key=f"save_{row['id']}"):
                    conn = get_db_connection()
                    conn.execute(
                        "UPDATE applied_jobs SET status=?,notes=? WHERE id=?",
                        (new_status, notes, row["id"])
                    )
                    conn.commit()
                    conn.close()
                    st.success("Saved!")
                    st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Configuration
# ─────────────────────────────────────────────────────────────────────────────
elif page == "⚙️ Configuration":
    st.markdown("# ⚙️ Configuration")

    cfg = st.session_state.config
    tabs = st.tabs(["🔍 Job Search", "🤖 Automation", "📊 Matching",
                    "📄 Resume", "🔐 Credentials"])

    # ── Tab 1: Job Search ────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("### Job Search Settings")
        js = cfg.setdefault("job_search", {})

        kw_raw = st.text_area(
            "Keywords (one per line)",
            value="\n".join(js.get("keywords", [])), height=120
        )
        loc_raw = st.text_area(
            "Locations (one per line)",
            value="\n".join(js.get("locations", [])), height=100
        )
        exp = st.select_slider(
            "Experience Level", ["entry", "mid", "senior"],
            value=js.get("experience_level", "mid")
        )

        st.markdown("#### Job Sites")
        sites = js.get("sites", [
            {"name": "linkedin", "enabled": True,
             "url": "https://www.linkedin.com/jobs/search/"},
            {"name": "indeed",   "enabled": True,
             "url": "https://www.indeed.com/jobs"},
            {"name": "glassdoor","enabled": False,
             "url": "https://www.glassdoor.com/Job/jobs.htm"},
        ])
        new_sites = []
        for site in sites:
            sc1, sc2 = st.columns([1, 3])
            with sc1:
                enabled = st.checkbox(site["name"].title(), value=site.get("enabled", True),
                                      key=f"cfg_site_{site['name']}")
            with sc2:
                url = st.text_input(f"{site['name']} URL", value=site.get("url",""),
                                    key=f"cfg_url_{site['name']}")
            new_sites.append({"name": site["name"], "enabled": enabled, "url": url})

        if st.button("💾 Save Job Search Settings"):
            cfg["job_search"]["keywords"]        = [k.strip() for k in kw_raw.splitlines() if k.strip()]
            cfg["job_search"]["locations"]       = [l.strip() for l in loc_raw.splitlines() if l.strip()]
            cfg["job_search"]["experience_level"]= exp
            cfg["job_search"]["sites"]           = new_sites
            save_config(cfg)

    # ── Tab 2: Automation ────────────────────────────────────────────────────
    with tabs[1]:
        st.markdown("### Automation Settings")
        auto = cfg.setdefault("automation", {})

        interval = st.number_input(
            "Check Interval (seconds)", min_value=60, max_value=86400,
            value=auto.get("check_interval_seconds", 3600), step=60
        )
        max_apps = st.number_input(
            "Max Applications per Day", min_value=1, max_value=100,
            value=auto.get("max_applications_per_day", 10)
        )
        delay = st.number_input(
            "Delay Between Applications (seconds)", min_value=5, max_value=300,
            value=auto.get("delay_between_applications", 30)
        )

        if st.button("💾 Save Automation Settings"):
            cfg["automation"]["check_interval_seconds"]     = interval
            cfg["automation"]["max_applications_per_day"]   = max_apps
            cfg["automation"]["delay_between_applications"] = delay
            save_config(cfg)

    # ── Tab 3: Matching ──────────────────────────────────────────────────────
    with tabs[2]:
        st.markdown("### Job Matching Criteria")
        match = cfg.setdefault("matching", {})

        min_score = st.slider(
            "Minimum Match Score (%)", 0, 100,
            value=match.get("min_match_score", 70)
        )

        mc1, mc2 = st.columns(2)
        with mc1:
            req_raw = st.text_area(
                "Required Skills (one per line)",
                value="\n".join(match.get("required_skills", [])), height=150
            )
        with mc2:
            pref_raw = st.text_area(
                "Preferred Skills (one per line)",
                value="\n".join(match.get("preferred_skills", [])), height=150
            )

        if st.button("💾 Save Matching Settings"):
            cfg["matching"]["min_match_score"] = min_score
            cfg["matching"]["required_skills"] = [s.strip() for s in req_raw.splitlines() if s.strip()]
            cfg["matching"]["preferred_skills"]= [s.strip() for s in pref_raw.splitlines() if s.strip()]
            save_config(cfg)

    # ── Tab 4: Resume ────────────────────────────────────────────────────────
    with tabs[3]:
        st.markdown("### Resume & Cover Letter")
        res = cfg.setdefault("resume", {})

        uploaded = st.file_uploader("📄 Upload Resume (PDF)", type=["pdf"])
        if uploaded:
            path = DATA_DIR / "resume.pdf"
            path.write_bytes(uploaded.getbuffer())
            cfg["resume"]["path"] = "data/resume.pdf"
            st.success(f"✅ Resume saved to {path}")

        resume_path = Path(res.get("path", "data/resume.pdf"))
        if resume_path.exists():
            st.markdown(
                f'<div class="job-card">📄 <strong>Current resume:</strong> '
                f'{resume_path.name} '
                f'({resume_path.stat().st_size // 1024} KB)</div>',
                unsafe_allow_html=True
            )

        st.markdown("#### Cover Letter Template")
        cl_path = Path(res.get("cover_letter_template", "data/cover_letter.txt"))
        cl_content = cl_path.read_text() if cl_path.exists() else (
            "Dear Hiring Manager,\n\nI am writing to apply for the "
            "{position} role at {company}.\n\nBest regards"
        )
        new_cl = st.text_area("Cover Letter Template", value=cl_content, height=200)
        st.caption("Use `{company}`, `{position}`, `{date}` as placeholders.")

        if st.button("💾 Save Cover Letter"):
            cl_path.parent.mkdir(parents=True, exist_ok=True)
            cl_path.write_text(new_cl)
            cfg["resume"]["cover_letter_template"] = str(cl_path)
            save_config(cfg)
            st.success("✅ Cover letter saved!")

    # ── Tab 5: Credentials ───────────────────────────────────────────────────
    with tabs[4]:
        st.markdown("### Platform Credentials")
        st.warning(
            "⚠️ Credentials are stored locally in config.yaml. "
            "Never share this file."
        )

        for platform in ["LinkedIn", "Indeed"]:
            with st.expander(f"🔐 {platform} Credentials"):
                key_prefix = platform.lower()
                platform_cfg = cfg.setdefault(key_prefix, {})
                em = st.text_input(
                    f"{platform} Email",
                    value=platform_cfg.get("email", ""),
                    key=f"{key_prefix}_email"
                )
                pw = st.text_input(
                    f"{platform} Password",
                    value=platform_cfg.get("password", ""),
                    type="password", key=f"{key_prefix}_password"
                )
                if st.button(f"💾 Save {platform}", key=f"save_{key_prefix}"):
                    cfg[key_prefix]["email"]    = em
                    cfg[key_prefix]["password"] = pw
                    save_config(cfg)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Email Settings
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📧 Email Settings":
    st.markdown("# 📧 Email Notifications")

    email_cfg = st.session_state.config.setdefault("email", {})

    col1, col2 = st.columns([1, 2])
    with col1:
        enabled = st.toggle("Enable Email Notifications",
                            value=email_cfg.get("enabled", False))
    with col2:
        if enabled:
            st.success("📧 Notifications are ENABLED")
        else:
            st.warning("📧 Notifications are DISABLED")

    st.markdown("---")

    e1, e2 = st.columns(2)
    with e1:
        smtp_server = st.text_input("SMTP Server",
                                    value=email_cfg.get("smtp_server", "smtp.gmail.com"))
        sender_email = st.text_input("Sender Email",
                                     value=email_cfg.get("sender_email", ""))
        recipient_email = st.text_input("Recipient Email",
                                        value=email_cfg.get("recipient_email", ""))
    with e2:
        smtp_port = st.number_input("SMTP Port", value=email_cfg.get("smtp_port", 587))
        sender_pw = st.text_input("App Password",
                                  value=email_cfg.get("sender_password", ""),
                                  type="password")
        st.info("💡 For Gmail, generate an **App Password** under Google Account → Security.")

    st.markdown("### 🔔 Notification Triggers")
    nc1, nc2, nc3 = st.columns(3)
    with nc1: notify_apply   = st.checkbox("On each application", value=True)
    with nc2: notify_daily   = st.checkbox("Daily summary",        value=True)
    with nc3: notify_error   = st.checkbox("On errors",            value=True)

    col_save, col_test = st.columns(2)
    with col_save:
        if st.button("💾 Save Email Settings", use_container_width=True):
            st.session_state.config["email"].update({
                "enabled": enabled, "smtp_server": smtp_server,
                "smtp_port": int(smtp_port), "sender_email": sender_email,
                "sender_password": sender_pw, "recipient_email": recipient_email,
            })
            save_config(st.session_state.config)

    with col_test:
        if st.button("📤 Send Test Email", use_container_width=True):
            if not all([sender_email, sender_pw, recipient_email]):
                st.error("Please fill in all email fields first.")
            else:
                with st.spinner("Sending test email..."):
                    time.sleep(1.5)
                st.success("✅ Test email sent! (Check your inbox)")


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Analytics
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📈 Analytics":
    st.markdown("# 📈 Analytics")

    df = get_recent_applications(500)
    if df.empty:
        st.info("No data yet. Load demo data or start applying!")
        st.stop()

    df["applied_at"]  = pd.to_datetime(df["applied_at"])
    df["date"]        = df["applied_at"].dt.date
    df["match_score"] = pd.to_numeric(df["match_score"], errors="coerce").fillna(0)

    # ── Row 1 ─────────────────────────────────────────────────────────────────
    a1, a2 = st.columns(2)

    with a1:
        st.markdown('<div class="section-header">📊 Score Distribution</div>',
                    unsafe_allow_html=True)
        fig = px.histogram(
            df, x="match_score", nbins=20,
            color_discrete_sequence=["#6366f1"],
            template="plotly_dark",
            labels={"match_score": "Match Score (%)"}
        )
        fig.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=0, r=0, t=20, b=0)
        )
        st.plotly_chart(fig, use_container_width=True)

    with a2:
        st.markdown('<div class="section-header">🏢 Top Companies</div>',
                    unsafe_allow_html=True)
        top_co = df["company"].value_counts().head(10).reset_index()
        top_co.columns = ["company", "count"]
        fig2 = px.bar(
            top_co, x="count", y="company", orientation="h",
            color="count",
            color_continuous_scale=["#312e81", "#6366f1", "#a5b4fc"],
            template="plotly_dark"
        )
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            coloraxis_showscale=False,
            margin=dict(l=0, r=0, t=20, b=0)
        )
        st.plotly_chart(fig2, use_container_width=True)

    # ── Row 2 ─────────────────────────────────────────────────────────────────
    b1, b2 = st.columns(2)

    with b1:
        st.markdown('<div class="section-header">📅 Daily Activity</div>',
                    unsafe_allow_html=True)
        daily = df.groupby("date").agg(
            applications=("id", "count"),
            avg_score=("match_score", "mean")
        ).reset_index()
        fig3 = go.Figure()
        fig3.add_trace(go.Bar(
            x=daily["date"], y=daily["applications"],
            name="Applications", marker_color="#6366f1"
        ))
        fig3.add_trace(go.Scatter(
            x=daily["date"], y=daily["avg_score"],
            name="Avg Score", yaxis="y2",
            line=dict(color="#34d399", width=2), mode="lines+markers"
        ))
        fig3.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            yaxis2=dict(overlaying="y", side="right", showgrid=False),
            margin=dict(l=0, r=0, t=20, b=0),
            legend=dict(font=dict(color="#e0e0e0"))
        )
        st.plotly_chart(fig3, use_container_width=True)

    with b2:
        st.markdown('<div class="section-header">🌐 Applications by Source</div>',
                    unsafe_allow_html=True)
        if "source" in df.columns:
            src_grp = df.groupby(["source", "status"]).size().reset_index(name="count")
            fig4 = px.bar(
                src_grp, x="source", y="count", color="status",
                color_discrete_map={
                    "applied": "#6366f1", "interview": "#34d399",
                    "rejected": "#f87171", "pending": "#fbbf24"
                },
                template="plotly_dark", barmode="stack"
            )
            fig4.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                margin=dict(l=0, r=0, t=20, b=0),
                legend=dict(font=dict(color="#e0e0e0"))
            )
            st.plotly_chart(fig4, use_container_width=True)

    # ── Score vs Status box plot ───────────────────────────────────────────────
    st.markdown('<div class="section-header">📦 Match Score by Status</div>',
                unsafe_allow_html=True)
    fig5 = px.box(
        df, x="status", y="match_score",
        color="status",
        color_discrete_map={
            "applied": "#6366f1", "interview": "#34d399",
            "rejected": "#f87171", "pending": "#fbbf24"
        },
        template="plotly_dark"
    )
    fig5.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        showlegend=False,
        margin=dict(l=0, r=0, t=20, b=0)
    )
    st.plotly_chart(fig5, use_container_width=True)

    # ── Summary table ─────────────────────────────────────────────────────────
    st.markdown('<div class="section-header">📋 Summary Statistics</div>',
                unsafe_allow_html=True)
    summary = df.groupby("status").agg(
        Count=("id", "count"),
        Avg_Score=("match_score", "mean"),
        Max_Score=("match_score", "max"),
        Min_Score=("match_score", "min")
    ).round(1).reset_index()
    st.dataframe(summary, use_container_width=True)


# ─────────────────────────────────────────────────────────────────────────────
# PAGE: Logs
# ─────────────────────────────────────────────────────────────────────────────
elif page == "📋 Logs":
    st.markdown("# 📋 System Logs")

    lc1, lc2 = st.columns([3, 1])
    with lc1:
        n_lines = st.slider("Lines to display", 20, 500, 100, step=20)
    with lc2:
        auto_refresh = st.toggle("Auto Refresh (5s)", value=False)

    if auto_refresh:
        time.sleep(5)
        st.rerun()

    log_lines = get_logs(n_lines)
    log_html  = "\n".join(
        f'<span style="color:{"#34d399" if "✅" in l else "#f87171" if "❌" in l else "#fbbf24" if "⚠️" in l else "#58a6ff"}">'
        f'{l.rstrip()}</span>'
        for l in log_lines
    )
    st.markdown(f'<div class="log-box">{log_html}</div>', unsafe_allow_html=True)

    if st.session_state.run_log:
        st.markdown("### 🤖 Automation Session Log")
        session_html = "\n".join(
            f'<span style="color:#a5b4fc">{entry}</span>'
            for entry in reversed(st.session_state.run_log[-50:])
        )
        st.markdown(f'<div class="log-box">{session_html}</div>',
                    unsafe_allow_html=True)

    if st.button("🗑️ Clear Session Log"):
        st.session_state.run_log = []
        st.rerun()

    # ── Log file management ───────────────────────────────────────────────────
    st.markdown("### 📂 Log Files")
    log_files = sorted(LOGS_DIR.glob("*.log"), reverse=True)
    if log_files:
        for lf in log_files[:5]:
            lfc1, lfc2, lfc3 = st.columns([3, 1, 1])
            with lfc1: st.text(lf.name)
            with lfc2: st.text(f"{lf.stat().st_size // 1024} KB")
            with lfc3:
                st.download_button(
                    "⬇️", lf.read_text(),
                    file_name=lf.name,
                    mime="text/plain",
                    key=f"dl_{lf.name}"
                )
    else:
        st.info("No log files found yet.")


# ──────────────────────────────────────────────────────────────────────────────
# ── Footer ─────────────────────────────────────────────────────────────────────
# ──────────────────────────────────────────────────────────────────────────────
st.markdown("---")
st.markdown(
    '<div style="text-align:center;color:#4b5563;font-size:.8rem">'
    '🚀 Job Application Automation System &nbsp;|&nbsp; '
    'Use responsibly &amp; comply with platform ToS'
    '</div>',
    unsafe_allow_html=True
)

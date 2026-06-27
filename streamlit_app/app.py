"""
JN Resolusi — Smart Cross-Reference & Audit Engine (Streamlit Edition)
MoE Agentic AI — PRESTIJ Programme 2025

Streamlit single-app deployment replacing Netlify + Render.
Combines backend logic, SQLite DB, and frontend UI in one platform.
"""

import sqlite3
import hashlib
import os
import re
import uuid
import io
import csv
from datetime import datetime, date, timedelta
from typing import Optional

import streamlit as st
import pandas as pd
from passlib.context import CryptContext
from jose import jwt, JWTError

# Agent imports
from agents.agent_a import run as agent_a_run, AgentAResult
from agents.agent_b import run as agent_b_run, AgentBResult
from agents.agent_c import run as agent_c_run, AgentCResult

# ---------------------------------------------------------------------------
# CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="JN Resolusi — Sistem Audit Pintar MOE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

DB_PATH = "jn_engine.db"
JWT_SECRET = os.environ.get("JWT_SECRET", "jnresolusi-dev-secret-2025-changeme")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = 24
ALLOWED_DOMAINS = {"@moe.gov.my", "@moe-dl.edu.my"}
DEFAULT_ADMIN_EMAIL = "admin@moe.gov.my"
DEFAULT_ADMIN_PASSWORD = "admin1234"

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

# ---------------------------------------------------------------------------
# DATABASE SETUP
# ---------------------------------------------------------------------------
@st.cache_resource
def init_db():
    """Create SQLite database and tables. Seed defaults on first run."""
    import os as _os
    db_dir = _os.path.join(_os.path.expanduser("~"), ".jn_engine")
    _os.makedirs(db_dir, exist_ok=True)
    db_path = _os.path.join(db_dir, "jn_engine.db")

    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id              TEXT PRIMARY KEY,
            email           TEXT UNIQUE NOT NULL,
            password_hash   TEXT NOT NULL,
            role            TEXT NOT NULL DEFAULT 'penyelaras_jn',
            is_active       INTEGER NOT NULL DEFAULT 1,
            created_at      TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS jn_audit_records (
            school_id           TEXT PRIMARY KEY,
            school_name         TEXT NOT NULL,
            school_type         TEXT NOT NULL,
            district            TEXT NOT NULL,
            state               TEXT NOT NULL,
            last_audit_date     TEXT NOT NULL,
            skpmg2_score        REAL NOT NULL,
            facility_gred       TEXT NOT NULL,
            canteen_hygiene_score REAL NOT NULL,
            integrity_risk_index  REAL NOT NULL,
            created_at          TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS matrix_payloads (
            id                  TEXT PRIMARY KEY,
            source_system_id    TEXT NOT NULL,
            source_system_name  TEXT NOT NULL,
            source_version      TEXT,
            school_id           TEXT NOT NULL,
            raw_text_extracted  TEXT,
            operational_score   REAL,
            mapped_category     TEXT,
            severity_level      TEXT,
            extracted_entities  TEXT,
            received_at         TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS discrepancy_log (
            id                          TEXT PRIMARY KEY,
            case_id                     TEXT UNIQUE NOT NULL,
            school_id                   TEXT NOT NULL,
            school_name                 TEXT,
            state                       TEXT,
            source_system_name          TEXT,
            audit_score_reference       REAL,
            operational_score_reported  REAL,
            score_delta                 REAL,
            discrepancy_index           REAL NOT NULL,
            di_classification           TEXT NOT NULL,
            flags                       TEXT NOT NULL DEFAULT '[]',
            anomaly_detected            INTEGER NOT NULL DEFAULT 0,
            confidence_score            REAL,
            agent_a_result              TEXT,
            agent_c_result              TEXT,
            brief_content               TEXT,
            timestamp                   TEXT NOT NULL DEFAULT (datetime('now'))
        );

        CREATE INDEX IF NOT EXISTS idx_dl_case_id ON discrepancy_log(case_id);
        CREATE INDEX IF NOT EXISTS idx_dl_anomaly ON discrepancy_log(anomaly_detected);
    """)

    # Seed audit records
    audit_data = [
        ("SKB001","SK Bandar Baru Nilai","SK","Seremban","Negeri Sembilan","2023-03-15",85.50,"A",88.00,0.120),
        ("SKB002","SK Bukit Jelutong","SK","Shah Alam","Selangor","2022-11-20",72.00,"B",65.00,0.350),
        ("SMK001","SMK Tun Hussein Onn","SMK","Kuala Lumpur","W.P. Kuala Lumpur","2024-01-10",91.20,"A",92.00,0.080),
        ("SMK002","SMK Pendang","SMK","Pendang","Kedah","2022-08-05",58.00,"C",45.00,0.680),
        ("SBP001","Sekolah Berasrama Penuh Integrasi Gombak","SBP","Gombak","Selangor","2023-09-22",94.80,"A",95.50,0.040),
        ("MRSM001","MRSM Kuala Klawang","MRSM","Jelebu","Negeri Sembilan","2023-06-14",88.30,"A",87.00,0.095),
        ("SKK001","SK Kluang Utama","SK","Kluang","Johor","2022-05-30",63.50,"C",58.00,0.420),
    ]
    conn.executemany(
        "INSERT OR IGNORE INTO jn_audit_records VALUES (?,?,?,?,?,?,?,?,?,?,datetime('now'))",
        audit_data
    )

    # Seed default admin
    hashed = pwd_context.hash(DEFAULT_ADMIN_PASSWORD)
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?,?,?,?)",
        (str(uuid.uuid4()), DEFAULT_ADMIN_EMAIL, hashed, "admin")
    )

    conn.commit()
    return conn

def get_db() -> sqlite3.Connection:
    """Get thread-local database connection."""
    if "db_conn" not in st.session_state:
        st.session_state.db_conn = init_db()
    return st.session_state.db_conn

# ---------------------------------------------------------------------------
# AUTH HELPERS
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_jwt(email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode(
        {"sub": email, "role": role, "exp": expire},
        JWT_SECRET, algorithm=JWT_ALGO
    )

def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        return None

def login_user(email: str, password: str) -> Optional[dict]:
    """Authenticate user against database."""
    if "@" in email:
        domain = "@" + email.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            return None
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
    if not row:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return {"email": row["email"], "role": row["role"], "token": create_jwt(row["email"], row["role"])}

def require_auth():
    """Ensure user is authenticated. Returns user dict or None."""
    if "user" not in st.session_state or not st.session_state.user:
        return None
    return st.session_state.user

def require_role(*roles: str):
    """Check if current user has one of the required roles."""
    user = require_auth()
    if not user:
        return False
    return user.get("role") in roles

# ---------------------------------------------------------------------------
# AGENT PIPELINE
# ---------------------------------------------------------------------------
def run_agent_pipeline(school_id: str, source_system_id: str, source_system_name: str,
                       raw_text: str, operational_score: float) -> dict:
    """Run Agent A → B → C pipeline and store results in DB."""
    db = get_db()

    # Agent A: Semantic Ingestion
    result_a = agent_a_run(school_id, raw_text, source_system_id)

    # Agent B: Discrepancy Index
    result_b = agent_b_run(school_id, operational_score, result_a, source_system_id)

    # Agent C: Executive Brief
    result_c = agent_c_run(school_id, source_system_name, result_a, result_b)

    # Store payload
    import json as json_mod
    payload_id = str(uuid.uuid4())
    db.execute("""INSERT INTO matrix_payloads (id, source_system_id, source_system_name, school_id,
                  raw_text_extracted, operational_score, mapped_category, severity_level, extracted_entities)
                  VALUES (?,?,?,?,?,?,?,?,?)""",
               (payload_id, source_system_id, source_system_name, school_id,
                raw_text, operational_score, result_a.mapped_category,
                result_a.severity, json_mod.dumps(result_a.extracted_entities)))

    # Store discrepancy
    flags_json = json_mod.dumps(result_b.flags)
    agent_a_json = json_mod.dumps({
        "mapped_category": result_a.mapped_category,
        "severity": result_a.severity,
        "entities": result_a.extracted_entities,
    })
    agent_c_json = json_mod.dumps({
        "alert_status": result_c.alert_status_label,
        "enforcement": result_c.enforcement_actions,
        "policy": result_c.policy_recommendations,
        "directive": result_c.executive_directive_text,
    })

    db.execute("""INSERT INTO discrepancy_log (id, case_id, school_id, school_name, state,
                  source_system_name, audit_score_reference, operational_score_reported,
                  score_delta, discrepancy_index, di_classification, flags, anomaly_detected,
                  confidence_score, agent_a_result, agent_c_result)
                  VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
               (str(uuid.uuid4()), result_b.case_id, school_id,
                result_c.school_name, result_c.state,
                source_system_name, result_b.audit_data_snapshot.get("skpmg2_score", 0),
                operational_score, result_b.score_delta, result_b.discrepancy_index,
                result_b.di_classification, flags_json, result_b.anomaly_detected,
                result_b.confidence_score, agent_a_json, agent_c_json))
    db.commit()

    return {
        "case_id": result_b.case_id,
        "school_id": school_id,
        "school_name": result_c.school_name,
        "di_classification": result_b.di_classification,
        "discrepancy_index": result_b.discrepancy_index,
        "anomaly_detected": result_b.anomaly_detected,
        "alert_level": result_c.alert_status_label,
        "alert_color": result_c.alert_color_code,
        "flags_count": len(result_b.flags),
        "flags_triggered": result_b.flags,
        "score_delta": result_b.score_delta,
        "state": result_c.state,
        "source_system": source_system_name,
        "issue_domain": result_a.mapped_category,
        "severity": result_a.severity,
        "confidence_score": result_b.confidence_score,
        "audit_score_reference": result_b.audit_data_snapshot.get("skpmg2_score", 0),
        "operational_score_reported": operational_score,
        "agent_a": agent_a_json,
        "agent_c": agent_c_json,
        "enforcement_actions": result_c.enforcement_actions,
        "policy_recommendations": result_c.policy_recommendations,
        "executive_directive_text": result_c.executive_directive_text,
        "generated_at": datetime.utcnow().isoformat(),
    }

# ---------------------------------------------------------------------------
# DI COLOR HELPERS
# ---------------------------------------------------------------------------
DI_COLORS = {
    "EXTREME_DISCREPANCY": "#C41E3A",
    "SEVERE_DISCREPANCY": "#C2410C",
    "MODERATE_DISCREPANCY": "#B45309",
    "MINOR_DISCREPANCY": "#1D4ED8",
    "DATA_ALIGNED": "#0F6B3C",
}

ROLE_LABELS = {
    "admin": "Admin",
    "penyelaras_jn": "Penyelaras JN",
    "peneraju_sektor": "Peneraju Sektor",
}

AUDIT_SCHOOLS = [
    "SKB001", "SKB002", "SMK001", "SMK002",
    "SBP001", "MRSM001", "SKK001", "UNKNOWN99"
]

DEMO_PAYLOADS = {
    "Ekstrem DI": {
        "source_system_id": "PRESTIJ-INTEGRITY-07",
        "source_system_name": "AI Integrity Monitoring Agent",
        "school_id": "SMK002",
        "operational_score": 96.5,
        "raw_text": "Laporan kritikal: rasuah dan penipuan rekod sekolah SMK002 oleh pentadbir. Rekod SKPMG2 didapati dimanipulasi secara sengaja. Integriti data sekolah sangat dipersoalkan. Tindakan segera diperlukan."
    },
    "Teruk DI": {
        "source_system_id": "PRESTIJ-FACILITY-02",
        "source_system_name": "AI Facility Assessment Agent",
        "school_id": "SKK001",
        "operational_score": 89.0,
        "raw_text": "Penilaian kemudahan sekolah SKK001 menunjukkan prestasi yang jauh lebih baik daripada rekod Nazir. Bangunan dan tandas dilaporkan dalam keadaan baik. Kantin bersih dan teratur. Namun terdapat tanda-tanda manipulasi rekod."
    },
    "Selaras": {
        "source_system_id": "PRESTIJ-ACADEMIC-01",
        "source_system_name": "AI Academic Quality Agent",
        "school_id": "SBP001",
        "operational_score": 93.0,
        "raw_text": "Laporan prestasi akademik SBP Integrasi Gombak menunjukkan kualiti pengajaran dan kurikulum yang cemerlang. PDPC berjalan dengan lancar."
    },
}

# ---------------------------------------------------------------------------
# UI: LOGIN PAGE
# ---------------------------------------------------------------------------
def render_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("""
        <div style="text-align:center;padding:20px 0 30px">
            <div style="font-size:48px">🛡️</div>
            <h1 style="color:#C41E3A;margin:0">JN RESOLUSI</h1>
            <p style="color:#6B7C93;font-size:14px">Sistem Audit Pintar MOE</p>
        </div>
        """, unsafe_allow_html=True)

        with st.form("login_form"):
            st.markdown("### Log Masuk")
            st.info("Akses terhad kepada domain rasmi: **@moe.gov.my** · **@moe-dl.edu.my**")
            email = st.text_input("Email", placeholder="nama@moe.gov.my")
            password = st.text_input("Kata Laluan", type="password", placeholder="••••••••")
            submitted = st.form_submit_button("Log Masuk", type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error("Sila isi email dan kata laluan.")
                else:
                    user = login_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error("Email atau kata laluan tidak sah.")

        st.caption("PRESTIJ-25 · MoE Agentic AI · v2.0 Streamlit")

# ---------------------------------------------------------------------------
# UI: SIDEBAR
# ---------------------------------------------------------------------------
def render_sidebar():
    user = st.session_state.user
    with st.sidebar:
        st.markdown("""
        <div style="display:flex;align-items:center;gap:10px;padding:10px 0 20px">
            <div style="background:#C41E3A;width:36px;height:36px;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px">🛡️</div>
            <div>
                <div style="font-weight:800;font-size:14px;color:#fff;line-height:1.2">JN RESOLUSI</div>
                <div style="font-size:10px;color:#6B7C93;letter-spacing:0.08em">Sistem Audit Pintar MOE</div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("**Navigasi**")

        page = st.radio(
            "Navigasi",
            ["📊 Papan Pemuka", "📤 Hantar Payload", "📋 Log Kes",
             "📄 Ringkasan Eksekutif", "ℹ️ Maklumat Sistem",
             "📁 Muat Naik CSV", "👥 Pengurusan Pengguna"],
            label_visibility="collapsed",
            key="nav_radio"
        )

        st.divider()

        # Quick demo buttons
        can_write = user["role"] in ("admin", "penyelaras_jn")
        if can_write:
            st.markdown("**Ingest Pantas**")
            for label in ["Ekstrem DI", "Teruk DI", "Selaras"]:
                if st.button(f"⚡ Demo: {label}", use_container_width=True, key=f"demo_{label}"):
                    d = DEMO_PAYLOADS[label]
                    st.session_state.demo_payload = d
                    st.session_state.nav_radio = "📤 Hantar Payload"
                    st.rerun()

        st.divider()

        # Stats
        db = get_db()
        total = db.execute("SELECT COUNT(*) FROM discrepancy_log").fetchone()[0]
        anomalies = db.execute("SELECT COUNT(*) FROM discrepancy_log WHERE anomaly_detected=1").fetchone()[0]
        st.markdown(f"""
        **Statistik Enjin**
        - Ejen: `3 Dalam Talian`
        - Kes: `{total}`
        - Anomali: `{anomalies}`
        """)

        st.divider()

        # User display
        st.markdown(f"""
        <div style="font-size:11px;color:#6B7C93">
        <span style="font-family:monospace">{user['email']}</span><br>
        <span style="background:#EEF2FF;color:#4338CA;padding:2px 8px;border-radius:10px;font-size:10px;font-weight:700">
        {ROLE_LABELS.get(user['role'], user['role'])}
        </span>
        </div>
        """, unsafe_allow_html=True)

        if st.button("🚪 Log Keluar", use_container_width=True):
            st.session_state.user = None
            st.session_state.pop("db_conn", None)
            st.rerun()

    return page

# ---------------------------------------------------------------------------
# UI: DASHBOARD
# ---------------------------------------------------------------------------
def render_dashboard():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">PEMANTAUAN LANGSUNG</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Papan Pemuka Enjin")
    st.caption("Pemantauan masa nyata ekosistem matrix 25×25.")

    db = get_db()
    cases = db.execute("SELECT * FROM discrepancy_log ORDER BY timestamp DESC").fetchall()
    total = len(cases)
    anomalies = sum(1 for c in cases if c["anomaly_detected"])
    extreme = sum(1 for c in cases if c["di_classification"] in ("EXTREME_DISCREPANCY", "SEVERE_DISCREPANCY"))
    aligned = sum(1 for c in cases if c["di_classification"] == "DATA_ALIGNED")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Jumlah Kes", total, help="Diproses")
    c2.metric("Anomali Dikesan", anomalies, delta=f"{int(anomalies/total*100)}% diproses" if total else "—")
    c3.metric("Ekstrem / Teruk", extreme, help="Tindakan Segera")
    c4.metric("Data Selaras", aligned, help="Konsisten")

    st.divider()
    st.subheader("Kes Terkini")

    if not cases:
        st.info("📋 Tiada kes diproses. Gunakan Hantar Payload untuk mula.")
    else:
        for c in cases[:8]:
            color = DI_COLORS.get(c["di_classification"], "#6B7C93")
            import json as json_mod
            flags = json_mod.loads(c["flags"]) if c["flags"] else []
            with st.container():
                cols = st.columns([3, 1, 1])
                cols[0].markdown(f"""
                <span style="font-family:monospace;font-size:10px;color:#C41E3A">{c['case_id']}</span><br>
                <span style="font-weight:600">{c['school_id']} — {c['school_name']}</span>
                """, unsafe_allow_html=True)
                cols[1].markdown(f"<span style='font-size:18px;font-weight:800;color:{color}'>{c['discrepancy_index']:.4f}</span>", unsafe_allow_html=True)
                badge = "🔴 ANOMALI" if c["anomaly_detected"] else "🟢 BERSIH"
                cols[2].markdown(f"<span style='font-size:12px'>{badge}</span>", unsafe_allow_html=True)
                if cols[2].button("Brief →", key=f"dbrief_{c['case_id']}"):
                    st.session_state.view_case_id = c["case_id"]
                    st.session_state.nav_radio = "📄 Ringkasan Eksekutif"
                    st.rerun()

    # DI Distribution
    st.divider()
    st.subheader("Taburan Discrepancy Index (DI)")
    dist_data = {
        "Klasifikasi": ["Selaras", "Minor", "Sederhana", "Teruk", "Ekstrem"],
        "Bilangan": [
            sum(1 for c in cases if c["di_classification"] == "DATA_ALIGNED"),
            sum(1 for c in cases if c["di_classification"] == "MINOR_DISCREPANCY"),
            sum(1 for c in cases if c["di_classification"] == "MODERATE_DISCREPANCY"),
            sum(1 for c in cases if c["di_classification"] == "SEVERE_DISCREPANCY"),
            sum(1 for c in cases if c["di_classification"] == "EXTREME_DISCREPANCY"),
        ]
    }
    if sum(dist_data["Bilangan"]) > 0:
        st.bar_chart(pd.DataFrame(dist_data).set_index("Klasifikasi"), use_container_width=True)

# ---------------------------------------------------------------------------
# UI: INGEST PAYLOAD
# ---------------------------------------------------------------------------
def render_ingest():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">PENGAMBILAN MATRIX</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Hantar Payload")
    st.caption("Hantar telemetri daripada sistem matrix luaran untuk dianalisis oleh pipeline Ejen A → B → C.")

    # Check for demo payload
    demo = st.session_state.pop("demo_payload", None)

    col_form, col_ref = st.columns([2, 1])

    with col_form:
        with st.form("ingest_form"):
            source_id = st.text_input("ID Sistem Sumber", value=demo["source_system_id"] if demo else "PRESTIJ-BULLY-03")
            source_name = st.text_input("Nama Sistem", value=demo["source_system_name"] if demo else "AI-Powered Bully Detection Agent")

            db_audit = get_db()
            schools = db_audit.execute("SELECT school_id, school_name FROM jn_audit_records ORDER BY school_id").fetchall()
            school_options = {f"{s['school_id']} — {s['school_name']}": s["school_id"] for s in schools}
            school_options["UNKNOWN99 — Sekolah Tidak Dikenali"] = "UNKNOWN99"

            selected_label = st.selectbox("Kod Sekolah", list(school_options.keys()),
                                          index=list(school_options.keys()).index(
                                              next((k for k in school_options if school_options[k] == (demo["school_id"] if demo else "SMK002")), list(school_options.keys())[0])
                                          ))
            school_id = school_options[selected_label]

            default_score = demo["operational_score"] if demo else 92.0
            op_score = st.slider("Skor Operasi", 0.0, 100.0, default_score, 0.5)

            default_text = demo["raw_text"] if demo else "Terdapat laporan kritikal berhubung salah guna kuasa oleh pentadbir sekolah SMK002..."
            raw_text = st.text_area("Laporan Teks (Raw Text Payload)", value=default_text, height=120)

            submitted = st.form_submit_button("🚀 Hantar ke Enjin", type="primary", use_container_width=True)

            if submitted:
                if require_role("admin", "penyelaras_jn"):
                    with st.spinner("Memproses melalui Ejen A → B → C..."):
                        result = run_agent_pipeline(school_id, source_id, source_name, raw_text, op_score)
                    st.session_state.last_ingest = result
                    st.success(f"✅ Payload diproses: {result['case_id']}")
                    if result["anomaly_detected"]:
                        st.warning(f"⚠️ ANOMALI DIKESAN — DI: {result['discrepancy_index']:.4f}")
                    st.rerun()
                else:
                    st.error("Anda tiada akses untuk menghantar payload.")

    with col_ref:
        st.markdown("**Formula DI**")
        st.latex(r"DI = \frac{|Audit - Op|}{100}")
        st.caption("Julat: [0.0000, 1.0000]")

        st.markdown("**Klasifikasi**")
        thresholds = [
            ("🔴 ≥ 0.75", "EKSTREM"),
            ("🟠 ≥ 0.50", "TERUK"),
            ("🟡 ≥ 0.25", "SEDERHANA"),
            ("🔵 ≥ 0.10", "MINOR"),
            ("🟢 < 0.10", "SELARAS"),
        ]
        for th, lbl in thresholds:
            st.markdown(f"`{th}` **{lbl}**")

        st.markdown("**Rekod Audit**")
        audit_row = db_audit.execute("SELECT * FROM jn_audit_records WHERE school_id=?", (school_id,)).fetchone()
        if audit_row:
            st.markdown(f"""
            **{audit_row['school_name']}** ({audit_row['state']})
            - SKPMG2: `{audit_row['skpmg2_score']}`
            - Gred: `{audit_row['facility_gred']}`
            - Kantin: `{audit_row['canteen_hygiene_score']}`
            - Risiko: `{audit_row['integrity_risk_index']:.3f}`
            """)

    # Show last ingest result
    if "last_ingest" in st.session_state:
        r = st.session_state.last_ingest
        color = DI_COLORS.get(r["di_classification"], "#6B7C93")
        st.divider()
        st.subheader("Keputusan Terkini")
        with st.container():
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Skor DI", f"{r['discrepancy_index']:.4f}")
            c2.metric("Klasifikasi", r["di_classification"].replace("_", " "))
            c3.metric("Bendera", str(r["flags_count"]))
            c4.metric("Amaran", r["alert_level"])
            if st.button("📄 Lihat Ringkasan Eksekutif", type="primary"):
                st.session_state.view_case_id = r["case_id"]
                st.session_state.nav_radio = "📄 Ringkasan Eksekutif"
                st.rerun()

# ---------------------------------------------------------------------------
# UI: CASES LOG
# ---------------------------------------------------------------------------
def render_cases():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">LOG KES</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Log Kes")
    st.caption("Semua kes yang telah diproses oleh enjin.")

    db = get_db()
    cases = db.execute("SELECT * FROM discrepancy_log ORDER BY timestamp DESC").fetchall()

    col_btn, col_clr = st.columns([1, 5])
    with col_btn:
        if st.button("🔄 Segar Semula"):
            st.rerun()
    with col_clr:
        if require_role("admin"):
            if st.button("🗑️ Padam Semua Kes", type="secondary"):
                db.execute("DELETE FROM discrepancy_log")
                db.execute("DELETE FROM matrix_payloads")
                db.commit()
                st.success("Semua kes dipadam.")
                st.rerun()

    if not cases:
        st.info("🗂️ Tiada kes. Ingest payload untuk mula.")
        return

    df_data = []
    for c in cases:
        df_data.append({
            "ID Kes": c["case_id"],
            "Sekolah": f"{c['school_id']} — {c['school_name']}",
            "Skor DI": f"{c['discrepancy_index']:.4f}",
            "Klasifikasi": c["di_classification"].replace("_", " "),
            "Bendera": c["flags"].count('"') // 2 if c["flags"] else 0,
            "Anomali": "YA" if c["anomaly_detected"] else "TIDAK",
            "Diproses": c["timestamp"][:19],
        })

    df = pd.DataFrame(df_data)

    # Display as interactive dataframe
    event = st.dataframe(df, use_container_width=True, hide_index=True,
                         column_config={
                             "ID Kes": st.column_config.TextColumn(width="small"),
                             "Sekolah": st.column_config.TextColumn(width="medium"),
                         },
                         on_select="rerun", selection_mode="single-row")

    # Handle row selection
    if event.selection and len(event.selection["rows"]) > 0:
        row_idx = event.selection["rows"][0]
        case_id = cases[row_idx]["case_id"]
        if st.button(f"📄 Lihat Brief — {case_id}", type="primary"):
            st.session_state.view_case_id = case_id
            st.session_state.nav_radio = "📄 Ringkasan Eksekutif"
            st.rerun()

# ---------------------------------------------------------------------------
# UI: EXECUTIVE BRIEF
# ---------------------------------------------------------------------------
def render_brief():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">OUTPUT EKSEKUTIF</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Ringkasan Eksekutif")

    case_id = st.session_state.get("view_case_id")

    if not case_id:
        st.info("📄 Pilih kes daripada Log Kes atau ingest payload baharu untuk lihat ringkasan.")
        return

    db = get_db()
    case = db.execute("SELECT * FROM discrepancy_log WHERE case_id=?", (case_id,)).fetchone()

    if not case:
        st.error("Kes tidak dijumpai.")
        return

    import json as json_mod
    color = DI_COLORS.get(case["di_classification"], "#6B7C93")
    flags = json_mod.loads(case["flags"]) if case["flags"] else []
    agent_c_data = json_mod.loads(case["agent_c_result"]) if case["agent_c_result"] else {}

    st.markdown(f"""
    <div style="border-left:4px solid {color};padding:16px 20px;background:#111C35;border-radius:0 8px 8px 0;margin-bottom:20px">
        <div style="font-size:10px;color:#C41E3A;letter-spacing:0.16em;font-weight:700">ARAHAN EKSEKUTIF — AI-COMPLAINT-MOE</div>
        <div style="font-size:22px;font-weight:800;color:#fff">{case['school_name']}</div>
        <div style="font-family:monospace;font-size:11px;color:#6B7C93">{case['case_id']} · {case['state'] or 'N/A'} · {case['timestamp'][:19]}</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown(f"**Status:** {agent_c_data.get('alert_status', 'N/A')}")

    # Section A: School Info
    with st.expander("A. Maklumat Sekolah", expanded=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"**Kod Sekolah:** `{case['school_id']}`")
        c1.markdown(f"**Sumber Sistem:** {case['source_system_name']}")
        c2.markdown(f"**Skor Audit JN:** `{case['audit_score_reference']:.2f}`")
        c2.markdown(f"**Skor Dilaporkan:** `{case['operational_score_reported']:.2f}`")

    # Section B: DI Analysis
    with st.expander("B. Analisis Discrepancy Index", expanded=True):
        c1, c2 = st.columns(2)
        c1.metric("Skor DI", f"{case['discrepancy_index']:.4f}")
        c1.metric("Delta", f"{case['score_delta']:+.2f}")
        c2.metric("Klasifikasi", case["di_classification"].replace("_", " "))
        c2.metric("Keyakinan", f"{int(case['confidence_score']*100) if case['confidence_score'] else 0}%")

        # DI Bar
        di_pct = min(100, case["discrepancy_index"] * 100)
        st.progress(di_pct / 100, text=f"DI: {case['discrepancy_index']:.4f} / 1.0000")

    # Flags
    if flags:
        with st.expander(f"C. Bendera Risiko ({len(flags)})", expanded=True):
            for f in flags:
                st.markdown(f"🔴 {f}")

    # Enforcement
    enf = agent_c_data.get("enforcement", [])
    if enf:
        with st.expander(f"D. Tindakan Penguatkuasaan ({len(enf)})", expanded=True):
            for i, action in enumerate(enf, 1):
                st.markdown(f"**{i}.** {action}")

    # Policy
    policy = agent_c_data.get("policy", [])
    if policy:
        with st.expander(f"E. Cadangan Pindaan Polisi ({len(policy)})", expanded=True):
            for p in policy:
                ref = p.get("legal_reference", "") if isinstance(p, dict) else ""
                action = p.get("recommended_action", "") if isinstance(p, dict) else str(p)
                st.markdown(f"📜 **{ref}** — {action}")

    # Directive text
    directive = agent_c_data.get("directive", "")
    if directive:
        with st.expander("F. Teks Perintah Eksekutif"):
            st.text(directive)

# ---------------------------------------------------------------------------
# UI: ADMIN PANEL
# ---------------------------------------------------------------------------
def render_admin():
    if not require_role("admin"):
        st.warning("Hanya Admin boleh mengakses bahagian ini.")
        return

    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">PENTADBIR SISTEM</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Pengurusan Pengguna")
    st.caption("Urus akaun pengguna sistem.")

    db = get_db()

    col_users, col_add = st.columns([2, 1])

    with col_users:
        st.subheader("Senarai Pengguna")
        users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()
        if users:
            user_data = []
            for u in users:
                user_data.append({
                    "Email": u["email"],
                    "Peranan": ROLE_LABELS.get(u["role"], u["role"]),
                    "Status": "Aktif" if u["is_active"] else "Tidak Aktif",
                    "ID": u["id"][:8] + "…",
                    # Hidden for action
                })
            st.dataframe(pd.DataFrame(user_data), use_container_width=True, hide_index=True)
        else:
            st.info("Tiada pengguna.")

    with col_add:
        st.subheader("Tambah Pengguna")
        with st.form("create_user_form"):
            new_email = st.text_input("Email", placeholder="nama@moe.gov.my")
            new_password = st.text_input("Kata Laluan", type="password", placeholder="Min 6 aksara")
            new_role = st.selectbox("Peranan", ["penyelaras_jn", "peneraju_sektor", "admin"])
            submitted = st.form_submit_button("➕ Cipta Pengguna", type="primary", use_container_width=True)

            if submitted:
                if not new_email or len(new_password) < 6:
                    st.error("Sila isi email dan kata laluan (min 6 aksara).")
                elif "@" not in new_email:
                    st.error("Format email tidak sah.")
                else:
                    hashed = pwd_context.hash(new_password)
                    try:
                        db.execute(
                            "INSERT INTO users (id, email, password_hash, role) VALUES (?,?,?,?)",
                            (str(uuid.uuid4()), new_email, hashed, new_role)
                        )
                        db.commit()
                        st.success(f"✅ Pengguna {new_email} berjaya dicipta!")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("Email sudah wujud!")

        # Role info
        st.markdown("**Had Peranan**")
        st.markdown("""
        - **Admin** — Semua akses
        - **Penyelaras JN** — Input + CSV
        - **Peneraju Sektor** — Baca sahaja
        """)

# ---------------------------------------------------------------------------
# UI: CSV UPLOAD
# ---------------------------------------------------------------------------
def render_csv_upload():
    if not require_role("admin", "penyelaras_jn"):
        st.warning("Anda tiada akses untuk muat naik CSV.")
        return

    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">MUAT NAIK CSV</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Muat Naik CSV Pukal")
    st.caption("Muat naik fail CSV dengan data sekolah untuk diproses secara pukal.")

    col_upload, col_info = st.columns([2, 1])

    with col_upload:
        uploaded = st.file_uploader("Pilih fail CSV", type=["csv"], label_visibility="collapsed")

        if uploaded:
            df = pd.read_csv(uploaded)
            st.markdown(f"**Pratonton** — {len(df)} baris")
            st.dataframe(df.head(), use_container_width=True, hide_index=True)

            if st.button("🚀 Proses CSV", type="primary", use_container_width=True):
                results = []
                errors = []
                progress = st.progress(0)
                status = st.empty()

                for i, row in df.iterrows():
                    try:
                        school = str(row.get("school", ""))
                        # Calculate operational score from reported columns
                        reported_cols = [c for c in df.columns if "_reported" in str(c)]
                        op_values = [float(row[c]) for c in reported_cols if pd.notna(row.get(c))]
                        op_score = sum(op_values) / len(op_values) if op_values else 50.0

                        # Generate raw text from columns
                        raw_parts = [f"{c}: {row[c]}" for c in df.columns if c != "school" and pd.notna(row.get(c))]
                        raw_text = "; ".join(raw_parts[:5])

                        result = run_agent_pipeline(
                            school, f"CSV-UPLOAD-{i+1:04d}",
                            "CSV Bulk Upload", raw_text, op_score
                        )
                        results.append({
                            "Baris": i + 1,
                            "Sekolah": school,
                            "Skor Op": f"{op_score:.1f}",
                            "Skor DI": f"{result['discrepancy_index']:.4f}",
                            "ID Kes": result["case_id"],
                        })
                    except Exception as e:
                        errors.append({"Baris": i + 1, "Ralat": str(e)})

                    progress.progress((i + 1) / len(df))
                    status.text(f"Memproses... {i+1}/{len(df)}")

                progress.empty()
                status.empty()

                if results:
                    st.success(f"✅ {len(results)} berjaya diproses")
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                if errors:
                    st.error(f"❌ {len(errors)} ralat")
                    st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

    with col_info:
        st.markdown("**Format CSV**")
        st.code("school,cleanliness_reported,cleanliness_actual,ict_reported,ict_actual,discipline_reported,discipline_actual\nSMK002,90,28,85,30,80,55", language=None)
        st.caption("Op Score = purata *_reported")
        st.caption("DI = |Audit − Op| / 100")

        st.markdown("**Akses**")
        st.markdown("- Admin\n- Penyelaras JN")

# ---------------------------------------------------------------------------
# UI: SYSTEM INFO
# ---------------------------------------------------------------------------
def render_system():
    st.markdown("""
    <div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">
        <span style="width:8px;height:8px;border-radius:50%;background:#C41E3A"></span>
        <span style="font-size:11px;font-weight:700;color:#C41E3A;letter-spacing:0.14em">INFO SISTEM</span>
    </div>
    """, unsafe_allow_html=True)
    st.title("Tentang Sistem")
    st.caption("MoE AI-Complaint — Sistem Imbangan Semak Pintar.")

    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Seni Bina")
        st.markdown("""
        **Ejen A** — Semantic Ingestion & Mapping  
        *NER + Weighted Taxonomy Scoring*

        **Ejen B** — Cross-Examination & Anomaly  
        *DI Computation + 8-Flag Generator*

        **Ejen C** — Executive Briefing  
        *Policy Matrix + Directive Generator*
        """)

    with c2:
        st.subheader("Tindanan Teknologi")
        st.markdown("""
        **Backend** — FastAPI + Python 3.12  
        **Database** — PostgreSQL / SQLite  
        **Frontend** — Streamlit (Python)  
        **Deploy** — Streamlit Cloud
        """)

    st.divider()
    st.subheader("Deployment")
    st.markdown("""
    🚀 Dijalankan di **Streamlit Cloud** — satu platform untuk backend + frontend.

    **Migrasi dari:** Netlify (frontend) + Render.com (backend + PostgreSQL)  
    **Ke:** Streamlit Cloud (all-in-one Python deployment)
    """)

# ---------------------------------------------------------------------------
# MAIN APP
# ---------------------------------------------------------------------------
def main():
    try:
        # Init DB on first load
        if "db_conn" not in st.session_state:
            st.session_state.db_conn = init_db()

        # Auth check
        if "user" not in st.session_state or not st.session_state.user:
            render_login()
            return

        # Render sidebar and get current page
        page = render_sidebar()

        # Route to page
        page_map = {
            "📊 Papan Pemuka": render_dashboard,
            "📤 Hantar Payload": render_ingest,
            "📋 Log Kes": render_cases,
            "📄 Ringkasan Eksekutif": render_brief,
            "ℹ️ Maklumat Sistem": render_system,
            "📁 Muat Naik CSV": render_csv_upload,
            "👥 Pengurusan Pengguna": render_admin,
        }

        render_fn = page_map.get(page)
        if render_fn:
            render_fn()
    except Exception as e:
        st.error(f"⚠️ Ralat sistem: {str(e)}")
        st.info("Refresh halaman atau hubungi admin.")

if __name__ == "__main__":
    main()

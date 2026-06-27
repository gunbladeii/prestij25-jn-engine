"""
JN Resolusi — Smart Cross-Reference & Audit Engine (Streamlit Edition)
MoE Agentic AI — PRESTIJ Programme 2025
"""

import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import streamlit as st
import pandas as pd
from passlib.context import CryptContext
from jose import jwt, JWTError

from agents.agent_a import run as agent_a_run, AgentAResult
from agents.agent_b import run as agent_b_run, AgentBResult
from agents.agent_c import run as agent_c_run, AgentCResult

# ---------------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="JN Resolusi — Sistem Audit Pintar MOE",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------
JWT_SECRET   = os.environ.get("JWT_SECRET", "jnresolusi-dev-secret-2025-changeme")
JWT_ALGO     = "HS256"
JWT_EXPIRE_HOURS = 24
ALLOWED_DOMAINS  = {"@moe.gov.my", "@moe-dl.edu.my"}
DEFAULT_ADMIN_EMAIL    = "admin@moe.gov.my"
DEFAULT_ADMIN_PASSWORD = "admin1234"

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")

DI_COLORS = {
    "EXTREME_DISCREPANCY":  "#C41E3A",
    "SEVERE_DISCREPANCY":   "#C2410C",
    "MODERATE_DISCREPANCY": "#B45309",
    "MINOR_DISCREPANCY":    "#1D4ED8",
    "DATA_ALIGNED":         "#0F6B3C",
}

ROLE_KEYS = ["penyelaras_jn", "peneraju_sektor", "admin"]

AUDIT_SCHOOLS = [
    "SKB001", "SKB002", "SMK001", "SMK002",
    "SBP001", "MRSM001", "SKK001", "UNKNOWN99"
]

DEMO_PAYLOADS = {
    "Ekstrem DI": {
        "source_system_id":   "PRESTIJ-INTEGRITY-07",
        "source_system_name": "AI Integrity Monitoring Agent",
        "school_id":          "SMK002",
        "operational_score":  96.5,
        "raw_text": "Laporan kritikal: rasuah dan penipuan rekod sekolah SMK002 oleh pentadbir. Rekod SKPMG2 didapati dimanipulasi secara sengaja. Integriti data sekolah sangat dipersoalkan. Tindakan segera diperlukan."
    },
    "Teruk DI": {
        "source_system_id":   "PRESTIJ-FACILITY-02",
        "source_system_name": "AI Facility Assessment Agent",
        "school_id":          "SKK001",
        "operational_score":  89.0,
        "raw_text": "Penilaian kemudahan sekolah SKK001 menunjukkan prestasi yang jauh lebih baik daripada rekod Nazir. Bangunan dan tandas dilaporkan dalam keadaan baik. Kantin bersih dan teratur. Namun terdapat tanda-tanda manipulasi rekod."
    },
    "Selaras": {
        "source_system_id":   "PRESTIJ-ACADEMIC-01",
        "source_system_name": "AI Academic Quality Agent",
        "school_id":          "SBP001",
        "operational_score":  93.0,
        "raw_text": "Laporan prestasi akademik SBP Integrasi Gombak menunjukkan kualiti pengajaran dan kurikulum yang cemerlang. PDPC berjalan dengan lancar."
    },
}

# ---------------------------------------------------------------------------
# TRANSLATIONS
# ---------------------------------------------------------------------------
_TR = {
    "BM": {
        # Auth
        "login_title":        "Log Masuk",
        "login_domain":       "Akses terhad kepada domain rasmi: **@moe.gov.my** · **@moe-dl.edu.my**",
        "login_email":        "Email",
        "login_password":     "Kata Laluan",
        "login_btn":          "Log Masuk",
        "login_empty":        "Sila isi email dan kata laluan.",
        "login_fail":         "Email atau kata laluan tidak sah.",
        "login_brand_desc":   "Platform Kecerdasan Buatan untuk pemantauan integriti dan analisis Discrepancy Index (DI) sekolah di bawah Kementerian Pendidikan Malaysia.",
        "login_feat_a":       "Ejen A — Pengambilan Semantik & NER",
        "login_feat_b":       "Ejen B — Analisis Discrepancy Index",
        "login_feat_c":       "Ejen C — Ringkasan Eksekutif & Polisi",
        "login_footer":       "PRESTIJ-25 · MoE Agentic AI · v2.0 Streamlit",
        # Sidebar
        "nav_monitoring":     "PEMANTAUAN",
        "nav_data_input":     "INPUT DATA",
        "nav_system":         "SISTEM",
        "nav_dashboard":      "📊  Papan Pemuka",
        "nav_cases":          "📋  Log & Kes",
        "nav_data_sub":       "📤  Penghantaran Data",
        "nav_users":          "👥  Pengurusan Pengguna",
        "nav_info":           "ℹ️  Maklumat Sistem",
        "nav_quick":          "Ingest Pantas",
        "stat_title":         "Statistik Enjin",
        "stat_agents":        "Ejen Dalam Talian",
        "stat_cases":         "Kes Diproses",
        "stat_anomalies":     "Anomali",
        "btn_logout":         "Log Keluar",
        "lang_toggle":        "EN",
        # Dashboard
        "dash_section":       "PEMANTAUAN LANGSUNG",
        "dash_title":         "Papan Pemuka Enjin",
        "dash_caption":       "Pemantauan masa nyata ekosistem matrix 25×25.",
        "dash_total":         "Jumlah Kes",
        "dash_anomaly":       "Anomali Dikesan",
        "dash_extreme":       "Ekstrem / Teruk",
        "dash_aligned":       "Data Selaras",
        "dash_recent":        "Kes Terkini",
        "dash_empty":         "📋 Tiada kes diproses. Gunakan Penghantaran Data untuk mula.",
        "dash_di_dist":       "Taburan Discrepancy Index",
        "dash_di_labels":     ["Selaras", "Minor", "Sederhana", "Teruk", "Ekstrem"],
        "dash_brief_btn":     "Brief →",
        # Data Submission
        "sub_section":        "PENGHANTARAN DATA",
        "sub_title":          "Penghantaran Data",
        "sub_caption":        "Hantar data melalui payload manual atau muat naik CSV pukal.",
        "tab_payload":        "📤  Hantar Payload",
        "tab_csv":            "📁  Muat Naik CSV",
        "sub_src_id":         "ID Sistem Sumber",
        "sub_src_name":       "Nama Sistem",
        "sub_school":         "Kod Sekolah",
        "sub_score":          "Skor Operasi",
        "sub_text":           "Laporan Teks (Raw Text Payload)",
        "sub_btn":            "🚀 Hantar ke Enjin",
        "sub_spin":           "Memproses melalui Ejen A → B → C...",
        "sub_ok":             "✅ Payload diproses",
        "sub_anomaly":        "⚠️ ANOMALI DIKESAN — DI",
        "sub_no_access":      "Anda tiada akses untuk menghantar payload.",
        "sub_result":         "Keputusan Terkini",
        "sub_di":             "Skor DI",
        "sub_class":          "Klasifikasi",
        "sub_flags":          "Bendera",
        "sub_alert":          "Amaran",
        "sub_view_brief":     "📄 Lihat Ringkasan Eksekutif",
        "sub_formula":        "Formula DI",
        "sub_di_range":       "Julat: [0.0000, 1.0000]",
        "sub_classify":       "Klasifikasi",
        "sub_audit_ref":      "Rekod Audit",
        "csv_select":         "Pilih fail CSV",
        "csv_preview":        "Pratonton",
        "csv_rows":           "baris",
        "csv_process":        "🚀 Proses CSV",
        "csv_processing":     "Memproses...",
        "csv_ok":             "berjaya diproses",
        "csv_err":            "ralat",
        "csv_no_access":      "Anda tiada akses untuk muat naik CSV.",
        "csv_format":         "Format CSV",
        "csv_access":         "Akses",
        # Cases & Brief
        "cases_section":      "LOG KES & RINGKASAN",
        "cases_title":        "Log & Ringkasan Kes",
        "cases_caption":      "Semua kes yang telah diproses beserta ringkasan eksekutif.",
        "tab_log":            "📋  Log Kes",
        "tab_brief":          "📄  Ringkasan Eksekutif",
        "cases_refresh":      "🔄 Segar Semula",
        "cases_del_all":      "🗑️ Padam Semua Kes",
        "cases_empty":        "🗂️ Tiada kes. Ingest payload untuk mula.",
        "cases_col_id":       "ID Kes",
        "cases_col_school":   "Sekolah",
        "cases_col_di":       "Skor DI",
        "cases_col_class":    "Klasifikasi",
        "cases_col_flags":    "Bendera",
        "cases_col_anomaly":  "Anomali",
        "cases_col_time":     "Diproses",
        "brief_prompt":       "📄 Pilih kes daripada Log Kes untuk lihat ringkasan eksekutif.",
        "brief_status":       "Status",
        "brief_school":       "A. Maklumat Sekolah",
        "brief_di":           "B. Analisis Discrepancy Index",
        "brief_flags":        "C. Bendera Risiko",
        "brief_enforce":      "D. Tindakan Penguatkuasaan",
        "brief_policy":       "E. Cadangan Pindaan Polisi",
        "brief_directive":    "F. Teks Perintah Eksekutif",
        "brief_code":         "Kod Sekolah",
        "brief_source":       "Sumber Sistem",
        "brief_audit":        "Skor Audit JN",
        "brief_op":           "Skor Dilaporkan",
        "brief_di_score":     "Skor DI",
        "brief_delta":        "Delta",
        "brief_class":        "Klasifikasi",
        "brief_conf":         "Keyakinan",
        "brief_view_btn":     "📄 Lihat Brief",
        # Admin
        "admin_section":      "PENTADBIR SISTEM",
        "admin_title":        "Pengurusan Pengguna",
        "admin_caption":      "Urus akaun pengguna sistem.",
        "admin_list":         "Senarai Pengguna",
        "admin_add":          "Tambah Pengguna",
        "admin_email":        "Email",
        "admin_password":     "Kata Laluan",
        "admin_role":         "Peranan",
        "admin_create":       "➕ Cipta Pengguna",
        "admin_no_access":    "Hanya Admin boleh mengakses bahagian ini.",
        "admin_empty":        "Tiada pengguna.",
        "admin_ph_email":     "nama@moe.gov.my",
        "admin_ph_pass":      "Min 6 aksara",
        "admin_err_empty":    "Sila isi email dan kata laluan (min 6 aksara).",
        "admin_err_email":    "Format email tidak sah.",
        "admin_err_pass":     "Kata laluan min 6 aksara.",
        "admin_created":      "✅ Pengguna {} berjaya dicipta!",
        "admin_exists":       "Email sudah wujud!",
        "admin_col_email":    "Email",
        "admin_col_role":     "Peranan",
        "admin_col_status":   "Status",
        "admin_active":       "🟢 Aktif",
        "admin_inactive":     "🔴 Tidak Aktif",
        "admin_edit_title":   "✏️ Edit Pengguna",
        "admin_save":         "💾 Simpan",
        "admin_cancel":       "Batal",
        "admin_updated":      "✅ Pengguna {} berjaya dikemaskini!",
        "admin_del_warn":     "⚠️ Padam pengguna **{}**? Tindakan ini tidak boleh dibuat asal.",
        "admin_del_btn":      "🗑️ Ya, Padam",
        "admin_deleted":      "✅ Pengguna {} dipadam.",
        "admin_new_pass":     "Kata Laluan Baharu (kosongkan jika tidak tukar)",
        "admin_active_lbl":   "Akaun Aktif",
        "admin_roles_title":  "Had Peranan",
        "admin_roles_desc":   "- **Admin** — Semua akses\n- **Penyelaras JN** — Input + CSV\n- **Peneraju Sektor** — Baca sahaja",
        # System Info
        "sys_section":        "INFO SISTEM",
        "sys_title":          "Tentang Sistem",
        "sys_caption":        "MoE AI-Complaint — Sistem Imbangan Semak Pintar.",
        "sys_arch":           "Seni Bina Ejen",
        "sys_stack":          "Tindanan Teknologi",
        "sys_deploy":         "Deployment",
        # Tooltips
        "tip_di":             "Discrepancy Index (DI) — Ukuran perbezaan antara skor audit JN dan skor operasi yang dilaporkan. Formula: |Audit − Op| / 100. Julat: 0.0–1.0.",
        "tip_anomaly":        "Anomali dikesan apabila DI melebihi ambang 0.25 atau bendera risiko berganda diaktifkan serentak.",
        "tip_extreme":        "Kes dengan klasifikasi EXTREME (DI ≥ 0.75) atau SEVERE (DI ≥ 0.50) memerlukan tindakan segera.",
        "tip_skpmg2":         "Standard Kualiti Pendidikan Malaysia Gelombang 2 — instrumen penilaian kualiti sekolah kebangsaan yang digunakan oleh Jemaah Nazir.",
        "tip_confidence":     "Skor keyakinan model (0–100%): gabungan kekuatan semantik Ejen A dan konsistensi cross-reference Ejen B.",
        "tip_flags":          "Bendera risiko: 8 semakan automatik termasuk skor terpencil, ketidakkonsistenan rekod, dan pengesanan manipulasi.",
        "tip_op_score":       "Skor prestasi sekolah yang dilaporkan oleh sistem sumber. Dibandingkan dengan skor audit JN untuk mengira DI.",
        "tip_src_id":         "Pengecam unik sistem sumber yang menghantar payload. Contoh: PRESTIJ-BULLY-03",
        "tip_raw_text":       "Teks laporan mentah daripada sistem sumber. Ejen A akan mengekstrak entiti dan maklumat relevan.",
        "tip_case_id":        "Pengecam unik kes dalam format PRESTIJ-YYYYMMDD-XXXXXXXX.",
        "tip_agent_a":        "Ejen A: Pengambilan Semantik — menjalankan NER dan pemetaan taksonomi pada teks laporan masuk.",
        "tip_agent_b":        "Ejen B: Cross-Examination — mengira DI, menjana bendera risiko, dan mengesan anomali statistik.",
        "tip_agent_c":        "Ejen C: Ringkasan Eksekutif — menjana perintah, tindakan penguatkuasaan, dan cadangan polisi.",
        # Misc
        "anomaly_yes":        "🔴 ANOMALI",
        "anomaly_no":         "🟢 BERSIH",
        "role_admin":         "Admin",
        "role_penyelaras":    "Penyelaras JN",
        "role_peneraju":      "Peneraju Sektor",
    },
    "EN": {
        # Auth
        "login_title":        "Sign In",
        "login_domain":       "Access restricted to official domains: **@moe.gov.my** · **@moe-dl.edu.my**",
        "login_email":        "Email",
        "login_password":     "Password",
        "login_btn":          "Sign In",
        "login_empty":        "Please enter your email and password.",
        "login_fail":         "Invalid email or password.",
        "login_brand_desc":   "AI-powered platform for integrity monitoring and Discrepancy Index (DI) analysis across Ministry of Education Malaysia schools.",
        "login_feat_a":       "Agent A — Semantic Ingestion & NER",
        "login_feat_b":       "Agent B — Discrepancy Index Analysis",
        "login_feat_c":       "Agent C — Executive Brief & Policy",
        "login_footer":       "PRESTIJ-25 · MoE Agentic AI · v2.0 Streamlit",
        # Sidebar
        "nav_monitoring":     "MONITORING",
        "nav_data_input":     "DATA INPUT",
        "nav_system":         "SYSTEM",
        "nav_dashboard":      "📊  Dashboard",
        "nav_cases":          "📋  Cases & Log",
        "nav_data_sub":       "📤  Data Submission",
        "nav_users":          "👥  User Management",
        "nav_info":           "ℹ️  System Info",
        "nav_quick":          "Quick Ingest",
        "stat_title":         "Engine Statistics",
        "stat_agents":        "Agents Online",
        "stat_cases":         "Cases Processed",
        "stat_anomalies":     "Anomalies",
        "btn_logout":         "Sign Out",
        "lang_toggle":        "BM",
        # Dashboard
        "dash_section":       "LIVE MONITORING",
        "dash_title":         "Engine Dashboard",
        "dash_caption":       "Real-time monitoring of the 25×25 matrix ecosystem.",
        "dash_total":         "Total Cases",
        "dash_anomaly":       "Anomalies Detected",
        "dash_extreme":       "Extreme / Severe",
        "dash_aligned":       "Data Aligned",
        "dash_recent":        "Recent Cases",
        "dash_empty":         "📋 No cases processed. Use Data Submission to begin.",
        "dash_di_dist":       "Discrepancy Index Distribution",
        "dash_di_labels":     ["Aligned", "Minor", "Moderate", "Severe", "Extreme"],
        "dash_brief_btn":     "Brief →",
        # Data Submission
        "sub_section":        "DATA SUBMISSION",
        "sub_title":          "Data Submission",
        "sub_caption":        "Submit data via manual payload or bulk CSV upload.",
        "tab_payload":        "📤  Submit Payload",
        "tab_csv":            "📁  Upload CSV",
        "sub_src_id":         "Source System ID",
        "sub_src_name":       "System Name",
        "sub_school":         "School Code",
        "sub_score":          "Operational Score",
        "sub_text":           "Report Text (Raw Text Payload)",
        "sub_btn":            "🚀 Submit to Engine",
        "sub_spin":           "Processing through Agent A → B → C...",
        "sub_ok":             "✅ Payload processed",
        "sub_anomaly":        "⚠️ ANOMALY DETECTED — DI",
        "sub_no_access":      "You do not have access to submit payloads.",
        "sub_result":         "Latest Result",
        "sub_di":             "DI Score",
        "sub_class":          "Classification",
        "sub_flags":          "Flags",
        "sub_alert":          "Alert Level",
        "sub_view_brief":     "📄 View Executive Brief",
        "sub_formula":        "DI Formula",
        "sub_di_range":       "Range: [0.0000, 1.0000]",
        "sub_classify":       "Classification",
        "sub_audit_ref":      "Audit Reference",
        "csv_select":         "Select CSV file",
        "csv_preview":        "Preview",
        "csv_rows":           "rows",
        "csv_process":        "🚀 Process CSV",
        "csv_processing":     "Processing...",
        "csv_ok":             "successfully processed",
        "csv_err":            "errors",
        "csv_no_access":      "You do not have access to upload CSV.",
        "csv_format":         "CSV Format",
        "csv_access":         "Access",
        # Cases & Brief
        "cases_section":      "CASE LOG & BRIEFS",
        "cases_title":        "Cases & Executive Log",
        "cases_caption":      "All processed cases with executive summaries.",
        "tab_log":            "📋  Case Log",
        "tab_brief":          "📄  Executive Brief",
        "cases_refresh":      "🔄 Refresh",
        "cases_del_all":      "🗑️ Delete All Cases",
        "cases_empty":        "🗂️ No cases. Ingest a payload to start.",
        "cases_col_id":       "Case ID",
        "cases_col_school":   "School",
        "cases_col_di":       "DI Score",
        "cases_col_class":    "Classification",
        "cases_col_flags":    "Flags",
        "cases_col_anomaly":  "Anomaly",
        "cases_col_time":     "Processed",
        "brief_prompt":       "📄 Select a case from Case Log to view its executive brief.",
        "brief_status":       "Status",
        "brief_school":       "A. School Information",
        "brief_di":           "B. Discrepancy Index Analysis",
        "brief_flags":        "C. Risk Flags",
        "brief_enforce":      "D. Enforcement Actions",
        "brief_policy":       "E. Policy Recommendations",
        "brief_directive":    "F. Executive Directive Text",
        "brief_code":         "School Code",
        "brief_source":       "Source System",
        "brief_audit":        "JN Audit Score",
        "brief_op":           "Reported Score",
        "brief_di_score":     "DI Score",
        "brief_delta":        "Delta",
        "brief_class":        "Classification",
        "brief_conf":         "Confidence",
        "brief_view_btn":     "📄 View Brief",
        # Admin
        "admin_section":      "SYSTEM ADMINISTRATION",
        "admin_title":        "User Management",
        "admin_caption":      "Manage system user accounts.",
        "admin_list":         "User List",
        "admin_add":          "Add User",
        "admin_email":        "Email",
        "admin_password":     "Password",
        "admin_role":         "Role",
        "admin_create":       "➕ Create User",
        "admin_no_access":    "Only Admins can access this section.",
        "admin_empty":        "No users found.",
        "admin_ph_email":     "name@moe.gov.my",
        "admin_ph_pass":      "Min 6 characters",
        "admin_err_empty":    "Please fill email and password (min 6 chars).",
        "admin_err_email":    "Invalid email format.",
        "admin_err_pass":     "Password must be at least 6 characters.",
        "admin_created":      "✅ User {} created successfully!",
        "admin_exists":       "Email already exists!",
        "admin_col_email":    "Email",
        "admin_col_role":     "Role",
        "admin_col_status":   "Status",
        "admin_active":       "🟢 Active",
        "admin_inactive":     "🔴 Inactive",
        "admin_edit_title":   "✏️ Edit User",
        "admin_save":         "💾 Save",
        "admin_cancel":       "Cancel",
        "admin_updated":      "✅ User {} updated successfully!",
        "admin_del_warn":     "⚠️ Delete user **{}**? This action cannot be undone.",
        "admin_del_btn":      "🗑️ Yes, Delete",
        "admin_deleted":      "✅ User {} deleted.",
        "admin_new_pass":     "New Password (leave blank to keep current)",
        "admin_active_lbl":   "Account Active",
        "admin_roles_title":  "Role Permissions",
        "admin_roles_desc":   "- **Admin** — Full access\n- **Penyelaras JN** — Input + CSV\n- **Peneraju Sektor** — Read-only",
        # System Info
        "sys_section":        "SYSTEM INFO",
        "sys_title":          "About the System",
        "sys_caption":        "MoE AI-Complaint — Smart Check & Balance Engine.",
        "sys_arch":           "Agent Architecture",
        "sys_stack":          "Technology Stack",
        "sys_deploy":         "Deployment",
        # Tooltips
        "tip_di":             "Discrepancy Index (DI) — Measures variance between JN audit score and reported operational score. Formula: |Audit − Op| / 100. Range: 0.0–1.0.",
        "tip_anomaly":        "An anomaly is detected when DI exceeds 0.25 threshold or multiple risk flags are triggered simultaneously.",
        "tip_extreme":        "Cases classified as EXTREME (DI ≥ 0.75) or SEVERE (DI ≥ 0.50) require immediate action.",
        "tip_skpmg2":         "Standard Kualiti Pendidikan Malaysia Gelombang 2 — National school quality assessment instrument used by Jemaah Nazir.",
        "tip_confidence":     "Model confidence score (0–100%): combined semantic strength from Agent A and cross-reference consistency from Agent B.",
        "tip_flags":          "Risk flags: 8 automated checks including outlier scores, record inconsistencies, and manipulation detection.",
        "tip_op_score":       "School performance score reported by the source system. Compared against JN audit score to compute DI.",
        "tip_src_id":         "Unique identifier of the source system submitting this payload. Example: PRESTIJ-BULLY-03",
        "tip_raw_text":       "Raw report text from the source system. Agent A will extract entities and relevant information.",
        "tip_case_id":        "Unique case identifier in the format PRESTIJ-YYYYMMDD-XXXXXXXX.",
        "tip_agent_a":        "Agent A: Semantic Ingestion — performs NER and weighted taxonomy mapping on incoming report text.",
        "tip_agent_b":        "Agent B: Cross-Examination — computes DI, generates risk flags, and detects statistical anomalies.",
        "tip_agent_c":        "Agent C: Executive Brief — generates directives, enforcement actions, and policy recommendations.",
        # Misc
        "anomaly_yes":        "🔴 ANOMALY",
        "anomaly_no":         "🟢 CLEAN",
        "role_admin":         "Admin",
        "role_penyelaras":    "Penyelaras JN",
        "role_peneraju":      "Peneraju Sektor",
    },
}

def t(key: str) -> str:
    lang = st.session_state.get("lang", "BM")
    return _TR.get(lang, _TR["BM"]).get(key, key)

def role_label(role_code: str) -> str:
    mapping = {
        "admin":          t("role_admin"),
        "penyelaras_jn":  t("role_penyelaras"),
        "peneraju_sektor":t("role_peneraju"),
    }
    return mapping.get(role_code, role_code)

# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------
def inject_css():
    st.markdown("""
    <style>
    /* ── Global ──────────────────────────────────── */
    .main .block-container { padding-top: 1.5rem !important; padding-bottom: 2rem !important; }
    [data-testid="stAppViewContainer"] > .main { background: #0A0F1E; }

    /* ── Sidebar ─────────────────────────────────── */
    section[data-testid="stSidebar"] > div:first-child { padding: 1rem 0.6rem !important; }

    /* Nav group headers */
    .nav-group {
        font-size: 9px; font-weight: 800; letter-spacing: 0.18em;
        color: #3B4A63; padding: 14px 8px 5px; text-transform: uppercase;
    }

    /* All sidebar buttons — base */
    section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
        background: transparent !important;
        border: none !important; border-left: 3px solid transparent !important;
        color: #6B7C93 !important; text-align: left !important;
        font-size: 13px !important; font-weight: 500 !important;
        padding: 8px 10px !important; border-radius: 0 6px 6px 0 !important;
        box-shadow: none !important; margin-bottom: 1px !important;
        transition: background 0.15s, color 0.15s !important;
    }
    section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
        background: rgba(255,255,255,0.04) !important;
        color: #cbd5e1 !important;
    }

    /* Active nav item */
    section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
        background: rgba(196,30,58,0.12) !important;
        border: none !important; border-left: 3px solid #C41E3A !important;
        color: #fff !important; text-align: left !important;
        font-size: 13px !important; font-weight: 700 !important;
        padding: 8px 10px !important; border-radius: 0 6px 6px 0 !important;
        box-shadow: none !important; margin-bottom: 1px !important;
    }

    /* ── Login page ──────────────────────────────── */
    .login-hero {
        background: linear-gradient(160deg, #0D1829 0%, #111C35 60%, #0D1829 100%);
        border-radius: 16px; padding: 48px 40px;
        border: 1px solid rgba(255,255,255,0.06);
        height: 100%;
    }
    .login-form-card {
        background: rgba(17,28,53,0.85);
        backdrop-filter: blur(20px);
        border: 1px solid rgba(255,255,255,0.08);
        border-radius: 16px; padding: 40px 36px;
    }
    .feat-item {
        display: flex; align-items: center; gap: 10px;
        padding: 10px 14px; border-radius: 8px;
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.05);
        margin-bottom: 8px;
        font-size: 13px; color: #9CA3AF;
    }
    .feat-dot { width: 6px; height: 6px; border-radius: 50%; background: #C41E3A; flex-shrink: 0; }

    /* ── Section header ──────────────────────────── */
    .section-tag {
        display: flex; align-items: center; gap: 8px; margin-bottom: 4px;
    }
    .section-tag .dot {
        width: 8px; height: 8px; border-radius: 50%; background: #C41E3A;
    }
    .section-tag .label {
        font-size: 11px; font-weight: 800; color: #C41E3A; letter-spacing: 0.14em;
    }

    /* ── Metric cards ────────────────────────────── */
    [data-testid="metric-container"] {
        background: #111C35 !important;
        border: 1px solid #1E2A45 !important;
        border-radius: 10px !important; padding: 16px !important;
    }
    [data-testid="stMetricLabel"] { color: #6B7C93 !important; }
    [data-testid="stMetricValue"] { color: #fff !important; }

    /* ── Tab-style radio ─────────────────────────── */
    .tab-radio div[role="radiogroup"] {
        display: flex; gap: 4px; background: #111C35;
        padding: 4px; border-radius: 8px; border: 1px solid #1E2A45;
    }
    .tab-radio div[role="radiogroup"] label {
        flex: 1; text-align: center; padding: 8px 16px;
        border-radius: 6px; cursor: pointer; font-size: 13px;
        color: #6B7C93; transition: all 0.15s;
    }
    .tab-radio div[role="radiogroup"] label:has(input:checked) {
        background: #C41E3A; color: #fff; font-weight: 700;
    }
    .tab-radio div[role="radiogroup"] input { display: none; }

    /* ── Case row cards ──────────────────────────── */
    .case-row {
        background: #111C35; border: 1px solid #1E2A45;
        border-radius: 8px; padding: 12px 16px; margin-bottom: 6px;
    }

    /* ── DI badge ────────────────────────────────── */
    .di-badge {
        display: inline-block; padding: 3px 10px; border-radius: 12px;
        font-size: 11px; font-weight: 700; letter-spacing: 0.06em;
    }

    /* ── Brief header card ───────────────────────── */
    .brief-header {
        padding: 16px 20px; background: #111C35;
        border-radius: 0 8px 8px 0; margin-bottom: 20px;
    }

    /* ── Sidebar divider ─────────────────────────── */
    section[data-testid="stSidebar"] hr { border-color: #1E2A45; margin: 8px 0; }

    /* ── Dataframe ───────────────────────────────── */
    [data-testid="stDataFrame"] { border: 1px solid #1E2A45 !important; border-radius: 8px !important; }

    /* ── Form inputs ─────────────────────────────── */
    .stTextInput input, .stTextArea textarea, .stSelectbox > div > div {
        background: #111C35 !important; border-color: #1E2A45 !important; color: #fff !important;
    }

    /* ── Progress bar ────────────────────────────── */
    .stProgress > div > div { background: #C41E3A !important; }
    </style>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------
@st.cache_resource
def init_db():
    db_dir  = os.path.join(os.path.expanduser("~"), ".jn_engine")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "jn_engine.db")

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
            school_id             TEXT PRIMARY KEY,
            school_name           TEXT NOT NULL,
            school_type           TEXT NOT NULL,
            district              TEXT NOT NULL,
            state                 TEXT NOT NULL,
            last_audit_date       TEXT NOT NULL,
            skpmg2_score          REAL NOT NULL,
            facility_gred         TEXT NOT NULL,
            canteen_hygiene_score REAL NOT NULL,
            integrity_risk_index  REAL NOT NULL,
            created_at            TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS matrix_payloads (
            id                 TEXT PRIMARY KEY,
            source_system_id   TEXT NOT NULL,
            source_system_name TEXT NOT NULL,
            source_version     TEXT,
            school_id          TEXT NOT NULL,
            raw_text_extracted TEXT,
            operational_score  REAL,
            mapped_category    TEXT,
            severity_level     TEXT,
            extracted_entities TEXT,
            received_at        TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS discrepancy_log (
            id                         TEXT PRIMARY KEY,
            case_id                    TEXT UNIQUE NOT NULL,
            school_id                  TEXT NOT NULL,
            school_name                TEXT,
            state                      TEXT,
            source_system_name         TEXT,
            audit_score_reference      REAL,
            operational_score_reported REAL,
            score_delta                REAL,
            discrepancy_index          REAL NOT NULL,
            di_classification          TEXT NOT NULL,
            flags                      TEXT NOT NULL DEFAULT '[]',
            anomaly_detected           INTEGER NOT NULL DEFAULT 0,
            confidence_score           REAL,
            agent_a_result             TEXT,
            agent_c_result             TEXT,
            brief_content              TEXT,
            timestamp                  TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_dl_case_id ON discrepancy_log(case_id);
        CREATE INDEX IF NOT EXISTS idx_dl_anomaly  ON discrepancy_log(anomaly_detected);
    """)

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

    hashed = pwd_context.hash(DEFAULT_ADMIN_PASSWORD)
    conn.execute(
        "INSERT OR IGNORE INTO users (id, email, password_hash, role) VALUES (?,?,?,?)",
        (str(uuid.uuid4()), DEFAULT_ADMIN_EMAIL, hashed, "admin")
    )
    conn.commit()
    return conn

def get_db() -> sqlite3.Connection:
    if "db_conn" not in st.session_state:
        st.session_state.db_conn = init_db()
    return st.session_state.db_conn

# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return pwd_context.hash(password)

def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)

def create_jwt(email: str, role: str) -> str:
    expire = datetime.utcnow() + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"sub": email, "role": role, "exp": expire}, JWT_SECRET, algorithm=JWT_ALGO)

def decode_jwt(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
    except JWTError:
        return None

def login_user(email: str, password: str) -> Optional[dict]:
    if "@" in email:
        domain = "@" + email.split("@")[1]
        if domain not in ALLOWED_DOMAINS:
            return None
    db  = get_db()
    row = db.execute("SELECT * FROM users WHERE email=? AND is_active=1", (email,)).fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        return None
    return {"email": row["email"], "role": row["role"], "token": create_jwt(row["email"], row["role"])}

def require_auth() -> Optional[dict]:
    return st.session_state.get("user")

def require_role(*roles: str) -> bool:
    user = require_auth()
    return bool(user) and user.get("role") in roles

# ---------------------------------------------------------------------------
# AGENT PIPELINE
# ---------------------------------------------------------------------------
def run_agent_pipeline(school_id, source_system_id, source_system_name, raw_text, operational_score) -> dict:
    import json as _json
    db = get_db()

    result_a = agent_a_run(school_id, raw_text, source_system_id)
    result_b = agent_b_run(school_id, operational_score, result_a, source_system_id)
    result_c = agent_c_run(school_id, source_system_name, result_a, result_b)

    payload_id = str(uuid.uuid4())
    db.execute("""INSERT INTO matrix_payloads
        (id, source_system_id, source_system_name, school_id,
         raw_text_extracted, operational_score, mapped_category, severity_level, extracted_entities)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (payload_id, source_system_id, source_system_name, school_id,
         raw_text, operational_score, result_a.mapped_category,
         result_a.severity, _json.dumps(result_a.extracted_entities)))

    flags_json   = _json.dumps(result_b.flags)
    agent_a_json = _json.dumps({"mapped_category": result_a.mapped_category,
                                 "severity": result_a.severity,
                                 "entities": result_a.extracted_entities})
    agent_c_json = _json.dumps({"alert_status":  result_c.alert_status_label,
                                 "enforcement":   result_c.enforcement_actions,
                                 "policy":        result_c.policy_recommendations,
                                 "directive":     result_c.executive_directive_text})

    db.execute("""INSERT INTO discrepancy_log
        (id, case_id, school_id, school_name, state, source_system_name,
         audit_score_reference, operational_score_reported, score_delta,
         discrepancy_index, di_classification, flags, anomaly_detected,
         confidence_score, agent_a_result, agent_c_result)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), result_b.case_id, school_id,
         result_c.school_name, result_c.state, source_system_name,
         result_b.audit_data_snapshot.get("skpmg2_score", 0),
         operational_score, result_b.score_delta, result_b.discrepancy_index,
         result_b.di_classification, flags_json, result_b.anomaly_detected,
         result_b.confidence_score, agent_a_json, agent_c_json))
    db.commit()

    return {
        "case_id":                   result_b.case_id,
        "school_id":                 school_id,
        "school_name":               result_c.school_name,
        "di_classification":         result_b.di_classification,
        "discrepancy_index":         result_b.discrepancy_index,
        "anomaly_detected":          result_b.anomaly_detected,
        "alert_level":               result_c.alert_status_label,
        "alert_color":               result_c.alert_color_code,
        "flags_count":               len(result_b.flags),
        "flags_triggered":           result_b.flags,
        "score_delta":               result_b.score_delta,
        "state":                     result_c.state,
        "source_system":             source_system_name,
        "issue_domain":              result_a.mapped_category,
        "severity":                  result_a.severity,
        "confidence_score":          result_b.confidence_score,
        "audit_score_reference":     result_b.audit_data_snapshot.get("skpmg2_score", 0),
        "operational_score_reported":operational_score,
        "agent_a":                   agent_a_json,
        "agent_c":                   agent_c_json,
        "enforcement_actions":       result_c.enforcement_actions,
        "policy_recommendations":    result_c.policy_recommendations,
        "executive_directive_text":  result_c.executive_directive_text,
        "generated_at":              datetime.utcnow().isoformat(),
    }

# ---------------------------------------------------------------------------
# UI HELPERS
# ---------------------------------------------------------------------------
def section_header(label: str):
    st.markdown(f"""
    <div class="section-tag">
        <span class="dot"></span>
        <span class="label">{label}</span>
    </div>
    """, unsafe_allow_html=True)

def _nav_btn(label_key: str, page_key: str, role_required=None):
    if role_required and not require_role(*role_required):
        return
    is_active = st.session_state.get("current_page") == page_key
    btn_type  = "primary" if is_active else "secondary"
    if st.sidebar.button(t(label_key), key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type):
        st.session_state.current_page = page_key
        st.session_state.pop("edit_user_id",   None)
        st.session_state.pop("delete_user_id", None)
        st.rerun()

def _tab_radio(opt_a_key: str, opt_b_key: str, state_key: str) -> str:
    """Render a styled tab-like radio and return current tab value ('a' or 'b')."""
    opts  = [t(opt_a_key), t(opt_b_key)]
    curr  = st.session_state.get(state_key, "a")
    idx   = 0 if curr == "a" else 1
    st.markdown('<div class="tab-radio">', unsafe_allow_html=True)
    chosen = st.radio("", opts, index=idx, horizontal=True,
                      label_visibility="collapsed",
                      key=f"tab_radio_{state_key}")
    st.markdown("</div>", unsafe_allow_html=True)
    new_val = "a" if chosen == opts[0] else "b"
    st.session_state[state_key] = new_val
    return new_val

# ---------------------------------------------------------------------------
# LOGIN PAGE
# ---------------------------------------------------------------------------
def render_login():
    lang = st.session_state.get("lang", "BM")

    # Language toggle at very top
    c_l, c_r = st.columns([5, 1])
    with c_r:
        lang_sel = st.radio("", ["BM", "EN"], horizontal=True,
                            index=0 if lang == "BM" else 1,
                            key="login_lang_radio",
                            label_visibility="collapsed")
        if lang_sel != lang:
            st.session_state.lang = lang_sel
            st.rerun()

    # Split layout: hero | form
    col_hero, col_form = st.columns([1, 1], gap="large")

    with col_hero:
        st.markdown(f"""
        <div class="login-hero">
            <div style="font-size:52px;margin-bottom:16px">🛡️</div>
            <h1 style="font-size:34px;font-weight:900;color:#fff;margin:0;line-height:1.1;letter-spacing:-0.02em">
                JN RESOLUSI
            </h1>
            <p style="color:#C41E3A;font-weight:700;letter-spacing:0.12em;font-size:12px;margin:10px 0 20px;text-transform:uppercase">
                Sistem Audit Pintar MOE
            </p>
            <p style="color:#6B7C93;font-size:13px;line-height:1.8;margin-bottom:28px">
                {t("login_brand_desc")}
            </p>
            <div class="feat-item"><span class="feat-dot"></span>{t("login_feat_a")}</div>
            <div class="feat-item"><span class="feat-dot"></span>{t("login_feat_b")}</div>
            <div class="feat-item"><span class="feat-dot"></span>{t("login_feat_c")}</div>
            <p style="margin-top:28px;font-size:11px;color:#2D3748">
                {t("login_footer")}
            </p>
        </div>
        """, unsafe_allow_html=True)

    with col_form:
        st.markdown('<div class="login-form-card">', unsafe_allow_html=True)
        st.markdown(f"### {t('login_title')}")
        st.info(t("login_domain"), icon="🔒")

        with st.form("login_form"):
            email    = st.text_input(t("login_email"),    placeholder=t("admin_ph_email"))
            password = st.text_input(t("login_password"), type="password", placeholder="••••••••")
            submitted = st.form_submit_button(t("login_btn"), type="primary", use_container_width=True)

            if submitted:
                if not email or not password:
                    st.error(t("login_empty"))
                else:
                    user = login_user(email, password)
                    if user:
                        st.session_state.user = user
                        st.rerun()
                    else:
                        st.error(t("login_fail"))

        st.markdown("</div>", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------
def render_sidebar() -> None:
    user = st.session_state.user
    with st.sidebar:
        # ── Brand ──────────────────────────────────
        st.markdown(f"""
        <div style="display:flex;align-items:center;gap:10px;padding:8px 4px 16px">
            <div style="background:#C41E3A;width:36px;height:36px;border-radius:8px;
                        display:flex;align-items:center;justify-content:center;font-size:18px">🛡️</div>
            <div>
                <div style="font-weight:800;font-size:14px;color:#fff;line-height:1.2">JN RESOLUSI</div>
                <div style="font-size:9px;color:#3B4A63;letter-spacing:0.1em;text-transform:uppercase">
                    Sistem Audit Pintar MOE
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # ── Language toggle ─────────────────────────
        lang = st.session_state.get("lang", "BM")
        lang_sel = st.radio("", ["BM", "EN"], horizontal=True,
                            index=0 if lang == "BM" else 1,
                            key="sidebar_lang_radio",
                            label_visibility="collapsed")
        if lang_sel != lang:
            st.session_state.lang = lang_sel
            st.rerun()

        st.divider()

        # ── Nav: MONITORING ─────────────────────────
        st.markdown(f'<div class="nav-group">{t("nav_monitoring")}</div>', unsafe_allow_html=True)
        _nav_btn("nav_dashboard", "dashboard")
        _nav_btn("nav_cases",     "cases")

        # ── Nav: DATA INPUT ─────────────────────────
        st.markdown(f'<div class="nav-group">{t("nav_data_input")}</div>', unsafe_allow_html=True)
        if require_role("admin", "penyelaras_jn"):
            _nav_btn("nav_data_sub", "data_input")

        # ── Nav: SYSTEM ─────────────────────────────
        st.markdown(f'<div class="nav-group">{t("nav_system")}</div>', unsafe_allow_html=True)
        _nav_btn("nav_users", "user_management", role_required=("admin",))
        _nav_btn("nav_info",  "system_info")

        st.divider()

        # ── Quick demo ingest ───────────────────────
        if require_role("admin", "penyelaras_jn"):
            st.markdown(f"<div class='nav-group'>{t('nav_quick')}</div>", unsafe_allow_html=True)
            for label in ["Ekstrem DI", "Teruk DI", "Selaras"]:
                if st.button(f"⚡ Demo: {label}", use_container_width=True, key=f"demo_{label}"):
                    st.session_state.demo_payload   = DEMO_PAYLOADS[label]
                    st.session_state.current_page   = "data_input"
                    st.session_state.data_tab       = "a"
                    st.rerun()

        st.divider()

        # ── Stats ───────────────────────────────────
        db       = get_db()
        total    = db.execute("SELECT COUNT(*) FROM discrepancy_log").fetchone()[0]
        anomalies= db.execute("SELECT COUNT(*) FROM discrepancy_log WHERE anomaly_detected=1").fetchone()[0]
        st.markdown(f"""
        <div style="font-size:11px;color:#4A5568;padding:4px 8px">
            <div style="font-weight:700;color:#6B7C93;margin-bottom:6px">{t('stat_title')}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span>{t('stat_agents')}</span><span style="color:#0F6B3C;font-weight:700">3 ✓</span>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:4px">
                <span>{t('stat_cases')}</span><span style="color:#fff;font-weight:700">{total}</span>
            </div>
            <div style="display:flex;justify-content:space-between">
                <span>{t('stat_anomalies')}</span><span style="color:#C41E3A;font-weight:700">{anomalies}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── User info + logout ──────────────────────
        st.markdown(f"""
        <div style="font-size:11px;color:#6B7C93;padding:4px 8px;margin-bottom:8px">
            <div style="font-family:monospace;color:#9CA3AF;margin-bottom:4px">{user['email']}</div>
            <span style="background:#1E2A45;color:#4338CA;padding:2px 8px;border-radius:10px;
                         font-size:10px;font-weight:700">{role_label(user['role'])}</span>
        </div>
        """, unsafe_allow_html=True)

        if st.sidebar.button(f"🚪 {t('btn_logout')}", use_container_width=True, key="logout_btn"):
            st.session_state.user = None
            st.session_state.pop("db_conn", None)
            st.rerun()

# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------
def render_dashboard():
    section_header(t("dash_section"))
    st.title(t("dash_title"))
    st.caption(t("dash_caption"))

    db     = get_db()
    cases  = db.execute("SELECT * FROM discrepancy_log ORDER BY timestamp DESC").fetchall()
    total  = len(cases)
    anomalies = sum(1 for c in cases if c["anomaly_detected"])
    extreme   = sum(1 for c in cases if c["di_classification"] in ("EXTREME_DISCREPANCY","SEVERE_DISCREPANCY"))
    aligned   = sum(1 for c in cases if c["di_classification"] == "DATA_ALIGNED")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(t("dash_total"),   total)
    c2.metric(t("dash_anomaly"), anomalies,
              delta=f"{int(anomalies/total*100)}%" if total else None,
              help=t("tip_anomaly"))
    c3.metric(t("dash_extreme"), extreme,  help=t("tip_extreme"))
    c4.metric(t("dash_aligned"), aligned,  help=t("tip_di"))

    st.divider()
    st.subheader(t("dash_recent"))

    if not cases:
        st.info(t("dash_empty"))
    else:
        import json as _json
        for c in cases[:8]:
            color = DI_COLORS.get(c["di_classification"], "#6B7C93")
            flags = _json.loads(c["flags"]) if c["flags"] else []
            badge = t("anomaly_yes") if c["anomaly_detected"] else t("anomaly_no")

            with st.container():
                st.markdown(f'<div class="case-row">', unsafe_allow_html=True)
                cols = st.columns([4, 1, 1, 1])
                cols[0].markdown(f"""
                <span style="font-family:monospace;font-size:10px;color:#C41E3A">{c['case_id']}</span><br>
                <span style="font-weight:600;color:#e2e8f0">{c['school_id']} — {c['school_name'] or '—'}</span>
                """, unsafe_allow_html=True)
                cols[1].markdown(f"<span style='font-size:20px;font-weight:800;color:{color}'>{c['discrepancy_index']:.4f}</span>", unsafe_allow_html=True)
                cols[2].markdown(f"<span style='font-size:12px'>{badge}</span>", unsafe_allow_html=True)
                if cols[3].button(t("dash_brief_btn"), key=f"dbrief_{c['case_id']}"):
                    st.session_state.view_case_id = c["case_id"]
                    st.session_state.current_page = "cases"
                    st.session_state.cases_tab    = "b"
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    # DI Distribution chart
    st.divider()
    st.subheader(t("dash_di_dist"))
    labels = t("dash_di_labels")
    dist   = {
        labels[0]: sum(1 for c in cases if c["di_classification"] == "DATA_ALIGNED"),
        labels[1]: sum(1 for c in cases if c["di_classification"] == "MINOR_DISCREPANCY"),
        labels[2]: sum(1 for c in cases if c["di_classification"] == "MODERATE_DISCREPANCY"),
        labels[3]: sum(1 for c in cases if c["di_classification"] == "SEVERE_DISCREPANCY"),
        labels[4]: sum(1 for c in cases if c["di_classification"] == "EXTREME_DISCREPANCY"),
    }
    if sum(dist.values()) > 0:
        st.bar_chart(pd.DataFrame({"n": dist}), use_container_width=True)

# ---------------------------------------------------------------------------
# DATA SUBMISSION (Hantar Payload + Muat Naik CSV)
# ---------------------------------------------------------------------------
def render_data_input():
    section_header(t("sub_section"))
    st.title(t("sub_title"))
    st.caption(t("sub_caption"))

    tab = _tab_radio("tab_payload", "tab_csv", "data_tab")

    st.divider()
    if tab == "a":
        _render_ingest_body()
    else:
        _render_csv_body()

def _render_ingest_body():
    if not require_role("admin", "penyelaras_jn"):
        st.warning(t("sub_no_access"))
        return

    demo = st.session_state.pop("demo_payload", None)
    col_form, col_ref = st.columns([2, 1])

    with col_form:
        with st.form("ingest_form"):
            source_id = st.text_input(t("sub_src_id"),
                                      value=demo["source_system_id"] if demo else "PRESTIJ-BULLY-03",
                                      help=t("tip_src_id"))
            source_name = st.text_input(t("sub_src_name"),
                                        value=demo["source_system_name"] if demo else "AI-Powered Bully Detection Agent")

            db_audit  = get_db()
            schools   = db_audit.execute("SELECT school_id, school_name FROM jn_audit_records ORDER BY school_id").fetchall()
            sch_opts  = {f"{s['school_id']} — {s['school_name']}": s["school_id"] for s in schools}
            sch_opts["UNKNOWN99 — Sekolah Tidak Dikenali"] = "UNKNOWN99"

            target_school = demo["school_id"] if demo else "SMK002"
            default_lbl   = next((k for k, v in sch_opts.items() if v == target_school), list(sch_opts.keys())[0])
            selected_lbl  = st.selectbox(t("sub_school"), list(sch_opts.keys()),
                                         index=list(sch_opts.keys()).index(default_lbl))
            school_id     = sch_opts[selected_lbl]

            op_score = st.slider(t("sub_score"), 0.0, 100.0,
                                 demo["operational_score"] if demo else 92.0, 0.5,
                                 help=t("tip_op_score"))
            raw_text = st.text_area(t("sub_text"),
                                    value=demo["raw_text"] if demo else "Terdapat laporan kritikal berhubung salah guna kuasa...",
                                    height=120, help=t("tip_raw_text"))

            submitted = st.form_submit_button(t("sub_btn"), type="primary", use_container_width=True)
            if submitted:
                with st.spinner(t("sub_spin")):
                    result = run_agent_pipeline(school_id, source_id, source_name, raw_text, op_score)
                st.session_state.last_ingest = result
                st.success(f"{t('sub_ok')}: **{result['case_id']}**")
                if result["anomaly_detected"]:
                    st.warning(f"{t('sub_anomaly')}: {result['discrepancy_index']:.4f}")
                st.rerun()

    with col_ref:
        st.markdown(f"**{t('sub_formula')}**")
        st.latex(r"DI = \frac{|Audit - Op|}{100}")
        st.caption(t("sub_di_range"))

        st.markdown(f"**{t('sub_classify')}**")
        for th, lbl in [("🔴 ≥ 0.75", "EKSTREM"), ("🟠 ≥ 0.50", "TERUK"),
                        ("🟡 ≥ 0.25", "SEDERHANA"), ("🔵 ≥ 0.10", "MINOR"), ("🟢 < 0.10", "SELARAS")]:
            st.markdown(f"`{th}` **{lbl}**")

        st.markdown(f"**{t('sub_audit_ref')}**")
        audit_row = get_db().execute("SELECT * FROM jn_audit_records WHERE school_id=?", (school_id,)).fetchone()
        if audit_row:
            st.markdown(f"""
            **{audit_row['school_name']}** ({audit_row['state']})
            - SKPMG2: `{audit_row['skpmg2_score']}`
            - Gred: `{audit_row['facility_gred']}`
            - Kantin: `{audit_row['canteen_hygiene_score']}`
            - Risiko: `{audit_row['integrity_risk_index']:.3f}`
            """)

    if "last_ingest" in st.session_state:
        r     = st.session_state.last_ingest
        color = DI_COLORS.get(r["di_classification"], "#6B7C93")
        st.divider()
        st.subheader(t("sub_result"))
        c1, c2, c3, c4 = st.columns(4)
        c1.metric(t("sub_di"),    f"{r['discrepancy_index']:.4f}", help=t("tip_di"))
        c2.metric(t("sub_class"), r["di_classification"].replace("_"," "))
        c3.metric(t("sub_flags"), str(r["flags_count"]),            help=t("tip_flags"))
        c4.metric(t("sub_alert"), r["alert_level"])
        if st.button(t("sub_view_brief"), type="primary"):
            st.session_state.view_case_id = r["case_id"]
            st.session_state.current_page = "cases"
            st.session_state.cases_tab    = "b"
            st.rerun()

def _render_csv_body():
    if not require_role("admin", "penyelaras_jn"):
        st.warning(t("csv_no_access"))
        return

    col_up, col_info = st.columns([2, 1])

    with col_up:
        uploaded = st.file_uploader(t("csv_select"), type=["csv"], label_visibility="collapsed")
        if uploaded:
            df = pd.read_csv(uploaded)
            st.markdown(f"**{t('csv_preview')}** — {len(df)} {t('csv_rows')}")
            st.dataframe(df.head(), use_container_width=True, hide_index=True)

            if st.button(t("csv_process"), type="primary", use_container_width=True):
                results, errors = [], []
                progress = st.progress(0)
                status   = st.empty()

                for i, row in df.iterrows():
                    try:
                        school = str(row.get("school", ""))
                        rep_cols = [c for c in df.columns if "_reported" in str(c)]
                        vals     = [float(row[c]) for c in rep_cols if pd.notna(row.get(c))]
                        op_score = sum(vals) / len(vals) if vals else 50.0
                        raw_parts = [f"{c}: {row[c]}" for c in df.columns if c != "school" and pd.notna(row.get(c))]
                        raw_text  = "; ".join(raw_parts[:5])
                        result = run_agent_pipeline(school, f"CSV-UPLOAD-{i+1:04d}", "CSV Bulk Upload", raw_text, op_score)
                        results.append({"Baris": i+1, "Sekolah": school,
                                        "Skor Op": f"{op_score:.1f}",
                                        "Skor DI": f"{result['discrepancy_index']:.4f}",
                                        "ID Kes": result["case_id"]})
                    except Exception as e:
                        errors.append({"Baris": i+1, "Ralat": str(e)})
                    progress.progress((i+1)/len(df))
                    status.text(f"{t('csv_processing')} {i+1}/{len(df)}")

                progress.empty(); status.empty()
                if results:
                    st.success(f"✅ {len(results)} {t('csv_ok')}")
                    st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                if errors:
                    st.error(f"❌ {len(errors)} {t('csv_err')}")
                    st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

    with col_info:
        st.markdown(f"**{t('csv_format')}**")
        st.code("school,cleanliness_reported,cleanliness_actual,\nSMK002,90,28,85,30", language=None)
        st.caption("Op Score = purata *_reported")
        st.caption("DI = |Audit − Op| / 100")
        st.markdown(f"**{t('csv_access')}**")
        st.markdown(f"- {t('role_admin')}\n- {t('role_penyelaras')}")

# ---------------------------------------------------------------------------
# CASES & BRIEF (combined)
# ---------------------------------------------------------------------------
def render_cases_combined():
    section_header(t("cases_section"))
    st.title(t("cases_title"))
    st.caption(t("cases_caption"))

    tab = _tab_radio("tab_log", "tab_brief", "cases_tab")

    st.divider()
    if tab == "a":
        _render_case_log_body()
    else:
        _render_brief_body()

def _render_case_log_body():
    db    = get_db()
    cases = db.execute("SELECT * FROM discrepancy_log ORDER BY timestamp DESC").fetchall()

    c_refresh, c_del = st.columns([1, 5])
    with c_refresh:
        if st.button(t("cases_refresh")):
            st.rerun()
    with c_del:
        if require_role("admin"):
            if st.button(t("cases_del_all"), type="secondary"):
                db.execute("DELETE FROM discrepancy_log")
                db.execute("DELETE FROM matrix_payloads")
                db.commit()
                st.rerun()

    if not cases:
        st.info(t("cases_empty"))
        return

    df_data = []
    for c in cases:
        df_data.append({
            t("cases_col_id"):     c["case_id"],
            t("cases_col_school"): f"{c['school_id']} — {c['school_name']}",
            t("cases_col_di"):     f"{c['discrepancy_index']:.4f}",
            t("cases_col_class"):  c["di_classification"].replace("_"," "),
            t("cases_col_anomaly"):t("anomaly_yes") if c["anomaly_detected"] else t("anomaly_no"),
            t("cases_col_time"):   c["timestamp"][:19],
        })
    df = pd.DataFrame(df_data)

    event = st.dataframe(df, use_container_width=True, hide_index=True,
                         on_select="rerun", selection_mode="single-row")

    if event.selection and len(event.selection["rows"]) > 0:
        row_idx = event.selection["rows"][0]
        case_id = cases[row_idx]["case_id"]
        if st.button(f"{t('brief_view_btn')} — {case_id}", type="primary"):
            st.session_state.view_case_id = case_id
            st.session_state.cases_tab    = "b"
            st.rerun()

def _render_brief_body():
    import json as _json
    case_id = st.session_state.get("view_case_id")

    if not case_id:
        st.info(t("brief_prompt"))
        return

    db   = get_db()
    case = db.execute("SELECT * FROM discrepancy_log WHERE case_id=?", (case_id,)).fetchone()

    if not case:
        st.error("Kes tidak dijumpai.")
        return

    color       = DI_COLORS.get(case["di_classification"], "#6B7C93")
    flags       = _json.loads(case["flags"]) if case["flags"] else []
    agent_c_data= _json.loads(case["agent_c_result"]) if case["agent_c_result"] else {}

    st.markdown(f"""
    <div class="brief-header" style="border-left:4px solid {color}">
        <div style="font-size:10px;color:#C41E3A;letter-spacing:0.16em;font-weight:700;margin-bottom:4px">
            ARAHAN EKSEKUTIF — AI-COMPLAINT-MOE
        </div>
        <div style="font-size:22px;font-weight:800;color:#fff">{case['school_name'] or '—'}</div>
        <div style="font-family:monospace;font-size:11px;color:#6B7C93;margin-top:4px">
            {case['case_id']} · {case['state'] or 'N/A'} · {case['timestamp'][:19]}
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.markdown(f"**{t('brief_status')}:** {agent_c_data.get('alert_status', 'N/A')}")

    with st.expander(t("brief_school"), expanded=True):
        c1, c2 = st.columns(2)
        c1.markdown(f"**{t('brief_code')}:** `{case['school_id']}`")
        c1.markdown(f"**{t('brief_source')}:** {case['source_system_name']}")
        c2.metric(t("brief_audit"), f"{case['audit_score_reference']:.2f}", help=t("tip_skpmg2"))
        c2.metric(t("brief_op"),    f"{case['operational_score_reported']:.2f}", help=t("tip_op_score"))

    with st.expander(t("brief_di"), expanded=True):
        c1, c2 = st.columns(2)
        c1.metric(t("brief_di_score"), f"{case['discrepancy_index']:.4f}", help=t("tip_di"))
        c1.metric(t("brief_delta"),    f"{case['score_delta']:+.2f}")
        c2.metric(t("brief_class"),    case["di_classification"].replace("_"," "))
        c2.metric(t("brief_conf"),     f"{int(case['confidence_score']*100) if case['confidence_score'] else 0}%",
                  help=t("tip_confidence"))
        di_pct = min(100, case["discrepancy_index"] * 100)
        st.progress(di_pct / 100, text=f"DI: {case['discrepancy_index']:.4f} / 1.0000")

    if flags:
        with st.expander(f"{t('brief_flags')} ({len(flags)})", expanded=True):
            for f in flags:
                st.markdown(f"🔴 {f}")

    enf = agent_c_data.get("enforcement", [])
    if enf:
        with st.expander(f"{t('brief_enforce')} ({len(enf)})", expanded=True):
            for i, action in enumerate(enf, 1):
                st.markdown(f"**{i}.** {action}")

    policy = agent_c_data.get("policy", [])
    if policy:
        with st.expander(f"{t('brief_policy')} ({len(policy)})", expanded=True):
            for p in policy:
                ref    = p.get("legal_reference", "") if isinstance(p, dict) else ""
                action = p.get("recommended_action", p) if isinstance(p, dict) else str(p)
                st.markdown(f"📜 **{ref}** — {action}")

    directive = agent_c_data.get("directive", "")
    if directive:
        with st.expander(t("brief_directive")):
            st.text(directive)

# ---------------------------------------------------------------------------
# USER MANAGEMENT (CRUD)
# ---------------------------------------------------------------------------
def render_admin():
    if not require_role("admin"):
        st.warning(t("admin_no_access"))
        return

    section_header(t("admin_section"))
    st.title(t("admin_title"))
    st.caption(t("admin_caption"))

    db                 = get_db()
    current_user_email = st.session_state.user["email"]

    col_users, col_add = st.columns([2, 1])

    with col_users:
        st.subheader(t("admin_list"))
        users = db.execute("SELECT * FROM users ORDER BY created_at DESC").fetchall()

        if not users:
            st.info(t("admin_empty"))
        else:
            hdr = st.columns([3, 2, 1, 1, 1])
            hdr[0].markdown(f"**{t('admin_col_email')}**")
            hdr[1].markdown(f"**{t('admin_col_role')}**")
            hdr[2].markdown(f"**{t('admin_col_status')}**")
            hdr[3].markdown("**✏️**")
            hdr[4].markdown("**🗑️**")
            st.divider()

            for u in users:
                is_self = u["email"] == current_user_email
                row     = st.columns([3, 2, 1, 1, 1])
                badge   = t("admin_active") if u["is_active"] else t("admin_inactive")
                row[0].markdown(f"<span style='font-size:13px'>{u['email']}</span>", unsafe_allow_html=True)
                row[1].markdown(role_label(u["role"]))
                row[2].markdown(badge)
                if row[3].button("✏️", key=f"edit_{u['id']}", help="Edit"):
                    st.session_state.edit_user_id = u["id"]
                    st.session_state.pop("delete_user_id", None)
                    st.rerun()
                if is_self:
                    row[4].markdown("—")
                else:
                    if row[4].button("🗑️", key=f"del_{u['id']}", help="Padam"):
                        st.session_state.delete_user_id = u["id"]
                        st.session_state.pop("edit_user_id", None)
                        st.rerun()

        # Edit form
        edit_id = st.session_state.get("edit_user_id")
        if edit_id:
            tgt = db.execute("SELECT * FROM users WHERE id=?", (edit_id,)).fetchone()
            if tgt:
                st.divider()
                st.markdown(f"#### {t('admin_edit_title')}: `{tgt['email']}`")
                with st.form("edit_user_form"):
                    upd_email  = st.text_input(t("admin_email"), value=tgt["email"])
                    upd_role   = st.selectbox(t("admin_role"), ROLE_KEYS,
                                              index=ROLE_KEYS.index(tgt["role"]) if tgt["role"] in ROLE_KEYS else 0,
                                              format_func=role_label)
                    upd_active = st.toggle(t("admin_active_lbl"), value=bool(tgt["is_active"]))
                    upd_pass   = st.text_input(t("admin_new_pass"), type="password",
                                               placeholder=t("admin_ph_pass"))
                    c_s, c_c   = st.columns(2)
                    save   = c_s.form_submit_button(t("admin_save"), type="primary", use_container_width=True)
                    cancel = c_c.form_submit_button(t("admin_cancel"), use_container_width=True)

                if save:
                    if not upd_email or "@" not in upd_email:
                        st.error(t("admin_err_email"))
                    elif upd_pass and len(upd_pass) < 6:
                        st.error(t("admin_err_pass"))
                    else:
                        if upd_pass:
                            db.execute("UPDATE users SET email=?,role=?,is_active=?,password_hash=? WHERE id=?",
                                       (upd_email, upd_role, int(upd_active), pwd_context.hash(upd_pass), edit_id))
                        else:
                            db.execute("UPDATE users SET email=?,role=?,is_active=? WHERE id=?",
                                       (upd_email, upd_role, int(upd_active), edit_id))
                        db.commit()
                        st.session_state.pop("edit_user_id", None)
                        st.success(t("admin_updated").format(upd_email))
                        st.rerun()
                if cancel:
                    st.session_state.pop("edit_user_id", None)
                    st.rerun()

        # Delete confirmation
        del_id = st.session_state.get("delete_user_id")
        if del_id:
            tgt = db.execute("SELECT * FROM users WHERE id=?", (del_id,)).fetchone()
            if tgt:
                st.divider()
                st.warning(t("admin_del_warn").format(tgt["email"]))
                c_yes, c_no = st.columns(2)
                if c_yes.button(t("admin_del_btn"), type="primary", use_container_width=True, key="confirm_del"):
                    db.execute("DELETE FROM users WHERE id=?", (del_id,))
                    db.commit()
                    st.session_state.pop("delete_user_id", None)
                    st.success(t("admin_deleted").format(tgt["email"]))
                    st.rerun()
                if c_no.button(t("admin_cancel"), use_container_width=True, key="cancel_del"):
                    st.session_state.pop("delete_user_id", None)
                    st.rerun()

    with col_add:
        st.subheader(t("admin_add"))
        with st.form("create_user_form"):
            new_email    = st.text_input(t("admin_email"),    placeholder=t("admin_ph_email"))
            new_password = st.text_input(t("admin_password"), type="password", placeholder=t("admin_ph_pass"))
            new_role     = st.selectbox(t("admin_role"), ROLE_KEYS, format_func=role_label)
            submitted    = st.form_submit_button(t("admin_create"), type="primary", use_container_width=True)

            if submitted:
                if not new_email or len(new_password) < 6:
                    st.error(t("admin_err_empty"))
                elif "@" not in new_email:
                    st.error(t("admin_err_email"))
                else:
                    try:
                        db.execute("INSERT INTO users (id,email,password_hash,role) VALUES (?,?,?,?)",
                                   (str(uuid.uuid4()), new_email, pwd_context.hash(new_password), new_role))
                        db.commit()
                        st.success(t("admin_created").format(new_email))
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error(t("admin_exists"))

        st.markdown(f"**{t('admin_roles_title')}**")
        st.markdown(t("admin_roles_desc"))

# ---------------------------------------------------------------------------
# SYSTEM INFO
# ---------------------------------------------------------------------------
def render_system():
    section_header(t("sys_section"))
    st.title(t("sys_title"))
    st.caption(t("sys_caption"))

    c1, c2 = st.columns(2)

    with c1:
        st.subheader(t("sys_arch"))
        for title, key in [
            ("**Ejen A** — Semantic Ingestion & Mapping",     "tip_agent_a"),
            ("**Ejen B** — Cross-Examination & Anomaly",      "tip_agent_b"),
            ("**Ejen C** — Executive Briefing & Policy",      "tip_agent_c"),
        ]:
            with st.container():
                st.markdown(title)
                st.caption(t(key))
                st.markdown("")

    with c2:
        st.subheader(t("sys_stack"))
        st.markdown("""
        **Backend** — Python 3.9+ / Streamlit
        **Database** — SQLite (`~/.jn_engine/jn_engine.db`)
        **Auth** — JWT (python-jose) + sha256_crypt (passlib)
        **Deploy** — Streamlit Cloud (auto-deploy on push)
        """)

    st.divider()
    st.subheader(t("sys_deploy"))
    st.markdown("""
    🚀 Dijalankan di **Streamlit Cloud** — satu platform untuk backend + frontend.

    | Layer | Platform | URL |
    |-------|----------|-----|
    | App (BE+FE+DB) | Streamlit Cloud | `prestij25-jn-engine.streamlit.app` |
    | Source | GitHub | `gunbladeii/prestij25-jn-engine` (`main`) |
    """)

    st.divider()
    st.subheader("DI Classification Thresholds")
    for di_range, cls, color in [
        ("≥ 0.75", "EXTREME DISCREPANCY",  "#C41E3A"),
        ("≥ 0.50", "SEVERE DISCREPANCY",   "#C2410C"),
        ("≥ 0.25", "MODERATE DISCREPANCY", "#B45309"),
        ("≥ 0.10", "MINOR DISCREPANCY",    "#1D4ED8"),
        ("< 0.10", "DATA ALIGNED",         "#0F6B3C"),
    ]:
        st.markdown(
            f"<span style='font-family:monospace;font-size:13px'>`{di_range}`</span> "
            f"<span style='background:{color};color:#fff;padding:2px 8px;border-radius:4px;"
            f"font-size:11px;font-weight:700'>{cls}</span>",
            unsafe_allow_html=True
        )

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    inject_css()

    # Session state defaults
    if "lang"         not in st.session_state: st.session_state.lang         = "BM"
    if "current_page" not in st.session_state: st.session_state.current_page = "dashboard"
    if "cases_tab"    not in st.session_state: st.session_state.cases_tab    = "a"
    if "data_tab"     not in st.session_state: st.session_state.data_tab     = "a"

    # Initialise DB
    if "db_conn" not in st.session_state:
        st.session_state.db_conn = init_db()

    # Auth gate
    if not st.session_state.get("user"):
        render_login()
        return

    render_sidebar()

    page_map = {
        "dashboard":       render_dashboard,
        "cases":           render_cases_combined,
        "data_input":      render_data_input,
        "user_management": render_admin,
        "system_info":     render_system,
    }

    try:
        render_fn = page_map.get(st.session_state.current_page, render_dashboard)
        render_fn()
    except Exception as e:
        st.error(f"⚠️ Ralat sistem: {str(e)}")
        st.info("Refresh halaman atau hubungi admin.")

if __name__ == "__main__":
    main()

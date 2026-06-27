"""
JN Resolusi — Smart Cross-Reference & Audit Engine (Streamlit Edition)
MoE Agentic AI — PRESTIJ Programme 2025
"""

import sqlite3
import os
import uuid
from datetime import datetime, timedelta
from typing import Optional

import io

import streamlit as st
import pandas as pd
from passlib.context import CryptContext
from jose import jwt, JWTError

try:
    from docx import Document as DocxDocument
    _DOCX_OK = True
except ImportError:
    _DOCX_OK = False

try:
    from pypdf import PdfReader
    _PDF_OK = True
except ImportError:
    _PDF_OK = False

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

# Google Drive integration
GDRIVE_FOLDER_ID   = "1Uum9rN7NnRAheFkGLwt1SDganainncAP"
GDRIVE_FOLDER_URL  = "https://drive.google.com/drive/folders/1Uum9rN7NnRAheFkGLwt1SDganainncAP"
GDRIVE_SCOPES      = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

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
        "sub_caption":        "Hantar data melalui payload manual atau muat naik fail (CSV, TXT, DOCX, PDF).",
        "tab_payload":        "📤  Hantar Payload",
        "tab_csv":            "📁  Muat Naik Fail",
        "tab_gdrive":         "📡  Google Drive API",
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
        "csv_select":         "Pilih fail (CSV, TXT, DOCX, PDF)",
        "csv_preview":        "Pratonton",
        "csv_rows":           "baris",
        "csv_process":        "🚀 Proses CSV",
        "csv_processing":     "Memproses...",
        "csv_ok":             "berjaya diproses",
        "csv_err":            "ralat",
        "csv_no_access":      "Anda tiada akses untuk muat naik fail.",
        "csv_format":         "Format CSV",
        "csv_access":         "Akses",
        "csv_map_title":      "📋 Langkah 1 — Padankan Lajur CSV",
        "csv_map_school":     "Lajur → Kod Sekolah",
        "csv_map_score":      "Lajur → Skor Operasi",
        "csv_map_text":       "Lajur → Teks Laporan (pilihan)",
        "csv_map_none":       "(tiada / guna lalai)",
        "csv_map_preview_title": "📊 Langkah 2 — Semak Pratonton Sebelum Hantar",
        "csv_map_confirm":    "✅ Sahkan & Hantar ke Enjin",
        "csv_map_warn":       "⚠️ Sila pilih lajur sekolah dan skor sebelum meneruskan.",
        "csv_map_default_score": "Skor lalai (jika tiada lajur skor)",
        "file_doc_info":      "📄 Fail teks diekstrak sebagai **1 kes**. Lengkapi butiran di bawah sebelum hantar.",
        "file_doc_school":    "Kod Sekolah",
        "file_doc_score":     "Skor Operasi",
        "file_doc_src":       "ID Sistem Sumber",
        "file_doc_btn":       "🚀 Hantar sebagai 1 Kes",
        "file_doc_ai_notice": "🤖 Skor operasi akan dianggar secara automatik oleh AI berdasarkan kandungan dokumen.",
        "file_doc_no_text":   "⚠️ Fail tidak mengandungi teks yang boleh diekstrak.",
        "file_doc_chars":     "aksara diekstrak",
        "file_doc_preview":   "Pratonton Teks",
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
        # Nav tooltips
        "tip_nav_dashboard":  "Papan pemuka utama — statistik enjin, kes terkini dan taburan DI.",
        "tip_nav_cases":      "Log semua kes yang telah diproses beserta ringkasan eksekutif.",
        "tip_nav_data":       "Hantar payload baharu atau muat naik fail CSV / DOCX / PDF untuk dianalisis.",
        "tip_nav_users":      "Urus akaun pengguna sistem (hanya Admin).",
        "tip_nav_info":       "Lihat seni bina sistem, tindanan teknologi dan maklumat deployment.",
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
        "sub_caption":        "Submit data via manual payload or bulk file upload (CSV, TXT, DOCX, PDF).",
        "tab_payload":        "📤  Submit Payload",
        "tab_csv":            "📁  Upload File",
        "tab_gdrive":         "📡  Google Drive API",
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
        "csv_select":         "Select file (CSV, TXT, DOCX, PDF)",
        "csv_preview":        "Preview",
        "csv_rows":           "rows",
        "csv_process":        "🚀 Process CSV",
        "csv_processing":     "Processing...",
        "csv_ok":             "successfully processed",
        "csv_err":            "errors",
        "csv_no_access":      "You do not have access to upload files.",
        "csv_format":         "CSV Format",
        "csv_access":         "Access",
        "csv_map_title":      "📋 Step 1 — Map CSV Columns",
        "csv_map_school":     "Column → School Code",
        "csv_map_score":      "Column → Operational Score",
        "csv_map_text":       "Column → Report Text (optional)",
        "csv_map_none":       "(none / use default)",
        "csv_map_preview_title": "📊 Step 2 — Review Before Submitting",
        "csv_map_confirm":    "✅ Confirm & Submit to Engine",
        "csv_map_warn":       "⚠️ Please select a school column and a score column before continuing.",
        "csv_map_default_score": "Default score (if no score column)",
        "file_doc_info":      "📄 Text extracted as **1 case**. Complete the details below before submitting.",
        "file_doc_school":    "School Code",
        "file_doc_score":     "Operational Score",
        "file_doc_src":       "Source System ID",
        "file_doc_btn":       "🚀 Submit as 1 Case",
        "file_doc_ai_notice": "🤖 Operational score will be estimated automatically by AI from document content.",
        "file_doc_no_text":   "⚠️ File contains no extractable text.",
        "file_doc_chars":     "characters extracted",
        "file_doc_preview":   "Text Preview",
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
        # Nav tooltips
        "tip_nav_dashboard":  "Main dashboard — engine statistics, recent cases and DI distribution.",
        "tip_nav_cases":      "Log of all processed cases with their executive briefs.",
        "tip_nav_data":       "Submit a new payload or upload CSV / DOCX / PDF for analysis.",
        "tip_nav_users":      "Manage system user accounts (Admin only).",
        "tip_nav_info":       "View system architecture, technology stack and deployment info.",
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
    /* ═══════════════════════════════════════════════════════════════
       NEURAL AUDIT GRID — JN Resolusi Design System v2
       Professional · Educational · Statistical · Technology
    ═══════════════════════════════════════════════════════════════ */

    /* ── Base & deep-space background ───────────────────────────── */
    [data-testid="stAppViewContainer"] {
        background: #0D1B35 !important;
        background-image:
            linear-gradient(rgba(56,189,248,0.035) 1px, transparent 1px),
            linear-gradient(90deg, rgba(56,189,248,0.035) 1px, transparent 1px),
            radial-gradient(ellipse 80% 50% at 50% -5%, rgba(59,130,246,0.14) 0%, transparent 70%);
        background-size: 52px 52px, 52px 52px, 100% 100%;
    }
    [data-testid="stAppViewContainer"] > .main { background: transparent !important; }
    .main .block-container { padding-top: 1.8rem !important; padding-bottom: 3rem !important; }

    /* ── Sidebar shell ───────────────────────────────────────────── */
    section[data-testid="stSidebar"] > div:first-child {
        background: rgba(1,4,13,0.98) !important;
        border-right: 2px solid rgba(56,189,248,0.14) !important;
        padding: 1rem 0.7rem !important;
        box-shadow: 4px 0 24px rgba(0,0,0,0.45) !important;
    }

    /* Nav group labels */
    .nav-group {
        font-size: 9px; font-weight: 800; letter-spacing: 0.2em;
        color: rgba(56,189,248,0.35); padding: 16px 10px 5px;
        text-transform: uppercase;
    }

    /* Inactive nav buttons — glassmorphism */
    section[data-testid="stSidebar"] [data-testid="baseButton-secondary"] {
        background: transparent !important;
        border: 1px solid transparent !important;
        border-radius: 10px !important;
        color: #475569 !important;
        text-align: left !important; font-size: 13px !important;
        font-weight: 500 !important; padding: 8px 12px !important;
        transition: all 0.18s ease !important;
        box-shadow: none !important; margin-bottom: 2px !important;
    }
    section[data-testid="stSidebar"] [data-testid="baseButton-secondary"]:hover {
        background: rgba(56,189,248,0.05) !important;
        border-color: rgba(56,189,248,0.18) !important;
        color: #94A3B8 !important;
        box-shadow: 0 0 14px rgba(56,189,248,0.07) !important;
    }

    /* Active nav button — glowing glass */
    section[data-testid="stSidebar"] [data-testid="baseButton-primary"] {
        background: linear-gradient(135deg,
            rgba(37,99,235,0.22) 0%,
            rgba(8,145,178,0.14) 100%) !important;
        border: 1px solid rgba(56,189,248,0.38) !important;
        border-radius: 10px !important;
        color: #93C5FD !important;
        text-align: left !important; font-size: 13px !important;
        font-weight: 700 !important; padding: 8px 12px !important;
        box-shadow: 0 0 20px rgba(37,99,235,0.14),
                    inset 0 1px 0 rgba(255,255,255,0.06) !important;
        margin-bottom: 2px !important;
    }

    /* ── Main-area primary buttons — gradient + glow ─────────────── */
    .main [data-testid="baseButton-primary"],
    [data-testid="stForm"] [data-testid="baseButton-primary"] {
        background: linear-gradient(135deg, #2563EB 0%, #0891B2 100%) !important;
        border: none !important; border-radius: 10px !important;
        color: #fff !important; font-weight: 700 !important;
        letter-spacing: 0.02em !important;
        box-shadow: 0 4px 18px rgba(37,99,235,0.38),
                    0 0 30px rgba(37,99,235,0.12),
                    inset 0 1px 0 rgba(255,255,255,0.16) !important;
        transition: all 0.2s ease !important;
    }
    .main [data-testid="baseButton-primary"]:hover,
    [data-testid="stForm"] [data-testid="baseButton-primary"]:hover {
        box-shadow: 0 6px 28px rgba(37,99,235,0.55),
                    0 0 40px rgba(37,99,235,0.2),
                    inset 0 1px 0 rgba(255,255,255,0.2) !important;
        transform: translateY(-1px) !important;
    }

    /* ── Secondary buttons — glassmorphism ───────────────────────── */
    .main [data-testid="baseButton-secondary"] {
        background: rgba(8,15,35,0.7) !important;
        border: 1px solid rgba(56,189,248,0.14) !important;
        border-radius: 10px !important; color: #64748B !important;
        backdrop-filter: blur(10px) !important;
        transition: all 0.18s ease !important;
    }
    .main [data-testid="baseButton-secondary"]:hover {
        background: rgba(56,189,248,0.06) !important;
        border-color: rgba(56,189,248,0.3) !important;
        color: #94A3B8 !important;
        box-shadow: 0 0 16px rgba(56,189,248,0.08) !important;
    }

    /* ── Metric cards — glass panels ─────────────────────────────── */
    [data-testid="metric-container"] {
        background: rgba(6,12,30,0.88) !important;
        border: 1px solid rgba(56,189,248,0.12) !important;
        border-radius: 14px !important; padding: 20px 18px !important;
        backdrop-filter: blur(20px) !important;
        box-shadow: 0 0 28px rgba(59,130,246,0.04),
                    inset 0 1px 0 rgba(255,255,255,0.04) !important;
        transition: border-color 0.2s, box-shadow 0.2s !important;
    }
    [data-testid="metric-container"]:hover {
        border-color: rgba(56,189,248,0.25) !important;
        box-shadow: 0 0 22px rgba(56,189,248,0.09) !important;
    }
    [data-testid="stMetricLabel"] {
        color: #475569 !important; font-size: 10px !important;
        font-weight: 700 !important; letter-spacing: 0.1em !important;
        text-transform: uppercase !important;
    }
    [data-testid="stMetricValue"] {
        color: #E2E8F0 !important; font-weight: 800 !important;
    }

    /* ── Form inputs — glass fields ──────────────────────────────── */
    .stTextInput input, .stTextArea textarea, .stNumberInput input {
        background: rgba(6,12,30,0.85) !important;
        border: 1px solid rgba(56,189,248,0.14) !important;
        border-radius: 10px !important; color: #E2E8F0 !important;
        transition: all 0.18s !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: rgba(59,130,246,0.5) !important;
        box-shadow: 0 0 0 3px rgba(59,130,246,0.08),
                    0 0 18px rgba(59,130,246,0.07) !important;
        outline: none !important;
    }
    .stSelectbox [data-baseweb="select"] > div,
    .stSelectbox > div > div {
        background: rgba(6,12,30,0.85) !important;
        border-color: rgba(56,189,248,0.14) !important;
        border-radius: 10px !important;
        color: #E2E8F0 !important;
    }

    /* ── Slider ──────────────────────────────────────────────────── */
    .stSlider [role="slider"] {
        background: #3B82F6 !important; border-color: #60A5FA !important;
        box-shadow: 0 0 12px rgba(59,130,246,0.5) !important;
    }
    .stSlider [data-baseweb="slider"] div[role="progressbar"] {
        background: linear-gradient(90deg, #3B82F6, #06B6D4) !important;
    }

    /* ── Section tag header ──────────────────────────────────────── */
    .section-tag {
        display: flex; align-items: center; gap: 10px; margin-bottom: 6px;
    }
    .section-tag .dot {
        width: 4px; height: 22px; border-radius: 2px; flex-shrink: 0;
        background: linear-gradient(180deg, #3B82F6 0%, #06B6D4 100%);
        box-shadow: 0 0 10px rgba(59,130,246,0.55);
    }
    .section-tag .label {
        font-size: 11px; font-weight: 800; letter-spacing: 0.18em;
        background: linear-gradient(90deg, #60A5FA, #22D3EE);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }

    /* ── Case row cards ──────────────────────────────────────────── */
    .case-row {
        background: rgba(6,12,30,0.75);
        border: 1px solid rgba(56,189,248,0.08);
        border-radius: 12px; padding: 14px 18px; margin-bottom: 8px;
        backdrop-filter: blur(10px);
        transition: all 0.18s ease;
    }
    .case-row:hover {
        border-color: rgba(56,189,248,0.22);
        box-shadow: 0 0 22px rgba(56,189,248,0.06);
        transform: translateX(2px);
    }

    /* ── DI badge ────────────────────────────────────────────────── */
    .di-badge {
        display: inline-flex; align-items: center; gap: 5px;
        padding: 4px 12px; border-radius: 20px;
        font-size: 11px; font-weight: 700; letter-spacing: 0.05em;
    }

    /* ── Brief header ────────────────────────────────────────────── */
    .brief-header {
        background: rgba(6,12,30,0.88);
        border: 1px solid rgba(56,189,248,0.1);
        border-radius: 14px; padding: 20px 24px; margin-bottom: 20px;
        backdrop-filter: blur(20px);
    }

    /* ── Login hero ──────────────────────────────────────────────── */
    .login-hero {
        border-radius: 20px; padding: 52px 44px; height: 100%;
        background:
            linear-gradient(rgba(56,189,248,0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(56,189,248,0.02) 1px, transparent 1px),
            linear-gradient(160deg, rgba(5,10,28,0.98) 0%, rgba(8,16,38,0.98) 100%);
        background-size: 44px 44px, 44px 44px, 100% 100%;
        border: 1px solid rgba(56,189,248,0.1);
        box-shadow: 0 0 60px rgba(37,99,235,0.06),
                    inset 0 1px 0 rgba(255,255,255,0.04);
    }
    .login-form-card {
        background: rgba(5,10,28,0.95);
        backdrop-filter: blur(30px);
        border: 1px solid rgba(56,189,248,0.12);
        border-radius: 20px; padding: 44px 40px;
        box-shadow: 0 0 60px rgba(37,99,235,0.06),
                    inset 0 1px 0 rgba(255,255,255,0.04);
    }
    .feat-item {
        display: flex; align-items: center; gap: 12px;
        padding: 11px 14px; border-radius: 10px;
        background: rgba(56,189,248,0.03);
        border: 1px solid rgba(56,189,248,0.08);
        margin-bottom: 10px; font-size: 13px; color: #64748B;
        transition: all 0.18s;
    }
    .feat-item:hover {
        background: rgba(56,189,248,0.07);
        border-color: rgba(56,189,248,0.18); color: #94A3B8;
    }
    .feat-dot {
        width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
        background: linear-gradient(135deg, #3B82F6, #06B6D4);
        box-shadow: 0 0 8px rgba(59,130,246,0.6);
    }

    /* ── Tab radio ───────────────────────────────────────────────── */
    .tab-radio div[role="radiogroup"] {
        display: flex; gap: 4px;
        background: rgba(6,12,30,0.85); padding: 4px; border-radius: 12px;
        border: 1px solid rgba(56,189,248,0.1);
    }
    .tab-radio div[role="radiogroup"] label {
        flex: 1; text-align: center; padding: 9px 18px; border-radius: 9px;
        cursor: pointer; font-size: 13px; color: #475569;
        transition: all 0.18s; font-weight: 500;
    }
    .tab-radio div[role="radiogroup"] label:has(input:checked) {
        background: linear-gradient(135deg, #2563EB, #0891B2);
        color: #fff; font-weight: 700;
        box-shadow: 0 0 18px rgba(37,99,235,0.32);
    }
    .tab-radio div[role="radiogroup"] input { display: none; }

    /* ── Sidebar brand block ─────────────────────────────────────── */
    .brand-block {
        background: linear-gradient(135deg,
            rgba(37,99,235,0.16) 0%, rgba(8,145,178,0.1) 100%);
        border: 1px solid rgba(56,189,248,0.15);
        border-radius: 14px; padding: 14px 12px; margin-bottom: 8px;
        position: relative; overflow: hidden;
    }
    .brand-block::after {
        content: '';
        position: absolute; top: -20px; right: -20px;
        width: 80px; height: 80px;
        background: radial-gradient(circle, rgba(59,130,246,0.18) 0%, transparent 70%);
        border-radius: 50%; pointer-events: none;
    }

    /* ── Sidebar stats box ───────────────────────────────────────── */
    .sidebar-stats {
        background: rgba(56,189,248,0.03);
        border: 1px solid rgba(56,189,248,0.08);
        border-radius: 12px; padding: 12px 14px;
    }
    .stat-row {
        display: flex; justify-content: space-between; align-items: center;
        margin-bottom: 7px; color: #475569; font-size: 11px;
    }
    .stat-row:last-child { margin-bottom: 0; }
    .stat-val { font-weight: 700; font-family: monospace; font-size: 12px; }

    /* ── User pill ───────────────────────────────────────────────── */
    .user-pill {
        background: rgba(56,189,248,0.04);
        border: 1px solid rgba(56,189,248,0.1);
        border-radius: 10px; padding: 10px 12px;
    }
    .role-badge {
        display: inline-block;
        background: linear-gradient(135deg, rgba(37,99,235,0.2), rgba(8,145,178,0.15));
        border: 1px solid rgba(56,189,248,0.25);
        color: #38BDF8; padding: 2px 10px; border-radius: 20px;
        font-size: 10px; font-weight: 700; letter-spacing: 0.06em;
    }

    /* ── Expanders ───────────────────────────────────────────────── */
    [data-testid="stExpander"] {
        background: rgba(6,12,30,0.65) !important;
        border: 1px solid rgba(56,189,248,0.08) !important;
        border-radius: 12px !important;
    }
    [data-testid="stExpander"] summary {
        color: #64748B !important; font-weight: 600 !important;
    }
    [data-testid="stExpander"] summary:hover { color: #94A3B8 !important; }

    /* ── Alerts ──────────────────────────────────────────────────── */
    [data-testid="stAlert"] { border-radius: 12px !important; }

    /* ── Dataframe ───────────────────────────────────────────────── */
    [data-testid="stDataFrame"] {
        border: 1px solid rgba(56,189,248,0.1) !important;
        border-radius: 12px !important;
    }

    /* ── Progress bar ────────────────────────────────────────────── */
    .stProgress > div > div {
        background: linear-gradient(90deg, #3B82F6, #06B6D4) !important;
        border-radius: 4px !important;
    }

    /* ── Dividers ────────────────────────────────────────────────── */
    hr { border-color: rgba(56,189,248,0.08) !important; }
    section[data-testid="stSidebar"] hr { border-color: rgba(56,189,248,0.07); margin: 10px 0; }

    /* ── Headings ────────────────────────────────────────────────── */
    h1 { color: #F1F5F9 !important; font-weight: 900 !important; letter-spacing: -0.02em !important; }
    h2 { color: #E2E8F0 !important; font-weight: 800 !important; }
    h3 { color: #CBD5E1 !important; font-weight: 700 !important; }

    /* ── Code blocks ─────────────────────────────────────────────── */
    [data-testid="stCode"],
    .stCodeBlock pre {
        background: rgba(6,12,30,0.9) !important;
        border: 1px solid rgba(56,189,248,0.1) !important;
        border-radius: 10px !important;
    }

    /* ── Scrollbar ───────────────────────────────────────────────── */
    ::-webkit-scrollbar { width: 5px; height: 5px; }
    ::-webkit-scrollbar-track { background: transparent; }
    ::-webkit-scrollbar-thumb {
        background: rgba(56,189,248,0.18); border-radius: 3px;
    }
    ::-webkit-scrollbar-thumb:hover { background: rgba(56,189,248,0.38); }

    /* ── Flag cards (Section C) ──────────────────────────────────── */
    .flag-card {
        background: rgba(196,30,58,0.06);
        border: 1px solid rgba(196,30,58,0.22);
        border-left: 3px solid #C41E3A;
        border-radius: 8px; padding: 11px 15px; margin-bottom: 7px;
    }
    .flag-card-title { color: #FCA5A5; font-weight: 700; font-size: 13px; margin-bottom: 4px; }
    .flag-card-raw   { color: #475569; font-family: monospace; font-size: 10px; margin-bottom: 5px; }
    .flag-card-desc  { color: #94A3B8; font-size: 12px; line-height: 1.6; }

    /* ── DI Calculation detail ───────────────────────────────────── */
    .di-calc-box {
        background: rgba(6,12,30,0.65);
        border: 1px solid rgba(56,189,248,0.1);
        border-radius: 10px; padding: 16px 20px; margin-top: 14px;
        font-family: 'Courier New', monospace;
    }
    .di-calc-title { color: rgba(56,189,248,0.5); font-size: 9px; font-weight: 800;
                     letter-spacing: 0.18em; text-transform: uppercase; margin-bottom: 10px; }
    .di-calc-row   { color: #64748B; font-size: 11px; margin-bottom: 5px; }
    .di-calc-row .val { color: #38BDF8; font-weight: 700; }
    .di-calc-row .src { color: #475569; font-size: 10px; }
    .di-calc-formula { border-top: 1px solid rgba(56,189,248,0.08);
                       margin-top: 10px; padding-top: 10px;
                       color: #E2E8F0; font-size: 13px; }
    .di-calc-formula .result { color: #F59E0B; font-weight: 900; font-size: 16px; }
    .di-source-tag {
        display: inline-block; padding: 2px 8px; border-radius: 4px;
        font-size: 9px; font-weight: 700; letter-spacing: 0.06em;
        background: rgba(37,99,235,0.15); border: 1px solid rgba(37,99,235,0.3);
        color: #60A5FA; margin-left: 6px; vertical-align: middle;
    }

    /* ── Official Directive Document ─────────────────────────────── */
    .directive-doc {
        background: rgba(8,15,35,0.7);
        border: 1px solid rgba(56,189,248,0.15);
        border-radius: 12px; padding: 36px 42px;
        font-family: 'Georgia', 'Times New Roman', serif;
        color: #CBD5E1; line-height: 1.85;
    }
    .directive-doc-header {
        text-align: center;
        border-bottom: 2px solid rgba(56,189,248,0.18);
        padding-bottom: 20px; margin-bottom: 24px;
    }
    .directive-doc-agency {
        font-size: 11px; font-weight: 800; letter-spacing: 0.2em;
        text-transform: uppercase; color: #60A5FA; margin-bottom: 4px;
    }
    .directive-doc-dept {
        font-size: 13px; font-weight: 700; color: #E2E8F0; margin-bottom: 2px;
    }
    .directive-doc-title {
        font-size: 16px; font-weight: 900; color: #fff;
        letter-spacing: 0.05em; text-transform: uppercase;
        margin-top: 12px; text-decoration: underline;
        text-underline-offset: 4px;
    }
    .directive-meta-row {
        display: flex; gap: 12px; margin-bottom: 5px; font-size: 12px;
    }
    .directive-meta-label {
        color: #60A5FA; font-weight: 700; min-width: 130px; font-family: monospace;
    }
    .directive-meta-value { color: #CBD5E1; }
    .directive-section-label {
        color: #38BDF8; font-weight: 800; font-size: 11px;
        letter-spacing: 0.15em; text-transform: uppercase;
        border-bottom: 1px solid rgba(56,189,248,0.12);
        padding-bottom: 4px; margin: 20px 0 10px;
    }
    .directive-body-text { font-size: 13px; color: #CBD5E1; }
    .directive-footer {
        border-top: 1px solid rgba(56,189,248,0.15);
        margin-top: 30px; padding-top: 20px;
    }
    .directive-sig-block { margin-top: 36px; }
    .directive-sig-line  {
        border-bottom: 1px solid rgba(148,163,184,0.35);
        width: 220px; height: 32px; margin-bottom: 6px;
    }
    .directive-sig-name  { color: #E2E8F0; font-weight: 700; font-size: 13px; }
    .directive-sig-title { color: #64748B; font-size: 11px; }

    /* ── Print styles ────────────────────────────────────────────── */
    @media print {
        section[data-testid="stSidebar"],
        [data-testid="baseButton-primary"],
        [data-testid="baseButton-secondary"],
        .nav-group, .section-tag, .sidebar-stats { display: none !important; }
        [data-testid="stAppViewContainer"] { background: white !important; }
        .directive-doc {
            background: white !important; color: black !important;
            border: none; border-radius: 0; padding: 0;
            font-family: 'Times New Roman', serif;
        }
        .directive-doc-agency, .directive-doc-dept, .directive-meta-label,
        .directive-section-label { color: #003399 !important; }
        .directive-meta-value, .directive-body-text { color: black !important; }
        .directive-doc-header { border-bottom: 2px solid #003399; }
        .directive-footer { border-top: 1px solid #ccc; }
    }
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
def _get_api_key() -> str:
    """Read Groq API key from Streamlit secrets or environment variable."""
    import os
    try:
        return st.secrets.get("GROQ_API_KEY", "")
    except Exception:
        return os.environ.get("GROQ_API_KEY", "")


def run_agent_pipeline(
    school_id,
    source_system_id,
    source_system_name,
    raw_text,
    operational_score=None,
) -> dict:
    import json as _json
    db = get_db()
    api_key = _get_api_key()

    result_a = agent_a_run(school_id, raw_text, source_system_id, api_key=api_key)
    result_b = agent_b_run(school_id, operational_score, result_a, source_system_id)
    result_c = agent_c_run(school_id, source_system_name, result_a, result_b, api_key=api_key)

    # Resolve the operational score actually used (AI-estimated or manual)
    resolved_op_score = (
        operational_score
        if operational_score is not None
        else (result_a.ai_estimated_operational_score or 50.0)
    )

    payload_id = str(uuid.uuid4())
    db.execute("""INSERT INTO matrix_payloads
        (id, source_system_id, source_system_name, school_id,
         raw_text_extracted, operational_score, mapped_category, severity_level, extracted_entities)
        VALUES (?,?,?,?,?,?,?,?,?)""",
        (payload_id, source_system_id, source_system_name, school_id,
         raw_text, resolved_op_score, result_a.mapped_category,
         result_a.severity, _json.dumps(result_a.extracted_entities)))

    flags_json   = _json.dumps(result_b.flags)
    agent_a_json = _json.dumps({"mapped_category": result_a.mapped_category,
                                 "severity": result_a.severity,
                                 "entities": result_a.extracted_entities})
    agent_c_json = _json.dumps({
        "alert_status":  result_c.alert_status_label,
        "enforcement":   result_c.enforcement_actions,
        "policy":        [
            {"flag": p.flag_trigger, "legal_reference": p.legal_reference, "recommended_action": p.recommended_action}
            for p in result_c.policy_recommendations
        ],
        "directive":     result_c.executive_directive_text,
    })

    db.execute("""INSERT INTO discrepancy_log
        (id, case_id, school_id, school_name, state, source_system_name,
         audit_score_reference, operational_score_reported, score_delta,
         discrepancy_index, di_classification, flags, anomaly_detected,
         confidence_score, agent_a_result, agent_c_result)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (str(uuid.uuid4()), result_b.case_id, school_id,
         result_c.school_name, result_c.state, source_system_name,
         result_b.audit_data_snapshot.get("skpmg2_score", 0),
         resolved_op_score, result_b.score_delta, result_b.discrepancy_index,
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
        "operational_score_reported":resolved_op_score,
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

def _nav_btn(label_key: str, page_key: str, role_required=None, tooltip_key: str = None):
    if role_required and not require_role(*role_required):
        return
    is_active = st.session_state.get("current_page") == page_key
    btn_type  = "primary" if is_active else "secondary"
    tip = t(tooltip_key) if tooltip_key else None
    if st.sidebar.button(t(label_key), key=f"nav_{page_key}",
                         use_container_width=True, type=btn_type, help=tip):
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

def _tab_radio_n(opt_keys: list, values: list, state_key: str) -> str:
    """Generalised tab radio supporting N options. Returns the selected value string."""
    opts    = [t(k) for k in opt_keys]
    curr    = st.session_state.get(state_key, values[0])
    idx     = values.index(curr) if curr in values else 0
    st.markdown('<div class="tab-radio">', unsafe_allow_html=True)
    chosen  = st.radio("", opts, index=idx, horizontal=True,
                       label_visibility="collapsed",
                       key=f"tab_radio_{state_key}")
    st.markdown("</div>", unsafe_allow_html=True)
    new_val = values[opts.index(chosen)]
    st.session_state[state_key] = new_val
    return new_val

# ---------------------------------------------------------------------------
# GOOGLE DRIVE HELPERS
# ---------------------------------------------------------------------------
def _get_gdrive_client():
    """Return authenticated gspread client, or None if not configured."""
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        raw = st.secrets.get("GDRIVE_SERVICE_ACCOUNT", {})
        info = dict(raw) if raw else {}
        if not info.get("private_key"):
            return None
        creds = Credentials.from_service_account_info(info, scopes=GDRIVE_SCOPES)
        return gspread.authorize(creds)
    except Exception:
        return None

def _list_gdrive_sheets(folder_id: str) -> list:
    """Return list of {id, name, modifiedTime} for Sheets in the folder."""
    try:
        from googleapiclient.discovery import build
        from google.oauth2.service_account import Credentials
        raw  = st.secrets.get("GDRIVE_SERVICE_ACCOUNT", {})
        info = dict(raw) if raw else {}
        creds = Credentials.from_service_account_info(
            info, scopes=["https://www.googleapis.com/auth/drive.readonly"]
        )
        svc = build("drive", "v3", credentials=creds, cache_discovery=False)
        res = svc.files().list(
            q=(f"'{folder_id}' in parents "
               "and mimeType='application/vnd.google-apps.spreadsheet' "
               "and trashed=false"),
            fields="files(id,name,modifiedTime)",
            orderBy="modifiedTime desc",
        ).execute()
        return res.get("files", [])
    except Exception as exc:
        return [{"_error": str(exc)}]

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
            <div style="margin-bottom:18px">
                <svg viewBox="0 0 80 80" fill="none" xmlns="http://www.w3.org/2000/svg"
                     style="width:80px;height:80px;filter:drop-shadow(0 0 18px rgba(37,99,235,0.7))">
                    <defs>
                        <linearGradient id="lg1" x1="0" y1="0" x2="80" y2="80" gradientUnits="userSpaceOnUse">
                            <stop offset="0%" stop-color="#2563EB"/>
                            <stop offset="100%" stop-color="#0891B2"/>
                        </linearGradient>
                    </defs>
                    <path d="M40 4 L72 16 L72 42 C72 60 58 71 40 77 C22 71 8 60 8 42 L8 16 Z"
                          fill="url(#lg1)" opacity="0.90"/>
                    <path d="M40 4 L72 16 L72 42 C72 60 58 71 40 77 C22 71 8 60 8 42 L8 16 Z"
                          fill="none" stroke="rgba(96,165,250,0.7)" stroke-width="2"/>
                    <path d="M40 18 L43.8 30.8 L57 30.8 L46.6 38.7 L50.4 51.5 L40 43.6 L29.6 51.5 L33.4 38.7 L23 30.8 L36.2 30.8 Z"
                          fill="white" opacity="0.95"/>
                </svg>
            </div>
            <h1 style="font-size:34px;font-weight:900;color:#fff;margin:0;line-height:1.1;letter-spacing:-0.02em">
                JN RESOLUSI
            </h1>
            <p style="background:linear-gradient(90deg,#60A5FA,#22D3EE);
                      -webkit-background-clip:text;-webkit-text-fill-color:transparent;
                      background-clip:text;
                      font-weight:800;letter-spacing:0.14em;font-size:12px;margin:10px 0 20px;text-transform:uppercase">
                Sistem Audit Pintar MOE · PRESTIJ-25
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
        _logo_svg = (
            '<svg viewBox="0 0 52 52" fill="none" xmlns="http://www.w3.org/2000/svg"'
            ' style="width:52px;height:52px;filter:drop-shadow(0 0 12px rgba(37,99,235,0.65))">'
            '<defs>'
            '<linearGradient id="sg1" x1="0" y1="0" x2="52" y2="52" gradientUnits="userSpaceOnUse">'
            '<stop offset="0%" stop-color="#1D4ED8"/>'
            '<stop offset="50%" stop-color="#2563EB"/>'
            '<stop offset="100%" stop-color="#0891B2"/>'
            '</linearGradient>'
            '<linearGradient id="sg2" x1="0" y1="0" x2="52" y2="0" gradientUnits="userSpaceOnUse">'
            '<stop offset="0%" stop-color="rgba(96,165,250,0.8)"/>'
            '<stop offset="100%" stop-color="rgba(34,211,238,0.4)"/>'
            '</linearGradient>'
            '</defs>'
            '<path d="M26 2 L47 10 L47 27 C47 39 38 46 26 50 C14 46 5 39 5 27 L5 10 Z" fill="url(#sg1)"/>'
            '<path d="M26 2 L47 10 L47 27 C47 39 38 46 26 50 C14 46 5 39 5 27 L5 10 Z"'
            ' fill="none" stroke="url(#sg2)" stroke-width="1.5"/>'
            '<path d="M26 11 L28.7 19.8 L38 19.8 L30.6 25.2 L33.4 34 L26 28.6 L18.6 34 L21.4 25.2 L14 19.8 L23.3 19.8 Z"'
            ' fill="white" opacity="0.96"/>'
            '</svg>'
        )
        _brand_html = (
            '<div style="background:linear-gradient(135deg,rgba(29,78,216,0.22) 0%,rgba(8,145,178,0.12) 100%);'
            'border:1px solid rgba(56,189,248,0.2);border-radius:14px;padding:14px 12px 10px;'
            'margin-bottom:6px;position:relative;overflow:hidden;">'
            '<div style="position:absolute;top:-15px;right:-15px;width:70px;height:70px;'
            'background:radial-gradient(circle,rgba(37,99,235,0.2) 0%,transparent 70%);border-radius:50%"></div>'
            '<div style="display:flex;align-items:center;gap:12px;position:relative">'
            + _logo_svg +
            '<div>'
            '<div style="font-weight:900;font-size:15px;color:#F8FAFC;letter-spacing:0.06em;'
            'text-shadow:0 0 20px rgba(37,99,235,0.4)">JN RESOLUSI</div>'
            '<div style="font-size:9px;letter-spacing:0.16em;text-transform:uppercase;'
            'background:linear-gradient(90deg,#60A5FA,#22D3EE);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;'
            'background-clip:text;margin-top:3px;font-weight:700">Sistem Audit Pintar MOE</div>'
            '</div></div>'
            '<div style="margin-top:10px;padding-top:8px;border-top:1px solid rgba(56,189,248,0.12);'
            'font-size:8px;color:rgba(56,189,248,0.35);letter-spacing:0.18em;font-weight:700">'
            'PRESTIJ-25 &nbsp;&middot;&nbsp; KPM AGENTIC AI &nbsp;&middot;&nbsp; v2.0</div>'
            '</div>'
        )
        st.markdown(_brand_html, unsafe_allow_html=True)

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
        _nav_btn("nav_dashboard", "dashboard", tooltip_key="tip_nav_dashboard")
        _nav_btn("nav_cases",     "cases",     tooltip_key="tip_nav_cases")

        # ── Nav: DATA INPUT ─────────────────────────
        st.markdown(f'<div class="nav-group">{t("nav_data_input")}</div>', unsafe_allow_html=True)
        if require_role("admin", "penyelaras_jn"):
            _nav_btn("nav_data_sub", "data_input", tooltip_key="tip_nav_data")

        # ── Nav: SYSTEM ─────────────────────────────
        st.markdown(f'<div class="nav-group">{t("nav_system")}</div>', unsafe_allow_html=True)
        _nav_btn("nav_users", "user_management", role_required=("admin",), tooltip_key="tip_nav_users")
        _nav_btn("nav_info",  "system_info",     tooltip_key="tip_nav_info")

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
        <div class="sidebar-stats">
            <div style="font-weight:800;font-size:9px;letter-spacing:0.16em;
                        color:rgba(56,189,248,0.4);text-transform:uppercase;margin-bottom:10px">
                {t('stat_title')}
            </div>
            <div class="stat-row">
                <span>{t('stat_agents')}</span>
                <span class="stat-val" style="color:#10B981">3 ✓</span>
            </div>
            <div class="stat-row">
                <span>{t('stat_cases')}</span>
                <span class="stat-val" style="color:#E2E8F0">{total}</span>
            </div>
            <div class="stat-row">
                <span>{t('stat_anomalies')}</span>
                <span class="stat-val" style="color:#EF4444">{anomalies}</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.divider()

        # ── User info + logout ──────────────────────
        st.markdown(f"""
        <div class="user-pill" style="margin-bottom:8px">
            <div style="font-family:monospace;font-size:11px;color:#64748B;
                        margin-bottom:6px;word-break:break-all">{user['email']}</div>
            <span class="role-badge">{role_label(user['role'])}</span>
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
# DATA SUBMISSION (Hantar Payload + Muat Naik Fail + Google Drive API)
# ---------------------------------------------------------------------------
def render_data_input():
    section_header(t("sub_section"))
    st.title(t("sub_title"))
    st.caption(t("sub_caption"))

    tab = _tab_radio_n(
        ["tab_payload", "tab_csv", "tab_gdrive"],
        ["a", "b", "c"],
        "data_tab",
    )

    st.divider()
    if tab == "a":
        _render_ingest_body()
    elif tab == "b":
        _render_csv_body()
    else:
        _render_gdrive_body()

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

def _extract_text_from_file(uploaded_file) -> str:
    """Extract plain text from TXT, DOCX, or PDF uploaded file objects."""
    name = uploaded_file.name.lower()
    raw_bytes = uploaded_file.read()

    if name.endswith(".txt"):
        for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
            try:
                return raw_bytes.decode(enc)
            except UnicodeDecodeError:
                continue
        return raw_bytes.decode("utf-8", errors="replace")

    if name.endswith(".docx"):
        if not _DOCX_OK:
            return ""
        doc = DocxDocument(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    if name.endswith(".pdf"):
        if not _PDF_OK:
            return ""
        reader = PdfReader(io.BytesIO(raw_bytes))
        pages = []
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                pages.append(txt)
        return "\n".join(pages)

    return ""


def _render_csv_body():
    if not require_role("admin", "penyelaras_jn"):
        st.warning(t("csv_no_access"))
        return

    col_up, col_info = st.columns([2, 1])

    with col_up:
        uploaded = st.file_uploader(
            t("csv_select"),
            type=["csv", "txt", "docx", "pdf"],
            label_visibility="collapsed",
        )

        if uploaded:
            fname = uploaded.name.lower()

            # ---- CSV: column mapper → preview → confirm → process ----
            if fname.endswith(".csv"):
                df = pd.read_csv(uploaded)
                cols = list(df.columns)
                none_opt = t("csv_map_none")
                col_opts = [none_opt] + cols

                st.markdown(f"**{t('csv_preview')}** — {len(df)} {t('csv_rows')}")
                st.dataframe(df.head(5), use_container_width=True, hide_index=True)
                st.divider()

                st.markdown(f"**{t('csv_map_title')}**")
                mc1, mc2, mc3 = st.columns(3)

                # auto-detect sensible defaults
                def _best(keywords):
                    for kw in keywords:
                        for c in cols:
                            if kw in c.lower():
                                return c
                    return none_opt

                school_col  = mc1.selectbox(t("csv_map_school"), col_opts,
                                            index=col_opts.index(_best(["school","sekolah","kod","id"])))
                score_col   = mc2.selectbox(t("csv_map_score"), col_opts,
                                            index=col_opts.index(_best(["score","skor","reported","op","math","reading","writing"])))
                text_col    = mc3.selectbox(t("csv_map_text"), col_opts,
                                            index=col_opts.index(_best(["text","laporan","report","notes","description","komen"])))
                default_score = st.slider(t("csv_map_default_score"), 0.0, 100.0, 70.0, 0.5)

                # ---- Step 2: preview mapped data ----
                st.divider()
                st.markdown(f"**{t('csv_map_preview_title')}**")

                preview_rows = []
                for _, row in df.head(5).iterrows():
                    sch  = str(row[school_col]) if school_col != none_opt else "UNKNOWN99"
                    try:
                        scr = float(row[score_col]) if score_col != none_opt else default_score
                    except (ValueError, TypeError):
                        scr = default_score
                    txt_preview = str(row[text_col])[:60] + "…" if text_col != none_opt else "(auto dari semua lajur)"
                    preview_rows.append({"Sekolah": sch, "Skor Op": f"{scr:.1f}", "Teks": txt_preview})

                st.dataframe(pd.DataFrame(preview_rows), use_container_width=True, hide_index=True)
                st.caption(f"Pratonton 5 baris pertama sahaja — {len(df)} baris akan diproses.")

                # ---- Step 3: confirm button ----
                st.divider()
                if st.button(t("csv_map_confirm"), type="primary", use_container_width=True):
                    results, errors = [], []
                    progress = st.progress(0)
                    status   = st.empty()

                    for i, row in df.iterrows():
                        try:
                            school = str(row[school_col]).strip() if school_col != none_opt else "UNKNOWN99"
                            if not school or school.lower() in ("nan","none",""):
                                school = "UNKNOWN99"

                            try:
                                op_score = float(row[score_col]) if score_col != none_opt else default_score
                            except (ValueError, TypeError):
                                op_score = default_score

                            if text_col != none_opt:
                                raw_text = str(row[text_col])
                            else:
                                raw_parts = [f"{c}: {row[c]}" for c in df.columns if pd.notna(row.get(c))]
                                raw_text  = "; ".join(raw_parts[:8])

                            result = run_agent_pipeline(school, f"CSV-{i+1:04d}", "CSV Bulk Upload", raw_text, op_score)
                            results.append({"Baris": i+1, "Sekolah": school,
                                            "Skor Op": f"{op_score:.1f}",
                                            "Skor DI": f"{result['discrepancy_index']:.4f}",
                                            "Klasifikasi": result["di_classification"].replace("_"," "),
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

            # ---- TXT / DOCX / PDF: whole file → 1 case ----
            else:
                raw_text = _extract_text_from_file(uploaded)

                if not raw_text.strip():
                    st.error(t("file_doc_no_text"))
                else:
                    st.info(t("file_doc_info"))
                    st.caption(f"📊 {len(raw_text):,} {t('file_doc_chars')}")

                    with st.expander(t("file_doc_preview")):
                        st.text(raw_text[:1500] + ("…" if len(raw_text) > 1500 else ""))

                    db_audit = get_db()
                    schools  = db_audit.execute("SELECT school_id, school_name FROM jn_audit_records ORDER BY school_id").fetchall()
                    sch_opts = {f"{s['school_id']} — {s['school_name']}": s["school_id"] for s in schools}
                    sch_opts["UNKNOWN99 — Sekolah Tidak Dikenali"] = "UNKNOWN99"

                    st.info(t("file_doc_ai_notice"))
                    with st.form("doc_ingest_form"):
                        src_id   = st.text_input(t("file_doc_src"), value=f"DOC-{uploaded.name[:20].upper()}")
                        sel_lbl  = st.selectbox(t("file_doc_school"), list(sch_opts.keys()))
                        school   = sch_opts[sel_lbl]
                        submitted = st.form_submit_button(t("file_doc_btn"), type="primary", use_container_width=True)

                    if submitted:
                        with st.spinner(t("csv_processing")):
                            result = run_agent_pipeline(school, src_id, uploaded.name, raw_text)
                        st.success(f"✅ {t('csv_ok')}: **{result['case_id']}**")
                        if result["anomaly_detected"]:
                            st.warning(f"⚠️ ANOMALI — DI: {result['discrepancy_index']:.4f}")

    with col_info:
        st.markdown(f"**{t('csv_format')}**")
        st.caption("CSV — setiap baris = 1 kes. Pilih lajur sendiri.")
        st.code("school_id, op_score, report\nSMK002, 92, Laporan buli...\nSKB001, 78, Kemudahan rosak...", language=None)
        st.divider()
        st.markdown("**TXT / DOCX / PDF**")
        st.caption("Seluruh fail = 1 kes. Isi maklumat sekolah sebelum hantar.")
        st.divider()
        st.markdown(f"**{t('csv_access')}**")
        st.markdown(f"- {t('role_admin')}\n- {t('role_penyelaras')}")

# ---------------------------------------------------------------------------
# GOOGLE DRIVE API INGEST
# ---------------------------------------------------------------------------
def _render_gdrive_body():
    if not require_role("admin", "penyelaras_jn"):
        st.warning(t("sub_no_access"))
        return

    gc = _get_gdrive_client()

    col_main, col_info = st.columns([2, 1])

    with col_info:
        if gc:
            st.markdown('<div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.25);'
                        'border-radius:10px;padding:14px 16px">'
                        '<div style="color:#10B981;font-weight:700;font-size:12px;margin-bottom:8px">'
                        '&#9679; GOOGLE DRIVE API — AKTIF</div>'
                        f'<div style="font-size:11px;color:#64748B;margin-bottom:4px">Folder ID: <code>{GDRIVE_FOLDER_ID[:20]}...</code></div>'
                        '<div style="font-size:11px;color:#64748B">Skop: Spreadsheets (baca sahaja)</div>'
                        '</div>', unsafe_allow_html=True)
        else:
            st.markdown('<div style="background:rgba(234,179,8,0.08);border:1px solid rgba(234,179,8,0.25);'
                        'border-radius:10px;padding:14px 16px">'
                        '<div style="color:#EAB308;font-weight:700;font-size:12px;margin-bottom:6px">'
                        '&#9711; BELUM DIKONFIGURASI</div>'
                        '<div style="font-size:11px;color:#64748B">Ikuti panduan setup di bawah.</div>'
                        '</div>', unsafe_allow_html=True)

        st.markdown("")
        st.markdown("**📋 Format Sheet Disokong**")
        st.caption("Google Sheets standard dalam folder Drive yang dikongsi dengan Service Account.")
        st.markdown("**🔄 Jadual Pull**")
        st.caption("Manual trigger oleh Admin / Penyelaras JN. Setiap kes diproses melalui pipeline Ejen A → B → C.")
        st.markdown(f"**🔗 Folder Drive**")
        st.markdown(f"[Buka Folder ↗]({GDRIVE_FOLDER_URL})")

    with col_main:
        if not gc:
            # ── Setup guide ──────────────────────────────────────────
            st.warning("⚙️ Google Drive API belum dikonfigurasi. Ikuti langkah berikut:")

            with st.expander("**Langkah 1 — Cipta Google Cloud Project & Service Account**", expanded=True):
                st.markdown("""
1. Pergi ke [Google Cloud Console](https://console.cloud.google.com)
2. Buat project baru atau pilih project sedia ada
3. Aktifkan **Google Drive API** dan **Google Sheets API**:
   - Menu kiri → *APIs & Services* → *Library*
   - Cari "Google Drive API" → Enable
   - Cari "Google Sheets API" → Enable
4. Buat Service Account:
   - *APIs & Services* → *Credentials* → *Create Credentials* → *Service Account*
   - Beri nama (contoh: `jn-resolusi-reader`)
   - Role: *Viewer* sudah cukup
5. Jana JSON key:
   - Klik Service Account → *Keys* → *Add Key* → *Create new key* → **JSON**
   - Simpan fail JSON ini
                """)

            with st.expander("**Langkah 2 — Kongsi Google Drive Folder dengan Service Account**"):
                st.markdown("""
1. Buka fail JSON — salin nilai `client_email` (contoh: `jn-resolusi-reader@project.iam.gserviceaccount.com`)
2. Pergi ke Google Drive folder ini: [Buka Folder](%s)
3. Klik kanan folder → **Share** → tampal email Service Account → Role: **Viewer** → Done
                """ % GDRIVE_FOLDER_URL)

            with st.expander("**Langkah 3 — Masukkan Credentials ke Streamlit Secrets**"):
                st.markdown("Pergi ke **Streamlit Cloud** → app → ⋮ → **Settings** → **Secrets** dan tampal format berikut:")
                st.code("""[GDRIVE_SERVICE_ACCOUNT]
type = "service_account"
project_id = "your-project-id"
private_key_id = "abc123"
private_key = \"\"\"-----BEGIN RSA PRIVATE KEY-----
...isi private key dari fail JSON...
-----END RSA PRIVATE KEY-----\"\"\"
client_email = "jn-resolusi-reader@project.iam.gserviceaccount.com"
client_id = "123456789"
auth_uri = "https://accounts.google.com/o/oauth2/auth"
token_uri = "https://oauth2.googleapis.com/token"
""", language="toml")
                st.info("Selepas simpan secrets, reboot app dari Streamlit Cloud dashboard.")

            with st.expander("**Langkah 4 — Format Standard Google Sheet**"):
                st.markdown("""
Sheet perlu ada header row. Lajur yang disyorkan (nama fleksibel — boleh map semasa ingest):

| school_id | operational_score | report_text | source_system |
|-----------|-------------------|-------------|---------------|
| SMK002    | 92.0              | Laporan...  | SISTEM-A      |
| SKB001    | 78.5              | Kemudahan...| SISTEM-B      |

Tiada lajur wajib — sistem akan bagi pilihan untuk map lajur sebelum proses.
                """)
            return

        # ── API connected — show sheets ───────────────────────────────
        st.markdown(f"**📁 Folder:** `{GDRIVE_FOLDER_ID}`")

        with st.spinner("Mendapatkan senarai sheets..."):
            sheets = _list_gdrive_sheets(GDRIVE_FOLDER_ID)

        if sheets and "_error" in sheets[0]:
            st.error(f"Ralat Drive API: {sheets[0]['_error']}")
            return

        if not sheets:
            st.info("Tiada Google Sheets dijumpai dalam folder ini.")
            return

        sheet_opts = {f"{s['name']}  [{s['modifiedTime'][:10]}]": s["id"] for s in sheets}
        selected_label = st.selectbox("📊 Pilih Google Sheet untuk diingest", list(sheet_opts.keys()))
        sheet_id       = sheet_opts[selected_label]
        sheet_name     = selected_label.split("  [")[0]

        try:
            import gspread
            wb        = gc.open_by_key(sheet_id)
            wsheets   = wb.worksheets()
            ws_names  = [w.title for w in wsheets]
            ws_sel    = st.selectbox("📋 Pilih Tab (Worksheet)", ws_names) if len(wsheets) > 1 else ws_names[0]
            ws        = wb.worksheet(ws_sel)

            with st.spinner("Memuatkan data..."):
                records = ws.get_all_records()

            if not records:
                st.warning("Worksheet ini kosong atau tiada data selepas header row.")
                return

            df   = pd.DataFrame(records)
            cols = list(df.columns)

            st.markdown(f"**{len(df)} baris** ditemui — pratonton 5 baris pertama:")
            st.dataframe(df.head(5), use_container_width=True, hide_index=True)

            st.divider()
            st.markdown("**📋 Padankan Lajur ke Medan Sistem**")

            none_opt  = "(tiada / guna lalai)"
            col_opts  = [none_opt] + cols

            def _best(kws):
                for kw in kws:
                    for c in cols:
                        if kw in c.lower():
                            return c
                return none_opt

            mc1, mc2, mc3, mc4 = st.columns(4)
            school_col  = mc1.selectbox("Kod Sekolah *", col_opts,
                                        index=col_opts.index(_best(["school","sekolah","kod","id"])))
            score_col   = mc2.selectbox("Skor Operasi *", col_opts,
                                        index=col_opts.index(_best(["score","skor","op","reported","nilai"])))
            text_col    = mc3.selectbox("Teks Laporan", col_opts,
                                        index=col_opts.index(_best(["text","laporan","report","notes","deskripsi"])))
            src_col     = mc4.selectbox("Nama Sistem Sumber", col_opts,
                                        index=col_opts.index(_best(["source","sistem","system","sumber"])))
            default_score = st.slider("Skor lalai (jika tiada lajur skor)", 0.0, 100.0, 70.0, 0.5)

            if school_col == none_opt or score_col == none_opt:
                st.warning("⚠️ Sila pilih sekurang-kurangnya lajur **Kod Sekolah** dan **Skor Operasi**.")
                return

            # Preview mapped rows
            st.divider()
            st.markdown("**📊 Pratonton Padanan (5 baris pertama)**")
            prev_rows = []
            for _, row in df.head(5).iterrows():
                sch = str(row[school_col]).strip()
                try:    scr = float(row[score_col])
                except: scr = default_score
                txt  = str(row[text_col])[:60] + "…" if text_col != none_opt else "(auto dari semua lajur)"
                src  = str(row[src_col]).strip() if src_col != none_opt else sheet_name
                prev_rows.append({"Sekolah": sch, "Skor": f"{scr:.1f}", "Sistem": src, "Teks": txt})
            st.dataframe(pd.DataFrame(prev_rows), use_container_width=True, hide_index=True)

            st.divider()
            col_btn, col_last = st.columns([2, 1])
            with col_btn:
                if st.button("🚀 Ingest Semua Baris ke Enjin", type="primary", use_container_width=True):
                    results, errors = [], []
                    prog   = st.progress(0)
                    status = st.empty()
                    for i, row in df.iterrows():
                        try:
                            sch = str(row[school_col]).strip() or "UNKNOWN99"
                            if sch.lower() in ("nan", "none", ""):
                                sch = "UNKNOWN99"
                            try:    scr = float(row[score_col])
                            except: scr = default_score
                            if text_col != none_opt:
                                txt = str(row[text_col])
                            else:
                                txt = "; ".join(f"{c}: {row[c]}" for c in cols if pd.notna(row.get(c)))
                            src = str(row[src_col]).strip() if src_col != none_opt else sheet_name
                            res = run_agent_pipeline(sch, f"GDRIVE-{i+1:04d}", src, txt, scr)
                            results.append({
                                "Baris": i+1, "Sekolah": sch, "Skor Op": f"{scr:.1f}",
                                "DI": f"{res['discrepancy_index']:.4f}",
                                "Klasifikasi": res["di_classification"].replace("_"," "),
                                "ID Kes": res["case_id"],
                            })
                        except Exception as e:
                            errors.append({"Baris": i+1, "Ralat": str(e)})
                        prog.progress((i+1) / len(df))
                        status.text(f"Memproses {i+1}/{len(df)}...")

                    prog.empty(); status.empty()
                    if results:
                        st.success(f"✅ {len(results)} baris berjaya diingest melalui Ejen A → B → C")
                        st.dataframe(pd.DataFrame(results), use_container_width=True, hide_index=True)
                    if errors:
                        st.error(f"❌ {len(errors)} ralat semasa pemprosesan")
                        st.dataframe(pd.DataFrame(errors), use_container_width=True, hide_index=True)

            with col_last:
                st.markdown(f"**Sheet:** `{sheet_name}`")
                st.markdown(f"**Worksheet:** `{ws_sel}`")
                st.markdown(f"**Jumlah baris:** `{len(df)}`")

        except Exception as e:
            st.error(f"Ralat semasa membaca Google Sheet: {str(e)}")


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

    _sname = case['school_name'] or '—'
    _scid  = case['case_id']
    _sstate= case['state'] or 'N/A'
    _sts   = case['timestamp'][:19]
    _bh = (
        f'<div class="brief-header" style="border-left:4px solid {color}">'
        '<div style="font-size:10px;color:#C41E3A;letter-spacing:0.16em;font-weight:700;margin-bottom:4px">'
        'ARAHAN EKSEKUTIF &mdash; AI-COMPLAINT-MOE</div>'
        f'<div style="font-size:22px;font-weight:800;color:#fff">{_sname}</div>'
        '<div style="font-family:monospace;font-size:11px;color:#6B7C93;margin-top:4px">'
        f'{_scid} &middot; {_sstate} &middot; {_sts}</div>'
        '</div>'
    )
    st.markdown(_bh, unsafe_allow_html=True)
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

        # ── Detailed DI calculation panel ────────────────────────────────
        audit_sc = case["audit_score_reference"] or 0.0
        op_sc    = case["operational_score_reported"] or 0.0
        delta    = abs(audit_sc - op_sc)
        audit_row_detail = get_db().execute(
            "SELECT last_audit_date, facility_gred, integrity_risk_index FROM jn_audit_records WHERE school_id=?",
            (case["school_id"],)
        ).fetchone()
        last_audit_str = audit_row_detail["last_audit_date"] if audit_row_detail else "—"
        facility_gred  = audit_row_detail["facility_gred"]   if audit_row_detail else "—"
        risk_idx       = f"{audit_row_detail['integrity_risk_index']:.3f}" if audit_row_detail else "—"
        direction = "lebih tinggi" if op_sc > audit_sc else ("lebih rendah" if op_sc < audit_sc else "sama")
        _src = case['source_system_name']
        _di  = case['discrepancy_index']
        _html_di = (
            '<div class="di-calc-box">'
            '<div class="di-calc-title">📐 Cara Pengiraan Discrepancy Index (DI)</div>'
            '<div class="di-calc-row">'
            '<span>Skor Audit JN (SKPMG2)</span> '
            f'<span class="src">← rekod nazir bertarikh {last_audit_str} · Gred {facility_gred}</span>'
            f'<br><span class="val">{audit_sc:.2f} / 100</span> '
            '<span class="di-source-tag">SUMBER: JN AUDIT DB</span>'
            '</div>'
            '<div class="di-calc-row" style="margin-top:8px">'
            '<span>Skor Operasi Dilaporkan</span> '
            f'<span class="src">← dihantar oleh {_src}</span>'
            f'<br><span class="val">{op_sc:.2f} / 100</span> '
            '<span class="di-source-tag">SUMBER: SISTEM LUAR</span>'
            '</div>'
            '<div class="di-calc-formula">'
            '<div style="color:#64748B;font-size:11px;margin-bottom:6px">Formula:</div>'
            'DI = |Skor Audit &minus; Skor Dilaporkan| &divide; 100<br>'
            f'DI = |{audit_sc:.2f} &minus; {op_sc:.2f}| &divide; 100<br>'
            f'DI = {delta:.2f} &divide; 100 = <span class="result">{_di:.4f}</span> '
            f'<span style="color:#94A3B8;font-size:11px;margin-left:10px">'
            f'(Skor dilaporkan {direction} sebanyak {delta:.1f} mata)</span>'
            '</div>'
            f'<div style="margin-top:10px;color:#475569;font-size:10px">'
            f'Indeks Risiko Integriti Sekolah: <span style="color:#F59E0B">{risk_idx}</span>'
            ' &nbsp;&middot;&nbsp; Julat DI: [0.0000 = selaras sempurna, 1.0000 = discrepancy ekstrem]'
            '</div>'
            '</div>'
        )
        st.markdown(_html_di, unsafe_allow_html=True)

    if flags:
        with st.expander(f"{t('brief_flags')} ({len(flags)})", expanded=True):
            _FLAG_MAP = {
                "POTENTIAL_DATA_MANIPULATION": (
                    "Petanda Manipulasi Data",
                    "Perbezaan DI melebihi ambang 0.50. Sistem mengesan kemungkinan pengubahsuaian atau pemalsuan rekod prestasi sekolah secara sengaja. Siasatan forensik data disyorkan."
                ),
                "OPERATIONAL_OVER_REPORTING_DETECTED": (
                    "Pelaporan Berlebihan (Over-Reporting)",
                    "Skor yang dilaporkan oleh sistem luar adalah jauh lebih tinggi daripada rekod audit JN. Ini menunjukkan kemungkinan sekolah melaporkan pencapaian yang lebih baik daripada realiti sebenar."
                ),
                "VISIBILITY_GAP_SUSPECTED": (
                    "Jurang Keterlihatan (Visibility Gap)",
                    "Skor dilaporkan adalah lebih rendah daripada rekod audit JN. Ini mungkin disebabkan kekurangan pelaporan atau sekolah menyembunyikan kelemahan tertentu daripada sistem luar."
                ),
                "HIGH_INTEGRITY_RISK_SCHOOL": (
                    "Sekolah Berisiko Integriti Tinggi",
                    "Rekod audit JN menunjukkan indeks risiko integriti melebihi 0.50 untuk sekolah ini. Kawalan dalaman dan tadbir urus sekolah memerlukan pengawasan rapi."
                ),
                "CANTEEN_HYGIENE_BELOW_THRESHOLD": (
                    "Kebersihan Kantin Di Bawah Piawaian",
                    "Skor kebersihan kantin dalam rekod JN berada di bawah tahap minimum 50 mata. Ini menunjukkan isu kesihatan dan pengurusan kantin yang serius."
                ),
                "CRITICAL_SEVERITY_REPORTED_BY_SOURCE": (
                    "Tahap Keterukan KRITIKAL Dilaporkan",
                    "Ejen A mengesan kandungan laporan teks pada tahap keterukan KRITIKAL. Isu yang dilaporkan oleh sistem sumber adalah serius dan memerlukan tindakan segera."
                ),
                "ADMINISTRATIVE_MISCONDUCT_CROSS_SIGNAL": (
                    "Isyarat Silang Salah Laku Pentadbiran",
                    "Laporan teks mengandungi petanda salah laku pentadbiran, dan DI melebihi 0.20. Kedua-dua faktor ini secara bersama menguatkan dakwaan masalah integriti di peringkat pengurusan sekolah."
                ),
                "SCHOOL_CODE_IDENTIFIER_MISMATCH": (
                    "Ketidakpadanan Kod Sekolah",
                    "Sistem mengesan ketidakpadanan antara kod sekolah dalam laporan dan rekod pangkalan data JN. Data mungkin dikaitkan kepada sekolah yang salah. Pengesahan manual diperlukan."
                ),
            }
            for raw_flag in flags:
                if raw_flag.startswith("AUDIT_DATA_STALE_"):
                    try:
                        days = int(raw_flag.split("_")[3])
                        title = "Data Audit JN Lapuk / Tidak Terkini"
                        desc  = (f"Rekod audit JN untuk sekolah ini telah berusia {days} hari "
                                 f"({days//365} tahun {days%365} hari). Skor SKPMG2 yang digunakan untuk mengira DI "
                                 "mungkin tidak mencerminkan keadaan semasa sekolah. Audit semula disyorkan.")
                    except Exception:
                        title = "Data Audit Lapuk"
                        desc  = "Rekod audit JN mungkin tidak terkini."
                else:
                    title, desc = _FLAG_MAP.get(raw_flag, (
                        raw_flag.replace("_", " ").title(),
                        "Bendera risiko automatik diaktifkan oleh algoritma Ejen B berdasarkan analisis data yang diterima."
                    ))
                _fc = (
                    f'<div class="flag-card">'
                    f'<div class="flag-card-raw">&#9873; {raw_flag}</div>'
                    f'<div class="flag-card-title">&#128308; {title}</div>'
                    f'<div class="flag-card-desc">{desc}</div>'
                    f'</div>'
                )
                st.markdown(_fc, unsafe_allow_html=True)

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
        with st.expander(t("brief_directive"), expanded=True):
            # Parse directive into paragraphs for clean rendering
            _lines = [ln.strip() for ln in directive.split("\n") if ln.strip()]
            _directive_html = "".join(
                f"<p style='margin:0 0 12px'>{ln}</p>" for ln in _lines
            )
            _ref_num  = case["case_id"]
            _date_str = case["timestamp"][:10]
            try:
                from datetime import date as _date
                _d = _date.fromisoformat(_date_str)
                _months = ["Januari","Februari","Mac","April","Mei","Jun",
                           "Julai","Ogos","September","Oktober","November","Disember"]
                _date_formal = f"{_d.day} {_months[_d.month-1]} {_d.year}"
            except Exception:
                _date_formal = _date_str

            _alert_lbl = agent_c_data.get("alert_status", "—")
            _school    = case["school_name"] or case["school_id"]
            _state     = case["state"] or "—"
            _di_cls    = case["di_classification"].replace("_", " ")

            _di_val = case['discrepancy_index']
            _meta = (
                f'<div class="directive-meta-row"><span class="directive-meta-label">NO. RUJUKAN</span>'
                f'<span class="directive-meta-value">: {_ref_num}</span></div>'
                f'<div class="directive-meta-row"><span class="directive-meta-label">TARIKH</span>'
                f'<span class="directive-meta-value">: {_date_formal}</span></div>'
                f'<div class="directive-meta-row"><span class="directive-meta-label">STATUS AMARAN</span>'
                f'<span class="directive-meta-value">: <strong style="color:#F59E0B">{_alert_lbl}</strong></span></div>'
                f'<div class="directive-meta-row"><span class="directive-meta-label">SEKOLAH BERKENAAN</span>'
                f'<span class="directive-meta-value">: {_school}</span></div>'
                f'<div class="directive-meta-row"><span class="directive-meta-label">NEGERI</span>'
                f'<span class="directive-meta-value">: {_state}</span></div>'
                f'<div class="directive-meta-row"><span class="directive-meta-label">KLASIFIKASI DI</span>'
                f'<span class="directive-meta-value">: <strong>{_di_cls}</strong>'
                f' &nbsp;(DI = {_di_val:.4f})</span></div>'
            )
            _footer_note = (
                f'Arahan ini dijana secara automatik oleh Ejen C &mdash; JN Resolusi Enjin pada {_date_formal}. '
                'Dokumen ini hendaklah dibaca bersama laporan audit penuh dan tidak menggantikan keputusan rasmi Jemaah Nazir.'
            )
            _doc = (
                '<div class="directive-doc">'
                '<div class="directive-doc-header">'
                '<div class="directive-doc-agency">Kementerian Pendidikan Malaysia</div>'
                '<div class="directive-doc-dept">Jemaah Nazir dan Jaminan Kualiti</div>'
                '<div class="directive-doc-dept" style="font-size:11px;color:#64748B;margin-top:2px">'
                'PRESTIJ-25 &middot; Agentic AI Programme &middot; JN Resolusi Enjin</div>'
                '<div class="directive-doc-title">Arahan Eksekutif Audit</div>'
                '</div>'
                + _meta +
                '<div class="directive-section-label">Perkara: Arahan Eksekutif Berdasarkan Analisis AI</div>'
                f'<div class="directive-body-text">{_directive_html}</div>'
                '<div class="directive-footer">'
                f'<div style="font-size:11px;color:#64748B;margin-bottom:16px">{_footer_note}</div>'
                '<div class="directive-sig-block">'
                '<div class="directive-sig-line"></div>'
                '<div class="directive-sig-name">Ketua Nazir Sekolah</div>'
                '<div class="directive-sig-title">Kementerian Pendidikan Malaysia</div>'
                '<div class="directive-sig-title" style="margin-top:4px">JN Resolusi AI Engine</div>'
                '</div></div></div>'
            )
            st.markdown(_doc, unsafe_allow_html=True)
            st.caption("💡 Gunakan Ctrl+P (Windows) atau Cmd+P (Mac) untuk cetak dokumen ini sebagai PDF.")

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

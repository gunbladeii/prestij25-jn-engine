-- ============================================================
-- JN Engine — PostgreSQL Schema (Supabase / Railway)
-- Run this once in Supabase SQL Editor before connecting app.
-- ============================================================

CREATE TABLE IF NOT EXISTS users (
    id              TEXT PRIMARY KEY,
    email           TEXT UNIQUE NOT NULL,
    password_hash   TEXT NOT NULL,
    role            TEXT NOT NULL DEFAULT 'penyelaras_jn',
    is_active       INTEGER NOT NULL DEFAULT 1,
    created_at      TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS jn_audit_records (
    school_id             TEXT PRIMARY KEY,
    school_name           TEXT NOT NULL,
    school_type           TEXT NOT NULL,
    district              TEXT NOT NULL,
    state                 TEXT NOT NULL,
    last_audit_date       TEXT NOT NULL,
    skpmg2_score          DOUBLE PRECISION NOT NULL,
    facility_gred         TEXT NOT NULL,
    canteen_hygiene_score DOUBLE PRECISION NOT NULL,
    integrity_risk_index  DOUBLE PRECISION NOT NULL,
    created_at            TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS matrix_payloads (
    id                 TEXT PRIMARY KEY,
    source_system_id   TEXT NOT NULL,
    source_system_name TEXT NOT NULL,
    source_version     TEXT,
    school_id          TEXT NOT NULL,
    raw_text_extracted TEXT,
    operational_score  DOUBLE PRECISION,
    mapped_category    TEXT,
    severity_level     TEXT,
    extracted_entities TEXT,
    received_at        TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);

CREATE TABLE IF NOT EXISTS discrepancy_log (
    id                         TEXT PRIMARY KEY,
    case_id                    TEXT UNIQUE NOT NULL,
    school_id                  TEXT NOT NULL,
    school_name                TEXT,
    state                      TEXT,
    source_system_name         TEXT,
    audit_score_reference      DOUBLE PRECISION,
    operational_score_reported DOUBLE PRECISION,
    score_delta                DOUBLE PRECISION,
    discrepancy_index          DOUBLE PRECISION NOT NULL,
    di_classification          TEXT NOT NULL,
    flags                      TEXT NOT NULL DEFAULT '[]',
    anomaly_detected           INTEGER NOT NULL DEFAULT 0,
    confidence_score           DOUBLE PRECISION,
    agent_a_result             TEXT,
    agent_c_result             TEXT,
    brief_content              TEXT,
    jn_reference_type          TEXT NOT NULL DEFAULT '',
    jn_reference_id            TEXT NOT NULL DEFAULT '',
    timestamp                  TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);

CREATE INDEX IF NOT EXISTS idx_dl_case_id ON discrepancy_log(case_id);
CREATE INDEX IF NOT EXISTS idx_dl_anomaly  ON discrepancy_log(anomaly_detected);

-- Seed audit records (run once)
INSERT INTO jn_audit_records VALUES
('SKB001','SK Bandar Baru Nilai','SK','Seremban','Negeri Sembilan','2023-03-15',85.50,'A',88.00,0.120,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('SKB002','SK Bukit Jelutong','SK','Shah Alam','Selangor','2022-11-20',72.00,'B',65.00,0.350,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('SMK001','SMK Tun Hussein Onn','SMK','Kuala Lumpur','W.P. Kuala Lumpur','2024-01-10',91.20,'A',92.00,0.080,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('SMK002','SMK Pendang','SMK','Pendang','Kedah','2022-08-05',58.00,'C',45.00,0.680,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('SBP001','Sekolah Berasrama Penuh Integrasi Gombak','SBP','Gombak','Selangor','2023-09-22',94.80,'A',95.50,0.040,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('MRSM001','MRSM Kuala Klawang','MRSM','Jelebu','Negeri Sembilan','2023-06-14',88.30,'A',87.00,0.095,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS')),
('SKK001','SK Kluang Utama','SK','Kluang','Johor','2022-05-30',63.50,'C',58.00,0.420,to_char(NOW(),'YYYY-MM-DD"T"HH24:MI:SS'))
ON CONFLICT DO NOTHING;

-- ============================================================
-- JN Dapatan Tables (Phase 1 — platform ready, API-ready)
-- ============================================================

CREATE TABLE IF NOT EXISTS jn_pemeriksaan (
    id                    TEXT PRIMARY KEY,
    school_id             TEXT NOT NULL,
    school_name           TEXT NOT NULL,
    school_type           TEXT NOT NULL DEFAULT '',
    district              TEXT NOT NULL DEFAULT '',
    state                 TEXT NOT NULL DEFAULT '',
    tarikh_pemeriksaan    TEXT NOT NULL,
    skpmg2_score          DOUBLE PRECISION NOT NULL,
    facility_gred         TEXT NOT NULL DEFAULT 'B',
    canteen_hygiene_score DOUBLE PRECISION NOT NULL DEFAULT 70.0,
    integrity_risk_index  DOUBLE PRECISION NOT NULL DEFAULT 0.3,
    sumber                TEXT NOT NULL DEFAULT 'manual',
    created_at            TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);
CREATE INDEX IF NOT EXISTS idx_pem_school ON jn_pemeriksaan(school_id);

CREATE TABLE IF NOT EXISTS jn_skas (
    id                TEXT PRIMARY KEY,
    school_id         TEXT NOT NULL,
    school_name       TEXT NOT NULL,
    district          TEXT NOT NULL DEFAULT '',
    state             TEXT NOT NULL DEFAULT '',
    tarikh_skas       TEXT NOT NULL,
    band              TEXT NOT NULL DEFAULT '',
    skor_keseluruhan  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    jenis_skas        TEXT NOT NULL DEFAULT '',
    sumber            TEXT NOT NULL DEFAULT 'manual',
    created_at        TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);
CREATE INDEX IF NOT EXISTS idx_skas_school ON jn_skas(school_id);

CREATE TABLE IF NOT EXISTS jn_skpk (
    id                TEXT PRIMARY KEY,
    school_id         TEXT NOT NULL,
    school_name       TEXT NOT NULL,
    district          TEXT NOT NULL DEFAULT '',
    state             TEXT NOT NULL DEFAULT '',
    tarikh_skpk       TEXT NOT NULL,
    band              TEXT NOT NULL DEFAULT '',
    skor_keseluruhan  DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    jenis_skpk        TEXT NOT NULL DEFAULT '',
    sumber            TEXT NOT NULL DEFAULT 'manual',
    created_at        TEXT NOT NULL DEFAULT (to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS'))
);
CREATE INDEX IF NOT EXISTS idx_skpk_school ON jn_skpk(school_id);

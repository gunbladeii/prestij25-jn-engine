-- =============================================================================
-- JEMAAH NAZIR SMART CHECK & BALANCE ENGINE
-- MoE Agentic AI — PRESTIJ Programme 2025
-- Database Schema v1.0 | PostgreSQL 16
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- =============================================================================
-- TABLE 1: INTERNAL JEMAAH NAZIR AUDIT RECORDS
-- Source of truth for all official inspection data. Immutable once committed.
-- =============================================================================
CREATE TABLE jn_audit_records (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    school_id           VARCHAR(20)     NOT NULL UNIQUE,
    school_name         VARCHAR(255)    NOT NULL,
    school_type         VARCHAR(50)     NOT NULL CHECK (school_type IN ('SK', 'SMK', 'SJK', 'SMJK', 'SAB', 'SBP', 'MRSM')),
    district            VARCHAR(100)    NOT NULL,
    state               VARCHAR(100)    NOT NULL CHECK (state IN (
                            'Johor','Kedah','Kelantan','Melaka','Negeri Sembilan',
                            'Pahang','Perak','Perlis','Pulau Pinang','Sabah',
                            'Sarawak','Selangor','Terengganu','W.P. Kuala Lumpur',
                            'W.P. Labuan','W.P. Putrajaya'
                        )),
    last_audit_date     DATE            NOT NULL,
    next_audit_due      DATE            GENERATED ALWAYS AS (last_audit_date + INTERVAL '3 years') STORED,
    skpmg2_score        NUMERIC(5,2)    NOT NULL CHECK (skpmg2_score BETWEEN 0 AND 100),
    skpmg2_band         VARCHAR(10)     GENERATED ALWAYS AS (
                            CASE
                                WHEN skpmg2_score >= 90 THEN 'CEMERLANG'
                                WHEN skpmg2_score >= 75 THEN 'BAIK'
                                WHEN skpmg2_score >= 60 THEN 'MEMUASKAN'
                                WHEN skpmg2_score >= 40 THEN 'LEMAH'
                                ELSE 'SANGAT LEMAH'
                            END
                        ) STORED,
    facility_gred       CHAR(1)         NOT NULL CHECK (facility_gred IN ('A','B','C','D','E')),
    canteen_hygiene_score NUMERIC(5,2)  NOT NULL CHECK (canteen_hygiene_score BETWEEN 0 AND 100),
    integrity_risk_index  NUMERIC(4,3)  NOT NULL CHECK (integrity_risk_index BETWEEN 0.000 AND 1.000),
    student_population  INTEGER,
    teacher_count       INTEGER,
    audit_officer_id    VARCHAR(50),
    notes               TEXT,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_jn_audit_school_id ON jn_audit_records (school_id);
CREATE INDEX idx_jn_audit_state ON jn_audit_records (state);
CREATE INDEX idx_jn_audit_risk ON jn_audit_records (integrity_risk_index DESC);
CREATE INDEX idx_jn_audit_skpmg2 ON jn_audit_records (skpmg2_score);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION update_updated_at()
RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = NOW(); RETURN NEW; END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_jn_audit_updated_at
    BEFORE UPDATE ON jn_audit_records
    FOR EACH ROW EXECUTE FUNCTION update_updated_at();

-- =============================================================================
-- TABLE 2: ECOSYSTEM MATRIX PAYLOAD INGEST LOG
-- Captures raw telemetry from all 24 external PRESTIJ vertical AI systems.
-- JSONB used for schema flexibility across heterogeneous source systems.
-- =============================================================================
CREATE TABLE matrix_payloads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system_id    VARCHAR(50)     NOT NULL,
    source_system_name  VARCHAR(255)    NOT NULL,
    source_version      VARCHAR(20),
    school_id           VARCHAR(20)     NOT NULL,
    raw_payload         JSONB           NOT NULL,
    raw_text_extracted  TEXT,
    operational_score   NUMERIC(5,2)    CHECK (operational_score BETWEEN 0 AND 100),
    -- Agent A output fields
    mapped_category     VARCHAR(100)    CHECK (mapped_category IN (
                            'Facilities', 'Academic Quality',
                            'Discipline', 'Administrative Misconduct', 'Uncategorised'
                        )),
    severity_level      VARCHAR(20)     CHECK (severity_level IN ('CRITICAL','HIGH','MEDIUM','LOW','UNKNOWN')),
    extracted_entities  JSONB,
    -- Processing metadata
    received_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    processed_at        TIMESTAMPTZ,
    processing_status   VARCHAR(50)     NOT NULL DEFAULT 'PENDING'
                            CHECK (processing_status IN ('PENDING','PROCESSING','COMPLETE','FAILED','QUARANTINED')),
    processing_error    TEXT,
    checksum_sha256     VARCHAR(64)
);

CREATE INDEX idx_matrix_school_id ON matrix_payloads (school_id);
CREATE INDEX idx_matrix_source ON matrix_payloads (source_system_id);
CREATE INDEX idx_matrix_status ON matrix_payloads (processing_status);
CREATE INDEX idx_matrix_received ON matrix_payloads (received_at DESC);
CREATE INDEX idx_matrix_payload_gin ON matrix_payloads USING GIN (raw_payload);
CREATE INDEX idx_matrix_entities_gin ON matrix_payloads USING GIN (extracted_entities);

-- =============================================================================
-- TABLE 3: DISCREPANCY LOG (Agent B Output)
-- Transactional audit trail for every anomaly check performed by Agent B.
-- This table feeds directly into the Executive Briefing generation pipeline.
-- =============================================================================
CREATE TABLE discrepancy_log (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id                     VARCHAR(60)     NOT NULL UNIQUE,
    payload_id                  UUID            NOT NULL REFERENCES matrix_payloads(id) ON DELETE RESTRICT,
    school_id                   VARCHAR(20)     NOT NULL,
    -- Scoring inputs
    audit_score_reference       NUMERIC(5,2)    NOT NULL,
    operational_score_reported  NUMERIC(5,2)    NOT NULL,
    score_delta                 NUMERIC(6,2)    GENERATED ALWAYS AS (operational_score_reported - audit_score_reference) STORED,
    -- Agent B output
    discrepancy_score           NUMERIC(5,4)    NOT NULL CHECK (discrepancy_score BETWEEN 0.0000 AND 1.0000),
    di_classification           VARCHAR(50)     NOT NULL CHECK (di_classification IN (
                                    'DATA_ALIGNED', 'MINOR_DISCREPANCY',
                                    'MODERATE_DISCREPANCY', 'SEVERE_DISCREPANCY', 'EXTREME_DISCREPANCY'
                                )),
    flags                       JSONB           NOT NULL DEFAULT '[]',
    anomaly_detected            BOOLEAN         NOT NULL DEFAULT FALSE,
    confidence_score            NUMERIC(4,3),
    -- Agent C output
    executive_brief_generated   BOOLEAN         NOT NULL DEFAULT FALSE,
    brief_generated_at          TIMESTAMPTZ,
    brief_content               JSONB,
    -- Workflow metadata
    reviewed_by_officer         VARCHAR(100),
    reviewed_at                 TIMESTAMPTZ,
    resolution_status           VARCHAR(50)     DEFAULT 'OPEN'
                                    CHECK (resolution_status IN ('OPEN','UNDER_REVIEW','ESCALATED','RESOLVED','CLOSED')),
    timestamp                   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_dl_case_id ON discrepancy_log (case_id);
CREATE INDEX idx_dl_school_id ON discrepancy_log (school_id);
CREATE INDEX idx_dl_anomaly ON discrepancy_log (anomaly_detected) WHERE anomaly_detected = TRUE;
CREATE INDEX idx_dl_classification ON discrepancy_log (di_classification);
CREATE INDEX idx_dl_score ON discrepancy_log (discrepancy_score DESC);
CREATE INDEX idx_dl_timestamp ON discrepancy_log (timestamp DESC);
CREATE INDEX idx_dl_flags_gin ON discrepancy_log USING GIN (flags);
CREATE INDEX idx_dl_resolution ON discrepancy_log (resolution_status) WHERE resolution_status = 'OPEN';

-- =============================================================================
-- TABLE 4: AUDIT TRAIL (Immutable append-only event log)
-- =============================================================================
CREATE TABLE audit_event_log (
    id              BIGSERIAL       PRIMARY KEY,
    event_type      VARCHAR(100)    NOT NULL,
    entity_type     VARCHAR(50)     NOT NULL,
    entity_id       VARCHAR(100),
    actor           VARCHAR(100),
    payload         JSONB,
    ip_address      INET,
    logged_at       TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_ael_entity ON audit_event_log (entity_type, entity_id);
CREATE INDEX idx_ael_logged ON audit_event_log (logged_at DESC);

-- =============================================================================
-- SEED DATA: Simulation Jemaah Nazir Records
-- =============================================================================
INSERT INTO jn_audit_records
    (school_id, school_name, school_type, district, state,
     last_audit_date, skpmg2_score, facility_gred,
     canteen_hygiene_score, integrity_risk_index, student_population, teacher_count)
VALUES
    ('SKB001', 'SK Bandar Baru Nilai', 'SK', 'Seremban', 'Negeri Sembilan',
     '2023-03-15', 85.50, 'A', 88.00, 0.120, 1240, 62),
    ('SKB002', 'SK Bukit Jelutong', 'SK', 'Shah Alam', 'Selangor',
     '2022-11-20', 72.00, 'B', 65.00, 0.350, 890, 44),
    ('SMK001', 'SMK Tun Hussein Onn', 'SMK', 'Kuala Lumpur', 'W.P. Kuala Lumpur',
     '2024-01-10', 91.20, 'A', 92.00, 0.080, 2100, 115),
    ('SMK002', 'SMK Pendang', 'SMK', 'Pendang', 'Kedah',
     '2022-08-05', 58.00, 'C', 45.00, 0.680, 760, 38),
    ('SBP001', 'Sekolah Berasrama Penuh Integrasi Gombak', 'SBP', 'Gombak', 'Selangor',
     '2023-09-22', 94.80, 'A', 95.50, 0.040, 980, 75),
    ('MRSM001', 'MRSM Kuala Klawang', 'MRSM', 'Jelebu', 'Negeri Sembilan',
     '2023-06-14', 88.30, 'A', 87.00, 0.095, 720, 58),
    ('SKK001', 'SK Kluang Utama', 'SK', 'Kluang', 'Johor',
     '2022-05-30', 63.50, 'C', 58.00, 0.420, 650, 31);

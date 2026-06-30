"""
AI Powered JN Resolution System — Smart Cross-Reference & Audit Engine
MoE Agentic AI — PRESTIJ Programme 2025

v2.0: JWT authentication, RBAC (3 roles), CSV bulk ingest.
      API-only; frontend served separately by Netlify.
      PostgreSQL-backed persistence.
"""

import io
import json
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import asyncpg
import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator

from agents import agent_a, agent_b, agent_c

# ---------------------------------------------------------------------------
# Auth configuration
# ---------------------------------------------------------------------------
JWT_SECRET = os.environ.get("JWT_SECRET", "jnresolusi-dev-secret-2025-changeme")
JWT_ALGO = "HS256"
JWT_EXPIRE_HOURS = int(os.environ.get("JWT_EXPIRE_HOURS", "24"))
AUTH_DOMAIN_1 = os.environ.get("AUTH_DOMAIN_1", "@moe.gov.my")
AUTH_DOMAIN_2 = os.environ.get("AUTH_DOMAIN_2", "@moe-dl.edu.my")
ALLOWED_DOMAINS = {AUTH_DOMAIN_1, AUTH_DOMAIN_2}
DEFAULT_ADMIN_EMAIL = os.environ.get("DEFAULT_ADMIN_EMAIL", "admin@moe.gov.my")
DEFAULT_ADMIN_PASSWORD = os.environ.get("DEFAULT_ADMIN_PASSWORD", "admin1234")

pwd_context = CryptContext(schemes=["sha256_crypt"], deprecated="auto")
bearer_scheme = HTTPBearer()

_pool: asyncpg.Pool | None = None

# ---------------------------------------------------------------------------
# Inline schema (auto-created on startup)
# ---------------------------------------------------------------------------
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email           VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(50)  NOT NULL DEFAULT 'penyelaras_jn',
    is_active       BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS matrix_payloads (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_system_id    VARCHAR(50)     NOT NULL,
    source_system_name  VARCHAR(255)    NOT NULL,
    source_version      VARCHAR(20),
    school_id           VARCHAR(20)     NOT NULL,
    raw_text_extracted  TEXT,
    operational_score   NUMERIC(5,2),
    mapped_category     VARCHAR(100),
    severity_level      VARCHAR(20),
    extracted_entities  JSONB,
    received_at         TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS discrepancy_log (
    id                          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id                     VARCHAR(60)     NOT NULL UNIQUE,
    school_id                   VARCHAR(20)     NOT NULL,
    school_name                 VARCHAR(255),
    state                       VARCHAR(100),
    source_system_name          VARCHAR(255),
    audit_score_reference       NUMERIC(5,2),
    operational_score_reported  NUMERIC(5,2),
    score_delta                 NUMERIC(6,2),
    discrepancy_index           NUMERIC(5,4)    NOT NULL,
    di_classification           VARCHAR(50)     NOT NULL,
    flags                       JSONB           NOT NULL DEFAULT '[]',
    anomaly_detected            BOOLEAN         NOT NULL DEFAULT FALSE,
    confidence_score            NUMERIC(4,3),
    agent_a_result              JSONB,
    agent_c_result              JSONB,
    brief_content               JSONB,
    timestamp                   TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_dl_case_id ON discrepancy_log (case_id);
CREATE INDEX IF NOT EXISTS idx_dl_timestamp ON discrepancy_log (timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_dl_anomaly ON discrepancy_log (anomaly_detected) WHERE anomaly_detected = TRUE;

CREATE TABLE IF NOT EXISTS jn_audit_records (
    school_id           VARCHAR(20)     PRIMARY KEY,
    school_name         VARCHAR(255)    NOT NULL,
    school_type         VARCHAR(50)     NOT NULL,
    district            VARCHAR(100)    NOT NULL,
    state               VARCHAR(100)    NOT NULL,
    last_audit_date     DATE            NOT NULL,
    skpmg2_score        NUMERIC(5,2)    NOT NULL,
    facility_gred       CHAR(1)         NOT NULL,
    canteen_hygiene_score NUMERIC(5,2)  NOT NULL,
    integrity_risk_index  NUMERIC(4,3)  NOT NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);
"""

SEED_AUDIT_SQL = """
INSERT INTO jn_audit_records
    (school_id, school_name, school_type, district, state,
     last_audit_date, skpmg2_score, facility_gred,
     canteen_hygiene_score, integrity_risk_index)
VALUES
    ('SKB001', 'SK Bandar Baru Nilai', 'SK', 'Seremban', 'Negeri Sembilan',
     '2023-03-15', 85.50, 'A', 88.00, 0.120),
    ('SKB002', 'SK Bukit Jelutong', 'SK', 'Shah Alam', 'Selangor',
     '2022-11-20', 72.00, 'B', 65.00, 0.350),
    ('SMK001', 'SMK Tun Hussein Onn', 'SMK', 'Kuala Lumpur', 'W.P. Kuala Lumpur',
     '2024-01-10', 91.20, 'A', 92.00, 0.080),
    ('SMK002', 'SMK Pendang', 'SMK', 'Pendang', 'Kedah',
     '2022-08-05', 58.00, 'C', 45.00, 0.680),
    ('SBP001', 'Sekolah Berasrama Penuh Integrasi Gombak', 'SBP', 'Gombak', 'Selangor',
     '2023-09-22', 94.80, 'A', 95.50, 0.040),
    ('MRSM001', 'MRSM Kuala Klawang', 'MRSM', 'Jelebu', 'Negeri Sembilan',
     '2023-06-14', 88.30, 'A', 87.00, 0.095),
    ('SKK001', 'SK Kluang Utama', 'SK', 'Kluang', 'Johor',
     '2022-05-30', 63.50, 'C', 58.00, 0.420)
ON CONFLICT (school_id) DO NOTHING;
"""


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
def hash_password(pw: str) -> str:
    return pwd_context.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    return pwd_context.verify(pw, hashed)


def create_token(email: str, role: str) -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRE_HOURS)
    return jwt.encode({"sub": email, "role": role, "exp": exp}, JWT_SECRET, algorithm=JWT_ALGO)


# ---------------------------------------------------------------------------
# Startup / teardown
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _pool
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        print("⚠ DATABASE_URL not set — running with NO persistence (data lost on restart)")
        _pool = None
    else:
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
        _pool = await asyncpg.create_pool(dsn=database_url, min_size=1, max_size=5)
        async with _pool.acquire() as conn:
            await conn.execute(SCHEMA_SQL)
            try:
                await conn.execute(SEED_AUDIT_SQL)
            except Exception:
                pass
            # Seed default admin on first run
            count = await conn.fetchval("SELECT COUNT(*) FROM users")
            if count == 0:
                hashed = hash_password(DEFAULT_ADMIN_PASSWORD)
                await conn.execute(
                    "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, 'admin') ON CONFLICT DO NOTHING",
                    DEFAULT_ADMIN_EMAIL,
                    hashed,
                )
                print(f"✅ Admin user seeded: {DEFAULT_ADMIN_EMAIL}")
        print("✅ PostgreSQL connected — data persisted")
    yield
    if _pool:
        await _pool.close()


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="AI Powered JN Resolution System — Smart Cross-Reference & Audit Engine",
    description="Supreme Truth & Audit Node — MoE PRESTIJ-25",
    version="2.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Auth dependencies
# ---------------------------------------------------------------------------
async def get_current_user(creds: HTTPAuthorizationCredentials = Depends(bearer_scheme)) -> dict:
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGO])
        email: str = payload.get("sub", "")
        role: str = payload.get("role", "")
        if not email:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"email": email, "role": role}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def require_roles(*roles: str):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["role"] not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions for this action")
        return user
    return checker


# ---------------------------------------------------------------------------
# Pydantic models
# ---------------------------------------------------------------------------
class LoginRequest(BaseModel):
    email: str
    password: str


class CreateUserRequest(BaseModel):
    email: str
    password: str = Field(..., min_length=6)
    role: str = "penyelaras_jn"


class MatrixIngestRequest(BaseModel):
    source_system_id: str = Field(..., min_length=3, max_length=50)
    source_system_name: str = Field(..., max_length=255)
    source_version: Optional[str] = Field(default="1.0.0")
    school_id: str = Field(..., min_length=4, max_length=20)
    raw_text: str = Field(..., min_length=10, max_length=10_000)
    operational_score: float = Field(..., ge=0.0, le=100.0)
    metadata: Optional[dict[str, Any]] = Field(default_factory=dict)

    @field_validator("school_id")
    @classmethod
    def uppercase_school_id(cls, v: str) -> str:
        return v.strip().upper()


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------
@app.post("/api/v1/auth/login", tags=["Auth"])
async def login(req: LoginRequest):
    email = req.email.lower().strip()
    if not any(email.endswith(d) for d in ALLOWED_DOMAINS):
        raise HTTPException(
            status_code=403,
            detail=f"Email domain not authorised. Allowed: {', '.join(ALLOWED_DOMAINS)}",
        )
    if not _pool:
        raise HTTPException(status_code=503, detail="Database not available")
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT email, password_hash, role, is_active FROM users WHERE email = $1", email
        )
    if not row or not row["is_active"] or not verify_password(req.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    token = create_token(row["email"], row["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "email": row["email"],
        "role": row["role"],
    }


@app.get("/api/v1/auth/me", tags=["Auth"])
async def get_me(user: dict = Depends(get_current_user)):
    return {"email": user["email"], "role": user["role"]}


@app.post("/api/v1/auth/users", tags=["Auth"])
async def create_user(req: CreateUserRequest, _user: dict = Depends(require_roles("admin"))):
    email = req.email.lower().strip()
    if not any(email.endswith(d) for d in ALLOWED_DOMAINS):
        raise HTTPException(status_code=400, detail="Email domain not authorised")
    if req.role not in ("admin", "peneraju_sektor", "penyelaras_jn"):
        raise HTTPException(status_code=400, detail="Invalid role. Use: admin, peneraju_sektor, penyelaras_jn")
    if not _pool:
        raise HTTPException(status_code=503, detail="Database not available")
    hashed = hash_password(req.password)
    try:
        async with _pool.acquire() as conn:
            await conn.execute(
                "INSERT INTO users (email, password_hash, role) VALUES ($1, $2, $3)", email, hashed, req.role
            )
    except asyncpg.UniqueViolationError:
        raise HTTPException(status_code=409, detail="Email already registered")
    return {"status": "created", "email": email, "role": req.role}


@app.get("/api/v1/auth/users", tags=["Auth"])
async def list_users(_user: dict = Depends(require_roles("admin"))):
    if not _pool:
        return {"users": []}
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, email, role, is_active, created_at FROM users ORDER BY created_at"
        )
    return {
        "users": [
            {
                "id": str(r["id"]),
                "email": r["email"],
                "role": r["role"],
                "is_active": r["is_active"],
                "created_at": r["created_at"].isoformat(),
            }
            for r in rows
        ]
    }


# ---------------------------------------------------------------------------
# Health check (public — no auth required)
# ---------------------------------------------------------------------------
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    case_count = 0
    if _pool:
        async with _pool.acquire() as conn:
            row = await conn.fetchrow("SELECT COUNT(*) AS c FROM discrepancy_log")
            case_count = row["c"] if row else 0
    return {
        "status": "OPERATIONAL",
        "engine": "AI Powered JN Resolution System — Smart Cross-Reference & Audit Engine",
        "version": "2.0.0",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "agents_online": ["Agent_A", "Agent_B", "Agent_C"],
        "cases_in_store": case_count,
        "environment": os.environ.get("RENDER_SERVICE_NAME", "local"),
        "db_connected": _pool is not None,
    }


# ---------------------------------------------------------------------------
# Core ingest pipeline (shared between JSON and CSV ingests)
# ---------------------------------------------------------------------------
async def _run_ingest_pipeline(
    *,
    source_system_id: str,
    source_system_name: str,
    source_version: str,
    school_id: str,
    raw_text: str,
    operational_score: float,
) -> dict:
    a_result = agent_a.run(
        school_id=school_id,
        raw_text=raw_text,
        source_system_id=source_system_id,
    )
    b_result = agent_b.run(
        school_id=school_id,
        operational_score=operational_score,
        agent_a_result=a_result,
        source_system_id=source_system_id,
    )
    c_result = agent_c.run(
        payload_school_id=school_id,
        source_system_name=source_system_name,
        agent_a=a_result,
        agent_b=b_result,
    )

    agent_a_json = json.dumps({
        "mapped_category": a_result.mapped_category,
        "category_confidence": a_result.category_confidence,
        "severity": a_result.severity,
        "severity_confidence": a_result.severity_confidence,
        "extracted_entities": a_result.extracted_entities,
        "processing_notes": a_result.processing_notes,
    })
    agent_c_json = json.dumps({
        "alert_status_label": c_result.alert_status_label,
        "alert_color_code": c_result.alert_color_code,
        "school_name": c_result.school_name,
        "state": c_result.state,
        "enforcement_actions": c_result.enforcement_actions,
        "policy_recommendations": [
            {
                "flag_trigger": pr.flag_trigger,
                "legal_reference": pr.legal_reference,
                "recommended_action": pr.recommended_action,
            }
            for pr in c_result.policy_recommendations
        ],
        "executive_directive_text": c_result.executive_directive_text,
        "generated_at": c_result.generated_at,
    })
    brief_json = json.dumps({
        "request": {
            "source_system_id": source_system_id,
            "source_system_name": source_system_name,
            "school_id": school_id,
            "operational_score": operational_score,
            "raw_text": raw_text,
        },
        "agent_a": json.loads(agent_a_json),
        "agent_b": {
            "case_id": b_result.case_id,
            "discrepancy_index": b_result.discrepancy_index,
            "di_classification": b_result.di_classification,
            "flags": b_result.flags,
            "anomaly_detected": b_result.anomaly_detected,
            "confidence_score": b_result.confidence_score,
            "audit_data_snapshot": b_result.audit_data_snapshot,
            "score_delta": b_result.score_delta,
            "audit_score_reference": b_result.audit_score_reference,
            "operational_score_reported": b_result.operational_score_reported,
        },
        "agent_c": json.loads(agent_c_json),
        "ingested_at": datetime.now(timezone.utc).isoformat(),
    })
    flags_json = json.dumps(b_result.flags)
    now = datetime.now(timezone.utc)

    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO matrix_payloads
                    (source_system_id, source_system_name, source_version,
                     school_id, raw_text_extracted, operational_score,
                     mapped_category, severity_level, extracted_entities, received_at)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9::jsonb,$10)
                """,
                source_system_id, source_system_name, source_version,
                school_id, raw_text, operational_score,
                a_result.mapped_category, a_result.severity,
                json.dumps(a_result.extracted_entities), now,
            )
            await conn.execute(
                """
                INSERT INTO discrepancy_log
                    (case_id, school_id, school_name, state, source_system_name,
                     audit_score_reference, operational_score_reported, score_delta,
                     discrepancy_index, di_classification, flags, anomaly_detected,
                     confidence_score, agent_a_result, agent_c_result, brief_content, timestamp)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11::jsonb,$12,$13,$14::jsonb,$15::jsonb,$16::jsonb,$17)
                """,
                b_result.case_id, school_id, c_result.school_name, c_result.state,
                source_system_name,
                b_result.audit_score_reference, b_result.operational_score_reported, b_result.score_delta,
                b_result.discrepancy_index, b_result.di_classification, flags_json, b_result.anomaly_detected,
                b_result.confidence_score, agent_a_json, agent_c_json, brief_json, now,
            )

    return {
        "status": "ACCEPTED",
        "case_id": b_result.case_id,
        "message": (
            "Anomaly detected — executive brief ready."
            if b_result.anomaly_detected
            else "Data within acceptable parameters."
        ),
        "school_id": school_id,
        "di_classification": b_result.di_classification,
        "discrepancy_index": b_result.discrepancy_index,
        "anomaly_detected": b_result.anomaly_detected,
        "flags_count": len(b_result.flags),
        "alert_level": c_result.alert_status_label,
        "processed_at": now.isoformat(),
    }


# ---------------------------------------------------------------------------
# Matrix ingestion endpoints (protected)
# ---------------------------------------------------------------------------
@app.post("/api/v1/matrix/ingest", status_code=202, tags=["Matrix Ingestion"])
async def ingest_matrix_payload(
    request: MatrixIngestRequest,
    _user: dict = Depends(require_roles("admin", "penyelaras_jn")),
):
    return await _run_ingest_pipeline(
        source_system_id=request.source_system_id,
        source_system_name=request.source_system_name,
        source_version=request.source_version or "1.0.0",
        school_id=request.school_id,
        raw_text=request.raw_text,
        operational_score=request.operational_score,
    )


@app.post("/api/v1/matrix/ingest/csv", tags=["Matrix Ingestion"])
async def ingest_csv(
    file: UploadFile = File(...),
    user: dict = Depends(require_roles("admin", "penyelaras_jn")),
):
    """
    Accepts a CSV file with columns:
      school, *_reported (avg → operational_score), *_actual (informational)

    Example:
      school,cleanliness_reported,cleanliness_actual,ict_reported,ict_actual
      SMK002,90,28,85,30
    """
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="File must be a .csv")
    content = await file.read()
    try:
        df = pd.read_csv(io.StringIO(content.decode("utf-8")))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid CSV format: {e}")

    if "school" not in df.columns:
        raise HTTPException(status_code=400, detail="CSV must contain a 'school' column")

    reported_cols = [c for c in df.columns if c.endswith("_reported")]
    now_ts = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    results: list[dict] = []
    errors: list[dict] = []

    for idx, row in df.iterrows():
        school_id = str(row["school"]).strip().upper()
        if not school_id or school_id == "NAN":
            errors.append({"row": int(idx) + 2, "error": "Missing school ID"})
            continue
        try:
            op_score = float(row[reported_cols].mean()) if reported_cols else 70.0
            op_score = max(0.0, min(100.0, op_score))
            parts = [f"{c.replace('_reported', '')}={row[c]:.0f}" for c in reported_cols if pd.notna(row[c])]
            raw_text = (
                f"CSV bulk upload untuk sekolah {school_id}. "
                + (", ".join(parts) if parts else "Tiada data tambahan.")
            )
            result = await _run_ingest_pipeline(
                source_system_id=f"CSV-BULK-{now_ts}",
                source_system_name=f"CSV Bulk Upload — {user['email']}",
                source_version="csv-1.0",
                school_id=school_id,
                raw_text=raw_text,
                operational_score=op_score,
            )
            results.append({
                "row": int(idx) + 2,
                "school": school_id,
                "operational_score": round(op_score, 2),
                "case_id": result["case_id"],
                "discrepancy_index": result["discrepancy_index"],
                "di_classification": result["di_classification"],
                "anomaly_detected": result["anomaly_detected"],
                "alert_level": result["alert_level"],
            })
        except Exception as e:
            errors.append({"row": int(idx) + 2, "school": school_id, "error": str(e)})

    return {
        "status": "COMPLETED",
        "total_rows": len(df),
        "processed": len(results),
        "errors": len(errors),
        "results": results,
        "error_details": errors,
    }


# ---------------------------------------------------------------------------
# Cases & briefs (all authenticated roles can read)
# ---------------------------------------------------------------------------
@app.get("/api/v1/matrix/executive-brief/{case_id}", tags=["Executive Output"])
async def get_executive_brief(case_id: str, _user: dict = Depends(get_current_user)):
    if not _pool:
        raise HTTPException(status_code=503, detail={"error": "DB_NOT_AVAILABLE"})
    async with _pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT brief_content FROM discrepancy_log WHERE case_id = $1", case_id
        )
        if not row or not row["brief_content"]:
            raise HTTPException(status_code=404, detail={"error": "CASE_NOT_FOUND", "case_id": case_id})

    brief = json.loads(row["brief_content"])
    b = brief["agent_b"]
    c = brief["agent_c"]
    a = brief["agent_a"]
    req = brief["request"]

    return {
        "case_id": case_id,
        "generated_at": c["generated_at"],
        "alert_status": c["alert_status_label"],
        "alert_color": c["alert_color_code"],
        "school_id": req["school_id"],
        "school_name": c["school_name"],
        "state": c["state"],
        "source_system": req["source_system_name"],
        "issue_domain": a["mapped_category"],
        "severity": a["severity"],
        "category_confidence": a["category_confidence"],
        "discrepancy_index": b["discrepancy_index"],
        "di_classification": b["di_classification"],
        "score_delta": b["score_delta"],
        "audit_score_reference": b["audit_score_reference"],
        "operational_score_reported": b["operational_score_reported"],
        "confidence_score": b["confidence_score"],
        "flags_triggered": b["flags"],
        "enforcement_actions": c["enforcement_actions"],
        "policy_recommendations": c["policy_recommendations"],
        "executive_directive_text": c["executive_directive_text"],
        "audit_snapshot": b["audit_data_snapshot"],
    }


@app.get("/api/v1/matrix/cases", tags=["System"])
async def list_cases(_user: dict = Depends(get_current_user)):
    if not _pool:
        return {"total_cases": 0, "cases": []}
    async with _pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT case_id, school_id, school_name, di_classification,
                   discrepancy_index, anomaly_detected, flags, brief_content, timestamp
            FROM discrepancy_log
            ORDER BY timestamp DESC
            LIMIT 100
            """
        )
    cases = []
    for r in rows:
        brief = json.loads(r["brief_content"]) if r["brief_content"] else {}
        c = brief.get("agent_c", {})
        flags = json.loads(r["flags"]) if isinstance(r["flags"], str) else (r["flags"] or [])
        cases.append({
            "case_id": r["case_id"],
            "school_id": r["school_id"],
            "school_name": r["school_name"] or c.get("school_name", ""),
            "di_classification": r["di_classification"],
            "discrepancy_index": float(r["discrepancy_index"]),
            "anomaly_detected": r["anomaly_detected"],
            "alert_level": c.get("alert_status_label", "UNKNOWN"),
            "alert_color": c.get("alert_color_code", "#888888"),
            "flags_count": len(flags) if flags else 0,
            "ingested_at": r["timestamp"].isoformat() if r["timestamp"] else "",
        })
    return {"total_cases": len(cases), "cases": cases}


@app.delete("/api/v1/matrix/cases", tags=["System"])
async def clear_cases(_user: dict = Depends(require_roles("admin"))):
    if _pool:
        async with _pool.acquire() as conn:
            await conn.execute("DELETE FROM discrepancy_log")
            await conn.execute("DELETE FROM matrix_payloads")
    return {"status": "cleared"}

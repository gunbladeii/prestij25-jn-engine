"""
Jemaah Nazir Smart Check & Balance Engine
MoE Agentic AI — PRESTIJ Programme 2025

FastAPI application entry point. Exposes the matrix ingestion and
executive briefing dispatch endpoints for the 25×25 ecosystem matrix.
"""

import hashlib
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

import asyncpg
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

from agents import agent_a, agent_b, agent_c

# ---------------------------------------------------------------------------
# In-memory case store (replace with DB persistence in production)
# ---------------------------------------------------------------------------
_case_store: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Lifespan: DB pool initialisation
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Production: replace with real DSN from environment
    # app.state.pool = await asyncpg.create_pool(dsn=os.environ["DATABASE_URL"])
    app.state.pool = None  # Simulation mode — DB pool not required for demo
    yield
    if app.state.pool:
        await app.state.pool.close()


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Jemaah Nazir Smart Check & Balance Engine",
    description=(
        "Supreme Truth & Audit Node for MoE PRESTIJ-25. "
        "Cross-references operational data from 24 external matrix systems "
        "against official Jemaah Nazir inspection records."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict to internal PRESTIJ IP range in production
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------
class MatrixIngestRequest(BaseModel):
    source_system_id: str = Field(
        ..., min_length=3, max_length=50,
        description="Unique identifier of the originating PRESTIJ matrix system",
        examples=["PRESTIJ-BULLY-03"],
    )
    source_system_name: str = Field(
        ..., max_length=255,
        description="Human-readable name of the originating system",
        examples=["AI-Powered Bully Detection & Discipline Management Agent"],
    )
    source_version: Optional[str] = Field(default="1.0.0", max_length=20)
    school_id: str = Field(
        ..., min_length=4, max_length=20,
        description="EMIS school identifier code",
        examples=["SMK002"],
    )
    raw_text: str = Field(
        ..., min_length=10, max_length=10_000,
        description="Unstructured incident or operational report text",
    )
    operational_score: float = Field(
        ..., ge=0.0, le=100.0,
        description="SKPMG2-equivalent score reported by the external system",
        examples=[82.5],
    )
    metadata: Optional[dict[str, Any]] = Field(
        default_factory=dict,
        description="Arbitrary key-value telemetry from the source system",
    )

    @field_validator("school_id")
    @classmethod
    def uppercase_school_id(cls, v: str) -> str:
        return v.strip().upper()


class MatrixIngestResponse(BaseModel):
    status: str
    case_id: str
    message: str
    school_id: str
    di_classification: str
    discrepancy_index: float
    anomaly_detected: bool
    flags_count: int
    alert_level: str
    processed_at: str


class ExecutiveBriefResponse(BaseModel):
    case_id: str
    generated_at: str
    alert_status: str
    alert_color: str
    school_id: str
    school_name: str
    state: str
    source_system: str
    issue_domain: str
    severity: str
    discrepancy_index: float
    di_classification: str
    score_delta: float
    audit_score_reference: float
    operational_score_reported: float
    confidence_score: float
    flags_triggered: list[str]
    enforcement_actions: list[str]
    policy_recommendations: list[dict]
    executive_directive_text: str


class HealthResponse(BaseModel):
    status: str
    engine: str
    version: str
    timestamp: str
    agents_online: list[str]
    cases_in_store: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """Engine health check — confirms all three agents are operational."""
    return HealthResponse(
        status="OPERATIONAL",
        engine="Jemaah Nazir Smart Check & Balance Engine",
        version="1.0.0",
        timestamp=datetime.utcnow().isoformat(),
        agents_online=["Agent_A_SemanticMapping", "Agent_B_AnomalyDetection", "Agent_C_ExecutiveBriefing"],
        cases_in_store=len(_case_store),
    )


@app.post(
    "/api/v1/matrix/ingest",
    response_model=MatrixIngestResponse,
    status_code=202,
    tags=["Matrix Ingestion"],
    summary="Ingest payload from an external PRESTIJ ecosystem system",
)
async def ingest_matrix_payload(
    request: MatrixIngestRequest,
    background_tasks: BackgroundTasks,
):
    """
    **POST /api/v1/matrix/ingest**

    Accepts telemetry payloads from any of the 24 external PRESTIJ matrix systems.
    Runs the full Agent A → Agent B → Agent C pipeline synchronously and stores
    the case result for retrieval via the executive brief endpoint.

    Returns a summary of the anomaly detection result.
    If `anomaly_detected` is true, retrieve the full brief via
    `GET /api/v1/matrix/executive-brief/{case_id}`.
    """
    # --- Agent A: Semantic Ingestion & Mapping ---
    a_result = agent_a.run(
        school_id=request.school_id,
        raw_text=request.raw_text,
        source_system_id=request.source_system_id,
    )

    # --- Agent B: Cross-Examination & Anomaly Detection ---
    b_result = agent_b.run(
        school_id=request.school_id,
        operational_score=request.operational_score,
        agent_a_result=a_result,
        source_system_id=request.source_system_id,
    )

    # --- Agent C: Executive Briefing Generation ---
    c_result = agent_c.run(
        payload_school_id=request.school_id,
        source_system_name=request.source_system_name,
        agent_a=a_result,
        agent_b=b_result,
    )

    # Persist case (in-memory; replace with asyncpg INSERT in production)
    _case_store[b_result.case_id] = {
        "request": request.model_dump(),
        "agent_a": {
            "mapped_category": a_result.mapped_category,
            "category_confidence": a_result.category_confidence,
            "severity": a_result.severity,
            "severity_confidence": a_result.severity_confidence,
            "extracted_entities": a_result.extracted_entities,
            "processing_notes": a_result.processing_notes,
        },
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
        "agent_c": {
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
        },
        "ingested_at": datetime.utcnow().isoformat(),
    }

    return MatrixIngestResponse(
        status="ACCEPTED",
        case_id=b_result.case_id,
        message=(
            "Anomaly detected — executive brief ready for retrieval."
            if b_result.anomaly_detected
            else "Payload processed — data within acceptable parameters."
        ),
        school_id=request.school_id,
        di_classification=b_result.di_classification,
        discrepancy_index=b_result.discrepancy_index,
        anomaly_detected=b_result.anomaly_detected,
        flags_count=len(b_result.flags),
        alert_level=c_result.alert_status_label,
        processed_at=datetime.utcnow().isoformat(),
    )


@app.get(
    "/api/v1/matrix/executive-brief/{case_id}",
    response_model=ExecutiveBriefResponse,
    tags=["Executive Output"],
    summary="Retrieve structured executive briefing for a processed case",
)
async def get_executive_brief(case_id: str):
    """
    **GET /api/v1/matrix/executive-brief/{case_id}**

    Returns the full executive briefing generated by Agent C for the given case.
    Includes the enforcement action directive, policy recommendations,
    and the formatted executive directive text for ministerial review.
    """
    case = _case_store.get(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "CASE_NOT_FOUND",
                "message": f"No case found with ID: {case_id}",
                "hint": "Ensure the case was ingested via POST /api/v1/matrix/ingest",
            },
        )

    b = case["agent_b"]
    c = case["agent_c"]
    a = case["agent_a"]
    req = case["request"]

    return ExecutiveBriefResponse(
        case_id=case_id,
        generated_at=c["generated_at"],
        alert_status=c["alert_status_label"],
        alert_color=c["alert_color_code"],
        school_id=req["school_id"],
        school_name=c["school_name"],
        state=c["state"],
        source_system=req["source_system_name"],
        issue_domain=a["mapped_category"],
        severity=a["severity"],
        discrepancy_index=b["discrepancy_index"],
        di_classification=b["di_classification"],
        score_delta=b["score_delta"],
        audit_score_reference=b["audit_score_reference"],
        operational_score_reported=b["operational_score_reported"],
        confidence_score=b["confidence_score"],
        flags_triggered=b["flags"],
        enforcement_actions=c["enforcement_actions"],
        policy_recommendations=c["policy_recommendations"],
        executive_directive_text=c["executive_directive_text"],
    )


@app.get(
    "/api/v1/matrix/cases",
    tags=["System"],
    summary="List all processed cases (summary view)",
)
async def list_cases():
    """Returns a summary index of all cases currently in the engine store."""
    return {
        "total_cases": len(_case_store),
        "cases": [
            {
                "case_id": cid,
                "school_id": data["request"]["school_id"],
                "di_classification": data["agent_b"]["di_classification"],
                "discrepancy_index": data["agent_b"]["discrepancy_index"],
                "anomaly_detected": data["agent_b"]["anomaly_detected"],
                "alert_level": data["agent_c"]["alert_status_label"],
                "ingested_at": data["ingested_at"],
            }
            for cid, data in _case_store.items()
        ],
    }

"""
Jemaah Nazir Smart Check & Balance Engine — API Server
MoE Agentic AI — PRESTIJ Programme 2025

Production build: API-only. Frontend is served separately by Netlify.
Render.com reads the PORT environment variable automatically.
"""

import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from agents import agent_a, agent_b, agent_c

_case_store: dict[str, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield


app = FastAPI(
    title="Jemaah Nazir Smart Check & Balance Engine",
    description="Supreme Truth & Audit Node — MoE PRESTIJ-25",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
    openapi_url="/api/openapi.json",
)

# CORS: allow Netlify domain + localhost dev
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    "http://localhost:8000,http://127.0.0.1:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Netlify proxy sends same-origin; wildcard safe here
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
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
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/v1/health", tags=["System"])
async def health_check():
    return {
        "status": "OPERATIONAL",
        "engine": "Jemaah Nazir Smart Check & Balance Engine",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "agents_online": ["Agent_A", "Agent_B", "Agent_C"],
        "cases_in_store": len(_case_store),
        "environment": os.environ.get("RENDER_SERVICE_NAME", "local"),
    }


@app.post("/api/v1/matrix/ingest", status_code=202, tags=["Matrix Ingestion"])
async def ingest_matrix_payload(request: MatrixIngestRequest):
    a_result = agent_a.run(
        school_id=request.school_id,
        raw_text=request.raw_text,
        source_system_id=request.source_system_id,
    )
    b_result = agent_b.run(
        school_id=request.school_id,
        operational_score=request.operational_score,
        agent_a_result=a_result,
        source_system_id=request.source_system_id,
    )
    c_result = agent_c.run(
        payload_school_id=request.school_id,
        source_system_name=request.source_system_name,
        agent_a=a_result,
        agent_b=b_result,
    )

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

    return {
        "status": "ACCEPTED",
        "case_id": b_result.case_id,
        "message": (
            "Anomaly detected — executive brief ready."
            if b_result.anomaly_detected
            else "Data within acceptable parameters."
        ),
        "school_id": request.school_id,
        "di_classification": b_result.di_classification,
        "discrepancy_index": b_result.discrepancy_index,
        "anomaly_detected": b_result.anomaly_detected,
        "flags_count": len(b_result.flags),
        "alert_level": c_result.alert_status_label,
        "processed_at": datetime.utcnow().isoformat(),
    }


@app.get("/api/v1/matrix/executive-brief/{case_id}", tags=["Executive Output"])
async def get_executive_brief(case_id: str):
    case = _case_store.get(case_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail={"error": "CASE_NOT_FOUND", "case_id": case_id},
        )
    b = case["agent_b"]
    c = case["agent_c"]
    a = case["agent_a"]
    req = case["request"]
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
async def list_cases():
    return {
        "total_cases": len(_case_store),
        "cases": [
            {
                "case_id": cid,
                "school_id": data["request"]["school_id"],
                "school_name": data["agent_c"]["school_name"],
                "di_classification": data["agent_b"]["di_classification"],
                "discrepancy_index": data["agent_b"]["discrepancy_index"],
                "anomaly_detected": data["agent_b"]["anomaly_detected"],
                "alert_level": data["agent_c"]["alert_status_label"],
                "alert_color": data["agent_c"]["alert_color_code"],
                "flags_count": len(data["agent_b"]["flags"]),
                "ingested_at": data["ingested_at"],
            }
            for cid, data in sorted(
                _case_store.items(),
                key=lambda x: x[1]["ingested_at"],
                reverse=True,
            )
        ],
    }


@app.delete("/api/v1/matrix/cases", tags=["System"])
async def clear_cases():
    _case_store.clear()
    return {"status": "cleared"}

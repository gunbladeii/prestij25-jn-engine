"""
Agent B — Cross-Examination & Anomaly Detection Agent
PRESTIJ-25 | Jemaah Nazir Smart Check & Balance Engine

Computes the Discrepancy Index (DI) by cross-referencing operational scores
from external matrix payloads against static Jemaah Nazir audit records.
Flags data manipulation, over-reporting, and visibility gaps.

DI Formula:  DI = abs(AuditScore - OperationalScore) / 100
DI Range:    [0.0, 1.0]  —  0.0 = perfect alignment, 1.0 = extreme discrepancy
"""

import uuid
from dataclasses import dataclass, field
from datetime import datetime, date
from typing import Optional
from agents.agent_a import AgentAResult

# ---------------------------------------------------------------------------
# Static Jemaah Nazir Audit Database (simulation)
# In production, this resolves via async DB query to jn_audit_records table.
# ---------------------------------------------------------------------------
JN_AUDIT_DATABASE: dict[str, dict] = {
    "SKB001": {
        "skpmg2_score": 85.50, "facility_gred": "A",
        "canteen_hygiene_score": 88.00, "integrity_risk_index": 0.120,
        "last_audit_date": date(2023, 3, 15), "school_name": "SK Bandar Baru Nilai",
        "state": "Negeri Sembilan",
    },
    "SKB002": {
        "skpmg2_score": 72.00, "facility_gred": "B",
        "canteen_hygiene_score": 65.00, "integrity_risk_index": 0.350,
        "last_audit_date": date(2022, 11, 20), "school_name": "SK Bukit Jelutong",
        "state": "Selangor",
    },
    "SMK001": {
        "skpmg2_score": 91.20, "facility_gred": "A",
        "canteen_hygiene_score": 92.00, "integrity_risk_index": 0.080,
        "last_audit_date": date(2024, 1, 10), "school_name": "SMK Tun Hussein Onn",
        "state": "W.P. Kuala Lumpur",
    },
    "SMK002": {
        "skpmg2_score": 58.00, "facility_gred": "C",
        "canteen_hygiene_score": 45.00, "integrity_risk_index": 0.680,
        "last_audit_date": date(2022, 8, 5), "school_name": "SMK Pendang",
        "state": "Kedah",
    },
    "SBP001": {
        "skpmg2_score": 94.80, "facility_gred": "A",
        "canteen_hygiene_score": 95.50, "integrity_risk_index": 0.040,
        "last_audit_date": date(2023, 9, 22), "school_name": "SBP Integrasi Gombak",
        "state": "Selangor",
    },
    "MRSM001": {
        "skpmg2_score": 88.30, "facility_gred": "A",
        "canteen_hygiene_score": 87.00, "integrity_risk_index": 0.095,
        "last_audit_date": date(2023, 6, 14), "school_name": "MRSM Kuala Klawang",
        "state": "Negeri Sembilan",
    },
    "SKK001": {
        "skpmg2_score": 63.50, "facility_gred": "C",
        "canteen_hygiene_score": 58.00, "integrity_risk_index": 0.420,
        "last_audit_date": date(2022, 5, 30), "school_name": "SK Kluang Utama",
        "state": "Johor",
    },
}

_DEFAULT_AUDIT_RECORD: dict = {
    "skpmg2_score": 70.00, "facility_gred": "B",
    "canteen_hygiene_score": 70.00, "integrity_risk_index": 0.300,
    "last_audit_date": date(2022, 1, 1), "school_name": "UNKNOWN",
    "state": "UNKNOWN",
}

# DI Classification thresholds (inclusive lower bound)
DI_THRESHOLDS: list[tuple[float, str]] = [
    (0.75, "EXTREME_DISCREPANCY"),
    (0.50, "SEVERE_DISCREPANCY"),
    (0.25, "MODERATE_DISCREPANCY"),
    (0.10, "MINOR_DISCREPANCY"),
    (0.00, "DATA_ALIGNED"),
]

# Audit staleness threshold (days)
AUDIT_STALENESS_DAYS = 1095  # 3 years


@dataclass
class AgentBResult:
    case_id: str
    school_id: str
    audit_record_found: bool
    audit_score_reference: float
    operational_score_reported: float
    score_delta: float
    discrepancy_index: float
    di_classification: str
    flags: list[str] = field(default_factory=list)
    anomaly_detected: bool = False
    confidence_score: float = 0.0
    audit_data_snapshot: dict = field(default_factory=dict)
    computed_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())


def _classify_di(di: float) -> str:
    for threshold, label in DI_THRESHOLDS:
        if di >= threshold:
            return label
    return "DATA_ALIGNED"


def _compute_confidence(di: float, flags: list[str], audit_found: bool) -> float:
    """
    Confidence in the anomaly detection output.
    Penalised when audit record is missing (fallback defaults used).
    """
    base = min(1.0, di * 1.5)
    flag_boost = min(0.3, len(flags) * 0.06)
    confidence = base + flag_boost
    if not audit_found:
        confidence *= 0.60  # 40% confidence penalty for missing reference data
    return round(min(1.0, confidence), 4)


def _generate_flags(
    di: float,
    operational_score: float,
    audit_score: float,
    audit_record: dict,
    agent_a: AgentAResult,
) -> list[str]:
    flags: list[str] = []

    if di >= 0.50:
        flags.append("POTENTIAL_DATA_MANIPULATION")

    if operational_score > audit_score and di > 0.30:
        flags.append("OPERATIONAL_OVER_REPORTING_DETECTED")

    if operational_score < audit_score and di > 0.30:
        flags.append("VISIBILITY_GAP_SUSPECTED")

    if audit_record.get("integrity_risk_index", 0) > 0.50:
        flags.append("HIGH_INTEGRITY_RISK_SCHOOL")

    if audit_record.get("canteen_hygiene_score", 100) < 50:
        flags.append("CANTEEN_HYGIENE_BELOW_THRESHOLD")

    if agent_a.severity == "CRITICAL":
        flags.append("CRITICAL_SEVERITY_REPORTED_BY_SOURCE")

    if agent_a.mapped_category == "Administrative Misconduct" and di > 0.20:
        flags.append("ADMINISTRATIVE_MISCONDUCT_CROSS_SIGNAL")

    # Audit staleness check
    last_audit = audit_record.get("last_audit_date")
    if isinstance(last_audit, date):
        days_since = (date.today() - last_audit).days
        if days_since > AUDIT_STALENESS_DAYS:
            flags.append(f"AUDIT_DATA_STALE_{days_since}_DAYS")

    if agent_a.processing_notes:
        for note in agent_a.processing_notes:
            if "MISMATCH" in note:
                flags.append("SCHOOL_CODE_IDENTIFIER_MISMATCH")
                break

    return flags


def run(
    school_id: str,
    operational_score: Optional[float],
    agent_a_result: AgentAResult,
    source_system_id: str,
) -> AgentBResult:
    """
    Entry point for Agent B.

    Args:
        school_id:          Target school identifier.
        operational_score:  Score reported by the external matrix system.
                            Pass None to use Agent A's AI-estimated score.
        agent_a_result:     Output from Agent A for this payload.
        source_system_id:   Source system identifier for the case ID namespace.

    Returns:
        AgentBResult with computed DI, classification, flags, and anomaly verdict.
    """
    case_id = f"PRESTIJ-{datetime.utcnow().strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    audit_record = JN_AUDIT_DATABASE.get(school_id.upper())
    audit_found = audit_record is not None
    if not audit_found:
        audit_record = _DEFAULT_AUDIT_RECORD.copy()

    audit_score = float(audit_record["skpmg2_score"])

    # Resolve operational score: explicit > AI-estimated > default
    if operational_score is not None:
        op_score = float(operational_score)
    elif agent_a_result.ai_estimated_operational_score is not None:
        op_score = float(agent_a_result.ai_estimated_operational_score)
    else:
        op_score = 50.0

    # Core DI computation — formula as specified
    di = abs(audit_score - op_score) / 100.0
    di = round(min(1.0, max(0.0, di)), 4)

    classification = _classify_di(di)
    flags = _generate_flags(di, op_score, audit_score, audit_record, agent_a_result)
    anomaly = di >= 0.25 or len(flags) >= 2
    confidence = _compute_confidence(di, flags, audit_found)

    return AgentBResult(
        case_id=case_id,
        school_id=school_id,
        audit_record_found=audit_found,
        audit_score_reference=audit_score,
        operational_score_reported=op_score,
        score_delta=round(op_score - audit_score, 2),
        discrepancy_index=di,
        di_classification=classification,
        flags=flags,
        anomaly_detected=anomaly,
        confidence_score=confidence,
        audit_data_snapshot={
            "skpmg2_score": audit_record["skpmg2_score"],
            "facility_gred": audit_record["facility_gred"],
            "canteen_hygiene_score": audit_record["canteen_hygiene_score"],
            "integrity_risk_index": audit_record["integrity_risk_index"],
            "school_name": audit_record.get("school_name", "N/A"),
            "state": audit_record.get("state", "N/A"),
            "last_audit_date": str(audit_record.get("last_audit_date", "N/A")),
            "audit_record_found": audit_found,
        },
    )

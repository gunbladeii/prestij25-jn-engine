"""
Agent A — Semantic Ingestion & Mapping Agent
PRESTIJ-25 | Jemaah Nazir Smart Check & Balance Engine

Performs NER-style entity extraction and semantic category mapping on
unstructured text payloads received from 24 external matrix systems.
"""

import re
import hashlib
from dataclasses import dataclass, field
from typing import Optional

# ---------------------------------------------------------------------------
# Category taxonomy: keyword → standardised domain mapping
# Weights reflect diagnostic specificity (higher = stronger signal)
# ---------------------------------------------------------------------------
CATEGORY_TAXONOMY: dict[str, list[tuple[str, float]]] = {
    "Facilities": [
        ("bangunan", 1.0), ("tandas", 1.2), ("kantin", 1.0), ("kemudahan", 0.8),
        ("infrastructure", 1.0), ("toilet", 1.2), ("canteen", 1.0), ("building", 0.8),
        ("rosak", 1.1), ("repair", 1.0), ("bocor", 1.3), ("elektrik", 1.0),
        ("air", 0.7), ("gelap", 1.1), ("padang", 0.8), ("perpustakaan", 0.9),
        ("makmal", 0.9), ("lab", 0.9), ("bilik", 0.8), ("dewan", 0.9),
    ],
    "Academic Quality": [
        ("pengajaran", 1.2), ("kurikulum", 1.3), ("akademik", 1.1), ("pdpc", 1.5),
        ("prestasi", 1.0), ("teaching", 1.2), ("curriculum", 1.3), ("exam", 1.0),
        ("ujian", 1.0), ("peperiksaan", 1.1), ("skor", 0.9), ("gred", 0.9),
        ("guru", 0.8), ("teacher", 0.8), ("kelas", 0.7), ("syllabus", 1.2),
        ("markah", 0.9), ("keputusan", 0.9), ("upsr", 1.4), ("pt3", 1.4), ("spm", 1.4),
    ],
    "Discipline": [
        ("disiplin", 1.3), ("ponteng", 1.4), ("buli", 1.5), ("attendance", 1.2),
        ("bullying", 1.5), ("gangster", 1.8), ("drug", 1.9), ("dadah", 1.9),
        ("vandalisme", 1.6), ("pergaduhan", 1.5), ("fight", 1.5), ("rokok", 1.4),
        ("smoking", 1.4), ("sexual", 2.0), ("seksual", 2.0), ("hamil", 1.8),
        ("samseng", 1.7), ("gengster", 1.8),
    ],
    "Administrative Misconduct": [
        ("salah guna", 1.8), ("rasuah", 2.0), ("corruption", 2.0), ("misuse", 1.7),
        ("fraud", 2.0), ("falsification", 2.0), ("rekod palsu", 2.0), ("penipuan", 1.9),
        ("manipulasi", 1.8), ("manipulation", 1.8), ("pecah amanah", 2.0),
        ("embezzlement", 2.0), ("wang", 0.7), ("kewangan", 0.9), ("peruntukan", 0.8),
        ("tender", 1.2), ("kontrak", 1.1), ("lantikan", 1.0), ("nepotism", 1.9),
    ],
}

SEVERITY_SIGNALS: dict[str, list[str]] = {
    "CRITICAL": [
        "kritikal", "critical", "bahaya", "emergency", "segera", "immediate",
        "severe", "extreme", "kecemasan", "maut", "death", "cedera", "injury",
        "sexual", "seksual", "assault", "dera",
    ],
    "HIGH": [
        "tinggi", "serius", "serious", "urgent", "high", "teruk", "major",
        "substantive", "significant", "rasuah", "corruption",
    ],
    "MEDIUM": [
        "sederhana", "moderate", "medium", "pertengahan", "average", "concern",
    ],
    "LOW": [
        "rendah", "low", "minor", "kecil", "small", "trivial", "ringan",
    ],
}

SCHOOL_CODE_PATTERN = re.compile(
    r'\b(SK[A-Z0-9\s]{1,30}|SMK[A-Z0-9\s]{1,30}|SJK[A-Z0-9\s]{1,30}|'
    r'MRSM[A-Z0-9\s]{1,20}|SBP[A-Z0-9\s]{1,20}|[A-Z]{2,4}\d{3,7})\b',
    re.IGNORECASE,
)


@dataclass
class AgentAResult:
    school_id: str
    detected_school_code: Optional[str]
    mapped_category: str
    category_confidence: float
    severity: str
    severity_confidence: float
    extracted_entities: dict = field(default_factory=dict)
    processing_notes: list[str] = field(default_factory=list)


def _score_categories(text: str) -> tuple[str, float]:
    """
    Weighted keyword scan across taxonomy.
    Returns best-matching category and a normalised confidence score [0,1].
    """
    scores: dict[str, float] = {cat: 0.0 for cat in CATEGORY_TAXONOMY}

    for category, kw_pairs in CATEGORY_TAXONOMY.items():
        for keyword, weight in kw_pairs:
            if keyword in text:
                scores[category] += weight

    total = sum(scores.values())
    if total == 0:
        return "Uncategorised", 0.0

    best_cat = max(scores, key=lambda c: scores[c])
    confidence = round(scores[best_cat] / total, 4)
    return best_cat, confidence


def _score_severity(text: str) -> tuple[str, float]:
    """
    Precedence-ordered severity detection with confidence.
    CRITICAL signals override lower-tier matches.
    """
    for level in ("CRITICAL", "HIGH", "MEDIUM", "LOW"):
        hits = [kw for kw in SEVERITY_SIGNALS[level] if kw in text]
        if hits:
            raw_confidence = min(1.0, len(hits) * 0.35)
            return level, round(raw_confidence, 4)
    return "UNKNOWN", 0.0


def run(school_id: str, raw_text: str, source_system_id: str) -> AgentAResult:
    """
    Entry point for Agent A.

    Args:
        school_id:        Declared school identifier from the incoming payload.
        raw_text:         Unstructured text content to analyse.
        source_system_id: Origin system identifier for provenance tracking.

    Returns:
        AgentAResult with all extracted fields populated.
    """
    normalised = raw_text.lower().strip()
    notes: list[str] = []

    # Entity: school code detection via regex NER
    code_match = SCHOOL_CODE_PATTERN.search(raw_text)
    detected_code = code_match.group(0).strip() if code_match else None
    if detected_code and detected_code.upper() != school_id.upper():
        notes.append(
            f"SCHOOL_CODE_MISMATCH: declared={school_id}, detected={detected_code}"
        )

    # Semantic category mapping
    mapped_category, cat_confidence = _score_categories(normalised)

    # Severity assessment
    severity, sev_confidence = _score_severity(normalised)

    # Ancillary entity extraction
    extracted_entities = {
        "source_system_id": source_system_id,
        "detected_school_code": detected_code,
        "declared_school_id": school_id,
        "text_char_count": len(raw_text),
        "text_word_count": len(raw_text.split()),
        "payload_checksum": hashlib.sha256(raw_text.encode()).hexdigest()[:16],
        "category_scores_summary": mapped_category,
        "severity_keywords_found": [
            kw for kw in SEVERITY_SIGNALS.get(severity, []) if kw in normalised
        ],
    }

    return AgentAResult(
        school_id=school_id,
        detected_school_code=detected_code,
        mapped_category=mapped_category,
        category_confidence=cat_confidence,
        severity=severity,
        severity_confidence=sev_confidence,
        extracted_entities=extracted_entities,
        processing_notes=notes,
    )

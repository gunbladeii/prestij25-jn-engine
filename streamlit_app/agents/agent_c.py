"""
Agent C — Executive Briefing & Policy Suggestion Agent
PRESTIJ-25 | Jemaah Nazir Smart Check & Balance Engine

Transforms anomaly alerts from Agent B into structured Executive Briefings
intended for the Minister of Education and senior KPM leadership.
When an Anthropic API key is provided, Claude Haiku generates dynamic formal
Bahasa Malaysia directives tailored to each case's specific findings.
"""

import json
from datetime import datetime
from dataclasses import dataclass, field
from agents.agent_a import AgentAResult
from agents.agent_b import AgentBResult

# ---------------------------------------------------------------------------
# Static enforcement matrix — used as fallback when API key is absent
# ---------------------------------------------------------------------------
ENFORCEMENT_MATRIX: dict[str, list[str]] = {
    "EXTREME_DISCREPANCY": [
        "Pengaktifan pasukan audit khas Jemaah Nazir dalam tempoh 24 jam — "
        "tanpa notis kepada pihak sekolah (protokol 'blind audit')",
        "Pembekuan serta-merta semua laporan prestasi dan rekod kewangan "
        "sekolah berkenaan sehingga siasatan forensik digital selesai",
        "Pemakluman segera kepada YBhg. Pengarah Pelajaran Negeri (JPN) "
        "dan Ketua Setiausaha Kementerian Pendidikan Malaysia",
        "Aktivasi modul perlindungan data PRESTIJ-25 — semua akses pentadbir "
        "sekolah kepada sistem EMIS dan APDM digantung sementara",
        "Cadangan penangguhan kelayakan sekolah daripada penerimaan anugerah "
        "atau pengiktirafan KPM sehingga status bersih disahkan",
        "Laporan forensik lengkap kepada SPRM jika bendera rasuah atau "
        "penipuan data dikonfirmasi dalam siasatan susulan",
    ],
    "SEVERE_DISCREPANCY": [
        "Kunjungan audit tidak dijadual (unannounced) dalam tempoh 48 jam "
        "oleh pasukan Jemaah Nazir rantau berkaitan",
        "Semakan silang menyeluruh data EMIS, APDM, dan SISPAA dengan rekod "
        "PPD dan JPN berkenaan — delta mesti didokumentasikan",
        "Temuduga berstruktur dengan Pengetua/Guru Besar dan Penolong Kanan "
        "oleh panel Jemaah Nazir dalam 5 hari bekerja",
        "Semakan rekod kewangan tiga tahun terakhir dan log akses sistem "
        "digital sekolah oleh Bahagian Audit Dalam KPM",
    ],
    "MODERATE_DISCREPANCY": [
        "Notis amaran rasmi Jemaah Nazir kepada Pengetua/Guru Besar dengan "
        "keperluan respons bertulis dalam 7 hari bekerja",
        "Pemantauan intensif melalui sistem EMIS selama 30 hari dengan "
        "laporan mingguan wajib kepada PPD berkenaan",
        "Semakan semula pelan pembangunan sekolah (SDP) dan penyelarasan "
        "dengan PPD untuk tindakan pembetulan",
        "Laporan susulan wajib kepada Jemaah Nazir dalam 14 hari bekerja",
    ],
    "MINOR_DISCREPANCY": [
        "Rekod sebagai kes 'perlu pemantauan' dalam sistem PRESTIJ-25",
        "Makluman kepada Pegawai Pendidikan Daerah (PPD) untuk pemantauan "
        "berkala tambahan dalam kitaran audit suku tahunan",
        "Notis nasihat kepada pihak sekolah untuk menyelaraskan pelaporan "
        "dengan piawaian SKPMG2",
    ],
    "DATA_ALIGNED": [
        "Rekod sebagai kes tertutup — data operasi konsisten dengan rekod "
        "audit rasmi Jemaah Nazir",
        "Pemantauan berkala standard mengikut jadual audit tahunan PRESTIJ-25",
    ],
}

POLICY_RECOMMENDATION_MAP: dict[str, dict[str, str]] = {
    "POTENTIAL_DATA_MANIPULATION": {
        "ref": "Akta Pendidikan 1996 — Seksyen 51(1) & Seksyen 117",
        "action": (
            "Cadangan pindaan kepada Garis Panduan Pelaporan Data Sekolah KPM untuk "
            "mewajibkan pengesahan digital berkod QR pada semua laporan SKPMG2. "
            "Setiap penyerahan laporan hendaklah dicap masa (timestamped) dan "
            "ditandatangani secara kriptografi oleh pegawai bertanggungjawab."
        ),
    },
    "VISIBILITY_GAP_SUSPECTED": {
        "ref": "Pekeliling Ikhtisas Bil. 3/2019 — Pengurusan Data Pendidikan",
        "action": (
            "Cadangan integrasi wajib modul pelaporan real-time ke dalam sistem APDM "
            "untuk menghapuskan jurang keterlihatan data antara operasi lapangan dan "
            "rekod pusat KPM. API-to-API sync wajib setiap 24 jam."
        ),
    },
    "HIGH_INTEGRITY_RISK_SCHOOL": {
        "ref": "PKPA Bil. 8/1991 — Panduan Pengurusan Kualiti Menyeluruh",
        "action": (
            "Cadangan pengkelasan formal sekolah berisiko tinggi (integrity_risk_index > 0.50) "
            "ke dalam program Pemantauan Intensif KPM-JPN yang dilaksanakan secara suku tahunan. "
            "Senarai sekolah ini hendaklah dikemaskini setiap bulan dalam pangkalan data PRESTIJ-25."
        ),
    },
    "OPERATIONAL_OVER_REPORTING_DETECTED": {
        "ref": "Arahan Perbendaharaan 2023 — Peraturan 56: Ketepatan Pelaporan",
        "action": (
            "Cadangan mekanisme semak-silang automatik antara skor operasi yang dilaporkan "
            "dan data peperiksaan awam (LEMBAGA PEPERIKSAAN) untuk mengesan inflasi skor "
            "sebelum ia mencapai pangkalan data rasmi KPM."
        ),
    },
    "CANTEEN_HYGIENE_BELOW_THRESHOLD": {
        "ref": "Peraturan Kebersihan Makanan 2009 (Pindaan 2021) — Jadual III",
        "action": (
            "Cadangan audit khas kantin sekolah oleh Pegawai Kesihatan Persekitaran (EHO) "
            "dalam tempoh 30 hari. Laporan EHO hendaklah diserahkan kepada JPN dan KPM "
            "sebelum lesen kantin diperbaharui."
        ),
    },
    "ADMINISTRATIVE_MISCONDUCT_CROSS_SIGNAL": {
        "ref": "Akta Suruhanjaya Pencegahan Rasuah Malaysia 2009 — Seksyen 17A",
        "action": (
            "Cadangan penubuhan mekanisme rujukan automatik kepada SPRM apabila "
            "bendera salah laku pentadbiran bertindih dengan DI > 0.20. Protokol "
            "kerahsiaan SPRM hendaklah diaktifkan secara bersamaan."
        ),
    },
}


@dataclass
class PolicyRecommendation:
    flag_trigger: str
    legal_reference: str
    recommended_action: str


@dataclass
class AgentCResult:
    case_id: str
    generated_at: str
    alert_status_label: str
    alert_color_code: str
    school_id: str
    school_name: str
    state: str
    source_system: str
    issue_domain: str
    severity: str
    discrepancy_index: float
    di_classification: str
    flags_triggered: list[str]
    audit_score_reference: float
    operational_score_reported: float
    score_delta: float
    enforcement_actions: list[str]
    policy_recommendations: list[PolicyRecommendation]
    executive_directive_text: str
    confidence_score: float


_ALERT_MAP: dict[str, tuple[str, str]] = {
    "EXTREME_DISCREPANCY":  ("MERAH — TINDAKAN SEGERA DIPERLUKAN", "#DC2626"),
    "SEVERE_DISCREPANCY":   ("JINGGA — TINDAKAN DALAM 48 JAM",     "#EA580C"),
    "MODERATE_DISCREPANCY": ("KUNING — PENYIASATAN DIPERLUKAN",    "#CA8A04"),
    "MINOR_DISCREPANCY":    ("BIRU — PEMANTAUAN DITINGKATKAN",     "#2563EB"),
    "DATA_ALIGNED":         ("HIJAU — DATA KONSISTEN",             "#16A34A"),
}


def _build_directive_text(
    agent_b: AgentBResult,
    agent_a: AgentAResult,
    school_name: str,
    state: str,
    enforcement_actions: list[str],
) -> str:
    now = datetime.utcnow()
    date_str = now.strftime("%d %B %Y")
    time_str = now.strftime("%H:%M UTC")
    delta_direction = "LEBIH TINGGI" if agent_b.score_delta > 0 else "LEBIH RENDAH"

    actions_formatted = "\n".join(
        f"    {i+1}. {action}" for i, action in enumerate(enforcement_actions)
    )

    flags_formatted = (
        "\n".join(f"    • {flag}" for flag in agent_b.flags)
        if agent_b.flags
        else "    (Tiada bendera risiko tambahan)"
    )

    return f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           PERINTAH EKSEKUTIF — SISTEM IMBANGAN SEMAK PINTAR                ║
║           Rujukan Kes: {agent_b.case_id:<52}║
║           PRESTIJ-25 | MoE Agentic AI Programme 2025                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tarikh    : {date_str}
Masa Jana : {time_str}

KEPADA    : YAB. MENTERI PENDIDIKAN MALAYSIA
            (Melalui: Ketua Pengarah Pelajaran Malaysia)
DARIPADA  : Nod Audit Agentik PRESTIJ-25 — Jemaah Nazir Smart Check & Balance Engine
TAHAP     : {_ALERT_MAP.get(agent_b.di_classification, ("TIDAK DIKETAHUI",""))[0]}

═══════════════════════════════════════════════════════════════════════════════
 A. MAKLUMAT SEKOLAH YANG DISIASAT
═══════════════════════════════════════════════════════════════════════════════

  Kod Sekolah    : {agent_b.school_id}
  Nama Sekolah   : {school_name}
  Negeri         : {state}
  Domain Isu     : {agent_a.mapped_category}
  Tahap Keparahan: {agent_a.severity} (keyakinan: {agent_a.severity_confidence:.0%})

═══════════════════════════════════════════════════════════════════════════════
 B. PENEMUAN ANALISIS DISCREPANCY INDEX (DI)
═══════════════════════════════════════════════════════════════════════════════

  Formula DI     : DI = |Skor Audit - Skor Operasi| / 100
  Skor Audit JN  : {agent_b.audit_score_reference:.2f}  [Rekod Rasmi Jemaah Nazir]
  Skor Dilaporkan: {agent_b.operational_score_reported:.2f}  [Sumber: Sistem Matrix Ekosistem]
  Delta Mutlak   : {abs(agent_b.score_delta):.2f} mata ({delta_direction} daripada audit rasmi)

  ┌─────────────────────────────────────────────────────┐
  │  INDEKS DISCREPANCY (DI) : {agent_b.discrepancy_index:.4f}                  │
  │  KLASIFIKASI             : {agent_b.di_classification:<26}│
  │  KEYAKINAN DETEKSI       : {agent_b.confidence_score:.0%}                         │
  └─────────────────────────────────────────────────────┘

  Bendera Risiko Dicetuskan:
{flags_formatted}

═══════════════════════════════════════════════════════════════════════════════
 C. TINDAKAN PENGUATKUASAAN YANG DISYORKAN
═══════════════════════════════════════════════════════════════════════════════

{actions_formatted}

═══════════════════════════════════════════════════════════════════════════════
 D. PERISYTIHARAN & PENGESAHAN
═══════════════════════════════════════════════════════════════════════════════

  Dokumen ini dijana secara automatik oleh Sistem Imbangan Semak Pintar
  Jemaah Nazir (PRESTIJ-25) menggunakan data audit rasmi Jemaah Nazir
  bertarikh {agent_b.audit_data_snapshot.get('last_audit_date', 'T/A')}.

  Semua tindakan penguatkuasaan yang disyorkan adalah tertakluk kepada:
  • Akta Pendidikan 1996 (Akta 550)
  • Perintah Am Bab 'D' — Tatatertib Perkhidmatan Awam
  • Arahan Tetap Ketua Pengarah Pelajaran Malaysia

  PENGESAHAN OLEH KETUA JEMAAH NAZIR MALAYSIA DIPERLUKAN
  SEBELUM PENGEDARAN RASMI DOKUMEN INI.

  ___________________________________    Tarikh: _______________
  [Tandatangan Ketua Jemaah Nazir]

  ___________________________________    Tarikh: _______________
  [Tandatangan Pengarah, Bahagian Audit]

[ Dijana oleh PRESTIJ-25 Engine | Rujukan Kes: {agent_b.case_id} ]
""".strip()


def _parse_ai_json(text: str) -> dict:
    text = text.strip()
    if "```" in text:
        for block in text.split("```"):
            block = block.strip()
            if block.startswith("json"):
                block = block[4:].strip()
            try:
                return json.loads(block)
            except (json.JSONDecodeError, ValueError):
                continue
        return {}
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return {}


def _run_with_ai(
    api_key: str,
    agent_a: AgentAResult,
    agent_b: AgentBResult,
    school_name: str,
    state: str,
) -> tuple[str, list[str], list[PolicyRecommendation]]:
    """
    Call Groq LLM to generate a dynamic formal BM executive directive,
    enforcement actions, and policy recommendations for this specific case.

    Returns (executive_directive_text, enforcement_actions, policy_recs).
    """
    from groq import Groq

    client = Groq(api_key=api_key)

    flags_text = "\n".join(f"- {f}" for f in agent_b.flags) if agent_b.flags else "- Tiada"
    ai_summary = agent_a.ai_category_summary or ""

    prompt_text = (
        "Anda adalah pegawai kanan sistem PRESTIJ-25, Jemaah Nazir Malaysia.\n\n"
        "Jana satu laporan audit eksekutif rasmi dalam Bahasa Malaysia berdasarkan dapatan berikut:\n\n"
        f"Sekolah: {school_name} ({agent_b.school_id}), Negeri: {state}\n"
        f"Domain Isu: {agent_a.mapped_category} | Keparahan: {agent_a.severity}\n"
        f"Skor Audit JN: {agent_b.audit_score_reference:.2f} | Skor Operasi: {agent_b.operational_score_reported:.2f}\n"
        f"Indeks Discrepancy (DI): {agent_b.discrepancy_index:.4f} — {agent_b.di_classification}\n"
        f"Bendera Risiko:\n{flags_text}\n"
        f"Ringkasan Dokumen: {ai_summary}\n\n"
        "Kembalikan HANYA objek JSON yang sah (tiada teks lain) dengan struktur berikut:\n"
        "{\n"
        '  "executive_directive": "<teks perintah eksekutif formal dalam BM, 3-5 perenggan>",\n'
        '  "enforcement_actions": ["<tindakan 1>", "<tindakan 2>"],\n'
        '  "policy_recommendations": [\n'
        '    {"flag": "<nama bendera>", "ref": "<rujukan undang-undang>", "action": "<cadangan>"}\n'
        "  ]\n"
        "}\n\n"
        "Panduan:\n"
        "- executive_directive: mulakan dengan 'ADALAH DENGAN INI DIPERINTAHKAN...', "
        "sebutkan sekolah, nilai DI, dan klasifikasi. Gunakan bahasa rasmi surat KPM.\n"
        "- enforcement_actions: 3-6 tindakan mengikut keparahan kes\n"
        "- policy_recommendations: cadangan dasar berdasarkan bendera risiko\n"
        "- Rujuk Akta Pendidikan 1996, Pekeliling Ikhtisas KPM, PKPA"
    )

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        max_tokens=1024,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": prompt_text}],
    )

    data = _parse_ai_json(response.choices[0].message.content)

    directive = data.get("executive_directive", "")
    if not directive:
        return "", [], []

    now = datetime.utcnow()
    date_str = now.strftime("%d %B %Y")
    time_str = now.strftime("%H:%M UTC")
    delta_direction = "LEBIH TINGGI" if agent_b.score_delta > 0 else "LEBIH RENDAH"

    full_directive = f"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           PERINTAH EKSEKUTIF — SISTEM IMBANGAN SEMAK PINTAR  [AI]          ║
║           Rujukan Kes: {agent_b.case_id:<52}║
║           PRESTIJ-25 | MoE Agentic AI Programme 2025                       ║
╚══════════════════════════════════════════════════════════════════════════════╝

Tarikh    : {date_str}
Masa Jana : {time_str}

KEPADA    : YAB. MENTERI PENDIDIKAN MALAYSIA
            (Melalui: Ketua Pengarah Pelajaran Malaysia)
DARIPADA  : Nod Audit Agentik PRESTIJ-25 — Jemaah Nazir Smart Check & Balance Engine
TAHAP     : {_ALERT_MAP.get(agent_b.di_classification, ("TIDAK DIKETAHUI",""))[0]}

═══════════════════════════════════════════════════════════════════════════════
 A. MAKLUMAT SEKOLAH YANG DISIASAT
═══════════════════════════════════════════════════════════════════════════════

  Kod Sekolah    : {agent_b.school_id}
  Nama Sekolah   : {school_name}
  Negeri         : {state}
  Domain Isu     : {agent_a.mapped_category}
  Tahap Keparahan: {agent_a.severity} (keyakinan: {agent_a.severity_confidence:.0%})

═══════════════════════════════════════════════════════════════════════════════
 B. PENEMUAN ANALISIS DISCREPANCY INDEX (DI)
═══════════════════════════════════════════════════════════════════════════════

  Formula DI     : DI = |Skor Audit - Skor Operasi| / 100
  Skor Audit JN  : {agent_b.audit_score_reference:.2f}  [Rekod Rasmi Jemaah Nazir]
  Skor Dilaporkan: {agent_b.operational_score_reported:.2f}  [AI-Anggaran daripada Dokumen]
  Delta Mutlak   : {abs(agent_b.score_delta):.2f} mata ({delta_direction} daripada audit rasmi)

  ┌─────────────────────────────────────────────────────┐
  │  INDEKS DISCREPANCY (DI) : {agent_b.discrepancy_index:.4f}                  │
  │  KLASIFIKASI             : {agent_b.di_classification:<26}│
  │  KEYAKINAN DETEKSI       : {agent_b.confidence_score:.0%}                         │
  └─────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
 C. PERINTAH EKSEKUTIF (DIJANA OLEH AI)
═══════════════════════════════════════════════════════════════════════════════

{directive}

═══════════════════════════════════════════════════════════════════════════════
 D. PERISYTIHARAN & PENGESAHAN
═══════════════════════════════════════════════════════════════════════════════

  Dokumen ini dijana secara automatik oleh Sistem Imbangan Semak Pintar
  Jemaah Nazir (PRESTIJ-25) dengan bantuan model AI Claude (Anthropic).

  Semua tindakan penguatkuasaan yang disyorkan adalah tertakluk kepada:
  • Akta Pendidikan 1996 (Akta 550)
  • Perintah Am Bab 'D' — Tatatertib Perkhidmatan Awam
  • Arahan Tetap Ketua Pengarah Pelajaran Malaysia

  PENGESAHAN OLEH KETUA JEMAAH NAZIR MALAYSIA DIPERLUKAN
  SEBELUM PENGEDARAN RASMI DOKUMEN INI.

  ___________________________________    Tarikh: _______________
  [Tandatangan Ketua Jemaah Nazir]

  ___________________________________    Tarikh: _______________
  [Tandatangan Pengarah, Bahagian Audit]

[ Dijana oleh PRESTIJ-25 Engine + AI | Rujukan Kes: {agent_b.case_id} ]
""".strip()

    enforcement_actions = data.get("enforcement_actions", [])
    if not isinstance(enforcement_actions, list):
        enforcement_actions = []

    policy_recs: list[PolicyRecommendation] = []
    for rec in data.get("policy_recommendations", []):
        if isinstance(rec, dict):
            policy_recs.append(
                PolicyRecommendation(
                    flag_trigger=rec.get("flag", "GENERAL"),
                    legal_reference=rec.get("ref", ""),
                    recommended_action=rec.get("action", ""),
                )
            )

    return full_directive, enforcement_actions, policy_recs


def run(
    payload_school_id: str,
    source_system_name: str,
    agent_a: AgentAResult,
    agent_b: AgentBResult,
    api_key: str = "",
) -> AgentCResult:
    """
    Entry point for Agent C.

    Args:
        payload_school_id:  School identifier from the original payload.
        source_system_name: Human-readable name of the originating matrix system.
        agent_a:            Semantic mapping result from Agent A.
        agent_b:            Anomaly detection result from Agent B.
        api_key:            Anthropic API key. If set, Claude Haiku generates
                            the executive directive dynamically.

    Returns:
        AgentCResult containing full executive brief, directive text,
        enforcement actions, and policy recommendations.
    """
    now = datetime.utcnow().isoformat()
    school_name = agent_b.audit_data_snapshot.get("school_name", "TIDAK DIKETAHUI")
    state = agent_b.audit_data_snapshot.get("state", "TIDAK DIKETAHUI")

    alert_label, alert_color = _ALERT_MAP.get(
        agent_b.di_classification, ("TIDAK DIKETAHUI", "#6B7280")
    )

    # Try AI path first
    if api_key:
        try:
            directive_text, enforcement_actions, policy_recs = _run_with_ai(
                api_key, agent_a, agent_b, school_name, state
            )
            if directive_text:
                return AgentCResult(
                    case_id=agent_b.case_id,
                    generated_at=now,
                    alert_status_label=alert_label,
                    alert_color_code=alert_color,
                    school_id=payload_school_id,
                    school_name=school_name,
                    state=state,
                    source_system=source_system_name,
                    issue_domain=agent_a.mapped_category,
                    severity=agent_a.severity,
                    discrepancy_index=agent_b.discrepancy_index,
                    di_classification=agent_b.di_classification,
                    flags_triggered=agent_b.flags,
                    audit_score_reference=agent_b.audit_score_reference,
                    operational_score_reported=agent_b.operational_score_reported,
                    score_delta=agent_b.score_delta,
                    enforcement_actions=enforcement_actions,
                    policy_recommendations=policy_recs,
                    executive_directive_text=directive_text,
                    confidence_score=agent_b.confidence_score,
                )
        except Exception:
            pass  # Fall through to static path

    # Static fallback path
    enforcement_actions = ENFORCEMENT_MATRIX.get(agent_b.di_classification, [])

    policy_recs_static: list[PolicyRecommendation] = []
    for flag in agent_b.flags:
        if flag in POLICY_RECOMMENDATION_MAP:
            rec_data = POLICY_RECOMMENDATION_MAP[flag]
            policy_recs_static.append(
                PolicyRecommendation(
                    flag_trigger=flag,
                    legal_reference=rec_data["ref"],
                    recommended_action=rec_data["action"],
                )
            )

    directive_text = _build_directive_text(
        agent_b, agent_a, school_name, state, enforcement_actions
    )

    return AgentCResult(
        case_id=agent_b.case_id,
        generated_at=now,
        alert_status_label=alert_label,
        alert_color_code=alert_color,
        school_id=payload_school_id,
        school_name=school_name,
        state=state,
        source_system=source_system_name,
        issue_domain=agent_a.mapped_category,
        severity=agent_a.severity,
        discrepancy_index=agent_b.discrepancy_index,
        di_classification=agent_b.di_classification,
        flags_triggered=agent_b.flags,
        audit_score_reference=agent_b.audit_score_reference,
        operational_score_reported=agent_b.operational_score_reported,
        score_delta=agent_b.score_delta,
        enforcement_actions=enforcement_actions,
        policy_recommendations=policy_recs_static,
        executive_directive_text=directive_text,
        confidence_score=agent_b.confidence_score,
    )

# SYSTEM CONTROLLER — Jemaah Nazir Smart Check & Balance Engine

> **Purpose:** Master reference document for ALL AI/agent interactions with this system.
> Any model, agent, or orchestrator MUST read this file before planning, coding, or deploying.
> This prevents hallucinated architecture, wrong URLs, dropped services, and out-of-sync plans.

---

## 1. SYSTEM IDENTITY

| Property | Value |
|----------|-------|
| **System Name** | Jemaah Nazir Smart Check & Balance Engine |
| **Programme** | PRESTIJ-25, MoE Agentic AI |
| **Tagline** | Supreme Truth & Audit Node |
| **Live Frontend** | `https://ai-agentic-complaint.netlify.app` |
| **Live Backend** | `https://prestij25-jn-engine.onrender.com` |
| **GitHub Org** | `gunbladeii` |
| **Primary Repo** | `gunbladeii/prestij25-jn-engine` |
| **Secondary Repo** | `gunbladeii/prestijAI` (legacy HTML only — DO NOT USE) |

---

## 2. ARCHITECTURE DIAGRAM

```mermaid
graph TB
    subgraph "Users / Browsers"
        U[Browser]
    end

    subgraph "Netlify (Static Hosting)"
        FE[Frontend<br/>index.html SPA<br/>ai-agentic-complaint.netlify.app]
    end

    subgraph "Render.com (Cloud Platform)"
        BE[Web Service<br/>prestij25-jn-engine<br/>Python 3.12 / FastAPI<br/>uvicorn]
        DB[(PostgreSQL 18<br/>prestij25-jn-db<br/>Free Tier 1GB)]
    end

    subgraph "GitHub"
        GH[gunbladeii/prestij25-jn-engine<br/>main branch]
    end

    subgraph "Local Dev (Docker)"
        DOCKER[Docker Compose<br/>engine + postgres:16-alpine<br/>localhost:8000]
    end

    U -->|HTTPS| FE
    FE -->|Proxy /api/* → 200 rewrite| BE
    BE -->|asyncpg| DB
    GH -->|Auto-Deploy| BE
    GH -->|Auto-Deploy| FE
    DOCKER -.->|Local dev only| BE
```

### Data Flow (Ingest Pipeline)

```mermaid
flowchart LR
    PAYLOAD[Matrix Payload<br/>from external AI system] --> INGEST[POST /api/v1/matrix/ingest]
    INGEST --> AGENT_A[Agent A<br/>Semantic Ingestion<br/>NER + Category Mapping]
    AGENT_A --> AGENT_B[Agent B<br/>Discrepancy Index<br/>Anomaly Detection]
    AGENT_B --> AGENT_C[Agent C<br/>Executive Brief<br/>Enforcement + Policy]
    AGENT_B --> DB_WRITE[(PostgreSQL<br/>matrix_payloads<br/>+ discrepancy_log)]
    AGENT_C --> DB_WRITE
    DB_WRITE --> API_READ[GET /api/v1/matrix/cases<br/>GET /api/v1/matrix/executive-brief/:id]
```

---

## 3. DEPLOYMENT TOPOGRAPHY

### Production (Live)

| Layer | Platform | Service Name | URL |
|-------|----------|-------------|-----|
| **Frontend** | Netlify | `ai-agentic-complaint` | `https://ai-agentic-complaint.netlify.app` |
| **Backend API** | Render (Web Service) | `prestij25-jn-engine` | `https://prestij25-jn-engine.onrender.com` |
| **Database** | Render (PostgreSQL) | `prestij25-jn-db` | Internal only |
| **Source** | GitHub | `gunbladeii/prestij25-jn-engine` | `main` branch |

### Critical Connection: Netlify Proxy

```
Netlify redirect rule (netlify.toml):
  /api/*  →  https://prestij25-jn-engine.onrender.com/api/:splat
  status 200, force true

Frontend JS:  const API = '';  // same-origin, relies on proxy
```

> ⚠️ **DO NOT** add full URLs in frontend JS. The Netlify proxy handles routing.
> ⚠️ **DO NOT** change the proxy target without updating `netlify.toml`.

### Local Development (Docker)

```bash
cd jemaah-nazir-engine/
docker compose up -d
# Engine:  http://localhost:8000
# Postgres: localhost:5432 (prestij / prestij25secret / jemaah_nazir)
# API Docs: http://localhost:8000/api/docs
```

---

## 4. FULL STACK & DEPENDENCIES

### Backend (Python)

| Package | Version | Purpose |
|---------|---------|---------|
| `fastapi` | 0.115.0 | API framework |
| `uvicorn[standard]` | 0.32.0 | ASGI server |
| `pydantic` | 2.9.2 | Validation |
| `asyncpg` | 0.30.0 | PostgreSQL async driver |
| `python-multipart` | 0.0.12 | Form parsing |
| `aiofiles` | 24.1.0 | Async file I/O |

### Frontend

| Tech | Details |
|------|---------|
| **Type** | Single Page Application (SPA) |
| **File** | Single `index.html` — all CSS/JS inline |
| **Fonts** | Barlow Condensed, IBM Plex Sans, IBM Plex Mono (Google Fonts) |
| **API Calls** | `fetch()` same-origin, proxied by Netlify |
| **State** | Server-side (PostgreSQL), fetched on page load |

### Database

| Property | Value |
|----------|-------|
| **Engine** | PostgreSQL 18 |
| **Production** | Render managed (`prestij25-jn-db`) |
| **Local** | `postgres:16-alpine` Docker image |
| **Driver** | `asyncpg` (async Python) |

---

## 5. FILE STRUCTURE

### Workspace Root: `c:\Users\HP\Documents\prestijProject\`

```
prestijProject/
├── SYSTEM_CONTROLLER.md          ← THIS FILE — master reference
├── promp1.txt                    ← scratch notes
│
├── webapps/                      ← PRODUCTION DEPLOYMENT (Netlify + Render)
│   ├── netlify.toml              ← Netlify config (publish dir, API proxy)
│   ├── render.yaml               ← Render Blueprint (web service + DB)
│   ├── .gitignore
│   ├── .git/                     ← git repo → gunbladeii/prestij25-jn-engine
│   ├── backend/
│   │   ├── main.py               ← FastAPI server (PostgreSQL-backed)
│   │   ├── requirements.txt
│   │   └── agents/
│   │       ├── __init__.py
│   │       ├── agent_a.py        ← Semantic ingestion / NER
│   │       ├── agent_b.py        ← Discrepancy index calculation
│   │       └── agent_c.py        ← Executive brief + enforcement
│   ├── frontend/
│   │   └── index.html            ← SPA (all CSS/JS inline)
│   └── database/
│       └── schema.sql            ← Full schema (4 tables, seed data)
│
└── jemaah-nazir-engine/          ← LOCAL DEV (Docker Compose)
    ├── docker-compose.yml
    ├── backend/
    │   ├── main.py               ← FastAPI (Docker variant)
    │   ├── requirements.txt
    │   └── agents/
    │       ├── __init__.py
    │       ├── agent_a.py
    │       ├── agent_b.py
    │       └── agent_c.py
    ├── database/
    │   └── schema.sql
    └── docs/
```

> ⚠️ **IMPORTANT:** `webapps/` is the PRODUCTION code. `jemaah-nazir-engine/` is a LOCAL DEV variant.
> They may diverge. When making changes, ensure the `webapps/` version is always updated.

---

## 6. API ENDPOINTS

Base URL: `https://prestij25-jn-engine.onrender.com`

### System

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Health check + DB status |
| `GET` | `/api/docs` | Swagger UI |

### Matrix Ingestion

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/v1/matrix/ingest` | Submit payload → runs Agent A→B→C pipeline |

**Request Body:**
```json
{
  "source_system_id": "PRESTIJ-INTEGRITY-07",
  "source_system_name": "AI Integrity Monitoring Agent",
  "source_version": "1.0.0",
  "school_id": "SMK002",
  "raw_text": "Laporan kritikal...",
  "operational_score": 96.5,
  "metadata": {}
}
```

### Cases & Briefs

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/matrix/cases` | List all cases (sorted by newest) |
| `GET` | `/api/v1/matrix/executive-brief/{case_id}` | Full brief for a case |
| `DELETE` | `/api/v1/matrix/cases` | Clear all cases |

---

## 7. DATABASE SCHEMA

### Production Tables (auto-created by `main.py` on startup)

#### `matrix_payloads` — Raw ingest log
```
id (UUID PK), source_system_id, source_system_name, source_version,
school_id, raw_text_extracted, operational_score, mapped_category,
severity_level, extracted_entities (JSONB), received_at (TIMESTAMPTZ)
```

#### `discrepancy_log` — Agent B/C output (THE main table for cases)
```
id (UUID PK), case_id (VARCHAR UNIQUE), school_id, school_name, state,
source_system_name, audit_score_reference, operational_score_reported,
score_delta, discrepancy_index, di_classification, flags (JSONB),
anomaly_detected (BOOL), confidence_score, agent_a_result (JSONB),
agent_c_result (JSONB), brief_content (JSONB), timestamp (TIMESTAMPTZ)
```

#### `jn_audit_records` — Seed audit data (7 schools)
```
school_id (PK), school_name, school_type, district, state,
last_audit_date, skpmg2_score, facility_gred,
canteen_hygiene_score, integrity_risk_index
```

### DI Classification Thresholds
| Range | Classification |
|-------|---------------|
| ≥ 0.75 | EXTREME DISCREPANCY |
| ≥ 0.50 | SEVERE DISCREPANCY |
| ≥ 0.25 | MODERATE DISCREPANCY |
| ≥ 0.10 | MINOR DISCREPANCY |
| < 0.10 | DATA ALIGNED |

Formula: `DI = |Audit Score − Operational Score| / 100`

---

## 8. ENVIRONMENT VARIABLES

### Render Web Service (`prestij25-jn-engine`)

| Key | Source | Purpose |
|-----|--------|---------|
| `DATABASE_URL` | From `prestij25-jn-db` | PostgreSQL connection string |
| `PYTHON_VERSION` | `3.12.0` | Python runtime |
| `RENDER_SERVICE_NAME` | `prestij25-jn-engine` | Environment identifier |
| `PORT` | Auto (Render) | Server port |

### Docker Compose (local)

| Key | Value |
|-----|-------|
| `DATABASE_URL` | `postgresql://prestij:prestij25secret@postgres:5432/jemaah_nazir` |
| `ENGINE_ENV` | `production` |
| `POSTGRES_DB` | `jemaah_nazir` |
| `POSTGRES_USER` | `prestij` |
| `POSTGRES_PASSWORD` | `prestij25secret` |

---

## 9. AGENT PIPELINE

### Agent A — Semantic Ingestion & Mapping
- **File:** `backend/agents/agent_a.py`
- **Function:** `agent_a.run(school_id, raw_text, source_system_id)`
- **Does:** NER-style entity extraction, category mapping (Facilities, Academic Quality, Discipline, Administrative Misconduct), severity classification
- **Returns:** `mapped_category`, `category_confidence`, `severity`, `severity_confidence`, `extracted_entities`, `processing_notes`

### Agent B — Discrepancy Index & Anomaly Detection
- **File:** `backend/agents/agent_b.py`
- **Function:** `agent_b.run(school_id, operational_score, agent_a_result, source_system_id)`
- **Does:** Compares operational score vs audit reference, calculates DI, flags anomalies
- **Returns:** `case_id`, `discrepancy_index`, `di_classification`, `flags`, `anomaly_detected`, `confidence_score`, `audit_data_snapshot`, `score_delta`

### Agent C — Executive Brief & Enforcement
- **File:** `backend/agents/agent_c.py`
- **Function:** `agent_c.run(payload_school_id, source_system_name, agent_a, agent_b)`
- **Does:** Generates executive directive, policy recommendations, enforcement actions
- **Returns:** `alert_status_label`, `alert_color_code`, `school_name`, `state`, `enforcement_actions`, `policy_recommendations`, `executive_directive_text`

---

## 10. DEPLOYMENT WORKFLOW

### Push-to-Deploy Pipeline

```
1. Edit files in webapps/
2. git add → git commit → git push origin main
3. Render: Auto-detects push → builds → deploys backend
4. Netlify: Auto-detects push → deploys frontend
5. No manual steps required
```

### Manual Redeploy (if needed)

- **Render:** Dashboard → `prestij25-jn-engine` → Manual Deploy → Deploy latest commit
- **Netlify:** Dashboard → `ai-agentic-complaint` → Deploys → Trigger deploy

### Database Note

- **PostgreSQL schema auto-creates** on first connection (IF NOT EXISTS)
- **Seed data auto-inserts** (7 Jemaah Nazir audit records, ON CONFLICT DO NOTHING)
- **Render free tier DB:** 1 GB storage, spins down with inactivity
- **Data persists** across Render spin-downs (this was the key migration from in-memory dict)

---

## 11. RULES FOR AI / AGENT INTERACTION

> **MANDATORY — Any AI model working on this system MUST follow these rules:**

### DO ✅

1. **READ THIS FILE FIRST** before any planning or coding
2. **All API paths** must start with `/api/v1/`
3. **Frontend API calls** use `const API = ''` (same-origin via Netlify proxy)
4. **Backend changes** go in `webapps/backend/` (production) — NOT `jemaah-nazir-engine/`
5. **Database queries** use `asyncpg` — parameterized with `$1, $2...`
6. **All POST ingest** must pass through Agent A → B → C pipeline
7. **Render URL scheme fix:** `postgres://` → `postgresql://` for asyncpg
8. **CORS:** wildcard `*` — safe because Netlify proxies same-origin
9. **Commit messages** in English, descriptive
10. **Test on live URLs** before declaring success

### DON'T ❌

1. **DO NOT** hardcode `localhost` URLs in production code
2. **DO NOT** use `gunbladeii/prestijAI` repo — it's legacy HTML only
3. **DO NOT** remove the Netlify proxy redirect — frontend breaks
4. **DO NOT** change the `render.yaml` service name — breaks Blueprint
5. **DO NOT** add new dependencies without updating `requirements.txt`
6. **DO NOT** use synchronous DB drivers — only `asyncpg` (async)
7. **DO NOT** bypass the Agent pipeline for ingest
8. **DO NOT** change the `case_id` format (`PRESTIJ-YYYYMMDD-XXXXXXXX`)
9. **DO NOT** assume data is in-memory — it's PostgreSQL
10. **DO NOT** modify `jemaah-nazir-engine/` when the production code is in `webapps/`

---

## 12. LIVE VERIFICATION CHECKLIST

Use these to verify system health after any change:

```bash
# 1. Backend health
curl https://prestij25-jn-engine.onrender.com/api/v1/health
# Expect: db_connected: true, agents_online: [Agent_A, Agent_B, Agent_C]

# 2. Frontend proxy health
curl https://ai-agentic-complaint.netlify.app/api/v1/health
# Expect: same JSON response

# 3. Frontend loads
curl -s https://ai-agentic-complaint.netlify.app/ | grep "AI-Complaint-MOE"
# Expect: title tag found

# 4. Ingest test
curl -X POST https://prestij25-jn-engine.onrender.com/api/v1/matrix/ingest \
  -H "Content-Type: application/json" \
  -d '{"source_system_id":"TEST-01","source_system_name":"Test","school_id":"SBP001","raw_text":"Test payload for verification","operational_score":93.0}'
# Expect: status ACCEPTED, case_id returned

# 5. Cases list
curl https://prestij25-jn-engine.onrender.com/api/v1/matrix/cases
# Expect: total_cases > 0, cases array
```

---

## 13. QUICK REFERENCE COMMANDS

### Local Dev
```powershell
# Start local stack
cd C:\Users\HP\Documents\prestijProject\jemaah-nazir-engine
docker compose up -d

# Check logs
docker compose logs -f engine

# Stop
docker compose down
```

### Git Workflow
```powershell
cd C:\Users\HP\Documents\prestijProject\webapps
git status
git add -A
git commit -m "descriptive message"
git push origin main
```

### Docker Cleanup
```powershell
docker compose down -v        # remove volumes (DB data too!)
docker compose build --no-cache
docker compose up -d
```

---

## 14. CURRENT STATE (Last Updated: 2026-06-23)

| Item | Status |
|------|--------|
| Frontend | ✅ Live at `ai-agentic-complaint.netlify.app` |
| Backend | ✅ Live at `prestij25-jn-engine.onrender.com` |
| Database | ✅ PostgreSQL connected (`db_connected: true`) |
| Data Persistence | ✅ Data survives Render spin-down |
| Favicon | ✅ Shield crest SVG (navy + gold) |
| Title | ✅ `AI-Complaint-MOE` |
| URL | ✅ Renamed from `prestij25-jn` → `ai-agentic-complaint` |
| 3 Agents | ✅ Agent A, B, C online |
| Demo Payloads | ✅ 3 test cases in DB |
| Render Free Tier | ⚠️ Spins down after 15 min idle |

---

> **This file is the SINGLE SOURCE OF TRUTH for system architecture.**
> If any AI model or agent suggests something that contradicts this document,
> REJECT the suggestion and point to this file.
>
> Maintainer: Update this file whenever architecture changes.

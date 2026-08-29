# RFI Nexus Data Mesh Intake & Central Repository

Monorepo workspace for **RFI Nexus Data Mesh Intake** — an automated system for ingesting, validating, schema-extracting, cataloging, and vector-indexing Request for Information (RFI) datasets across enterprise Data Mesh domains.

---

## 🏗️ Workspace Architecture

```
ClarION_Pysum/
├── package.json           # Root monorepo workspace configuration
├── README.md              # Project documentation & guidelines
├── load_rfi.py            # Layer 3: Neo4j Graph Database Loader Script
├── validate_rfi_json.py   # Pre-load JSON schema & naming consistency validator
├── analyze_patterns.py    # Graph pattern analysis & Louvain community detection
├── schemas/               # Shared JSON Schema definitions for RFI intake
│   ├── rfi_extraction_schema.json
│   └── rfi_extraction_example.json
├── apps/
│   ├── backend/           # Layer 1: Data Mesh Intake API (FastAPI - Port 8000)
│   │   ├── main.py        # FastAPI application & entrypoint
│   │   ├── requirements.txt # Dependencies: fastapi, uvicorn, pydantic, anthropic, supabase, httpx
│   │   ├── README.md
│   │   └── .env.example
│   └── frontend/          # React + Vite Application (Port 5173)
│       ├── package.json   # Dependencies: lucide-react, axios, react-hook-form, tailwindcss
│       ├── vite.config.js # Vite + Tailwind CSS configuration
│       └── src/
│           ├── App.jsx    # Interactive RFI Intake Portal component
│           └── IngestionDashboard.tsx # RFI ingestion dashboard
└── LAYER2/
    └── layer2/            # Layer 2: Central Repository (FastAPI - Port 8001)
        ├── alembic/       # PostgreSQL + pgvector database migrations
        ├── app/
        │   ├── main.py    # Central Repository API entrypoint
        │   ├── config.py  # Configuration & environment settings
        │   ├── database.py# Async SQLAlchemy database session engine
        │   ├── models/    # RFI, Consideration, and Audit Log ORM models
        │   ├── routers/   # Ingest & Search (Semantic & Hybrid Vector Search)
        │   └── services/  # SentenceTransformers (all-MiniLM-L6-v2) & Neo4j driver
        ├── tests/         # Pytest integration & unit test suite
        └── docker-compose.yml # PostgreSQL + pgvector container definition
```

---

## 🔄 Cross-Layer Integration Flow

1. **Ingestion & Validation (Layer 1)**: User uploads a PDF or JSON payload in the Frontend or directly to `POST http://localhost:8000/ingest`.
2. **Schema Verification & Forwarding**: Layer 1 validates the payload against Pydantic v2 schemas and forwards the record to **Layer 2** (`http://localhost:8001/rfi`).
3. **Vector Embedding & Audit Trail (Layer 2)**: Layer 2 computes per-consideration 384-dimensional embeddings, writes the record into PostgreSQL/pgvector, and records an immutable SHA-256 audit chain entry.
4. **Graph Enrichment (Layer 3 Bridge)**: Layer 2 bridges to Neo4j graph nodes using the exact merge key format `{rfi_id}-C{number}` for hybrid vector-graph queries.

---

## ⚡ Quick Start

### 1. Root Workspace Commands
From the repository root:
- **Run Frontend**: `npm run dev:frontend`
- **Run Layer 1 Backend**: `npm run dev:backend` (runs on port 8000)
- **Run Layer 2 Repository**: `npm run dev:layer2` (runs on port 8001)

### 2. Service Startup Steps

#### Layer 2 Database & Service (`LAYER2/layer2`)
```bash
cd LAYER2/layer2
docker compose up -d
alembic upgrade head
uvicorn app.main:app --reload --port 8001
```

#### Layer 1 Backend (`apps/backend`)
```bash
cd apps/backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

#### Frontend (`apps/frontend`)
```bash
cd apps/frontend
npm install
npm run dev
```

---

## 🧪 End-to-End Testing Instructions

Execute the following commands sequentially to verify the entire intake, vector storage, search, and audit chain pipeline:

### 1. Ingest RFI Record (Layer 1 ➔ Layer 2)
```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d @schemas/rfi_extraction_example.json | python3 -m json.tool
```
*Expected Output*: Look for `"status": "success"` and `"layer2_status": "forwarded"`.

### 2. Semantic Search (Layer 2 - Whole RFI Vector Search)
```bash
curl -s -X POST http://localhost:8001/search \
  -H "Content-Type: application/json" \
  -d '{"query": "proof of payment", "top_k": 3}' | python3 -m json.tool
```
*Expected Output*: Returns ranked RFIs with similarity scores (e.g. `score: 0.6668`).

### 3. Hybrid Search (Layer 2 - Per-Consideration Vector + Graph Recall)
```bash
curl -s -X POST http://localhost:8001/search/hybrid \
  -H "Content-Type: application/json" \
  -d '{"query": "proof of payment", "top_k": 3}' | python3 -m json.tool
```
*Expected Output*: Returns consideration merge key (e.g., `CT-2024-123456-12-00-SM01-001-C1`) with similarity score (e.g., `score: 0.7602`).

### 4. Duplicate Record Rejection
```bash
curl -s -X POST http://localhost:8000/ingest \
  -H "Content-Type: application/json" \
  -d @schemas/rfi_extraction_example.json | python3 -m json.tool
```
*Expected Output*: Returns `"layer2_status": "duplicate"`.

### 5. Audit Chain Integrity Verification
```bash
curl -s http://localhost:8001/rfi/<RFI_UUID>/audit | python3 -m json.tool
```
*Expected Output*: Returns `"chain_valid": true` with SHA-256 hash log.

---

## 📌 Planned Future Additions / TODO

> 📝 **UI Vector Search Integration (Planned)**:
> Currently, the search bar on the Frontend (`apps/frontend`) performs local client-side filtering. Connecting the UI directly to Layer 2's `POST /search/hybrid` endpoint for real-time vector search from the web interface is documented and planned for a future integration phase.

---

## 📦 Installed Tech Stack & Dependencies

### `apps/backend/requirements.txt`
- `fastapi` — High performance web framework for APIs
- `uvicorn` — Lightning-fast ASGI server implementation
- `pydantic` — Data validation and schema management
- `anthropic` — Anthropic Claude SDK for AI schema extraction
- `supabase` — Supabase Python Client for Data Mesh registry persistence
- `httpx` — Async HTTP client for Layer 2 record forwarding

### `LAYER2/layer2/pyproject.toml`
- `sqlalchemy` & `asyncpg` — Async PostgreSQL ORM driver
- `pgvector` — High performance vector similarity extension
- `sentence-transformers` — Embeddings generation (`all-MiniLM-L6-v2`)
- `alembic` — Database schema migration tool
- `neo4j` — Driver for Layer 3 graph database enrichment

### `apps/frontend/package.json`
- `tailwindcss` & `@tailwindcss/vite` — Utility-first CSS framework
- `lucide-react` — Icon set
- `axios` — HTTP client for backend API communication
- `react-hook-form` — Performant form state management & validation


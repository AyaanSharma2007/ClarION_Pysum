# ClarION Project Task & Implementation Checklist

## Project Overview
AI-based analytics feature for Medical RFI (Request for Information) Repository Application.

---

## 📋 Master Task Checklist

### Phase 1: Database Schema Updates (Supabase & Neo4j)
- [x] Enable `pgvector` extension in Postgres (`CREATE EXTENSION IF NOT EXISTS vector;`)
- [x] Add analytics columns to `rfi_intake` staging table (`department`, `category`, `urgency`, `summary`, `is_duplicate`, `resolved_at`, `embedding vector(384)`)
- [x] Create HNSW vector index (`rfi_intake_embedding_idx`) for fast cosine similarity search
- [x] Create Postgres stored procedure `match_rfis(query_embedding, similarity_threshold, match_count)`
- [x] Implement Neo4j schema graph merge operations:
  - `(RFI)-[:SUBMITTED_BY]->(Department)`
  - `(RFI)-[:HAS_CATEGORY]->(Category)`
  - `(RFI)-[:IS_SIMILAR_TO {similarity}]->(RFI)`
- [x] Update database init script (`scripts/init_db.py`) to apply schema changes & stored procedures automatically

### Phase 2: RFI Ingestion Pipeline Updates (FastAPI)
- [x] Implement Qwen-1.5B JSON prompt extraction (`department`, `category`, `urgency`, `summary`) in `analytics_enrichment.py`
- [x] Add sentence-transformers (`all-MiniLM-L6-v2`) 384-dimensional vector embedding generation
- [x] Store enriched JSON metadata + embedding vector in Supabase `rfi_intake` table
- [x] Trigger `pgvector` similarity search (`match_rfis`) with cosine similarity threshold > 0.85
- [x] Flag redundant/duplicate RFIs (`is_duplicate = True`)
- [x] Merge Neo4j graph nodes and `[:IS_SIMILAR_TO]` similarity relationships
- [x] Connect `enrich_rfi_analytics` into background tasks in `ingest.py`
- [x] Create database enrichment script (`scripts/enrich_existing_db.py`) for existing records

### Phase 3: Analytics API Endpoints (FastAPI)
- [x] Create router `apps/backend/app/api/analytics.py`
- [x] Implement `GET /analytics/department-metrics`: total RFIs and resolution times grouped by department (with fallback department inference)
- [x] Implement `GET /analytics/repeating-topics`: top clustered recurring questions (Neo4j graph edges + Supabase fallback)
- [x] Implement `GET /analytics/trends`: time-series data for daily RFI volume (30/60/90 days)
- [x] Implement `GET /analytics/kpis`: top-level summary KPIs (RFIs this month, Redundancy rate, Most problematic department, total all-time)
- [x] Write backend unit tests in `apps/backend/app/tests/test_analytics.py`

### Phase 4: Analytics Dashboard (React Frontend)
- [x] Build component `AnalyticsDashboard.jsx` with Recharts widgets:
  - Top-level KPI cards (RFIs This Month, Redundancy Rate %, Most Problematic Dept)
  - Department Volume Bar Chart (Total RFIs vs Resolved)
  - RFI Volume Trends Area Chart (30d / 60d / 90d toggle)
  - Top Repeating Questions table (Summary, Department, Frequency, Similarity)
  - Department Performance table (Total, Resolved, Unresolved, Avg Resolution Time)
- [x] Fix Header Duplication: Accept `showHeader` prop (default `false` when embedded in `App.jsx`) to avoid dual stacked headers
- [x] Integrate view switcher tab (**📋 RFIs Repository** / **📊 Analytics**) into main sticky header in `App.jsx`
- [x] Add `Analytics` option to `Header.jsx` tab navigation list

---

## 🔍 Verification & Build Status
- **Backend Tests:** 33 unit tests passed (`PYTHONPATH=. .venv/bin/pytest apps/backend/app/tests`)
- **Frontend Build:** Production Vite bundle built successfully with exit code 0 (`npm --prefix apps/frontend run build`)
- **Database Init:** `scripts/init_db.py` executed successfully
- **Data Enrichment:** `scripts/enrich_existing_db.py` enriched 25 database records with department, summary, urgency, and category fields

---

## 📌 Future Maintenance & Next Steps
- [ ] Add real-time WebSocket push updates for analytics when new RFIs are uploaded.
- [ ] Implement fine-grained department filtering on the Analytics Dashboard widgets.
- [ ] Add CSV export for repeating questions and department performance tables.

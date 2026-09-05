# RFI Nexus — Layer 2 Setup Guide

## Quick-start (local dev, no external keys needed)

```bash
# 1. From the project root, enter the layer2 directory
cd ClarION/layer2

# 2. Copy the env template
cp .env.example .env

# 3. Start Postgres + pgvector
docker compose up -d

# 4. Install Python dependencies (Python 3.11+)
pip install -e ".[dev]"

# 5. Run the database migration
alembic upgrade head

# 6. Start the API server
uvicorn app.main:app --reload

# 7. Open the interactive API docs
# → http://localhost:8000/docs
```

The first startup downloads `all-MiniLM-L6-v2` (~90 MB, cached at
`~/.cache/huggingface`). Subsequent starts are instant.

---

## Running the tests

```bash
# With docker-compose running and migration applied:
pytest tests/ -v
```

---

## Connecting Layer 1

Layer 1 should POST validated RFI records to:

```
POST http://localhost:8000/rfi
Content-Type: application/json
```

The expected payload is identical to `rfi_extraction_schema.json` in the project root.
See `rfi_extraction_example.json` for a working example.

For bulk loads (synthetic dataset, historical backfill):

```
POST http://localhost:8000/rfi/batch
Content-Type: application/json

{ "records": [ <RFICreate>, <RFICreate>, ... ] }   (max 500 per call)
```

---

## What Layer 3 and later layers can read

| Endpoint | Use case |
|---|---|
| `GET /rfi/{id}` | Full structured record with considerations, NCA, indication, workflow state |
| `POST /search` | Semantic search — embed a query and find similar RFIs |
| `GET /rfi/{id}/similar` | Pre-fetch candidates for the recommender (Layer 5) |
| `GET /rfi/{id}/audit` | Full hash-chained audit trail with `chain_valid` flag |
| Direct DB | Layer 4 (risk engine) can read `rfi.embedding` and `rfi.rfi_text` directly via `DATABASE_URL` for training |

---

## Environment variables reference

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | local postgres | asyncpg connection string |
| `EMBEDDING_BACKEND` | `sentence_transformers` | `sentence_transformers` or `voyage` |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Model name passed to the backend |
| `EMBEDDING_DIMENSION` | `384` | Must match the model's output dimension |
| `VOYAGE_API_KEY` | — | Required if `EMBEDDING_BACKEND=voyage` |
| `EXTRACTION_BACKEND` | `stub` | `stub` (no-op) or `claude` |
| `ANTHROPIC_API_KEY` | — | Required if `EXTRACTION_BACKEND=claude` |
| `AUTH_ENABLED` | `false` | Set `true` to enforce Supabase JWT auth |
| `SUPABASE_JWT_SECRET` | — | Required if `AUTH_ENABLED=true` |
| `SLA_HOURS_DEFAULT` | `72` | Hours before an SLA warning fires |
| `APP_ENV` | `development` | `development` (verbose logs, open CORS) or `production` |

---

## Step-by-step: Switching to Supabase

When your teammate shares the Supabase project URL and service-role key:

### 1. Get your connection string from Supabase

In the Supabase dashboard:
- **Settings → Database → Connection string**
- Choose **URI** format, select **Session mode** (port 5432)
- Copy the connection string — it looks like:
  ```
  postgresql://postgres.<project-ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
  ```

### 2. Update `.env`

```bash
DATABASE_URL=postgresql+asyncpg://postgres.<project-ref>:<password>@aws-0-eu-central-1.pooler.supabase.com:5432/postgres
```

Prefix `postgresql://` with `postgresql+asyncpg://` so SQLAlchemy uses the async driver.

### 3. Enable pgvector in Supabase

In the Supabase dashboard:
- **Database → Extensions → search "vector" → Enable**

Or via SQL editor:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

### 4. Run the migration against Supabase

The migration in `alembic/versions/001_initial_schema.py` creates all tables.
Run it once:

```bash
alembic upgrade head
```

Alembic reads `DATABASE_URL` from `.env` automatically and converts the asyncpg
driver to psycopg3 for the sync migration runner.

### 5. Set up Row-Level Security (RLS) for teams

In the Supabase SQL editor, after the migration runs:

```sql
-- Enable RLS on the RFI table
ALTER TABLE rfi ENABLE ROW LEVEL SECURITY;

-- Example: RA Clinical can see all RFIs
CREATE POLICY "ra_clinical_read_all" ON rfi
  FOR SELECT
  USING (auth.jwt() ->> 'team' = 'RA Clinical');

-- Example: Affiliates only see their own team's RFIs
CREATE POLICY "affiliates_own_rfis" ON rfi
  FOR SELECT
  USING (owner_team = auth.jwt() ->> 'team');

-- Repeat for INSERT/UPDATE as appropriate per team
```

Adjust the `owner_team` values to match what Layer 1 sets.

### 6. Enable Auth in Layer 2

Once Supabase Auth is configured:

```bash
# In .env:
AUTH_ENABLED=true
SUPABASE_JWT_SECRET=<from Supabase → Settings → API → JWT Secret>
```

Then add this middleware to `app/main.py` (the code is already
structured to receive this addition in one place):

```python
# app/middleware/auth.py  ← create this file
from fastapi import Request, HTTPException
import jwt  # pip install pyjwt

async def verify_jwt(request: Request, call_next):
    from app.config import settings
    if not settings.AUTH_ENABLED:
        return await call_next(request)

    token = request.headers.get("Authorization", "").removeprefix("Bearer ")
    if not token:
        raise HTTPException(status_code=401, detail="Missing token")
    try:
        jwt.decode(token, settings.SUPABASE_JWT_SECRET, algorithms=["HS256"])
    except jwt.InvalidTokenError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return await call_next(request)
```

```python
# In app/main.py — add after the CORS middleware:
from app.middleware.auth import verify_jwt
app.middleware("http")(verify_jwt)
```

---

## Step-by-step: Switching to Voyage AI embeddings

When you have a Voyage AI key:

### 1. Install the SDK

```bash
pip install voyageai
```

### 2. Update `.env`

```bash
EMBEDDING_BACKEND=voyage
EMBEDDING_MODEL=voyage-large-2
EMBEDDING_DIMENSION=1536
VOYAGE_API_KEY=pa-...
```

### 3. Run a new migration to widen the vector column

The initial schema uses `vector(384)`. Voyage produces `vector(1536)`:

```bash
alembic revision -m "widen_embedding_to_1536"
```

In the generated file:
```python
def upgrade():
    op.execute("ALTER TABLE rfi ALTER COLUMN embedding TYPE vector(1536)")
    # Drop and recreate the HNSW index with the new dimension
    op.execute("DROP INDEX IF EXISTS ix_rfi_embedding_hnsw")
    op.execute("""
        CREATE INDEX ix_rfi_embedding_hnsw ON rfi
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
    """)

def downgrade():
    op.execute("ALTER TABLE rfi ALTER COLUMN embedding TYPE vector(384)")
```

```bash
alembic upgrade head
```

### 4. Re-embed all existing records

A backfill script (`scripts/reembed.py`) is planned for Week 2. It will:
```python
# Pseudocode — implement once Voyage key is available
for rfi in session.scalars(select(RFI)):
    rfi.embedding = await embedding_service.encode_async(rfi.rfi_text)
await session.commit()
```

---

## Step-by-step: Activating Claude API extraction

When you have an Anthropic key:

### 1. Install the SDK

```bash
pip install anthropic
```

### 2. Update `.env`

```bash
EXTRACTION_BACKEND=claude
ANTHROPIC_API_KEY=sk-ant-...
```

### 3. That's it

The `ExtractionService._extract_via_claude()` method in
`app/services/extraction.py` is already written and wired in.
It will activate automatically on the next server start.

### 4. Backfill category on existing records (optional)

If you already have records stored with `category=null`, run:

```bash
# Create scripts/backfill_categories.py:
import asyncio
from sqlalchemy import select
from app.database import AsyncSessionLocal
from app.models.rfi import RFI
from app.services.extraction import extraction_service

async def main():
    async with AsyncSessionLocal() as session:
        rfis = await session.scalars(select(RFI).where(RFI.category == None))
        for rfi in rfis:
            if rfi.rfi_text:
                result = await extraction_service.extract(rfi.rfi_text)
                rfi.category = result.category
        await session.commit()

asyncio.run(main())
```

---

## Integration seams for other layers

### For the Layer 3 team (Neo4j / Knowledge Graph)

The tables you need to read:

| Table | Graph node | Merge key |
|---|---|---|
| `rfi` | `RFI` | `rfi_id` |
| `nca` | `MSC` | `country` |
| `therapeutic_area` | `Indication` | `name` |
| `ctr_article` | `CTRArticle` | `name` |
| `consideration` | `Consideration` | `(rfi_id, number)` |

Relationships to create in Neo4j (from the graph model image):

```cypher
MATCH (r:RFI {rfi_id: $rfi_id}), (m:MSC {country: $country})
MERGE (r)-[:SUBMITTED_TO]->(m)

MATCH (r:RFI {rfi_id: $rfi_id}), (i:Indication {name: $name})
MERGE (r)-[:INDICATION_TO]->(i)

MATCH (r:RFI {rfi_id: $rfi_id}), (c:Consideration {number: $number, rfi_id: $rfi_id})
MERGE (r)-[:HAS_CONSIDERATION]->(c)
```

You can either read directly from `DATABASE_URL` (read replica pattern)
or call `GET /rfi/{id}` for individual records and iterate.

### For the Layer 4 team (Risk Prediction)

Read `rfi.embedding` (the 384-dim vector) and `rfi.category` directly
from Postgres for training features. The `consideration.outcome_status`
column is your training label (null = unknown, "accepted" = positive outcome).

### For the Layer 5 team (Recommender)

Call `GET /rfi/{id}/similar?top_k=20` to get pre-ranked semantic candidates.
Re-rank these by `response_component.success_score` for your final output.
To promote a response to `response_component`, POST to (planned Layer 5 endpoint):
`POST /consideration/{id}/promote` — this is a stub endpoint ready for your team to implement.

---

## Deployment (when you're ready)

### Backend (Render or Fly.io)

```bash
# Render: set these in the Render dashboard environment variables:
DATABASE_URL=<supabase connection string>
EMBEDDING_BACKEND=sentence_transformers   # or voyage
VOYAGE_API_KEY=<if voyage>
EXTRACTION_BACKEND=stub                  # or claude
ANTHROPIC_API_KEY=<if claude>
AUTH_ENABLED=true
SUPABASE_JWT_SECRET=<from supabase>
APP_ENV=production

# Start command (Render):
uvicorn app.main:app --host 0.0.0.0 --port $PORT
```

### Run migrations in production

```bash
# Run once before starting the server (add to your deploy script):
alembic upgrade head
```

### Frontend (Vercel / teammates)

Set `NEXT_PUBLIC_API_URL=https://your-render-url.onrender.com` in Vercel's
environment variables. All Layer 2 endpoints are CORS-open in development;
in production, set `APP_ENV=production` and the CORS middleware will
restrict origins (add allowed URLs to the `allow_origins` list in `app/main.py`).

---

## Common troubleshooting

| Problem | Fix |
|---|---|
| `asyncpg.exceptions.UndefinedObjectError: type "vector" does not exist` | Run `CREATE EXTENSION IF NOT EXISTS vector` in Postgres, then `alembic upgrade head` |
| `sentence_transformers not found` | `pip install sentence-transformers` |
| `ModuleNotFoundError: anthropic` | `pip install anthropic` (only needed when `EXTRACTION_BACKEND=claude`) |
| `ModuleNotFoundError: voyageai` | `pip install voyageai` (only needed when `EMBEDDING_BACKEND=voyage`) |
| Startup hangs for 30+ seconds | First-time model download. Wait once; subsequent starts are instant. |
| `409 Conflict` on ingest | Layer 1 is sending a duplicate `rfi_id`. The record is already stored. |
| `chain_valid: false` in audit | A row in `audit_log` was modified after being written. Do not UPDATE audit rows. |

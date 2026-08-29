# Layer 2 — Central Repository: Implementation Guide (Updated)

**Status:** Revised after the decision to run semantic search natively inside Neo4j (Layer 3) instead of Postgres/pgvector.
**Audience:** This document is self-contained and written to be handed directly to a coding agent/IDE for implementation. It does not assume the reader has read any other project document.

---

## 1. What Layer 2 is, in one paragraph

Layer 2 is the system of record for every RFI (Request for Information) and its response. It stores structured facts — the RFI text, the response text, which national competent authority (NCA) issued it, its category, who owns it, when it arrived — in a relational database, and exposes that data over a small HTTP API. It does **not** do search-by-meaning, does **not** generate embeddings, and does **not** talk to any LLM or embedding model. That responsibility now belongs entirely to Layer 3 (the Neo4j knowledge graph). Layer 2's job is to be a fast, reliable, boring database of facts that both writes cleanly and reads back cleanly by ID or by structured filter.

---

## 2. Explicit scope boundaries

**Layer 2 DOES:**
- Accept validated RFI and response records and store them.
- Serve structured, filtered queries (by NCA, category, date range, owning team).
- Serve fast lookups by ID or list of IDs (this is how Layer 3's search results get "hydrated" into full records — see Section 6).
- Own ID generation. Every RFI and every response gets a UUID here, and that UUID is the join key every other layer must use to refer to that record.

**Layer 2 DOES NOT:**
- Generate or store vector embeddings.
- Perform semantic/similarity search.
- Call any embedding model or LLM API.
- Decide which records are "similar" to each other — that is Layer 3's job, using Neo4j's native vector index.

If a task looks like "find RFIs similar in meaning to X," it does not belong in this codebase. Route it to Layer 3.

---

## 3. Tech stack

| Component | Choice |
|---|---|
| Database | PostgreSQL (via Supabase, or plain Postgres for local dev) |
| API framework | FastAPI (Python) |
| Local dev environment | Docker Compose |
| Testing | pytest + FastAPI's TestClient |
| Auth (structured access control) | Supabase Auth / Postgres row-level security, scoped by `owner_team` |

No embedding library, no vector extension, and no LLM SDK are required for this layer. If any of those show up as a dependency here, that's a sign scope has drifted — stop and check against Section 2.

---

## 4. Database schema (final)

```sql
-- Reference tables
create table nca (
  id uuid primary key default gen_random_uuid(),
  country text not null,
  name text not null
);

create table ctr_article (
  id uuid primary key default gen_random_uuid(),
  article_number text not null,
  description text
);

create table therapeutic_area (
  id uuid primary key default gen_random_uuid(),
  name text not null
);

-- Core RFI table (maps to Neo4j's "Consideration" node — see Section 7)
create table rfi (
  id uuid primary key default gen_random_uuid(),
  rfi_text text not null,               -- maps to Neo4j Consideration.concern_text
  category text,
  nca_id uuid references nca(id),
  ctr_article_id uuid references ctr_article(id),
  therapeutic_area_id uuid references therapeutic_area(id),
  owner_team text not null,
  received_at timestamptz default now()
);

-- Response table (maps to Neo4j's "Response" node — see Section 7)
create table response (
  id uuid primary key default gen_random_uuid(),
  rfi_id uuid not null references rfi(id) on delete cascade,
  response_text text not null,          -- maps to Neo4j Response.response_text
  submitted_at timestamptz default now(),
  success_score float                    -- optional, filled in later by outcome tracking
);

-- Indexes for structured queries only (no vector index in this layer)
create index rfi_nca_category_idx on rfi (nca_id, category);
create index rfi_owner_team_idx on rfi (owner_team);
create index response_rfi_id_idx on response (rfi_id);
```

**No `embedding` column exists on either table.** If you are migrating an existing database that has one, drop it:

```sql
alter table rfi drop column if exists embedding;
drop index if exists rfi_embedding_idx;
```

The `pgvector` extension is not required by this layer and does not need to be installed.

---

## 5. Row-level security

Scope reads to the requesting team, with a permissive default to be tightened later:

```sql
alter table rfi enable row level security;

create policy "team_scoped_read"
on rfi for select
using (owner_team = current_setting('app.current_team', true));
```

Apply the same pattern to `response` via its `rfi_id` join if per-team scoping is required there too.

---

## 6. API contract (this is the source of truth — implement exactly this)

### `POST /rfi`
Create a new RFI record. Called by Layer 1 after validation.

Request:
```json
{
  "rfi_text": "string, required",
  "category": "string, optional",
  "nca_code": "string, required",
  "ctr_article_id": "uuid, optional",
  "therapeutic_area_id": "uuid, optional",
  "owner_team": "string, required"
}
```

Response `201`:
```json
{ "id": "uuid", "created_at": "timestamp" }
```

### `POST /rfi/{id}/responses`
Attach a response to an existing RFI.

Request:
```json
{ "response_text": "string, required" }
```

Response `201`:
```json
{ "id": "uuid", "rfi_id": "uuid", "created_at": "timestamp" }
```

### `GET /rfi/{id}`
Fetch one RFI with all of its responses. **This is the endpoint Layer 3 hydrates search results through.**

Response `200`:
```json
{
  "id": "uuid",
  "rfi_text": "string",
  "category": "string",
  "nca_code": "string",
  "owner_team": "string",
  "received_at": "timestamp",
  "responses": [
    { "id": "uuid", "response_text": "string", "submitted_at": "timestamp" }
  ]
}
```

### `GET /rfi?ids=<id1,id2,id3>`
Batch hydration endpoint. Given a list of IDs (as returned by Layer 3's vector search), return the full structured record for each. **This endpoint did not exist in the previous version of this layer and is now required.**

Response `200`: array of the same object shape as `GET /rfi/{id}`.

### `GET /rfi?nca=<code>&category=<cat>&owner_team=<team>`
Structured filter query, no IDs required. Any combination of query params is optional; omit for "all."

Response `200`: array of the same object shape as `GET /rfi/{id}` (responses may be omitted here for performance — return RFI-level fields only, add a `?include=responses` flag if needed).

### `GET /rfi/export?since=<timestamp>`
Bulk export endpoint for Layer 3's one-time and incremental embedding jobs. Layer 3 must **never** connect to this Postgres database directly — it pulls text to embed through this endpoint only.

Response `200`: paginated array of `{ id, rfi_text, responses: [{ id, response_text }] }`.

### Explicitly removed from this layer
`GET /rfi/search` (semantic search) is **not** part of this contract. Do not implement it here. If a ticket asks for it, it belongs in Layer 3.

---

## 7. The ID contract — read this before writing any code

This is the single most important coordination point with Layer 3, and the most common way this kind of split silently breaks.

- **Layer 2 is the authority on IDs.** Every `rfi.id` and `response.id` is generated here (`gen_random_uuid()`), once, at insert time.
- When Layer 3 creates the corresponding graph nodes (`Consideration` for an RFI, `Response` for a response), it **must reuse these exact same IDs** as the Neo4j node's identifying property. Do not let Neo4j generate its own IDs for these nodes.
- Field name mapping (same content, different names by convention on each side — do not rename either side to match the other):

| Postgres (Layer 2) | Neo4j (Layer 3) |
|---|---|
| `rfi.id` | `Consideration` node ID |
| `rfi.rfi_text` | `Consideration.concern_text` |
| `response.id` | `Response` node ID |
| `response.response_text` | `Response.response_text` |

If this mapping is violated anywhere (Neo4j generating its own IDs, or the text field going into the graph under a different property than `concern_text`/`response_text`), the two-hop search flow in Section 8 breaks silently — Neo4j will return IDs that don't resolve to anything in `GET /rfi/{id}`.

---

## 8. How this layer is used at query time (for context, not implemented here)

```
1. User submits a natural-language query.
2. Layer 3 embeds the query and runs db.index.vector.queryNodes(...) against Neo4j.
3. Neo4j returns a list of { id, score } — no structured details.
4. The caller sends those IDs to GET /rfi?ids=... on THIS layer.
5. This layer returns the full structured record for each ID.
6. The caller merges the score from step 3 with the record from step 5 for display.
```

Layer 2 only needs to implement step 4/5 correctly. Steps 1–3 and 6 are out of scope here.

---

## 9. Project structure

```
/layer2-repository/
  main.py                 # FastAPI app, route registration
  models.py                # Pydantic request/response models matching Section 6 exactly
  db.py                     # connection pool, query helpers
  routes/
    rfi.py                  # POST /rfi, GET /rfi/{id}, GET /rfi?ids=, GET /rfi (filters)
    responses.py             # POST /rfi/{id}/responses
    export.py                 # GET /rfi/export
  schema.sql                # Section 4, exactly as written
  tests/
    test_contract.py         # Section 10
  docker-compose.yml         # Section 11
  Dockerfile
  requirements.txt
```

---

## 10. Contract tests (write these before considering the layer "done")

```python
def test_create_and_fetch_rfi(client):
    r = client.post("/rfi", json={
        "rfi_text": "Please clarify the statistical analysis plan.",
        "category": "statistics",
        "nca_code": "DE",
        "owner_team": "RA Clinical",
    })
    assert r.status_code == 201
    rfi_id = r.json()["id"]

    r2 = client.get(f"/rfi/{rfi_id}")
    assert r2.status_code == 200
    assert r2.json()["rfi_text"] == "Please clarify the statistical analysis plan."
    assert r2.json()["responses"] == []

def test_add_response(client, existing_rfi_id):
    r = client.post(f"/rfi/{existing_rfi_id}/responses", json={
        "response_text": "The statistical analysis plan is provided in Appendix 4.",
    })
    assert r.status_code == 201

def test_batch_hydration(client, existing_rfi_ids):
    ids_param = ",".join(existing_rfi_ids)
    r = client.get(f"/rfi?ids={ids_param}")
    assert r.status_code == 200
    assert len(r.json()) == len(existing_rfi_ids)
    for item in r.json():
        assert set(item.keys()) >= {"id", "rfi_text", "category", "nca_code", "owner_team", "received_at", "responses"}

def test_structured_filter(client):
    r = client.get("/rfi?nca=DE&category=statistics")
    assert r.status_code == 200
    for item in r.json():
        assert item["category"] == "statistics"

def test_no_embedding_field_leaks_into_responses(client, existing_rfi_id):
    r = client.get(f"/rfi/{existing_rfi_id}")
    assert "embedding" not in r.json()

def test_search_endpoint_does_not_exist(client):
    r = client.get("/rfi/search?q=anything")
    assert r.status_code == 404
```

That last test is deliberate — it's a guardrail against scope creep back into semantic search on this layer.

---

## 11. Local development setup

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    ports: ["5432:5432"]
    environment:
      POSTGRES_PASSWORD: devpassword
      POSTGRES_DB: layer2
    volumes:
      - ./schema.sql:/docker-entrypoint-initdb.d/schema.sql

  api:
    build: .
    ports: ["8000:8000"]
    environment:
      DATABASE_URL: postgresql://postgres:devpassword@postgres:5432/layer2
    depends_on: [postgres]
```

`docker-compose up` should bring up a fully working, self-contained Layer 2 with schema pre-loaded, requiring nothing from any other layer.

---

## 12. Definition of done

- [ ] Schema in Section 4 applied, no `embedding` column anywhere, no vector index.
- [ ] All six endpoints in Section 6 implemented exactly as specified (paths, methods, request/response shapes).
- [ ] `GET /rfi/search` does not exist (returns 404).
- [ ] All tests in Section 10 pass.
- [ ] `docker-compose up` runs the full stack locally with zero external dependencies.
- [ ] `GET /rfi/export` is confirmed working against a sample of records — this is what unblocks Layer 3's embedding job, so treat it as high priority, not an afterthought.
- [ ] The ID mapping table in Section 7 has been shared with whoever owns Layer 3, and they've confirmed their graph population script reuses Postgres-generated IDs rather than generating its own.

-- =============================================================================
-- ClarION Platform Layer 2 — Supabase PostgreSQL + pgvector Schema
-- Source of Truth: Clarion_Bible.md (Section 7, Section 10, Section 14.1)
-- =============================================================================

-- 1. Enable vector extension for semantic search
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Lookup Tables
CREATE TABLE IF NOT EXISTS msc (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  msc_country TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS indication (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  indication_name TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS ctr_article (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ctr_article_name TEXT NOT NULL UNIQUE,
  description TEXT
);

-- 3. Core RFI Table (Submission / Document Level)
CREATE TABLE IF NOT EXISTS rfi (
  rfi_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  rfi_type TEXT NOT NULL CHECK (rfi_type IN ('validation', 'assessment')),
  status TEXT NOT NULL DEFAULT 'received'
    CHECK (status IN ('received', 'ready_for_response', 'awaiting_response', 'drafting', 'pending_approval', 'approved', 'submitted')),
  msc_id UUID REFERENCES msc(id),
  indication_id UUID REFERENCES indication(id),
  owner_team TEXT NOT NULL,
  source_document_ref TEXT,             -- Evidence Integrity: "Original" dimension
  received_at TIMESTAMPTZ DEFAULT NOW()
);

-- 4. Consideration Table: individual concern/question raised within an RFI.
-- consideration_id format: {rfi_id}-C{number} (Shared join key with Neo4j)
CREATE TABLE IF NOT EXISTS consideration (
  consideration_id TEXT PRIMARY KEY,
  rfi_id UUID NOT NULL REFERENCES rfi(rfi_id) ON DELETE CASCADE,
  concern_text TEXT NOT NULL,           -- Maps to Neo4j Consideration.concern_text
  ctr_article_id UUID REFERENCES ctr_article(id),
  embedding VECTOR(384),                -- pgvector semantic embedding (384-dim, e.g., all-MiniLM-L6-v2)
  cluster_id INT,                       -- Louvain cluster ID from Neo4j graph analysis
  is_hub_article BOOLEAN DEFAULT FALSE, -- Centrality hub flag from Neo4j
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. Response Table
CREATE TABLE IF NOT EXISTS response (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consideration_id TEXT NOT NULL REFERENCES consideration(consideration_id) ON DELETE CASCADE,
  response_text TEXT NOT NULL,          -- Maps to Neo4j Response.response_text
  embedding VECTOR(384),
  success_score FLOAT,
  approved_by TEXT,                     -- Null until GATE-001 is satisfied by human authorization
  approved_at TIMESTAMPTZ,
  submitted_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 6. Hash-Chained Audit Log (ALCOA+ Compliance & Evidence Integrity)
CREATE TABLE IF NOT EXISTS audit_log (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  record_id TEXT NOT NULL,
  record_type TEXT NOT NULL,
  event_type TEXT NOT NULL,
  actor TEXT NOT NULL,
  prev_hash TEXT,
  curr_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 7. Governance & Active Learning Tables (Section 14.1)
CREATE TABLE IF NOT EXISTS extraction_correction (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  consideration_id TEXT NOT NULL REFERENCES consideration(consideration_id),
  field_name TEXT NOT NULL,           -- e.g. 'ctr_article_id', 'msc_id'
  original_value TEXT,
  corrected_value TEXT NOT NULL,
  corrected_by TEXT NOT NULL,
  corrected_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS policy_override (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  policy_rule TEXT NOT NULL,          -- e.g. 'RFI-SLA-001'
  record_id TEXT NOT NULL,
  overridden_by TEXT NOT NULL,
  justification TEXT NOT NULL,        -- Required, never null
  overridden_at TIMESTAMPTZ DEFAULT NOW()
);

-- 8. Performance & Similarity Indexes
CREATE INDEX IF NOT EXISTS consideration_embedding_idx ON consideration USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS response_embedding_idx ON response USING hnsw (embedding vector_cosine_ops);
CREATE INDEX IF NOT EXISTS rfi_msc_idx ON rfi (msc_id);
CREATE INDEX IF NOT EXISTS rfi_owner_team_idx ON rfi (owner_team);
CREATE INDEX IF NOT EXISTS consideration_rfi_id_idx ON consideration (rfi_id);
CREATE INDEX IF NOT EXISTS audit_log_record_idx ON audit_log (record_id);

-- 9. Row-Level Security (RLS) Configuration
ALTER TABLE rfi ENABLE ROW LEVEL SECURITY;
ALTER TABLE consideration ENABLE ROW LEVEL SECURITY;
ALTER TABLE response ENABLE ROW LEVEL SECURITY;

-- Default permissive RLS policies for development / team-scoped access
-- Policy: RA Clinical team can view all RFIs
DROP POLICY IF EXISTS "ra_clinical_read_all" ON rfi;
CREATE POLICY "ra_clinical_read_all" ON rfi
  FOR SELECT
  USING (auth.jwt() ->> 'team' = 'RA Clinical' OR true); -- Permissive fallback for dev

-- Policy: Team members can access RFIs assigned to their team
DROP POLICY IF EXISTS "team_access_policy" ON rfi;
CREATE POLICY "team_access_policy" ON rfi
  FOR ALL
  USING (owner_team = auth.jwt() ->> 'team' OR auth.role() = 'authenticated' OR auth.role() = 'anon');


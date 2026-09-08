-- =============================================================================
-- ClarION Analytics — pgvector Migration for RFI Analytics
-- Phase 1: Enable pgvector, add embedding column to rfi_intake, create
--           match_rfis stored procedure for cosine similarity search.
-- =============================================================================

-- 1. Enable pgvector extension (idempotent)
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Add analytics columns to the rfi_intake table.
--    The rfi_intake table is the flat ingest table used by the Layer 1 pipeline.
--    We add: embedding (384-dim vector from all-MiniLM-L6-v2),
--            department, category, urgency, summary (extracted by Qwen),
--            is_duplicate (boolean flag for redundancy tracking),
--            resolved_at (timestamptz for resolution time metrics).
ALTER TABLE rfi_intake
  ADD COLUMN IF NOT EXISTS embedding vector(384),
  ADD COLUMN IF NOT EXISTS department TEXT,
  ADD COLUMN IF NOT EXISTS category TEXT,
  ADD COLUMN IF NOT EXISTS urgency TEXT CHECK (urgency IN ('High', 'Medium', 'Low')),
  ADD COLUMN IF NOT EXISTS summary TEXT,
  ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;

-- 3. Create HNSW index for fast cosine similarity search on the embedding column
CREATE INDEX IF NOT EXISTS rfi_intake_embedding_idx
  ON rfi_intake USING hnsw (embedding vector_cosine_ops);

-- 4. Create indexes for analytics aggregation queries
CREATE INDEX IF NOT EXISTS rfi_intake_department_idx ON rfi_intake (department);
CREATE INDEX IF NOT EXISTS rfi_intake_category_idx ON rfi_intake (category);
CREATE INDEX IF NOT EXISTS rfi_intake_ingested_at_idx ON rfi_intake (ingested_at);

-- 5. Stored procedure: match_rfis
--    Performs cosine similarity search against the rfi_intake table.
--    Returns the top N most similar RFIs above a given similarity threshold.
--    Usage: SELECT * FROM match_rfis(query_embedding, 0.85, 10);
CREATE OR REPLACE FUNCTION match_rfis(
  query_embedding vector(384),
  similarity_threshold float DEFAULT 0.85,
  match_count int DEFAULT 10
)
RETURNS TABLE (
  rfi_id TEXT,
  department TEXT,
  category TEXT,
  urgency TEXT,
  summary TEXT,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    ri.rfi_id,
    ri.department,
    ri.category,
    ri.urgency,
    ri.summary,
    1 - (ri.embedding <=> query_embedding) AS similarity
  FROM rfi_intake ri
  WHERE ri.embedding IS NOT NULL
    AND 1 - (ri.embedding <=> query_embedding) > similarity_threshold
  ORDER BY ri.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;

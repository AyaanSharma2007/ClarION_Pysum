import psycopg
from dotenv import load_dotenv
import os
import sys

def main():
    # Load environment variables from Layer 2
    load_dotenv(dotenv_path="LAYER2/layer2/.env")
    db_url = os.environ.get('DATABASE_URL')
    if not db_url:
        print("DATABASE_URL not found in LAYER2/layer2/.env. Skipping DB init.")
        sys.exit(0)
        
    # Alembic handles the ORM tables, but we need to create the Layer 1 staging table
    # psycopg needs postgresql:// instead of postgresql+asyncpg://
    url = db_url.replace('postgresql+asyncpg://', 'postgresql://').split('?')[0]
    
    try:
        conn = psycopg.connect(url)
    except Exception as e:
        print(f"Failed to connect to database: {e}")
        sys.exit(1)
        
    cur = conn.cursor()

    print("Creating rfi_intake staging table and enabling vector extension...")
    cur.execute('''
    CREATE EXTENSION IF NOT EXISTS vector;

    CREATE TABLE IF NOT EXISTS rfi_intake (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        rfi_id TEXT NOT NULL,
        due_date TEXT,
        response_date TEXT,
        submit_date TEXT,
        msc JSONB,
        indication JSONB,
        considerations JSONB,
        ingested_at TIMESTAMPTZ DEFAULT NOW(),
        owner_team TEXT,
        validation_status TEXT,
        department TEXT,
        category TEXT,
        urgency TEXT,
        summary TEXT,
        is_duplicate BOOLEAN DEFAULT FALSE,
        resolved_at TIMESTAMPTZ,
        embedding vector(384),
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS department TEXT;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS category TEXT;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS urgency TEXT;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS summary TEXT;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS is_duplicate BOOLEAN DEFAULT FALSE;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS resolved_at TIMESTAMPTZ;
    ALTER TABLE rfi_intake ADD COLUMN IF NOT EXISTS embedding vector(384);

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
    ''')

    print("Granting permissions for Supabase anon/authenticated roles...")
    cur.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON public.rfi_intake TO anon;')
    cur.execute('GRANT SELECT, INSERT, UPDATE, DELETE ON public.rfi_intake TO authenticated;')
    cur.execute('GRANT USAGE ON SCHEMA public TO anon;')
    cur.execute('GRANT USAGE ON SCHEMA public TO authenticated;')

    print("Disabling RLS on rfi_intake (backend internal table)...")
    cur.execute('ALTER TABLE public.rfi_intake DISABLE ROW LEVEL SECURITY;')

    conn.commit()
    print('Database initialization complete.')
    conn.close()

if __name__ == "__main__":
    main()

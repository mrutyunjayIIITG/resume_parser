import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
import logging

load_dotenv()

# Your Supabase Connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable is not set.")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

migration_sql = """
-- 1. Enable the vector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Drop the old JSON column and add the new math-optimized VECTOR column
ALTER TABLE resumes DROP COLUMN IF EXISTS embedding;
ALTER TABLE resumes ADD COLUMN embedding vector(384);

-- 3. Create search function
CREATE OR REPLACE FUNCTION match_resumes (
  query_embedding vector(384),
  match_threshold float,
  match_count int
)
RETURNS TABLE (
  id int,
  candidate_name varchar,
  email varchar,
  parsed_json json,
  similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    resumes.id,
    resumes.candidate_name,
    resumes.email,
    resumes.parsed_json,
    1 - (resumes.embedding <=> query_embedding) AS similarity
  FROM resumes
  WHERE 1 - (resumes.embedding <=> query_embedding) > match_threshold
  ORDER BY resumes.embedding <=> query_embedding
  LIMIT match_count;
END;
$$;
"""

def run_migration():
    try:
        engine = create_engine(DATABASE_URL)
        with engine.connect() as conn:
            # We need to run each part separately if using some drivers, 
            # but let's try the whole block first.
            logger.info("Executing production migration on Supabase...")
            conn.execute(text(migration_sql))
            conn.commit()
            logger.info("Migration successful! Your database is now a Vector Engine.")
    except Exception as e:
        logger.error(f"Migration failed: {e}")

if __name__ == "__main__":
    run_migration()

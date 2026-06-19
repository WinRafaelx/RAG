import os
import atexit
import psycopg
from psycopg_pool import ConnectionPool
from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Opt #4: Persistent connection pool — reuses TCP connections across queries
# instead of opening a new connection on every search call.
# ---------------------------------------------------------------------------
_pool: ConnectionPool | None = None

def _get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        db_url = os.getenv("DATABASE_URL")
        if not db_url:
            raise ValueError("DATABASE_URL environment variable is not set")
        _pool = ConnectionPool(
            conninfo=db_url,
            min_size=0,
            max_size=3,
            open=True,
            timeout=3.0,
            kwargs={"connect_timeout": 3},
        )
        atexit.register(_pool.close)
    return _pool


def get_connection():
    """Return a connection from the pool (use as context manager)."""
    return _get_pool().connection()


def init_db():
    dimension = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Enable pgvector extension
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

            # Check if table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_name = 'novel_chunks'
                );
            """)
            table_exists = cur.fetchone()[0]

            if table_exists:
                try:
                    # Retrieve typmod for the embedding column to check its dimension
                    cur.execute("""
                        SELECT att.atttypmod
                        FROM pg_attribute att
                        JOIN pg_class cls ON att.attrelid = cls.oid
                        WHERE cls.relname = 'novel_chunks' AND att.attname = 'embedding';
                    """)
                    row = cur.fetchone()
                    # typmod is the dimension (e.g. 1536 or 384)
                    if row and row[0] != dimension:
                        cur.execute("DROP TABLE IF EXISTS novel_chunks CASCADE;")
                        table_exists = False
                except Exception:
                    cur.execute("DROP TABLE IF EXISTS novel_chunks CASCADE;")
                    table_exists = False

            # Create/Recreate novel_chunks table
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS novel_chunks (
                    id TEXT PRIMARY KEY,
                    source_file TEXT,
                    chapter_number INT,
                    chapter_title TEXT,
                    chunk_index INT,
                    content TEXT,
                    char_count INT,
                    language TEXT,
                    characters TEXT[],
                    embedding vector({dimension})
                );
            """)
            conn.commit()


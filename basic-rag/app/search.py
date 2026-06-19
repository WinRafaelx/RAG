import argparse
import sys

from app.db import get_connection
from app.embeddings import get_embedding

def search_similar_chunks(query: str, limit: int = 5) -> None:
    try:
        query_embedding = get_embedding(query, is_query=True)
    except Exception as e:
        print(f"Error generating embedding for query: {e}", file=sys.stderr)
        return

    # Connect to PostgreSQL and query
    with get_connection() as conn:
        with conn.cursor() as cur:
            # pgvector cosine distance operator is <=>
            # pgvector L2 distance operator is <->
            # Let's use cosine distance (ascending for closest distance, i.e. highest similarity)
            cur.execute("""
                SELECT 
                    embedding <=> %s::vector AS distance,
                    chapter_number,
                    id,
                    content
                FROM novel_chunks
                ORDER BY embedding <=> %s::vector ASC
                LIMIT %s;
            """, (str(query_embedding), str(query_embedding), limit))
            
            rows = cur.fetchall()

    if not rows:
        print("No similar chunks found in database. Make sure chunks have been indexed.")
        return

    print(f"\nTop {len(rows)} most similar chunks:\n" + "=" * 50)
    for row in rows:
        distance, chapter_number, chunk_id, content = row
        score = 1.0 - distance # cosine similarity score
        preview = content[:500]
        
        print(f"Score/Distance: {score:.4f} (Distance: {distance:.4f})")
        print(f"Chapter:        {chapter_number}")
        print(f"Chunk ID:       {chunk_id}")
        print(f"Content Preview:\n{preview}")
        print("-" * 50)

def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def main() -> None:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Search similar chunks in the pgvector database.")
    parser.add_argument("query", type=str, help="The search query.")
    args = parser.parse_args()

    search_similar_chunks(args.query)

if __name__ == "__main__":
    main()

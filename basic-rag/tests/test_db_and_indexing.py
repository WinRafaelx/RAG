import json
import os
from unittest.mock import MagicMock, patch
import pytest
import psycopg

from app.db import get_connection, init_db
from app.embeddings import get_embedding
from app.index_chunks import index_chunks

# Set up test env DATABASE_URL in case it's different, but we have local .env loaded.
# Let's verify we can connect to PostgreSQL
def test_db_connection_and_init():
    try:
        # Initialize DB and tables
        init_db()
    except Exception as e:
        pytest.skip(f"Database is not accessible or not running: {e}")

    # If successfully initialized, verify table exists and we can insert
    with get_connection() as conn:
        with conn.cursor() as cur:
            # Check table exists
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_name = 'novel_chunks'
                );
            """)
            table_exists = cur.fetchone()[0]
            assert table_exists is True

@patch.dict(os.environ, {"EMBEDDING_PROVIDER": "openai", "EMBEDDING_MODEL": "text-embedding-3-small"})
@patch("app.embeddings.OpenAI")
def test_get_embedding(mock_openai_class):
    # Setup mocks
    mock_client = MagicMock()
    mock_openai_class.return_value = mock_client
    
    mock_response = MagicMock()
    mock_response.data = [MagicMock(embedding=[0.1] * 1536)]
    mock_client.embeddings.create.return_value = mock_response

    embedding = get_embedding("Hello")
    assert len(embedding) == 1536
    assert embedding[0] == 0.1
    mock_client.embeddings.create.assert_called_once_with(
        input=["Hello"],
        model="text-embedding-3-small"
    )

@patch("app.index_chunks.get_embedding")
def test_indexing_chunks(mock_get_embedding, tmp_path):
    dim = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    # Setup mock embedding
    mock_get_embedding.return_value = [0.05] * dim

    # Setup dummy chunk JSON file
    chunk_data = [
        {
            "id": "test_chapter:ch999:chunk0",
            "source_file": "test_chapter.txt",
            "chapter_number": 999,
            "chapter_title": "Test Title",
            "chunk_index": 0,
            "content": "This is test content.",
            "char_count": 21,
            "language": "th",
            "characters": ["ช็องมย็อง"]
        }
    ]

    json_file = tmp_path / "test_chunks.json"
    json_file.write_text(json.dumps(chunk_data), encoding="utf-8")

    try:
        init_db()
    except Exception as e:
        pytest.skip(f"Database is not accessible: {e}")

    # Run indexing function
    indexed_count = index_chunks(json_file)
    assert indexed_count == 1

    # Verify database state
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, content, characters, embedding FROM novel_chunks WHERE id = %s;", ("test_chapter:ch999:chunk0",))
            row = cur.fetchone()
            assert row is not None
            assert row[1] == "This is test content."
            assert row[2] == ["ช็องมย็อง"]
            
            # Retrieve vector and check dimension/value
            embedding_str = row[3]
            assert isinstance(embedding_str, str)
            # Parse it
            vals = [float(x) for x in embedding_str.strip("[]").split(",")]
            assert len(vals) == dim
            assert abs(vals[0] - 0.05) < 1e-5

            # Clean up test row
            cur.execute("DELETE FROM novel_chunks WHERE id = %s;", ("test_chapter:ch999:chunk0",))
            conn.commit()


from app.search import search_similar_chunks

@patch("app.search.get_embedding")
def test_search_similar_chunks(mock_get_embedding, capsys):
    dim = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    mock_get_embedding.return_value = [0.1] * dim

    try:
        init_db()
    except Exception as e:
        pytest.skip(f"Database is not accessible: {e}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Clean up if exists
            cur.execute("DELETE FROM novel_chunks WHERE id = %s;", ("test_search_id",))
            # Insert dummy vector
            cur.execute("""
                INSERT INTO novel_chunks (
                    id, source_file, chapter_number, chapter_title, chunk_index,
                    content, char_count, language, characters, embedding
                ) VALUES (
                    %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s::vector
                )
            """, (
                "test_search_id", "test.txt", 123, "Test Chapter Title", 1,
                "This content should match search.", 34, "th", ["ยูอีซ็อล"], str([0.1]*dim)
            ))
            conn.commit()

    # Run search
    search_similar_chunks("search query", limit=1)

    captured = capsys.readouterr()
    assert "test_search_id" in captured.out
    assert "Chapter:        123" in captured.out
    assert "This content should match search." in captured.out

    # Clean up test row
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM novel_chunks WHERE id = %s;", ("test_search_id",))
            conn.commit()

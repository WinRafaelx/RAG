import os
from unittest.mock import patch
import pytest

from app.mcp_server import search_novel_chunks
from app.db import init_db, get_connection

@patch("app.mcp_server.get_embedding")
def test_mcp_search_tool(mock_get_embedding):
    dim = int(os.getenv("EMBEDDING_DIMENSION", "384"))
    mock_get_embedding.return_value = [0.1] * dim

    try:
        init_db()
    except Exception as e:
        pytest.skip(f"Database is not accessible: {e}")

    with get_connection() as conn:
        with conn.cursor() as cur:
            # Clean up if exists
            cur.execute("DELETE FROM novel_chunks WHERE id = %s;", ("test_mcp_id",))
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
                "test_mcp_id", "test_mcp.txt", 777, "Test MCP Title", 1,
                "This content matches the MCP search tool.", 40, "th", ["ยูอีซ็อล"], str([0.1]*dim)
            ))
            conn.commit()

    # Call search tool function
    result = search_novel_chunks("match", limit=1)

    assert "test_mcp_id" in result
    assert "Chapter 777" in result
    assert "This content matches the MCP search tool." in result

    # Clean up test row
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM novel_chunks WHERE id = %s;", ("test_mcp_id",))
            conn.commit()

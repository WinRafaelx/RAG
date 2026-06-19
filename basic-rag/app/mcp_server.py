import os
import sys
import logging
import functools
import threading

# Suppress Hugging Face symlinks warning (belt-and-suspenders alongside HF_HUB_OFFLINE)
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from mcp.server.fastmcp import FastMCP
from app.db import get_connection
from app.embeddings import get_embedding

# Log to stderr so it doesn't pollute the stdio MCP transport
logging.basicConfig(
    stream=sys.stderr,
    level=logging.INFO,
    format="[mcp-server] %(asctime)s %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# Create MCP server named mount-hua-fan-book
mcp = FastMCP("mount-hua-fan-book")

# ---------------------------------------------------------------------------
# Opt #1/5: Tuning constants
# ---------------------------------------------------------------------------
_MAX_LIMIT = 10          # hard cap on results per call
_DEFAULT_LIMIT = 5       # Opt #5: lowered from 5 → 3 to save LLM tokens
_CONTENT_PREVIEW = 700   # Opt #2: max chars per chunk returned to agent


# ---------------------------------------------------------------------------
# Opt #3: Warm up the embedding model at server start in the main thread.
# This prevents deadlocks/race conditions with PyTorch during parallel request processing.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Opt #4: Connection pool is handled in app/db.py — get_connection() now
# returns a pooled connection instead of opening a new TCP socket each time.
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# In-process LRU cache — keyed on (query, limit).
# Holds up to 64 unique results so repeated identical tool calls are free.
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=64)
def _cached_search(query: str, limit: int) -> str:
    """Run the embedding + DB query and return a formatted string result.

    Results are cached so that repeated identical calls cost nothing.
    """
    logger.info("Cache MISS — embedding + DB query for: %r (limit=%d)", query, limit)

    try:
        query_embedding = get_embedding(query, is_query=True)
    except Exception as e:
        return (
            f"Error generating embedding for query: {e}\n"
            "[SEARCH COMPLETE] Failed to generate embedding. Do not retry."
        )

    try:
        with get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT
                        1 - (embedding <=> %s::vector) AS similarity,
                        chapter_number,
                        chapter_title,
                        id,
                        content
                    FROM novel_chunks
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT %s;
                    """,
                    (str(query_embedding), str(query_embedding), limit),
                )
                rows = cur.fetchall()
    except Exception as e:
        return (
            f"Error executing database query: {e}. "
            "Make sure the database is running and indexed.\n"
            "[SEARCH COMPLETE] Database error occurred. Do not retry."
        )

    if not rows:
        return (
            "No matching passages found in the database. "
            "Ensure chunks have been indexed using app.index_chunks.\n"
            "[SEARCH COMPLETE] 0 passages found. Do not retry with the same query."
        )

    lines = []
    lines.append(f"Top {len(rows)} matching novel passages for search query: '{query}'")
    lines.append("=" * 60)
    for index, row in enumerate(rows, 1):
        similarity, chapter_number, chapter_title, chunk_id, content = row

        # Opt #2: Truncate chunk content to save LLM input tokens.
        # Full chunks avg 1,172 chars; we cap at _CONTENT_PREVIEW chars.
        # The answer is almost always in the first paragraph.
        preview = content[:_CONTENT_PREVIEW]
        if len(content) > _CONTENT_PREVIEW:
            preview += "…"

        lines.append(
            f"{index}. Chapter {chapter_number}: {chapter_title} "
            f"(ID: {chunk_id}, Similarity: {similarity:.4f})"
        )
        lines.append("-" * 60)
        lines.append(preview)
        lines.append("=" * 60)

    # Structured footer — signals to the agent that the search is complete
    lines.append(
        f"[SEARCH COMPLETE] Returned {len(rows)} passage(s). "
        "This is the full result set available for this query. "
        "Do NOT call this tool again with the same or a very similar query — "
        "synthesize your answer from the passages above instead."
    )

    return "\n".join(lines)


@mcp.tool()
def search_novel_chunks(query: str, limit: int = _DEFAULT_LIMIT) -> str:
    """Search for matching passages in the "Return of the Mount Hua Sect" novel.

    Uses local semantic (vector) search — no external API is called.

    IMPORTANT USAGE RULES (read before calling):
    - Call this tool AT MOST ONCE per user question.
    - If the returned passages do not contain a perfect answer, synthesize the
      best answer you can from what is returned. Do NOT call again with a
      rephrased or similar query — the database contains all available data and
      a second call will not produce meaningfully different results.
    - Maximum useful limit is 10. Larger values are clamped automatically.

    Args:
        query: Search query in Thai or English describing the event, character
               action, or context you are looking for.
        limit: Maximum number of relevant passages to retrieve (default 3, max 10).

    Returns:
        Formatted string of matching passages ending with a [SEARCH COMPLETE]
        marker. Stop searching once you receive this marker.
    """
    # Safeguard: cap limit to prevent runaway large fetches
    capped_limit = min(max(1, limit), _MAX_LIMIT)
    if capped_limit != limit:
        logger.warning("limit clamped from %d to %d", limit, capped_limit)

    logger.info("search_novel_chunks called — query=%r limit=%d", query, capped_limit)

    result = _cached_search(query, capped_limit)

    info = _cached_search.cache_info()
    logger.info("Cache stats — hits=%d misses=%d size=%d", info.hits, info.misses, info.currsize)

    return result


if __name__ == "__main__":
    # Warm up the embedding model synchronously in the main thread before starting the server.
    # This prevents thread race conditions/deadlocks inside PyTorch.
    try:
        logger.info("Warming up E5 embedding model...")
        get_embedding("warmup", is_query=True)
        logger.info("Model warm-up complete — server is ready.")
    except Exception as exc:
        logger.warning("Model warm-up failed (non-fatal): %s", exc)

    # Start the FastMCP server on stdio transport
    mcp.run()

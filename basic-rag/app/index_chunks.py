import argparse
import json
import os
import sys
from pathlib import Path

# Suppress Hugging Face symlinks warning
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

from app.db import get_connection, init_db
from app.embeddings import get_embedding

def index_chunks(path: Path) -> int:
    # Ensure the DB schema exists
    init_db()

    # Find files to process
    if path.is_file():
        files = [path]
    elif path.is_dir():
        files = sorted(path.glob("*.json"))
    else:
        print(f"Error: path not found: {path}", file=sys.stderr)
        return 0

    if not files:
        print(f"No JSON chunk files found in {path}", file=sys.stderr)
        return 0

    total_indexed = 0
    with get_connection() as conn:
        with conn.cursor() as cur:
            for file_path in files:
                try:
                    with open(file_path, "r", encoding="utf-8") as f:
                        chunks = json.load(f)
                except Exception as e:
                    print(f"Error reading JSON from {file_path}: {e}", file=sys.stderr)
                    continue

                if not isinstance(chunks, list):
                    print(f"Error: expected JSON array in {file_path}", file=sys.stderr)
                    continue

                file_indexed = 0
                for index, chunk in enumerate(chunks):
                    chunk_id = chunk.get("id")
                    content = chunk.get("content", "")
                    if not chunk_id or not content:
                        continue

                    # Generate embedding
                    try:
                        embedding = get_embedding(content)
                    except Exception as e:
                        print(f"Error generating embedding for chunk {chunk_id}: {e}", file=sys.stderr)
                        continue

                    # Prepare fields
                    source_file = chunk.get("source_file")
                    chapter_number = chunk.get("chapter_number")
                    chapter_title = chunk.get("chapter_title")
                    chunk_index = chunk.get("chunk_index")
                    char_count = chunk.get("char_count", len(content))
                    language = chunk.get("language", "th")
                    characters = chunk.get("characters", [])

                    cur.execute("""
                        INSERT INTO novel_chunks (
                            id, source_file, chapter_number, chapter_title, chunk_index,
                            content, char_count, language, characters, embedding
                        ) VALUES (
                            %s, %s, %s, %s, %s,
                            %s, %s, %s, %s, %s::vector
                        )
                        ON CONFLICT (id) DO UPDATE SET
                            source_file = EXCLUDED.source_file,
                            chapter_number = EXCLUDED.chapter_number,
                            chapter_title = EXCLUDED.chapter_title,
                            chunk_index = EXCLUDED.chunk_index,
                            content = EXCLUDED.content,
                            char_count = EXCLUDED.char_count,
                            language = EXCLUDED.language,
                            characters = EXCLUDED.characters,
                            embedding = EXCLUDED.embedding;
                    """, (
                        chunk_id, source_file, chapter_number, chapter_title, chunk_index,
                        content, char_count, language, characters, str(embedding)
                    ))
                    file_indexed += 1
                
                conn.commit()
                total_indexed += file_indexed
                print(f"Indexed {file_indexed} chunks from {file_path.name}")

    return total_indexed

def _configure_utf8_output() -> None:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")

def main() -> None:
    _configure_utf8_output()
    parser = argparse.ArgumentParser(description="Index chunks JSON file or folder into pgvector database.")
    parser.add_argument("path", type=Path, help="Path to a chunk JSON file or directory containing JSON files.")
    args = parser.parse_args()

    count = index_chunks(args.path)
    print(f"\nFinished! Total indexed chunks: {count}")

if __name__ == "__main__":
    main()

# Basic Thai Novel RAG Ingestion

This Python 3.11+ project implements only the first layer of a Thai novel RAG pipeline: reading chapter `.txt` files, cleaning text, parsing chapter metadata, chunking paragraphs, attaching metadata, and exporting chunks to JSON.

It does not include embeddings, vector databases, retrieval, LLM calls, LangChain, or a frontend.

## Setup

Create a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

On Windows:

```powershell
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Run Tests

```bash
pytest
```

## Ingest One Chapter

```bash
python -m app.ingest data/724_chapter.txt
```

This prints the source file, chapter number, chapter title, paragraph count, chunk count, and the first 300 characters of each chunk.

## Export Chunks To JSON

```bash
python -m app.ingest data/724_chapter.txt --out chunks/724_chapter.json
```

## Export All Chapters To JSON

Process every `.txt` chapter in `data/` and write one JSON file per chapter into `chunks/`:

```bash
python -m app.ingest data --out chunks
```

With known characters:

```bash
python -m app.ingest data/724_chapter.txt --characters characters.txt --out chunks/724_chapter.json
```

For all chapters with known characters:

```bash
python -m app.ingest data --characters characters.txt --out chunks
```

## Discover Character Candidates

Generate a review list from the current chapters:

```bash
python -m app.character_candidates data --out character_candidates.md --json character_candidates.json
```

Review `character_candidates.md`, copy real character names into `characters.txt`, then regenerate chunks with:

```bash
python -m app.ingest data --characters characters.txt --out chunks
```

`characters.txt` should contain one character name per line.

## Example Output JSON

```json
[
  {
    "id": "724_chapter:ch724:chunk0",
    "source_file": "724_chapter.txt",
    "chapter_number": 724,
    "chapter_title": "ข้ากลับมาแล้ว (4)",
    "chunk_index": 0,
    "content": "ช็องมย็องเดินหน้ามุ่ยเข้ามา...",
    "char_count": 1200,
    "language": "th",
    "characters": ["ช็องมย็อง"]
  }
]
```

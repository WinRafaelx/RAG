import json

from app.chunk_qa import (
    analyze_chunk,
    analyze_chunks_dir,
    write_qa_json,
    write_qa_markdown,
)


def make_chunk(content, **overrides):
    chunk = {
        "id": "724_chapter:ch724:chunk0",
        "source_file": "724_chapter.txt",
        "chapter_number": 724,
        "chapter_title": "ข้ากลับมาแล้ว (4)",
        "chunk_index": 0,
        "content": content,
        "char_count": len(content),
        "language": "th",
        "characters": ["ช็องมย็อง"],
    }
    return {**chunk, **overrides}


def test_analyze_chunk_flags_suspicious_start_and_missing_characters():
    chunk = make_chunk("และเดินต่อไป", characters=[])

    result = analyze_chunk("724_chapter.json", chunk)

    assert result.file == "724_chapter.json"
    assert result.chunk_id == "724_chapter:ch724:chunk0"
    assert "suspicious_start" in result.warnings
    assert "no_characters" in result.warnings
    assert result.priority >= 2


def test_analyze_chunk_flags_open_quote_and_short_content():
    chunk = make_chunk("“สั้นมาก")

    result = analyze_chunk("724_chapter.json", chunk, min_chars=30)

    assert "too_short" in result.warnings
    assert "unbalanced_dialogue_quotes" in result.warnings


def test_analyze_chunk_counts_paragraphs_and_dialogue_start():
    chunk = make_chunk("“เริ่มพูด”\n\nช็องมย็องตอบ")

    result = analyze_chunk("724_chapter.json", chunk)

    assert result.paragraph_count == 2
    assert result.starts_with_dialogue is True
    assert result.character_count == 1


def test_analyze_chunks_dir_sorts_by_priority(tmp_path):
    chunks_dir = tmp_path / "chunks"
    chunks_dir.mkdir()
    (chunks_dir / "724_chapter.json").write_text(
        json.dumps(
                [
                    make_chunk("ช็องมย็องเดินต่อไป"),
                    make_chunk("และ", chunk_index=1, characters=[]),
                ],
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    results = analyze_chunks_dir(chunks_dir)

    assert [result.chunk_index for result in results] == [1, 0]
    assert results[0].priority > results[1].priority


def test_write_qa_markdown_and_json(tmp_path):
    chunk = make_chunk("และเดินต่อไป", characters=[])
    result = analyze_chunk("724_chapter.json", chunk)
    markdown_path = tmp_path / "qa.md"
    json_path = tmp_path / "qa.json"

    write_qa_markdown([result], markdown_path)
    write_qa_json([result], json_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert "Chunk QA Report" in markdown
    assert "suspicious_start" in markdown
    assert loaded[0]["chunk_id"] == "724_chapter:ch724:chunk0"

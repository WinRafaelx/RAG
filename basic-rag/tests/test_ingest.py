import json
import sys

import pytest

from app.ingest import (
    chunks_to_dicts,
    export_chunks_to_json,
    ingest_chapter_file,
    ingest_path,
    main,
    parse_chapter_file,
)


def test_parse_chapter_title_and_number(tmp_path):
    chapter_file = tmp_path / "chapter_724.txt"
    chapter_file.write_text(
        "ตอนที่ 724 — ข้ากลับมาแล้ว (4)\n\nช็องมย็องเดินเข้ามา\n\n“ข้าไม่เข้าใจเลยจริงๆ...”",
        encoding="utf-8",
    )

    chapter = parse_chapter_file(chapter_file)

    assert chapter.source_file == "chapter_724.txt"
    assert chapter.chapter_number == 724
    assert chapter.chapter_title == "ข้ากลับมาแล้ว (4)"
    assert chapter.paragraphs == ["ช็องมย็องเดินเข้ามา", "“ข้าไม่เข้าใจเลยจริงๆ...”"]


def test_parse_chapter_uses_none_when_metadata_is_missing(tmp_path):
    chapter_file = tmp_path / "unknown.txt"
    chapter_file.write_text("ไม่มีหัวตอน\n\nเนื้อหา", encoding="utf-8")

    chapter = parse_chapter_file(chapter_file)

    assert chapter.chapter_number is None
    assert chapter.chapter_title is None
    assert chapter.paragraphs == ["เนื้อหา"]


def test_parse_chapter_rejects_missing_and_non_txt_files(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_chapter_file(tmp_path / "missing.txt")

    chapter_file = tmp_path / "chapter.md"
    chapter_file.write_text("ตอนที่ 724 — ข้ากลับมาแล้ว (4)", encoding="utf-8")
    with pytest.raises(ValueError):
        parse_chapter_file(chapter_file)


def test_parse_empty_chapter_file(tmp_path):
    chapter_file = tmp_path / "empty.txt"
    chapter_file.write_text("\n\n", encoding="utf-8")

    chapter = parse_chapter_file(chapter_file)

    assert chapter.paragraphs == []
    assert chapter.chapter_number is None
    assert chapter.chapter_title is None


def test_export_chunks_to_json_preserves_thai_text(tmp_path):
    from app.models import Chunk

    output_file = tmp_path / "chunks" / "chapter_724.json"
    chunks = [
        Chunk(
            id="chapter_724:ch724:chunk0",
            source_file="chapter_724.txt",
            chapter_number=724,
            chapter_title="ข้ากลับมาแล้ว (4)",
            chunk_index=0,
            content="ช็องมย็องเดินเข้ามา",
            char_count=len("ช็องมย็องเดินเข้ามา"),
            characters=["ช็องมย็อง"],
        )
    ]

    export_chunks_to_json(chunks, output_file)

    loaded = json.loads(output_file.read_text(encoding="utf-8"))
    assert loaded == chunks_to_dicts(chunks)
    assert "ช็องมย็อง" in output_file.read_text(encoding="utf-8")


def test_ingest_chapter_file_exports_to_source_stem_json(tmp_path):
    chapter_file = tmp_path / "724_chapter.txt"
    output_dir = tmp_path / "chunks"
    chapter_file.write_text("ตอนที่ 724 — ข้ากลับมาแล้ว (4)\n\nเนื้อหา", encoding="utf-8")

    chapter, chunks, output_file = ingest_chapter_file(chapter_file, output_dir=output_dir)

    assert chapter.chapter_number == 724
    assert len(chunks) == 1
    assert output_file == output_dir / "724_chapter.json"
    assert output_file.exists()


def test_ingest_path_processes_all_txt_files_in_directory(tmp_path):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "chunks"
    data_dir.mkdir()
    (data_dir / "725_chapter.txt").write_text("ตอนที่ 725 — ชื่อหนึ่ง\n\nก", encoding="utf-8")
    (data_dir / "724_chapter.txt").write_text("ตอนที่ 724 — ชื่อสอง\n\nข", encoding="utf-8")
    (data_dir / "ignore.md").write_text("ignore", encoding="utf-8")

    results = ingest_path(data_dir, output_dir=output_dir)

    assert [result[0].source_file for result in results] == ["724_chapter.txt", "725_chapter.txt"]
    assert (output_dir / "724_chapter.json").exists()
    assert (output_dir / "725_chapter.json").exists()


def test_cli_prints_summary_and_exports_json(tmp_path, monkeypatch, capsys):
    chapter_file = tmp_path / "chapter_724.txt"
    output_file = tmp_path / "out" / "chapter_724.json"
    chapter_file.write_text(
        "ตอนที่ 724 — ข้ากลับมาแล้ว (4)\n\nช็องมย็องเดินเข้ามา",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m app.ingest", str(chapter_file), "--out", str(output_file)],
    )

    main()

    output = capsys.readouterr().out
    assert "source file: chapter_724.txt" in output
    assert "chunk count: 1" in output
    assert output_file.exists()


def test_cli_processes_directory(tmp_path, monkeypatch, capsys):
    data_dir = tmp_path / "data"
    output_dir = tmp_path / "chunks"
    data_dir.mkdir()
    (data_dir / "724_chapter.txt").write_text("ตอนที่ 724 — ชื่อ\n\nเนื้อหา", encoding="utf-8")
    monkeypatch.setattr(
        sys,
        "argv",
        ["python -m app.ingest", str(data_dir), "--out", str(output_dir)],
    )

    main()

    output = capsys.readouterr().out
    assert "processed files: 1" in output
    assert (output_dir / "724_chapter.json").exists()

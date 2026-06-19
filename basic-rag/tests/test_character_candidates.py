import json

from app.character_candidates import (
    discover_character_candidates,
    extract_candidate_names,
    write_candidates_json,
    write_candidates_markdown,
)


def test_extract_candidate_names_uses_context_verbs_and_prefixes():
    text = "ช็องมย็องกล่าวเสียงเบา แบ็กช็อนถามกลับ ท่านเจ้าสำนักตอบ"

    candidates = extract_candidate_names(text)

    assert "ช็องมย็อง" in candidates
    assert "แบ็กช็อน" in candidates
    assert "ท่านเจ้าสำนัก" not in candidates


def test_extract_candidate_names_strips_particles_and_rejects_fragments():
    text = "ช็องมย็องก็กล่าวขึ้น ฮยอนจงที่มองมา ยูมอง ซานกล่าว"

    candidates = extract_candidate_names(text)

    assert "ช็องมย็อง" in candidates
    assert "ฮยอนจง" in candidates
    assert "ช็องมย็องก็" not in candidates
    assert "ฮยอนจงที่" not in candidates
    assert "ยู" not in candidates
    assert "ซาน" not in candidates


def test_discover_character_candidates_counts_files_and_samples(tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "724_chapter.txt").write_text(
        "ช็องมย็องกล่าวเสียงเบา\n\nแบ็กช็อนถามกลับ\n\nช็องมย็องมองไปด้านหน้า",
        encoding="utf-8",
    )
    (data_dir / "725_chapter.txt").write_text(
        "แบ็กช็อนกล่าวกับช็องมย็อง\n\nฮยอนจงมองทุกคน",
        encoding="utf-8",
    )

    candidates = discover_character_candidates(data_dir, min_count=1)

    names = [candidate.name for candidate in candidates]
    assert names[:3] == ["ช็องมย็อง", "แบ็กช็อน", "ฮยอนจง"]
    assert candidates[0].total_count == 3
    assert candidates[0].context_hits == 2
    assert candidates[0].files == ["724_chapter.txt", "725_chapter.txt"]
    assert candidates[0].samples


def test_write_candidates_markdown_and_json(tmp_path):
    data_dir = tmp_path / "data"
    markdown_path = tmp_path / "candidates.md"
    json_path = tmp_path / "candidates.json"
    data_dir.mkdir()
    (data_dir / "724_chapter.txt").write_text("ช็องมย็องกล่าว ช็องมย็องถาม", encoding="utf-8")

    candidates = discover_character_candidates(data_dir, min_count=1)
    write_candidates_markdown(candidates, markdown_path)
    write_candidates_json(candidates, json_path)

    markdown = markdown_path.read_text(encoding="utf-8")
    loaded = json.loads(json_path.read_text(encoding="utf-8"))
    assert "ช็องมย็อง" in markdown
    assert loaded[0]["name"] == "ช็องมย็อง"

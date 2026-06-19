from app.characters import extract_known_characters, load_known_characters
from app.chunker import chunk_chapter
from app.models import Chapter


def make_chapter(paragraphs, chapter_number=724):
    return Chapter(
        source_file="724_chapter.txt",
        chapter_number=chapter_number,
        chapter_title="ข้ากลับมาแล้ว (4)" if chapter_number else None,
        raw_text="\n\n".join(paragraphs),
        paragraphs=paragraphs,
    )


def test_groups_normal_paragraphs_without_splitting_dialogue():
    paragraphs = [
        "ช็องมย็องเดินเข้ามา",
        "“ข้าไม่เข้าใจเลยจริงๆ...”",
        "ทว่าเขากลับต้องเงียบเสียงลง",
    ]
    chapter = make_chapter(paragraphs)

    chunks = chunk_chapter(chapter, max_chars=1200, overlap_chars=0)

    assert len(chunks) == 1
    assert chunks[0].content == "\n\n".join(paragraphs)
    assert "“ข้าไม่เข้าใจเลยจริงๆ...”" in chunks[0].content


def test_splits_by_paragraph_groups_when_max_chars_is_exceeded():
    chapter = make_chapter(["ก" * 20, "ข" * 20, "ค" * 20])

    chunks = chunk_chapter(chapter, max_chars=45, overlap_chars=0)

    assert [chunk.content for chunk in chunks] == ["ก" * 20 + "\n\n" + "ข" * 20, "ค" * 20]


def test_long_paragraph_fallback_split():
    chapter = make_chapter(["ก" * 55])

    chunks = chunk_chapter(chapter, max_chars=20, overlap_chars=0)

    assert [chunk.content for chunk in chunks] == ["ก" * 20, "ก" * 20, "ก" * 15]


def test_chunker_rejects_invalid_sizes():
    chapter = make_chapter(["เนื้อหา"])

    import pytest

    with pytest.raises(ValueError):
        chunk_chapter(chapter, max_chars=0)
    with pytest.raises(ValueError):
        chunk_chapter(chapter, overlap_chars=-1)


def test_chunker_skips_empty_paragraphs_and_flushes_before_long_paragraph():
    chapter = make_chapter(["", "ก" * 10, "ข" * 25])

    chunks = chunk_chapter(chapter, max_chars=20, overlap_chars=0)

    assert [chunk.content for chunk in chunks] == ["ก" * 10, "ข" * 20, "ข" * 5]


def test_overlap_behavior_adds_complete_previous_paragraph_to_next_chunk():
    chapter = make_chapter(["first paragraph", "second paragraph", "third paragraph"])

    chunks = chunk_chapter(chapter, max_chars=35, overlap_chars=20)

    assert chunks[1].content.startswith("second paragraph\n\n")
    assert chunks[1].char_count == len(chunks[1].content)


def test_overlap_does_not_start_in_middle_of_long_paragraph():
    chapter = make_chapter(["a long previous paragraph", "next paragraph"])

    chunks = chunk_chapter(chapter, max_chars=25, overlap_chars=5)

    assert chunks[1].content == "next paragraph"


def test_chunk_metadata_and_unknown_chapter_id():
    chapter = make_chapter(["ช็องมย็องพบแบ็กช็อน"], chapter_number=None)

    chunks = chunk_chapter(chapter, known_characters=["ช็องมย็อง", "แบ็กช็อน"])

    assert chunks[0].id == "724_chapter:ch_unknown:chunk0"
    assert chunks[0].source_file == "724_chapter.txt"
    assert chunks[0].chapter_number is None
    assert chunks[0].language == "th"
    assert chunks[0].characters == ["ช็องมย็อง", "แบ็กช็อน"]


def test_character_extraction_preserves_first_appearance_order():
    text = "แบ็กช็อนมองช็องมย็อง แล้วช็องมย็องก็หัวเราะ"

    characters = extract_known_characters(text, ["ช็องมย็อง", "แบ็กช็อน"])

    assert characters == ["แบ็กช็อน", "ช็องมย็อง"]


def test_load_known_characters_ignores_empty_lines(tmp_path):
    file_path = tmp_path / "characters.txt"
    file_path.write_text("\nช็องมย็อง\n\nแบ็กช็อน\n", encoding="utf-8")

    assert load_known_characters(file_path) == ["ช็องมย็อง", "แบ็กช็อน"]


def test_load_known_characters_rejects_missing_file(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        load_known_characters(tmp_path / "missing.txt")
